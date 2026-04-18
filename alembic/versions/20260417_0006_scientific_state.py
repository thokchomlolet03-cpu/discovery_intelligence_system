"""add canonical scientific state tables

Revision ID: 20260417_0006
Revises: 20260329_0005
Create Date: 2026-04-17 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_0006"
down_revision = "20260329_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "target_definition_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("target_name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("target_kind", sa.String(length=64), nullable=False, server_default="classification"),
        sa.Column("optimization_direction", sa.String(length=64), nullable=False, server_default="classify"),
        sa.Column("measurement_column", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("label_column", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("measurement_unit", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("scientific_meaning", sa.Text(), nullable=False, server_default=""),
        sa.Column("assay_context", sa.Text(), nullable=False, server_default=""),
        sa.Column("dataset_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("mapping_confidence", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("success_definition", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_target_definition_records_workspace_id", "target_definition_records", ["workspace_id"])

    op.create_table(
        "evidence_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("candidate_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("assay", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("target_name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("observed_value", sa.Float(), nullable=True),
        sa.Column("observed_label", sa.Integer(), nullable=True),
        sa.Column("source_row_index", sa.Integer(), nullable=True),
        sa.Column("source_column", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
    )
    op.create_index("ix_evidence_records_session_id", "evidence_records", ["session_id"])
    op.create_index("ix_evidence_records_workspace_id", "evidence_records", ["workspace_id"])
    op.create_index("ix_evidence_records_evidence_type", "evidence_records", ["evidence_type"])
    op.create_index("ix_evidence_records_candidate_id", "evidence_records", ["candidate_id"])
    op.create_index("ix_evidence_records_canonical_smiles", "evidence_records", ["canonical_smiles"])

    op.create_table(
        "model_output_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_id", sa.String(length=256), nullable=False),
        sa.Column("smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("model_family", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("model_kind", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("calibration_method", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("training_scope", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("model_source", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("model_source_role", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("baseline_fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("bridge_state_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("predicted_value", sa.Float(), nullable=True),
        sa.Column("prediction_dispersion", sa.Float(), nullable=True),
        sa.Column("novelty", sa.Float(), nullable=True),
        sa.Column("applicability_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("diagnostics_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
    )
    op.create_index("ix_model_output_records_session_id", "model_output_records", ["session_id"])
    op.create_index("ix_model_output_records_workspace_id", "model_output_records", ["workspace_id"])
    op.create_index("ix_model_output_records_candidate_id", "model_output_records", ["candidate_id"])
    op.create_index("ix_model_output_records_canonical_smiles", "model_output_records", ["canonical_smiles"])

    op.create_table(
        "recommendation_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_id", sa.String(length=256), nullable=False),
        sa.Column("smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decision_intent", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("modeling_mode", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("scoring_mode", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("bucket", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("risk", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="suggested"),
        sa.Column("priority_score", sa.Float(), nullable=True),
        sa.Column("experiment_value", sa.Float(), nullable=True),
        sa.Column("acquisition_score", sa.Float(), nullable=True),
        sa.Column("rationale_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("rationale_json", sa.JSON(), nullable=False),
        sa.Column("policy_trace_json", sa.JSON(), nullable=False),
        sa.Column("recommendation_json", sa.JSON(), nullable=False),
        sa.Column("normalized_explanation_json", sa.JSON(), nullable=False),
        sa.Column("governance_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
    )
    op.create_index("ix_recommendation_records_session_id", "recommendation_records", ["session_id"])
    op.create_index("ix_recommendation_records_workspace_id", "recommendation_records", ["workspace_id"])
    op.create_index("ix_recommendation_records_candidate_id", "recommendation_records", ["candidate_id"])
    op.create_index("ix_recommendation_records_canonical_smiles", "recommendation_records", ["canonical_smiles"])
    op.create_index("ix_recommendation_records_rank", "recommendation_records", ["rank"])
    op.create_index("ix_recommendation_records_status", "recommendation_records", ["status"])

    op.create_table(
        "carryover_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("source_session_id", sa.String(length=128), nullable=False),
        sa.Column("source_candidate_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("target_candidate_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, server_default=""),
        sa.Column("carryover_kind", sa.String(length=64), nullable=False, server_default="review_memory"),
        sa.Column("match_basis", sa.String(length=64), nullable=False, server_default="canonical_smiles"),
        sa.Column("review_event_id", sa.Integer(), nullable=True),
        sa.Column("source_status", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source_action", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_reviewer", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("source_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["source_session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["review_event_id"], ["review_events.id"]),
    )
    op.create_index("ix_carryover_records_workspace_id", "carryover_records", ["workspace_id"])
    op.create_index("ix_carryover_records_session_id", "carryover_records", ["session_id"])
    op.create_index("ix_carryover_records_source_session_id", "carryover_records", ["source_session_id"])
    op.create_index("ix_carryover_records_canonical_smiles", "carryover_records", ["canonical_smiles"])


def downgrade() -> None:
    op.drop_index("ix_carryover_records_canonical_smiles", table_name="carryover_records")
    op.drop_index("ix_carryover_records_source_session_id", table_name="carryover_records")
    op.drop_index("ix_carryover_records_session_id", table_name="carryover_records")
    op.drop_index("ix_carryover_records_workspace_id", table_name="carryover_records")
    op.drop_table("carryover_records")

    op.drop_index("ix_recommendation_records_status", table_name="recommendation_records")
    op.drop_index("ix_recommendation_records_rank", table_name="recommendation_records")
    op.drop_index("ix_recommendation_records_canonical_smiles", table_name="recommendation_records")
    op.drop_index("ix_recommendation_records_candidate_id", table_name="recommendation_records")
    op.drop_index("ix_recommendation_records_workspace_id", table_name="recommendation_records")
    op.drop_index("ix_recommendation_records_session_id", table_name="recommendation_records")
    op.drop_table("recommendation_records")

    op.drop_index("ix_model_output_records_canonical_smiles", table_name="model_output_records")
    op.drop_index("ix_model_output_records_candidate_id", table_name="model_output_records")
    op.drop_index("ix_model_output_records_workspace_id", table_name="model_output_records")
    op.drop_index("ix_model_output_records_session_id", table_name="model_output_records")
    op.drop_table("model_output_records")

    op.drop_index("ix_evidence_records_canonical_smiles", table_name="evidence_records")
    op.drop_index("ix_evidence_records_candidate_id", table_name="evidence_records")
    op.drop_index("ix_evidence_records_evidence_type", table_name="evidence_records")
    op.drop_index("ix_evidence_records_workspace_id", table_name="evidence_records")
    op.drop_index("ix_evidence_records_session_id", table_name="evidence_records")
    op.drop_table("evidence_records")

    op.drop_index("ix_target_definition_records_workspace_id", table_name="target_definition_records")
    op.drop_table("target_definition_records")
