import logging
import random
from typing import Any, Dict, List, Optional

from app.models.database import Execution, NodeExecution, Server

logger = logging.getLogger(__name__)


class ServerResolutionMixin:

    def _require_server(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Server:
        server = self._resolve_server_for_schedule(config, context or {})
        if not server:
            raise ValueError("A valid scheduled server is required")
        return server

    def _resolve_server(self, config: Dict[str, Any]) -> Optional[Server]:
        server_id = config.get("server_id")
        if server_id is None:
            return None
        return self.db.query(Server).filter(Server.id == int(server_id)).first()

    def _resolve_server_for_schedule(self, config: Dict[str, Any], context: Dict[str, Any]) -> Optional[Server]:
        mode = self._schedule_mode(config, context)
        if mode == "fixed":
            server_id = config.get("server_id")
            if server_id in (None, ""):
                raise ValueError("Fixed scheduling mode requires server_id on every server node")
            return self.db.query(Server).filter(Server.id == int(server_id)).first()

        if mode == "random":
            role = self._schedule_role(config)
            server_id = self._scheduled_server_id_for_role(context, role)
            if server_id not in (None, ""):
                return self.db.query(Server).filter(Server.id == int(server_id)).first()
            return self._resolve_idle_server_by_region(self._schedule_region(config, context))

        raise ValueError(f"Unsupported schedule_mode: {mode}")

    def _resolve_server_with_region(self, config: Dict[str, Any], context: Dict[str, Any]) -> Optional[Server]:
        return self._resolve_server_for_schedule(config, context)

    def _resolve_idle_server_by_region(self, region: str) -> Optional[Server]:
        busy_server_ids = self._compute_busy_server_ids()

        query = self.db.query(Server).filter(
            Server.region == region,
            Server.schedulable.is_(True)
        )
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
        config["scheduled_server_id"] = server.id
        config["server_name"] = server.name
        config["host"] = server.host
        config["region"] = server.region or "私有云"

    def _schedule_role(self, config: Dict[str, Any]) -> str:
        role = str(config.get("schedule_role") or "").strip()
        if role:
            return role

        node_type = str(config.get("_node_type") or config.get("node_type") or "")
        if node_type.startswith("iot_benchmark_"):
            return "benchmark"
        return "default"

    def _scheduled_server_id_for_role(self, context: Dict[str, Any], role: str) -> Optional[int]:
        scheduled_servers = context.get("_scheduled_servers")
        if isinstance(scheduled_servers, dict):
            role_payload = scheduled_servers.get(role)
            if isinstance(role_payload, dict) and role_payload.get("server_id") not in (None, ""):
                return int(role_payload["server_id"])
            return None

        if role == "default" and context.get("server_id") not in (None, ""):
            return int(context["server_id"])
        return None

    def _scheduled_server_context(self, role: str, server: Server) -> Dict[str, Any]:
        return {
            role: {
                "server_id": server.id,
                "server_name": server.name,
                "host": server.host,
                "region": server.region or "私有云",
            }
        }

    def _target_region(self, config: Dict[str, Any], context: Dict[str, Any]) -> str:
        region = config.get("region")
        if region in (None, ""):
            region = context.get("region")
        if region in (None, ""):
            region = "私有云"
        return str(region)

    def _schedule_mode(self, config: Dict[str, Any], context: Dict[str, Any]) -> str:
        mode = config.get("_schedule_mode") or context.get("_schedule_mode")
        if mode in (None, ""):
            raise ValueError("Workflow schedule_mode is required")
        return str(mode)

    def _schedule_region(self, config: Dict[str, Any], context: Dict[str, Any]) -> str:
        region = config.get("_schedule_region") or context.get("_schedule_region")
        if region in (None, ""):
            raise ValueError("Workflow schedule_region is required for random scheduling")
        return str(region)

    def _compute_busy_server_ids(self) -> List[int]:
        running_executions = self.db.query(Execution.id).filter(
            Execution.status == "running"
        ).all()
        running_exec_ids = [e.id for e in running_executions]

        if not running_exec_ids:
            return []

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
                for field in ("config_nodes", "data_nodes"):
                    raw_nodes = ne.input_data.get(field)
                    if not isinstance(raw_nodes, list):
                        continue
                    for item in raw_nodes:
                        if isinstance(item, dict) and item.get("server_id") is not None:
                            busy_ids.append(int(item["server_id"]))

        return list(set(busy_ids))

    def _node_requires_server(self, node_type: str) -> bool:
        server_required_types = {
            "shell", "upload", "download", "config", "iotdb_config",
            "log_view", "iotdb_deploy", "iotdb_start", "iotdb_cli",
            "iotdb_stop", "iotdb_cluster_deploy", "iotdb_cluster_start",
            "iotdb_cluster_check", "iotdb_cluster_stop", "iot_benchmark_deploy",
            "iot_benchmark_start", "iot_benchmark_wait"
        }
        return node_type in server_required_types

    def _node_uses_top_level_server(self, node_type: str) -> bool:
        cluster_topology_types = {
            "iotdb_cluster_deploy",
            "iotdb_cluster_start",
            "iotdb_cluster_check",
            "iotdb_cluster_stop",
        }
        return self._node_requires_server(node_type) and node_type not in cluster_topology_types
