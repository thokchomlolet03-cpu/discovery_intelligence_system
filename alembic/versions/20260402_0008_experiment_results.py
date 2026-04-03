"""add experiment result records

Revision ID: 20260402_0008
Revises: 20260402_0007
Create Date: 2026-04-02 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0008"
down_revision = "20260402_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_results",
        sa.Column("experiment_result_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("source_experiment_request_id", sa.String(length=128), nullable=True),
        sa.Column("source_claim_id", sa.String(length=128), nullable=True),
        sa.Column("ingested_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_id", sa.String(length=256), nullable=False),
        sa.Column("candidate_reference", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("target_definition_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("observed_value", sa.Float(), nullable=True),
        sa.Column("observed_label", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("measurement_unit", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("assay_context", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_quality", sa.String(length=32), nullable=False, server_default="provisional"),
        sa.Column("result_source", sa.String(length=32), nullable=False, server_default="manual_entry"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_by", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["ingested_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["source_claim_id"], ["claims.claim_id"]),
        sa.ForeignKeyConstraint(["source_experiment_request_id"], ["experiment_requests.experiment_request_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("experiment_result_id"),
    )
    op.create_index(op.f("ix_experiment_results_session_id"), "experiment_results", ["session_id"], unique=False)
    op.create_index(op.f("ix_experiment_results_workspace_id"), "experiment_results", ["workspace_id"], unique=False)
    op.create_index(
        op.f("ix_experiment_results_source_experiment_request_id"),
        "experiment_results",
        ["source_experiment_request_id"],
        unique=False,
    )
    op.create_index(op.f("ix_experiment_results_source_claim_id"), "experiment_results", ["source_claim_id"], unique=False)
    op.create_index(op.f("ix_experiment_results_ingested_by_user_id"), "experiment_results", ["ingested_by_user_id"], unique=False)
    op.create_index(op.f("ix_experiment_results_candidate_id"), "experiment_results", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_experiment_results_result_quality"), "experiment_results", ["result_quality"], unique=False)
    op.create_index(op.f("ix_experiment_results_result_source"), "experiment_results", ["result_source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_experiment_results_result_source"), table_name="experiment_results")
    op.drop_index(op.f("ix_experiment_results_result_quality"), table_name="experiment_results")
    op.drop_index(op.f("ix_experiment_results_candidate_id"), table_name="experiment_results")
    op.drop_index(op.f("ix_experiment_results_ingested_by_user_id"), table_name="experiment_results")
    op.drop_index(op.f("ix_experiment_results_source_claim_id"), table_name="experiment_results")
    op.drop_index(op.f("ix_experiment_results_source_experiment_request_id"), table_name="experiment_results")
    op.drop_index(op.f("ix_experiment_results_workspace_id"), table_name="experiment_results")
    op.drop_index(op.f("ix_experiment_results_session_id"), table_name="experiment_results")
    op.drop_table("experiment_results")
