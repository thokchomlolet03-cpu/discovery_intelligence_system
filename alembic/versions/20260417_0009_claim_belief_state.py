"""add claim experiment belief tables

Revision ID: 20260417_0009
Revises: 20260417_0008
Create Date: 2026-04-17 20:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_0009"
down_revision = "20260417_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("run_metadata_session_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("claim_scope", sa.String(length=64), nullable=False, server_default="candidate"),
        sa.Column("claim_type", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("claim_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("claim_summary_json", sa.JSON(), nullable=False),
        sa.Column("source_basis", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("support_links_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="active"),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("claim_id"),
    )
    op.create_index("ix_claims_session_id", "claims", ["session_id"])
    op.create_index("ix_claims_workspace_id", "claims", ["workspace_id"])
    op.create_index("ix_claims_claim_id", "claims", ["claim_id"])
    op.create_index("ix_claims_candidate_id", "claims", ["candidate_id"])

    op.create_table(
        "experiment_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("requested_measurement", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="requested"),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_experiment_requests_request_id", "experiment_requests", ["request_id"])
    op.create_index("ix_experiment_requests_claim_id", "experiment_requests", ["claim_id"])

    op.create_table(
        "experiment_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("result_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("observed_value", sa.Float(), nullable=True),
        sa.Column("observed_label", sa.Integer(), nullable=True),
        sa.Column("result_summary_json", sa.JSON(), nullable=False),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="recorded"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("result_id"),
    )
    op.create_index("ix_experiment_results_result_id", "experiment_results", ["result_id"])
    op.create_index("ix_experiment_results_request_id", "experiment_results", ["request_id"])
    op.create_index("ix_experiment_results_claim_id", "experiment_results", ["claim_id"])

    op.create_table(
        "belief_updates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("update_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("result_id", sa.String(length=128), nullable=False),
        sa.Column("update_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("pre_belief_state_json", sa.JSON(), nullable=False),
        sa.Column("post_belief_state_json", sa.JSON(), nullable=False),
        sa.Column("deterministic_rule", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("update_id"),
    )
    op.create_index("ix_belief_updates_update_id", "belief_updates", ["update_id"])
    op.create_index("ix_belief_updates_claim_id", "belief_updates", ["claim_id"])

    op.create_table(
        "belief_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("belief_state_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("current_state", sa.String(length=64), nullable=False, server_default="unresolved"),
        sa.Column("current_strength", sa.String(length=64), nullable=False, server_default="tentative"),
        sa.Column("support_basis_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("latest_update_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="active"),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("belief_state_id"),
    )
    op.create_index("ix_belief_states_belief_state_id", "belief_states", ["belief_state_id"])
    op.create_index("ix_belief_states_claim_id", "belief_states", ["claim_id"])


def downgrade() -> None:
    op.drop_index("ix_belief_states_claim_id", table_name="belief_states")
    op.drop_index("ix_belief_states_belief_state_id", table_name="belief_states")
    op.drop_table("belief_states")
    op.drop_index("ix_belief_updates_claim_id", table_name="belief_updates")
    op.drop_index("ix_belief_updates_update_id", table_name="belief_updates")
    op.drop_table("belief_updates")
    op.drop_index("ix_experiment_results_claim_id", table_name="experiment_results")
    op.drop_index("ix_experiment_results_request_id", table_name="experiment_results")
    op.drop_index("ix_experiment_results_result_id", table_name="experiment_results")
    op.drop_table("experiment_results")
    op.drop_index("ix_experiment_requests_claim_id", table_name="experiment_requests")
    op.drop_index("ix_experiment_requests_request_id", table_name="experiment_requests")
    op.drop_table("experiment_requests")
    op.drop_index("ix_claims_candidate_id", table_name="claims")
    op.drop_index("ix_claims_claim_id", table_name="claims")
    op.drop_index("ix_claims_workspace_id", table_name="claims")
    op.drop_index("ix_claims_session_id", table_name="claims")
    op.drop_table("claims")
