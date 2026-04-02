# backend/tests/test_main.py
import sys
sys.path.insert(0, 'backend')
import pytest

def test_app_exists(client):
    """Test that FastAPI app can be created"""
    from app.main import app
    assert app is not None

def test_health_endpoint(client):
    """Test health check endpoint returns success"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"