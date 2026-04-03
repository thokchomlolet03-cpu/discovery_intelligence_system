"""add experiment request records

Revision ID: 20260402_0007
Revises: 20260402_0006
Create Date: 2026-04-02 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0007"
down_revision = "20260402_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_requests",
        sa.Column("experiment_request_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_id", sa.String(length=256), nullable=False),
        sa.Column("candidate_reference", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("target_definition_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("requested_measurement", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("requested_direction", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("rationale_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority_tier", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by", sa.String(length=256), nullable=False, server_default="system"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.claim_id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("experiment_request_id"),
        sa.UniqueConstraint("workspace_id", "session_id", "claim_id", name="uq_experiment_requests_session_claim"),
    )
    op.create_index(op.f("ix_experiment_requests_session_id"), "experiment_requests", ["session_id"], unique=False)
    op.create_index(op.f("ix_experiment_requests_workspace_id"), "experiment_requests", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_experiment_requests_claim_id"), "experiment_requests", ["claim_id"], unique=False)
    op.create_index(op.f("ix_experiment_requests_requested_by_user_id"), "experiment_requests", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_experiment_requests_candidate_id"), "experiment_requests", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_experiment_requests_priority_tier"), "experiment_requests", ["priority_tier"], unique=False)
    op.create_index(op.f("ix_experiment_requests_status"), "experiment_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_experiment_requests_status"), table_name="experiment_requests")
    op.drop_index(op.f("ix_experiment_requests_priority_tier"), table_name="experiment_requests")
    op.drop_index(op.f("ix_experiment_requests_candidate_id"), table_name="experiment_requests")
    op.drop_index(op.f("ix_experiment_requests_requested_by_user_id"), table_name="experiment_requests")
    op.drop_index(op.f("ix_experiment_requests_claim_id"), table_name="experiment_requests")
    op.drop_index(op.f("ix_experiment_requests_workspace_id"), table_name="experiment_requests")
    op.drop_index(op.f("ix_experiment_requests_session_id"), table_name="experiment_requests")
    op.drop_table("experiment_requests")
