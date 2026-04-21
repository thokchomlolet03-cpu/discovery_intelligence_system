"""Add material goal specification state

Revision ID: 20260421_0014
Revises: 20260420_0013
Create Date: 2026-04-21 11:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260421_0014"
down_revision = "20260420_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_goal_specifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("raw_user_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("domain_scope", sa.String(length=64), nullable=False, server_default="polymer_material"),
        sa.Column("requirement_status", sa.String(length=64), nullable=False, server_default="insufficient_needs_clarification"),
        sa.Column("structured_requirements_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("missing_critical_requirements_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("clarification_questions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("scientific_target_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("provenance_markers_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_id"),
    )
    op.create_index("ix_material_goal_specifications_session_id", "material_goal_specifications", ["session_id"], unique=False)
    op.create_index("ix_material_goal_specifications_workspace_id", "material_goal_specifications", ["workspace_id"], unique=False)
    op.create_index("ix_material_goal_specifications_requirement_status", "material_goal_specifications", ["requirement_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_material_goal_specifications_requirement_status", table_name="material_goal_specifications")
    op.drop_index("ix_material_goal_specifications_workspace_id", table_name="material_goal_specifications")
    op.drop_index("ix_material_goal_specifications_session_id", table_name="material_goal_specifications")
    op.drop_table("material_goal_specifications")
