import shlex
import sys

sys.path.insert(0, "backend")

from app.models.database import Server
from app.services.execution_engine import ExecutionEngine
from app.services.ssh_service import SSHResult


class FakeDeploySSH:
    def __init__(self):
        self.commands = []
        self.uploads = []
        self.writes = []

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

    def upload_file(self, host, username, password, local_path, remote_path, port=22, timeout=30):
        self.uploads.append({
            "host": host,
            "local_path": local_path,
            "remote_path": remote_path,
            "port": port,
            "timeout": timeout,
        })
        return {"status": "success", "ssh_port": port}

    def read_file(self, host, username, password, remote_path, port=22, timeout=30):
        return {
            "status": "success",
            "content": "cluster_name=defaultCluster\nain_rpc_port=10810\n",
            "ssh_port": port,
        }

    def write_file(self, host, username, password, remote_path, content, port=22, timeout=30):
        self.writes.append({
            "host": host,
            "remote_path": remote_path,
            "content": content,
        })
        return {"status": "success", "ssh_port": port}


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


def test_iotdb_ainode_deploy_writes_ainode_config(db_session):
    db_session.add_all([
        Server(id=1, name="ain-1", host="10.0.0.3", port=22, username="root", password="pw"),
        Server(id=2, name="dn-1", host="10.0.0.2", port=22, username="root", password="pw"),
    ])
    db_session.commit()

    engine = ExecutionEngine(db_session)
    fake_ssh = FakeDeploySSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iotdb_ainode_deploy_node({
        "server_id": 1,
        "_schedule_mode": "fixed",
        "_schedule_region": "私有云",
        "package_url": "https://example.com/timechodb-ainode-bin.tar.gz",
        "remote_package_path": "/tmp/timechodb-ainode-bin.tar.gz",
        "install_dir": "/opt/iotdb-ainode",
        "package_type": "tar.gz",
        "cluster_name": "prodCluster",
        "config_nodes": [{"server_id": 1, "host": "10.0.0.1", "cn_internal_port": 10710}],
        "data_nodes": [{"server_id": 2, "host": "10.0.0.2", "dn_rpc_port": 6667}],
        "ain_rpc_port": 10810,
        "username": "root",
        "password": "root",
        "config_items": {"ain_inference_memory_usage_ratio": "0.3"},
    })

    assert result["exit_status"] == 0
    assert result["ainode_home"] == "/opt/iotdb-ainode"
    assert result["ainode_conf_path"] == "/opt/iotdb-ainode/conf/iotdb-ainode.properties"
    assert result["ain_seed_config_node"] == "10.0.0.1:10710"
    assert result["ain_cluster_ingress_address"] == "10.0.0.2"
    assert result["ain_cluster_ingress_port"] == 6667
    assert "start-ainode.sh" in fake_ssh.commands[1]["command"]
    assert "stop-ainode.sh" in fake_ssh.commands[1]["command"]
    assert len(fake_ssh.writes) == 1

    content = fake_ssh.writes[0]["content"]
    assert "cluster_name=prodCluster" in content
    assert "ain_seed_config_node=10.0.0.1:10710" in content
    assert "ain_rpc_address=10.0.0.3" in content
    assert "ain_rpc_port=10810" in content
    assert "ain_cluster_ingress_address=10.0.0.2" in content
    assert "ain_cluster_ingress_port=6667" in content
    assert "ain_inference_memory_usage_ratio=0.3" in content


def test_iotdb_ainode_start_uses_daemon_script_and_waits_for_port(db_session):
    db_session.add(Server(id=1, name="ain-1", host="10.0.0.3", port=22, username="root", password="pw"))
    db_session.commit()

    engine = ExecutionEngine(db_session)
    fake_ssh = FakeDeploySSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iotdb_ainode_start_node({
        "server_id": 1,
        "_schedule_mode": "fixed",
        "_schedule_region": "私有云",
        "ainode_home": "/opt/iotdb-ainode",
        "ain_rpc_address": "10.0.0.3",
        "ain_rpc_port": 10810,
        "timeout_seconds": 30,
    })

    assert result["exit_status"] == 0
    assert result["start_script"] == "start-ainode.sh"
    assert "bash sbin/start-ainode.sh -d" in fake_ssh.commands[0]["command"]
    assert "/dev/tcp/10.0.0.3/10810" in fake_ssh.commands[1]["command"]


def test_iotdb_ainode_check_uses_first_data_node_for_show_ainodes(db_session):
    db_session.add(Server(id=2, name="dn-1", host="10.0.0.2", port=22, username="root", password="pw"))
    db_session.commit()

    engine = ExecutionEngine(db_session)
    fake_ssh = FakeDeploySSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iotdb_ainode_check_node({
        "_schedule_mode": "fixed",
        "_schedule_region": "私有云",
        "data_nodes": [{"server_id": 2, "host": "10.0.0.2", "install_dir": "/opt/iotdb", "dn_rpc_port": 6667}],
        "validation_sqls": ["show cluster"],
    })

    assert result["exit_status"] == 0
    assert result["checked_sqls"] == ["show ainodes", "show cluster"]
    assert "start-cli.sh" in fake_ssh.commands[0]["command"]
    assert "show ainodes" in fake_ssh.commands[0]["command"]
