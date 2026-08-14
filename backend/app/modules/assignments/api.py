from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.assignments.models import Assignment
from app.modules.assignments.schemas import (
    AssignmentDetailOut,
    AssignmentSummaryOut,
    ManagedAssignmentBulkDeleteIn,
    ManagedAssignmentBulkDeleteOut,
    ManagedAssignmentCreateIn,
    ManagedAssignmentOut,
    ManagedAssignmentUpdateIn,
)
from app.modules.identity.models import Student
from app.modules.identity.security import get_current_student
from app.modules.sessions.application import find_session, session_snapshot
from app.modules.sessions.domain import as_utc, is_closed
from app.modules.sessions.models import AnswerSession
from uuid import uuid4

router = APIRouter(prefix="/assignments", tags=["assignments"])
management_router = APIRouter(prefix="/question-management", tags=["question management"])


@management_router.get("", response_model=list[ManagedAssignmentOut])
def list_managed_assignments(db: Session = Depends(get_db)) -> list[Assignment]:
    return list(db.scalars(select(Assignment).order_by(Assignment.grade, Assignment.created_at.desc())))


@management_router.post("", response_model=list[ManagedAssignmentOut], status_code=status.HTTP_201_CREATED)
def create_managed_assignment(body: ManagedAssignmentCreateIn, db: Session = Depends(get_db)) -> list[Assignment]:
    grades = sorted(set(body.grades))
    if any(grade < 1 or grade > 7 for grade in grades):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "INVALID_GRADES", "message": "年级必须在 1 到 7 之间。"})
    now = datetime.now(timezone.utc)
    assignments = [
        Assignment(
            id=str(uuid4()), title=body.title.strip(), prompt=body.prompt.strip(), grade=grade,
            input_type=body.input_type, published_at=now, deadline=None,
        )
        for grade in grades
    ]
    db.add_all(assignments)
    db.commit()
    for assignment in assignments:
        db.refresh(assignment)
    return assignments


@management_router.put("/{assignment_id}", response_model=ManagedAssignmentOut)
def update_managed_assignment(assignment_id: str, body: ManagedAssignmentUpdateIn, db: Session = Depends(get_db)) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "ASSIGNMENT_NOT_FOUND", "message": "没有找到这道题目。"})
    assignment.title = body.title.strip()
    assignment.prompt = body.prompt.strip()
    assignment.grade = body.grade
    assignment.input_type = body.input_type
    db.commit()
    db.refresh(assignment)
    return assignment


@management_router.post("/bulk-delete", response_model=ManagedAssignmentBulkDeleteOut)
def bulk_delete_managed_assignments(body: ManagedAssignmentBulkDeleteIn, db: Session = Depends(get_db)) -> ManagedAssignmentBulkDeleteOut:
    requested_ids = list(dict.fromkeys(body.ids))
    assignments = {item.id: item for item in db.scalars(select(Assignment).where(Assignment.id.in_(requested_ids)))}
    used_ids = set(db.scalars(select(AnswerSession.assignment_id).where(AnswerSession.assignment_id.in_(requested_ids))))
    deleted_ids = []
    blocked_ids = []
    for assignment_id in requested_ids:
        assignment = assignments.get(assignment_id)
        if assignment is None:
            continue
        if assignment_id in used_ids:
            blocked_ids.append(assignment_id)
            continue
        db.delete(assignment)
        deleted_ids.append(assignment_id)
    db.commit()
    return ManagedAssignmentBulkDeleteOut(
        deleted_ids=deleted_ids,
        blocked_ids=blocked_ids,
        not_found_ids=[assignment_id for assignment_id in requested_ids if assignment_id not in assignments],
    )


@management_router.delete("/{assignment_id}")
def delete_managed_assignment(assignment_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "ASSIGNMENT_NOT_FOUND", "message": "没有找到这道题目。"})
    if db.scalar(select(AnswerSession.id).where(AnswerSession.assignment_id == assignment_id).limit(1)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "ASSIGNMENT_IN_USE", "message": "这道题目已经产生学习记录，不能删除。"})
    db.delete(assignment)
    db.commit()
    return {"deleted": True}


@router.get("", response_model=list[AssignmentSummaryOut])
def list_assignments(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> list[AssignmentSummaryOut]:
    now = datetime.now(timezone.utc)
    statement = (
        select(Assignment)
        .where(
            Assignment.grade == student.grade,
            Assignment.published_at.is_not(None),
            Assignment.published_at <= now,
        )
        .order_by(Assignment.deadline.asc().nulls_last(), Assignment.created_at.desc())
    )
    result = []
    for assignment in db.scalars(statement):
        answer_session = find_session(db, assignment.id, student.id)
        result.append(
            AssignmentSummaryOut(
                id=assignment.id,
                title=assignment.title,
                prompt=assignment.prompt,
                grade=assignment.grade,
                input_type=assignment.input_type,
                deadline=as_utc(assignment.deadline),
                availability="CLOSED" if is_closed(assignment.deadline, now) else "OPEN",
                session=session_snapshot(db, answer_session, assignment) if answer_session else None,
            )
        )
    return result


@router.get("/{assignment_id}", response_model=AssignmentDetailOut)
def get_assignment(
    assignment_id: str,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> AssignmentDetailOut:
    from fastapi import HTTPException, status

    now = datetime.now(timezone.utc)
    assignment = db.get(Assignment, assignment_id)
    if (
        assignment is None
        or assignment.grade != student.grade
        or assignment.published_at is None
        or as_utc(assignment.published_at) > now
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ASSIGNMENT_NOT_FOUND", "message": "没有找到这项作业。"},
        )
    answer_session = find_session(db, assignment.id, student.id)
    return AssignmentDetailOut(
        id=assignment.id,
        title=assignment.title,
        prompt=assignment.prompt,
        grade=assignment.grade,
        input_type=assignment.input_type,
        published_at=as_utc(assignment.published_at),
        deadline=as_utc(assignment.deadline),
        availability="CLOSED" if is_closed(assignment.deadline, now) else "OPEN",
        session=session_snapshot(db, answer_session, assignment) if answer_session else None,
    )
