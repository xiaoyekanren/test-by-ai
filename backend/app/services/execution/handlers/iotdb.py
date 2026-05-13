import shlex
import time
from typing import Any, Dict, List, Optional

from app.models.database import Server


class IoTDBHandlersMixin:

    def _execute_iotdb_deploy_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import os
        server = self._require_server(config, context)
        role = self._normalize_node_role(config.get("node_role"))
        install_dir = self._required_str(config, "install_dir")
        remote_package_path = config.get("remote_package_path")
        if not remote_package_path and config.get("artifact_local_path"):
            remote_package_path = f"/tmp/{os.path.basename(str(config['artifact_local_path']))}"

        deploy_result = self._deploy_package_to_server(
            server=server,
            artifact_local_path=config.get("artifact_local_path"),
            package_url=config.get("package_url"),
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
        start_script = f"cd {self._quote(iotdb_home)} && bash sbin/{script_name} && true"
        start_result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command=start_script,
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

    def _execute_iotdb_ainode_deploy_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import os

        server = self._require_server(config, context)
        install_dir = self._required_str(config, "install_dir", "ainode_home")
        remote_package_path = config.get("remote_package_path")
        if not remote_package_path and config.get("artifact_local_path"):
            remote_package_path = f"/tmp/{os.path.basename(str(config['artifact_local_path']))}"

        deploy_result = self._deploy_package_to_server(
            server=server,
            artifact_local_path=config.get("artifact_local_path"),
            package_url=config.get("package_url"),
            remote_package_path=str(remote_package_path or ""),
            install_dir=install_dir,
            package_type=str(config.get("package_type", "auto")),
            extract_subdir=str(config.get("extract_subdir", "") or "").strip("/"),
            overwrite=bool(config.get("overwrite", False)),
            timeout=int(config.get("timeout", 600)),
            node_role="ainode",
            expected_scripts=["start-ainode.sh", "stop-ainode.sh"],
            expected_paths=[
                "conf/iotdb-ainode.properties",
                "lib/ainode",
                "sbin/start-ainode.sh",
                "sbin/stop-ainode.sh",
            ]
        )
        if deploy_result.get("exit_status") != 0:
            return deploy_result

        conf_path = self._ainode_config_path(install_dir)
        replacements = self._build_ainode_replacements(config, server)
        config_result = self._apply_config_file_to_server(
            server=server,
            file_path=conf_path,
            replacements=replacements,
            timeout=int(config.get("timeout", 600)),
            backup_before_write=bool(config.get("backup_before_write", True))
        )
        if config_result.get("exit_status") != 0:
            config_result.update({
                "ainode_home": install_dir,
                "ainode_conf_path": conf_path,
                "remote_package_path": deploy_result.get("remote_package_path"),
                "package_url": deploy_result.get("package_url"),
            })
            return config_result

        stdout = "\n".join(
            part for part in [deploy_result.get("stdout", ""), config_result.get("stdout", "")]
            if part
        ).strip()
        result = {
            **deploy_result,
            "stdout": stdout,
            "ainode_home": install_dir,
            "iotdb_home": install_dir,
            "ainode_conf_path": conf_path,
            "conf_path": conf_path,
            "ain_rpc_address": replacements["ain_rpc_address"],
            "ain_rpc_port": int(replacements["ain_rpc_port"]),
            "wait_port": int(replacements["ain_rpc_port"]),
            "ain_seed_config_node": replacements["ain_seed_config_node"],
            "ain_cluster_ingress_address": replacements["ain_cluster_ingress_address"],
            "ain_cluster_ingress_port": int(replacements["ain_cluster_ingress_port"]),
            "backup_path": config_result.get("backup_path"),
            "config_items": replacements,
            "server_id": server.id,
            "host": server.host,
        }
        return result

    def _execute_iotdb_ainode_start_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        ainode_home = self._required_str(config, "ainode_home", "iotdb_home", "install_dir")
        host = str(config.get("ain_rpc_address") or config.get("host") or server.host or "127.0.0.1")
        wait_port = int(config.get("wait_port", config.get("ain_rpc_port", 10810)))
        timeout_seconds = int(config.get("timeout_seconds", config.get("timeout", 60)))

        start_script = f"cd {self._quote(ainode_home)} && bash sbin/start-ainode.sh -d && true"
        start_result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command=start_script,
            port=server.port,
            timeout=min(timeout_seconds, 60)
        )
        if start_result.exit_status != 0:
            payload = self._ssh_result_to_dict(start_result)
            payload.update({"ainode_home": ainode_home, "ain_rpc_address": host, "ain_rpc_port": wait_port, "wait_port": wait_port})
            return payload

        deadline = time.time() + timeout_seconds
        last_result = None
        while time.time() < deadline:
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
                    "ainode_home": ainode_home,
                    "iotdb_home": ainode_home,
                    "ain_rpc_address": host,
                    "ain_rpc_port": wait_port,
                    "wait_port": wait_port,
                    "host": host,
                    "start_script": "start-ainode.sh"
                }
            time.sleep(2)

        return {
            "exit_status": -1,
            "stdout": start_result.stdout,
            "stderr": (last_result.stderr if last_result else ""),
            "error": f"IoTDB AINode did not become ready within {timeout_seconds} seconds",
            "ainode_home": ainode_home,
            "ain_rpc_address": host,
            "ain_rpc_port": wait_port,
            "wait_port": wait_port,
            "start_script": "start-ainode.sh"
        }

    def _execute_iotdb_ainode_stop_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        ainode_home = self._required_str(config, "ainode_home", "iotdb_home", "install_dir")
        timeout_seconds = int(config.get("timeout_seconds", config.get("timeout", 60)))
        target = config.get("remove_target") or config.get("ain_remove_target")
        script = "bash sbin/stop-ainode.sh"
        if target:
            script += f" -t {self._quote(str(target))}"

        stop_script = f"cd {self._quote(ainode_home)} && {script}"
        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote(stop_script),
            port=server.port,
            timeout=timeout_seconds
        )
        payload = self._ssh_result_to_dict(result)
        payload["ainode_home"] = ainode_home
        payload["iotdb_home"] = ainode_home
        payload["stop_script"] = "stop-ainode.sh"
        if config.get("ain_rpc_port") not in (None, ""):
            payload["ain_rpc_port"] = int(config["ain_rpc_port"])
        return payload

    def _execute_iotdb_ainode_check_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        target = self._resolve_ainode_check_target(config, context or {})
        server = self.db.query(Server).filter(Server.id == int(target["server_id"])).first()
        if not server:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "A valid DataNode server is required for AINode check"}
        username = str(config.get("username") or "root")
        password = str(config.get("password") or "root")
        sql_dialect = str(config.get("sql_dialect") or "tree")
        timeout_seconds = int(config.get("timeout_seconds", config.get("timeout", 300)))
        validation_sqls = ["show ainodes"] + self._normalize_line_list(config.get("validation_sqls") or [])

        result = self._run_sql_batch(
            server=server,
            iotdb_home=str(target["iotdb_home"]),
            host=str(target["host"]),
            rpc_port=int(target["rpc_port"]),
            username=username,
            password=password,
            sql_dialect=sql_dialect,
            sql_list=validation_sqls,
            timeout_seconds=timeout_seconds
        )
        result.update({
            "iotdb_home": target["iotdb_home"],
            "host": target["host"],
            "rpc_port": int(target["rpc_port"]),
            "checked_sqls": validation_sqls,
        })
        return result

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

    def _ainode_config_path(self, ainode_home: str) -> str:
        return f"{ainode_home.rstrip('/')}/conf/iotdb-ainode.properties"

    def _build_ainode_replacements(self, config: Dict[str, Any], server: Server) -> Dict[str, str]:
        config_nodes = config.get("config_nodes") if isinstance(config.get("config_nodes"), list) else []
        data_nodes = config.get("data_nodes") if isinstance(config.get("data_nodes"), list) else []
        seed_node = config_nodes[0] if config_nodes and isinstance(config_nodes[0], dict) else {}
        ingress_node = data_nodes[0] if data_nodes and isinstance(data_nodes[0], dict) else {}

        seed_host = str(seed_node.get("host") or config.get("cn_host") or config.get("seed_config_node_host") or "127.0.0.1")
        seed_port = int(seed_node.get("cn_internal_port") or config.get("cn_internal_port") or config.get("seed_config_node_port") or 10710)
        ingress_host = str(
            config.get("ain_cluster_ingress_address")
            or config.get("target_host")
            or ingress_node.get("host")
            or config.get("host")
            or server.host
            or "127.0.0.1"
        )
        ingress_port = int(
            config.get("ain_cluster_ingress_port")
            or config.get("target_rpc_port")
            or ingress_node.get("dn_rpc_port")
            or ingress_node.get("rpc_port")
            or config.get("rpc_port")
            or 6667
        )
        replacements: Dict[str, str] = {
            "cluster_name": str(config.get("cluster_name") or "defaultCluster"),
            "ain_seed_config_node": str(config.get("ain_seed_config_node") or f"{seed_host}:{seed_port}"),
            "ain_rpc_address": str(config.get("ain_rpc_address") or server.host or "127.0.0.1"),
            "ain_rpc_port": str(int(config.get("ain_rpc_port", config.get("wait_port", 10810)))),
            "ain_cluster_ingress_address": ingress_host,
            "ain_cluster_ingress_port": str(ingress_port),
            "ain_cluster_ingress_username": str(config.get("username") or config.get("ain_cluster_ingress_username") or "root"),
            "ain_cluster_ingress_password": str(config.get("password") or config.get("ain_cluster_ingress_password") or "root"),
        }

        config_items = config.get("config_items") or {}
        if isinstance(config_items, dict):
            for key, value in config_items.items():
                replacements[str(key)] = str(value)
        return replacements

    def _resolve_ainode_check_target(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        data_nodes = config.get("data_nodes") if isinstance(config.get("data_nodes"), list) else []
        if data_nodes:
            primary = next((item for item in data_nodes if isinstance(item, dict) and item.get("server_id") is not None), None)
            if primary:
                return {
                    "server_id": int(primary["server_id"]),
                    "iotdb_home": str(primary.get("install_dir") or config.get("iotdb_home") or context.get("iotdb_home") or ""),
                    "host": str(primary.get("host") or config.get("host") or context.get("host") or "127.0.0.1"),
                    "rpc_port": int(primary.get("dn_rpc_port") or primary.get("rpc_port") or config.get("rpc_port") or 6667),
                }

        return {
            "server_id": int(self._required_str(config, "server_id")),
            "iotdb_home": self._required_str(config, "iotdb_home"),
            "host": str(config.get("host") or context.get("host") or "127.0.0.1"),
            "rpc_port": int(config.get("rpc_port", 6667)),
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
