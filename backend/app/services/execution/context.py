from typing import Any, Dict

from app.models.database import Server


class ContextMixin:

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
            "benchmark_home",
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
            "data_nodes", "benchmark_home", "benchmark_run", "benchmark_result",
            "target_host", "region"
        ]:
            if key in result and result[key] not in (None, ""):
                updates[key] = result[key]

        if node_type == "iotdb_cli" and result.get("executed_sqls"):
            updates["executed_sqls"] = result["executed_sqls"]
        return updates
