"""add structured job progress fields

Revision ID: 20260329_0005
Revises: 20260328_0004
Create Date: 2026-03-29 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329_0005"
down_revision = "20260328_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(
            sa.Column("progress_stage", sa.String(length=64), nullable=False, server_default=sa.text("'queued'"))
        )
        batch_op.add_column(sa.Column("progress_percent", sa.Integer(), nullable=False, server_default=sa.text("0")))

    op.execute("UPDATE jobs SET progress_stage = 'queued' WHERE progress_stage IS NULL OR progress_stage = ''")
    op.execute("UPDATE jobs SET progress_percent = 0 WHERE progress_percent IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("progress_percent")
        batch_op.drop_column("progress_stage")
