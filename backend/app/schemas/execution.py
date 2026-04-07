# backend/app/schemas/execution.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, Literal
from datetime import datetime

# Status literals for execution
EXECUTION_STATUS = Literal["pending", "running", "paused", "completed", "failed"]
TRIGGER_TYPE = Literal["manual", "scheduled", "api"]
EXECUTION_RESULT = Literal["passed", "failed", "partial"]

class ExecutionCreate(BaseModel):
    workflow_id: int
    trigger_type: TRIGGER_TYPE = Field(default="manual")
    triggered_by: Optional[str] = None

class ExecutionUpdate(BaseModel):
    status: Optional[EXECUTION_STATUS] = None

class ExecutionResponse(BaseModel):
    id: int
    workflow_id: int
    status: EXECUTION_STATUS
    trigger_type: TRIGGER_TYPE
    triggered_by: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration: Optional[int]
    result: Optional[EXECUTION_RESULT]
    summary: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NodeExecutionResponse(BaseModel):
    id: int
    execution_id: int
    node_id: str
    node_type: str
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration: Optional[int]
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    log_path: Optional[str]
    error_message: Optional[str]
    retry_count: int

    model_config = ConfigDict(from_attributes=True)