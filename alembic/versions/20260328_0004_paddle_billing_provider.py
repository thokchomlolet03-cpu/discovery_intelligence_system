"""add paddle billing linkage and webhook event storage

Revision ID: 20260328_0004
Revises: 20260326_0003
Create Date: 2026-03-28 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0004"
down_revision = "20260326_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(sa.Column("external_billing_provider", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("external_customer_ref", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("external_price_ref", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("provider_subscription_status", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("billing_synced_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(op.f("ix_workspaces_external_billing_provider"), ["external_billing_provider"], unique=False)
        batch_op.create_index(op.f("ix_workspaces_external_customer_ref"), ["external_customer_ref"], unique=False)
        batch_op.create_index(op.f("ix_workspaces_provider_subscription_status"), ["provider_subscription_status"], unique=False)

    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=256), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_id", name="uq_billing_webhook_events_provider_event"),
    )
    op.create_index(op.f("ix_billing_webhook_events_provider"), "billing_webhook_events", ["provider"], unique=False)
    op.create_index(op.f("ix_billing_webhook_events_event_id"), "billing_webhook_events", ["event_id"], unique=False)
    op.create_index(op.f("ix_billing_webhook_events_event_type"), "billing_webhook_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_billing_webhook_events_workspace_id"), "billing_webhook_events", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_billing_webhook_events_workspace_id"), table_name="billing_webhook_events")
    op.drop_index(op.f("ix_billing_webhook_events_event_type"), table_name="billing_webhook_events")
    op.drop_index(op.f("ix_billing_webhook_events_event_id"), table_name="billing_webhook_events")
    op.drop_index(op.f("ix_billing_webhook_events_provider"), table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")

    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_index(op.f("ix_workspaces_provider_subscription_status"))
        batch_op.drop_index(op.f("ix_workspaces_external_customer_ref"))
        batch_op.drop_index(op.f("ix_workspaces_external_billing_provider"))
        batch_op.drop_column("billing_synced_at")
        batch_op.drop_column("provider_subscription_status")
        batch_op.drop_column("external_price_ref")
        batch_op.drop_column("external_customer_ref")
        batch_op.drop_column("external_billing_provider")
