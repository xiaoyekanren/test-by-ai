# backend/app/models/database.py
from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship, DeclarativeBase

from app.utils.time import UTCDateTime, utc_now

class Base(DeclarativeBase):
    pass

class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    host = Column(String(100), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(50))
    password = Column(String(100))
    description = Column(Text)
    tags = Column(String(200))
    status = Column(String(20), default="offline")  # 'online' | 'offline'
    region = Column(String(20), default="私有云", server_default="私有云")  # 区域字段: 私有云 | 公司-上层 | 公司 | Fit楼 | 公有云 | 异构
    schedulable = Column(Boolean, default=True, server_default="1")
    created_at = Column(UTCDateTime(), default=utc_now)
    updated_at = Column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    def __init__(self, **kwargs):
        # Set default value for region when creating Python instance
        # (SQLAlchemy's Column default only applies during INSERT, not instance creation)
        if "region" not in kwargs:
            kwargs["region"] = "私有云"
        if "schedulable" not in kwargs:
            kwargs["schedulable"] = True
        super().__init__(**kwargs)

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    nodes = Column(JSON, default=list)
    edges = Column(JSON, default=list)
    variables = Column(JSON, default=dict)
    schedule_mode = Column(String(20), default="fixed", server_default="fixed")
    schedule_region = Column(String(20), default="私有云", server_default="私有云")
    created_at = Column(UTCDateTime(), default=utc_now)
    updated_at = Column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    executions = relationship("Execution", back_populates="workflow")

    def __init__(self, **kwargs):
        if "schedule_mode" not in kwargs:
            kwargs["schedule_mode"] = "fixed"
        if "schedule_region" not in kwargs:
            kwargs["schedule_region"] = "私有云"
        super().__init__(**kwargs)

class Execution(Base):
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending | running | paused | completed | failed | stopped
    trigger_type = Column(String(20), default="manual")  # 'manual' | 'scheduled' | 'api'
    triggered_by = Column(String(50))
    started_at = Column(UTCDateTime())
    finished_at = Column(UTCDateTime())
    duration = Column(Integer)  # seconds
    result = Column(String(20))  # 'passed' | 'failed' | 'partial'
    summary = Column(JSON)  # {"total": 10, "passed": 8, "failed": 2}
    created_at = Column(UTCDateTime(), default=utc_now)

    workflow = relationship("Workflow", back_populates="executions")
    node_executions = relationship("NodeExecution", back_populates="execution")

class NodeExecution(Base):
    __tablename__ = "node_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False)
    node_id = Column(String(50), nullable=False)
    node_type = Column(String(30), nullable=False)
    status = Column(String(20), default="pending")  # 'pending' | 'running' | 'success' | 'failed' | 'skipped'
    started_at = Column(UTCDateTime())
    finished_at = Column(UTCDateTime())
    duration = Column(Integer)
    input_data = Column(JSON)
    output_data = Column(JSON)
    log_path = Column(String(200))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    execution = relationship("Execution", back_populates="node_executions")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    updated_at = Column(UTCDateTime(), default=utc_now, onupdate=utc_now)
