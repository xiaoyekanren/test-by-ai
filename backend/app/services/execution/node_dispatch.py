import logging
from typing import Any, Callable, Dict

from app.models.database import NodeExecution
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class NodeDispatchMixin:

    def _execute_workflow_node(
        self,
        execution_id: int,
        node: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        from app.services.execution.engine import ExecutionEngine

        db = self.session_factory()
        try:
            worker = ExecutionEngine(
                db,
                session_factory=self.session_factory,
                reservation_lock=self.reservation_lock
            )
            worker.ssh_service = self.ssh_service
            return worker._execute_workflow_node_in_session(execution_id, node, context)
        finally:
            db.close()

    def _execute_workflow_node_in_session(
        self,
        execution_id: int,
        node: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        node_id = node.get("id")
        node_type = node.get("type", "shell")
        config = dict(node.get("config", {}) or {})
        config["_execution_id"] = execution_id
        config["_node_id"] = node_id

        with self.reservation_lock:
            if self._node_uses_top_level_server(node_type):
                explicit_region = config.get("region") not in (None, "")
                server = self._resolve_server_with_region(config, context)
                if server:
                    self._write_server_config(config, server)
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
                started_at=utc_now(),
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
            with self.reservation_lock:
                context_update = (
                    self._build_context_updates(node_type, config, result)
                    if node_execution.status == "success"
                    else {}
                )
        except Exception as exc:
            logger.exception("Error executing node %s", node_id)
            node_execution.status = "failed"
            node_execution.error_message = str(exc)
            node_execution.output_data = {"exit_status": -1, "error": str(exc)}
            context_update = {}

        with self.reservation_lock:
            node_execution.finished_at = utc_now()
            node_execution.duration = int(
                (node_execution.finished_at - node_execution.started_at).total_seconds()
            )
            self.db.commit()

        return {
            "node_id": node_id,
            "status": node_execution.status,
            "context": context_update,
            "error": node_execution.error_message,
        }

    def _execute_node(self, node_type: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        merged = self._merge_config_with_context(config, context)
        handler = self._node_handlers.get(node_type)
        if handler is not None:
            return handler(merged, context)
        return {
            "exit_status": 0,
            "stdout": "",
            "stderr": "",
            "message": f"Node type {node_type} executed without side effects"
        }
