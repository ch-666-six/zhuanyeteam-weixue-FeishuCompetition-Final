from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("grade >= 1 AND grade <= 7", name="ck_students_grade_range"),
        Index("ix_students_grade", "grade"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    grade: Mapped[int] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

