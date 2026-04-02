# backend/tests/test_workflows_api.py
import sys
sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.dependencies import get_db
import pytest
import os

TEST_DB_URL = "sqlite:///./test_db.sqlite"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

def test_list_workflows_empty():
    response = client.get("/api/workflows")
    assert response.status_code == 200
    assert response.json() == []

def test_create_workflow():
    response = client.post("/api/workflows", json={
        "name": "test-workflow",
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls"}}],
        "edges": []
    })
    assert response.status_code == 201
    assert response.json()["name"] == "test-workflow"

def test_get_workflow():
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.get("/api/workflows/1")
    assert response.status_code == 200
    assert response.json()["name"] == "test"

def test_update_workflow_nodes():
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.put("/api/workflows/1", json={
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "echo test"}}]
    })
    assert response.status_code == 200
    assert len(response.json()["nodes"]) == 1

def test_delete_workflow():
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.delete("/api/workflows/1")
    assert response.status_code == 204