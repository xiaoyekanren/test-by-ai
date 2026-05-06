import shlex
import sys

sys.path.insert(0, "backend")

from app.models.database import Server
from app.services.execution_engine import ExecutionEngine
from app.services.ssh_service import SSHResult


class FakeBenchmarkSSH:
    def __init__(self):
        self.commands = []
        self.writes = []
        self.config_content = "HOST=127.0.0.1\nPORT=6667\nCREATE_SCHEMA=false\n"

    def run_command(self, host, username, password, command, port=22, timeout=30):
        self.commands.append({
            "host": host,
            "command": command,
            "port": port,
            "timeout": timeout,
        })
        if "echo $pid" in command:
            return SSHResult(exit_status=0, stdout="12345\n", stderr="", ssh_port=port)
        return SSHResult(exit_status=0, stdout="ok", stderr="", ssh_port=port)

    def read_file(self, host, username, password, remote_path, port=22, timeout=30):
        return {"status": "success", "content": self.config_content}

    def write_file(self, host, username, password, remote_path, content, port=22, timeout=30):
        self.writes.append({
            "remote_path": remote_path,
            "content": content,
        })
        return {"status": "success"}

    def quote(self, value):
        return shlex.quote(str(value))


def test_iot_benchmark_deploy_checks_benchmark_layout(db_session):
    db_session.add(Server(id=1, name="bench", host="10.0.0.10", port=22, username="root", password="pw"))
    db_session.commit()
    engine = ExecutionEngine(db_session)
    fake_ssh = FakeBenchmarkSSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iot_benchmark_deploy_node({
        "server_id": 1,
        "_schedule_mode": "fixed",
        "_schedule_region": "私有云",
        "package_url": "https://example.com/iot-benchmark.zip",
        "remote_package_path": "/tmp/iot-benchmark.zip",
        "install_dir": "/opt/iot-benchmark",
        "package_type": "zip",
    })

    assert result["exit_status"] == 0
    assert result["benchmark_home"] == "/opt/iot-benchmark"
    assert result["benchmark_conf_path"] == "/opt/iot-benchmark/conf/config.properties"
    assert "test -e /opt/iot-benchmark/benchmark.sh" in fake_ssh.commands[-1]["command"]
    assert "test -e /opt/iot-benchmark/conf/config.properties" in fake_ssh.commands[-1]["command"]


def test_iot_benchmark_start_maps_common_read_write_config_and_cluster_targets(db_session):
    db_session.add(Server(id=1, name="bench", host="10.0.0.10", port=22, username="root", password="pw"))
    db_session.commit()
    engine = ExecutionEngine(db_session)
    fake_ssh = FakeBenchmarkSSH()
    engine.ssh_service = fake_ssh

    result = engine._execute_iot_benchmark_start_node({
        "server_id": 1,
        "_schedule_mode": "fixed",
        "_schedule_region": "私有云",
        "benchmark_home": "/opt/iot-benchmark",
        "data_nodes": [
            {"host": "10.0.0.21", "rpc_port": 6667},
            {"host": "10.0.0.22", "dn_rpc_port": 6668},
        ],
        "device_number": 12,
        "sensor_number": 3,
        "data_client_number": 2,
        "batch_size_per_write": 50,
        "create_schema": True,
        "is_delete_data": False,
        "query_device_num": 4,
        "write_operation_timeout_ms": 120000,
        "read_operation_timeout_ms": 300000,
        "csv_output": True,
    })

    assert result["exit_status"] == 0
    assert result["target_host"] == "10.0.0.21,10.0.0.22"
    assert result["rpc_port"] == "6667,6668"
    written_config = fake_ssh.writes[0]["content"]
    assert "HOST=10.0.0.21,10.0.0.22" in written_config
    assert "PORT=6667,6668" in written_config
    assert "DEVICE_NUMBER=12" in written_config
    assert "SENSOR_NUMBER=3" in written_config
    assert "DATA_CLIENT_NUMBER=2" in written_config
    assert "BATCH_SIZE_PER_WRITE=50" in written_config
    assert "CREATE_SCHEMA=true" in written_config
    assert "IS_DELETE_DATA=false" in written_config
    assert "QUERY_DEVICE_NUM=4" in written_config
    assert "WRITE_OPERATION_TIMEOUT_MS=120000" in written_config
    assert "READ_OPERATION_TIMEOUT_MS=300000" in written_config
    assert "CSV_OUTPUT=true" in written_config


def test_iot_benchmark_summary_parser_extracts_metrics(db_session):
    engine = ExecutionEngine(db_session)
    summary = engine._parse_iot_benchmark_summary(
        "INGESTION throughput 123.5 ok 120 fail 1\n"
        "PRECISE_QUERY avg latency 8.2 p95 12 p99 20\n"
    )

    assert summary["metrics"]["throughput"] == 123.5
    assert summary["metrics"]["ok_count"] == 120
    assert summary["metrics"]["fail_count"] == 1
    assert summary["metrics"]["avg_latency"] == 8.2
    assert "INGESTION" in summary["operation_lines"]
    assert "PRECISE_QUERY" in summary["operation_lines"]
