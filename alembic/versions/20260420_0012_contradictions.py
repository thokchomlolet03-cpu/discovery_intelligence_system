"""Add contradiction scientific state table

Revision ID: 20260420_0012
Revises: 20260419_0011
Create Date: 2026-04-20 11:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_0012"
down_revision = "20260419_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contradictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contradiction_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("claim_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("contradiction_scope", sa.String(length=64), nullable=False, server_default="claim"),
        sa.Column("contradiction_type", sa.String(length=64), nullable=False, server_default="support_structure_conflict"),
        sa.Column("source_object_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source_object_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contradiction_id"),
    )
    op.create_index("ix_contradictions_claim_id", "contradictions", ["claim_id"], unique=False)
    op.create_index("ix_contradictions_session_id", "contradictions", ["session_id"], unique=False)
    op.create_index("ix_contradictions_workspace_id", "contradictions", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_contradictions_workspace_id", table_name="contradictions")
    op.drop_index("ix_contradictions_session_id", table_name="contradictions")
    op.drop_index("ix_contradictions_claim_id", table_name="contradictions")
    op.drop_table("contradictions")
