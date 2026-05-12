import fnmatch
import hashlib
import hmac
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.database import Execution, GitLabWebhookEvent, GitLabWebhookRule, Workflow
from app.schemas.webhook import (
    GitLabWebhookEventResponse,
    GitLabWebhookRuleCreate,
    GitLabWebhookRuleResponse,
    GitLabWebhookRuleUpdate,
    GitLabWebhookTriggerResponse,
)
from app.services.execution_engine import ExecutionEngine

router = APIRouter()


def _hash_secret(secret: str) -> str:
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _verify_secret(secret_hash: str, provided: Optional[str]) -> bool:
    if not secret_hash or not provided:
        return False
    return hmac.compare_digest(secret_hash, _hash_secret(provided))


def _rule_response(rule: GitLabWebhookRule) -> GitLabWebhookRuleResponse:
    return GitLabWebhookRuleResponse(
        id=rule.id,
        name=rule.name,
        enabled=bool(rule.enabled),
        workflow_ids=list(rule.workflow_ids or []),
        project_id=rule.project_id,
        project_path=rule.project_path,
        ref_patterns=list(rule.ref_patterns or []),
        secret_configured=bool(rule.secret_hash),
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _validate_workflows(db: Session, workflow_ids: List[int]) -> List[int]:
    unique_ids = []
    for workflow_id in workflow_ids:
        if int(workflow_id) not in unique_ids:
            unique_ids.append(int(workflow_id))
    found = {
        item[0]
        for item in db.query(Workflow.id).filter(Workflow.id.in_(unique_ids)).all()
    }
    missing = [workflow_id for workflow_id in unique_ids if workflow_id not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"工作流不存在: {', '.join(str(item) for item in missing)}",
        )
    return unique_ids


def _project_path(payload: Dict[str, Any]) -> Optional[str]:
    project = payload.get("project")
    if isinstance(project, dict):
        return project.get("path_with_namespace") or project.get("web_url") or project.get("name")
    return None


def _project_id(payload: Dict[str, Any]) -> Optional[str]:
    value = payload.get("project_id")
    if value in (None, "") and isinstance(payload.get("project"), dict):
        value = payload["project"].get("id")
    return None if value in (None, "") else str(value)


def _short_event_summary(payload: Dict[str, Any], event_uuid: Optional[str]) -> Dict[str, Any]:
    return {
        "event_uuid": event_uuid,
        "project_id": _project_id(payload),
        "project_path": _project_path(payload),
        "ref": payload.get("ref"),
        "before_sha": payload.get("before"),
        "after_sha": payload.get("after") or payload.get("checkout_sha"),
        "checkout_sha": payload.get("checkout_sha"),
        "user_name": payload.get("user_name"),
        "user_username": payload.get("user_username") or payload.get("user_name"),
    }


def _normalize_ref(value: Optional[str]) -> str:
    ref = str(value or "").strip()
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/")
    return ref


def _matches_ref(rule: GitLabWebhookRule, ref: Optional[str]) -> bool:
    patterns = [str(item).strip() for item in (rule.ref_patterns or []) if str(item).strip()]
    if not patterns:
        return True
    full_ref = str(ref or "").strip()
    short_ref = _normalize_ref(full_ref)
    for pattern in patterns:
        normalized_pattern = _normalize_ref(pattern)
        if fnmatch.fnmatch(full_ref, pattern) or fnmatch.fnmatch(short_ref, normalized_pattern):
            return True
    return False


def _matches_project(rule: GitLabWebhookRule, payload: Dict[str, Any]) -> bool:
    payload_project_id = _project_id(payload)
    payload_project_path = _project_path(payload)
    if rule.project_id and str(rule.project_id) != str(payload_project_id or ""):
        return False
    if rule.project_path and str(rule.project_path) != str(payload_project_path or ""):
        return False
    return True


def _create_event(
    db: Session,
    rule_id: int,
    summary: Dict[str, Any],
    status_value: str,
    execution_ids: Optional[List[int]] = None,
    error: Optional[str] = None,
) -> GitLabWebhookEvent:
    event = GitLabWebhookEvent(
        rule_id=rule_id,
        event_uuid=summary.get("event_uuid"),
        project_id=summary.get("project_id"),
        project_path=summary.get("project_path"),
        ref=summary.get("ref"),
        before_sha=summary.get("before_sha"),
        after_sha=summary.get("after_sha"),
        user_name=summary.get("user_name"),
        user_username=summary.get("user_username"),
        status=status_value,
        execution_ids=execution_ids or [],
        error=error,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/gitlab/rules", response_model=List[GitLabWebhookRuleResponse])
def list_gitlab_webhook_rules(db: Session = Depends(get_db)):
    rules = db.query(GitLabWebhookRule).order_by(GitLabWebhookRule.id.asc()).all()
    return [_rule_response(rule) for rule in rules]


@router.post("/gitlab/rules", response_model=GitLabWebhookRuleResponse, status_code=status.HTTP_201_CREATED)
def create_gitlab_webhook_rule(payload: GitLabWebhookRuleCreate, db: Session = Depends(get_db)):
    workflow_ids = _validate_workflows(db, payload.workflow_ids)
    rule = GitLabWebhookRule(
        name=payload.name.strip(),
        enabled=payload.enabled,
        workflow_ids=workflow_ids,
        project_id=(payload.project_id or "").strip() or None,
        project_path=(payload.project_path or "").strip() or None,
        ref_patterns=payload.ref_patterns,
        secret_hash=_hash_secret(payload.secret_token),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_response(rule)


@router.put("/gitlab/rules/{rule_id}", response_model=GitLabWebhookRuleResponse)
def update_gitlab_webhook_rule(
    rule_id: int,
    payload: GitLabWebhookRuleUpdate,
    db: Session = Depends(get_db),
):
    rule = db.query(GitLabWebhookRule).filter(GitLabWebhookRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitLab webhook 规则不存在")

    update_data = payload.model_dump(exclude_unset=True)
    if "workflow_ids" in update_data and update_data["workflow_ids"] is not None:
        rule.workflow_ids = _validate_workflows(db, update_data["workflow_ids"])
    if "name" in update_data and update_data["name"] is not None:
        rule.name = str(update_data["name"]).strip()
    if "enabled" in update_data and update_data["enabled"] is not None:
        rule.enabled = bool(update_data["enabled"])
    if "project_id" in update_data:
        rule.project_id = (update_data.get("project_id") or "").strip() or None
    if "project_path" in update_data:
        rule.project_path = (update_data.get("project_path") or "").strip() or None
    if "ref_patterns" in update_data and update_data["ref_patterns"] is not None:
        rule.ref_patterns = update_data["ref_patterns"]
    if "secret_token" in update_data and update_data["secret_token"]:
        rule.secret_hash = _hash_secret(update_data["secret_token"])

    db.commit()
    db.refresh(rule)
    return _rule_response(rule)


@router.delete("/gitlab/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gitlab_webhook_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(GitLabWebhookRule).filter(GitLabWebhookRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitLab webhook 规则不存在")
    db.query(GitLabWebhookEvent).filter(GitLabWebhookEvent.rule_id == rule_id).delete(synchronize_session=False)
    db.delete(rule)
    db.commit()
    return None


@router.get("/gitlab/events", response_model=List[GitLabWebhookEventResponse])
def list_gitlab_webhook_events(rule_id: Optional[int] = None, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(GitLabWebhookEvent)
    if rule_id is not None:
        query = query.filter(GitLabWebhookEvent.rule_id == rule_id)
    return query.order_by(GitLabWebhookEvent.received_at.desc()).limit(limit).all()


@router.post("/gitlab/{rule_id}", response_model=GitLabWebhookTriggerResponse)
async def trigger_gitlab_webhook(
    rule_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitlab_event: Optional[str] = Header(default=None, alias="X-Gitlab-Event"),
    x_gitlab_token: Optional[str] = Header(default=None, alias="X-Gitlab-Token"),
    x_gitlab_event_uuid: Optional[str] = Header(default=None, alias="X-Gitlab-Event-UUID"),
    x_gitlab_webhook_uuid: Optional[str] = Header(default=None, alias="X-Gitlab-Webhook-UUID"),
    db: Session = Depends(get_db),
):
    rule = db.query(GitLabWebhookRule).filter(GitLabWebhookRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitLab webhook 规则不存在")
    if not _verify_secret(rule.secret_hash, x_gitlab_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="GitLab webhook token 无效")

    payload = await request.json()
    summary = _short_event_summary(payload, x_gitlab_webhook_uuid or x_gitlab_event_uuid)
    if x_gitlab_event != "Push Hook":
        _create_event(db, rule_id, summary, "ignored", error=f"Unsupported event: {x_gitlab_event or 'unknown'}")
        return GitLabWebhookTriggerResponse(status="ignored", rule_id=rule_id, message="Only Push Hook is supported", event=summary)
    if not rule.enabled:
        _create_event(db, rule_id, summary, "ignored", error="Rule disabled")
        return GitLabWebhookTriggerResponse(status="ignored", rule_id=rule_id, message="Rule is disabled", event=summary)
    if not _matches_project(rule, payload):
        _create_event(db, rule_id, summary, "ignored", error="Project filter did not match")
        return GitLabWebhookTriggerResponse(status="ignored", rule_id=rule_id, message="Project filter did not match", event=summary)
    if not _matches_ref(rule, payload.get("ref")):
        _create_event(db, rule_id, summary, "ignored", error="Ref pattern did not match")
        return GitLabWebhookTriggerResponse(status="ignored", rule_id=rule_id, message="Ref pattern did not match", event=summary)

    workflow_ids = list(rule.workflow_ids or [])
    workflows = db.query(Workflow).filter(Workflow.id.in_(workflow_ids)).all()
    workflows_by_id = {workflow.id: workflow for workflow in workflows}
    missing = [workflow_id for workflow_id in workflow_ids if workflow_id not in workflows_by_id]
    if missing:
        event = _create_event(
            db,
            rule_id,
            summary,
            "error",
            error=f"Workflow not found: {', '.join(str(item) for item in missing)}",
        )
        return GitLabWebhookTriggerResponse(
            status="ignored",
            rule_id=rule_id,
            message=event.error or "Workflow not found",
            event=summary,
        )

    engine = ExecutionEngine(db)
    execution_ids: List[int] = []
    for workflow_id in workflow_ids:
        execution = engine.create_execution(
            workflow_id=workflow_id,
            trigger_type="webhook",
            triggered_by=f"gitlab:{rule_id}",
        )
        execution.summary = {
            "webhook": {
                "provider": "gitlab",
                "rule_id": rule_id,
                "rule_name": rule.name,
                **summary,
            }
        }
        db.commit()
        db.refresh(execution)
        execution_ids.append(execution.id)
        background_tasks.add_task(engine.execute_workflow, execution.id)

    _create_event(db, rule_id, summary, "accepted", execution_ids=execution_ids)
    return GitLabWebhookTriggerResponse(
        status="accepted",
        rule_id=rule_id,
        execution_ids=execution_ids,
        message=f"Triggered {len(execution_ids)} workflow execution(s)",
        event=summary,
    )
