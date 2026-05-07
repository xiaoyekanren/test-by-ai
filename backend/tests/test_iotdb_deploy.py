import shlex
import sys

sys.path.insert(0, "backend")

from app.models.database import Server
from app.services.execution_engine import ExecutionEngine
from app.services.ssh_service import SSHResult


class FakeDeploySSH:
    def __init__(self):
        self.commands = []

    def run_command(self, host, username, password, command, port=22, timeout=30):
        self.commands.append({
            "host": host,
            "command": command,
            "port": port,
            "timeout": timeout,
        })
        return SSHResult(exit_status=0, stdout="ok", stderr="", ssh_port=port)

    def quote(self, value):
        return shlex.quote(str(value))


def test_iotdb_deploy_downloads_package_url_before_extracting(db_session):
    db_session.add(Server(id=1, name="node-1", host="10.0.0.1", port=22, username="root", password="pw"))
    db_session.commit()

    engine = ExecutionEngine(db_session)
    fake_ssh = FakeDeploySSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iotdb_deploy_node({
        "server_id": 1,
        "_schedule_mode": "fixed",
        "_schedule_region": "私有云",
        "package_url": "https://example.com/apache-iotdb-bin.zip",
        "remote_package_path": "/tmp/apache-iotdb-bin.zip",
        "install_dir": "/opt/iotdb",
        "package_type": "zip",
        "timeout": 900,
    })

    assert result["exit_status"] == 0
    assert result["package_url"] == "https://example.com/apache-iotdb-bin.zip"
    assert result["remote_package_path"] == "/tmp/apache-iotdb-bin.zip"
    assert len(fake_ssh.commands) == 2
    assert "curl -fL" in fake_ssh.commands[0]["command"]
    assert "wget -O" in fake_ssh.commands[0]["command"]
    assert "https://example.com/apache-iotdb-bin.zip" in fake_ssh.commands[0]["command"]
    assert "unzip -q" in fake_ssh.commands[1]["command"]


def test_iotdb_deploy_rejects_local_artifact_and_package_url_together(db_session):
    db_session.add(Server(id=1, name="node-1", host="10.0.0.1", port=22, username="root", password="pw"))
    db_session.commit()

    engine = ExecutionEngine(db_session)
    fake_ssh = FakeDeploySSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iotdb_deploy_node({
        "server_id": 1,
        "_schedule_mode": "fixed",
        "_schedule_region": "私有云",
        "artifact_local_path": "/tmp/apache-iotdb-bin.zip",
        "package_url": "https://example.com/apache-iotdb-bin.zip",
        "remote_package_path": "/tmp/apache-iotdb-bin.zip",
        "install_dir": "/opt/iotdb",
    })

    assert result["exit_status"] == -1
    assert result["error"] == "Use either artifact_local_path or package_url, not both"
    assert fake_ssh.commands == []
