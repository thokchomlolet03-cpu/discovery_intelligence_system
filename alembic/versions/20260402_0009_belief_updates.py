"""add belief update records

Revision ID: 20260402_0009
Revises: 20260402_0008
Create Date: 2026-04-02 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0009"
down_revision = "20260402_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "belief_updates",
        sa.Column("belief_update_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("experiment_result_id", sa.String(length=128), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("candidate_label", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("previous_support_level", sa.String(length=32), nullable=False, server_default="limited"),
        sa.Column("updated_support_level", sa.String(length=32), nullable=False, server_default="limited"),
        sa.Column("update_direction", sa.String(length=32), nullable=False, server_default="unresolved"),
        sa.Column("update_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("governance_status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.claim_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["experiment_result_id"], ["experiment_results.experiment_result_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("belief_update_id"),
        sa.UniqueConstraint("workspace_id", "claim_id", "experiment_result_id", name="uq_belief_updates_claim_result"),
    )
    op.create_index(op.f("ix_belief_updates_session_id"), "belief_updates", ["session_id"], unique=False)
    op.create_index(op.f("ix_belief_updates_workspace_id"), "belief_updates", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_belief_updates_claim_id"), "belief_updates", ["claim_id"], unique=False)
    op.create_index(op.f("ix_belief_updates_experiment_result_id"), "belief_updates", ["experiment_result_id"], unique=False)
    op.create_index(op.f("ix_belief_updates_created_by_user_id"), "belief_updates", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_belief_updates_candidate_id"), "belief_updates", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_belief_updates_previous_support_level"), "belief_updates", ["previous_support_level"], unique=False)
    op.create_index(op.f("ix_belief_updates_updated_support_level"), "belief_updates", ["updated_support_level"], unique=False)
    op.create_index(op.f("ix_belief_updates_update_direction"), "belief_updates", ["update_direction"], unique=False)
    op.create_index(op.f("ix_belief_updates_governance_status"), "belief_updates", ["governance_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_belief_updates_governance_status"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_update_direction"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_updated_support_level"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_previous_support_level"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_candidate_id"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_created_by_user_id"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_experiment_result_id"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_claim_id"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_workspace_id"), table_name="belief_updates")
    op.drop_index(op.f("ix_belief_updates_session_id"), table_name="belief_updates")
    op.drop_table("belief_updates")
