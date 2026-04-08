# backend/app/api/executions.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.dependencies import get_db
from app.schemas.execution import (
    ExecutionCreate,
    ExecutionResponse,
    ExecutionUpdate,
    NodeExecutionResponse
)
from app.services.execution_engine import ExecutionEngine
from app.models.database import Execution, NodeExecution

router = APIRouter()


@router.get("", response_model=List[ExecutionResponse])
def list_executions(
    workflow_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all executions with optional filters"""
    engine = ExecutionEngine(db)
    executions = engine.list_executions(workflow_id=workflow_id, status=status, limit=limit)
    return executions


@router.post("", response_model=ExecutionResponse, status_code=201)
def create_execution(
    execution_data: ExecutionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create and start a new execution"""
    # Check if workflow exists
    from app.models.database import Workflow
    workflow = db.query(Workflow).filter(Workflow.id == execution_data.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    engine = ExecutionEngine(db)
    execution = engine.create_execution(
        workflow_id=execution_data.workflow_id,
        trigger_type=execution_data.trigger_type,
        triggered_by=execution_data.triggered_by
    )

    # Start execution in background
    background_tasks.add_task(engine.execute_workflow, execution.id)

    return execution


@router.get("/{execution_id}", response_model=ExecutionResponse)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    """Get execution by ID"""
    engine = ExecutionEngine(db)
    execution = engine.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.post("/{execution_id}/stop", response_model=ExecutionResponse)
def stop_execution(execution_id: int, db: Session = Depends(get_db)):
    """Stop a running execution"""
    engine = ExecutionEngine(db)
    execution = engine.stop_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_execution(execution_id: int, db: Session = Depends(get_db)):
    """Delete an execution and its node records"""
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    db.query(NodeExecution).filter(
        NodeExecution.execution_id == execution_id
    ).delete(synchronize_session=False)
    db.delete(execution)
    db.commit()
    return None


@router.get("/{execution_id}/nodes", response_model=List[NodeExecutionResponse])
def get_node_executions(execution_id: int, db: Session = Depends(get_db)):
    """Get all node executions for an execution"""
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    node_executions = db.query(NodeExecution).filter(
        NodeExecution.execution_id == execution_id
    ).all()
    return node_executions
