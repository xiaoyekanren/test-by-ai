import sys
import threading
import time

sys.path.insert(0, "backend")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Execution, NodeExecution, Workflow
from app.services.execution_engine import ExecutionEngine


def make_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'dag.db'}",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session_factory


def create_workflow(session, nodes, edges):
    workflow = Workflow(name="dag-test", nodes=nodes, edges=edges)
    session.add(workflow)
    session.commit()
    session.refresh(workflow)

    execution = Execution(workflow_id=workflow.id, status="pending")
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def test_dag_join_waits_for_all_upstreams_and_runs_roots_in_parallel(tmp_path, monkeypatch):
    session_factory = make_engine(tmp_path)
    session = session_factory()
    execution = create_workflow(
        session,
        nodes=[
            {"id": "deploy-a", "type": "report", "config": {}},
            {"id": "deploy-b", "type": "report", "config": {}},
            {"id": "deploy-c", "type": "report", "config": {}},
            {"id": "cluster-check", "type": "summary", "config": {}},
        ],
        edges=[
            {"from": "deploy-a", "to": "cluster-check"},
            {"from": "deploy-b", "to": "cluster-check"},
            {"from": "deploy-c", "to": "cluster-check"},
        ],
    )

    lock = threading.Lock()
    starts = {}
    finishes = {}

    def fake_execute_node(self, node_type, config, context):
        node_id = config["_node_id"]
        with lock:
            starts[node_id] = time.monotonic()
        if node_id.startswith("deploy-"):
            time.sleep(0.15)
        with lock:
            finishes[node_id] = time.monotonic()
        return {"exit_status": 0}

    monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)

    started = time.monotonic()
    ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)
    elapsed = time.monotonic() - started

    session.expire_all()
    refreshed = session.query(Execution).filter(Execution.id == execution.id).first()
    node_statuses = {
        item.node_id: item.status
        for item in session.query(NodeExecution).filter(NodeExecution.execution_id == execution.id).all()
    }

    assert refreshed.status == "completed"
    assert node_statuses == {
        "deploy-a": "success",
        "deploy-b": "success",
        "deploy-c": "success",
        "cluster-check": "success",
    }
    assert starts["cluster-check"] >= finishes["deploy-a"]
    assert starts["cluster-check"] >= finishes["deploy-b"]
    assert starts["cluster-check"] >= finishes["deploy-c"]
    assert elapsed < 0.35
    session.close()


def test_dag_skips_join_when_any_upstream_fails(tmp_path, monkeypatch):
    session_factory = make_engine(tmp_path)
    session = session_factory()
    execution = create_workflow(
        session,
        nodes=[
            {"id": "start-a", "type": "report", "config": {}},
            {"id": "start-b", "type": "report", "config": {}},
            {"id": "cluster-check", "type": "summary", "config": {}},
        ],
        edges=[
            {"from": "start-a", "to": "cluster-check"},
            {"from": "start-b", "to": "cluster-check"},
        ],
    )

    executed_nodes = []
    lock = threading.Lock()

    def fake_execute_node(self, node_type, config, context):
        node_id = config["_node_id"]
        with lock:
            executed_nodes.append(node_id)
        if node_id == "start-a":
            return {"exit_status": 1, "error": "start failed"}
        return {"exit_status": 0}

    monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)

    ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

    session.expire_all()
    refreshed = session.query(Execution).filter(Execution.id == execution.id).first()
    node_statuses = {
        item.node_id: item.status
        for item in session.query(NodeExecution).filter(NodeExecution.execution_id == execution.id).all()
    }

    assert refreshed.status == "failed"
    assert refreshed.summary is not None
    assert refreshed.summary["total"] == 3
    assert refreshed.summary["passed"] == 1
    assert refreshed.summary["failed"] == 1
    assert refreshed.summary["skipped"] == 1

    workflow_state = refreshed.summary["workflow_state"]
    assert workflow_state["version"] == 1
    assert [node["id"] for node in workflow_state["nodes"]] == [
        "start-a",
        "start-b",
        "cluster-check",
    ]
    assert {
        node["id"]: node["status"]
        for node in workflow_state["nodes"]
    } == {
        "start-a": "failed",
        "start-b": "success",
        "cluster-check": "skipped",
    }
    assert node_statuses["start-a"] == "failed"
    assert node_statuses["start-b"] == "success"
    assert node_statuses["cluster-check"] == "skipped"
    assert "cluster-check" not in executed_nodes
    session.close()


def test_workflow_without_edges_keeps_legacy_node_order(tmp_path, monkeypatch):
    session_factory = make_engine(tmp_path)
    session = session_factory()
    execution = create_workflow(
        session,
        nodes=[
            {"id": "first", "type": "report", "config": {}},
            {"id": "second", "type": "report", "config": {}},
            {"id": "third", "type": "report", "config": {}},
        ],
        edges=[],
    )

    executed_nodes = []
    lock = threading.Lock()

    def fake_execute_node(self, node_type, config, context):
        with lock:
            executed_nodes.append(config["_node_id"])
        return {"exit_status": 0}

    monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)

    ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

    assert executed_nodes == ["first", "second", "third"]
    session.close()


def test_stop_request_prevents_downstream_scheduling(tmp_path, monkeypatch):
    session_factory = make_engine(tmp_path)
    session = session_factory()
    execution = create_workflow(
        session,
        nodes=[
            {"id": "start", "type": "report", "config": {}},
            {"id": "after", "type": "report", "config": {}},
        ],
        edges=[
            {"from": "start", "to": "after"},
        ],
    )

    executed_nodes = []
    lock = threading.Lock()

    def fake_execute_node(self, execution_id, node, context):
        node_id = node["id"]
        with lock:
            executed_nodes.append(node_id)
        if node_id == "start":
            stop_session = session_factory()
            try:
                ExecutionEngine(stop_session, session_factory=session_factory).stop_execution(execution_id)
            finally:
                stop_session.close()
        return {"status": "success", "context": {}}

    monkeypatch.setattr(ExecutionEngine, "_execute_workflow_node", fake_execute_node)

    ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

    session.expire_all()
    refreshed = session.query(Execution).filter(Execution.id == execution.id).first()
    node_statuses = {
        item.node_id: item.status
        for item in session.query(NodeExecution).filter(NodeExecution.execution_id == execution.id).all()
    }

    assert refreshed.status == "stopped"
    assert refreshed.summary["stopped_at"]
    assert executed_nodes == ["start"]
    assert node_statuses["after"] == "skipped"
    session.close()
