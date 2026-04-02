# backend/tests/test_executions_api.py
import sys
sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.dependencies import get_db
import pytest

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
    # Create a workflow for testing
    client.post("/api/workflows", json={"name": "test-wf", "nodes": [], "edges": []})
    yield
    Base.metadata.drop_all(bind=test_engine)

def test_create_execution():
    response = client.post("/api/executions", json={"workflow_id": 1})
    assert response.status_code == 201
    data = response.json()
    assert data["workflow_id"] == 1
    assert data["status"] == "pending"

def test_get_execution():
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.get("/api/executions/1")
    assert response.status_code == 200
    # Status could be pending, running, or completed since execution happens in background
    assert response.json()["status"] in ["pending", "running", "completed"]

def test_list_executions():
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.get("/api/executions")
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_stop_execution():
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.post("/api/executions/1/stop")
    assert response.status_code == 200