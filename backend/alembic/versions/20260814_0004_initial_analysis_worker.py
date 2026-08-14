"""Add recoverable AI leases and initial analysis results.

Revision ID: 20260814_0004
Revises: 20260814_0003
Create Date: 2026-08-14
"""
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0004"
down_revision: Optional[str] = "20260814_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_jobs", sa.Column("lease_owner", sa.String(length=80), nullable=True))
    op.add_column("ai_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ai_jobs", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE ai_jobs SET updated_at = created_at WHERE updated_at IS NULL")
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    op.create_table(
        "initial_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("input_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_jobs.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["answer_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
        sa.UniqueConstraint("session_id", "input_version", name="uq_initial_analyses_session_version"),
    )


def downgrade() -> None:
    op.drop_table("initial_analyses")
    with op.batch_alter_table("ai_jobs") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("lease_owner")
