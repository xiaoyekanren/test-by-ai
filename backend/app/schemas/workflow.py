# backend/app/schemas/workflow.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

# Node type literal for validation
NODE_TYPE = Literal[
    "shell", "upload", "download", "config", "log_view", "iotdb_deploy", "iotdb_start",
    "iotdb_stop", "iotdb_cli", "iotdb_config", "iotdb_cluster_deploy", "iotdb_cluster_start",
    "iotdb_cluster_check", "iotdb_cluster_stop", "iot_benchmark_start", "iot_benchmark_wait",
    "condition", "loop", "wait", "parallel", "assert", "report", "summary", "notify"
]
SCHEDULE_MODE = Literal["fixed", "random"]

class NodeDefinition(BaseModel):
    id: str
    type: NODE_TYPE
    config: Dict[str, Any] = {}
    position: Optional[Dict[str, float]] = None

class EdgeDefinition(BaseModel):
    from_node: str = Field(..., alias="from")
    to: str
    label: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    nodes: List[NodeDefinition] = []
    edges: List[EdgeDefinition] = []
    variables: Dict[str, str] = {}
    schedule_mode: SCHEDULE_MODE = "fixed"
    schedule_region: str = "私有云"

class WorkflowCreate(WorkflowBase):
    pass

class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    nodes: Optional[List[NodeDefinition]] = None
    edges: Optional[List[EdgeDefinition]] = None
    variables: Optional[Dict[str, str]] = None
    schedule_mode: Optional[SCHEDULE_MODE] = None
    schedule_region: Optional[str] = None

class WorkflowResponse(WorkflowBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
