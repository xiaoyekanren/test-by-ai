import sys
import threading

sys.path.insert(0, "backend")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Execution, NodeExecution, Workflow
from app.services.execution_engine import ExecutionEngine


def make_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'control.db'}",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session_factory


def create_workflow(session, nodes, edges):
    workflow = Workflow(name="control-test", nodes=nodes, edges=edges)
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    execution = Execution(workflow_id=workflow.id, status="pending")
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def get_node_statuses(session, execution_id):
    return {
        item.node_id: item.status
        for item in session.query(NodeExecution)
        .filter(NodeExecution.execution_id == execution_id).all()
    }


class TestConditionNode:

    def test_condition_true_branch_executes_false_branch_skipped(self, tmp_path, monkeypatch):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        execution = create_workflow(
            session,
            nodes=[
                {"id": "cond", "type": "condition", "config": {"expression": "true"}},
                {"id": "then-task", "type": "report", "config": {}},
                {"id": "else-task", "type": "report", "config": {}},
            ],
            edges=[
                {"from": "cond", "to": "then-task", "label": "True"},
                {"from": "cond", "to": "else-task", "label": "False"},
            ],
        )

        def fake_execute_node(self, node_type, config, context):
            if node_type == "condition":
                return {"exit_status": 0, "branch": "true"}
            return {"exit_status": 0}

        monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)
        ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

        session.expire_all()
        statuses = get_node_statuses(session, execution.id)
        assert statuses["cond"] == "success"
        assert statuses["then-task"] == "success"
        assert statuses["else-task"] == "skipped"
        session.close()

    def test_condition_false_branch_executes_true_branch_skipped(self, tmp_path, monkeypatch):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        execution = create_workflow(
            session,
            nodes=[
                {"id": "cond", "type": "condition", "config": {"expression": "false"}},
                {"id": "then-task", "type": "report", "config": {}},
                {"id": "else-task", "type": "report", "config": {}},
            ],
            edges=[
                {"from": "cond", "to": "then-task", "label": "True"},
                {"from": "cond", "to": "else-task", "label": "False"},
            ],
        )

        def fake_execute_node(self, node_type, config, context):
            if node_type == "condition":
                return {"exit_status": 0, "branch": "false"}
            return {"exit_status": 0}

        monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)
        ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

        session.expire_all()
        statuses = get_node_statuses(session, execution.id)
        assert statuses["cond"] == "success"
        assert statuses["then-task"] == "skipped"
        assert statuses["else-task"] == "success"
        session.close()

    def test_condition_skipped_branch_cascades_to_descendants(self, tmp_path, monkeypatch):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        execution = create_workflow(
            session,
            nodes=[
                {"id": "cond", "type": "condition", "config": {}},
                {"id": "then-a", "type": "report", "config": {}},
                {"id": "then-b", "type": "report", "config": {}},
                {"id": "else-a", "type": "report", "config": {}},
            ],
            edges=[
                {"from": "cond", "to": "then-a", "label": "True"},
                {"from": "then-a", "to": "then-b"},
                {"from": "cond", "to": "else-a", "label": "False"},
            ],
        )

        def fake_execute_node(self, node_type, config, context):
            if node_type == "condition":
                return {"exit_status": 0, "branch": "false"}
            return {"exit_status": 0}

        monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)
        ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

        session.expire_all()
        statuses = get_node_statuses(session, execution.id)
        assert statuses["then-a"] == "skipped"
        assert statuses["then-b"] == "skipped"
        assert statuses["else-a"] == "success"
        session.close()


class TestLoopNode:

    def test_loop_executes_body_n_times(self, tmp_path, monkeypatch):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        execution = create_workflow(
            session,
            nodes=[
                {"id": "loop", "type": "loop", "config": {"loop_type": "for", "iterations": 3}},
                {"id": "body", "type": "report", "config": {}},
            ],
            edges=[
                {"from": "loop", "to": "body"},
            ],
        )

        lock = threading.Lock()
        executed = []

        def fake_execute_node(self, node_type, config, context):
            node_id = config["_node_id"]
            with lock:
                executed.append(node_id)
            if node_type == "loop":
                return {"exit_status": 0, "loop_type": "for", "loop_iterations": 3}
            return {"exit_status": 0}

        monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)
        ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

        body_runs = [n for n in executed if n == "body"]
        assert len(body_runs) == 3
        session.close()

    def test_loop_stops_on_body_failure(self, tmp_path, monkeypatch):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        execution = create_workflow(
            session,
            nodes=[
                {"id": "loop", "type": "loop", "config": {"loop_type": "for", "iterations": 5}},
                {"id": "body", "type": "report", "config": {}},
            ],
            edges=[
                {"from": "loop", "to": "body"},
            ],
        )

        lock = threading.Lock()
        call_count = [0]

        def fake_execute_node(self, node_type, config, context):
            node_id = config["_node_id"]
            if node_type == "loop":
                return {"exit_status": 0, "loop_type": "for", "loop_iterations": 5}
            with lock:
                call_count[0] += 1
            if call_count[0] == 2:
                return {"exit_status": 1, "error": "fail on 2nd iteration"}
            return {"exit_status": 0}

        monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)
        ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

        assert call_count[0] == 2
        session.close()

    def test_loop_single_iteration(self, tmp_path, monkeypatch):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        execution = create_workflow(
            session,
            nodes=[
                {"id": "loop", "type": "loop", "config": {"loop_type": "for", "iterations": 1}},
                {"id": "body", "type": "report", "config": {}},
                {"id": "after", "type": "report", "config": {}},
            ],
            edges=[
                {"from": "loop", "to": "body"},
                {"from": "body", "to": "after"},
            ],
        )

        lock = threading.Lock()
        executed = []

        def fake_execute_node(self, node_type, config, context):
            node_id = config["_node_id"]
            with lock:
                executed.append(node_id)
            if node_type == "loop":
                return {"exit_status": 0, "loop_type": "for", "loop_iterations": 1}
            return {"exit_status": 0}

        monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)
        ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

        session.expire_all()
        refreshed = session.query(Execution).filter(Execution.id == execution.id).first()
        assert refreshed.status == "completed"
        assert executed.count("body") == 1
        assert executed.count("after") == 1
        session.close()


class TestParallelNode:

    def test_parallel_node_passes_through(self, tmp_path, monkeypatch):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        execution = create_workflow(
            session,
            nodes=[
                {"id": "par", "type": "parallel", "config": {"max_concurrent": 3}},
                {"id": "task-a", "type": "report", "config": {}},
                {"id": "task-b", "type": "report", "config": {}},
            ],
            edges=[
                {"from": "par", "to": "task-a"},
                {"from": "par", "to": "task-b"},
            ],
        )

        def fake_execute_node(self, node_type, config, context):
            if node_type == "parallel":
                return {"exit_status": 0, "max_concurrent": 3}
            return {"exit_status": 0}

        monkeypatch.setattr(ExecutionEngine, "_execute_node", fake_execute_node)
        ExecutionEngine(session, session_factory=session_factory).execute_workflow(execution.id)

        session.expire_all()
        statuses = get_node_statuses(session, execution.id)
        assert statuses["par"] == "success"
        assert statuses["task-a"] == "success"
        assert statuses["task-b"] == "success"
        session.close()


class TestAssertNode:

    def test_assert_handler_builds_log_contains_command(self):
        from app.services.execution.handlers.control import ControlHandlersMixin
        mixin = ControlHandlersMixin()
        mixin._quote = lambda v: f"'{v}'"

        cmd = mixin._build_assert_command(
            "log_contains",
            {"file_path": "/var/log/app.log"},
            "ERROR"
        )
        assert "grep" in cmd
        assert "ERROR" in cmd
        assert "/var/log/app.log" in cmd

    def test_assert_handler_builds_file_exists_command(self):
        from app.services.execution.handlers.control import ControlHandlersMixin
        mixin = ControlHandlersMixin()
        mixin._quote = lambda v: f"'{v}'"

        cmd = mixin._build_assert_command("file_exists", {}, "/tmp/test.txt")
        assert "test -f" in cmd
        assert "/tmp/test.txt" in cmd

    def test_assert_handler_builds_process_running_command(self):
        from app.services.execution.handlers.control import ControlHandlersMixin
        mixin = ControlHandlersMixin()
        mixin._quote = lambda v: f"'{v}'"

        cmd = mixin._build_assert_command("process_running", {}, "java")
        assert "pgrep" in cmd
        assert "java" in cmd

    def test_assert_handler_builds_port_open_command(self):
        from app.services.execution.handlers.control import ControlHandlersMixin
        mixin = ControlHandlersMixin()
        mixin._quote = lambda v: f"'{v}'"

        cmd = mixin._build_assert_command("port_open", {"port": "8080", "host": "localhost"}, "")
        assert "8080" in cmd

    def test_assert_handler_returns_none_for_unknown_type(self):
        from app.services.execution.handlers.control import ControlHandlersMixin
        mixin = ControlHandlersMixin()
        mixin._quote = lambda v: f"'{v}'"

        cmd = mixin._build_assert_command("unknown_type", {}, "")
        assert cmd is None


class TestConditionHandlerUnit:

    def test_condition_defaults_to_true_without_expression(self):
        from app.services.execution.handlers.control import ControlHandlersMixin
        mixin = ControlHandlersMixin()
        result = mixin._execute_condition_node({}, {})
        assert result["exit_status"] == 0
        assert result["branch"] == "true"


class TestEdgeLabelTracking:

    def test_build_execution_graph_returns_edge_labels(self, tmp_path):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        eng = ExecutionEngine(session, session_factory=session_factory)

        nodes = [
            {"id": "a", "type": "condition", "config": {}},
            {"id": "b", "type": "report", "config": {}},
            {"id": "c", "type": "report", "config": {}},
        ]
        edges = [
            {"from": "a", "to": "b", "label": "True"},
            {"from": "a", "to": "c", "label": "False"},
        ]
        _, _, _, _, edge_labels = eng._build_execution_graph(nodes, edges)

        assert edge_labels[("a", "b")] == "True"
        assert edge_labels[("a", "c")] == "False"
        session.close()

    def test_build_execution_graph_omits_unlabeled_edges(self, tmp_path):
        session_factory = make_engine(tmp_path)
        session = session_factory()
        eng = ExecutionEngine(session, session_factory=session_factory)

        nodes = [
            {"id": "a", "type": "report", "config": {}},
            {"id": "b", "type": "report", "config": {}},
        ]
        edges = [
            {"from": "a", "to": "b"},
        ]
        _, _, _, _, edge_labels = eng._build_execution_graph(nodes, edges)

        assert len(edge_labels) == 0
        session.close()
