# backend/app/services/ssh_service.py
import os
from dataclasses import dataclass
from typing import Optional
import logging

import paramiko

logger = logging.getLogger(__name__)


@dataclass
class SSHResult:
    """Result of an SSH command execution."""
    exit_status: int
    stdout: str
    stderr: str
    error: Optional[str] = None
    ssh_port: Optional[int] = None


class SSHService:
    """SSH service for running commands and file transfer"""

    def _connect_client(
        self,
        host: str,
        username: Optional[str],
        password: Optional[str],
        port: int = 22,
        timeout: int = 30
    ) -> tuple[paramiko.SSHClient | None, Optional[int], Optional[Exception]]:
        ports_to_try = [22, port] if port != 22 else [22]
        last_exc = None

        for ssh_port in ports_to_try:
            try:
                client = paramiko.SSHClient()
                client.load_system_host_keys()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    hostname=host,
                    port=ssh_port,
                    username=username,
                    password=password,
                    timeout=timeout
                )
                return client, ssh_port, None
            except Exception as exc:
                last_exc = exc

        return None, None, last_exc

    def run_command(
        self,
        host: str,
        username: Optional[str],
        password: Optional[str],
        command: str,
        port: int = 22,
        timeout: int = 30
    ) -> SSHResult:
        """Execute command on remote server via SSH

        Args:
            host: The hostname or IP address of the remote server
            username: SSH username (optional)
            password: SSH password (optional)
            command: The command to execute
            port: SSH port (default 22, will also try this as alternate)
            timeout: Connection timeout in seconds

        Returns:
            SSHResult with exit_status, stdout, stderr, and optional error
        """
        client, ssh_port, error = self._connect_client(host, username, password, port, timeout)
        if client is None:
            return SSHResult(exit_status=-1, stdout="", stderr="", error=str(error))

        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode('utf-8', errors='ignore')
            err = stderr.read().decode('utf-8', errors='ignore')
            exit_status = stdout.channel.recv_exit_status()
            return SSHResult(exit_status=exit_status, stdout=out, stderr=err, ssh_port=ssh_port)
        except Exception as exc:
            return SSHResult(exit_status=-1, stdout="", stderr="", error=str(exc), ssh_port=ssh_port)
        finally:
            client.close()

    def upload_file(
        self,
        host: str,
        username: Optional[str],
        password: Optional[str],
        local_path: str,
        remote_path: str,
        port: int = 22,
        timeout: int = 30
    ) -> dict:
        """Upload file to remote server via SFTP

        Args:
            host: The hostname or IP address of the remote server
            username: SSH username (optional)
            password: SSH password (optional)
            local_path: Path to the local file to upload
            remote_path: Destination path on the remote server
            port: SSH port (default 22, will also try this as alternate)
            timeout: Connection timeout in seconds

        Returns:
            dict with 'status' key ('success' or 'error') and optional 'message'
        """
        client, ssh_port, error = self._connect_client(host, username, password, port, timeout)
        if client is None:
            return {"status": "error", "message": str(error)}

        sftp = None
        try:
            sftp = client.open_sftp()
            remote_dir = os.path.dirname(remote_path).replace("\\", "/")
            if remote_dir:
                self.run_command(
                    host=host,
                    username=username,
                    password=password,
                    command=f"mkdir -p {self.quote(remote_dir)}",
                    port=ssh_port or port,
                    timeout=timeout
                )
            sftp.put(local_path, remote_path)
            return {"status": "success", "ssh_port": ssh_port}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        finally:
            if sftp is not None:
                sftp.close()
            client.close()

    def download_file(
        self,
        host: str,
        username: Optional[str],
        password: Optional[str],
        remote_path: str,
        local_path: str,
        port: int = 22,
        timeout: int = 30
    ) -> dict:
        client, ssh_port, error = self._connect_client(host, username, password, port, timeout)
        if client is None:
            return {"status": "error", "message": str(error)}

        sftp = None
        try:
            sftp = client.open_sftp()
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            sftp.get(remote_path, local_path)
            return {"status": "success", "ssh_port": ssh_port}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        finally:
            if sftp is not None:
                sftp.close()
            client.close()

    def read_file(
        self,
        host: str,
        username: Optional[str],
        password: Optional[str],
        remote_path: str,
        port: int = 22,
        timeout: int = 30
    ) -> dict:
        client, ssh_port, error = self._connect_client(host, username, password, port, timeout)
        if client is None:
            return {"status": "error", "message": str(error)}

        sftp = None
        try:
            sftp = client.open_sftp()
            with sftp.file(remote_path, "r") as remote_file:
                content = remote_file.read().decode("utf-8", errors="ignore")
            return {"status": "success", "content": content, "ssh_port": ssh_port}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        finally:
            if sftp is not None:
                sftp.close()
            client.close()

    def write_file(
        self,
        host: str,
        username: Optional[str],
        password: Optional[str],
        remote_path: str,
        content: str,
        port: int = 22,
        timeout: int = 30
    ) -> dict:
        client, ssh_port, error = self._connect_client(host, username, password, port, timeout)
        if client is None:
            return {"status": "error", "message": str(error)}

        sftp = None
        try:
            sftp = client.open_sftp()
            remote_dir = os.path.dirname(remote_path).replace("\\", "/")
            if remote_dir:
                self.run_command(
                    host=host,
                    username=username,
                    password=password,
                    command=f"mkdir -p {self.quote(remote_dir)}",
                    port=ssh_port or port,
                    timeout=timeout
                )
            with sftp.file(remote_path, "w") as remote_file:
                remote_file.write(content)
            return {"status": "success", "ssh_port": ssh_port}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        finally:
            if sftp is not None:
                sftp.close()
            client.close()

    @staticmethod
    def quote(value: str) -> str:
        escaped = value.replace("'", "'\"'\"'")
        return f"'{escaped}'"
