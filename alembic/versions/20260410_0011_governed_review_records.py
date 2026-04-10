"""add governed review records

Revision ID: 20260410_0011
Revises: 20260402_0010
Create Date: 2026-04-10 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_0011"
down_revision = "20260402_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governed_review_records",
        sa.Column("review_record_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=256), nullable=False),
        sa.Column("target_key", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("candidate_id", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("source_class_label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("provenance_confidence_label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("trust_tier_label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("review_status_label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("review_reason_label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("review_reason_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("promotion_gate_status_label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("promotion_block_reason_label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("decision_outcome", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("decision_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("supersedes_review_record_id", sa.String(length=128), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(length=256), nullable=False, server_default="system"),
        sa.Column("actor_user_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("review_record_id"),
    )
    op.create_index(op.f("ix_governed_review_records_workspace_id"), "governed_review_records", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_governed_review_records_session_id"), "governed_review_records", ["session_id"], unique=False)
    op.create_index(op.f("ix_governed_review_records_subject_type"), "governed_review_records", ["subject_type"], unique=False)
    op.create_index(op.f("ix_governed_review_records_subject_id"), "governed_review_records", ["subject_id"], unique=False)
    op.create_index(op.f("ix_governed_review_records_target_key"), "governed_review_records", ["target_key"], unique=False)
    op.create_index(op.f("ix_governed_review_records_candidate_id"), "governed_review_records", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_governed_review_records_active"), "governed_review_records", ["active"], unique=False)
    op.create_index(op.f("ix_governed_review_records_trust_tier_label"), "governed_review_records", ["trust_tier_label"], unique=False)
    op.create_index(op.f("ix_governed_review_records_review_status_label"), "governed_review_records", ["review_status_label"], unique=False)
    op.create_index(op.f("ix_governed_review_records_decision_outcome"), "governed_review_records", ["decision_outcome"], unique=False)
    op.create_index(op.f("ix_governed_review_records_supersedes_review_record_id"), "governed_review_records", ["supersedes_review_record_id"], unique=False)
    op.create_index(op.f("ix_governed_review_records_recorded_at"), "governed_review_records", ["recorded_at"], unique=False)
    op.create_index(op.f("ix_governed_review_records_actor_user_id"), "governed_review_records", ["actor_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_governed_review_records_actor_user_id"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_recorded_at"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_supersedes_review_record_id"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_decision_outcome"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_review_status_label"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_trust_tier_label"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_active"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_candidate_id"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_target_key"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_subject_id"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_subject_type"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_session_id"), table_name="governed_review_records")
    op.drop_index(op.f("ix_governed_review_records_workspace_id"), table_name="governed_review_records")
    op.drop_table("governed_review_records")
