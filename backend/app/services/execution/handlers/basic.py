import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BasicHandlersMixin:

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
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        server = self._require_server(config, context)
        role = self._normalize_node_role(config.get("node_role"))
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

    def _execute_iotdb_config_node(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        server = self._require_server(config, context)
        role = self._normalize_node_role(config.get("node_role"))
        iotdb_home = self._required_str(config, "iotdb_home")
        file_path = config.get("file_path") or self._default_config_path(iotdb_home)
        replacements = config.get("config_items") or {}

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
