# backend/tests/test_schemas.py
import sys
sys.path.insert(0, 'backend')
from app.schemas.server import ServerCreate, ServerResponse
from app.schemas.workflow import WorkflowCreate, WorkflowResponse
from app.schemas.execution import ExecutionCreate, ExecutionResponse

def test_server_create_schema():
    """Test ServerCreate validation"""
    data = {"name": "test", "host": "192.168.1.1"}
    server = ServerCreate(**data)
    assert server.name == "test"
    assert server.port == 22  # default

def test_server_create_requires_name_host():
    """Test ServerCreate requires name and host"""
    from pydantic import ValidationError
    try:
        ServerCreate(host="192.168.1.1")
        assert False, "Should raise ValidationError"
    except ValidationError as e:
        assert "name" in str(e)

def test_workflow_create_schema():
    """Test WorkflowCreate with nodes"""
    data = {
        "name": "test-workflow",
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls"}}],
        "edges": [{"from": "n1", "to": "n2"}]
    }
    wf = WorkflowCreate(**data)
    assert wf.name == "test-workflow"
    assert len(wf.nodes) == 1

def test_execution_create_schema():
    """Test ExecutionCreate"""
    data = {"workflow_id": 1, "trigger_type": "manual"}
    ex = ExecutionCreate(**data)
    assert ex.workflow_id == 1