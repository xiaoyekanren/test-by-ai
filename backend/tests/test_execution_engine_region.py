# backend/tests/test_execution_engine_region.py
import sys
sys.path.insert(0, 'backend')
import pytest
from unittest.mock import MagicMock, patch
from app.models.database import Server, Execution, NodeExecution, Workflow
from app.services.execution_engine import ExecutionEngine


@pytest.fixture
def db_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def engine(db_session):
    """Create an ExecutionEngine instance."""
    return ExecutionEngine(db_session)


class TestResolveServerWithRegion:
    """Tests for _resolve_server_with_region method."""

    def test_resolve_server_explicit_server_id_in_config(self, engine, db_session):
        """Test that explicit server_id in config is used directly."""
        # Setup mock server
        mock_server = Server(id=1, name="test-server", host="192.168.1.1", region="私有云")
        db_session.query.return_value.filter.return_value.first.return_value = mock_server

        config = {"server_id": 1}
        context = {}

        result = engine._resolve_server_with_region(config, context)

        assert result is not None
        assert result.id == 1
        assert result.name == "test-server"

    def test_resolve_server_explicit_server_id_in_context(self, engine, db_session):
        """Test that server_id from context is used if not in config."""
        # Setup mock server
        mock_server = Server(id=2, name="context-server", host="192.168.1.2", region="公司")
        db_session.query.return_value.filter.return_value.first.return_value = mock_server

        config = {}
        context = {"server_id": 2}

        result = engine._resolve_server_with_region(config, context)

        assert result is not None
        assert result.id == 2

    def test_resolve_server_explicit_region_in_config(self, engine, db_session):
        """Test that explicit region in config selects idle server from that region."""
        # Setup mock idle servers
        mock_servers = [
            Server(id=3, name="region-server-1", host="192.168.1.3", region="公司-上层"),
            Server(id=4, name="region-server-2", host="192.168.1.4", region="公司-上层"),
        ]
        db_session.query.return_value.filter.return_value.all.return_value = mock_servers
        # Mock busy server IDs
        engine._compute_busy_server_ids = MagicMock(return_value=[])

        config = {"region": "公司-上层"}
        context = {}

        result = engine._resolve_server_with_region(config, context)

        assert result is not None
        assert result.region == "公司-上层"
        # Should be one of the idle servers
        assert result.id in [3, 4]

    def test_resolve_server_region_from_context(self, engine, db_session):
        """Test that region from context is used if not in config."""
        mock_servers = [
            Server(id=5, name="fit-server", host="192.168.1.5", region="Fit楼"),
        ]
        db_session.query.return_value.filter.return_value.all.return_value = mock_servers
        engine._compute_busy_server_ids = MagicMock(return_value=[])

        config = {}
        context = {"region": "Fit楼"}

        result = engine._resolve_server_with_region(config, context)

        assert result is not None
        assert result.region == "Fit楼"

    def test_resolve_server_default_region(self, engine, db_session):
        """Test that default region '私有云' is used when no region specified."""
        mock_servers = [
            Server(id=6, name="private-server", host="192.168.1.6", region="私有云"),
        ]
        db_session.query.return_value.filter.return_value.all.return_value = mock_servers
        engine._compute_busy_server_ids = MagicMock(return_value=[])

        config = {}
        context = {}

        result = engine._resolve_server_with_region(config, context)

        assert result is not None
        assert result.region == "私有云"

    def test_resolve_server_no_idle_servers(self, engine, db_session):
        """Test that None is returned when no idle servers available in target region."""
        # Mock query chain: db.query(Server).filter(Server.region == region).filter(...).all()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter2 = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter2
        mock_filter2.all.return_value = []  # Empty list for no idle servers

        engine._compute_busy_server_ids = MagicMock(return_value=[1, 2, 3])

        config = {"region": "公有云"}
        context = {}

        result = engine._resolve_server_with_region(config, context)

        assert result is None

    def test_resolve_server_excludes_busy_servers(self, engine, db_session):
        """Test that busy servers are excluded from selection."""
        # Only one idle server (id=7) in the region, others are busy
        mock_servers = [
            Server(id=7, name="idle-server", host="192.168.1.7", region="私有云"),
        ]
        # Mock query chain with proper filter chain handling
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter2 = MagicMock()
        db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter2
        mock_filter2.all.return_value = mock_servers

        engine._compute_busy_server_ids = MagicMock(return_value=[1, 2, 3, 4, 5, 6])

        config = {}
        context = {}

        result = engine._resolve_server_with_region(config, context)

        assert result is not None
        assert result.id == 7


class TestComputeBusyServerIds:
    """Tests for _compute_busy_server_ids method."""

    def test_compute_busy_server_ids_no_running_executions(self, engine, db_session):
        """Test that empty list is returned when no running executions."""
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = engine._compute_busy_server_ids()

        assert result == []

    def test_compute_busy_server_ids_with_running_executions(self, engine, db_session):
        """Test that busy server IDs are computed from running node executions."""
        # Mock running execution
        mock_execution = Execution(id=1, workflow_id=1, status="running")
        db_session.query.return_value.filter.return_value.all.side_effect = [
            [mock_execution],  # First call for running executions
            # Second call for node executions
            [NodeExecution(execution_id=1, node_id="node-1", status="running", input_data={"server_id": 1})],
        ]

        result = engine._compute_busy_server_ids()

        assert 1 in result

    def test_compute_busy_server_ids_multiple_executions(self, engine, db_session):
        """Test that busy server IDs from multiple executions are collected."""
        mock_executions = [
            Execution(id=1, workflow_id=1, status="running"),
            Execution(id=2, workflow_id=2, status="running"),
        ]
        # New implementation uses single query with .in_() filter
        mock_node_executions = [
            NodeExecution(execution_id=1, node_id="n1", status="running", input_data={"server_id": 1}),
            NodeExecution(execution_id=2, node_id="n2", status="running", input_data={"server_id": 2}),
        ]
        # Mock the query chain for execution IDs
        mock_query = db_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.all.return_value = mock_executions

        # Mock the query chain for node_executions with .in_() filter
        mock_ne_query = db_session.query.return_value
        mock_ne_filter = mock_ne_query.filter.return_value
        mock_ne_filter.all.return_value = mock_node_executions

        result = engine._compute_busy_server_ids()

        assert 1 in result
        assert 2 in result

    def test_compute_busy_server_ids_no_server_id_in_input_data(self, engine, db_session):
        """Test that node executions without server_id in input_data are ignored."""
        mock_execution = Execution(id=1, workflow_id=1, status="running")
        db_session.query.return_value.filter.return_value.all.side_effect = [
            [mock_execution],
            [NodeExecution(execution_id=1, node_id="n1", status="running", input_data={})],
        ]

        result = engine._compute_busy_server_ids()

        assert result == []

    def test_compute_busy_server_ids_from_cluster_nodes(self, engine, db_session):
        """Test that cluster topology node server IDs are also marked busy."""
        mock_execution = Execution(id=1, workflow_id=1, status="running")
        db_session.query.return_value.filter.return_value.all.side_effect = [
            [mock_execution],
            [
                NodeExecution(
                    execution_id=1,
                    node_id="cluster",
                    status="running",
                    input_data={
                        "config_nodes": [{"server_id": 10}],
                        "data_nodes": [{"server_id": 11}, {"server_id": 12}],
                    },
                )
            ],
        ]

        result = engine._compute_busy_server_ids()

        assert sorted(result) == [10, 11, 12]


class TestNodeRequiresServer:
    """Tests for _node_requires_server method."""

    def test_node_requires_server_shell(self, engine):
        """Test that shell node requires a server."""
        assert engine._node_requires_server("shell") is True

    def test_node_requires_server_upload(self, engine):
        """Test that upload node requires a server."""
        assert engine._node_requires_server("upload") is True

    def test_node_requires_server_download(self, engine):
        """Test that download node requires a server."""
        assert engine._node_requires_server("download") is True

    def test_node_requires_server_config(self, engine):
        """Test that config node requires a server."""
        assert engine._node_requires_server("config") is True

    def test_node_requires_server_iotdb_config(self, engine):
        """Test that iotdb_config node requires a server."""
        assert engine._node_requires_server("iotdb_config") is True

    def test_node_requires_server_log_view(self, engine):
        """Test that log_view node requires a server."""
        assert engine._node_requires_server("log_view") is True

    def test_node_requires_server_iotdb_deploy(self, engine):
        """Test that iotdb_deploy node requires a server."""
        assert engine._node_requires_server("iotdb_deploy") is True

    def test_node_requires_server_iotdb_start(self, engine):
        """Test that iotdb_start node requires a server."""
        assert engine._node_requires_server("iotdb_start") is True

    def test_node_requires_server_iotdb_cli(self, engine):
        """Test that iotdb_cli node requires a server."""
        assert engine._node_requires_server("iotdb_cli") is True

    def test_node_requires_server_iotdb_stop(self, engine):
        """Test that iotdb_stop node requires a server."""
        assert engine._node_requires_server("iotdb_stop") is True

    def test_node_requires_server_cluster_nodes(self, engine):
        """Test that cluster nodes require a server."""
        assert engine._node_requires_server("iotdb_cluster_deploy") is True
        assert engine._node_requires_server("iotdb_cluster_start") is True
        assert engine._node_requires_server("iotdb_cluster_check") is True
        assert engine._node_requires_server("iotdb_cluster_stop") is True

    def test_cluster_nodes_do_not_use_top_level_server_resolution(self, engine):
        """Test that cluster topology nodes resolve servers from config/data nodes."""
        assert engine._node_uses_top_level_server("iotdb_cluster_deploy") is False
        assert engine._node_uses_top_level_server("iotdb_cluster_start") is False
        assert engine._node_uses_top_level_server("iotdb_cluster_check") is False
        assert engine._node_uses_top_level_server("iotdb_cluster_stop") is False

    def test_node_requires_server_unknown_type(self, engine):
        """Test that unknown node types do not require a server."""
        assert engine._node_requires_server("unknown_type") is False

    def test_node_requires_server_empty_type(self, engine):
        """Test that empty node type does not require a server."""
        assert engine._node_requires_server("") is False


class TestBuildContextUpdates:
    """Tests for _build_context_updates method."""

    def test_build_context_updates_includes_region(self, engine, db_session):
        """Test that region is included in context updates."""
        mock_server = Server(id=1, name="test", host="192.168.1.1", region="私有云")
        db_session.query.return_value.filter.return_value.first.return_value = mock_server

        config = {"server_id": 1}
        result = {}

        updates = engine._build_context_updates("shell", config, result)

        assert "region" in updates
        assert updates["region"] == "私有云"

    def test_build_context_updates_region_from_result(self, engine, db_session):
        """Test that region from result is included in updates."""
        config = {}
        result = {"region": "公司"}

        updates = engine._build_context_updates("shell", config, result)

        assert "region" in updates
        assert updates["region"] == "公司"


class TestRequireServer:
    """Tests for _require_server method."""

    def test_require_server_with_context_resolves_by_region(self, engine, db_session):
        """Test that _require_server uses _resolve_server_with_region when context is provided."""
        mock_server = Server(id=1, name="test", host="192.168.1.1", region="私有云")
        db_session.query.return_value.filter.return_value.first.return_value = mock_server

        config = {"server_id": 1}
        context = {"region": "私有云"}

        result = engine._require_server(config, context)

        assert result.id == 1

    def test_require_server_without_context_uses_resolve_server(self, engine, db_session):
        """Test that _require_server uses _resolve_server when context is None."""
        mock_server = Server(id=2, name="test2", host="192.168.1.2", region="公司")
        db_session.query.return_value.filter.return_value.first.return_value = mock_server

        config = {"server_id": 2}

        result = engine._require_server(config)

        assert result.id == 2

    def test_require_server_raises_when_no_server(self, engine, db_session):
        """Test that ValueError is raised when no server available."""
        db_session.query.return_value.filter.return_value.first.return_value = None
        db_session.query.return_value.filter.return_value.all.return_value = []

        config = {}
        context = {}

        with pytest.raises(ValueError, match="no idle server available"):
            engine._require_server(config, context)


class TestMergeConfigWithContext:
    """Tests for _merge_config_with_context method."""

    def test_merge_config_with_context_includes_region(self, engine):
        """Test that region is included as a fallback key."""
        config = {}
        context = {"region": "私有云"}

        merged = engine._merge_config_with_context(config, context)

        assert "region" in merged
        assert merged["region"] == "私有云"

    def test_merge_config_with_context_keeps_existing_region(self, engine):
        """Test that existing region in config is not overwritten."""
        config = {"region": "公司"}
        context = {"region": "私有云"}

        merged = engine._merge_config_with_context(config, context)

        assert merged["region"] == "公司"
