# backend/app/api/iotdb.py
import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ValidationError
from ..dependencies import get_db
from ..models.database import Server
from ..services.ssh_service import SSHService
import posixpath
import time

router = APIRouter()
MAX_LOG_READ_BYTES = 256 * 1024
DEFAULT_LOG_TAIL_LINES = 100
MAX_LOG_TAIL_LINES = 1000
DEFAULT_CLI_HOST = "127.0.0.1"
DEFAULT_CLI_RPC_PORT = 6667


class CLISessionRequest(BaseModel):
    server_id: int
    iotdb_home: str
    host: Optional[str] = None
    rpc_port: Optional[int] = None
    username: Optional[str] = None
    cli_password: Optional[str] = None
    sql_dialect: Optional[str] = "tree"


class LogsListRequest(BaseModel):
    server_id: int
    iotdb_home: str


class LogReadRequest(BaseModel):
    server_id: int
    iotdb_home: str
    path: str
    tail: Optional[int] = DEFAULT_LOG_TAIL_LINES


class LogStreamRequest(BaseModel):
    server_id: int
    iotdb_home: str
    path: str
    tail: Optional[int] = DEFAULT_LOG_TAIL_LINES


class ConfigsListRequest(BaseModel):
    server_id: int
    iotdb_home: str


class ConfigReadRequest(BaseModel):
    server_id: int
    iotdb_home: str
    path: str


class ConfigWriteRequest(BaseModel):
    server_id: int
    iotdb_home: str
    path: str
    content: str


class RestartRequest(BaseModel):
    server_id: int
    iotdb_home: str
    restart_scope: str = "all"


class FileInfo(BaseModel):
    name: str
    path: str
    size: int
    modified: str


class LogContent(BaseModel):
    server_id: int
    server_name: str
    path: str
    content: str
    size: int


class ConfigContent(BaseModel):
    server_id: int
    server_name: str
    path: str
    content: str


class RestartResult(BaseModel):
    server_id: int
    server_name: str
    iotdb_home: str
    success: bool
    message: str
    stdout: str
    stderr: str


def get_server(db: Session, server_id: int) -> Server:
    """Get server by ID, raise 404 if not found."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server with id {server_id} not found"
        )
    return server


def normalize_remote_path(path: str) -> str:
    """Normalize a remote Linux path before using it in shell commands."""
    if "\x00" in path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    normalized = posixpath.normpath(path)
    if not normalized.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path must be absolute")
    return normalized


def child_path_under(path: str, parent: str) -> str:
    normalized_path = normalize_remote_path(path)
    normalized_parent = normalize_remote_path(parent)
    if normalized_path != normalized_parent and not normalized_path.startswith(f"{normalized_parent}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path must be under {normalized_parent}"
        )
    return normalized_path


def clamp_tail_lines(tail: Optional[int]) -> int:
    if tail is None:
        return DEFAULT_LOG_TAIL_LINES
    if tail < 1:
        return DEFAULT_LOG_TAIL_LINES
    return min(tail, MAX_LOG_TAIL_LINES)


def command_error(result, fallback: str) -> Optional[str]:
    if result.error:
        return result.error
    if result.exit_status != 0:
        return result.stderr or fallback
    return None


def logs_dir(iotdb_home: str) -> str:
    return normalize_remote_path(posixpath.join(iotdb_home, "logs"))


def conf_dir(iotdb_home: str) -> str:
    return normalize_remote_path(posixpath.join(iotdb_home, "conf"))


def build_cli_command(
    ssh_service: SSHService,
    iotdb_home: str,
    host: Optional[str] = None,
    rpc_port: Optional[int] = None,
    username: Optional[str] = None,
    cli_password: Optional[str] = None,
    sql_dialect: Optional[str] = "tree"
) -> str:
    cli_script = posixpath.join(normalize_remote_path(iotdb_home), "sbin", "start-cli.sh")
    normalized_sql_dialect = "table" if sql_dialect == "table" else "tree"
    command_parts = [ssh_service.quote(cli_script)]
    command_parts.extend(["-h", ssh_service.quote(host or DEFAULT_CLI_HOST)])
    command_parts.extend(["-p", str(rpc_port or DEFAULT_CLI_RPC_PORT)])
    if username:
        command_parts.extend(["-u", ssh_service.quote(username)])
    if cli_password:
        command_parts.extend(["-pw", ssh_service.quote(cli_password)])
    command_parts.extend(["-sql_dialect", ssh_service.quote(normalized_sql_dialect)])
    return " ".join(command_parts)


@router.websocket("/cli/session")
async def cli_session(websocket: WebSocket, db: Session = Depends(get_db)):
    """Run an interactive IoTDB CLI session over WebSocket."""
    await websocket.accept()

    ssh_service = SSHService()
    client = None
    channel = None

    try:
        try:
            session_request = CLISessionRequest(**await websocket.receive_json())
            server = get_server(db, session_request.server_id)
            command = build_cli_command(
                ssh_service=ssh_service,
                iotdb_home=session_request.iotdb_home,
                host=session_request.host,
                rpc_port=session_request.rpc_port,
                username=session_request.username,
                cli_password=session_request.cli_password,
                sql_dialect=session_request.sql_dialect
            )
        except (ValidationError, HTTPException) as exc:
            detail = getattr(exc, "detail", str(exc))
            await websocket.send_json({"type": "error", "message": detail})
            await websocket.close(code=1008)
            return

        client, _ssh_port, connect_error = ssh_service._connect_client(
            host=server.host,
            username=server.username,
            password=server.password,
            port=server.port,
            timeout=10
        )
        if client is None:
            await websocket.send_json({"type": "error", "message": f"Failed to connect: {connect_error}"})
            await websocket.close(code=1011)
            return

        transport = client.get_transport()
        if transport is None:
            await websocket.send_json({"type": "error", "message": "SSH transport is not available"})
            await websocket.close(code=1011)
            return

        channel = transport.open_session()
        channel.get_pty(term="xterm", width=200, height=50)
        channel.exec_command(command)
        await websocket.send_json({"type": "ready"})

        async def pump_channel_to_websocket():
            while True:
                if channel.recv_ready():
                    output = channel.recv(4096).decode("utf-8", errors="ignore")
                    await websocket.send_json({"type": "output", "data": output})
                    continue
                if channel.exit_status_ready():
                    await websocket.send_json({"type": "exit"})
                    break
                await asyncio.sleep(0.05)

        async def pump_websocket_to_channel():
            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")
                if message_type == "disconnect":
                    break
                if message_type == "input":
                    data = str(message.get("data", ""))
                    if data:
                        channel.send(data)
                    continue
                if message_type == "resize":
                    try:
                        cols = int(message.get("cols", 0))
                        rows = int(message.get("rows", 0))
                        if cols > 0 and rows > 0:
                            channel.resize_pty(width=cols, height=rows)
                    except (TypeError, ValueError):
                        pass
                    continue
                if message_type == "command":
                    sql = str(message.get("sql", ""))
                    if sql:
                        channel.send(sql if sql.endswith("\n") else f"{sql}\n")
                    continue

        tasks = [
            asyncio.create_task(pump_channel_to_websocket()),
            asyncio.create_task(pump_websocket_to_channel())
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        if channel is not None:
            try:
                channel.send("exit\n")
            except Exception:
                pass
            channel.close()
        if client is not None:
            client.close()


@router.post("/logs/list", response_model=List[FileInfo])
def list_logs(request: LogsListRequest, db: Session = Depends(get_db)):
    """List log files in logs directory."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()

    target_logs_dir = logs_dir(request.iotdb_home)
    command = f"find {ssh_service.quote(target_logs_dir)} -maxdepth 1 -name '*.log' -printf '%f\\n%p\\n%s\\n%T+\\n' | paste - - - -"

    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=30
    )

    error = command_error(result, "Failed to list logs")
    if error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list logs: {error}"
        )

    files = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) == 4:
            files.append(FileInfo(
                name=parts[0],
                path=parts[1],
                size=int(parts[2]) if parts[2] else 0,
                modified=parts[3] or ""
            ))

    # Sort by modification time descending
    files.sort(key=lambda x: x.modified, reverse=True)
    return files


@router.post("/logs/read", response_model=LogContent)
def read_log(request: LogReadRequest, db: Session = Depends(get_db)):
    """Read the last lines of a log file with a size cap."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()
    target_path = child_path_under(request.path, logs_dir(request.iotdb_home))
    tail_lines = clamp_tail_lines(request.tail)

    command = (
        f"tail -n {tail_lines} {ssh_service.quote(target_path)} "
        f"| tail -c {MAX_LOG_READ_BYTES}"
    )

    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=60
    )

    error = command_error(result, "Failed to read log")
    if error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read log: {error}"
        )

    # Get file size
    size_result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=f"stat -c %s {ssh_service.quote(target_path)}",
        port=server.port,
        timeout=10
    )
    size = int(size_result.stdout.strip()) if size_result.stdout.strip() else 0

    return LogContent(
        server_id=request.server_id,
        server_name=server.name,
        path=target_path,
        content=result.stdout,
        size=size
    )


@router.post("/logs/stream")
def stream_log(request: LogStreamRequest, db: Session = Depends(get_db)):
    """Stream the last lines of a log file and follow new content."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()
    target_path = child_path_under(request.path, logs_dir(request.iotdb_home))
    tail_lines = clamp_tail_lines(request.tail)
    command = f"tail -n {tail_lines} -F {ssh_service.quote(target_path)}"

    def generate():
        client = None
        try:
            client, _ssh_port, connect_error = ssh_service._connect_client(
                host=server.host,
                username=server.username,
                password=server.password,
                port=server.port,
                timeout=10
            )
            if client is None:
                yield f"Failed to connect: {connect_error}\n"
                return

            _stdin, stdout, stderr = client.exec_command(command)
            channel = stdout.channel
            while True:
                if channel.recv_ready():
                    yield channel.recv(4096).decode("utf-8", errors="ignore")
                    continue
                if channel.recv_stderr_ready():
                    yield stderr.channel.recv_stderr(4096).decode("utf-8", errors="ignore")
                    continue
                if channel.exit_status_ready():
                    break
                time.sleep(0.5)
        finally:
            if client is not None:
                client.close()

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.post("/configs/list", response_model=List[FileInfo])
def list_configs(request: ConfigsListRequest, db: Session = Depends(get_db)):
    """List config files in conf directory."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()

    target_conf_dir = conf_dir(request.iotdb_home)
    command = f"find {ssh_service.quote(target_conf_dir)} -maxdepth 1 -type f -printf '%f\\n%p\\n%s\\n%T+\\n' | paste - - - -"

    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=30
    )

    error = command_error(result, "Failed to list configs")
    if error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list configs: {error}"
        )

    files = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) == 4:
            files.append(FileInfo(
                name=parts[0],
                path=parts[1],
                size=int(parts[2]) if parts[2] else 0,
                modified=parts[3] or ""
            ))

    # Sort by name
    files.sort(key=lambda x: x.name)
    return files


@router.post("/configs/read", response_model=ConfigContent)
def read_config(request: ConfigReadRequest, db: Session = Depends(get_db)):
    """Read config file content."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()
    target_path = child_path_under(request.path, conf_dir(request.iotdb_home))

    result = ssh_service.read_file(
        host=server.host,
        username=server.username,
        password=server.password,
        remote_path=target_path,
        port=server.port,
        timeout=30
    )

    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read config: {result['message']}"
        )

    return ConfigContent(
        server_id=request.server_id,
        server_name=server.name,
        path=target_path,
        content=result["content"]
    )


@router.post("/configs/write")
def write_config(request: ConfigWriteRequest, db: Session = Depends(get_db)):
    """Write config file content."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()
    target_path = child_path_under(request.path, conf_dir(request.iotdb_home))

    result = ssh_service.write_file(
        host=server.host,
        username=server.username,
        password=server.password,
        remote_path=target_path,
        content=request.content,
        port=server.port,
        timeout=30
    )

    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write config: {result['message']}"
        )

    return {"success": True, "message": "Config saved successfully"}


@router.post("/restart", response_model=RestartResult)
def restart_iotdb(request: RestartRequest, db: Session = Depends(get_db)):
    """Restart IoTDB service."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()

    iotdb_home = normalize_remote_path(request.iotdb_home)
    script_by_scope = {
        "all": ("stop-standalone.sh", "start-standalone.sh"),
        "cn": ("stop-confignode.sh", "start-confignode.sh"),
        "dn": ("stop-datanode.sh", "start-datanode.sh"),
    }
    restart_scope = request.restart_scope.lower()
    if restart_scope not in script_by_scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="restart_scope must be one of: all, cn, dn"
        )

    stop_script_name, start_script_name = script_by_scope[restart_scope]
    stop_script = posixpath.join(iotdb_home, "sbin", stop_script_name)
    start_script = posixpath.join(iotdb_home, "sbin", start_script_name)

    # Stop first
    stop_result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=f"bash {ssh_service.quote(stop_script)}",
        port=server.port,
        timeout=60
    )

    # Then start
    start_result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=f"bash {ssh_service.quote(start_script)}",
        port=server.port,
        timeout=60
    )

    success = start_result.exit_status == 0 and not start_result.error
    message = f"IoTDB {restart_scope} restarted successfully" if success else f"Failed to restart IoTDB {restart_scope}"

    return RestartResult(
        server_id=request.server_id,
        server_name=server.name,
        iotdb_home=iotdb_home,
        success=success,
        message=message,
        stdout=start_result.stdout,
        stderr=start_result.stderr
    )
