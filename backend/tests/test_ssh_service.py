# backend/tests/test_ssh_service.py
import sys
sys.path.insert(0, 'backend')
from app.services.ssh_service import SSHService

def test_ssh_service_exists():
    """Test SSHService can be instantiated"""
    service = SSHService()
    assert service is not None

def test_ssh_service_has_run_command():
    """Test SSHService has run_command method"""
    service = SSHService()
    assert hasattr(service, 'run_command')

def test_ssh_service_has_upload():
    """Test SSHService has upload_file method"""
    service = SSHService()
    assert hasattr(service, 'upload_file')

def test_ssh_result_structure():
    """Test SSHResult has expected fields"""
    from app.services.ssh_service import SSHResult
    result = SSHResult(exit_status=0, stdout="OK", stderr="")
    assert result.exit_status == 0
    assert result.stdout == "OK"