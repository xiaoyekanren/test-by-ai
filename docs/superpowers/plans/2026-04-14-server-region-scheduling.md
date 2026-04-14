# Server Region 与空闲节点调度 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为服务器增加 `Region` 属性和"节点繁忙"状态展示，实现工作流执行时按区域随机选择空闲服务器。

**Architecture:** 后端增加 `region` 字段和 `is_busy` 计算字段，执行引擎新增服务器解析逻辑按区域调度。前端在服务器管理页面和工作流节点配置面板增加 Region 下拉框。

**Tech Stack:** Python FastAPI/SQLAlchemy (backend), Vue 3/Element Plus (frontend), SQLite (database)

---

## File Structure

**Backend:**
- Modify: `backend/app/models/database.py:9-23` - Server model 增加 `region` 字段
- Modify: `backend/app/schemas/server.py` - ServerBase/ServerCreate/ServerUpdate/ServerResponse 增加 `region` 字段
- Modify: `backend/app/api/servers.py:13-17` - list_servers 返回 `is_busy` 计算字段
- Modify: `backend/app/services/execution_engine.py:1105-1115` - `_resolve_server`/`_require_server` 增加区域调度逻辑
- Modify: `backend/app/services/execution_engine.py:175-211` - `_execute_node` 增加首节点服务器选择逻辑
- Create: `backend/tests/test_server_region.py` - Region 和调度测试

**Frontend:**
- Modify: `frontend/src/types/index.ts:362-414` - Server/ServerCreate/ServerUpdate/ServerExecuteResult 增加 `region` 和 `is_busy` 字段
- Modify: `frontend/src/views/ServersView.vue` - 服务器列表增加 Region 列和繁忙状态列，新增/编辑弹窗增加 Region 下拉框
- Modify: `frontend/src/components/workflow/NodeConfigPanel.vue` - 节点配置面板增加 Region 下拉框

**Documentation:**
- Create: `docs/design/server-region-scheduling.md` - 设计文档

---

## Task 1: Backend Server Model 增加 Region 字段

**Files:**
- Modify: `backend/app/models/database.py`
- Modify: `backend/app/models/setup.py`

- [ ] **Step 1: Write the failing test for region field**

```python
# backend/tests/test_server_region.py
import sys
sys.path.insert(0, 'backend')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, Server

def test_server_region_field():
    """Test Server model has region field with default value"""
    server = Server(
        name="test-region-server",
        host="192.168.1.1",
        port=22,
        username="admin",
        password="secret"
    )
    # 默认值应为 私有云
    assert server.region == "私有云"
    
    server2 = Server(
        name="test-region-server-2",
        host="192.168.1.2",
        port=22,
        username="admin",
        password="secret",
        region="公司"
    )
    assert server2.region == "公司"

def test_server_region_valid_values():
    """Test Server model accepts valid region values"""
    valid_regions = ["私有云", "公司-上层", "公司", "Fit楼", "公有云", "异构"]
    for region in valid_regions:
        server = Server(
            name=f"server-{region}",
            host="192.168.1.1",
            port=22,
            username="admin",
            password="secret",
            region=region
        )
        assert server.region == region
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_server_region.py::test_server_region_field -v`
Expected: FAIL with "Server has no attribute 'region'"

- [ ] **Step 3: Write Server model region field**

```python
# backend/app/models/database.py
# 在 Server 类的 __tablename__ = "servers" 下面增加 region 字段
# 找到 status 字段后，在其下方添加:

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
    region = Column(String(20), default="私有云")  # 新增: 区域字段
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_server_region.py::test_server_region_field -v`
Expected: PASS

- [ ] **Step 5: Write database migration logic for existing SQLite**

```python
# backend/app/models/setup.py
# 添加检测和迁移逻辑

def migrate_add_region_column(engine):
    """Add region column to existing servers table if missing"""
    import sqlite3
    db_path = str(engine.url).replace("sqlite:///", "")
    if not db_path:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if region column exists
    cursor.execute("PRAGMA table_info(servers)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "region" not in columns:
        cursor.execute("ALTER TABLE servers ADD COLUMN region VARCHAR(20) DEFAULT '私有云'")
        conn.commit()
    
    conn.close()
```

并在 `init_db()` 函数中调用:
```python
def init_db():
    engine = create_engine(config.DATABASE_URL)
    Base.metadata.create_all(engine)
    migrate_add_region_column(engine)  # 新增
    return engine
```

- [ ] **Step 6: Run all model tests to verify no regression**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/database.py backend/app/models/setup.py backend/tests/test_server_region.py
git commit -m "$(cat <<'EOF'
feat: add region field to Server model

- Add region column to Server model with default value '私有云'
- Add migration logic for existing SQLite databases
- Add tests for region field validation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Backend Server Schema 增加 Region 字段

**Files:**
- Modify: `backend/app/schemas/server.py`

- [ ] **Step 1: Write the failing test for schema region**

```python
# backend/tests/test_server_region.py 增加:

def test_server_create_schema_region():
    """Test ServerCreate schema accepts region field"""
    from app.schemas.server import ServerCreate, ServerUpdate, ServerResponse
    
    # ServerCreate with default region
    create1 = ServerCreate(name="test", host="192.168.1.1")
    assert create1.region == "私有云"
    
    # ServerCreate with explicit region
    create2 = ServerCreate(name="test2", host="192.168.1.2", region="公司")
    assert create2.region == "公司"
    
    # ServerUpdate with region
    update = ServerUpdate(region="公有云")
    assert update.region == "公有云"
    
    # ServerResponse with region
    response_data = {
        "id": 1,
        "name": "test",
        "host": "192.168.1.1",
        "port": 22,
        "username": "admin",
        "description": None,
        "tags": None,
        "status": "offline",
        "region": "异构",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00"
    }
    response = ServerResponse.model_validate(response_data)
    assert response.region == "异构"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_server_region.py::test_server_create_schema_region -v`
Expected: FAIL with "field required" or "extra field not permitted"

- [ ] **Step 3: Write schema region field**

```python
# backend/app/schemas/server.py
# 在 ServerBase 类增加 region 字段
# 在文件开头定义 REGION_OPTIONS 常量

from pydantic import BaseModel, Field, ConfigDict, SecretStr, field_validator
from typing import Optional, Literal
from datetime import datetime

REGION_OPTIONS = Literal["私有云", "公司-上层", "公司", "Fit楼", "公有云", "异构"]

class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=50)
    password: Optional[SecretStr] = Field(default=None, max_length=100)
    description: Optional[str] = None
    tags: Optional[str] = Field(default=None, max_length=200)
    region: REGION_OPTIONS = Field(default="私有云")

class ServerCreate(ServerBase):
    pass

class ServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = Field(None, min_length=1, max_length=100)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    region: Optional[REGION_OPTIONS] = None

class ServerResponse(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    tags: Optional[str] = Field(default=None, max_length=200)
    status: str = "offline"
    region: REGION_OPTIONS = "私有云"  # 新增
    is_busy: bool = False  # 新增: 计算字段
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_server_region.py::test_server_create_schema_region -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/server.py backend/tests/test_server_region.py
git commit -m "$(cat <<'EOF'
feat: add region field to Server schemas

- Add region field to ServerBase, ServerCreate, ServerUpdate, ServerResponse
- Add is_busy computed field to ServerResponse
- Use Literal type for valid region values

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Backend Server API 增加 is_busy 计算字段

**Files:**
- Modify: `backend/app/api/servers.py`

- [ ] **Step 1: Write the failing test for is_busy**

```python
# backend/tests/test_server_region.py 增加:

def test_server_list_is_busy():
    """Test server list returns is_busy computed field"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.database import Base, Server, Workflow, Execution, NodeExecution
    from app.api.servers import list_servers
    from datetime import datetime
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Create server
    server = Server(name="busy-server", host="192.168.1.1", port=22, username="admin", password="secret")
    db.add(server)
    db.commit()
    db.refresh(server)
    
    # Create workflow
    workflow = Workflow(name="test-wf")
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    # Create running execution
    execution = Execution(
        workflow_id=workflow.id,
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    # Create running node_execution linked to server
    node_exec = NodeExecution(
        execution_id=execution.id,
        node_id="node1",
        node_type="shell",
        status="running",
        started_at=datetime.utcnow(),
        input_data={"server_id": server.id}
    )
    db.add(node_exec)
    db.commit()
    
    # Mock request to get server list
    servers_list = list_servers(db)
    
    # Server should be marked as busy
    assert len(servers_list) == 1
    assert servers_list[0].is_busy == True
    
    # Mark node_execution as completed
    node_exec.status = "success"
    db.commit()
    
    servers_list2 = list_servers(db)
    assert servers_list2[0].is_busy == False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_server_region.py::test_server_list_is_busy -v`
Expected: FAIL with "is_busy not returned" or similar

- [ ] **Step 3: Write is_busy computation in API**

```python
# backend/app/api/servers.py
# 修改 list_servers 函数增加 is_busy 计算

from sqlalchemy.orm import Session
from typing import List, Set
from ..schemas.server import ServerResponse

def _compute_busy_servers(db: Session) -> Set[int]:
    """Compute set of server_ids that are currently busy"""
    from ..models.database import Execution, NodeExecution
    
    # Find all running executions
    running_executions = db.query(Execution.id).filter(
        Execution.status == "running"
    ).all()
    running_exec_ids = [e.id for e in running_executions]
    
    if not running_exec_ids:
        return set()
    
    # Find all running node_executions in these executions
    running_node_execs = db.query(NodeExecution).filter(
        NodeExecution.execution_id.in_(running_exec_ids),
        NodeExecution.status == "running"
    ).all()
    
    # Extract server_ids from input_data
    busy_server_ids = set()
    for ne in running_node_execs:
        if ne.input_data and isinstance(ne.input_data, dict):
            server_id = ne.input_data.get("server_id")
            if server_id is not None:
                busy_server_ids.add(int(server_id))
    
    return busy_server_ids


@router.get("", response_model=List[ServerResponse])
def list_servers(db: Session = Depends(get_db)):
    """List all servers with is_busy computed field"""
    servers = db.query(Server).all()
    busy_server_ids = _compute_busy_servers(db)
    
    # Convert to response with is_busy
    responses = []
    for server in servers:
        server_dict = {
            "id": server.id,
            "name": server.name,
            "host": server.host,
            "port": server.port,
            "username": server.username,
            "description": server.description,
            "tags": server.tags,
            "status": server.status,
            "region": server.region or "私有云",
            "is_busy": server.id in busy_server_ids,
            "created_at": server.created_at,
            "updated_at": server.updated_at
        }
        responses.append(ServerResponse.model_validate(server_dict))
    
    return responses
```

- [ ] **Step 4: Update create_server and update_server to handle region**

```python
# backend/app/api/servers.py
# 在 create_server 函数中增加 region 参数

@router.post("", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
def create_server(server: ServerCreate, db: Session = Depends(get_db)):
    """Create a new server"""
    # Check if server with same name already exists
    existing = db.query(Server).filter(Server.name == server.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Server with name '{server.name}' already exists"
        )

    # Create server instance
    db_server = Server(
        name=server.name,
        host=server.host,
        port=server.port,
        username=server.username,
        password=server.password.get_secret_value() if server.password else None,
        description=server.description,
        tags=server.tags,
        region=server.region  # 新增
    )

    db.add(db_server)
    db.commit()
    db.refresh(db_server)

    # 返回带 is_busy 的响应
    busy_ids = _compute_busy_servers(db)
    server_dict = {
        "id": db_server.id,
        "name": db_server.name,
        "host": db_server.host,
        "port": db_server.port,
        "username": db_server.username,
        "description": db_server.description,
        "tags": db_server.tags,
        "status": db_server.status,
        "region": db_server.region or "私有云",
        "is_busy": db_server.id in busy_ids,
        "created_at": db_server.created_at,
        "updated_at": db_server.updated_at
    }
    return ServerResponse.model_validate(server_dict)


@router.put("/{server_id}", response_model=ServerResponse)
def update_server(server_id: int, server_update: ServerUpdate, db: Session = Depends(get_db)):
    """Update a server"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server with id {server_id} not found"
        )

    # Check for name uniqueness if name is being updated
    if server_update.name and server_update.name != server.name:
        existing = db.query(Server).filter(Server.name == server_update.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server with name '{server_update.name}' already exists"
            )

    # Update fields
    update_data = server_update.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"] is not None:
        update_data["password"] = update_data["password"].get_secret_value()

    for field, value in update_data.items():
        setattr(server, field, value)

    db.commit()
    db.refresh(server)

    # 返回带 is_busy 的响应
    busy_ids = _compute_busy_servers(db)
    server_dict = {
        "id": server.id,
        "name": server.name,
        "host": server.host,
        "port": server.port,
        "username": server.username,
        "description": server.description,
        "tags": server.tags,
        "status": server.status,
        "region": server.region or "私有云",
        "is_busy": server.id in busy_ids,
        "created_at": server.created_at,
        "updated_at": server.updated_at
    }
    return ServerResponse.model_validate(server_dict)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_server_region.py::test_server_list_is_busy -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/servers.py backend/tests/test_server_region.py
git commit -m "$(cat <<'EOF'
feat: add is_busy computed field to server list API

- Compute is_busy based on running node_executions linked to server
- Update create_server and update_server to return is_busy
- Add region handling in server CRUD operations

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Backend Execution Engine 增加区域调度逻辑

**Files:**
- Modify: `backend/app/services/execution_engine.py`

- [ ] **Step 1: Write the failing test for region scheduling**

```python
# backend/tests/test_server_region.py 增加:

def test_resolve_server_by_region():
    """Test execution engine resolves server by region"""
    import random
    random.seed(42)
    
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.database import Base, Server, Workflow, Execution
    from app.services.execution_engine import ExecutionEngine
    from datetime import datetime
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Create servers in different regions
    server1 = Server(name="server-private-1", host="192.168.1.1", port=22, username="admin", password="secret", region="私有云")
    server2 = Server(name="server-private-2", host="192.168.1.2", port=22, username="admin", password="secret", region="私有云")
    server3 = Server(name="server-company", host="192.168.2.1", port=22, username="admin", password="secret", region="公司")
    db.add_all([server1, server2, server3])
    db.commit()
    
    engine_svc = ExecutionEngine(db)
    
    # Test: resolve server without server_id and region -> default to 私有云
    config = {"command": "echo test", "timeout": 10}
    context = {}
    resolved = engine_svc._resolve_server_with_region(config, context)
    assert resolved is not None
    assert resolved.region == "私有云"
    
    # Test: resolve server with explicit region
    config2 = {"command": "echo test", "timeout": 10, "region": "公司"}
    context2 = {}
    resolved2 = engine_svc._resolve_server_with_region(config2, context2)
    assert resolved2 is not None
    assert resolved2.region == "公司"
    assert resolved2.id == server3.id
    
    # Test: resolve server inherits from context
    config3 = {"command": "echo test", "timeout": 10}
    context3 = {"server_id": server1.id}
    resolved3 = engine_svc._resolve_server_with_region(config3, context3)
    assert resolved3 is not None
    assert resolved3.id == server1.id

def test_resolve_server_no_idle():
    """Test execution engine fails when no idle server in region"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.database import Base, Server, Workflow, Execution, NodeExecution
    from app.services.execution_engine import ExecutionEngine
    from datetime import datetime
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Create one server in 私有云
    server = Server(name="busy-server", host="192.168.1.1", port=22, username="admin", password="secret", region="私有云")
    db.add(server)
    db.commit()
    db.refresh(server)
    
    # Create workflow and running execution
    workflow = Workflow(name="test-wf")
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    execution = Execution(workflow_id=workflow.id, status="running", started_at=datetime.utcnow())
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    # Mark server as busy via running node_execution
    node_exec = NodeExecution(
        execution_id=execution.id,
        node_id="node1",
        node_type="shell",
        status="running",
        started_at=datetime.utcnow(),
        input_data={"server_id": server.id}
    )
    db.add(node_exec)
    db.commit()
    
    engine_svc = ExecutionEngine(db)
    
    # Test: no idle server in 私有云 -> returns None
    config = {"command": "echo test", "timeout": 10}
    context = {}
    resolved = engine_svc._resolve_server_with_region(config, context)
    assert resolved is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_server_region.py::test_resolve_server_by_region -v`
Expected: FAIL with "method not found" or similar

- [ ] **Step 3: Write server resolution with region logic**

```python
# backend/app/services/execution_engine.py
# 在 _resolve_server 方法后增加 _resolve_server_with_region 方法

import random

def _resolve_server_with_region(self, config: Dict[str, Any], context: Dict[str, Any]) -> Optional[Server]:
    """Resolve server with region-based scheduling logic
    
    Logic:
    1. If server_id is explicitly set in config or context, use that server
    2. If region is explicitly set in config, select random idle server from that region
    3. If neither, default to '私有云' region and select random idle server
    4. If no idle server in target region, return None (execution will fail)
    """
    # Step 1: Check explicit server_id
    server_id = config.get("server_id")
    if server_id in (None, ""):
        server_id = context.get("server_id")
    
    if server_id is not None and server_id != "":
        return self.db.query(Server).filter(Server.id == int(server_id)).first()
    
    # Step 2: Determine target region
    region = config.get("region")
    if region in (None, ""):
        region = context.get("region")
    if region in (None, ""):
        region = "私有云"  # Default region
    
    # Step 3: Find idle servers in target region
    busy_server_ids = self._compute_busy_server_ids()
    
    idle_servers = self.db.query(Server).filter(
        Server.region == region,
        Server.id.notin_(busy_server_ids) if busy_server_ids else True
    ).all()
    
    if not idle_servers:
        return None
    
    # Step 4: Random select
    return random.choice(idle_servers)


def _compute_busy_server_ids(self) -> List[int]:
    """Compute list of server_ids that are currently busy"""
    from app.models.database import Execution, NodeExecution
    
    running_executions = self.db.query(Execution.id).filter(
        Execution.status == "running"
    ).all()
    running_exec_ids = [e.id for e in running_executions]
    
    if not running_exec_ids:
        return []
    
    running_node_execs = self.db.query(NodeExecution).filter(
        NodeExecution.execution_id.in_(running_exec_ids),
        NodeExecution.status == "running"
    ).all()
    
    busy_ids = []
    for ne in running_node_execs:
        if ne.input_data and isinstance(ne.input_data, dict):
            server_id = ne.input_data.get("server_id")
            if server_id is not None:
                busy_ids.append(int(server_id))
    
    return busy_ids
```

- [ ] **Step 4: Update _require_server to use new logic**

```python
# backend/app/services/execution_engine.py
# 修改 _require_server 方法

def _require_server(self, config: Dict[str, Any], context: Dict[str, Any] = None) -> Server:
    """Require a server, using region-based scheduling if no explicit server_id"""
    if context is None:
        context = {}
    
    server = self._resolve_server_with_region(config, context)
    if not server:
        region = config.get("region") or context.get("region") or "私有云"
        raise ValueError(f"No idle server found in region {region}")
    return server
```

- [ ] **Step 5: Update _execute_node to pass context and update it**

```python
# backend/app/services/execution_engine.py
# 修改 execute_workflow 方法中的节点执行逻辑

def execute_workflow(self, execution_id: int) -> None:
    execution = self.get_execution(execution_id)
    if not execution:
        logger.error("Execution %s not found", execution_id)
        return

    workflow = self.db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
    if not workflow:
        logger.error("Workflow %s not found", execution.workflow_id)
        execution.status = "failed"
        execution.finished_at = datetime.utcnow()
        self.db.commit()
        return

    execution.status = "running"
    execution.started_at = datetime.utcnow()
    self.db.commit()

    nodes = workflow.nodes or []
    passed_count = 0
    failed_count = 0
    context: Dict[str, Any] = {}
    first_server_node_resolved = False  # 新增: 标记首节点是否已解析服务器

    try:
        for node in nodes:
            node_id = node.get("id")
            node_type = node.get("type", "shell")
            config = node.get("config", {}) or {}

            node_execution = NodeExecution(
                execution_id=execution_id,
                node_id=node_id,
                node_type=node_type,
                status="running",
                started_at=datetime.utcnow(),
                input_data=config
            )
            self.db.add(node_execution)
            self.db.commit()
            self.db.refresh(node_execution)

            try:
                # 新增: 对于需要服务器的节点，解析服务器并写入 input_data
                if self._node_requires_server(node_type):
                    resolved_server = self._resolve_server_with_region(config, context)
                    if resolved_server:
                        # 写入解析结果到 input_data
                        node_execution.input_data = {
                            **(config or {}),
                            "server_id": resolved_server.id,
                            "server_name": resolved_server.name,
                            "host": resolved_server.host,
                            "region": resolved_server.region
                        }
                        self.db.commit()
                        
                        # 更新 context 供后续节点继承
                        if not first_server_node_resolved:
                            context["server_id"] = resolved_server.id
                            context["host"] = resolved_server.host
                            context["region"] = resolved_server.region
                            first_server_node_resolved = True
                
                result = self._execute_node(node_type, config, context)
                node_execution.output_data = result
                exit_status = result.get("exit_status", -1)
                node_execution.status = "success" if exit_status == 0 else "failed"
                if exit_status != 0:
                    node_execution.error_message = (
                        result.get("error")
                        or result.get("stderr")
                        or "Unknown error"
                    )
                else:
                    context.update(self._build_context_updates(node_type, config, result))

                if node_execution.status == "success":
                    passed_count += 1
                else:
                    failed_count += 1
            except Exception as exc:
                logger.exception("Error executing node %s", node_id)
                node_execution.status = "failed"
                node_execution.error_message = str(exc)
                node_execution.output_data = {"exit_status": -1, "error": str(exc)}
                failed_count += 1

            node_execution.finished_at = datetime.utcnow()
            node_execution.duration = int(
                (node_execution.finished_at - node_execution.started_at).total_seconds()
            )
            self.db.commit()

            if node_execution.status != "success":
                break

        execution.finished_at = datetime.utcnow()
        execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
        execution.summary = {
            "total": len(nodes),
            "passed": passed_count,
            "failed": failed_count,
        }

        if failed_count == 0:
            execution.status = "completed"
            execution.result = "passed"
        else:
            execution.status = "failed"
            execution.result = "failed" if passed_count == 0 else "partial"

        self.db.commit()
    except Exception as exc:
        logger.exception("Error in execution %s", execution_id)
        execution.status = "failed"
        execution.finished_at = datetime.utcnow()
        if execution.started_at:
            execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
        execution.result = "failed"
        execution.summary = {"error": str(exc)}
        self.db.commit()


def _node_requires_server(self, node_type: str) -> bool:
    """Check if node type requires a server"""
    server_required_types = [
        "shell", "upload", "download", "config", "log_view",
        "iotdb_deploy", "iotdb_start", "iotdb_stop", "iotdb_cli", "iotdb_config"
    ]
    return node_type in server_required_types
```

- [ ] **Step 6: Update all _execute_* methods to use context**

```python
# backend/app/services/execution_engine.py
# 修改 _execute_shell_node 等方法，传入 context 参数

def _execute_shell_node(self, config: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    if context is None:
        context = {}
    command = str(config.get("command", "")).strip()
    if not command:
        return {"exit_status": -1, "stdout": "", "stderr": "", "error": "Command is required"}

    server = self._require_server(config, context)  # 传入 context
    timeout = int(config.get("timeout", 60))

    if server:
        result = self.ssh_service.run_command(
            host=server.host,
            username=server.username,
            password=server.password,
            command=command,
            port=server.port,
            timeout=timeout
        )
        return self._ssh_result_to_dict(result)

    # ... (rest unchanged)
```

同样更新其他需要服务器的方法: `_execute_upload_node`, `_execute_download_node`, `_execute_config_node`, `_execute_log_view_node`, `_execute_iotdb_deploy_node`, `_execute_iotdb_start_node`, `_execute_iotdb_cli_node`, `_execute_iotdb_stop_node`。

- [ ] **Step 7: Update _build_context_updates to include region**

```python
# backend/app/services/execution_engine.py
# 修改 _build_context_updates 方法增加 region

def _build_context_updates(
    self,
    node_type: str,
    config: Dict[str, Any],
    result: Dict[str, Any]
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    server_id = config.get("server_id")
    if server_id is not None:
        updates["server_id"] = server_id
        server = self.db.query(Server).filter(Server.id == int(server_id)).first()
        if server:
            updates["host"] = server.host
            updates["region"] = server.region or "私有云"  # 新增

    for key in [
        "node_role", "iotdb_home", "conf_path", "rpc_port", "wait_port",
        "remote_package_path", "backup_path", "cluster_name", "config_nodes", "data_nodes",
        "region"  # 新增
    ]:
        if key in result and result[key] not in (None, ""):
            updates[key] = result[key]

    if node_type == "iotdb_cli" and result.get("executed_sqls"):
        updates["executed_sqls"] = result["executed_sqls"]
    return updates
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_server_region.py::test_resolve_server_by_region tests/test_server_region.py::test_resolve_server_no_idle -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/execution_engine.py backend/tests/test_server_region.py
git commit -m "$(cat <<'EOF'
feat: add region-based server scheduling in execution engine

- Add _resolve_server_with_region for intelligent server selection
- Add _compute_busy_server_ids to track busy servers
- Add _node_requires_server to identify server-dependent nodes
- Update execute_workflow to resolve server on first node
- Update context inheritance to include server_id/host/region
- Fail execution when no idle server in target region

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Frontend Types 增加 Region 和 is_busy

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Write frontend type updates**

```typescript
// frontend/src/types/index.ts
// 更新 Server 相关类型

// 增加 REGION_OPTIONS 常量
export const REGION_OPTIONS: string[] = ["私有云", "公司-上层", "公司", "Fit楼", "公有云", "异构"]

export interface Server {
  id: number
  name: string
  host: string
  port: number
  username: string | null
  description: string | null
  tags: string | null
  status: string
  region: string  // 新增
  is_busy: boolean  // 新增
  created_at: string
  updated_at: string
}

export interface ServerCreate {
  name: string
  host: string
  port?: number
  username?: string | null
  password?: string | null
  description?: string | null
  tags?: string | null
  region?: string  // 新增
}

export interface ServerUpdate {
  name?: string
  host?: string
  port?: number
  username?: string | null
  password?: string | null
  description?: string | null
  tags?: string | null
  region?: string  // 新增
}

export interface ServerTestResult {
  success: boolean
  message: string
  server_id: number
  server_name: string
  ssh_port?: number
}

export interface ServerExecuteResult {
  server_id: number
  server_name: string
  command: string
  exit_status: number | null
  stdout: string
  stderr: string
  error: string | null
  ssh_port: number
}

// 更新 NodeDefinition config 类型增加 region
// 在 NODE_CONFIGS 中为需要服务器的节点增加 region 默认配置
```

- [ ] **Step 2: Update NODE_CONFIGS with region field**

```typescript
// frontend/src/types/index.ts
// 在 shell node 的 defaultConfig 中增加 region

shell: {
  type: 'shell',
  label: 'Shell',
  category: 'basic',
  icon: 'Monitor',
  color: '#409EFF',
  description: 'Execute shell command',
  defaultConfig: { command: '', server_id: null, region: null, timeout: 300, retry: 0 },
  inputs: 1,
  outputs: 1
},
```

同样为其他需要服务器的节点增加 region: upload, download, config, log_view, iotdb_deploy, iotdb_start, iotdb_stop, iotdb_cli, iotdb_config。

- [ ] **Step 3: Run frontend type check**

Run: `cd frontend && npm run typecheck`
Expected: PASS (with possible errors in views that need updating)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "$(cat <<'EOF'
feat: add region and is_busy fields to frontend Server types

- Add region field to Server, ServerCreate, ServerUpdate interfaces
- Add is_busy computed field to Server interface
- Add REGION_OPTIONS constant for dropdown
- Add region to defaultConfig for server-dependent nodes

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Frontend ServersView 增加 Region 列和繁忙状态

**Files:**
- Modify: `frontend/src/views/ServersView.vue`

- [ ] **Step 1: Update ServersView table columns**

在 `ServersView.vue` 的 ElTable 中增加 Region 列和繁忙状态列:

```vue
<!-- frontend/src/views/ServersView.vue -->
<!-- 在 ElTableColumn prop="status" 后增加 Region 列 -->

<ElTableColumn prop="region" label="Region" width="100" align="center">
  <template #default="{ row }">
    <ElTag size="small" type="info">{{ row.region || '私有云' }}</ElTag>
  </template>
</ElTableColumn>

<!-- 在 Tags 列后增加繁忙状态列 -->
<ElTableColumn prop="is_busy" label="Busy" width="80" align="center">
  <template #default="{ row }">
    <span class="busy-tag" :class="row.is_busy ? 'busy' : 'idle'">
      {{ row.is_busy ? '繁忙' : '空闲' }}
    </span>
  </template>
</ElTableColumn>
```

- [ ] **Step 2: Update form dialog with Region dropdown**

在新增/编辑服务器弹窗中增加 Region 下拉框:

```vue
<!-- frontend/src/views/ServersView.vue -->
<!-- 在 ElFormItem label="Tags" 后增加 Region 下拉框 -->

<ElFormItem label="Region" prop="region">
  <ElSelect v-model="formData.region" placeholder="Select region" size="small" style="width: 100%">
    <ElOption
      v-for="region in REGION_OPTIONS"
      :key="region"
      :label="region"
      :value="region"
    />
  </ElSelect>
</ElFormItem>
```

- [ ] **Step 3: Update formData and form initialization**

```typescript
// frontend/src/views/ServersView.vue
// 更新 formData 增加 region 字段

import { REGION_OPTIONS } from '@/types'

const formData = reactive<ServerCreate & { password?: string }>({
  name: '',
  host: '',
  port: 22,
  username: '',
  password: '',
  description: '',
  tags: '',
  region: '私有云'  // 新增，默认值
})

// 更新 resetForm
function resetForm() {
  Object.assign(formData, {
    name: '',
    host: '',
    port: 22,
    username: '',
    password: '',
    description: '',
    tags: '',
    region: '私有云'  // 新增
  })
  formRef.value?.clearValidate()
}

// 更新 openEditDialog
function openEditDialog(server: Server) {
  dialogMode.value = 'edit'
  currentServerId.value = server.id
  Object.assign(formData, {
    name: server.name,
    host: server.host,
    port: server.port,
    username: server.username || '',
    password: '',
    description: server.description || '',
    tags: server.tags || '',
    region: server.region || '私有云'  // 新增
  })
  dialogVisible.value = true
}

// 更新 submitForm
async function submitForm() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      if (dialogMode.value === 'create') {
        const newServer = await serversStore.addServer({
          name: formData.name,
          host: formData.host,
          port: formData.port,
          username: formData.username || null,
          password: formData.password || null,
          description: formData.description || null,
          tags: formData.tags || null,
          region: formData.region  // 新增
        })
        dialogVisible.value = false
        testConnection(newServer)
      } else if (currentServerId.value) {
        const updateData: ServerUpdate = {
          name: formData.name,
          host: formData.host,
          port: formData.port,
          username: formData.username || null,
          description: formData.description || null,
          tags: formData.tags || null,
          region: formData.region  // 新增
        }
        if (formData.password) {
          updateData.password = formData.password
        }
        await serversStore.updateServer(currentServerId.value, updateData)
        ElMessage.success('Server updated successfully')
      }
      dialogVisible.value = false
    } catch (error) {
      ElMessage.error(dialogMode.value === 'create' ? 'Failed to create server' : 'Failed to update server')
    }
  })
}
```

- [ ] **Step 4: Update grouped view table**

同样在分组视图的 ElTable 中增加 Region 列和繁忙状态列。

- [ ] **Step 5: Add CSS for busy status**

```css
/* frontend/src/views/ServersView.vue */
/* 在 style scoped 中增加繁忙状态样式 */

.busy-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 18px;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 6px;
}

.busy-tag.busy {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.busy-tag.idle {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}
```

- [ ] **Step 6: Run frontend build**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/ServersView.vue
git commit -m "$(cat <<'EOF'
feat: add Region column and busy status to ServersView

- Add Region column with tag display in server table
- Add busy/idle status column with visual indicators
- Add Region dropdown in create/edit server dialog
- Update form data and handlers to include region
- Add CSS styles for busy status display

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Frontend NodeConfigPanel 增加 Region 下拉框

**Files:**
- Modify: `frontend/src/components/workflow/NodeConfigPanel.vue`

- [ ] **Step 1: Add region field type definition**

```typescript
// frontend/src/components/workflow/NodeConfigPanel.vue
// 在 FieldDefinition 接口中增加 region 类型

interface FieldDefinition {
  field: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'select' | 'checkbox' | 'json' | 'keyValue' | 'server' | 'region'  // 新增 region
  options?: Array<{ value: string | number | boolean; label: string }>
  placeholder?: string
  min?: number
  max?: number
}

// 增加 REGION_OPTIONS 常量
import { REGION_OPTIONS } from '@/types'
```

- [ ] **Step 2: Add region field to node definitions**

```typescript
// frontend/src/components/workflow/NodeConfigPanel.vue
// 在 getFieldDefinitions 中为需要服务器的节点增加 region 字段

// 例如 shell 节点:
shell: [
  { field: 'command', label: 'Command', type: 'textarea', placeholder: 'Enter shell command...' },
  { field: 'server_id', label: 'Server', type: 'server' },
  { field: 'region', label: 'Region', type: 'region' },  // 新增
  { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 },
  { field: 'retry', label: 'Retry Count', type: 'number', min: 0, max: 10 }
],
```

同样为其他需要服务器的节点增加 region 字段: upload, download, config, log_view, iotdb_deploy, iotdb_start, iotdb_stop, iotdb_cli, iotdb_config。

- [ ] **Step 3: Add region template in Vue template**

```vue
<!-- frontend/src/components/workflow/NodeConfigPanel.vue -->
<!-- 在 template 中增加 region 类型处理 -->

<template v-else-if="field.type === 'region'">
  <ElSelect
    :model-value="(getConfigValue(field.field) as string | null | undefined)"
    placeholder="Select region (default: 私有云)"
    clearable
    size="small"
    style="width: 100%"
    @update:model-value="updateConfig(field.field, $event)"
  >
    <ElOption
      v-for="region in REGION_OPTIONS"
      :key="region"
      :label="region"
      :value="region"
    />
  </ElSelect>
</template>
```

- [ ] **Step 4: Update getFieldLayoutClass**

```typescript
// frontend/src/components/workflow/NodeConfigPanel.vue
// 在 getFieldLayoutClass 中增加 region 类型处理

const getFieldLayoutClass = (field: FieldDefinition) => {
  if (['textarea', 'json', 'keyValue'].includes(field.type)) return 'field-full'
  if (field.type === 'number') return 'field-compact field-inline'
  if (field.type === 'checkbox') return 'field-compact field-inline'
  if (['host', 'username', 'password', 'node_role', 'package_type', 'wait_strategy', 'sql_dialect', 'format', 'type', 'region'].includes(field.field)) return 'field-medium field-inline'  // 增加 region
  if (['local_path', 'remote_path', 'file_path', 'iotdb_home', 'install_dir', 'artifact_local_path', 'remote_package_path'].includes(field.field)) return 'field-wide field-inline'
  if (field.type === 'server' || field.type === 'region') return 'field-wide field-inline'  // 增加 region
  return 'field-wide field-inline'
}
```

- [ ] **Step 5: Update getFieldSection**

```typescript
// frontend/src/components/workflow/NodeConfigPanel.vue
// 在 getFieldSection 中增加 region 字段分类

const getFieldSection = (field: FieldDefinition) => {
  if (['server_id', 'host', 'username', 'password', 'region'].includes(field.field)) return 'connection'  // 增加 region
  // ... 其余不变
}
```

- [ ] **Step 6: Run frontend build**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/workflow/NodeConfigPanel.vue
git commit -m "$(cat <<'EOF'
feat: add Region dropdown to workflow node config panel

- Add 'region' field type to FieldDefinition
- Add region field to server-dependent node configurations
- Add region select template with REGION_OPTIONS
- Update layout and section classification for region field

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: 设计文档更新

**Files:**
- Create: `docs/design/server-region-scheduling.md`

- [ ] **Step 1: Write design document**

```markdown
# 服务器区域调度设计文档

## 背景

原有系统中，工作流节点需要指定具体 server_id 执行任务。当没有指定 server_id 时，节点执行会失败。本设计增加区域（Region）属性，允许系统自动从指定区域随机选择空闲服务器执行任务。

## 功能需求

1. 服务器增加 `region` 字段，标识服务器所属区域
2. 服务器列表展示 `is_busy` 状态，标识当前是否有运行中的工作流节点占用
3. 工作流节点可配置 `region`，系统自动从该区域选择空闲服务器
4. 未指定 server_id 和 region 时，默认从 `私有云` 区域选择

## 数据模型

### Server 模型变更

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| region | String(20) | 私有云 | 区域标识 |

### Region 允许值

- 私有云
- 公司-上层
- 公司
- Fit楼
- 公有云
- 异构

## 调度逻辑

### 执行引擎解析流程

1. 节点显式配置 `server_id` → 使用指定服务器
2. 节点显式配置 `region` → 从该区域随机选择空闲服务器
3. 节点未配置两者 → 默认 `私有云` 区域，随机选择空闲服务器
4. 指定区域无空闲服务器 → 执行失败，返回 `No idle server found in region {region}`

### 空闲判定

服务器被判定为"繁忙"需满足：
- 存在 `status='running'` 的执行
- 该执行中存在 `status='running'` 的节点执行
- 该节点执行的 `input_data.server_id` 匹配该服务器

### 上下文继承

首个需要服务器的节点解析成功后，解析结果写入执行上下文：
- `server_id`: 选中的服务器 ID
- `host`: 服务器主机地址
- `region`: 服务器区域

后续未显式指定 server_id 的节点继承上下文中的服务器信息。

## API 变更

### Server List Response

新增字段：
- `region`: 服务器区域
- `is_busy`: 是否繁忙（计算字段）

### Server Create/Update

新增参数：
- `region`: 可选，区域标识

## 前端变更

### ServersView

- 表格新增 Region 列（Tag 展示）
- 表格新增繁忙状态列（空闲/繁忙）
- 新增/编辑弹窗新增 Region 下拉框

### NodeConfigPanel

- 需服务器的节点配置新增 Region 下拉框
- Region 选择不影响显式 Server 选择

## 测试策略

1. Region 字段测试：创建、更新、列表服务器时 region 正确处理
2. 繁忙状态测试：构造运行中执行和节点执行，验证 is_busy 计算
3. 调度测试：无 server_id/region 时默认选择；有 region 时区域限制；无空闲时失败
4. 上下文继承测试：后续节点正确继承首节点服务器信息

## 实现日期

2026-04-14
```

- [ ] **Step 2: Commit**

```bash
git add docs/design/server-region-scheduling.md
git commit -m "$(cat <<'EOF'
docs: add server region scheduling design document

- Document region field and scheduling logic
- Document is_busy computation rules
- Document context inheritance mechanism
- Document API and frontend changes

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: 运行完整测试

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 3: Run frontend typecheck**

Run: `cd frontend && npm run typecheck`
Expected: PASS

---

## Self-Review Checklist

1. **Spec coverage**: 
   - Region 字段: Task 1, 2, 3 ✓
   - is_busy 计算: Task 3 ✓
   - 区域调度逻辑: Task 4 ✓
   - 前端展示: Task 6, 7 ✓
   - 设计文档: Task 8 ✓

2. **Placeholder scan**: No TBD, TODO, or incomplete code blocks ✓

3. **Type consistency**: 
   - Backend: `REGION_OPTIONS = Literal[...]` matches frontend `REGION_OPTIONS: string[]`
   - ServerResponse includes `is_busy: bool` matching frontend `is_busy: boolean`
   - All methods signature updated for context parameter ✓