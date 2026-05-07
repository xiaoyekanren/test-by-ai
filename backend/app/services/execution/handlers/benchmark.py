import os
import re
import shlex
import time
from typing import Any, Dict, List, Optional, Tuple

from app.models.database import Server
from app.utils.time import utc_now


class BenchmarkHandlersMixin:

    def _execute_iot_benchmark_deploy_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        install_dir = self._required_str(config, "install_dir").rstrip("/")
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
            node_role="iot_benchmark",
            expected_scripts=[],
            expected_paths=["benchmark.sh", "conf/config.properties"],
        )
        if deploy_result.get("exit_status") != 0:
            return deploy_result

        deploy_result.update({
            "server_id": server.id,
            "server_name": server.name,
            "region": server.region,
            "host": server.host,
            "benchmark_home": install_dir,
            "benchmark_conf_path": f"{install_dir}/conf/config.properties",
        })
        return deploy_result

    def _execute_iot_benchmark_start_node(self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server = self._require_server(config, context)
        timeout = int(config.get("timeout", 60))
        benchmark_home = self._required_str(config, "benchmark_home").rstrip("/")
        target_host, rpc_port = self._build_iot_benchmark_targets(config, server)
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
            "benchmark_home": benchmark_home,
            "started_at": utc_now().isoformat()
        }
        return {
            "exit_status": 0,
            "stdout": f"Started IoT Benchmark pid={pid} on server {server.id}",
            "stderr": start_result.stderr,
            "benchmark_run": benchmark_run,
            "server_id": server.id,
            "region": server.region,
            "benchmark_home": benchmark_home,
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
        server_config = dict(config)
        if server_id not in (None, ""):
            server_config["server_id"] = server_id
        server_config.setdefault("_node_type", "iot_benchmark_wait")
        server_config["schedule_role"] = self._schedule_role(server_config)
        server = self._require_server(server_config, context or {})
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
            "summary": self._parse_iot_benchmark_summary(result.stdout),
            "finished_at": utc_now().isoformat()
        }
        return payload

    def _build_iot_benchmark_targets(self, config: Dict[str, Any], server: Server) -> Tuple[str, Any]:
        data_nodes = config.get("data_nodes")
        if isinstance(data_nodes, list) and data_nodes:
            hosts: List[str] = []
            ports: List[str] = []
            for item in data_nodes:
                if not isinstance(item, dict):
                    continue
                host = str(item.get("host") or "").strip()
                if not host and item.get("server_id") not in (None, ""):
                    target_server = self.db.query(Server).filter(Server.id == int(item["server_id"])).first()
                    host = target_server.host if target_server else ""
                if not host:
                    continue
                port = item.get("rpc_port") or item.get("dn_rpc_port") or item.get("wait_port") or config.get("rpc_port", 6667)
                hosts.append(host)
                ports.append(str(int(port)))
            if hosts:
                return ",".join(hosts), ",".join(ports)

        target_host = str(config.get("target_host") or config.get("host") or server.host).strip()
        return target_host, int(config.get("rpc_port", 6667))

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
        direct_mappings = {
            "DEVICE_NUMBER": "device_number",
            "SENSOR_NUMBER": "sensor_number",
            "DATA_CLIENT_NUMBER": "data_client_number",
            "SCHEMA_CLIENT_NUMBER": "schema_client_number",
            "BATCH_SIZE_PER_WRITE": "batch_size_per_write",
            "DEVICE_NUM_PER_WRITE": "device_num_per_write",
            "CREATE_SCHEMA": "create_schema",
            "IS_DELETE_DATA": "is_delete_data",
            "POINT_STEP": "point_step",
            "QUERY_SENSOR_NUM": "query_sensor_num",
            "QUERY_DEVICE_NUM": "query_device_num",
            "QUERY_INTERVAL": "query_interval",
            "WRITE_OPERATION_TIMEOUT_MS": "write_operation_timeout_ms",
            "READ_OPERATION_TIMEOUT_MS": "read_operation_timeout_ms",
            "TEST_MAX_TIME": "test_max_time",
            "RESULT_PRINT_INTERVAL": "result_print_interval",
            "ENABLE_FIXED_QUERY": "enable_fixed_query",
            "TEST_DATA_PERSISTENCE": "test_data_persistence",
            "CSV_OUTPUT": "csv_output",
        }
        for property_key, config_key in direct_mappings.items():
            if config_key in config:
                replacements[property_key] = self._format_iot_benchmark_property(config[config_key])

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

    def _format_iot_benchmark_property(self, value: Any) -> Any:
        if isinstance(value, bool):
            return str(value).lower()
        return value

    def _parse_iot_benchmark_summary(self, stdout: str) -> Dict[str, Any]:
        operation_lines: Dict[str, str] = {}
        metrics: Dict[str, float] = {}
        metric_patterns = {
            "throughput": r"throughput[^0-9-]*(-?\d+(?:\.\d+)?)",
            "avg_latency": r"(?:avg|average)[^0-9-]*(-?\d+(?:\.\d+)?)",
            "p95_latency": r"p95[^0-9-]*(-?\d+(?:\.\d+)?)",
            "p99_latency": r"p99[^0-9-]*(-?\d+(?:\.\d+)?)",
            "ok_count": r"(?:ok|success)[^0-9-]*(\d+)",
            "fail_count": r"(?:fail|error)[^0-9-]*(\d+)",
        }
        operation_names = {
            "INGESTION", "PRECISE_QUERY", "RANGE_QUERY", "VALUE_RANGE_QUERY",
            "AGG_RANGE_QUERY", "AGG_VALUE_QUERY", "AGG_RANGE_VALUE_QUERY",
            "GROUP_BY_QUERY", "LATEST_POINT_QUERY", "VERIFICATION_QUERY",
            "DEVICE_QUERY", "SET_OP_QUERY",
        }

        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        for line in lines:
            upper_line = line.upper()
            for operation_name in operation_names:
                if operation_name in upper_line:
                    operation_lines[operation_name] = line
            normalized = line.lower()
            for metric_key, pattern in metric_patterns.items():
                match = re.search(pattern, normalized)
                if match:
                    value = float(match.group(1))
                    metrics[metric_key] = int(value) if value.is_integer() else value

        return {
            "metrics": metrics,
            "operation_lines": operation_lines,
            "line_count": len(lines),
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
