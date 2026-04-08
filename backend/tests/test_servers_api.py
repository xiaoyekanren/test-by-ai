# backend/tests/test_servers_api.py
import sys
sys.path.insert(0, 'backend')

from app.services.ssh_service import SSHResult
from app.models.database import Server


def test_list_servers_empty(client):
    response = client.get("/api/servers")
    assert response.status_code == 200
    assert response.json() == []

def test_create_server(client):
    response = client.post("/api/servers", json={
        "name": "test-server",
        "host": "192.168.1.1",
        "port": 22
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-server"
    assert data["id"] == 1

def test_create_server_with_all_fields(client):
    response = client.post("/api/servers", json={
        "name": "full-server",
        "host": "10.0.0.1",
        "port": 2222,
        "username": "admin",
        "password": "secret",
        "description": "Test server description",
        "tags": "production,linux"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "full-server"
    assert data["host"] == "10.0.0.1"
    assert data["port"] == 2222
    assert data["username"] == "admin"
    assert data["description"] == "Test server description"
    assert data["tags"] == "production,linux"

def test_create_duplicate_server(client):
    client.post("/api/servers", json={"name": "duplicate-test", "host": "192.168.1.1"})
    response = client.post("/api/servers", json={"name": "duplicate-test", "host": "192.168.1.2"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

def test_get_server(client):
    client.post("/api/servers", json={"name": "test", "host": "192.168.1.1"})
    response = client.get("/api/servers/1")
    assert response.status_code == 200
    assert response.json()["name"] == "test"

def test_get_server_not_found(client):
    response = client.get("/api/servers/999")
    assert response.status_code == 404

def test_update_server(client):
    client.post("/api/servers", json={"name": "test", "host": "192.168.1.1"})
    response = client.put("/api/servers/1", json={"host": "192.168.1.2"})
    assert response.status_code == 200
    data = response.json()
    assert data["host"] == "192.168.1.2"

def test_update_server_name_conflict(client):
    client.post("/api/servers", json={"name": "server1", "host": "192.168.1.1"})
    client.post("/api/servers", json={"name": "server2", "host": "192.168.1.2"})
    response = client.put("/api/servers/1", json={"name": "server2"})
    assert response.status_code == 400

def test_update_server_not_found(client):
    response = client.put("/api/servers/999", json={"host": "192.168.1.2"})
    assert response.status_code == 404

def test_delete_server(client):
    client.post("/api/servers", json={"name": "test", "host": "192.168.1.1"})
    response = client.delete("/api/servers/1")
    assert response.status_code == 204

    # Verify server is deleted
    response = client.get("/api/servers/1")
    assert response.status_code == 404

def test_delete_server_not_found(client):
    response = client.delete("/api/servers/999")
    assert response.status_code == 404

def test_list_servers(client):
    client.post("/api/servers", json={"name": "server1", "host": "192.168.1.1"})
    client.post("/api/servers", json={"name": "server2", "host": "192.168.1.2"})
    response = client.get("/api/servers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

def test_test_connection_not_found(client):
    response = client.post("/api/servers/999/test")
    assert response.status_code == 404

def test_test_connection_marks_server_offline_on_failure(client, db_session, monkeypatch):
    class FailingSSHService:
        def run_command(self, **kwargs):
            return SSHResult(exit_status=-1, stdout="", stderr="", error="timeout")

    monkeypatch.setattr("app.api.servers.SSHService", FailingSSHService)
    client.post("/api/servers", json={"name": "test", "host": "192.168.1.1"})
    server = db_session.query(Server).filter(Server.id == 1).first()
    server.status = "online"
    db_session.commit()

    response = client.post("/api/servers/1/test")

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert client.get("/api/servers/1").json()["status"] == "offline"

def test_execute_command_not_found(client):
    response = client.post("/api/servers/999/execute", json={"command": "ls"})
    assert response.status_code == 404

def test_execute_command_missing_command(client):
    client.post("/api/servers", json={"name": "test", "host": "192.168.1.1"})
    response = client.post("/api/servers/1/execute", json={})
    assert response.status_code == 400
