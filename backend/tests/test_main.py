# backend/tests/test_main.py
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, 'backend')
from app.main import app

client = TestClient(app)

def test_app_exists():
    """Test that FastAPI app can be created"""
    assert app is not None

def test_health_endpoint():
    """Test health check endpoint returns success"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"