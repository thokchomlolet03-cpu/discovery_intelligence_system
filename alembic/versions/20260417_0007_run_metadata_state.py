"""add canonical run metadata table

Revision ID: 20260417_0007
Revises: 20260417_0006
Create Date: 2026-04-17 16:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_0007"
down_revision = "20260417_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_run_metadata_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("source_name", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("input_type", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("decision_intent", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("modeling_mode", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("scoring_mode", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("run_contract_json", sa.JSON(), nullable=False),
        sa.Column("comparison_anchors_json", sa.JSON(), nullable=False),
        sa.Column("ranking_policy_json", sa.JSON(), nullable=False),
        sa.Column("ranking_diagnostics_json", sa.JSON(), nullable=False),
        sa.Column("trust_summary_json", sa.JSON(), nullable=False),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False),
        sa.Column("source_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_canonical_run_metadata_records_workspace_id", "canonical_run_metadata_records", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_canonical_run_metadata_records_workspace_id", table_name="canonical_run_metadata_records")
    op.drop_table("canonical_run_metadata_records")
