# backend/app/api/servers.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Set
from ..dependencies import get_db
from ..models.database import Server, Execution, NodeExecution, Workflow
from ..schemas.server import ServerCreate, ServerUpdate, ServerResponse
from ..services.ssh_service import SSHService

router = APIRouter()


def _compute_busy_servers(db: Session) -> Set[int]:
    """计算当前正在使用中的服务器 ID 集合"""
    # Find all running executions
    running_executions = db.query(Execution.id).filter(
        Execution.status == "running"
    ).all()
    running_exec_ids = [e.id for e in running_executions]

    if not running_exec_ids:
        return set()

    # Find all running node_executions in these executions
    running_node_execs = db.query(NodeExecution).filter(
        NodeExecution.execution_id.in_(running_exec_ids),
        NodeExecution.status == "running"
    ).all()

    # Extract server_ids from input_data
    busy_server_ids = set()
    for ne in running_node_execs:
        if ne.input_data and isinstance(ne.input_data, dict):
            server_id = ne.input_data.get("server_id")
            if server_id is not None:
                busy_server_ids.add(int(server_id))

    return busy_server_ids


def _build_server_response(server: Server, is_busy: bool) -> ServerResponse:
    """根据 Server 模型和 is_busy 计算字段构建 ServerResponse"""
    server_dict = {
        "id": server.id,
        "name": server.name,
        "host": server.host,
        "port": server.port,
        "username": server.username,
        "description": server.description,
        "tags": server.tags,
        "status": server.status,
        "region": server.region or "私有云",
        "is_busy": is_busy,
        "created_at": server.created_at,
        "updated_at": server.updated_at
    }
    return ServerResponse.model_validate(server_dict)


def _matches_server_id(value: Any, server_id: int) -> bool:
    if value in (None, ""):
        return False
    try:
        return int(value) == server_id
    except (TypeError, ValueError):
        return False


def _node_config_references_server(config: Dict[str, Any], server_id: int) -> bool:
    if _matches_server_id(config.get("server_id"), server_id):
        return True

    for field in ("config_nodes", "data_nodes"):
        nodes = config.get(field)
        if not isinstance(nodes, list):
            continue
        for item in nodes:
            if (
                isinstance(item, dict)
                and _matches_server_id(item.get("server_id"), server_id)
            ):
                return True

    return False


def _workflows_referencing_server(db: Session, server_id: int) -> List[Workflow]:
    workflows = db.query(Workflow).all()
    referenced: List[Workflow] = []
    for workflow in workflows:
        for node in workflow.nodes or []:
            if not isinstance(node, dict):
                continue
            config = node.get("config") or {}
            if isinstance(config, dict) and _node_config_references_server(config, server_id):
                referenced.append(workflow)
                break
    return referenced


@router.get("", response_model=List[ServerResponse])
def list_servers(db: Session = Depends(get_db)):
    """列出所有服务器，包含 is_busy 计算字段"""
    servers = db.query(Server).all()
    busy_server_ids = _compute_busy_servers(db)

    # Convert to response with is_busy
    responses = []
    for server in servers:
        responses.append(_build_server_response(server, server.id in busy_server_ids))

    return responses


@router.post("", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(server: ServerCreate, db: Session = Depends(get_db)):
    """创建新服务器"""
    # Check if server with same name already exists
    existing = db.query(Server).filter(Server.name == server.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"服务器名称 '{server.name}' 已存在"
        )

    # Create server instance
    db_server = Server(
        name=server.name,
        host=server.host,
        port=server.port,
        username=server.username,
        password=server.password.get_secret_value() if server.password else None,
        description=server.description,
        tags=server.tags,
        region=server.region
    )

    db.add(db_server)
    db.commit()
    db.refresh(db_server)

    # Freshly created server is not busy
    return _build_server_response(db_server, is_busy=False)


@router.get("/{server_id}", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db)):
    """根据 ID 获取服务器"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"服务器 ID {server_id} 不存在"
        )
    busy_server_ids = _compute_busy_servers(db)
    return _build_server_response(server, server.id in busy_server_ids)


@router.put("/{server_id}", response_model=ServerResponse)
def update_server(server_id: int, server_update: ServerUpdate, db: Session = Depends(get_db)):
    """更新服务器"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"服务器 ID {server_id} 不存在"
        )

    # Check for name uniqueness if name is being updated
    if server_update.name and server_update.name != server.name:
        existing = db.query(Server).filter(Server.name == server_update.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"服务器名称 '{server_update.name}' 已存在"
            )

    # Update fields
    update_data = server_update.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"] is not None:
        update_data["password"] = update_data["password"].get_secret_value()

    for field, value in update_data.items():
        setattr(server, field, value)

    db.commit()
    db.refresh(server)

    # Check if server is busy after update
    busy_server_ids = _compute_busy_servers(db)
    return _build_server_response(server, server.id in busy_server_ids)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: int, db: Session = Depends(get_db)):
    """删除服务器"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"服务器 ID {server_id} 不存在"
        )

    referencing_workflows = _workflows_referencing_server(db, server_id)
    if referencing_workflows:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "该服务器正被现有工作流使用",
                "workflows": [
                    {"id": workflow.id, "name": workflow.name}
                    for workflow in referencing_workflows
                ]
            }
        )

    db.delete(server)
    db.commit()

    return None


@router.post("/{server_id}/test")
def test_connection(server_id: int, db: Session = Depends(get_db)):
    """测试服务器的 SSH 连接"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"服务器 ID {server_id} 不存在"
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
        server.status = "offline"
        db.commit()
        return {
            "success": False,
            "message": f"连接失败: {result.error}",
            "server_id": server_id,
            "server_name": server.name
        }

    # Update server status to online
    server.status = "online"
    db.commit()

    return {
        "success": True,
        "message": "连接成功",
        "server_id": server_id,
        "server_name": server.name,
        "ssh_port": result.ssh_port
    }


@router.post("/{server_id}/execute")
def execute_command(server_id: int, command_data: dict, db: Session = Depends(get_db)):
    """通过 SSH 在服务器上执行命令"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"服务器 ID {server_id} 不存在"
        )

    command = command_data.get("command")
    if not command:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="命令不能为空"
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
