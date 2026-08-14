"""Add uniform AI run debug fields.

Revision ID: 20260814_0003
Revises: 20260814_0002
Create Date: 2026-08-14
"""
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0003"
down_revision: Optional[str] = "20260814_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("ai_runs")}
    if "output_summary" not in columns:
        op.add_column("ai_runs", sa.Column("output_summary", sa.Text(), nullable=True))
    if "duration_ms" not in columns:
        op.add_column("ai_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("ai_runs")}
    if "duration_ms" in columns:
        op.drop_column("ai_runs", "duration_ms")
    if "output_summary" in columns:
        op.drop_column("ai_runs", "output_summary")
