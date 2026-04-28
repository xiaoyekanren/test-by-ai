# backend/app/api/test_suites.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from ..dependencies import get_db
from ..models.database import TestSuite, TestSuiteCase, Workflow
from ..schemas.test_suite import (
    TestSuiteCreate, TestSuiteUpdate, TestSuiteResponse,
    TestSuiteDetailResponse, TestSuiteCaseItem, AddCaseRequest,
)

router = APIRouter()


def _build_response(suite: TestSuite) -> dict:
    return {
        "id": suite.id,
        "name": suite.name,
        "description": suite.description,
        "suite_type": suite.suite_type,
        "artifact_version": suite.artifact_version,
        "created_at": suite.created_at,
        "updated_at": suite.updated_at,
        "case_count": len(suite.cases),
    }


def _build_detail_response(suite: TestSuite) -> dict:
    resp = _build_response(suite)
    resp["cases"] = [
        {
            "workflow_id": sc.workflow.id,
            "workflow_name": sc.workflow.name,
            "sort_order": sc.sort_order,
            "priority": sc.workflow.priority,
            "test_type": sc.workflow.test_type,
        }
        for sc in sorted(suite.cases, key=lambda c: c.sort_order)
    ]
    return resp


@router.get("", response_model=List[TestSuiteResponse])
def list_test_suites(
    suite_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(TestSuite)
    if suite_type:
        query = query.filter(TestSuite.suite_type == suite_type)
    suites = query.order_by(TestSuite.updated_at.desc()).all()
    return [_build_response(s) for s in suites]


@router.post("", response_model=TestSuiteResponse, status_code=status.HTTP_201_CREATED)
def create_test_suite(suite: TestSuiteCreate, db: Session = Depends(get_db)):
    existing = db.query(TestSuite).filter(TestSuite.name == suite.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"测试套件 '{suite.name}' 已存在",
        )
    db_suite = TestSuite(
        name=suite.name,
        description=suite.description,
        suite_type=suite.suite_type,
        artifact_version=suite.artifact_version,
    )
    db.add(db_suite)
    db.commit()
    db.refresh(db_suite)
    return _build_response(db_suite)


@router.get("/{suite_id}", response_model=TestSuiteDetailResponse)
def get_test_suite(suite_id: int, db: Session = Depends(get_db)):
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="测试套件不存在")
    return _build_detail_response(suite)


@router.put("/{suite_id}", response_model=TestSuiteResponse)
def update_test_suite(suite_id: int, update: TestSuiteUpdate, db: Session = Depends(get_db)):
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="测试套件不存在")

    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(suite, key, value)

    db.commit()
    db.refresh(suite)
    return _build_response(suite)


@router.delete("/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_suite(suite_id: int, db: Session = Depends(get_db)):
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="测试套件不存在")
    db.delete(suite)
    db.commit()
    return None


@router.post("/{suite_id}/cases", response_model=TestSuiteDetailResponse)
def add_case_to_suite(suite_id: int, req: AddCaseRequest, db: Session = Depends(get_db)):
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="测试套件不存在")

    workflow = db.query(Workflow).filter(Workflow.id == req.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    existing = db.query(TestSuiteCase).filter(
        TestSuiteCase.suite_id == suite_id,
        TestSuiteCase.workflow_id == req.workflow_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该工作流已在套件中")

    sort_order = req.sort_order
    if sort_order is None:
        max_order = max((c.sort_order for c in suite.cases), default=-1)
        sort_order = max_order + 1

    sc = TestSuiteCase(suite_id=suite_id, workflow_id=req.workflow_id, sort_order=sort_order)
    db.add(sc)
    db.commit()
    db.refresh(suite)
    return _build_detail_response(suite)


@router.delete("/{suite_id}/cases/{workflow_id}", response_model=TestSuiteDetailResponse)
def remove_case_from_suite(suite_id: int, workflow_id: int, db: Session = Depends(get_db)):
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="测试套件不存在")

    sc = db.query(TestSuiteCase).filter(
        TestSuiteCase.suite_id == suite_id,
        TestSuiteCase.workflow_id == workflow_id,
    ).first()
    if not sc:
        raise HTTPException(status_code=404, detail="该工作流不在套件中")

    db.delete(sc)
    db.commit()
    db.refresh(suite)
    return _build_detail_response(suite)


@router.put("/{suite_id}/cases/reorder", response_model=TestSuiteDetailResponse)
def reorder_cases(suite_id: int, workflow_ids: List[int], db: Session = Depends(get_db)):
    suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="测试套件不存在")

    cases_map = {sc.workflow_id: sc for sc in suite.cases}
    unknown = set(workflow_ids) - cases_map.keys()
    if unknown:
        raise HTTPException(status_code=400, detail=f"以下工作流不在套件中: {sorted(unknown)}")

    for i, wid in enumerate(workflow_ids):
        cases_map[wid].sort_order = i

    db.commit()
    db.refresh(suite)
    return _build_detail_response(suite)
