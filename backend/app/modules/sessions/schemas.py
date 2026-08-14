from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional, Union

from app.ai.initial_analysis import InitialAnalysisV1, InitialAnalysisV2
from app.ai.final_evaluation import FinalEvaluationV1

from pydantic import BaseModel, Field


class SessionJobOut(BaseModel):
    status: Literal["IDLE", "QUEUED", "RUNNING", "FAILED_RETRYABLE", "FAILED_FINAL", "SUCCEEDED"]
    error_code: Optional[str] = None


class SessionJobsOut(BaseModel):
    initial_analysis: SessionJobOut
    final_evaluation: SessionJobOut = Field(default_factory=lambda: SessionJobOut(status="IDLE"))
    coaching_question: SessionJobOut = Field(default_factory=lambda: SessionJobOut(status="IDLE"))


class CoachingSummaryOut(BaseModel):
    status: Literal["NOT_STARTED", "ACTIVE", "ENDED_BY_STUDENT", "ENDED_BY_LIMIT", "SKIPPED"]
    current_round: int = Field(default=0, ge=0, le=20)
    completed_rounds: int = Field(default=0, ge=0, le=20)
    max_rounds: int = 20
    current_turn_id: Optional[str] = None


class SessionSnapshotOut(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    version: int
    phase: Literal["INITIAL_DRAFT", "INITIAL_ANALYSIS", "COACHING", "FINAL_DRAFT", "RESULT"]
    mode: Literal["INITIAL"]
    submission_status: Literal["DRAFT", "SUBMITTED"]
    allowed_actions: List[Literal["SUBMIT_INITIAL_ANSWER", "RETRY_INITIAL_ANALYSIS", "START_COACHING", "START_FINAL_DRAFT", "SUBMIT_COACHING_RESPONSE", "END_COACHING", "RETRY_COACHING_QUESTION", "SUBMIT_FINAL_ANSWER", "RETRY_FINAL_EVALUATION"]]
    next_view: Literal["INITIAL_DRAFT", "INITIAL_ANALYSIS_PENDING", "INITIAL_ANALYSIS", "COACHING_PENDING", "COACHING", "FINAL_DRAFT", "FINAL_EVALUATION_PENDING", "RESULT"]
    jobs: SessionJobsOut
    coaching: CoachingSummaryOut = Field(default_factory=lambda: CoachingSummaryOut(status="NOT_STARTED"))
    initial_answer: Optional[str] = None
    current_submission_id: Optional[str] = None
    final_answer: Optional[str] = None
    deadline: Optional[datetime] = None
    server_time: datetime


class CreateSessionIn(BaseModel):
    assignment_id: str = Field(min_length=1, max_length=36)


class InitialAnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    expected_version: int = Field(ge=1)


class InitialAnalysisOut(BaseModel):
    session_id: str
    input_version: int
    initial_answer: str
    analysis: Union[InitialAnalysisV1, InitialAnalysisV2]


class VersionedActionIn(BaseModel):
    expected_version: int = Field(ge=1)


class FinalAnswerIn(VersionedActionIn):
    answer: str = Field(min_length=1, max_length=12000)


class CoachingResponseIn(VersionedActionIn):
    answer: str = Field(min_length=1, max_length=12000)


class CoachingTurnOut(BaseModel):
    id: str
    round_number: int
    question_text: Optional[str]
    focus_element: Optional[str]
    scaffold_type: Optional[str]
    student_response: Optional[str]
    status: Literal["WAITING", "READY", "ANSWERED", "FAILED"]


class CoachingOut(BaseModel):
    session_id: str
    status: Literal["ACTIVE", "ENDED_BY_STUDENT", "ENDED_BY_LIMIT", "SKIPPED"]
    current_round: int
    max_rounds: int
    turns: List[CoachingTurnOut]


class FinalEvaluationOut(BaseModel):
    session_id: str
    submission_id: str
    initial_answer: str
    final_answer: str
    evaluation: FinalEvaluationV1
