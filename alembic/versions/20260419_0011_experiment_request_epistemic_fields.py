"""Add epistemic experiment request fields

Revision ID: 20260419_0011
Revises: 20260419_0010
Create Date: 2026-04-19 18:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_0011"
down_revision = "20260419_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiment_requests", sa.Column("tested_claim_id", sa.String(length=128), nullable=False, server_default=""))
    op.add_column("experiment_requests", sa.Column("experiment_intent", sa.String(length=128), nullable=False, server_default=""))
    op.add_column("experiment_requests", sa.Column("epistemic_goal_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("experiment_requests", sa.Column("existing_context_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("experiment_requests", sa.Column("strengthening_outcome_description", sa.Text(), nullable=False, server_default=""))
    op.add_column("experiment_requests", sa.Column("weakening_outcome_description", sa.Text(), nullable=False, server_default=""))
    op.add_column("experiment_requests", sa.Column("expected_learning_value", sa.Text(), nullable=False, server_default=""))
    op.add_column("experiment_requests", sa.Column("linked_claim_evidence_snapshot_json", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("experiment_requests", sa.Column("protocol_context_summary", sa.Text(), nullable=False, server_default=""))
    op.create_index("ix_experiment_requests_tested_claim_id", "experiment_requests", ["tested_claim_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_experiment_requests_tested_claim_id", table_name="experiment_requests")
    op.drop_column("experiment_requests", "protocol_context_summary")
    op.drop_column("experiment_requests", "linked_claim_evidence_snapshot_json")
    op.drop_column("experiment_requests", "expected_learning_value")
    op.drop_column("experiment_requests", "weakening_outcome_description")
    op.drop_column("experiment_requests", "strengthening_outcome_description")
    op.drop_column("experiment_requests", "existing_context_summary")
    op.drop_column("experiment_requests", "epistemic_goal_summary")
    op.drop_column("experiment_requests", "experiment_intent")
    op.drop_column("experiment_requests", "tested_claim_id")
