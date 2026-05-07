from typing import Any, Dict, List, Optional

from app.models.database import Server


class ClusterHandlersMixin:

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

        deploy_targets = self._group_cluster_entries_by_install(config_nodes + data_nodes)

        for target in deploy_targets:
            server = self._require_server({
                "server_id": target["server_id"],
                "_schedule_mode": config.get("_schedule_mode"),
                "_schedule_region": config.get("_schedule_region"),
            }, context)
            entries = target["entries"]
            deploy_result = self._deploy_package_to_server(
                server=server,
                artifact_local_path=config.get("artifact_local_path"),
                remote_package_path=self._required_str(config, "remote_package_path"),
                install_dir=str(target["install_dir"]),
                package_type=str(config.get("package_type", "auto")),
                extract_subdir=str(config.get("extract_subdir", "") or "").strip("/"),
                overwrite=bool(config.get("overwrite", False)),
                timeout=int(config.get("timeout", 900)),
                node_role="cluster",
                expected_scripts=[
                    self._start_script_for_role(str(entry["node_role"]))
                    for entry in entries
                ]
            )
            results.append({"step": "deploy", "node": target, "result": deploy_result})
            stdout_parts.append(deploy_result.get("stdout", ""))
            if deploy_result.get("exit_status") != 0:
                return self._cluster_failure("Cluster deploy failed during package deployment", results, cluster_name, config_nodes, data_nodes)

            replacements = self._build_cluster_replacements_for_entries(entries, cluster_name, seed, common_config)
            config_result = self._apply_config_file_to_server(
                server=server,
                file_path=self._default_config_path(str(target["install_dir"])),
                replacements=replacements,
                timeout=int(config.get("timeout", 900)),
                backup_before_write=bool(config.get("backup_before_write", True))
            )
            results.append({"step": "config", "node": target, "result": config_result})
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
            install_dir = str(item.get("install_dir") or base_install_dir.rstrip("/"))
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

    def _group_cluster_entries_by_install(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[tuple[int, str], Dict[str, Any]] = {}
        for entry in entries:
            key = (int(entry["server_id"]), str(entry["install_dir"]).rstrip("/"))
            if key not in grouped:
                grouped[key] = {
                    "server_id": key[0],
                    "host": entry["host"],
                    "install_dir": key[1],
                    "entries": []
                }
            grouped[key]["entries"].append(entry)
        return list(grouped.values())

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

    def _build_cluster_replacements_for_entries(
        self,
        entries: List[Dict[str, Any]],
        cluster_name: str,
        seed_config_node: str,
        common_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        replacements = {str(key): str(value) for key, value in common_config.items()}
        replacements["cluster_name"] = cluster_name

        for entry in entries:
            role_replacements = self._build_cluster_replacements(
                entry=entry,
                cluster_name=cluster_name,
                seed_config_node=seed_config_node,
                common_config={}
            )
            replacements.update(role_replacements)

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
