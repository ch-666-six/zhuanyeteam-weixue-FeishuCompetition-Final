"""Add V1.1 text coaching sessions and turns.

Revision ID: 20260814_0007
Revises: 20260814_0006
Create Date: 2026-08-14
"""
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0007"
down_revision: Optional[str] = "20260814_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("answer_sessions") as batch:
        batch.drop_constraint("ck_answer_sessions_phase", type_="check")
        batch.create_check_constraint(
            "ck_answer_sessions_phase",
            "phase IN ('INITIAL_DRAFT', 'INITIAL_ANALYSIS', 'COACHING', 'FINAL_DRAFT', 'RESULT')",
        )
    op.create_table(
        "coaching_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False),
        sa.Column("max_rounds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('ACTIVE', 'ENDED_BY_STUDENT', 'ENDED_BY_LIMIT', 'SKIPPED')", name="ck_coaching_sessions_status"),
        sa.CheckConstraint("current_round >= 0 AND current_round <= 20", name="ck_coaching_sessions_round"),
        sa.ForeignKeyConstraint(["session_id"], ["answer_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_table(
        "coaching_turns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("focus_element", sa.String(length=32), nullable=True),
        sa.Column("scaffold_type", sa.String(length=48), nullable=True),
        sa.Column("student_response", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("question_job_id", sa.String(length=36), nullable=True),
        sa.Column("question_schema_version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("round_number >= 1 AND round_number <= 20", name="ck_coaching_turns_round"),
        sa.CheckConstraint("status IN ('WAITING', 'READY', 'ANSWERED', 'FAILED')", name="ck_coaching_turns_status"),
        sa.ForeignKeyConstraint(["question_job_id"], ["ai_jobs.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["answer_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_job_id"),
        sa.UniqueConstraint("session_id", "round_number", name="uq_coaching_turns_session_round"),
    )


def downgrade() -> None:
    op.drop_table("coaching_turns")
    op.drop_table("coaching_sessions")
    with op.batch_alter_table("answer_sessions") as batch:
        batch.drop_constraint("ck_answer_sessions_phase", type_="check")
        batch.create_check_constraint(
            "ck_answer_sessions_phase",
            "phase IN ('INITIAL_DRAFT', 'INITIAL_ANALYSIS', 'FINAL_DRAFT', 'RESULT')",
        )
