"""add canonical candidate state table

Revision ID: 20260417_0008
Revises: 20260417_0007
Create Date: 2026-04-17 18:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_0008"
down_revision = "20260417_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_candidate_state_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_id", sa.String(length=256), nullable=False),
        sa.Column("smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("identity_context_json", sa.JSON(), nullable=False),
        sa.Column("evidence_summary_json", sa.JSON(), nullable=False),
        sa.Column("predictive_summary_json", sa.JSON(), nullable=False),
        sa.Column("recommendation_summary_json", sa.JSON(), nullable=False),
        sa.Column("governance_summary_json", sa.JSON(), nullable=False),
        sa.Column("carryover_summary_json", sa.JSON(), nullable=False),
        sa.Column("trust_summary_json", sa.JSON(), nullable=False),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False),
        sa.Column("source_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
    )
    op.create_index("ix_canonical_candidate_state_records_session_id", "canonical_candidate_state_records", ["session_id"])
    op.create_index("ix_canonical_candidate_state_records_workspace_id", "canonical_candidate_state_records", ["workspace_id"])
    op.create_index("ix_canonical_candidate_state_records_candidate_id", "canonical_candidate_state_records", ["candidate_id"])
    op.create_index("ix_canonical_candidate_state_records_canonical_smiles", "canonical_candidate_state_records", ["canonical_smiles"])
    op.create_index("ix_canonical_candidate_state_records_rank", "canonical_candidate_state_records", ["rank"])


def downgrade() -> None:
    op.drop_index("ix_canonical_candidate_state_records_rank", table_name="canonical_candidate_state_records")
    op.drop_index("ix_canonical_candidate_state_records_canonical_smiles", table_name="canonical_candidate_state_records")
    op.drop_index("ix_canonical_candidate_state_records_candidate_id", table_name="canonical_candidate_state_records")
    op.drop_index("ix_canonical_candidate_state_records_workspace_id", table_name="canonical_candidate_state_records")
    op.drop_index("ix_canonical_candidate_state_records_session_id", table_name="canonical_candidate_state_records")
    op.drop_table("canonical_candidate_state_records")
