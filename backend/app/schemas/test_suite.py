# backend/app/schemas/test_suite.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime

SUITE_TYPE = Literal["smoke", "regression", "feature", "performance"]


class TestSuiteBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    suite_type: SUITE_TYPE = "feature"
    artifact_version: Optional[str] = None


class TestSuiteCreate(TestSuiteBase):
    pass


class TestSuiteUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    suite_type: Optional[SUITE_TYPE] = None
    artifact_version: Optional[str] = None


class TestSuiteCaseItem(BaseModel):
    workflow_id: int
    workflow_name: str
    sort_order: int
    priority: Optional[str] = None
    test_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TestSuiteResponse(TestSuiteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    case_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TestSuiteDetailResponse(TestSuiteResponse):
    cases: List[TestSuiteCaseItem] = []


class AddCaseRequest(BaseModel):
    workflow_id: int
    sort_order: Optional[int] = None
