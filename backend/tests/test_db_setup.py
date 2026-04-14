# backend/tests/test_db_setup.py
import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, 'backend')

from app.config import DATABASE_PATH, BASE_DIR
from app.models.database import Base
from app.models.setup import init_db
from sqlalchemy import create_engine, inspect


class TestDatabaseSetup:
    """Tests for database initialization."""

    def test_data_directory_exists(self):
        """Verify that the data directory exists."""
        data_dir = BASE_DIR / "data"
        assert data_dir.exists(), f"Data directory {data_dir} should exist"
        assert data_dir.is_dir(), f"{data_dir} should be a directory"

    def test_database_file_created_on_init(self, tmp_path):
        """Verify that init_db creates the database file."""
        # Use a temporary database path for this test
        test_db_path = tmp_path / "test_app.db"
        test_db_url = f"sqlite:///{test_db_path}"

        # Create engine with test database
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

        # Call init_db with test engine
        init_db(test_engine)

        # Verify database file was created
        assert test_db_path.exists(), "Database file should be created"

    def test_all_tables_created(self, tmp_path):
        """Verify that all required tables are created."""
        # Use a temporary database path for this test
        test_db_path = tmp_path / "test_app.db"
        test_db_url = f"sqlite:///{test_db_path}"

        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

        # Initialize database
        init_db(test_engine)

        # Get list of tables
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()

        # Verify all required tables exist
        required_tables = {"servers", "workflows", "executions", "node_executions"}
        actual_tables = set(tables)

        assert required_tables.issubset(actual_tables), \
            f"Missing tables. Required: {required_tables}, Got: {actual_tables}"

    def test_servers_table_columns(self, tmp_path):
        """Verify servers table has expected columns."""
        test_db_path = tmp_path / "test_app.db"
        test_db_url = f"sqlite:///{test_db_path}"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

        init_db(test_engine)

        inspector = inspect(test_engine)
        columns = [col["name"] for col in inspector.get_columns("servers")]

        expected_columns = {"id", "name", "host", "port", "username", "password",
                          "description", "tags", "status", "region", "created_at", "updated_at"}
        actual_columns = set(columns)

        assert expected_columns.issubset(actual_columns), \
            f"Missing columns in servers table. Expected: {expected_columns}, Got: {actual_columns}"

    def test_workflows_table_columns(self, tmp_path):
        """Verify workflows table has expected columns."""
        test_db_path = tmp_path / "test_app.db"
        test_db_url = f"sqlite:///{test_db_path}"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

        init_db(test_engine)

        inspector = inspect(test_engine)
        columns = [col["name"] for col in inspector.get_columns("workflows")]

        expected_columns = {"id", "name", "description", "nodes", "edges",
                          "variables", "created_at", "updated_at"}
        actual_columns = set(columns)

        assert expected_columns.issubset(actual_columns), \
            f"Missing columns in workflows table. Expected: {expected_columns}, Got: {actual_columns}"

    def test_executions_table_columns(self, tmp_path):
        """Verify executions table has expected columns."""
        test_db_path = tmp_path / "test_app.db"
        test_db_url = f"sqlite:///{test_db_path}"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

        init_db(test_engine)

        inspector = inspect(test_engine)
        columns = [col["name"] for col in inspector.get_columns("executions")]

        expected_columns = {"id", "workflow_id", "status", "trigger_type", "triggered_by",
                          "started_at", "finished_at", "duration", "result", "summary", "created_at"}
        actual_columns = set(columns)

        assert expected_columns.issubset(actual_columns), \
            f"Missing columns in executions table. Expected: {expected_columns}, Got: {actual_columns}"

    def test_node_executions_table_columns(self, tmp_path):
        """Verify node_executions table has expected columns."""
        test_db_path = tmp_path / "test_app.db"
        test_db_url = f"sqlite:///{test_db_path}"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

        init_db(test_engine)

        inspector = inspect(test_engine)
        columns = [col["name"] for col in inspector.get_columns("node_executions")]

        expected_columns = {"id", "execution_id", "node_id", "node_type", "status",
                          "started_at", "finished_at", "duration", "input_data",
                          "output_data", "log_path", "error_message", "retry_count"}
        actual_columns = set(columns)

        assert expected_columns.issubset(actual_columns), \
            f"Missing columns in node_executions table. Expected: {expected_columns}, Got: {actual_columns}"

    def test_init_db_idempotent(self, tmp_path):
        """Verify that calling init_db multiple times is safe."""
        test_db_path = tmp_path / "test_app.db"
        test_db_url = f"sqlite:///{test_db_path}"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})

        # Call init_db twice
        init_db(test_engine)
        init_db(test_engine)

        # Verify tables still exist
        inspector = inspect(test_engine)
        tables = set(inspector.get_table_names())

        required_tables = {"servers", "workflows", "executions", "node_executions"}
        assert required_tables.issubset(tables), \
            "Tables should exist after multiple init_db calls"
