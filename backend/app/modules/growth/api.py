from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.identity.models import Student
from app.modules.identity.security import get_current_student

from .schemas import GrowthReportOut
from .service import build_report


router = APIRouter(prefix="/growth", tags=["growth"])


@router.get("", response_model=GrowthReportOut)
def get_growth_report(
    grade: Literal["all", "1", "2", "3", "4", "5", "6", "7"] = Query("all"),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> GrowthReportOut:
    selected_grade = None if grade == "all" else int(grade)
    return build_report(db, student, selected_grade)
