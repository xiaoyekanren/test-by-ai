import os
import time
from typing import Any, Dict, List, Optional

from app.models.database import Server


class UtilsMixin:

    def _apply_config_file_to_server(
        self,
        server: Server,
        file_path: str,
        replacements: Dict[str, Any],
        timeout: int,
        backup_before_write: bool
    ) -> Dict[str, Any]:
        read_result = self.ssh_service.read_file(
            host=server.host,
            username=server.username,
            password=server.password,
            remote_path=file_path,
            port=server.port,
            timeout=timeout
        )
        if read_result["status"] != "success":
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": read_result.get("message", ""),
                "error": read_result.get("message", "Failed to read config file")
            }

        updated = self._replace_properties(read_result["content"], replacements)
        backup_path = None
        if backup_before_write:
            backup_path = f"{file_path}.bak.{int(time.time())}"
            backup_result = self.ssh_service.run_command(
                host=server.host,
                username=server.username,
                password=server.password,
                command=f"cp {self._quote(file_path)} {self._quote(backup_path)}",
                port=server.port,
                timeout=timeout
            )
            if backup_result.exit_status != 0:
                return self._ssh_result_to_dict(backup_result)

        write_result = self.ssh_service.write_file(
            host=server.host,
            username=server.username,
            password=server.password,
            remote_path=file_path,
            content=updated,
            port=server.port,
            timeout=timeout
        )
        if write_result["status"] != "success":
            return {
                "exit_status": -1,
                "stdout": "",
                "stderr": write_result.get("message", ""),
                "error": write_result.get("message", "Failed to write config file")
            }

        result: Dict[str, Any] = {
            "exit_status": 0,
            "stdout": f"Updated configuration file {file_path}",
            "stderr": "",
            "file_path": file_path,
            "conf_path": file_path,
            "updated_keys": sorted(replacements.keys())
        }
        if backup_path:
            result["backup_path"] = backup_path
        return result

    def _deploy_package_to_server(
        self,
        server: Server,
        artifact_local_path: Any,
        remote_package_path: str,
        install_dir: str,
        package_type: str,
        extract_subdir: str,
        overwrite: bool,
        timeout: int,
        node_role: str,
        expected_scripts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not remote_package_path:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "remote_package_path is required"}

        if artifact_local_path:
            upload_result = self._execute_upload_node({
                "server_id": server.id,
                "local_path": artifact_local_path,
                "remote_path": remote_package_path,
                "timeout": timeout
            })
            if upload_result.get("exit_status") != 0:
                return upload_result

        detected_type = self._detect_package_type(remote_package_path, package_type)
        if detected_type is None:
            return {"exit_status": -1, "stdout": "", "stderr": "", "error": "Unsupported package_type"}

        scripts_to_check = expected_scripts or [self._start_script_for_role(node_role)]
        tmp_dir = f"{install_dir}.extracting"
        commands = [
            "set -e",
            f"mkdir -p {self._quote(os.path.dirname(install_dir) or '/')}",
        ]
        if overwrite:
            commands.append(f"rm -rf {self._quote(install_dir)}")
        commands.extend([
            f"rm -rf {self._quote(tmp_dir)}",
            f"mkdir -p {self._quote(tmp_dir)}"
        ])

        if detected_type == "tar.gz":
            commands.append(f"tar -xzf {self._quote(remote_package_path)} -C {self._quote(tmp_dir)}")
        else:
            commands.append(f"unzip -q {self._quote(remote_package_path)} -d {self._quote(tmp_dir)}")

        if extract_subdir:
            source_dir_expr = f"{tmp_dir.rstrip('/')}/{extract_subdir}"
        else:
            source_dir_expr = '$(find ' + self._quote(tmp_dir) + " -mindepth 1 -maxdepth 1 -type d | head -n 1)"

        commands.extend([
            f"source_dir={source_dir_expr}",
            'if [ -z "$source_dir" ]; then source_dir=' + self._quote(tmp_dir) + "; fi",
            f"mkdir -p {self._quote(install_dir)}",
            f"cp -R \"$source_dir\"/. {self._quote(install_dir)}/"
        ])
        for script in sorted(set(scripts_to_check)):
            expected_script_path = f"{install_dir.rstrip('/')}/sbin/{script}"
            commands.append(f"test -f {self._quote(expected_script_path)}")
        commands.append(f"rm -rf {self._quote(tmp_dir)}")

        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command="bash -lc " + self._quote("\n".join(commands)),
            port=server.port,
            timeout=timeout
        )
        payload = self._ssh_result_to_dict(result)
        payload.update({
            "remote_package_path": remote_package_path,
            "iotdb_home": install_dir,
            "conf_path": self._default_config_path(install_dir),
            "expected_start_script": sorted(set(scripts_to_check))[0],
            "expected_start_scripts": sorted(set(scripts_to_check))
        })
        return payload

    def _required_str(self, config: Dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = config.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        raise ValueError(f"Missing required config field: {'/'.join(keys)}")

    def _normalize_line_list(self, value: Any) -> List[str]:
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _normalize_node_role(self, role: Any) -> str:
        value = str(role or "standalone").strip().lower()
        if value in {"confignode", "config_node", "config-node"}:
            return "confignode"
        if value in {"datanode", "data_node", "data-node"}:
            return "datanode"
        return "standalone"

    def _default_config_path(self, iotdb_home: str) -> str:
        return f"{iotdb_home.rstrip('/')}/conf/iotdb-system.properties"

    def _default_wait_port(self, role: str, config: Dict[str, Any]) -> int:
        if role == "confignode":
            return int(config.get("cn_internal_port", 10710))
        if role == "datanode":
            return int(config.get("rpc_port", config.get("dn_rpc_port", 6667)))
        return int(config.get("rpc_port", 6667))

    def _safe_path_segment(self, value: Any) -> str:
        segment = "".join(
            char if char.isalnum() or char in {"-", "_"} else "-"
            for char in str(value or "node")
        ).strip("-")
        return segment or "node"

    def _start_script_for_role(self, role: str) -> str:
        if role == "confignode":
            return "start-confignode.sh"
        if role == "datanode":
            return "start-datanode.sh"
        return "start-standalone.sh"

    def _stop_script_for_role(self, role: str) -> str:
        if role == "confignode":
            return "stop-confignode.sh"
        if role == "datanode":
            return "stop-datanode.sh"
        return "stop-standalone.sh"

    def _detect_package_type(self, remote_path: str, package_type: str) -> Optional[str]:
        if package_type != "auto":
            if package_type in {"zip", "tar.gz"}:
                return package_type
            if package_type == "tgz":
                return "tar.gz"
            return None

        lower = remote_path.lower()
        if lower.endswith(".zip"):
            return "zip"
        if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            return "tar.gz"
        return None

    def _replace_properties(self, content: str, replacements: Dict[str, Any]) -> str:
        lines = content.splitlines()
        remaining = {str(key): str(value) for key, value in replacements.items()}
        updated_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                updated_lines.append(line)
                continue

            key, _, _ = line.partition("=")
            prop_key = key.strip()
            if prop_key in remaining:
                updated_lines.append(f"{prop_key}={remaining.pop(prop_key)}")
            else:
                updated_lines.append(line)

        if remaining:
            if updated_lines and updated_lines[-1].strip():
                updated_lines.append("")
            for key, value in remaining.items():
                updated_lines.append(f"{key}={value}")

        return "\n".join(updated_lines) + "\n"

    def _ssh_result_to_dict(self, result) -> Dict[str, Any]:
        payload = {
            "exit_status": result.exit_status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": result.error
        }
        if getattr(result, "ssh_port", None) is not None:
            payload["ssh_port"] = result.ssh_port
        return payload

    def _quote(self, value: str) -> str:
        return self.ssh_service.quote(value)
