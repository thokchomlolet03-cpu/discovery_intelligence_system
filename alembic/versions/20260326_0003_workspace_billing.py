"""add workspace billing foundations

Revision ID: 20260326_0003
Revises: 20260326_0002
Create Date: 2026-03-26 02:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_0003"
down_revision = "20260326_0002"
branch_labels = None
depends_on = None

LEGACY_WORKSPACE_ID = "legacy_workspace"


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(sa.Column("plan_tier", sa.String(length=32), nullable=False, server_default="free"))
        batch_op.add_column(sa.Column("plan_status", sa.String(length=32), nullable=False, server_default="active"))
        batch_op.add_column(sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("external_subscription_ref", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("billing_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch_op.create_index(op.f("ix_workspaces_plan_tier"), ["plan_tier"], unique=False)
        batch_op.create_index(op.f("ix_workspaces_plan_status"), ["plan_status"], unique=False)
        batch_op.create_index(op.f("ix_workspaces_external_subscription_ref"), ["external_subscription_ref"], unique=False)

    op.create_table(
        "workspace_usage_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("job_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspace_usage_events_workspace_id"), "workspace_usage_events", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_workspace_usage_events_event_type"), "workspace_usage_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_workspace_usage_events_created_at"), "workspace_usage_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_workspace_usage_events_session_id"), "workspace_usage_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_workspace_usage_events_job_id"), "workspace_usage_events", ["job_id"], unique=False)

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE workspaces
            SET plan_tier = CASE WHEN workspace_id = :legacy_workspace_id THEN 'internal' ELSE 'free' END,
                plan_status = 'active'
            """
        ),
        {"legacy_workspace_id": LEGACY_WORKSPACE_ID},
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workspace_usage_events_job_id"), table_name="workspace_usage_events")
    op.drop_index(op.f("ix_workspace_usage_events_session_id"), table_name="workspace_usage_events")
    op.drop_index(op.f("ix_workspace_usage_events_created_at"), table_name="workspace_usage_events")
    op.drop_index(op.f("ix_workspace_usage_events_event_type"), table_name="workspace_usage_events")
    op.drop_index(op.f("ix_workspace_usage_events_workspace_id"), table_name="workspace_usage_events")
    op.drop_table("workspace_usage_events")

    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_index(op.f("ix_workspaces_external_subscription_ref"))
        batch_op.drop_index(op.f("ix_workspaces_plan_status"))
        batch_op.drop_index(op.f("ix_workspaces_plan_tier"))
        batch_op.drop_column("billing_metadata")
        batch_op.drop_column("external_subscription_ref")
        batch_op.drop_column("current_period_ends_at")
        batch_op.drop_column("trial_ends_at")
        batch_op.drop_column("plan_status")
        batch_op.drop_column("plan_tier")
