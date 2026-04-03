"""add first-class claim records

Revision ID: 20260402_0006
Revises: 20260329_0005
Create Date: 2026-04-02 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0006"
down_revision = "20260329_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("candidate_id", sa.String(length=256), nullable=False),
        sa.Column("candidate_reference", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("target_definition_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("claim_type", sa.String(length=64), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("bounded_scope", sa.Text(), nullable=False),
        sa.Column("support_level", sa.String(length=32), nullable=False, server_default="limited"),
        sa.Column("evidence_basis_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_recommendation_rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=256), nullable=False, server_default="system"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("workspace_id", "session_id", "candidate_id", "claim_type", name="uq_claims_session_candidate_type"),
    )
    op.create_index(op.f("ix_claims_session_id"), "claims", ["session_id"], unique=False)
    op.create_index(op.f("ix_claims_workspace_id"), "claims", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_claims_created_by_user_id"), "claims", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_claims_candidate_id"), "claims", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_claims_claim_type"), "claims", ["claim_type"], unique=False)
    op.create_index(op.f("ix_claims_support_level"), "claims", ["support_level"], unique=False)
    op.create_index(op.f("ix_claims_status"), "claims", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_claims_status"), table_name="claims")
    op.drop_index(op.f("ix_claims_support_level"), table_name="claims")
    op.drop_index(op.f("ix_claims_claim_type"), table_name="claims")
    op.drop_index(op.f("ix_claims_candidate_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_created_by_user_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_workspace_id"), table_name="claims")
    op.drop_index(op.f("ix_claims_session_id"), table_name="claims")
    op.drop_table("claims")
