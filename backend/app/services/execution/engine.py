import json
import logging
import re
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, List, Optional, Set

from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Execution, NodeExecution, Server, Workflow
from app.config import BASE_DIR
from app.services.ssh_service import SSHService
from app.utils.time import utc_now

from .graph import GraphMixin
from .node_dispatch import NodeDispatchMixin
from .server_resolution import ServerResolutionMixin
from .context import ContextMixin
from .utils import UtilsMixin
from .handlers import (
    BasicHandlersMixin,
    IoTDBHandlersMixin,
    ClusterHandlersMixin,
    BenchmarkHandlersMixin,
    ControlHandlersMixin,
)

logger = logging.getLogger(__name__)

WEBHOOK_EXECUTION_LOG_DIR = BASE_DIR / "data" / "logs" / "executions"
SENSITIVE_KEY_PATTERN = re.compile(r"(password|passwd|secret|token|authorization|cookie|private[_-]?key)", re.IGNORECASE)


class ExecutionEngine(
    GraphMixin,
    NodeDispatchMixin,
    ServerResolutionMixin,
    ContextMixin,
    UtilsMixin,
    BasicHandlersMixin,
    IoTDBHandlersMixin,
    ClusterHandlersMixin,
    BenchmarkHandlersMixin,
    ControlHandlersMixin,
):
    """Service for managing workflow executions."""

    def __init__(
        self,
        db: Session,
        session_factory: Optional[Callable[[], Session]] = None,
        reservation_lock: Optional[RLock] = None
    ):
        self.db = db
        self.ssh_service = SSHService()
        self.session_factory = session_factory or sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=db.get_bind()
        )
        self.reservation_lock = reservation_lock or RLock()
        self._node_handlers: Dict[str, Callable] = {
            "shell": self._execute_shell_node,
            "upload": self._execute_upload_node,
            "download": self._execute_download_node,
            "config": self._execute_config_node,
            "iotdb_config": self._execute_iotdb_config_node,
            "log_view": self._execute_log_view_node,
            "iotdb_deploy": self._execute_iotdb_deploy_node,
            "iotdb_start": self._execute_iotdb_start_node,
            "iotdb_cli": self._execute_iotdb_cli_node,
            "iotdb_stop": self._execute_iotdb_stop_node,
            "iotdb_ainode_deploy": self._execute_iotdb_ainode_deploy_node,
            "iotdb_ainode_start": self._execute_iotdb_ainode_start_node,
            "iotdb_ainode_stop": self._execute_iotdb_ainode_stop_node,
            "iotdb_ainode_check": self._execute_iotdb_ainode_check_node,
            "iotdb_cluster_deploy": self._execute_iotdb_cluster_deploy_node,
            "iotdb_cluster_start": self._execute_iotdb_cluster_start_node,
            "iotdb_cluster_check": self._execute_iotdb_cluster_check_node,
            "iotdb_cluster_stop": self._execute_iotdb_cluster_stop_node,
            "iot_benchmark_deploy": self._execute_iot_benchmark_deploy_node,
            "iot_benchmark_start": self._execute_iot_benchmark_start_node,
            "iot_benchmark_wait": self._execute_iot_benchmark_wait_node,
            "condition": self._execute_condition_node,
            "loop": self._execute_loop_node,
            "wait": self._execute_wait_node,
            "parallel": self._execute_parallel_node,
            "assert": self._execute_assert_node,
        }

    def create_execution(
        self,
        workflow_id: int,
        trigger_type: str = "manual",
        triggered_by: Optional[str] = None
    ) -> Execution:
        execution = Execution(
            workflow_id=workflow_id,
            status="pending",
            trigger_type=trigger_type,
            triggered_by=triggered_by
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        logger.info("Created execution %s for workflow %s", execution.id, workflow_id)
        return execution

    def get_execution(self, execution_id: int) -> Optional[Execution]:
        return self.db.query(Execution).filter(Execution.id == execution_id).first()

    def list_executions(
        self,
        workflow_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Execution]:
        query = self.db.query(Execution)
        if workflow_id:
            query = query.filter(Execution.workflow_id == workflow_id)
        if status:
            query = query.filter(Execution.status == status)
        return query.order_by(Execution.created_at.desc()).limit(limit).all()

    def stop_execution(self, execution_id: int) -> Optional[Execution]:
        execution = self.get_execution(execution_id)
        if not execution:
            return None

        if execution.status in ["pending", "running"]:
            stopped_at = utc_now()
            execution.status = "stopped"
            execution.finished_at = stopped_at
            if execution.started_at:
                execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            workflow = self.db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
            summary = {
                **(execution.summary or {}),
                "stopped_at": stopped_at.isoformat(),
            }
            if workflow:
                summary.update({
                    "workflow_state": self._build_workflow_state_snapshot(
                        execution_id,
                        workflow.nodes or [],
                        workflow.edges or [],
                        {}
                    ),
                })
            execution.summary = summary
            self.db.commit()
            self.db.refresh(execution)
            logger.info("Stopped execution %s", execution_id)

        return execution

    def _is_stop_requested(self, execution_id: int) -> bool:
        status = self.db.query(Execution.status).filter(
            Execution.id == execution_id
        ).scalar()
        return status == "stopped"

    def _current_execution_summary(self, execution_id: int) -> Dict[str, Any]:
        summary = self.db.query(Execution.summary).filter(
            Execution.id == execution_id
        ).scalar()
        return dict(summary or {})

    def _finalize_webhook_execution(self, execution: Optional[Execution]) -> None:
        if execution is None or getattr(execution, "trigger_type", None) != "webhook":
            return

        try:
            WEBHOOK_EXECUTION_LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_path = WEBHOOK_EXECUTION_LOG_DIR / f"{execution.id}.jsonl"
            node_executions = self.db.query(NodeExecution).filter(
                NodeExecution.execution_id == execution.id
            ).order_by(NodeExecution.id.asc()).all()

            with open(log_path, "w", encoding="utf-8") as output:
                output.write(json.dumps({
                    "type": "execution",
                    "execution_id": execution.id,
                    "workflow_id": execution.workflow_id,
                    "status": execution.status,
                    "result": execution.result,
                    "duration": execution.duration,
                    "summary": self._redact_for_log(execution.summary or {}),
                }, ensure_ascii=False) + "\n")

                for node_execution in node_executions:
                    output_data = node_execution.output_data or {}
                    output.write(json.dumps({
                        "type": "node",
                        "node_execution_id": node_execution.id,
                        "node_id": node_execution.node_id,
                        "node_type": node_execution.node_type,
                        "status": node_execution.status,
                        "duration": node_execution.duration,
                        "started_at": node_execution.started_at.isoformat() if node_execution.started_at else None,
                        "finished_at": node_execution.finished_at.isoformat() if node_execution.finished_at else None,
                        "error_message": self._truncate_log_value(node_execution.error_message),
                        "stdout": self._truncate_log_value(output_data.get("stdout") if isinstance(output_data, dict) else None),
                        "stderr": self._truncate_log_value(output_data.get("stderr") if isinstance(output_data, dict) else None),
                        "error": self._truncate_log_value(output_data.get("error") if isinstance(output_data, dict) else None),
                    }, ensure_ascii=False) + "\n")

            for node_execution in node_executions:
                node_execution.log_path = str(log_path)
                node_execution.input_data = None
                node_execution.output_data = None

            execution.summary = {
                **(execution.summary or {}),
                "webhook_log_path": str(log_path),
                "node_details_pruned": True,
            }
        except Exception as exc:
            logger.exception("Failed to finalize webhook execution %s", execution.id)
            execution.summary = {
                **(execution.summary or {}),
                "webhook_log_error": str(exc),
            }

    def _redact_for_log(self, value):
        if isinstance(value, dict):
            return {
                key: "***"
                if SENSITIVE_KEY_PATTERN.search(str(key))
                else self._redact_for_log(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact_for_log(item) for item in value]
        return self._truncate_log_value(value)

    def _truncate_log_value(self, value, limit: int = 4000):
        if value is None:
            return None
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"

    def _cleanup_execution_processes(self, execution: Optional[Execution]) -> Dict[str, Any]:
        if execution is None:
            return {}

        node_executions = self.db.query(NodeExecution).filter(
            NodeExecution.execution_id == execution.id
        ).all()

        server_install_dirs: Dict[int, Set[str]] = {}
        for ne in node_executions:
            inp = ne.input_data or {}
            for sid, dirs in self._extract_server_dirs(inp).items():
                server_install_dirs.setdefault(sid, set()).update(dirs)

        if not server_install_dirs:
            return {}

        cleanup_results: Dict[str, Any] = {}
        for server_id, dirs in server_install_dirs.items():
            server = self.db.query(Server).filter(Server.id == server_id).first()
            if not server:
                continue
            parts = []
            for d in sorted(dirs):
                quoted = self._quote(d)
                parts.append(
                    f"cd {quoted} 2>/dev/null && "
                    f"for s in sbin/stop-*.sh; do [ -f \"$s\" ] && bash \"$s\" -f 2>/dev/null; done"
                )
                # 基于安装目录路径精准查找残留进程，先 SIGTERM 再 SIGKILL
                parts.append(
                    f"_pids=$(pgrep -f {quoted} 2>/dev/null); "
                    f"if [ -n \"$_pids\" ]; then kill $_pids 2>/dev/null; sleep 2; kill -9 $_pids 2>/dev/null; fi"
                )
            parts.append("echo cleanup_done")
            cmd = "; ".join(parts)
            try:
                result = self.ssh_service.run_command(
                    host=server.host,
                    username=server.username,
                    password=server.password,
                    command=cmd,
                    port=server.port,
                    timeout=30
                )
                cleanup_results[f"{server.host}({server_id})"] = {
                    "exit_status": result.exit_status,
                    "stdout": self._truncate_log_value(result.stdout, 500),
                    "dirs": list(dirs),
                }
            except Exception as exc:
                cleanup_results[f"{server.host}({server_id})"] = {"error": str(exc)}
        return cleanup_results

    def _extract_server_dirs(self, input_data: Dict[str, Any]) -> Dict[int, Set[str]]:
        result: Dict[int, Set[str]] = {}
        sid = input_data.get("server_id")
        if sid not in (None, ""):
            dirs = set()
            for key in ("iotdb_home", "ainode_home", "install_dir", "benchmark_home"):
                val = input_data.get(key)
                if val not in (None, ""):
                    dirs.add(str(val))
            if dirs:
                result[int(sid)] = dirs

        for group_key in ("config_nodes", "data_nodes"):
            group = input_data.get(group_key)
            if not isinstance(group, list):
                continue
            for item in group:
                if not isinstance(item, dict):
                    continue
                item_sid = item.get("server_id")
                if item_sid in (None, ""):
                    continue
                item_dir = item.get("install_dir") or item.get("iotdb_home")
                if item_dir not in (None, ""):
                    result.setdefault(int(item_sid), set()).add(str(item_dir))
        return result

    def execute_workflow(self, execution_id: int) -> None:
        execution = self.get_execution(execution_id)
        if not execution:
            logger.error("Execution %s not found", execution_id)
            return

        workflow = self.db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
        if not workflow:
            logger.error("Workflow %s not found", execution.workflow_id)
            execution.status = "failed"
            execution.finished_at = utc_now()
            self.db.commit()
            return

        if self._is_stop_requested(execution_id):
            logger.info("Execution %s was stopped before worker start", execution_id)
            return

        execution.status = "running"
        execution.started_at = utc_now()
        self.db.commit()

        nodes = workflow.nodes or []
        edges = workflow.edges or []
        workflow_context = {
            "_schedule_mode": workflow.schedule_mode,
            "_schedule_region": workflow.schedule_region,
        }
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        blocking_skipped_count = 0

        try:
            node_order, nodes_by_id, parents, children, edge_labels = self._build_execution_graph(nodes, edges)
            pending: Set[str] = set(node_order)
            running: Dict[Future, str] = {}
            statuses: Dict[str, str] = {}
            context_updates: Dict[str, Dict[str, Any]] = {}
            node_output_data: Dict[str, Dict[str, Any]] = {}
            loop_state: Dict[str, Dict[str, Any]] = {}
            control_flow_skipped: Set[str] = set()
            stop_requested = False

            max_workers = max(1, min(8, len(node_order) or 1))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while pending or running:
                    if self._is_stop_requested(execution_id):
                        stop_requested = True
                        for future, node_id in list(running.items()):
                            if future.cancel():
                                running.pop(future, None)
                                statuses[node_id] = "skipped"
                                skipped_count += 1
                                blocking_skipped_count += 1
                                self._create_skipped_node_execution(
                                    execution_id,
                                    nodes_by_id[node_id],
                                    "Skipped because execution was stopped"
                                )
                        for node_id in list(pending):
                            pending.remove(node_id)
                            statuses[node_id] = "skipped"
                            skipped_count += 1
                            blocking_skipped_count += 1
                            self._create_skipped_node_execution(
                                execution_id,
                                nodes_by_id[node_id],
                                "Skipped because execution was stopped"
                            )
                        if not running:
                            break

                    blocked = [
                        node_id for node_id in node_order
                        if node_id in pending and any(statuses.get(parent_id) in {"failed", "skipped"} for parent_id in parents[node_id])
                    ]
                    for node_id in blocked:
                        blocking_parents = [
                            parent_id for parent_id in parents[node_id]
                            if statuses.get(parent_id) in {"failed", "skipped"}
                        ]
                        is_control_flow_skip = bool(blocking_parents) and all(
                            statuses.get(parent_id) == "skipped" and parent_id in control_flow_skipped
                            for parent_id in blocking_parents
                        )
                        pending.remove(node_id)
                        statuses[node_id] = "skipped"
                        skipped_count += 1
                        if is_control_flow_skip:
                            control_flow_skipped.add(node_id)
                            reason = "Skipped because an upstream condition branch was not selected"
                        else:
                            blocking_skipped_count += 1
                            reason = "Skipped because an upstream node did not complete successfully"
                        self._create_skipped_node_execution(
                            execution_id,
                            nodes_by_id[node_id],
                            reason
                        )

                    ready = [
                        node_id for node_id in node_order
                        if node_id in pending and all(statuses.get(parent_id) == "success" for parent_id in parents[node_id])
                    ]
                    for node_id in ready:
                        pending.remove(node_id)
                        context = {
                            **workflow_context,
                            **self._merge_parent_contexts(parents[node_id], context_updates),
                        }
                        future = executor.submit(
                            self._execute_workflow_node,
                            execution_id,
                            nodes_by_id[node_id],
                            context
                        )
                        running[future] = node_id

                    if not running:
                        if pending:
                            for node_id in list(pending):
                                pending.remove(node_id)
                                statuses[node_id] = "skipped"
                                skipped_count += 1
                                blocking_skipped_count += 1
                                self._create_skipped_node_execution(
                                    execution_id,
                                    nodes_by_id[node_id],
                                    "Skipped because workflow graph contains a cycle or unreachable dependency"
                                )
                        break

                    done, _ = wait(running.keys(), return_when=FIRST_COMPLETED)
                    for future in done:
                        node_id = running.pop(future)
                        try:
                            node_result = future.result()
                        except Exception as exc:
                            logger.exception("Error executing node %s", node_id)
                            node_result = {
                                "status": "failed",
                                "context": {},
                                "error": str(exc)
                            }

                        status_value = str(node_result.get("status") or "failed")
                        statuses[node_id] = status_value
                        if status_value == "success":
                            passed_count += 1
                            context_updates[node_id] = dict(node_result.get("context") or {})
                            output_data = node_result.get("output_data") or {}
                            node_output_data[node_id] = output_data
                            node_type = nodes_by_id[node_id].get("type")

                            if node_type == "condition":
                                branch = str(output_data.get("branch", "true")).lower()
                                for child_id in children[node_id]:
                                    label = edge_labels.get((node_id, child_id), "").lower()
                                    if label and label != branch and child_id in pending:
                                        pending.remove(child_id)
                                        statuses[child_id] = "skipped"
                                        skipped_count += 1
                                        control_flow_skipped.add(child_id)
                                        self._create_skipped_node_execution(
                                            execution_id,
                                            nodes_by_id[child_id],
                                            f"Skipped: condition took '{branch}' branch"
                                        )

                            if node_type == "loop":
                                loop_cfg = nodes_by_id[node_id].get("config") or {}
                                total = max(1, int(loop_cfg.get("iterations", 1)))
                                body = self._get_loop_body(node_id, children)
                                loop_state[node_id] = {
                                    "current": 0,
                                    "total": total,
                                    "body": body,
                                }
                        else:
                            failed_count += 1

                    self._check_loop_iterations(
                        loop_state, statuses, pending, context_updates,
                        execution_id, nodes_by_id, children
                    )

            execution.finished_at = utc_now()
            execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            execution.summary = {
                **self._current_execution_summary(execution_id),
                "total": len(nodes),
                "passed": passed_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "workflow_state": self._build_workflow_state_snapshot(execution_id, nodes, edges, statuses),
            }

            if stop_requested:
                execution.status = "stopped"
                execution.result = "partial" if passed_count else "failed"
            elif failed_count == 0 and blocking_skipped_count == 0:
                execution.status = "completed"
                execution.result = "passed"
            else:
                execution.status = "failed"
                execution.result = "failed" if passed_count == 0 else "partial"

            cleanup = self._cleanup_execution_processes(execution)
            if cleanup:
                execution.summary = {**(execution.summary or {}), "cleanup": cleanup}
            self._finalize_webhook_execution(execution)
            self.db.commit()
        except Exception as exc:
            logger.exception("Error in execution %s", execution_id)
            execution.status = "failed"
            execution.finished_at = utc_now()
            if execution.started_at:
                execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            execution.result = "failed"
            execution.summary = {
                "error": str(exc),
                "workflow_state": self._build_workflow_state_snapshot(
                    execution_id,
                    workflow.nodes or [],
                    workflow.edges or [],
                    locals().get("statuses", {})
                ),
            }
            cleanup = self._cleanup_execution_processes(execution)
            if cleanup:
                execution.summary = {**(execution.summary or {}), "cleanup": cleanup}
            self._finalize_webhook_execution(execution)
            self.db.commit()
