"""Add teacher-selected assignment input type.

Revision ID: 20260814_0008
Revises: 20260814_0007
Create Date: 2026-08-14
"""
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0008"
down_revision: Optional[str] = "20260814_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(sa.Column("input_type", sa.String(length=16), nullable=False, server_default="TEXT"))
        batch.create_check_constraint("ck_assignments_input_type", "input_type IN ('TEXT', 'VOICE')")


def downgrade() -> None:
    with op.batch_alter_table("assignments") as batch:
        batch.drop_constraint("ck_assignments_input_type", type_="check")
        batch.drop_column("input_type")
