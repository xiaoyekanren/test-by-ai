# backend/tests/test_executions_api.py
import sys
sys.path.insert(0, 'backend')
import pytest

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