import sys
import shlex

sys.path.insert(0, "backend")

from app.models.database import Server
from app.services.execution_engine import ExecutionEngine
from app.services.ssh_service import SSHResult


class FakeClusterSSH:
    def __init__(self):
        self.commands = []
        self.writes = []

    def run_command(self, host, username, password, command, port=22, timeout=30):
        self.commands.append({
            "host": host,
            "command": command,
            "port": port,
            "timeout": timeout,
        })
        return SSHResult(exit_status=0, stdout=f"ok {host}", stderr="", ssh_port=port)

    def quote(self, value):
        return shlex.quote(str(value))

    def read_file(self, host, username, password, remote_path, port=22, timeout=30):
        return {
            "status": "success",
            "content": "cluster_name=defaultCluster\n",
            "ssh_port": port,
        }

    def write_file(self, host, username, password, remote_path, content, port=22, timeout=30):
        self.writes.append({
            "host": host,
            "remote_path": remote_path,
            "content": content,
        })
        return {"status": "success", "ssh_port": port}


def test_cluster_deploy_deploys_and_writes_role_configs(db_session):
    db_session.add_all([
        Server(id=1, name="cn-1", host="10.0.0.1", port=22, username="root", password="pw", region="公司"),
        Server(id=2, name="dn-1", host="10.0.0.2", port=22, username="root", password="pw", region="公司"),
    ])
    db_session.commit()

    engine = ExecutionEngine(db_session)
    fake_ssh = FakeClusterSSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iotdb_cluster_deploy_node({
        "_schedule_mode": "fixed",
        "_schedule_region": "公司",
        "remote_package_path": "/tmp/apache-iotdb-bin.zip",
        "install_dir": "/opt/iotdb-cluster",
        "cluster_name": "prodCluster",
        "config_nodes": [{"server_id": 1}],
        "data_nodes": [{"server_id": 2}],
        "common_config": {
            "schema_replication_factor": "1",
            "data_replication_factor": "1",
        },
        "overwrite": True,
        "timeout": 900,
    })

    assert result["exit_status"] == 0
    assert result["cluster_name"] == "prodCluster"
    assert result["config_nodes"][0]["install_dir"] == "/opt/iotdb-cluster"
    assert result["data_nodes"][0]["install_dir"] == "/opt/iotdb-cluster"
    assert len(fake_ssh.writes) == 2

    config_content = next(item["content"] for item in fake_ssh.writes if item["host"] == "10.0.0.1")
    data_content = next(item["content"] for item in fake_ssh.writes if item["host"] == "10.0.0.2")

    assert "cluster_name=prodCluster" in config_content
    assert "cn_internal_address=10.0.0.1" in config_content
    assert "cn_seed_config_node=10.0.0.1:10710" in config_content
    assert "schema_replication_factor=1" in config_content

    assert "cluster_name=prodCluster" in data_content
    assert "dn_rpc_address=10.0.0.2" in data_content
    assert "dn_seed_config_node=10.0.0.1:10710" in data_content
    assert "data_replication_factor=1" in data_content


def test_cluster_deploy_deploys_once_and_merges_config_for_colocated_roles(db_session):
    db_session.add(Server(id=1, name="node-1", host="10.0.0.1", port=22, username="root", password="pw", region="公司"))
    db_session.commit()

    engine = ExecutionEngine(db_session)
    fake_ssh = FakeClusterSSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iotdb_cluster_deploy_node({
        "_schedule_mode": "fixed",
        "_schedule_region": "公司",
        "remote_package_path": "/tmp/apache-iotdb-bin.zip",
        "install_dir": "/opt/iotdb",
        "cluster_name": "prodCluster",
        "config_nodes": [{"server_id": 1}],
        "data_nodes": [{"server_id": 1}],
        "backup_before_write": False,
        "timeout": 900,
    })

    deploy_commands = [item["command"] for item in fake_ssh.commands if "apache-iotdb-bin.zip" in item["command"]]

    assert result["exit_status"] == 0
    assert len(deploy_commands) == 1
    assert "start-confignode.sh" in deploy_commands[0]
    assert "start-datanode.sh" in deploy_commands[0]
    assert len(fake_ssh.writes) == 1

    content = fake_ssh.writes[0]["content"]
    assert "cn_internal_address=10.0.0.1" in content
    assert "cn_seed_config_node=10.0.0.1:10710" in content
    assert "dn_rpc_address=10.0.0.1" in content
    assert "dn_seed_config_node=10.0.0.1:10710" in content


def test_cluster_deploy_requires_config_and_data_nodes(db_session):
    db_session.add(Server(id=1, name="cn-1", host="10.0.0.1", port=22, username="root", password="pw"))
    db_session.commit()

    engine = ExecutionEngine(db_session)

    no_config = engine._execute_iotdb_cluster_deploy_node({
        "remote_package_path": "/tmp/apache-iotdb-bin.zip",
        "config_nodes": [],
        "data_nodes": [{"server_id": 1}],
    })
    no_data = engine._execute_iotdb_cluster_deploy_node({
        "remote_package_path": "/tmp/apache-iotdb-bin.zip",
        "config_nodes": [{"server_id": 1}],
        "data_nodes": [],
    })

    assert no_config["error"] == "At least one ConfigNode is required"
    assert no_data["error"] == "At least one DataNode is required"
