"""add belief state records

Revision ID: 20260402_0010
Revises: 20260402_0009
Create Date: 2026-04-02 21:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0010"
down_revision = "20260402_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "belief_states",
        sa.Column("belief_state_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("target_key", sa.String(length=512), nullable=False),
        sa.Column("target_definition_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("summary_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("active_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("supported_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weakened_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unresolved_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_update_source", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("latest_belief_update_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("support_distribution_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("governance_scope_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("belief_state_id"),
        sa.UniqueConstraint("workspace_id", "target_key", name="uq_belief_states_workspace_target"),
    )
    op.create_index(op.f("ix_belief_states_workspace_id"), "belief_states", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_belief_states_target_key"), "belief_states", ["target_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_belief_states_target_key"), table_name="belief_states")
    op.drop_index(op.f("ix_belief_states_workspace_id"), table_name="belief_states")
    op.drop_table("belief_states")
