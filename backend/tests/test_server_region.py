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
        "is_busy": False,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00"
    }
    response = ServerResponse.model_validate(response_data)
    assert response.region == "异构"
    assert response.is_busy == False


def test_server_list_is_busy():
    """Test server list returns is_busy computed field"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.database import Base, Server, Workflow, Execution, NodeExecution
    from app.api.servers import list_servers, _compute_busy_servers
    from datetime import datetime

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create server
    server = Server(name="busy-server", host="192.168.1.1", port=22, username="admin", password="secret", region="私有云")
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

    # Test _compute_busy_servers helper
    busy_ids = _compute_busy_servers(db)
    assert server.id in busy_ids

    # Test server list response
    servers_list = list_servers(db)

    # Server should be marked as busy
    assert len(servers_list) == 1
    assert servers_list[0].is_busy == True

    # Mark node_execution as completed
    node_exec.status = "success"
    db.commit()

    servers_list2 = list_servers(db)
    assert servers_list2[0].is_busy == False


def test_create_server_returns_is_busy_false():
    """Test create_server returns is_busy=False for new server"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.database import Base
    from app.api.servers import create_server
    from app.schemas.server import ServerCreate

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create server via API
    server_create = ServerCreate(name="new-server", host="192.168.1.1", region="公司")
    result = create_server(server_create, db)

    assert result.is_busy == False
    assert result.region == "公司"


def test_get_server_returns_is_busy():
    """Test get_server returns is_busy computed field"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.database import Base, Server, Workflow, Execution, NodeExecution
    from app.api.servers import get_server
    from datetime import datetime

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create server
    server = Server(name="test-server", host="192.168.1.1", port=22, username="admin", password="secret")
    db.add(server)
    db.commit()
    db.refresh(server)

    # Get server without any running execution
    result = get_server(server.id, db)
    assert result.is_busy == False

    # Create workflow and running execution
    workflow = Workflow(name="test-wf")
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    execution = Execution(workflow_id=workflow.id, status="running", started_at=datetime.utcnow())
    db.add(execution)
    db.commit()
    db.refresh(execution)

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

    # Get server with running execution
    result2 = get_server(server.id, db)
    assert result2.is_busy == True