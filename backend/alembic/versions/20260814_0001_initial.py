"""Create students and assignments.

Revision ID: 20260814_0001
Revises:
Create Date: 2026-08-14
"""
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0001"
down_revision: Optional[str] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("grade >= 1 AND grade <= 7", name="ck_students_grade_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_students_grade", "students", ["grade"], unique=False)

    op.create_table(
        "assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("grade >= 1 AND grade <= 7", name="ck_assignments_grade_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assignments_grade", "assignments", ["grade"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assignments_grade", table_name="assignments")
    op.drop_table("assignments")
    op.drop_index("ix_students_grade", table_name="students")
    op.drop_table("students")

