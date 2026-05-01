# backend/app/models/setup.py
"""
数据库初始化模块。
提供数据库初始化和创建所有表的函数。
"""
import sqlite3
from sqlalchemy import Engine
from .database import Base


def migrate_servers_table_columns(engine: Engine) -> None:
    """
    为已有的 servers 表添加缺失的列。

    此迁移处理本地旧数据库中 servers 表已存在但尚未匹配当前
    SQLAlchemy 模型的情况。

    Args:
        engine: 用于迁移的 SQLAlchemy 引擎
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
    初始化数据库，创建所有表。

    此函数创建 SQLAlchemy 元数据中定义的所有表（如果尚不存在）。
    可以安全地多次调用。

    Args:
        engine: 要使用的 SQLAlchemy 引擎。如果为 None，则使用
                app.dependencies 中的默认引擎。
    """
    if engine is None:
        # Import here to avoid circular imports
        from app.dependencies import engine as default_engine
        engine = default_engine

    # Create all tables defined in Base metadata
    Base.metadata.create_all(bind=engine)

    # Run migrations for existing databases
    migrate_servers_table_columns(engine)
