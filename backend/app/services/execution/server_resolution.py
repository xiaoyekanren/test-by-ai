import logging
import random
from typing import Any, Dict, List, Optional

from app.models.database import Execution, NodeExecution, Server

logger = logging.getLogger(__name__)


class ServerResolutionMixin:

    def _require_server(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Server:
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
            "iotdb_cluster_check", "iotdb_cluster_stop", "iot_benchmark_start",
            "iot_benchmark_wait"
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
