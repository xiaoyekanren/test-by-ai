# backend/app/api/monitoring.py
"""
API endpoints for system monitoring.
Provides both local and remote monitoring capabilities.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from ..dependencies import get_db
from ..models.database import Server
from ..services.monitoring_service import MonitoringService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/local/status")
def get_local_status():
    """Get local server status (CPU, memory, disk).

    Returns:
        Dict containing cpu_percent, memory info, and disk info.
    """
    logger.info("API call: GET /api/monitoring/local/status")

    service = MonitoringService()
    status = service.get_status()

    logger.debug(f"Returning local status: CPU={status['cpu_percent']}%")
    return status


@router.get("/local/processes")
def get_local_processes(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of processes to return"),
    sort_by: str = Query("cpu", pattern="^(cpu|memory)$", description="Sort by 'cpu' or 'memory'")
):
    """Get list of local processes sorted by CPU or memory usage.

    Args:
        limit: Maximum number of processes to return (1-500, default 50).
        sort_by: Sort field - 'cpu' or 'memory' (default 'cpu').

    Returns:
        List of process dictionaries with pid, name, cpu_percent, memory_percent.
    """
    logger.info(f"API call: GET /api/monitoring/local/processes (limit={limit}, sort_by={sort_by})")

    service = MonitoringService()
    processes = service.get_processes(limit=limit, sort_by=sort_by)

    logger.debug(f"Returning {len(processes)} processes")
    return processes


@router.post("/local/process/{pid}/kill")
def kill_local_process(pid: int):
    """Kill a local process by PID.

    Args:
        pid: Process ID to kill.

    Returns:
        Dict with success status and pid or error message.
    """
    logger.info(f"API call: POST /api/monitoring/local/process/{pid}/kill")

    service = MonitoringService()
    result = service.kill_process(pid)

    if result["success"]:
        logger.info(f"Successfully killed process {pid}")
    else:
        logger.warning(f"Failed to kill process {pid}: {result.get('error', 'Unknown error')}")

    return result


@router.get("/remote/{server_id}/status")
def get_remote_status(
    server_id: int,
    db: Session = Depends(get_db)
):
    """Get remote server status via SSH.

    Args:
        server_id: ID of the server to monitor.

    Returns:
        Dict containing server info and system status (CPU, memory, disk).
    """
    logger.info(f"API call: GET /api/monitoring/remote/{server_id}/status")

    # Get server from database
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        logger.warning(f"Server with ID {server_id} not found")
        raise HTTPException(
            status_code=404,
            detail=f"Server with id {server_id} not found"
        )

    logger.info(f"Getting remote status for server: {server.name} ({server.host})")

    service = MonitoringService()
    status = service.get_remote_status(
        host=server.host,
        username=server.username,
        password=server.password,
        port=server.port,
        server_id=server.id,
        server_name=server.name
    )

    logger.debug(f"Returning remote status for server {server.name}")
    return status


@router.get("/remote/{server_id}/processes")
def get_remote_processes(
    server_id: int,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of processes to return"),
    sort_by: str = Query("cpu", pattern="^(cpu|memory)$", description="Sort by 'cpu' or 'memory'"),
    db: Session = Depends(get_db)
):
    """Get list of processes from remote server via SSH.

    Args:
        server_id: ID of the server to monitor.
        limit: Maximum number of processes to return (1-500, default 50).
        sort_by: Sort field - 'cpu' or 'memory' (default 'cpu').

    Returns:
        Dict containing server info and list of processes.
    """
    logger.info(f"API call: GET /api/monitoring/remote/{server_id}/processes (limit={limit}, sort_by={sort_by})")

    # Get server from database
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        logger.warning(f"Server with ID {server_id} not found")
        raise HTTPException(
            status_code=404,
            detail=f"Server with id {server_id} not found"
        )

    logger.info(f"Getting remote processes for server: {server.name} ({server.host})")

    service = MonitoringService()
    result = service.get_remote_processes(
        host=server.host,
        username=server.username,
        password=server.password,
        port=server.port,
        limit=limit,
        sort_by=sort_by,
        server_id=server.id,
        server_name=server.name
    )

    logger.debug(f"Returning {len(result['processes'])} processes for server {server.name}")
    return result