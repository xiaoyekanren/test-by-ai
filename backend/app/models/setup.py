# backend/app/models/setup.py
"""
Database initialization module.
Provides functions to initialize the database and create all tables.
"""
import sqlite3
from sqlalchemy import Engine
from .database import Base


def migrate_servers_table_columns(engine: Engine) -> None:
    """
    Add missing columns to existing servers table.

    This migration handles older local databases where the servers table
    already exists but does not yet match the current SQLAlchemy model.

    Args:
        engine: SQLAlchemy engine to use for the migration
    """
    db_path = str(engine.url).replace("sqlite:///", "")
    if not db_path:
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(servers)")
        columns = [row[1] for row in cursor.fetchall()]

        if "tags" not in columns:
            cursor.execute("ALTER TABLE servers ADD COLUMN tags VARCHAR(200)")

        if "region" not in columns:
            cursor.execute("ALTER TABLE servers ADD COLUMN region VARCHAR(20) DEFAULT '私有云'")

        conn.commit()

        conn.close()
    except sqlite3.OperationalError:
        # Table doesn't exist yet - will be created by create_all()
        pass


def init_db(engine: Engine = None) -> None:
    """
    Initialize the database by creating all tables.

    This function creates all tables defined in the SQLAlchemy metadata
    if they don't already exist. It's safe to call multiple times.

    Args:
        engine: SQLAlchemy engine to use. If None, uses the default engine
                from app.dependencies.
    """
    if engine is None:
        # Import here to avoid circular imports
        from app.dependencies import engine as default_engine
        engine = default_engine

    # Create all tables defined in Base metadata
    Base.metadata.create_all(bind=engine)

    # Run migrations for existing databases
    migrate_servers_table_columns(engine)
