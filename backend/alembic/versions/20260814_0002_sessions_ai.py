"""Create answer sessions, AI jobs, runs and idempotency records.

Revision ID: 20260814_0002
Revises: 20260814_0001
Create Date: 2026-08-14
"""
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0002"
down_revision: Optional[str] = "20260814_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("submission_status", sa.String(length=16), nullable=False),
        sa.Column("initial_answer", sa.Text(), nullable=True),
        sa.Column("initial_answer_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("phase IN ('INITIAL_DRAFT', 'INITIAL_ANALYSIS', 'FINAL_DRAFT', 'RESULT')", name="ck_answer_sessions_phase"),
        sa.CheckConstraint("mode = 'INITIAL'", name="ck_answer_sessions_mode"),
        sa.CheckConstraint("submission_status IN ('DRAFT', 'SUBMITTED')", name="ck_answer_sessions_submission_status"),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "assignment_id", name="uq_answer_sessions_student_assignment"),
    )
    op.create_index("ix_answer_sessions_student_phase", "answer_sessions", ["student_id", "phase"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "endpoint", "idempotency_key", name="uq_idempotency_scope_key"),
    )

    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_version", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["answer_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "job_type", "input_version", name="uq_ai_jobs_session_type_version"),
    )
    op.create_index("ix_ai_jobs_status_next_run", "ai_jobs", ["status", "next_run_at"])

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=80), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("schema_version", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["ai_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ai_runs")
    op.drop_index("ix_ai_jobs_status_next_run", table_name="ai_jobs")
    op.drop_table("ai_jobs")
    op.drop_table("idempotency_records")
    op.drop_index("ix_answer_sessions_student_phase", table_name="answer_sessions")
    op.drop_table("answer_sessions")
