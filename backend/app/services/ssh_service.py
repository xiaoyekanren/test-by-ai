# backend/app/services/ssh_service.py
import os
from dataclasses import dataclass
from typing import Optional
import logging

import paramiko

logger = logging.getLogger(__name__)


@dataclass
class SSHResult:
    """SSH 命令执行结果。"""
    exit_status: int
    stdout: str
    stderr: str
    error: Optional[str] = None
    ssh_port: Optional[int] = None


class SSHService:
    """SSH 服务，用于远程命令执行和文件传输"""

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
        """通过 SSH 在远程服务器上执行命令

        Args:
            host: 远程服务器的主机名或 IP 地址
            username: SSH 用户名（可选）
            password: SSH 密码（可选）
            command: 要执行的命令
            port: SSH 端口（默认 22，同时会尝试此端口作为备选）
            timeout: 连接超时时间（秒）

        Returns:
            SSHResult，包含 exit_status、stdout、stderr 和可选的 error
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
        """通过 SFTP 上传文件到远程服务器

        Args:
            host: 远程服务器的主机名或 IP 地址
            username: SSH 用户名（可选）
            password: SSH 密码（可选）
            local_path: 本地文件路径
            remote_path: 远程服务器上的目标路径
            port: SSH 端口（默认 22，同时会尝试此端口作为备选）
            timeout: 连接超时时间（秒）

        Returns:
            包含 'status' 键（'success' 或 'error'）和可选 'message' 的字典
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
