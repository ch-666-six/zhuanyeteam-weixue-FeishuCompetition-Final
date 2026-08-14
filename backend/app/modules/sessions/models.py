from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class AnswerSession(Base):
    __tablename__ = "answer_sessions"
    __table_args__ = (
        UniqueConstraint("student_id", "assignment_id", name="uq_answer_sessions_student_assignment"),
        CheckConstraint(
            "phase IN ('INITIAL_DRAFT', 'INITIAL_ANALYSIS', 'COACHING', 'FINAL_DRAFT', 'RESULT')",
            name="ck_answer_sessions_phase",
        ),
        CheckConstraint("mode = 'INITIAL'", name="ck_answer_sessions_mode"),
        CheckConstraint("submission_status IN ('DRAFT', 'SUBMITTED')", name="ck_answer_sessions_submission_status"),
        Index("ix_answer_sessions_student_phase", "student_id", "phase"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), nullable=False)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="INITIAL_DRAFT")
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="INITIAL")
    submission_status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    initial_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    initial_answer_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_submission_id: Mapped[Optional[str]] = mapped_column(ForeignKey("answer_submissions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("student_id", "endpoint", "idempotency_key", name="uq_idempotency_scope_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class AiJob(Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        UniqueConstraint("session_id", "job_type", "input_version", name="uq_ai_jobs_session_type_version"),
        Index("ix_ai_jobs_status_next_run", "status", "next_run_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("answer_sessions.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="QUEUED")
    input_version: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class AiRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("ai_jobs.id"), nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    schema_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class InitialAnalysis(Base):
    __tablename__ = "initial_analyses"
    __table_args__ = (
        UniqueConstraint("session_id", "input_version", name="uq_initial_analyses_session_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("answer_sessions.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("ai_jobs.id"), nullable=False, unique=True)
    input_version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class CoachingSession(Base):
    __tablename__ = "coaching_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'ENDED_BY_STUDENT', 'ENDED_BY_LIMIT', 'SKIPPED')",
            name="ck_coaching_sessions_status",
        ),
        CheckConstraint("current_round >= 0 AND current_round <= 20", name="ck_coaching_sessions_round"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("answer_sessions.id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CoachingTurn(Base):
    __tablename__ = "coaching_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "round_number", name="uq_coaching_turns_session_round"),
        CheckConstraint("round_number >= 1 AND round_number <= 20", name="ck_coaching_turns_round"),
        CheckConstraint("status IN ('WAITING', 'READY', 'ANSWERED', 'FAILED')", name="ck_coaching_turns_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("answer_sessions.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    focus_element: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    scaffold_type: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    student_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="WAITING")
    question_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("ai_jobs.id"), nullable=True, unique=True)
    question_schema_version: Mapped[str] = mapped_column(String(40), nullable=False, default="coaching-question-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AnswerSubmission(Base):
    __tablename__ = "answer_submissions"
    __table_args__ = (
        UniqueConstraint("session_id", "submission_version", name="uq_answer_submissions_session_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("answer_sessions.id"), nullable=False)
    submission_version: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_session_version: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class FinalEvaluation(Base):
    __tablename__ = "final_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("answer_sessions.id"), nullable=False)
    submission_id: Mapped[str] = mapped_column(ForeignKey("answer_submissions.id"), nullable=False, unique=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("ai_jobs.id"), nullable=False, unique=True)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(40), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
