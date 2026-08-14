from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


GrowthDimensionKey = Literal["attitude", "information", "reasoning", "argument", "expression"]
GrowthLevel = Literal["暂未体现", "正在发展", "表达清楚"]


class GrowthPointOut(BaseModel):
    session_id: str
    assignment_id: str
    assignment_title: str
    submitted_at: datetime
    grade: int
    level: GrowthLevel
    level_value: int = Field(ge=1, le=3)
    eligible: bool
    quote: Optional[str] = None
    observation: str


class GrowthDimensionOut(BaseModel):
    key: GrowthDimensionKey
    name: str
    current_level: Optional[GrowthLevel]
    current_value: Optional[int] = Field(default=None, ge=1, le=3)
    stable_level: Optional[GrowthLevel]
    evidence_count: int = Field(ge=0)
    summary: str
    points: list[GrowthPointOut]


class GrowthTimelineItemOut(BaseModel):
    session_id: str
    assignment_id: str
    assignment_title: str
    submitted_at: datetime
    grade: int
    used_coaching: bool
    coaching_rounds: int = Field(ge=0)
    status: Literal["INCLUDED", "EVIDENCE_INCOMPLETE"]
    representative_dimensions: list[str]
    quote: Optional[str] = None


class GrowthCoverageOut(BaseModel):
    completed_assignments: int = Field(ge=0)
    trend_eligible_assignments: int = Field(ge=0)
    available_grades: list[int]


class TeacherConfirmationOut(BaseModel):
    available: bool = False
    confirmed_count: int = 0
    total_count: int = Field(ge=0)


class ThinkingMoveEvidenceOut(BaseModel):
    session_id: str
    assignment_title: str
    quote: str


class ThinkingMoveOut(BaseModel):
    key: str
    name: str
    student_label: str
    count: int = Field(ge=0)
    evidence: list[ThinkingMoveEvidenceOut]


class GrowthReportOut(BaseModel):
    selected_grade: Optional[int]
    student_grade: int
    coverage: GrowthCoverageOut
    dimensions: list[GrowthDimensionOut]
    timeline: list[GrowthTimelineItemOut]
    thinking_moves: list[ThinkingMoveOut]
    narrative: str
    teacher_confirmation: TeacherConfirmationOut
