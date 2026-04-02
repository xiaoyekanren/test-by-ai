# Phase 1: Backend Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Flask backend to FastAPI with SQLAlchemy models, Pydantic schemas, and execution engine.

**Architecture:** FastAPI app with layered structure (API → Service → Model), async execution engine for workflow nodes, WebSocket for real-time progress.

**Tech Stack:** FastAPI 0.100+, Pydantic 2.x, SQLAlchemy 2.x, paramiko 3.x, asyncio

---

## Task 1: Project Skeleton

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/dependencies.py`
- Test: `backend/tests/test_main.py`

- [ ] **Step 1: Write the failing test for FastAPI app startup**

```python
# backend/tests/test_main.py
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, 'backend')
from app.main import app

client = TestClient(app)

def test_app_exists():
    """Test that FastAPI app can be created"""
    assert app is not None

def test_health_endpoint():
    """Test health check endpoint returns success"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_main.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.main'"

- [ ] **Step 3: Create requirements.txt**

```text
# backend/requirements.txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
sqlalchemy==2.0.25
aiosqlite==0.19.0
paramiko==3.4.0
python-multipart==0.0.6
pytest==7.4.4
httpx==0.26.0
websockets==12.0
```

- [ ] **Step 4: Create app/__init__.py**

```python
# backend/app/__init__.py
# Empty init file for package
```

- [ ] **Step 5: Create config.py**

```python
# backend/app/config.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = BASE_DIR / "data" / "app.db"

# Ensure data directory exists
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 6: Create dependencies.py for database injection**

```python
# backend/app/dependencies.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .config import DATABASE_PATH

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 7: Create main.py with health endpoint**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="IoTDB Test Automation Platform",
    description="Backend API for IoTDB test automation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# API routes will be registered here in later tasks
# from app.api import servers, workflows, executions, monitoring
# app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
# app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
# app.include_router(executions.router, prefix="/api/executions", tags=["executions"])
# app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd backend && pip install -r requirements.txt && python -m pytest tests/test_main.py -v`
Expected: PASS (2 tests)

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/app/__init__.py backend/app/config.py backend/app/dependencies.py backend/app/main.py backend/tests/test_main.py
git commit -m "feat: create FastAPI project skeleton with health endpoint"
```

---

## Task 2: SQLAlchemy Models

**Files:**
- Create: `backend/app/models/database.py`
- Create: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test for model creation**

```python
# backend/tests/test_models.py
import sys
sys.path.insert(0, 'backend')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, Server, Workflow, Execution, NodeExecution

def test_server_model():
    """Test Server model can be instantiated"""
    server = Server(
        name="test-server",
        host="192.168.1.1",
        port=22,
        username="admin",
        password="secret"
    )
    assert server.name == "test-server"
    assert server.host == "192.168.1.1"

def test_workflow_model():
    """Test Workflow model with nodes JSON"""
    workflow = Workflow(
        name="test-workflow",
        nodes=[{"id": "node1", "type": "shell"}],
        edges=[{"from": "node1", "to": "node2"}]
    )
    assert workflow.name == "test-workflow"
    assert len(workflow.nodes) == 1

def test_execution_model():
    """Test Execution model"""
    execution = Execution(
        workflow_id=1,
        status="pending",
        trigger_type="manual"
    )
    assert execution.status == "pending"

def test_node_execution_model():
    """Test NodeExecution model"""
    ne = NodeExecution(
        execution_id=1,
        node_id="node1",
        node_type="shell",
        status="pending"
    )
    assert ne.node_id == "node1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.models.database'"

- [ ] **Step 3: Create models/__init__.py**

```python
# backend/app/models/__init__.py
from .database import Base, Server, Workflow, Execution, NodeExecution
```

- [ ] **Step 4: Create database.py with all models**

```python
# backend/app/models/database.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime

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
    role = Column(String(20), default="test_node")  # 'test_node' | 'target_node' | 'both'
    status = Column(String(20), default="offline")  # 'online' | 'offline'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    nodes = Column(JSON, default=list)  # [{"id": "node1", "type": "shell", "config": {...}}]
    edges = Column(JSON, default=list)  # [{"from": "node1", "to": "node2"}]
    variables = Column(JSON, default=dict)  # {"var1": "value1"}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    executions = relationship("Execution", back_populates="workflow")

class Execution(Base):
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    status = Column(String(20), default="pending")  # 'pending' | 'running' | 'paused' | 'completed' | 'failed'
    trigger_type = Column(String(20), default="manual")  # 'manual' | 'scheduled' | 'api'
    triggered_by = Column(String(50))
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration = Column(Integer)  # seconds
    result = Column(String(20))  # 'passed' | 'failed' | 'partial'
    summary = Column(JSON)  # {"total": 10, "passed": 8, "failed": 2}
    created_at = Column(DateTime, default=datetime.utcnow)

    workflow = relationship("Workflow", back_populates="executions")
    node_executions = relationship("NodeExecution", back_populates="execution")

class NodeExecution(Base):
    __tablename__ = "node_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False)
    node_id = Column(String(50), nullable=False)
    node_type = Column(String(30), nullable=False)
    status = Column(String(20), default="pending")  # 'pending' | 'running' | 'success' | 'failed' | 'skipped'
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration = Column(Integer)
    input_data = Column(JSON)
    output_data = Column(JSON)
    log_path = Column(String(200))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    execution = relationship("Execution", back_populates="node_executions")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/__init__.py backend/app/models/database.py backend/tests/test_models.py
git commit -m "feat: add SQLAlchemy models for Server, Workflow, Execution, NodeExecution"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/server.py`
- Create: `backend/app/schemas/workflow.py`
- Create: `backend/app/schemas/execution.py`
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write the failing test for schema validation**

```python
# backend/tests/test_schemas.py
import sys
sys.path.insert(0, 'backend')
from app.schemas.server import ServerCreate, ServerResponse
from app.schemas.workflow import WorkflowCreate, WorkflowResponse
from app.schemas.execution import ExecutionCreate, ExecutionResponse

def test_server_create_schema():
    """Test ServerCreate validation"""
    data = {"name": "test", "host": "192.168.1.1"}
    server = ServerCreate(**data)
    assert server.name == "test"
    assert server.port == 22  # default

def test_server_create_requires_name_host():
    """Test ServerCreate requires name and host"""
    from pydantic import ValidationError
    try:
        ServerCreate(host="192.168.1.1")
        assert False, "Should raise ValidationError"
    except ValidationError as e:
        assert "name" in str(e)

def test_workflow_create_schema():
    """Test WorkflowCreate with nodes"""
    data = {
        "name": "test-workflow",
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls"}}],
        "edges": [{"from": "n1", "to": "n2"}]
    }
    wf = WorkflowCreate(**data)
    assert wf.name == "test-workflow"
    assert len(wf.nodes) == 1

def test_execution_create_schema():
    """Test ExecutionCreate"""
    data = {"workflow_id": 1, "trigger_type": "manual"}
    ex = ExecutionCreate(**data)
    assert ex.workflow_id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_schemas.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.schemas'"

- [ ] **Step 3: Create schemas/__init__.py**

```python
# backend/app/schemas/__init__.py
from .server import ServerCreate, ServerUpdate, ServerResponse
from .workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from .execution import ExecutionCreate, ExecutionResponse, NodeExecutionResponse
```

- [ ] **Step 4: Create server.py schemas**

```python
# backend/app/schemas/server.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=50)
    password: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    tags: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default="test_node")

class ServerCreate(ServerBase):
    pass

class ServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = Field(None, min_length=1, max_length=100)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    role: Optional[str] = None

class ServerResponse(ServerBase):
    id: int
    status: str = "offline"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 5: Create workflow.py schemas**

```python
# backend/app/schemas/workflow.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class NodeDefinition(BaseModel):
    id: str
    type: str  # shell, upload, download, iotdb_deploy, condition, loop, etc.
    config: Dict[str, Any] = {}
    position: Optional[Dict[str, float]] = None  # {"x": 100, "y": 200}

class EdgeDefinition(BaseModel):
    from: str
    to: str
    label: Optional[str] = None

class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    nodes: List[NodeDefinition] = []
    edges: List[EdgeDefinition] = []
    variables: Dict[str, str] = {}

class WorkflowCreate(WorkflowBase):
    pass

class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    nodes: Optional[List[NodeDefinition]] = None
    edges: Optional[List[EdgeDefinition]] = None
    variables: Optional[Dict[str, str]] = None

class WorkflowResponse(WorkflowBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 6: Create execution.py schemas**

```python
# backend/app/schemas/execution.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class ExecutionCreate(BaseModel):
    workflow_id: int
    trigger_type: str = Field(default="manual")
    triggered_by: Optional[str] = None

class ExecutionUpdate(BaseModel):
    status: Optional[str] = None

class ExecutionResponse(BaseModel):
    id: int
    workflow_id: int
    status: str
    trigger_type: str
    triggered_by: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration: Optional[int]
    result: Optional[str]
    summary: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True

class NodeExecutionResponse(BaseModel):
    id: int
    execution_id: int
    node_id: str
    node_type: str
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration: Optional[int]
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    log_path: Optional[str]
    error_message: Optional[str]
    retry_count: int

    class Config:
        from_attributes = True
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_schemas.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/ backend/tests/test_schemas.py
git commit -m "feat: add Pydantic schemas for Server, Workflow, Execution"
```

---

## Task 4: SSH Service

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/ssh_service.py`
- Test: `backend/tests/test_ssh_service.py`

- [ ] **Step 1: Write the failing test for SSH service**

```python
# backend/tests/test_ssh_service.py
import sys
sys.path.insert(0, 'backend')
from app.services.ssh_service import SSHService

def test_ssh_service_exists():
    """Test SSHService can be instantiated"""
    service = SSHService()
    assert service is not None

def test_ssh_service_has_run_command():
    """Test SSHService has run_command method"""
    service = SSHService()
    assert hasattr(service, 'run_command')

def test_ssh_service_has_upload():
    """Test SSHService has upload_file method"""
    service = SSHService()
    assert hasattr(service, 'upload_file')

def test_ssh_result_structure():
    """Test SSHResult has expected fields"""
    from app.services.ssh_service import SSHResult
    result = SSHResult(exit_status=0, stdout="OK", stderr="")
    assert result.exit_status == 0
    assert result.stdout == "OK"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ssh_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services'"

- [ ] **Step 3: Create services/__init__.py**

```python
# backend/app/services/__init__.py
from .ssh_service import SSHService, SSHResult
```

- [ ] **Step 4: Create ssh_service.py (migrate from api/utils.py)**

```python
# backend/app/services/ssh_service.py
import paramiko
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class SSHResult:
    exit_status: int
    stdout: str
    stderr: str
    error: Optional[str] = None
    ssh_port: Optional[int] = None

class SSHService:
    """SSH service for running commands and file transfer"""

    def run_command(
        self,
        host: str,
        username: Optional[str],
        password: Optional[str],
        command: str,
        port: int = 22,
        timeout: int = 30
    ) -> SSHResult:
        """Execute command on remote server via SSH"""
        ports_to_try = [22, port] if port != 22 else [22]
        last_exc = None

        for ssh_port in ports_to_try:
            try:
                client = paramiko.SSHClient()
                client.load_system_host_keys()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    hostname=host,
                    port=ssh_port,
                    username=username,
                    password=password,
                    timeout=timeout
                )
                stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
                out = stdout.read().decode('utf-8', errors='ignore')
                err = stderr.read().decode('utf-8', errors='ignore')
                exit_status = stdout.channel.recv_exit_status()
                client.close()
                return SSHResult(exit_status=exit_status, stdout=out, stderr=err, ssh_port=ssh_port)
            except Exception as e:
                last_exc = e
                continue

        return SSHResult(exit_status=-1, stdout="", stderr="", error=str(last_exc))

    def upload_file(
        self,
        host: str,
        username: Optional[str],
        password: Optional[str],
        local_path: str,
        remote_path: str,
        port: int = 22,
        timeout: int = 30
    ) -> dict:
        """Upload file to remote server via SFTP"""
        ports_to_try = [22, port] if port != 22 else [22]
        last_exc = None

        for p in ports_to_try:
            try:
                transport = paramiko.Transport((host, p))
                transport.connect(username=username, password=password)
                sftp = paramiko.SFTPClient.from_transport(transport)
                sftp.put(local_path, remote_path)
                sftp.close()
                transport.close()
                return {"status": "success"}
            except Exception as e:
                last_exc = e
                try:
                    transport.close()
                except:
                    pass
                continue

        return {"status": "error", "message": str(last_exc)}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ssh_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/ssh_service.py backend/tests/test_ssh_service.py
git commit -m "feat: add SSHService for remote command execution and file upload"
```

---

## Task 5: Server API

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/servers.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_servers_api.py`

- [ ] **Step 1: Write the failing test for servers API**

```python
# backend/tests/test_servers_api.py
import sys
sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import Base, Server
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.dependencies import get_db
import pytest

# Test database setup
TEST_DB_URL = "sqlite:///./test_db.sqlite"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

def test_list_servers_empty():
    """Test listing servers when empty"""
    response = client.get("/api/servers")
    assert response.status_code == 200
    assert response.json() == []

def test_create_server():
    """Test creating a server"""
    response = client.post("/api/servers", json={
        "name": "test-server",
        "host": "192.168.1.1",
        "port": 22
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-server"
    assert data["id"] == 1

def test_get_server():
    """Test getting a specific server"""
    # Create first
    client.post("/api/servers", json={"name": "test", "host": "192.168.1.1"})
    # Get it
    response = client.get("/api/servers/1")
    assert response.status_code == 200
    assert response.json()["name"] == "test"

def test_get_server_not_found():
    """Test getting non-existent server"""
    response = client.get("/api/servers/999")
    assert response.status_code == 404

def test_update_server():
    """Test updating a server"""
    client.post("/api/servers", json={"name": "test", "host": "192.168.1.1"})
    response = client.put("/api/servers/1", json={"host": "192.168.1.2"})
    assert response.status_code == 200

def test_delete_server():
    """Test deleting a server"""
    client.post("/api/servers", json={"name": "test", "host": "192.168.1.1"})
    response = client.delete("/api/servers/1")
    assert response.status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_servers_api.py -v`
Expected: FAIL with "404 Not Found" (route not registered)

- [ ] **Step 3: Create api/__init__.py**

```python
# backend/app/api/__init__.py
from .servers import router as servers_router
```

- [ ] **Step 4: Create servers.py API router**

```python
# backend/app/api/servers.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..dependencies import get_db
from ..models.database import Server
from ..schemas.server import ServerCreate, ServerUpdate, ServerResponse
from ..services.ssh_service import SSHService

router = APIRouter()
ssh_service = SSHService()

@router.get("", response_model=List[ServerResponse])
def list_servers(db: Session = Depends(get_db)):
    """Get all servers"""
    servers = db.query(Server).order_by(Server.created_at.desc()).all()
    return servers

@router.post("", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(server: ServerCreate, db: Session = Depends(get_db)):
    """Create a new server"""
    db_server = Server(**server.model_dump())
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server

@router.get("/{server_id}", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db)):
    """Get server by ID"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

@router.put("/{server_id}", response_model=ServerResponse)
def update_server(server_id: int, server: ServerUpdate, db: Session = Depends(get_db)):
    """Update server"""
    db_server = db.query(Server).filter(Server.id == server_id).first()
    if not db_server:
        raise HTTPException(status_code=404, detail="Server not found")
    for key, value in server.model_dump(exclude_unset=True).items():
        setattr(db_server, key, value)
    db.commit()
    db.refresh(db_server)
    return db_server

@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: int, db: Session = Depends(get_db)):
    """Delete server"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    db.delete(server)
    db.commit()

@router.post("/{server_id}/test")
def test_connection(server_id: int, db: Session = Depends(get_db)):
    """Test server connection"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command="echo OK",
        port=server.port,
        timeout=3
    )
    if result.error:
        return {"status": "error", "message": result.error, "server_status": "offline"}
    # Update status
    server.status = "online"
    db.commit()
    return {"status": "success", "message": "Connection successful", "server_status": "online"}

@router.post("/{server_id}/execute")
def execute_command(server_id: int, payload: dict, db: Session = Depends(get_db)):
    """Execute command on server"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    command = payload.get("command", "")
    if not command:
        raise HTTPException(status_code=400, detail="Command is required")
    result = ssh_service.run_command(
        host=server.host,
        username=server.username,
        password=server.password,
        command=command,
        port=server.port,
        timeout=30
    )
    if result.error:
        return {"status": "error", "message": result.error, "output": ""}
    return {"status": "success", "output": result.stdout, "error": result.stderr, "exit_status": result.exit_status}
```

- [ ] **Step 5: Update main.py to register router**

```python
# backend/app/main.py (add router registration after imports)
from app.api.servers import router as servers_router
app.include_router(servers_router, prefix="/api/servers", tags=["servers"])
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_servers_api.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/__init__.py backend/app/api/servers.py backend/tests/test_servers_api.py
git commit -m "feat: add servers API with CRUD and SSH execute"
```

---

## Task 6: Workflow API

**Files:**
- Create: `backend/app/api/workflows.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_workflows_api.py`

- [ ] **Step 1: Write the failing test for workflows API**

```python
# backend/tests/test_workflows_api.py
import sys
sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.dependencies import get_db
import pytest

TEST_DB_URL = "sqlite:///./test_db.sqlite"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

def test_list_workflows_empty():
    """Test listing workflows when empty"""
    response = client.get("/api/workflows")
    assert response.status_code == 200
    assert response.json() == []

def test_create_workflow():
    """Test creating a workflow"""
    response = client.post("/api/workflows", json={
        "name": "test-workflow",
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "ls"}}],
        "edges": []
    })
    assert response.status_code == 201
    assert response.json()["name"] == "test-workflow"

def test_get_workflow():
    """Test getting a workflow"""
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.get("/api/workflows/1")
    assert response.status_code == 200
    assert response.json()["name"] == "test"

def test_update_workflow_nodes():
    """Test updating workflow nodes"""
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.put("/api/workflows/1", json={
        "nodes": [{"id": "n1", "type": "shell", "config": {"command": "echo test"}}]
    })
    assert response.status_code == 200
    assert len(response.json()["nodes"]) == 1

def test_delete_workflow():
    """Test deleting a workflow"""
    client.post("/api/workflows", json={"name": "test", "nodes": [], "edges": []})
    response = client.delete("/api/workflows/1")
    assert response.status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_workflows_api.py -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: Create workflows.py API router**

```python
# backend/app/api/workflows.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..dependencies import get_db
from ..models.database import Workflow
from ..schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse

router = APIRouter()

@router.get("", response_model=List[WorkflowResponse])
def list_workflows(db: Session = Depends(get_db)):
    """Get all workflows"""
    workflows = db.query(Workflow).order_by(Workflow.created_at.desc()).all()
    return workflows

@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    """Create a new workflow"""
    db_workflow = Workflow(**workflow.model_dump())
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """Get workflow by ID"""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(workflow_id: int, workflow: WorkflowUpdate, db: Session = Depends(get_db)):
    """Update workflow"""
    db_workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    for key, value in workflow.model_dump(exclude_unset=True).items():
        setattr(db_workflow, key, value)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """Delete workflow"""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    db.delete(workflow)
    db.commit()
```

- [ ] **Step 4: Update main.py to register workflow router**

```python
# backend/app/main.py (add after servers router)
from app.api.workflows import router as workflows_router
app.include_router(workflows_router, prefix="/api/workflows", tags=["workflows"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_workflows_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/workflows.py backend/tests/test_workflows_api.py
git commit -m "feat: add workflows API with CRUD operations"
```

---

## Task 7: Monitoring API (Local)

**Files:**
- Create: `backend/app/api/monitoring.py`
- Create: `backend/app/services/monitoring_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_monitoring_api.py`

- [ ] **Step 1: Write the failing test for monitoring API**

```python
# backend/tests/test_monitoring_api.py
import sys
sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_local_status():
    """Test getting local server status"""
    response = client.get("/api/monitoring/local/status")
    assert response.status_code == 200
    data = response.json()
    assert "cpu" in data
    assert "memory" in data
    assert "disk" in data

def test_get_local_processes():
    """Test getting local processes"""
    response = client.get("/api/monitoring/local/processes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "pid" in data[0]
        assert "name" in data[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_monitoring_api.py -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: Create monitoring_service.py**

```python
# backend/app/services/monitoring_service.py
import psutil
from datetime import datetime
from typing import List, Dict, Any

class MonitoringService:
    """Service for collecting system monitoring data"""

    def get_status(self) -> Dict[str, Any]:
        """Get system status (CPU, memory, disk)"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "usage": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total": memory.total,
                "used": memory.used,
                "available": memory.available,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            }
        }

    def get_processes(self, limit: int = 20, sort_by: str = "memory") -> List[Dict[str, Any]]:
        """Get running processes"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu': proc.info['cpu_percent'] or 0.0,
                    'memory': proc.info['memory_percent'] or 0.0
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if sort_by == 'cpu':
            processes.sort(key=lambda x: x['cpu'], reverse=True)
        else:
            processes.sort(key=lambda x: x['memory'], reverse=True)

        return processes[:limit]

    def kill_process(self, pid: int) -> bool:
        """Kill a process by PID"""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            return True
        except psutil.NoSuchProcess:
            return False
```

- [ ] **Step 4: Create monitoring.py API router**

```python
# backend/app/api/monitoring.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from ..services.monitoring_service import MonitoringService
from ..services.ssh_service import SSHService
from ..dependencies import get_db
from ..models.database import Server

router = APIRouter()
monitoring_service = MonitoringService()
ssh_service = SSHService()

@router.get("/local/status")
def get_local_status():
    """Get local server status"""
    return monitoring_service.get_status()

@router.get("/local/processes")
def get_local_processes(limit: int = 20, sort_by: str = "memory"):
    """Get local processes"""
    return monitoring_service.get_processes(limit=limit, sort_by=sort_by)

@router.post("/local/process/{pid}/kill")
def kill_local_process(pid: int):
    """Kill local process"""
    success = monitoring_service.kill_process(pid)
    if not success:
        raise HTTPException(status_code=404, detail=f"Process {pid} not found")
    return {"status": "success", "message": f"Process {pid} terminated"}

@router.get("/remote/{server_id}/status")
def get_remote_status(server_id: int, db = Depends(get_db)):
    """Get remote server status via SSH"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    # Use shell commands to get status
    cmd = "(nproc || echo '1') && (uptime | grep -oP 'average: \\K[0-9.]+' || echo '0') && (free -b | awk '/^Mem:/ {print $2, $3}') && (df -B1 / | tail -1 | awk '{print $2, $3, $(NF-1)}')"
    result = ssh_service.run_command(server.host, server.username, server.password, cmd, server.port)
    if result.error:
        return {"status": "error", "message": result.error}
    # Parse output
    lines = result.stdout.strip().split('\n')
    try:
        return {
            "status": "success",
            "data": {
                "cpu_count": int(lines[0]),
                "cpu_usage": float(lines[1]),
                "memory": {"total": int(lines[2].split()[0]), "used": int(lines[2].split()[1])},
                "disk": {"total": int(lines[3].split()[0]), "used": int(lines[3].split()[1]), "percent": lines[3].split()[2]}
            }
        }
    except:
        return {"status": "success", "data": {"raw": result.stdout}}

@router.get("/remote/{server_id}/processes")
def get_remote_processes(server_id: int, limit: int = 20, db = Depends(get_db)):
    """Get remote processes via SSH"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    cmd = f"ps -eo pid,comm,%cpu,%mem --sort=-%mem | head -n {limit+1}"
    result = ssh_service.run_command(server.host, server.username, server.password, cmd, server.port)
    if result.error:
        return {"status": "error", "message": result.error}
    lines = result.stdout.strip().splitlines()
    procs = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 4:
            try:
                procs.append({"pid": int(parts[0]), "name": parts[1], "cpu": float(parts[2]), "memory": float(parts[3])})
            except:
                continue
    return {"status": "success", "data": procs}
```

- [ ] **Step 5: Update main.py**

```python
# backend/app/main.py (add after workflows router)
from app.api.monitoring import router as monitoring_router
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_monitoring_api.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/monitoring_service.py backend/app/api/monitoring.py backend/tests/test_monitoring_api.py
git commit -m "feat: add monitoring API for local and remote system status"
```

---

## Task 8: Execution Model and API

**Files:**
- Create: `backend/app/api/executions.py`
- Create: `backend/app/services/execution_engine.py` (basic version)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_executions_api.py`

- [ ] **Step 1: Write the failing test for executions API**

```python
# backend/tests/test_executions_api.py
import sys
sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.dependencies import get_db
import pytest

TEST_DB_URL = "sqlite:///./test_db.sqlite"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    # Create a workflow for testing
    client.post("/api/workflows", json={"name": "test-wf", "nodes": [], "edges": []})
    yield
    Base.metadata.drop_all(bind=test_engine)

def test_create_execution():
    """Test creating an execution"""
    response = client.post("/api/executions", json={"workflow_id": 1})
    assert response.status_code == 201
    data = response.json()
    assert data["workflow_id"] == 1
    assert data["status"] == "pending"

def test_get_execution():
    """Test getting an execution"""
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.get("/api/executions/1")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"

def test_list_executions():
    """Test listing executions"""
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.get("/api/executions")
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_stop_execution():
    """Test stopping an execution"""
    client.post("/api/executions", json={"workflow_id": 1})
    response = client.post("/api/executions/1/stop")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_executions_api.py -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: Create execution_engine.py (basic version)**

```python
# backend/app/services/execution_engine.py
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models.database import Execution, NodeExecution, Workflow, Server
from ..services.ssh_service import SSHService

class ExecutionEngine:
    """Workflow execution engine"""

    def __init__(self):
        self.ssh_service = SSHService()
        self.running_executions: Dict[int, asyncio.Task] = {}

    def create_execution(self, db: Session, workflow_id: int, trigger_type: str = "manual", triggered_by: Optional[str] = None) -> Execution:
        """Create a new execution record"""
        execution = Execution(
            workflow_id=workflow_id,
            status="pending",
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            created_at=datetime.utcnow()
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    def get_execution(self, db: Session, execution_id: int) -> Optional[Execution]:
        """Get execution by ID"""
        return db.query(Execution).filter(Execution.id == execution_id).first()

    def list_executions(self, db: Session) -> list:
        """List all executions"""
        return db.query(Execution).order_by(Execution.created_at.desc()).all()

    def stop_execution(self, db: Session, execution_id: int) -> bool:
        """Stop a running execution"""
        execution = self.get_execution(db, execution_id)
        if not execution:
            return False
        if execution.status == "running":
            execution.status = "stopped"
            execution.finished_at = datetime.utcnow()
            db.commit()
        return True

    async def execute_workflow(self, db: Session, execution_id: int) -> None:
        """Execute workflow nodes asynchronously"""
        execution = self.get_execution(db, execution_id)
        if not execution:
            return
        workflow = db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
        if not workflow:
            return

        execution.status = "running"
        execution.started_at = datetime.utcnow()
        db.commit()

        # Execute each node (basic sequential execution for now)
        for node in workflow.nodes or []:
            node_exec = NodeExecution(
                execution_id=execution_id,
                node_id=node.get("id"),
                node_type=node.get("type"),
                status="running",
                started_at=datetime.utcnow()
            )
            db.add(node_exec)
            db.commit()

            # Execute based on node type
            result = await self._execute_node(db, node, workflow.variables or {})

            node_exec.status = "success" if result.get("success") else "failed"
            node_exec.finished_at = datetime.utcnow()
            node_exec.output_data = result
            db.commit()

        execution.status = "completed"
        execution.finished_at = datetime.utcnow()
        db.commit()

    async def _execute_node(self, db: Session, node: dict, variables: dict) -> Dict[str, Any]:
        """Execute a single node"""
        node_type = node.get("type")
        config = node.get("config", {})

        if node_type == "shell":
            server_id = config.get("server_id")
            command = config.get("command", "")
            if server_id:
                server = db.query(Server).filter(Server.id == server_id).first()
                if server:
                    result = self.ssh_service.run_command(
                        host=server.host,
                        username=server.username,
                        password=server.password,
                        command=command,
                        port=server.port,
                        timeout=config.get("timeout", 30)
                    )
                    return {"success": result.exit_status == 0, "output": result.stdout, "error": result.stderr}
            return {"success": False, "error": "No server configured"}

        # Other node types will be implemented in later phases
        return {"success": True, "output": "Node executed"}
```

- [ ] **Step 4: Create executions.py API router**

```python
# backend/app/api/executions.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from ..dependencies import get_db
from ..schemas.execution import ExecutionCreate, ExecutionResponse
from ..services.execution_engine import ExecutionEngine

router = APIRouter()
engine = ExecutionEngine()

@router.get("", response_model=List[ExecutionResponse])
def list_executions(db: Session = Depends(get_db)):
    """List all executions"""
    return engine.list_executions(db)

@router.post("", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
def create_execution(execution: ExecutionCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Create and start a new execution"""
    new_execution = engine.create_execution(
        db,
        workflow_id=execution.workflow_id,
        trigger_type=execution.trigger_type,
        triggered_by=execution.triggered_by
    )
    # Start execution in background
    background_tasks.add_task(engine.execute_workflow, db, new_execution.id)
    return new_execution

@router.get("/{execution_id}", response_model=ExecutionResponse)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    """Get execution by ID"""
    execution = engine.get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution

@router.post("/{execution_id}/stop")
def stop_execution(execution_id: int, db: Session = Depends(get_db)):
    """Stop a running execution"""
    success = engine.stop_execution(db, execution_id)
    if not success:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"status": "success", "message": "Execution stopped"}
```

- [ ] **Step 5: Update main.py**

```python
# backend/app/main.py (add after monitoring router)
from app.api.executions import router as executions_router
app.include_router(executions_router, prefix="/api/executions", tags=["executions"])
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_executions_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/execution_engine.py backend/app/api/executions.py backend/tests/test_executions_api.py
git commit -m "feat: add execution API with background workflow execution"
```

---

## Task 9: Database Initialization and Migration

**Files:**
- Create: `backend/app/models/setup.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_db_setup.py`

- [ ] **Step 1: Write the failing test for database initialization**

```python
# backend/tests/test_db_setup.py
import sys
sys.path.insert(0, 'backend')
import os
from pathlib import Path

def test_data_directory_created():
    """Test that data directory exists"""
    from app.config import DATABASE_PATH
    assert DATABASE_PATH.parent.exists()

def test_database_tables_created():
    """Test that all tables are created"""
    from sqlalchemy import create_engine, inspect
    from app.config import DATABASE_PATH
    from app.models.database import Base

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    assert "servers" in tables
    assert "workflows" in tables
    assert "executions" in tables
    assert "node_executions" in tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_db_setup.py -v`
Expected: FAIL with "tables not found"

- [ ] **Step 3: Create setup.py for database initialization**

```python
# backend/app/models/setup.py
from sqlalchemy import create_engine
from .database import Base
from ..config import DATABASE_PATH

def init_db():
    """Initialize database with all tables"""
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(bind=engine)
    return engine
```

- [ ] **Step 4: Update main.py to call init_db on startup**

```python
# backend/app/main.py (add after imports, before app definition)
from app.models.setup import init_db
init_db()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_db_setup.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/setup.py backend/tests/test_db_setup.py
git commit -m "feat: add database initialization on app startup"
```

---

## Task 10: Run Full Backend Tests

**Files:**
- All previous files

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Start backend server manually to verify**

Run: `cd backend && uvicorn app.main:app --reload --port 8000`

Verify: Open http://localhost:8000/docs to see Swagger UI with all API endpoints

- [ ] **Step 3: Final commit for Phase 1 completion**

```bash
git add -A
git commit -m "feat: complete Phase 1 backend refactoring - FastAPI with servers, workflows, executions, monitoring APIs"
```

---

## Summary

Phase 1 delivers a working FastAPI backend with:
- 10 tasks completed with TDD approach
- 4 API routers: servers, workflows, executions, monitoring
- SQLAlchemy models with proper relationships
- Pydantic schemas for validation
- SSH service for remote execution
- Basic execution engine for workflow nodes
- ~35 tests passing

**Next Phase (2):** Vue 3 frontend with workflow editor