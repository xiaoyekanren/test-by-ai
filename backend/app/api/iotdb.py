# backend/app/api/iotdb.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from ..dependencies import get_db
from ..models.database import Server
from ..services.ssh_service import SSHService
import os

router = APIRouter()


class CLIRequest(BaseModel):
    server_id: int
    iotdb_home: str
    sql: str
    timeout: Optional[int] = 60


class LogsListRequest(BaseModel):
    server_id: int
    iotdb_home: str


class LogReadRequest(BaseModel):
    server_id: int
    path: str
    tail: Optional[int] = None


class ConfigsListRequest(BaseModel):
    server_id: int
    iotdb_home: str


class ConfigReadRequest(BaseModel):
    server_id: int
    path: str


class ConfigWriteRequest(BaseModel):
    server_id: int
    path: str
    content: str


class RestartRequest(BaseModel):
    server_id: int
    iotdb_home: str


class FileInfo(BaseModel):
    name: str
    path: str
    size: int
    modified: str


class CLIResult(BaseModel):
    server_id: int
    server_name: str
    iotdb_home: str
    command: str
    exit_status: int
    stdout: str
    stderr: str
    error: Optional[str] = None


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


@router.post("/cli", response_model=CLIResult)
def execute_cli(request: CLIRequest, db: Session = Depends(get_db)):
    """Execute IoTDB CLI SQL command."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()

    # Build CLI command
    cli_script = os.path.join(request.iotdb_home, "sbin", "start-cli.sh")
    # Escape SQL for shell
    escaped_sql = request.sql.replace("'", "'\"'\"'")
    command = f"{cli_script} -e '{escaped_sql}'"

    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=request.timeout
    )

    return CLIResult(
        server_id=request.server_id,
        server_name=server.name,
        iotdb_home=request.iotdb_home,
        command=request.sql,
        exit_status=result.exit_status,
        stdout=result.stdout,
        stderr=result.stderr,
        error=result.error
    )


@router.post("/logs/list", response_model=List[FileInfo])
def list_logs(request: LogsListRequest, db: Session = Depends(get_db)):
    """List log files in logs directory."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()

    logs_dir = os.path.join(request.iotdb_home, "logs")
    # List .log files with details
    command = f"find '{logs_dir}' -maxdepth 1 -name '*.log' -printf '%f\\n%p\\n%s\\n%T+\\n' | paste - - - -"

    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=30
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list logs: {result.error}"
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
    """Read log file content."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()

    if request.tail:
        command = f"tail -n {request.tail} '{request.path}'"
    else:
        command = f"cat '{request.path}'"

    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=60
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read log: {result.error}"
        )

    # Get file size
    size_result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=f"stat -c %s '{request.path}'",
        port=server.port,
        timeout=10
    )
    size = int(size_result.stdout.strip()) if size_result.stdout.strip() else 0

    return LogContent(
        server_id=request.server_id,
        server_name=server.name,
        path=request.path,
        content=result.stdout,
        size=size
    )


@router.post("/configs/list", response_model=List[FileInfo])
def list_configs(request: ConfigsListRequest, db: Session = Depends(get_db)):
    """List config files in conf directory."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()

    conf_dir = os.path.join(request.iotdb_home, "conf")
    # List all files in conf directory
    command = f"find '{conf_dir}' -maxdepth 1 -type f -printf '%f\\n%p\\n%s\\n%T+\\n' | paste - - - -"

    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=30
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list configs: {result.error}"
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

    result = ssh_service.read_file(
        host=server.host,
        username=server.username,
        password=server.password,
        remote_path=request.path,
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
        path=request.path,
        content=result["content"]
    )


@router.post("/configs/write")
def write_config(request: ConfigWriteRequest, db: Session = Depends(get_db)):
    """Write config file content."""
    server = get_server(db, request.server_id)
    ssh_service = SSHService()

    result = ssh_service.write_file(
        host=server.host,
        username=server.username,
        password=server.password,
        remote_path=request.path,
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

    stop_script = os.path.join(request.iotdb_home, "sbin", "stop-standalone.sh")
    start_script = os.path.join(request.iotdb_home, "sbin", "start-standalone.sh")

    # Stop first
    stop_result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=f"bash {stop_script}",
        port=server.port,
        timeout=60
    )

    # Then start
    start_result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=f"bash {start_script}",
        port=server.port,
        timeout=60
    )

    success = start_result.exit_status == 0 and not start_result.error
    message = "IoTDB restarted successfully" if success else "Failed to restart IoTDB"

    return RestartResult(
        server_id=request.server_id,
        server_name=server.name,
        iotdb_home=request.iotdb_home,
        success=success,
        message=message,
        stdout=start_result.stdout,
        stderr=start_result.stderr
    )