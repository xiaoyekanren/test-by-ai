import logging
import os
import random
import shlex
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.database import Execution, NodeExecution, Server, Workflow
from app.services.ssh_service import SSHService

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Service for managing workflow executions."""

    def __init__(self, db: Session):
        self.db = db
        self.ssh_service = SSHService()

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
            execution.status = "failed"
            execution.finished_at = datetime.utcnow()
            if execution.started_at:
                execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            self.db.commit()
            self.db.refresh(execution)
            logger.info("Stopped execution %s", execution_id)

        return execution

    def execute_workflow(self, execution_id: int) -> None:
        execution = self.get_execution(execution_id)
        if not execution:
            logger.error("Execution %s not found", execution_id)
            return

        workflow = self.db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
        if not workflow:
            logger.error("Workflow %s not found", execution.workflow_id)
            execution.status = "failed"
            execution.finished_at = datetime.utcnow()
            self.db.commit()
            return

        execution.status = "running"
        execution.started_at = datetime.utcnow()
        self.db.commit()

        nodes = workflow.nodes or []
        passed_count = 0
        failed_count = 0
        context: Dict[str, Any] = {}

        try:
            for node in nodes:
                node_id = node.get("id")
                node_type = node.get("type", "shell")
                # Copy config to avoid mutating original workflow definition
                config = dict(node.get("config", {}) or {})
                config["_execution_id"] = execution_id
                config["_node_id"] = node_id

                if self._node_requires_server(node_type):
                    explicit_region = config.get("region") not in (None, "")
                    server = self._resolve_server_with_region(config, context)
                    if server:
                        self._write_server_config(config, server)
                        context["server_id"] = server.id
                        context["server_name"] = server.name
                        context["host"] = server.host
                        context["region"] = server.region
                        logger.info(
                            "Resolved server %s (%s) in region %s for node %s",
                            server.id, server.name, server.region, node_id
                        )
                    elif config.get("region") in (None, ""):
                        config["region"] = self._target_region(config, context)
                    merge_context = context
                    if explicit_region and not server:
                        logger.warning(
                            "No idle server found in explicit region %s for node %s; inherited server context will not be used",
                            config.get("region"),
                            node_id
                        )
                        merge_context = {
                            key: value
                            for key, value in context.items()
                            if key not in {"server_id", "server_name", "host"}
                        }
                    config = self._merge_config_with_context(config, merge_context)

                node_execution = NodeExecution(
                    execution_id=execution_id,
                    node_id=node_id,
                    node_type=node_type,
                    status="running",
                    started_at=datetime.utcnow(),
                    input_data=config
                )
                self.db.add(node_execution)
                self.db.commit()
                self.db.refresh(node_execution)

                try:
                    result = self._execute_node(node_type, config, context)
                    node_execution.output_data = result
                    exit_status = result.get("exit_status", -1)
                    node_execution.status = "success" if exit_status == 0 else "failed"
                    if exit_status != 0:
                        node_execution.error_message = (
                            result.get("error")
                            or result.get("stderr")
                            or "Unknown error"
                        )
                    else:
                        context.update(self._build_context_updates(node_type, config, result))

                    if node_execution.status == "success":
                        passed_count += 1
                    else:
                        failed_count += 1
                except Exception as exc:
                    logger.exception("Error executing node %s", node_id)
                    node_execution.status = "failed"
                    node_execution.error_message = str(exc)
                    node_execution.output_data = {"exit_status": -1, "error": str(exc)}
                    failed_count += 1

                node_execution.finished_at = datetime.utcnow()
                node_execution.duration = int(
                    (node_execution.finished_at - node_execution.started_at).total_seconds()
                )
                self.db.commit()

                if node_execution.status != "success":
                    break

            execution.finished_at = datetime.utcnow()
            execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            execution.summary = {
                "total": len(nodes),
                "passed": passed_count,
                "failed": failed_count,
            }

            if failed_count == 0:
                execution.status = "completed"
                execution.result = "passed"
            else:
                execution.status = "failed"
                execution.result = "failed" if passed_count == 0 else "partial"

            self.db.commit()
        except Exception as exc:
            logger.exception("Error in execution %s", execution_id)
            execution.status = "failed"
            execution.finished_at = datetime.utcnow()
            if execution.started_at:
                execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            execution.result = "failed"
            execution.summary = {"error": str(exc)}
            self.db.commit()

    def _execute_node(self, node_type: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        merged = self._merge_config_with_context(config, context)

        if node_type == "shell":
            return self._execute_shell_node(merged, context)
        if node_type == "upload":
            return self._execute_upload_node(merged, context)
        if node_type == "download":
            return self._execute_download_node(merged, context)
        if node_type in {"config", "iotdb_config"}:
            return self._execute_config_node(node_type, merged, context)
        if node_type == "log_view":
            return self._execute_log_view_node(merged, context)
        if node_type == "iotdb_deploy":
            return self._execute_iotdb_deploy_node(merged, context)
        if node_type == "iotdb_start":
            return self._execute_iotdb_start_node(merged, context)
        if node_type == "iotdb_cli":
            return self._execute_iotdb_cli_node(merged, context)
        if node_type == "iotdb_stop":
            return self._execute_iotdb_stop_node(merged, context)
        if node_type == "iotdb_cluster_deploy":
            return self._execute_iotdb_cluster_deploy_node(merged, context)
        if node_type == "iotdb_cluster_start":
            return self._execute_iotdb_cluster_start_node(merged, context)
        if node_type == "iotdb_cluster_check":
            return self._execute_iotdb_cluster_check_node(merged, context)
        if node_type == "iotdb_cluster_stop":
            return self._execute_iotdb_cluster_stop_node(merged, context)
        if node_type == "iot_benchmark_start":
            return self._execute_iot_benchmark_start_node(merged, context)
        if node_type == "iot_benchmark_wait":
            return self._execute_iot_benchmark_wait_node(merged, context)

        return {
            "exit_status": 0,
            "stdout": "",
            "stderr": "",
            "message": f"Node type {node_type} executed without side effects"
        }

    def _execute_shell_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        command = str(config.get("command", "")).strip()
        if not command:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "Command is required"}

        server = self._resolve_server_with_region(config, context or {})
        timeout = int(config.get("timeout", 60))

        if server:
            self._write_server_config(config, server)
            logger.info(
                "Executing shell command on server %s (%s) in region %s",
                server.id,
                server.name,
                server.region or "私有云"
            )
            result = self.ssh_service.run_command(
                host=server.host,
                username=server.username,
                password=server.password,
                command=command,
                port=server.port,
                timeout=timeout
            )
            return self._ssh_result_to_dict(result)

        target_region = self._target_region(config, context or {})
        logger.warning(
            "Shell node has no idle server in region %s; command will not run locally",
            target_region
        )
        return {
            "exit_status": -1,
            "stdout": "",
            "stderr": "",
            "error": f"No idle server found in region {target_region}"
        }

    def _execute_upload_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        local_path = self._required_str(config, "local_path", "artifact_local_path")
        remote_path = self._required_str(config, "remote_path", "remote_package_path")

        result = self.ssh_service.upload_file(
            host=server.host,
            username=server.username,
            password=server.password,
            local_path=local_path,
            remote_path=remote_path,
            port=server.port,
            timeout=int(config.get("timeout", 300))
        )
        if result["status"] != "success":
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": result.get("message", ""),
                "error": result.get("message", "Upload failed"),
                "local_path": local_path,
                "remote_path": remote_path
            }

        return {
            "exit_status": 0,
            "stdout": f"Uploaded {local_path} to {remote_path}",
            "stderr": "",
            "local_path": local_path,
            "remote_path": remote_path
        }

    def _execute_download_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        remote_path = self._required_str(config, "remote_path")
        local_path = self._required_str(config, "local_path")

        result = self.ssh_service.download_file(
            host=server.host,
            username=server.username,
            password=server.password,
            remote_path=remote_path,
            local_path=local_path,
            port=server.port,
            timeout=int(config.get("timeout", 300))
        )
        if result["status"] != "success":
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": result.get("message", ""),
                "error": result.get("message", "Download failed"),
                "local_path": local_path,
                "remote_path": remote_path
            }

        return {
            "exit_status": 0,
            "stdout": f"Downloaded {remote_path} to {local_path}",
            "stderr": "",
            "local_path": local_path,
            "remote_path": remote_path
        }

    def _execute_config_node(
        self,
        node_type: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        server = self._require_server(config, context)
        role = self._normalize_node_role(config.get("node_role"))

        if node_type == "iotdb_config":
            iotdb_home = self._required_str(config, "iotdb_home")
            file_path = config.get("file_path") or self._default_config_path(iotdb_home)
            replacements = config.get("config_items") or {}
        else:
            file_path = self._required_str(config, "file_path")
            replacements = config.get("config_items") or config.get("replacements") or {}
            iotdb_home = config.get("iotdb_home")

        if not isinstance(replacements, dict) or not replacements:
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": "",
                "error": "config_items/replacements must be a non-empty object"
            }

        result = self._apply_config_file_to_server(
            server=server,
            file_path=file_path,
            replacements=replacements,
            timeout=int(config.get("timeout", 60)),
            backup_before_write=bool(config.get("backup_before_write", False))
        )
        if result.get("exit_status") == 0 and iotdb_home:
            result["iotdb_home"] = iotdb_home
            result["node_role"] = role
            if "rpc_port" in context:
                result["rpc_port"] = context["rpc_port"]
        return result

    def _execute_log_view_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        file_path = self._required_str(config, "file_path")
        lines = int(config.get("lines", 100))
        command = f"tail -n {lines} {self._quote(file_path)}"
        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command=command,
            port=server.port,
            timeout=int(config.get("timeout", 30))
        )
        payload = self._ssh_result_to_dict(result)
        payload["file_path"] = file_path
        return payload

    def _execute_iotdb_deploy_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        role = self._normalize_node_role(config.get("node_role"))
        install_dir = self._required_str(config, "install_dir", "install_path")
        remote_package_path = config.get("remote_package_path") or config.get("remote_path")
        if not remote_package_path and config.get("artifact_local_path"):
            remote_package_path = f"/tmp/{os.path.basename(str(config['artifact_local_path']))}"

        deploy_result = self._deploy_package_to_server(
            server=server,
            artifact_local_path=config.get("artifact_local_path") or config.get("local_path"),
            remote_package_path=str(remote_package_path or ""),
            install_dir=install_dir,
            package_type=str(config.get("package_type", "auto")),
            extract_subdir=str(config.get("extract_subdir", "") or "").strip("/"),
            overwrite=bool(config.get("overwrite", False)),
            timeout=int(config.get("timeout", 600)),
            node_role=role
        )
        if deploy_result.get("exit_status") != 0:
            return deploy_result

        rpc_port = int(config.get("rpc_port", 6667))
        deploy_result.update({
            "node_role": role,
            "server_id": server.id,
            "host": server.host,
            "rpc_port": rpc_port,
            "wait_port": int(config.get("wait_port", rpc_port))
        })
        return deploy_result

    def _execute_iotdb_start_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        role = self._normalize_node_role(config.get("node_role"))
        iotdb_home = self._required_str(config, "iotdb_home")
        host = str(config.get("host") or server.host or "127.0.0.1")
        rpc_port = int(config.get("rpc_port", config.get("wait_port", 6667)))
        wait_port = int(config.get("wait_port", self._default_wait_port(role, config)))
        timeout_seconds = int(config.get("timeout_seconds", config.get("timeout", 60)))
        wait_strategy = str(config.get("wait_strategy", "port"))

        script_name = self._start_script_for_role(role)
        start_script = f"cd {self._quote(iotdb_home)} && bash sbin/{script_name}"
        start_result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote(start_script),
            port=server.port,
            timeout=min(timeout_seconds, 60)
        )
        if start_result.exit_status != 0:
            payload = self._ssh_result_to_dict(start_result)
            payload.update({"iotdb_home": iotdb_home, "rpc_port": rpc_port, "wait_port": wait_port, "node_role": role})
            return payload

        deadline = time.time() + timeout_seconds
        last_result = None
        while time.time() < deadline:
            effective_cli_check = wait_strategy == "cli" and role in {"standalone", "datanode"}
            if effective_cli_check:
                last_result = self._run_iotdb_sql(
                    server,
                    iotdb_home,
                    host,
                    rpc_port,
                    str(config.get("username") or "root"),
                    str(config.get("password") or "root"),
                    "show databases",
                    str(config.get("sql_dialect") or "tree"),
                    20
                )
            else:
                wait_cmd = "bash -lc " + self._quote(f"echo >/dev/tcp/{host}/{wait_port}")
                last_result = self.ssh_service.run_command(
                    host=server.host,
                    username=server.username,
                    password=server.password,
                    command=wait_cmd,
                    port=server.port,
                    timeout=10
                )

            if last_result.exit_status == 0:
                return {
                    "exit_status": 0,
                    "stdout": start_result.stdout + (last_result.stdout or ""),
                    "stderr": start_result.stderr + (last_result.stderr or ""),
                    "iotdb_home": iotdb_home,
                    "rpc_port": rpc_port,
                    "wait_port": wait_port,
                    "host": host,
                    "node_role": role,
                    "start_script": script_name
                }
            time.sleep(2)

        return {
            "exit_status": -1,
            "stdout": start_result.stdout,
            "stderr": (last_result.stderr if last_result else ""),
            "error": f"IoTDB did not become ready within {timeout_seconds} seconds",
            "iotdb_home": iotdb_home,
            "rpc_port": rpc_port,
            "wait_port": wait_port,
            "host": host,
            "node_role": role,
            "start_script": script_name
        }

    def _execute_iotdb_cli_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        iotdb_home = self._required_str(config, "iotdb_home")
        host = str(config.get("host") or server.host or "127.0.0.1")
        rpc_port = int(config.get("rpc_port", 6667))
        username = str(config.get("username") or "root")
        password = str(config.get("password") or "root")
        sql_dialect = str(config.get("sql_dialect") or "tree")
        timeout_seconds = int(config.get("timeout_seconds", config.get("timeout", 300)))
        sql_list = self._normalize_line_list(config.get("sqls") or config.get("commands") or [])
        if not sql_list:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "At least one SQL statement is required"}

        return self._run_sql_batch(
            server=server,
            iotdb_home=iotdb_home,
            host=host,
            rpc_port=rpc_port,
            username=username,
            password=password,
            sql_dialect=sql_dialect,
            sql_list=sql_list,
            timeout_seconds=timeout_seconds
        )

    def _execute_iotdb_stop_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        role = self._normalize_node_role(config.get("node_role"))
        iotdb_home = self._required_str(config, "iotdb_home")
        graceful = bool(config.get("graceful", True))
        timeout_seconds = int(config.get("timeout_seconds", config.get("timeout", 60)))
        script_name = self._stop_script_for_role(role)
        script = f"bash sbin/{script_name}"
        if not graceful:
            script += " -f"

        stop_script = f"cd {self._quote(iotdb_home)} && {script}"
        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote(stop_script),
            port=server.port,
            timeout=timeout_seconds
        )
        payload = self._ssh_result_to_dict(result)
        payload["iotdb_home"] = iotdb_home
        payload["node_role"] = role
        payload["stop_script"] = script_name
        return payload

    def _execute_iotdb_cluster_deploy_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cluster_name = str(config.get("cluster_name") or "defaultCluster")
        config_nodes = self._normalize_cluster_nodes(config.get("config_nodes"), "confignode", config)
        data_nodes = self._normalize_cluster_nodes(config.get("data_nodes"), "datanode", config)
        if not config_nodes:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "At least one ConfigNode is required"}
        if not data_nodes:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "At least one DataNode is required"}

        common_config = config.get("common_config") or {}
        if not isinstance(common_config, dict):
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "common_config must be an object"}

        results: List[Dict[str, Any]] = []
        stdout_parts: List[str] = []
        seed_cn = config_nodes[0]
        seed = f"{seed_cn['host']}:{seed_cn['cn_internal_port']}"

        for entry in config_nodes + data_nodes:
            server = self._require_server(entry, context)
            deploy_result = self._deploy_package_to_server(
                server=server,
                artifact_local_path=config.get("artifact_local_path"),
                remote_package_path=self._required_str(config, "remote_package_path"),
                install_dir=str(entry["install_dir"]),
                package_type=str(config.get("package_type", "auto")),
                extract_subdir=str(config.get("extract_subdir", "") or "").strip("/"),
                overwrite=bool(config.get("overwrite", False)),
                timeout=int(config.get("timeout", 900)),
                node_role=str(entry["node_role"])
            )
            results.append({"step": "deploy", "node": entry, "result": deploy_result})
            stdout_parts.append(deploy_result.get("stdout", ""))
            if deploy_result.get("exit_status") != 0:
                return self._cluster_failure("Cluster deploy failed during package deployment", results, cluster_name, config_nodes, data_nodes)

            replacements = self._build_cluster_replacements(
                entry=entry,
                cluster_name=cluster_name,
                seed_config_node=seed,
                common_config=common_config
            )
            config_result = self._apply_config_file_to_server(
                server=server,
                file_path=self._default_config_path(str(entry["install_dir"])),
                replacements=replacements,
                timeout=int(config.get("timeout", 900)),
                backup_before_write=bool(config.get("backup_before_write", True))
            )
            results.append({"step": "config", "node": entry, "result": config_result})
            stdout_parts.append(config_result.get("stdout", ""))
            if config_result.get("exit_status") != 0:
                return self._cluster_failure("Cluster deploy failed during config write", results, cluster_name, config_nodes, data_nodes)

        return {
            "exit_status": 0,
            "stdout": "\n".join(part for part in stdout_parts if part).strip(),
            "stderr": "",
            "cluster_name": cluster_name,
            "config_nodes": config_nodes,
            "data_nodes": data_nodes,
            "results": results
        }

    def _execute_iotdb_cluster_start_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cluster_name = str(config.get("cluster_name") or "defaultCluster")
        config_nodes = self._normalize_cluster_nodes(config.get("config_nodes"), "confignode", config)
        data_nodes = self._normalize_cluster_nodes(config.get("data_nodes"), "datanode", config)
        wait_strategy = str(config.get("wait_strategy") or "port")
        timeout_seconds = int(config.get("timeout_seconds", 180))
        results: List[Dict[str, Any]] = []

        for entry in config_nodes + data_nodes:
            start_result = self._execute_iotdb_start_node({
                "server_id": entry["server_id"],
                "node_role": entry["node_role"],
                "iotdb_home": entry["install_dir"],
                "host": entry["host"],
                "rpc_port": entry.get("dn_rpc_port", entry.get("rpc_port", 6667)),
                "wait_port": self._cluster_wait_port(entry),
                "wait_strategy": wait_strategy,
                "timeout_seconds": timeout_seconds
            }, context)
            results.append({"node": entry, "result": start_result})
            if start_result.get("exit_status") != 0:
                return self._cluster_failure("Cluster start failed", results, cluster_name, config_nodes, data_nodes)

        return {
            "exit_status": 0,
            "stdout": "\n".join(item["result"].get("stdout", "") for item in results if item["result"].get("stdout")).strip(),
            "stderr": "",
            "cluster_name": cluster_name,
            "config_nodes": config_nodes,
            "data_nodes": data_nodes,
            "started_nodes": results
        }

    def _execute_iotdb_cluster_check_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cluster_name = str(config.get("cluster_name") or "defaultCluster")
        config_nodes = self._normalize_cluster_nodes(config.get("config_nodes"), "confignode", config)
        data_nodes = self._normalize_cluster_nodes(config.get("data_nodes"), "datanode", config)
        if not data_nodes:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "At least one DataNode is required for cluster check"}

        primary = data_nodes[0]
        server = self._require_server({"server_id": primary["server_id"]}, context)
        username = str(config.get("username") or "root")
        password = str(config.get("password") or "root")
        sql_dialect = str(config.get("sql_dialect") or "tree")
        timeout_seconds = int(config.get("timeout_seconds", 300))
        validation_sqls = self._normalize_line_list(config.get("validation_sqls") or [])

        cluster_check = self._run_iotdb_sql(
            server=server,
            iotdb_home=str(primary["install_dir"]),
            host=str(primary["host"]),
            rpc_port=int(primary.get("dn_rpc_port", primary.get("rpc_port", 6667))),
            username=username,
            password=password,
            sql="show cluster",
            sql_dialect=sql_dialect,
            timeout=timeout_seconds
        )
        if cluster_check.exit_status != 0:
            payload = self._ssh_result_to_dict(cluster_check)
            payload.update({"cluster_name": cluster_name, "config_nodes": config_nodes, "data_nodes": data_nodes})
            return payload

        result: Dict[str, Any] = {
            "exit_status": 0,
            "stdout": cluster_check.stdout,
            "stderr": cluster_check.stderr,
            "results": [self._ssh_result_to_dict(cluster_check) | {"sql": "show cluster"}],
            "cluster_name": cluster_name,
            "config_nodes": config_nodes,
            "data_nodes": data_nodes
        }
        if validation_sqls:
            batch_result = self._run_sql_batch(
                server=server,
                iotdb_home=str(primary["install_dir"]),
                host=str(primary["host"]),
                rpc_port=int(primary.get("dn_rpc_port", primary.get("rpc_port", 6667))),
                username=username,
                password=password,
                sql_dialect=sql_dialect,
                sql_list=validation_sqls,
                timeout_seconds=timeout_seconds
            )
            if batch_result.get("exit_status") != 0:
                batch_result.update({"cluster_name": cluster_name, "config_nodes": config_nodes, "data_nodes": data_nodes})
                return batch_result
            result["stdout"] = "\n".join(part for part in [cluster_check.stdout, batch_result.get("stdout", "")] if part).strip()
            result["results"].extend(batch_result.get("results", []))

        return result

    def _execute_iotdb_cluster_stop_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cluster_name = str(config.get("cluster_name") or "defaultCluster")
        config_nodes = self._normalize_cluster_nodes(config.get("config_nodes"), "confignode", config)
        data_nodes = self._normalize_cluster_nodes(config.get("data_nodes"), "datanode", config)
        graceful = bool(config.get("graceful", True))
        timeout_seconds = int(config.get("timeout_seconds", 180))
        results: List[Dict[str, Any]] = []

        for entry in list(reversed(data_nodes)) + list(reversed(config_nodes)):
            stop_result = self._execute_iotdb_stop_node({
                "server_id": entry["server_id"],
                "node_role": entry["node_role"],
                "iotdb_home": entry["install_dir"],
                "graceful": graceful,
                "timeout_seconds": timeout_seconds
            }, context)
            results.append({"node": entry, "result": stop_result})
            if stop_result.get("exit_status") != 0:
                return self._cluster_failure("Cluster stop failed", results, cluster_name, config_nodes, data_nodes)

        return {
            "exit_status": 0,
            "stdout": "\n".join(item["result"].get("stdout", "") for item in results if item["result"].get("stdout")).strip(),
            "stderr": "",
            "cluster_name": cluster_name,
            "config_nodes": config_nodes,
            "data_nodes": data_nodes,
            "stopped_nodes": results
        }

    def _execute_iot_benchmark_start_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        timeout = int(config.get("timeout", 60))
        benchmark_home = self._required_str(config, "benchmark_home").rstrip("/")
        target_host = str(config.get("target_host") or config.get("host") or server.host).strip()
        rpc_port = int(config.get("rpc_port", 6667))
        execution_id = str(config.get("_execution_id") or int(time.time()))
        node_id = self._safe_path_segment(config.get("_node_id") or "iot-benchmark")
        run_dir = str(config.get("run_dir") or f"/tmp/iot-benchmark-runs/{execution_id}/{node_id}-{int(time.time())}")
        conf_dir = f"{run_dir.rstrip('/')}/conf"
        stdout_path = f"{run_dir.rstrip('/')}/benchmark.out"
        pid_path = f"{run_dir.rstrip('/')}/benchmark.pid"
        exit_path = f"{run_dir.rstrip('/')}/benchmark.exit"

        prep_script = "\n".join([
            "set -e",
            f"rm -rf {self._quote(run_dir)}",
            f"mkdir -p {self._quote(run_dir)}",
            f"test -d {self._quote(f'{benchmark_home}/conf')}",
            f"test -f {self._quote(f'{benchmark_home}/benchmark.sh')}",
            f"cp -R {self._quote(f'{benchmark_home}/conf')} {self._quote(conf_dir)}",
        ])
        prep_result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote(prep_script),
            port=server.port,
            timeout=timeout
        )
        if prep_result.exit_status != 0:
            return self._ssh_result_to_dict(prep_result)

        config_path = f"{conf_dir}/config.properties"
        read_result = self.ssh_service.read_file(
            host=server.host,
            username=server.username,
            password=server.password,
            remote_path=config_path,
            port=server.port,
            timeout=timeout
        )
        if read_result["status"] != "success":
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": read_result.get("message", ""),
                "error": read_result.get("message", "Failed to read benchmark config")
            }

        replacements = self._build_iot_benchmark_replacements(config, target_host, rpc_port)
        updated_config = self._replace_properties(read_result["content"], replacements)
        write_result = self.ssh_service.write_file(
            host=server.host,
            username=server.username,
            password=server.password,
            remote_path=config_path,
            content=updated_config,
            port=server.port,
            timeout=timeout
        )
        if write_result["status"] != "success":
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": write_result.get("message", ""),
                "error": write_result.get("message", "Failed to write benchmark config")
            }

        benchmark_cmd = f"cd {self._quote(benchmark_home)} && bash ./benchmark.sh -cf {self._quote(conf_dir)}"
        wrapper_cmd = f"{benchmark_cmd}; code=$?; echo $code > {self._quote(exit_path)}; exit $code"
        start_script = "\n".join([
            "set -e",
            f"nohup bash -lc {self._quote(wrapper_cmd)} > {self._quote(stdout_path)} 2>&1 < /dev/null &",
            "pid=$!",
            f"echo $pid > {self._quote(pid_path)}",
            "echo $pid",
        ])
        start_result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote(start_script),
            port=server.port,
            timeout=timeout
        )
        if start_result.exit_status != 0:
            return self._ssh_result_to_dict(start_result)

        pid = start_result.stdout.strip().splitlines()[-1] if start_result.stdout.strip() else ""
        benchmark_run = {
            "server_id": server.id,
            "server_name": server.name,
            "region": server.region,
            "pid": pid,
            "run_dir": run_dir,
            "conf_dir": conf_dir,
            "config_path": config_path,
            "stdout_path": stdout_path,
            "pid_path": pid_path,
            "exit_path": exit_path,
            "target_host": target_host,
            "rpc_port": rpc_port,
            "started_at": datetime.utcnow().isoformat()
        }
        return {
            "exit_status": 0,
            "stdout": f"Started IoT Benchmark pid={pid} on server {server.id}",
            "stderr": start_result.stderr,
            "benchmark_run": benchmark_run,
            "server_id": server.id,
            "region": server.region,
            "target_host": target_host,
            "rpc_port": rpc_port,
            "updated_keys": sorted(replacements.keys())
        }

    def _execute_iot_benchmark_wait_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        benchmark_run = config.get("benchmark_run")
        if not isinstance(benchmark_run, dict) and context:
            benchmark_run = context.get("benchmark_run")
        if not isinstance(benchmark_run, dict):
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "benchmark_run is required"}

        server_id = benchmark_run.get("server_id") or config.get("server_id")
        server = self._require_server({"server_id": server_id} if server_id else config, context)
        self._write_server_config(config, server)
        pid = str(benchmark_run.get("pid") or "").strip()
        stdout_path = str(benchmark_run.get("stdout_path") or "").strip()
        exit_path = str(benchmark_run.get("exit_path") or "").strip()
        if not pid or not stdout_path or not exit_path:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "benchmark_run is incomplete"}

        timeout_seconds = int(config.get("timeout_seconds", 3600))
        poll_interval = max(1, int(config.get("poll_interval_seconds", 5)))
        tail_lines = max(1, int(config.get("tail_lines", 200)))
        kill_on_timeout = bool(config.get("kill_on_timeout", False))
        deadline = time.time() + timeout_seconds

        while time.time() <= deadline:
            check_result = self.ssh_service.run_command(
                host=server.host,
                username=server.username,
                password=server.password,
                command=f"ps -p {shlex.quote(pid)} -o pid= >/dev/null 2>&1 && echo running || echo done",
                port=server.port,
                timeout=30
            )
            if check_result.exit_status != 0:
                return self._ssh_result_to_dict(check_result)
            if "running" not in check_result.stdout:
                return self._collect_iot_benchmark_result(server, benchmark_run, tail_lines)
            time.sleep(poll_interval)

        if kill_on_timeout:
            self.ssh_service.run_command(
                host=server.host,
                username=server.username,
                password=server.password,
                command=f"kill {shlex.quote(pid)} >/dev/null 2>&1 || true",
                port=server.port,
                timeout=30
            )

        tail_result = self._tail_remote_file(server, stdout_path, tail_lines)
        return {
            "exit_status": -1,
            "stdout": tail_result.get("stdout", ""),
            "stderr": tail_result.get("stderr", ""),
            "error": f"IoT Benchmark did not finish within {timeout_seconds} seconds",
            "benchmark_run": benchmark_run
        }

    def _collect_iot_benchmark_result(
        self,
        server: Server,
        benchmark_run: Dict[str, Any],
        tail_lines: int
    ) -> Dict[str, Any]:
        stdout_path = str(benchmark_run.get("stdout_path"))
        exit_path = str(benchmark_run.get("exit_path"))
        collect_script = "\n".join([
            f"code=$(cat {self._quote(exit_path)} 2>/dev/null || echo 1)",
            "echo __IOT_BENCHMARK_EXIT_STATUS__=$code",
            f"tail -n {tail_lines} {self._quote(stdout_path)} 2>/dev/null || true",
            "exit $code",
        ])
        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote(collect_script),
            port=server.port,
            timeout=60
        )
        payload = self._ssh_result_to_dict(result)
        payload["benchmark_run"] = benchmark_run
        payload["server_id"] = server.id
        payload["region"] = server.region
        payload["benchmark_result"] = {
            "exit_status": result.exit_status,
            "stdout_tail": result.stdout,
            "stderr": result.stderr,
            "finished_at": datetime.utcnow().isoformat()
        }
        return payload

    def _run_sql_batch(
        self,
        server: Server,
        iotdb_home: str,
        host: str,
        rpc_port: int,
        username: str,
        password: str,
        sql_dialect: str,
        sql_list: List[str],
        timeout_seconds: int
    ) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        stdout_parts: List[str] = []
        stderr_parts: List[str] = []

        for sql in sql_list:
            result = self._run_iotdb_sql(
                server=server,
                iotdb_home=iotdb_home,
                host=host,
                rpc_port=rpc_port,
                username=username,
                password=password,
                sql=sql,
                sql_dialect=sql_dialect,
                timeout=timeout_seconds
            )
            result_dict = self._ssh_result_to_dict(result)
            result_dict["sql"] = sql
            results.append(result_dict)
            stdout_parts.append(result.stdout)
            stderr_parts.append(result.stderr or result.error or "")
            if result.exit_status != 0:
                return {
                    "exit_status": result.exit_status,
                    "stdout": "\n".join(stdout_parts).strip(),
                    "stderr": "\n".join(part for part in stderr_parts if part).strip(),
                    "error": result.error or result.stderr or f"Failed to execute SQL: {sql}",
                    "executed_sqls": sql_list,
                    "results": results,
                    "iotdb_home": iotdb_home,
                    "rpc_port": rpc_port
                }

        return {
            "exit_status": 0,
            "stdout": "\n".join(part for part in stdout_parts if part).strip(),
            "stderr": "\n".join(part for part in stderr_parts if part).strip(),
            "executed_sqls": sql_list,
            "results": results,
            "iotdb_home": iotdb_home,
            "rpc_port": rpc_port,
            "host": host
        }

    def _run_iotdb_sql(
        self,
        server: Server,
        iotdb_home: str,
        host: str,
        rpc_port: int,
        username: str,
        password: str,
        sql: str,
        sql_dialect: str,
        timeout: int
    ):
        cli_script = (
            f"cd {self._quote(iotdb_home)} && "
            f"bash sbin/start-cli.sh -h {shlex.quote(host)} "
            f"-p {rpc_port} -u {shlex.quote(username)} -pw {shlex.quote(password)} "
            f"-sql_dialect {shlex.quote(sql_dialect)} -e {shlex.quote(sql)}"
        )
        return self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote(cli_script),
            port=server.port,
            timeout=timeout
        )

    def _apply_config_file_to_server(
        self,
        server: Server,
        file_path: str,
        replacements: Dict[str, Any],
        timeout: int,
        backup_before_write: bool
    ) -> Dict[str, Any]:
        read_result = self.ssh_service.read_file(
            host=server.host,
            username=server.username,
            password=server.password,
            remote_path=file_path,
            port=server.port,
            timeout=timeout
        )
        if read_result["status"] != "success":
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": read_result.get("message", ""),
                "error": read_result.get("message", "Failed to read config file")
            }

        updated = self._replace_properties(read_result["content"], replacements)
        backup_path = None
        if backup_before_write:
            backup_path = f"{file_path}.bak.{int(time.time())}"
            backup_result = self.ssh_service.run_command(
                host=server.host,
                username=server.username,
                password=server.password,
                command=f"cp {self._quote(file_path)} {self._quote(backup_path)}",
                port=server.port,
                timeout=timeout
            )
            if backup_result.exit_status != 0:
                return self._ssh_result_to_dict(backup_result)

        write_result = self.ssh_service.write_file(
            host=server.host,
            username=server.username,
            password=server.password,
            remote_path=file_path,
            content=updated,
            port=server.port,
            timeout=timeout
        )
        if write_result["status"] != "success":
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": write_result.get("message", ""),
                "error": write_result.get("message", "Failed to write config file")
            }

        result: Dict[str, Any] = {
            "exit_status": 0,
            "stdout": f"Updated configuration file {file_path}",
            "stderr": "",
            "file_path": file_path,
            "conf_path": file_path,
            "updated_keys": sorted(replacements.keys())
        }
        if backup_path:
            result["backup_path"] = backup_path
        return result

    def _deploy_package_to_server(
        self,
        server: Server,
        artifact_local_path: Any,
        remote_package_path: str,
        install_dir: str,
        package_type: str,
        extract_subdir: str,
        overwrite: bool,
        timeout: int,
        node_role: str
    ) -> Dict[str, Any]:
        if not remote_package_path:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "remote_package_path is required"}

        if artifact_local_path:
            upload_result = self._execute_upload_node({
                "server_id": server.id,
                "local_path": artifact_local_path,
                "remote_path": remote_package_path,
                "timeout": timeout
            })
            if upload_result.get("exit_status") != 0:
                return upload_result

        detected_type = self._detect_package_type(remote_package_path, package_type)
        if detected_type is None:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "Unsupported package_type"}

        expected_script = self._start_script_for_role(node_role)
        tmp_dir = f"{install_dir}.extracting"
        commands = [
            "set -e",
            f"mkdir -p {self._quote(os.path.dirname(install_dir) or '/')}",
        ]
        if overwrite:
            commands.append(f"rm -rf {self._quote(install_dir)}")
        commands.extend([
            f"rm -rf {self._quote(tmp_dir)}",
            f"mkdir -p {self._quote(tmp_dir)}"
        ])

        if detected_type == "tar.gz":
            commands.append(f"tar -xzf {self._quote(remote_package_path)} -C {self._quote(tmp_dir)}")
        else:
            commands.append(f"unzip -q {self._quote(remote_package_path)} -d {self._quote(tmp_dir)}")

        if extract_subdir:
            source_dir_expr = f"{tmp_dir.rstrip('/')}/{extract_subdir}"
        else:
            source_dir_expr = '$(find ' + self._quote(tmp_dir) + " -mindepth 1 -maxdepth 1 -type d | head -n 1)"

        expected_script_path = f"{install_dir.rstrip('/')}/sbin/{expected_script}"
        commands.extend([
            f"source_dir={source_dir_expr}",
            'if [ -z "$source_dir" ]; then source_dir=' + self._quote(tmp_dir) + "; fi",
            f"mkdir -p {self._quote(install_dir)}",
            f"cp -R \"$source_dir\"/. {self._quote(install_dir)}/",
            f"test -f {self._quote(expected_script_path)}",
            f"rm -rf {self._quote(tmp_dir)}"
        ])

        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote("\n".join(commands)),
            port=server.port,
            timeout=timeout
        )
        payload = self._ssh_result_to_dict(result)
        payload.update({
            "remote_package_path": remote_package_path,
            "iotdb_home": install_dir,
            "conf_path": self._default_config_path(install_dir),
            "expected_start_script": expected_script
        })
        return payload

    def _normalize_cluster_nodes(self, raw_nodes: Any, role: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(raw_nodes, list):
            return []

        normalized: List[Dict[str, Any]] = []
        base_install_dir = str(config.get("install_dir") or "/opt/iotdb-cluster")
        for index, item in enumerate(raw_nodes):
            if not isinstance(item, dict):
                continue
            server_id = item.get("server_id")
            if server_id is None:
                continue
            server = self.db.query(Server).filter(Server.id == int(server_id)).first()
            if not server:
                continue

            node_role = self._normalize_node_role(item.get("node_role") or role)
            host = str(item.get("host") or server.host)
            install_dir = str(item.get("install_dir") or f"{base_install_dir.rstrip('/')}/{node_role}-{index + 1}")
            normalized_item: Dict[str, Any] = {
                "server_id": int(server_id),
                "node_role": node_role,
                "host": host,
                "install_dir": install_dir,
                "cluster_name": str(config.get("cluster_name") or "defaultCluster")
            }

            if node_role == "confignode":
                normalized_item["cn_internal_port"] = int(item.get("cn_internal_port", 10710 + index * 20))
                normalized_item["cn_consensus_port"] = int(item.get("cn_consensus_port", 10720 + index * 20))
            elif node_role == "datanode":
                normalized_item["dn_rpc_port"] = int(item.get("dn_rpc_port", 6667 + index * 10))
                normalized_item["dn_internal_port"] = int(item.get("dn_internal_port", 10730 + index * 10))
                normalized_item["dn_mpp_data_exchange_port"] = int(item.get("dn_mpp_data_exchange_port", 10740 + index * 10))
                normalized_item["dn_data_region_consensus_port"] = int(item.get("dn_data_region_consensus_port", 10750 + index * 10))
                normalized_item["dn_schema_region_consensus_port"] = int(item.get("dn_schema_region_consensus_port", 10760 + index * 10))

            for key, value in item.items():
                if key not in normalized_item:
                    normalized_item[key] = value

            normalized.append(normalized_item)

        return normalized

    def _build_cluster_replacements(
        self,
        entry: Dict[str, Any],
        cluster_name: str,
        seed_config_node: str,
        common_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        replacements = {str(key): str(value) for key, value in common_config.items()}
        replacements["cluster_name"] = cluster_name

        if entry["node_role"] == "confignode":
            replacements.update({
                "cn_internal_address": str(entry["host"]),
                "cn_internal_port": str(entry["cn_internal_port"]),
                "cn_consensus_port": str(entry["cn_consensus_port"]),
                "cn_seed_config_node": seed_config_node
            })
        elif entry["node_role"] == "datanode":
            replacements.update({
                "dn_rpc_address": str(entry["host"]),
                "dn_rpc_port": str(entry["dn_rpc_port"]),
                "dn_internal_address": str(entry["host"]),
                "dn_internal_port": str(entry["dn_internal_port"]),
                "dn_mpp_data_exchange_port": str(entry["dn_mpp_data_exchange_port"]),
                "dn_data_region_consensus_port": str(entry["dn_data_region_consensus_port"]),
                "dn_schema_region_consensus_port": str(entry["dn_schema_region_consensus_port"]),
                "dn_seed_config_node": seed_config_node
            })

        if isinstance(entry.get("config_items"), dict):
            for key, value in entry["config_items"].items():
                replacements[str(key)] = str(value)

        return replacements

    def _cluster_wait_port(self, entry: Dict[str, Any]) -> int:
        if entry["node_role"] == "confignode":
            return int(entry["cn_internal_port"])
        if entry["node_role"] == "datanode":
            return int(entry["dn_rpc_port"])
        return int(entry.get("rpc_port", 6667))

    def _cluster_failure(
        self,
        message: str,
        results: List[Dict[str, Any]],
        cluster_name: str,
        config_nodes: List[Dict[str, Any]],
        data_nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        last_result = results[-1]["result"] if results else {}
        return {
            "exit_status": -1,
            "stdout": "\n".join(item["result"].get("stdout", "") for item in results if item["result"].get("stdout")).strip(),
            "stderr": "\n".join(item["result"].get("stderr", "") for item in results if item["result"].get("stderr")).strip(),
            "error": message,
            "cluster_name": cluster_name,
            "config_nodes": config_nodes,
            "data_nodes": data_nodes,
            "results": results,
            "failed_node": results[-1]["node"] if results else None,
            "failed_step_error": last_result.get("error") or last_result.get("stderr")
        }

    def _merge_config_with_context(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(config)
        has_explicit_region = config.get("region") not in (None, "")
        fallback_keys = [
            "server_id",
            "node_role",
            "iotdb_home",
            "conf_path",
            "rpc_port",
            "wait_port",
            "host",
            "remote_package_path",
            "cluster_name",
            "config_nodes",
            "data_nodes",
            "benchmark_run",
            "benchmark_result",
            "region",
        ]
        for key in fallback_keys:
            if has_explicit_region and key in {"server_id", "host"}:
                continue
            if merged.get(key) in (None, "", []):
                if key in context:
                    merged[key] = context[key]
        return merged

    def _build_context_updates(
        self,
        node_type: str,
        config: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        updates: Dict[str, Any] = {}
        server_id = config.get("server_id")
        if server_id is not None:
            updates["server_id"] = server_id
            server = self.db.query(Server).filter(Server.id == int(server_id)).first()
            if server:
                updates["host"] = server.host
                updates["region"] = server.region

        for key in [
            "node_role", "iotdb_home", "conf_path", "rpc_port", "wait_port",
            "remote_package_path", "backup_path", "cluster_name", "config_nodes",
            "data_nodes", "benchmark_run", "benchmark_result", "target_host", "region"
        ]:
            if key in result and result[key] not in (None, ""):
                updates[key] = result[key]

        if node_type == "iotdb_cli" and result.get("executed_sqls"):
            updates["executed_sqls"] = result["executed_sqls"]
        return updates

    def _require_server(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Server:
        """Require a server, using region-based scheduling if context is provided."""
        if context is not None:
            server = self._resolve_server_with_region(config, context)
        else:
            server = self._resolve_server(config)
        if not server:
            raise ValueError("A valid server_id is required or no idle server available in target region")
        return server

    def _resolve_server(self, config: Dict[str, Any]) -> Optional[Server]:
        server_id = config.get("server_id")
        if server_id is None:
            return None
        return self.db.query(Server).filter(Server.id == int(server_id)).first()

    def _resolve_server_with_region(self, config: Dict[str, Any], context: Dict[str, Any]) -> Optional[Server]:
        """Resolve server with region-based scheduling logic.

        Priority:
        1. Explicit server_id in config
        2. Explicit region in config -> random idle server from that region
        3. server_id in context
        4. region in context -> random idle server from that region
        5. Default to '私有云' region -> random idle server
        """
        server_id = config.get("server_id")
        if server_id is not None and server_id != "":
            return self.db.query(Server).filter(Server.id == int(server_id)).first()

        region = config.get("region")
        if region not in (None, ""):
            return self._resolve_idle_server_by_region(str(region))

        server_id = context.get("server_id")
        if server_id is not None and server_id != "":
            return self.db.query(Server).filter(Server.id == int(server_id)).first()

        return self._resolve_idle_server_by_region(self._target_region(config, context))

    def _resolve_idle_server_by_region(self, region: str) -> Optional[Server]:
        busy_server_ids = self._compute_busy_server_ids()

        query = self.db.query(Server).filter(Server.region == region)
        if busy_server_ids:
            query = query.filter(Server.id.notin_(busy_server_ids))

        idle_servers = query.all()

        if not idle_servers:
            logger.warning(
                "No idle server found in region %s; busy_server_ids=%s",
                region,
                busy_server_ids
            )
            return None

        server = random.choice(idle_servers)
        logger.info(
            "Selected idle server %s (%s) from region %s; candidates=%s",
            server.id,
            server.name,
            region,
            [item.id for item in idle_servers]
        )
        return server

    def _write_server_config(self, config: Dict[str, Any], server: Server) -> None:
        config["server_id"] = server.id
        config["server_name"] = server.name
        config["host"] = server.host
        config["region"] = server.region or "私有云"

    def _target_region(self, config: Dict[str, Any], context: Dict[str, Any]) -> str:
        region = config.get("region")
        if region in (None, ""):
            region = context.get("region")
        if region in (None, ""):
            region = "私有云"
        return str(region)

    def _compute_busy_server_ids(self) -> List[int]:
        """Get IDs of servers currently being used in running executions."""
        # Find all running executions
        running_executions = self.db.query(Execution.id).filter(
            Execution.status == "running"
        ).all()
        running_exec_ids = [e.id for e in running_executions]

        if not running_exec_ids:
            return []

        # Single query with .in_() filter for all running node_executions
        running_node_execs = self.db.query(NodeExecution).filter(
            NodeExecution.execution_id.in_(running_exec_ids),
            NodeExecution.status == "running"
        ).all()

        busy_ids: List[int] = []
        for ne in running_node_execs:
            if ne.input_data and isinstance(ne.input_data, dict):
                server_id = ne.input_data.get("server_id")
                if server_id is not None:
                    busy_ids.append(int(server_id))

        return list(set(busy_ids))

    def _node_requires_server(self, node_type: str) -> bool:
        """Check if a node type requires a server to execute."""
        server_required_types = {
            "shell", "upload", "download", "config", "iotdb_config",
            "log_view", "iotdb_deploy", "iotdb_start", "iotdb_cli",
            "iotdb_stop", "iotdb_cluster_deploy", "iotdb_cluster_start",
            "iotdb_cluster_check", "iotdb_cluster_stop", "iot_benchmark_start",
            "iot_benchmark_wait"
        }
        return node_type in server_required_types

    def _required_str(self, config: Dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = config.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        raise ValueError(f"Missing required config field: {'/'.join(keys)}")

    def _normalize_line_list(self, value: Any) -> List[str]:
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _normalize_node_role(self, role: Any) -> str:
        value = str(role or "standalone").strip().lower()
        if value in {"confignode", "config_node", "config-node"}:
            return "confignode"
        if value in {"datanode", "data_node", "data-node"}:
            return "datanode"
        return "standalone"

    def _default_config_path(self, iotdb_home: str) -> str:
        return f"{iotdb_home.rstrip('/')}/conf/iotdb-system.properties"

    def _default_wait_port(self, role: str, config: Dict[str, Any]) -> int:
        if role == "confignode":
            return int(config.get("cn_internal_port", 10710))
        if role == "datanode":
            return int(config.get("rpc_port", config.get("dn_rpc_port", 6667)))
        return int(config.get("rpc_port", 6667))

    def _safe_path_segment(self, value: Any) -> str:
        segment = "".join(
            char if char.isalnum() or char in {"-", "_"} else "-"
            for char in str(value or "node")
        ).strip("-")
        return segment or "node"

    def _build_iot_benchmark_replacements(
        self,
        config: Dict[str, Any],
        target_host: str,
        rpc_port: int
    ) -> Dict[str, Any]:
        replacements: Dict[str, Any] = {
            "DB_SWITCH": config.get("db_switch", "IoTDB-200-SESSION_BY_TABLET"),
            "IoTDB_DIALECT_MODE": config.get("dialect", "tree"),
            "HOST": target_host,
            "PORT": rpc_port,
            "USERNAME": config.get("username", "root"),
            "PASSWORD": config.get("password", "root"),
            "DB_NAME": config.get("db_name", "test"),
            "BENCHMARK_WORK_MODE": config.get("work_mode", "testWithDefaultPath"),
            "LOOP": config.get("loop", 100),
            "OPERATION_PROPORTION": config.get("operation_proportion", "1:0:0:0:0:0:0:0:0:0:0:0"),
        }

        extra_items = config.get("config_items")
        if isinstance(extra_items, dict):
            for key, value in extra_items.items():
                if key and value is not None:
                    replacements[str(key)] = value

        return {
            key: value
            for key, value in replacements.items()
            if value is not None and str(value) != ""
        }

    def _tail_remote_file(self, server: Server, remote_path: str, tail_lines: int) -> Dict[str, Any]:
        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command=f"tail -n {tail_lines} {self._quote(remote_path)} 2>/dev/null || true",
            port=server.port,
            timeout=30
        )
        return self._ssh_result_to_dict(result)

    def _start_script_for_role(self, role: str) -> str:
        if role == "confignode":
            return "start-confignode.sh"
        if role == "datanode":
            return "start-datanode.sh"
        return "start-standalone.sh"

    def _stop_script_for_role(self, role: str) -> str:
        if role == "confignode":
            return "stop-confignode.sh"
        if role == "datanode":
            return "stop-datanode.sh"
        return "stop-standalone.sh"

    def _detect_package_type(self, remote_path: str, package_type: str) -> Optional[str]:
        if package_type != "auto":
            if package_type in {"zip", "tar.gz"}:
                return package_type
            if package_type == "tgz":
                return "tar.gz"
            return None

        lower = remote_path.lower()
        if lower.endswith(".zip"):
            return "zip"
        if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            return "tar.gz"
        return None

    def _replace_properties(self, content: str, replacements: Dict[str, Any]) -> str:
        lines = content.splitlines()
        remaining = {str(key): str(value) for key, value in replacements.items()}
        updated_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                updated_lines.append(line)
                continue

            key, _, _ = line.partition("=")
            prop_key = key.strip()
            if prop_key in remaining:
                updated_lines.append(f"{prop_key}={remaining.pop(prop_key)}")
            else:
                updated_lines.append(line)

        if remaining:
            if updated_lines and updated_lines[-1].strip():
                updated_lines.append("")
            for key, value in remaining.items():
                updated_lines.append(f"{key}={value}")

        return "\n".join(updated_lines) + "\n"

    def _ssh_result_to_dict(self, result) -> Dict[str, Any]:
        payload = {
            "exit_status": result.exit_status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": result.error
        }
        if getattr(result, "ssh_port", None) is not None:
            payload["ssh_port"] = result.ssh_port
        return payload

    def _quote(self, value: str) -> str:
        return self.ssh_service.quote(value)
