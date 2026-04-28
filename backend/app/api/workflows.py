# backend/app/api/workflows.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from ..dependencies import get_db
from ..models.database import Execution, NodeExecution, Workflow
from ..schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse

router = APIRouter()


@router.get("", response_model=List[WorkflowResponse])
def list_workflows(
    is_test_case: Optional[bool] = None,
    priority: Optional[str] = None,
    test_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Workflow)
    if is_test_case is True:
        query = query.filter(Workflow.priority.isnot(None))
    elif is_test_case is False:
        query = query.filter(Workflow.priority.is_(None))
    if priority:
        query = query.filter(Workflow.priority == priority)
    if test_type:
        query = query.filter(Workflow.test_type == test_type)
    return query.all()


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
        priority=workflow.priority,
        test_type=workflow.test_type,
        labels=workflow.labels,
        source=workflow.source,
    )
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
