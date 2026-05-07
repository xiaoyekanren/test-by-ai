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
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls", "server_id": 1}}],
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
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "echo test", "server_id": 1}}]
    })
    assert response.status_code == 200
    assert len(response.json()["nodes"]) == 1


def test_create_random_workflow_rejects_fixed_server(client):
    response = client.post("/api/workflows", json={
        "name": "random-workflow",
        "schedule_mode": "random",
        "schedule_region": "私有云",
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls", "server_id": 1}}],
        "edges": []
    })

    assert response.status_code == 400


def test_create_fixed_workflow_requires_server(client):
    response = client.post("/api/workflows", json={
        "name": "fixed-workflow",
        "schedule_mode": "fixed",
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls"}}],
        "edges": []
    })

    assert response.status_code == 400


def test_create_random_workflow_without_server(client):
    response = client.post("/api/workflows", json={
        "name": "random-workflow-ok",
        "schedule_mode": "random",
        "schedule_region": "私有云",
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls"}}],
        "edges": []
    })

    assert response.status_code == 201
    assert response.json()["schedule_mode"] == "random"
    assert response.json()["schedule_region"] == "私有云"

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
