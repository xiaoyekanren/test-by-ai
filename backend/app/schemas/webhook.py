from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GitLabWebhookRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    workflow_ids: List[int] = Field(default_factory=list, min_length=1)
    project_id: Optional[str] = Field(default=None, max_length=50)
    project_path: Optional[str] = Field(default=None, max_length=300)
    ref_patterns: List[str] = Field(default_factory=list)
    secret_token: str = Field(min_length=1, max_length=500)

    @field_validator("workflow_ids")
    @classmethod
    def workflow_ids_must_be_positive(cls, value: List[int]) -> List[int]:
        cleaned = []
        for item in value:
            if int(item) <= 0:
                raise ValueError("workflow_ids must contain positive ids")
            if int(item) not in cleaned:
                cleaned.append(int(item))
        return cleaned

    @field_validator("ref_patterns")
    @classmethod
    def normalize_ref_patterns(cls, value: List[str]) -> List[str]:
        return [item.strip() for item in value if item.strip()]


class GitLabWebhookRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    workflow_ids: Optional[List[int]] = None
    project_id: Optional[str] = Field(default=None, max_length=50)
    project_path: Optional[str] = Field(default=None, max_length=300)
    ref_patterns: Optional[List[str]] = None
    secret_token: Optional[str] = Field(default=None, min_length=1, max_length=500)

    @field_validator("workflow_ids")
    @classmethod
    def workflow_ids_must_be_positive(cls, value: Optional[List[int]]) -> Optional[List[int]]:
        if value is None:
            return value
        cleaned = []
        for item in value:
            if int(item) <= 0:
                raise ValueError("workflow_ids must contain positive ids")
            if int(item) not in cleaned:
                cleaned.append(int(item))
        if not cleaned:
            raise ValueError("workflow_ids must contain at least one id")
        return cleaned

    @field_validator("ref_patterns")
    @classmethod
    def normalize_ref_patterns(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        return [item.strip() for item in value if item.strip()]


class GitLabWebhookRuleResponse(BaseModel):
    id: int
    name: str
    enabled: bool
    workflow_ids: List[int]
    project_id: Optional[str]
    project_path: Optional[str]
    ref_patterns: List[str]
    secret_configured: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GitLabWebhookEventResponse(BaseModel):
    id: int
    rule_id: int
    event_uuid: Optional[str]
    project_id: Optional[str]
    project_path: Optional[str]
    ref: Optional[str]
    before_sha: Optional[str]
    after_sha: Optional[str]
    user_name: Optional[str]
    user_username: Optional[str]
    status: str
    execution_ids: List[int]
    error: Optional[str]
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GitLabWebhookTriggerResponse(BaseModel):
    status: Literal["accepted", "ignored"]
    rule_id: int
    execution_ids: List[int] = Field(default_factory=list)
    message: str
    event: Dict[str, Any] = Field(default_factory=dict)
