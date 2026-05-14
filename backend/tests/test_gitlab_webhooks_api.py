import json
import sys
from pathlib import Path

sys.path.insert(0, "backend")

from app.config import BASE_DIR
from app.models.database import GitLabWebhookEvent, NodeExecution


def create_workflow(client, name="webhook-workflow"):
    response = client.post(
        "/api/workflows",
        json={
            "name": name,
            "nodes": [{"id": "report", "type": "report", "config": {}}],
            "edges": [],
        },
    )
    assert response.status_code == 201
    return response.json()


def create_rule(client, workflow_ids, token="secret", ref_patterns=None):
    response = client.post(
        "/api/webhooks/gitlab/rules",
        json={
            "name": "main-push",
            "enabled": True,
            "workflow_ids": workflow_ids,
            "project_id": "123",
            "project_path": "group/project",
            "ref_patterns": ref_patterns or ["main"],
            "secret_token": token,
        },
    )
    assert response.status_code == 201
    return response.json()


def push_payload(ref="refs/heads/main"):
    return {
        "object_kind": "push",
        "event_name": "push",
        "project_id": 123,
        "project": {
            "id": 123,
            "path_with_namespace": "group/project",
        },
        "ref": ref,
        "before": "a" * 40,
        "after": "b" * 40,
        "checkout_sha": "b" * 40,
        "user_name": "Alice",
        "user_username": "alice",
    }


def webhook_headers(token="secret", event="Push Hook"):
    return {
        "X-Gitlab-Event": event,
        "X-Gitlab-Token": token,
        "X-Gitlab-Webhook-UUID": "event-1",
    }


def test_gitlab_webhook_rejects_missing_or_wrong_secret(client):
    workflow = create_workflow(client)
    rule = create_rule(client, [workflow["id"]])

    missing = client.post(f"/api/webhooks/gitlab/{rule['id']}", json=push_payload())
    wrong = client.post(
        f"/api/webhooks/gitlab/{rule['id']}",
        json=push_payload(),
        headers=webhook_headers(token="wrong"),
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401


def test_gitlab_webhook_ignores_non_push_hook(client, db_session):
    workflow = create_workflow(client)
    rule = create_rule(client, [workflow["id"]])

    response = client.post(
        f"/api/webhooks/gitlab/{rule['id']}",
        json=push_payload(),
        headers=webhook_headers(event="Merge Request Hook"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    event = db_session.query(GitLabWebhookEvent).one()
    assert event.status == "ignored"
    assert event.execution_ids == []


def test_gitlab_webhook_ignores_unmatched_ref(client, db_session):
    workflow = create_workflow(client)
    rule = create_rule(client, [workflow["id"]], ref_patterns=["release/*"])

    response = client.post(
        f"/api/webhooks/gitlab/{rule['id']}",
        json=push_payload(ref="refs/heads/main"),
        headers=webhook_headers(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    event = db_session.query(GitLabWebhookEvent).one()
    assert event.status == "ignored"
    assert event.error == "Ref pattern did not match"


def test_gitlab_webhook_triggers_multiple_workflows(client, db_session):
    workflow_a = create_workflow(client, "workflow-a")
    workflow_b = create_workflow(client, "workflow-b")
    rule = create_rule(client, [workflow_a["id"], workflow_b["id"]])

    response = client.post(
        f"/api/webhooks/gitlab/{rule['id']}",
        json=push_payload(),
        headers=webhook_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert len(data["execution_ids"]) == 2

    event = db_session.query(GitLabWebhookEvent).one()
    assert event.status == "accepted"
    assert event.project_id == "123"
    assert event.project_path == "group/project"
    assert event.ref == "refs/heads/main"
    assert event.execution_ids == data["execution_ids"]


def test_webhook_execution_writes_log_and_prunes_node_payloads(client, db_session):
    workflow = create_workflow(client)
    rule = create_rule(client, [workflow["id"]])

    response = client.post(
        f"/api/webhooks/gitlab/{rule['id']}",
        json=push_payload(),
        headers=webhook_headers(),
    )

    assert response.status_code == 200
    execution_id = response.json()["execution_ids"][0]
    node_execution = db_session.query(NodeExecution).filter(
        NodeExecution.execution_id == execution_id
    ).one()

    assert node_execution.input_data is None
    assert node_execution.output_data is None
    assert node_execution.log_path

    log_path = Path(node_execution.log_path)
    assert log_path.exists()
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["type"] == "execution"
    assert lines[0]["execution_id"] == execution_id
    assert any(line["type"] == "node" and line["node_id"] == "report" for line in lines)

    if log_path.is_relative_to(BASE_DIR):
        log_path.unlink(missing_ok=True)
