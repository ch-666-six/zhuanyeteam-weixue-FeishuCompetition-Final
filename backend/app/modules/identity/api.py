from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.infrastructure.database import get_db
from app.modules.identity.models import Student
from app.modules.identity.schemas import DemoLoginIn, DemoLoginOut, DemoStudentOut
from app.modules.identity.security import create_access_token

router = APIRouter(prefix="/demo", tags=["demo identity"])


@router.get("/students", response_model=list[DemoStudentOut])
def list_demo_students(db: Session = Depends(get_db)) -> list[Student]:
    return list(
        db.scalars(
            select(Student).where(Student.is_demo.is_(True)).order_by(Student.grade, Student.display_name)
        )
    )


@router.post("/login", response_model=DemoLoginOut)
def demo_login(
    body: DemoLoginIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DemoLoginOut:
    student = db.get(Student, body.student_id)
    if student is None or not student.is_demo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "没有找到这个演示身份。"},
        )
    return DemoLoginOut(
        access_token=create_access_token(student.id, settings),
        student=DemoStudentOut.model_validate(student),
    )

