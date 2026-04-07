# backend/app/api/servers.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..dependencies import get_db
from ..models.database import Server
from ..schemas.server import ServerCreate, ServerUpdate, ServerResponse
from ..services.ssh_service import SSHService

router = APIRouter()


@router.get("", response_model=List[ServerResponse])
def list_servers(db: Session = Depends(get_db)):
    """List all servers"""
    servers = db.query(Server).all()
    return servers


@router.post("", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(server: ServerCreate, db: Session = Depends(get_db)):
    """Create a new server"""
    # Check if server with same name already exists
    existing = db.query(Server).filter(Server.name == server.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Server with name '{server.name}' already exists"
        )

    # Create server instance
    db_server = Server(
        name=server.name,
        host=server.host,
        port=server.port,
        username=server.username,
        password=server.password.get_secret_value() if server.password else None,
        description=server.description,
        tags=server.tags
    )

    db.add(db_server)
    db.commit()
    db.refresh(db_server)

    return db_server


@router.get("/{server_id}", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db)):
    """Get a server by ID"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server with id {server_id} not found"
        )
    return server


@router.put("/{server_id}", response_model=ServerResponse)
def update_server(server_id: int, server_update: ServerUpdate, db: Session = Depends(get_db)):
    """Update a server"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server with id {server_id} not found"
        )

    # Check for name uniqueness if name is being updated
    if server_update.name and server_update.name != server.name:
        existing = db.query(Server).filter(Server.name == server_update.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server with name '{server_update.name}' already exists"
            )

    # Update fields
    update_data = server_update.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"] is not None:
        update_data["password"] = update_data["password"].get_secret_value()

    for field, value in update_data.items():
        setattr(server, field, value)

    db.commit()
    db.refresh(server)

    return server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: int, db: Session = Depends(get_db)):
    """Delete a server"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server with id {server_id} not found"
        )

    db.delete(server)
    db.commit()

    return None


@router.post("/{server_id}/test")
def test_connection(server_id: int, db: Session = Depends(get_db)):
    """Test SSH connection to a server"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server with id {server_id} not found"
        )

    ssh_service = SSHService()
    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command="echo 'Connection test successful'",
        port=server.port,
        timeout=10
    )

    if result.error:
        return {
            "success": False,
            "message": f"Connection failed: {result.error}",
            "server_id": server_id,
            "server_name": server.name
        }

    # Update server status to online
    server.status = "online"
    db.commit()

    return {
        "success": True,
        "message": "Connection successful",
        "server_id": server_id,
        "server_name": server.name,
        "ssh_port": result.ssh_port
    }


@router.post("/{server_id}/execute")
def execute_command(server_id: int, command_data: dict, db: Session = Depends(get_db)):
    """Execute a command on a server via SSH"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server with id {server_id} not found"
        )

    command = command_data.get("command")
    if not command:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Command is required"
        )

    timeout = command_data.get("timeout", 30)

    ssh_service = SSHService()
    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=timeout
    )

    return {
        "server_id": server_id,
        "server_name": server.name,
        "command": command,
        "exit_status": result.exit_status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "error": result.error,
        "ssh_port": result.ssh_port
    }
