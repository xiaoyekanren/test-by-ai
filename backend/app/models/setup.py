# backend/app/models/setup.py
"""
Database initialization module.
Provides functions to initialize the database and create all tables.
"""
from sqlalchemy import Engine
from .database import Base


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