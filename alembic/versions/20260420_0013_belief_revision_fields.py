"""Add contradiction-aware belief revision fields

Revision ID: 20260420_0013
Revises: 20260420_0012
Create Date: 2026-04-20 13:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_0013"
down_revision = "20260420_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("belief_updates", sa.Column("revision_mode", sa.String(length=64), nullable=False, server_default="bounded_contradiction_aware"))
    op.add_column("belief_updates", sa.Column("contradiction_pressure", sa.String(length=32), nullable=False, server_default="none"))
    op.add_column("belief_updates", sa.Column("support_balance_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("belief_updates", sa.Column("revision_rationale", sa.Text(), nullable=False, server_default=""))
    op.add_column("belief_updates", sa.Column("triggering_contradiction_ids_json", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("belief_updates", sa.Column("triggering_source_summary", sa.Text(), nullable=False, server_default=""))

    op.add_column("belief_states", sa.Column("contradiction_pressure", sa.String(length=32), nullable=False, server_default="none"))
    op.add_column("belief_states", sa.Column("support_balance_summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("belief_states", sa.Column("latest_revision_rationale", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("belief_states", "latest_revision_rationale")
    op.drop_column("belief_states", "support_balance_summary")
    op.drop_column("belief_states", "contradiction_pressure")

    op.drop_column("belief_updates", "triggering_source_summary")
    op.drop_column("belief_updates", "triggering_contradiction_ids_json")
    op.drop_column("belief_updates", "revision_rationale")
    op.drop_column("belief_updates", "support_balance_summary")
    op.drop_column("belief_updates", "contradiction_pressure")
    op.drop_column("belief_updates", "revision_mode")
