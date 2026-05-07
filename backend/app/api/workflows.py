# backend/app/api/workflows.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..dependencies import get_db
from ..models.database import Execution, NodeExecution, Workflow
from ..schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse

router = APIRouter()

TOP_LEVEL_SERVER_NODE_TYPES = {
    "shell", "upload", "download", "config", "iotdb_config",
    "log_view", "iotdb_deploy", "iotdb_start", "iotdb_cli",
    "iotdb_stop", "iot_benchmark_deploy", "iot_benchmark_start", "iot_benchmark_wait"
}

CLUSTER_SERVER_NODE_TYPES = {
    "iotdb_cluster_deploy",
    "iotdb_cluster_start",
    "iotdb_cluster_check",
    "iotdb_cluster_stop",
}


def _has_value(value) -> bool:
    return value not in (None, "", [])


def _validate_workflow_schedule(schedule_mode: str, schedule_region: str, nodes: List[dict]) -> None:
    if schedule_mode == "random" and not _has_value(schedule_region):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="随机调度模式必须选择调度区域"
        )

    for node in nodes:
        node_type = node.get("type")
        config = node.get("config") or {}
        node_id = node.get("id") or node_type

        if node_type in TOP_LEVEL_SERVER_NODE_TYPES:
            has_server_id = _has_value(config.get("server_id"))
            if schedule_mode == "fixed" and not has_server_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"固定主机模式下节点 {node_id} 必须选择服务器"
                )
            if schedule_mode == "random" and has_server_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"随机调度模式下节点 {node_id} 不能选择固定服务器"
                )

        if node_type in CLUSTER_SERVER_NODE_TYPES:
            for field in ("config_nodes", "data_nodes"):
                cluster_nodes = config.get(field) or []
                if not isinstance(cluster_nodes, list):
                    continue
                for index, item in enumerate(cluster_nodes):
                    if not isinstance(item, dict):
                        continue
                    has_server_id = _has_value(item.get("server_id"))
                    if schedule_mode == "fixed" and not has_server_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"固定主机模式下节点 {node_id} 的 {field}[{index}] 必须选择服务器"
                        )
                    if schedule_mode == "random" and has_server_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"随机调度模式下节点 {node_id} 的 {field}[{index}] 不能选择固定服务器"
                        )


@router.get("", response_model=List[WorkflowResponse])
def list_workflows(db: Session = Depends(get_db)):
    """列出所有工作流"""
    workflows = db.query(Workflow).all()
    return workflows


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    """创建新工作流"""
    # Check if workflow with same name already exists
    existing = db.query(Workflow).filter(Workflow.name == workflow.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"工作流名称 '{workflow.name}' 已存在"
        )

    db_workflow = Workflow(
        name=workflow.name,
        description=workflow.description,
        nodes=[node.model_dump(by_alias=True) for node in workflow.nodes],
        edges=[edge.model_dump(by_alias=True) for edge in workflow.edges],
        variables=workflow.variables,
        schedule_mode=workflow.schedule_mode,
        schedule_region=workflow.schedule_region,
    )
    _validate_workflow_schedule(db_workflow.schedule_mode, db_workflow.schedule_region, db_workflow.nodes)
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """根据 ID 获取工作流"""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工作流 ID {workflow_id} 不存在"
        )
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(workflow_id: int, workflow_update: WorkflowUpdate, db: Session = Depends(get_db)):
    """更新工作流"""
    db_workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工作流 ID {workflow_id} 不存在"
        )

    update_data = workflow_update.model_dump(exclude_unset=True, by_alias=True)
    next_schedule_mode = update_data.get("schedule_mode", db_workflow.schedule_mode)
    next_schedule_region = update_data.get("schedule_region", db_workflow.schedule_region)
    next_nodes = update_data.get("nodes", db_workflow.nodes or [])
    _validate_workflow_schedule(next_schedule_mode, next_schedule_region, next_nodes)

    for key, value in update_data.items():
        setattr(db_workflow, key, value)

    db.commit()
    db.refresh(db_workflow)
    return db_workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """删除工作流"""
    db_workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工作流 ID {workflow_id} 不存在"
        )

    execution_ids = [
        row[0]
        for row in db.query(Execution.id)
        .filter(Execution.workflow_id == workflow_id)
        .all()
    ]
    if execution_ids:
        db.query(NodeExecution).filter(
            NodeExecution.execution_id.in_(execution_ids)
        ).delete(synchronize_session=False)
        db.query(Execution).filter(
            Execution.id.in_(execution_ids)
        ).delete(synchronize_session=False)

    db.delete(db_workflow)
    db.commit()
    return None
