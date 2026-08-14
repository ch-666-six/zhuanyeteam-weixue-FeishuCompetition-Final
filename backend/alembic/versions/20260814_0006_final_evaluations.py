"""Add versioned final evaluation results.

Revision ID: 20260814_0006
Revises: 20260814_0005
Create Date: 2026-08-14
"""
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0006"
down_revision: Optional[str] = "20260814_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "final_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("rubric_version", sa.String(length=40), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_jobs.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["answer_sessions.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["answer_submissions.id"]),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("job_id"), sa.UniqueConstraint("submission_id"),
    )


def downgrade() -> None:
    op.drop_table("final_evaluations")
