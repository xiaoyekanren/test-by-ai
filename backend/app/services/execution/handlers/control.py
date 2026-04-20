import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ControlHandlersMixin:

    def _execute_condition_node(
        self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        expression = str(config.get("expression", "")).strip()
        if not expression:
            return {
                "exit_status": 0,
                "branch": "true",
                "stdout": "No expression provided, defaulting to true branch",
                "stderr": "",
            }

        server = self._try_resolve_server(config, context or {})
        if not server:
            return {
                "exit_status": 0,
                "branch": "true",
                "stdout": "No server available, defaulting to true branch",
                "stderr": "",
            }

        timeout = int(config.get("timeout", 30))
        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command=expression,
            port=server.port,
            timeout=timeout,
        )
        branch = "true" if result.exit_status == 0 else "false"
        payload = self._ssh_result_to_dict(result)
        payload["branch"] = branch
        payload["exit_status"] = 0
        return payload

    def _execute_loop_node(
        self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        loop_type = config.get("loop_type", "for")
        iterations = max(1, int(config.get("iterations", 1)))
        condition = str(config.get("condition", "")).strip()

        return {
            "exit_status": 0,
            "stdout": f"Loop node: type={loop_type}, iterations={iterations}",
            "stderr": "",
            "loop_type": loop_type,
            "loop_iterations": iterations,
            "loop_condition": condition,
        }

    def _execute_wait_node(
        self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        condition_cmd = str(config.get("condition", "")).strip()
        timeout = max(1, int(config.get("timeout", 60)))
        interval = max(1, int(config.get("interval", 5)))

        if not condition_cmd:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "Wait condition is required"}

        server = self._try_resolve_server(config, context or {})
        if not server:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "No server available for wait node"}

        deadline = time.monotonic() + timeout
        attempt = 0

        while time.monotonic() < deadline:
            attempt += 1
            result = self.ssh_service.run_command(
                host=server.host,
                username=server.username,
                password=server.password,
                command=condition_cmd,
                port=server.port,
                timeout=min(30, timeout),
            )
            if result.exit_status == 0:
                payload = self._ssh_result_to_dict(result)
                payload["wait_attempts"] = attempt
                return payload

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(interval, remaining))

        return {
            "exit_status": -1,
            "stdout": "",
            "stderr": result.stderr if result else "",
            "error": f"Wait condition not met within {timeout}s after {attempt} attempts",
            "wait_attempts": attempt,
        }

    def _execute_parallel_node(
        self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        max_concurrent = int(config.get("max_concurrent", 5))
        return {
            "exit_status": 0,
            "stdout": f"Parallel gate: max_concurrent={max_concurrent}",
            "stderr": "",
            "max_concurrent": max_concurrent,
        }

    def _execute_assert_node(
        self, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        assert_type = str(config.get("assert_type", "custom")).strip()
        params = config.get("params") or {}
        if isinstance(params, str):
            import json
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, ValueError):
                params = {}
        expected = str(config.get("expected", "")).strip()

        server = self._try_resolve_server(config, context or {})
        if not server:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "No server available for assert node"}

        command = self._build_assert_command(assert_type, params, expected)
        if not command:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": f"Unknown assert_type: {assert_type}"}

        timeout = int(config.get("timeout", 30))
        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command=command,
            port=server.port,
            timeout=timeout,
        )
        payload = self._ssh_result_to_dict(result)
        payload["assert_type"] = assert_type
        payload["assert_passed"] = result.exit_status == 0
        return payload

    def _build_assert_command(
        self, assert_type: str, params: Dict[str, Any], expected: str
    ) -> Optional[str]:
        if assert_type == "log_contains":
            file_path = params.get("file_path", "")
            pattern = expected or params.get("pattern", "")
            if not file_path or not pattern:
                return None
            return f"grep -q {self._quote(pattern)} {self._quote(file_path)}"

        if assert_type == "file_exists":
            file_path = expected or params.get("file_path", "")
            if not file_path:
                return None
            return f"test -f {self._quote(file_path)}"

        if assert_type == "process_running":
            process_name = expected or params.get("process_name", "")
            if not process_name:
                return None
            return f"pgrep -f {self._quote(process_name)} > /dev/null 2>&1"

        if assert_type == "port_open":
            port = params.get("port", expected)
            host = params.get("host", "127.0.0.1")
            if not port:
                return None
            return f"ss -tlnp | grep -q ':{port} ' || nc -z {self._quote(host)} {port}"

        if assert_type == "custom":
            command = expected or params.get("command", "")
            return command if command else None

        return None

    def _try_resolve_server(self, config: Dict[str, Any], context: Dict[str, Any]):
        try:
            return self._resolve_server_with_region(config, context)
        except Exception:
            return None
