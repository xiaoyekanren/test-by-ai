# backend/tests/test_models.py
import sys
from datetime import UTC

sys.path.insert(0, 'backend')
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, Server, Workflow, Execution, NodeExecution
from app.utils.time import utc_now

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
    assert server.schedulable is True

def test_workflow_model():
    """Test Workflow model with nodes JSON"""
    workflow = Workflow(
        name="test-workflow",
        nodes=[{"id": "node1", "type": "shell"}],
        edges=[{"from": "node1", "to": "node2"}]
    )
    assert workflow.name == "test-workflow"
    assert len(workflow.nodes) == 1
    assert workflow.schedule_mode == "fixed"
    assert workflow.schedule_region == "私有云"

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


def test_timestamp_columns_round_trip_as_aware_utc():
    """Persisted timestamps should keep UTC timezone information."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    workflow = Workflow(name="tz-workflow")
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    execution = Execution(
        workflow_id=workflow.id,
        status="running",
        trigger_type="manual",
        started_at=utc_now()
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    assert execution.created_at is not None
    assert execution.created_at.tzinfo == UTC
    assert execution.started_at is not None
    assert execution.started_at.tzinfo == UTC

    raw_started_at = db.execute(text("SELECT started_at FROM executions WHERE id = :id"), {"id": execution.id}).scalar_one()
    raw_created_at = db.execute(text("SELECT created_at FROM executions WHERE id = :id"), {"id": execution.id}).scalar_one()
    assert raw_started_at.endswith("+00:00")
    assert raw_created_at.endswith("+00:00")
