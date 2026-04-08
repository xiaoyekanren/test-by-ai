# backend/tests/test_executions_api.py
import sys
sys.path.insert(0, 'backend')
import pytest
from app.models.database import NodeExecution

@pytest.fixture(autouse=True)
def setup_workflow(client):
    """Create a workflow for testing executions."""
    client.post("/api/workflows", json={"name": "test-wf", "nodes": [], "edges": []})

def test_create_execution(client):
    response = client.post("/api/executions", json={"workflow_id": 1})
    assert response.status_code == 201
    data = response.json()
    assert data["workflow_id"] == 1
    assert data["status"] == "pending"

def test_get_execution(client):
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.get("/api/executions/1")
    assert response.status_code == 200
    # Status could be pending, running, or completed since execution happens in background
    assert response.json()["status"] in ["pending", "running", "completed"]

def test_list_executions(client):
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.get("/api/executions")
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_stop_execution(client):
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.post("/api/executions/1/stop")
    assert response.status_code == 200

def test_delete_execution(client, db_session):
    create_response = client.post("/api/executions", json={"workflow_id": 1})
    execution_id = create_response.json()["id"]
    db_session.add(NodeExecution(
        execution_id=execution_id,
        node_id="node-1",
        node_type="shell",
        status="success",
    ))
    db_session.commit()

    response = client.delete(f"/api/executions/{execution_id}")
    assert response.status_code == 204
    assert client.get(f"/api/executions/{execution_id}").status_code == 404
    assert db_session.query(NodeExecution).filter(
        NodeExecution.execution_id == execution_id
    ).count() == 0

def test_delete_execution_not_found(client):
    response = client.delete("/api/executions/999")
    assert response.status_code == 404
