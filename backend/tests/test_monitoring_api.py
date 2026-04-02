# backend/tests/test_monitoring_api.py
import sys
sys.path.insert(0, 'backend')

from unittest.mock import patch, MagicMock


class TestMonitoringService:
    """Tests for MonitoringService class"""

    def test_get_status_returns_system_info(self):
        """Test that get_status returns CPU, memory, and disk info"""
        from app.services.monitoring_service import MonitoringService

        service = MonitoringService()
        status = service.get_status()

        # Should contain required keys
        assert "cpu_percent" in status
        assert "memory" in status
        assert "disk" in status

        # Memory should have required fields
        assert "total" in status["memory"]
        assert "available" in status["memory"]
        assert "percent" in status["memory"]
        assert "used" in status["memory"]

        # Disk should have required fields
        assert "total" in status["disk"]
        assert "used" in status["disk"]
        assert "free" in status["disk"]
        assert "percent" in status["disk"]

    def test_get_processes_returns_list(self):
        """Test that get_processes returns a list of processes"""
        from app.services.monitoring_service import MonitoringService

        service = MonitoringService()
        processes = service.get_processes(limit=10)

        assert isinstance(processes, list)
        assert len(processes) <= 10

        # Each process should have required fields
        if len(processes) > 0:
            proc = processes[0]
            assert "pid" in proc
            assert "name" in proc
            assert "cpu_percent" in proc
            assert "memory_percent" in proc

    def test_get_processes_sort_by_cpu(self):
        """Test that processes can be sorted by CPU"""
        from app.services.monitoring_service import MonitoringService

        service = MonitoringService()
        processes = service.get_processes(limit=10, sort_by="cpu")

        # Verify sorted by cpu_percent descending
        if len(processes) > 1:
            for i in range(len(processes) - 1):
                assert processes[i]["cpu_percent"] >= processes[i + 1]["cpu_percent"]

    def test_get_processes_sort_by_memory(self):
        """Test that processes can be sorted by memory"""
        from app.services.monitoring_service import MonitoringService

        service = MonitoringService()
        processes = service.get_processes(limit=10, sort_by="memory")

        # Verify sorted by memory_percent descending
        if len(processes) > 1:
            for i in range(len(processes) - 1):
                assert processes[i]["memory_percent"] >= processes[i + 1]["memory_percent"]

    def test_kill_process_success(self):
        """Test killing a process (mocked)"""
        from app.services.monitoring_service import MonitoringService

        service = MonitoringService()

        with patch('psutil.Process') as mock_process_class:
            mock_process = MagicMock()
            mock_process_class.return_value = mock_process

            result = service.kill_process(12345)

            mock_process_class.assert_called_once_with(12345)
            mock_process.terminate.assert_called_once()
            assert result["success"] is True
            assert result["pid"] == 12345

    def test_kill_process_not_found(self):
        """Test killing a non-existent process"""
        from app.services.monitoring_service import MonitoringService

        service = MonitoringService()

        with patch('psutil.Process') as mock_process_class:
            import psutil
            mock_process_class.side_effect = psutil.NoSuchProcess(99999)

            result = service.kill_process(99999)

            assert result["success"] is False
            assert "error" in result


class TestMonitoringAPI:
    """Tests for monitoring API endpoints"""

    def test_get_local_status(self, client):
        """Test GET /api/monitoring/local/status"""
        response = client.get("/api/monitoring/local/status")
        assert response.status_code == 200
        data = response.json()
        assert "cpu_percent" in data
        assert "memory" in data
        assert "disk" in data

    def test_get_local_processes(self, client):
        """Test GET /api/monitoring/local/processes"""
        response = client.get("/api/monitoring/local/processes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_local_processes_with_limit(self, client):
        """Test GET /api/monitoring/local/processes with limit"""
        response = client.get("/api/monitoring/local/processes?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    def test_get_local_processes_with_sort(self, client):
        """Test GET /api/monitoring/local/processes with sort_by"""
        response = client.get("/api/monitoring/local/processes?sort_by=memory")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_kill_local_process(self, client):
        """Test POST /api/monitoring/local/process/{pid}/kill"""
        with patch('app.services.monitoring_service.MonitoringService.kill_process') as mock_kill:
            mock_kill.return_value = {"success": True, "pid": 12345}

            response = client.post("/api/monitoring/local/process/12345/kill")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_kill_local_process_failed(self, client):
        """Test POST /api/monitoring/local/process/{pid}/kill when kill fails"""
        with patch('app.services.monitoring_service.MonitoringService.kill_process') as mock_kill:
            mock_kill.return_value = {"success": False, "error": "Process not found"}

            response = client.post("/api/monitoring/local/process/99999/kill")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_get_remote_status_server_not_found(self, client):
        """Test GET /api/monitoring/remote/{server_id}/status with non-existent server"""
        response = client.get("/api/monitoring/remote/999/status")
        assert response.status_code == 404

    def test_get_remote_processes_server_not_found(self, client):
        """Test GET /api/monitoring/remote/{server_id}/processes with non-existent server"""
        response = client.get("/api/monitoring/remote/999/processes")
        assert response.status_code == 404

    def test_get_remote_status_success(self, client):
        """Test GET /api/monitoring/remote/{server_id}/status with existing server"""
        # First create a server
        client.post("/api/servers", json={
            "name": "test-remote",
            "host": "192.168.1.1",
            "port": 22
        })

        with patch('app.services.monitoring_service.MonitoringService.get_remote_status') as mock_remote:
            mock_remote.return_value = {
                "server_id": 1,
                "server_name": "test-remote",
                "cpu_percent": 25.5,
                "memory": {"total": 8589934592, "available": 4294967296, "percent": 50.0, "used": 4294967296},
                "disk": {"total": 107374182400, "used": 53687091200, "free": 53687091200, "percent": 50.0}
            }

            response = client.get("/api/monitoring/remote/1/status")
            assert response.status_code == 200
            data = response.json()
            assert "cpu_percent" in data
            assert "memory" in data
            assert "disk" in data

    def test_get_remote_processes_success(self, client):
        """Test GET /api/monitoring/remote/{server_id}/processes with existing server"""
        # First create a server
        client.post("/api/servers", json={
            "name": "test-remote-procs",
            "host": "192.168.1.2",
            "port": 22
        })

        with patch('app.services.monitoring_service.MonitoringService.get_remote_processes') as mock_remote:
            mock_remote.return_value = {
                "server_id": 1,
                "server_name": "test-remote-procs",
                "processes": [
                    {"pid": 1, "name": "init", "cpu_percent": 0.0, "memory_percent": 0.1},
                    {"pid": 100, "name": "sshd", "cpu_percent": 0.5, "memory_percent": 0.2}
                ]
            }

            response = client.get("/api/monitoring/remote/1/processes")
            assert response.status_code == 200
            data = response.json()
            assert "processes" in data
            assert isinstance(data["processes"], list)