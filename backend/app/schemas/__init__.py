# backend/app/schemas/__init__.py
from .server import ServerCreate, ServerUpdate, ServerResponse
from .workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from .execution import ExecutionCreate, ExecutionUpdate, ExecutionResponse, NodeExecutionResponse
from .test_suite import (
    TestSuiteCreate, TestSuiteUpdate, TestSuiteResponse,
    TestSuiteDetailResponse, AddCaseRequest, TestSuiteCaseItem,
)
