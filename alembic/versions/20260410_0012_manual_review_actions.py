"""add manual review action fields

Revision ID: 20260410_0012
Revises: 20260410_0011
Create Date: 2026-04-10 18:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_0012"
down_revision = "20260410_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "governed_review_records",
        sa.Column("review_origin_label", sa.String(length=32), nullable=False, server_default="derived"),
    )
    op.add_column(
        "governed_review_records",
        sa.Column("manual_action_label", sa.String(length=128), nullable=False, server_default=""),
    )
    op.add_column(
        "governed_review_records",
        sa.Column("reviewer_label", sa.String(length=256), nullable=False, server_default=""),
    )
    op.add_column(
        "governed_review_records",
        sa.Column("reviewer_user_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        op.f("ix_governed_review_records_review_origin_label"),
        "governed_review_records",
        ["review_origin_label"],
        unique=False,
    )
    op.create_index(
        op.f("ix_governed_review_records_reviewer_user_id"),
        "governed_review_records",
        ["reviewer_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_governed_review_records_reviewer_user_id_users",
        "governed_review_records",
        "users",
        ["reviewer_user_id"],
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_governed_review_records_reviewer_user_id_users",
        "governed_review_records",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_governed_review_records_reviewer_user_id"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_review_origin_label"), table_name="governed_review_records")
    op.drop_column("governed_review_records", "reviewer_user_id")
    op.drop_column("governed_review_records", "reviewer_label")
    op.drop_column("governed_review_records", "manual_action_label")
    op.drop_column("governed_review_records", "review_origin_label")
