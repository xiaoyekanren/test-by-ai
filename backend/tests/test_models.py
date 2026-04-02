# backend/tests/test_models.py
import sys
sys.path.insert(0, 'backend')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, Server, Workflow, Execution, NodeExecution

def test_server_model():
    """Test Server model can be instantiated"""
    server = Server(
        name="test-server",
        host="192.168.1.1",
        port=22,
        username="admin",
        password="secret"
    )
    assert server.name == "test-server"
    assert server.host == "192.168.1.1"

def test_workflow_model():
    """Test Workflow model with nodes JSON"""
    workflow = Workflow(
        name="test-workflow",
        nodes=[{"id": "node1", "type": "shell"}],
        edges=[{"from": "node1", "to": "node2"}]
    )
    assert workflow.name == "test-workflow"
    assert len(workflow.nodes) == 1

def test_execution_model():
    """Test Execution model"""
    execution = Execution(
        workflow_id=1,
        status="pending",
        trigger_type="manual"
    )
    assert execution.status == "pending"

def test_node_execution_model():
    """Test NodeExecution model"""
    ne = NodeExecution(
        execution_id=1,
        node_id="node1",
        node_type="shell",
        status="pending"
    )
    assert ne.node_id == "node1"