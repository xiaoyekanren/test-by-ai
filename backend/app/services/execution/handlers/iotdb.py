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
