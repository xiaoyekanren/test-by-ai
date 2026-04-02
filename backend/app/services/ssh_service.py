# backend/app/services/ssh_service.py
import paramiko
from dataclasses import dataclass
from typing import Optional
import logging

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
                stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
                out = stdout.read().decode('utf-8', errors='ignore')
                err = stderr.read().decode('utf-8', errors='ignore')
                exit_status = stdout.channel.recv_exit_status()
                client.close()
                return SSHResult(exit_status=exit_status, stdout=out, stderr=err, ssh_port=ssh_port)
            except Exception as e:
                last_exc = e
                continue

        return SSHResult(exit_status=-1, stdout="", stderr="", error=str(last_exc))

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
        ports_to_try = [22, port] if port != 22 else [22]
        last_exc = None

        for p in ports_to_try:
            try:
                transport = paramiko.Transport((host, p))
                transport.connect(username=username, password=password)
                sftp = paramiko.SFTPClient.from_transport(transport)
                sftp.put(local_path, remote_path)
                sftp.close()
                transport.close()
                return {"status": "success"}
            except Exception as e:
                last_exc = e
                try:
                    transport.close()
                except Exception:
                    pass
                continue

        return {"status": "error", "message": str(last_exc)}