"""add claim evidence links

Revision ID: 20260419_0010
Revises: 20260417_0009
Create Date: 2026-04-19 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_0010"
down_revision = "20260417_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claim_evidence_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("link_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("linked_object_type", sa.String(length=64), nullable=False),
        sa.Column("linked_object_id", sa.String(length=128), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("link_id"),
    )
    op.create_index("ix_claim_evidence_links_link_id", "claim_evidence_links", ["link_id"])
    op.create_index("ix_claim_evidence_links_session_id", "claim_evidence_links", ["session_id"])
    op.create_index("ix_claim_evidence_links_workspace_id", "claim_evidence_links", ["workspace_id"])
    op.create_index("ix_claim_evidence_links_claim_id", "claim_evidence_links", ["claim_id"])
    op.create_index("ix_claim_evidence_links_linked_object_type", "claim_evidence_links", ["linked_object_type"])
    op.create_index("ix_claim_evidence_links_relation_type", "claim_evidence_links", ["relation_type"])


def downgrade() -> None:
    op.drop_index("ix_claim_evidence_links_relation_type", table_name="claim_evidence_links")
    op.drop_index("ix_claim_evidence_links_linked_object_type", table_name="claim_evidence_links")
    op.drop_index("ix_claim_evidence_links_claim_id", table_name="claim_evidence_links")
    op.drop_index("ix_claim_evidence_links_workspace_id", table_name="claim_evidence_links")
    op.drop_index("ix_claim_evidence_links_session_id", table_name="claim_evidence_links")
    op.drop_index("ix_claim_evidence_links_link_id", table_name="claim_evidence_links")
    op.drop_table("claim_evidence_links")
