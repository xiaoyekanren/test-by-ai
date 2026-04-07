# backend/tests/test_workflows_api.py
import sys
sys.path.insert(0, 'backend')
import pytest

def test_list_workflows_empty(client):
    response = client.get("/api/workflows")
    assert response.status_code == 200
    assert response.json() == []

def test_create_workflow(client):
    response = client.post("/api/workflows", json={
        "name": "test-workflow",
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls"}}],
        "edges": []
    })
    assert response.status_code == 201
    assert response.json()["name"] == "test-workflow"

def test_get_workflow(client):
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.get("/api/workflows/1")
    assert response.status_code == 200
    assert response.json()["name"] == "test"

def test_update_workflow_nodes(client):
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.put("/api/workflows/1", json={
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "echo test"}}]
    })
    assert response.status_code == 200
    assert len(response.json()["nodes"]) == 1

def test_delete_workflow(client):
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.delete("/api/workflows/1")
    assert response.status_code == 204

def test_delete_workflow_with_executions(client):
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    execution_response = client.post("/api/executions", json={"workflow_id": 1})
    assert execution_response.status_code == 201

    response = client.delete("/api/workflows/1")
    assert response.status_code == 204

    response = client.get("/api/workflows/1")
    assert response.status_code == 404
