"""Add immutable final answer submissions.

Revision ID: 20260814_0005
Revises: 20260814_0004
Create Date: 2026-08-14
"""
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0005"
down_revision: Optional[str] = "20260814_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("submission_version", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("source_session_version", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["answer_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "submission_version", name="uq_answer_submissions_session_version"),
    )
    op.create_index("ix_answer_submissions_session", "answer_submissions", ["session_id"])
    with op.batch_alter_table("answer_sessions") as batch_op:
        batch_op.add_column(sa.Column("current_submission_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_answer_sessions_current_submission", "answer_submissions", ["current_submission_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("answer_sessions") as batch_op:
        batch_op.drop_constraint("fk_answer_sessions_current_submission", type_="foreignkey")
        batch_op.drop_column("current_submission_id")
    op.drop_index("ix_answer_submissions_session", table_name="answer_submissions")
    op.drop_table("answer_submissions")
