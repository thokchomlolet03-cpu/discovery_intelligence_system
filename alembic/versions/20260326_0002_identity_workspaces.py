"""add identity and workspace scoping

Revision ID: 20260326_0002
Revises: 20260326_0001
Create Date: 2026-03-26 01:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_0002"
down_revision = "20260326_0001"
branch_labels = None
depends_on = None

LEGACY_WORKSPACE_ID = "legacy_workspace"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("owner_user_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    op.create_index(op.f("ix_workspaces_owner_user_id"), "workspaces", ["owner_user_id"], unique=False)

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_memberships_workspace_user"),
    )
    op.create_index(op.f("ix_workspace_memberships_user_id"), "workspace_memberships", ["user_id"], unique=False)
    op.create_index(op.f("ix_workspace_memberships_workspace_id"), "workspace_memberships", ["workspace_id"], unique=False)

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO workspaces (workspace_id, name, owner_user_id, created_at, updated_at)
            VALUES (:workspace_id, :name, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"workspace_id": LEGACY_WORKSPACE_ID, "name": "Legacy Workspace"},
    )

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(
            sa.Column("workspace_id", sa.String(length=128), nullable=False, server_default=LEGACY_WORKSPACE_ID)
        )
        batch_op.add_column(sa.Column("created_by_user_id", sa.String(length=128), nullable=True))
        batch_op.create_index(op.f("ix_sessions_workspace_id"), ["workspace_id"], unique=False)
        batch_op.create_index(op.f("ix_sessions_created_by_user_id"), ["created_by_user_id"], unique=False)
        batch_op.create_foreign_key("fk_sessions_workspace_id_workspaces", "workspaces", ["workspace_id"], ["workspace_id"])
        batch_op.create_foreign_key("fk_sessions_created_by_user_id_users", "users", ["created_by_user_id"], ["user_id"])

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(
            sa.Column("workspace_id", sa.String(length=128), nullable=False, server_default=LEGACY_WORKSPACE_ID)
        )
        batch_op.add_column(sa.Column("created_by_user_id", sa.String(length=128), nullable=True))
        batch_op.create_index(op.f("ix_jobs_workspace_id"), ["workspace_id"], unique=False)
        batch_op.create_index(op.f("ix_jobs_created_by_user_id"), ["created_by_user_id"], unique=False)
        batch_op.create_foreign_key("fk_jobs_workspace_id_workspaces", "workspaces", ["workspace_id"], ["workspace_id"])
        batch_op.create_foreign_key("fk_jobs_created_by_user_id_users", "users", ["created_by_user_id"], ["user_id"])

    with op.batch_alter_table("review_events") as batch_op:
        batch_op.add_column(
            sa.Column("workspace_id", sa.String(length=128), nullable=False, server_default=LEGACY_WORKSPACE_ID)
        )
        batch_op.add_column(sa.Column("actor_user_id", sa.String(length=128), nullable=True))
        batch_op.create_index(op.f("ix_review_events_workspace_id"), ["workspace_id"], unique=False)
        batch_op.create_index(op.f("ix_review_events_actor_user_id"), ["actor_user_id"], unique=False)
        batch_op.create_foreign_key("fk_review_events_workspace_id_workspaces", "workspaces", ["workspace_id"], ["workspace_id"])
        batch_op.create_foreign_key("fk_review_events_actor_user_id_users", "users", ["actor_user_id"], ["user_id"])

    with op.batch_alter_table("artifact_records") as batch_op:
        batch_op.add_column(
            sa.Column("workspace_id", sa.String(length=128), nullable=False, server_default=LEGACY_WORKSPACE_ID)
        )
        batch_op.add_column(sa.Column("created_by_user_id", sa.String(length=128), nullable=True))
        batch_op.create_index(op.f("ix_artifact_records_workspace_id"), ["workspace_id"], unique=False)
        batch_op.create_index(op.f("ix_artifact_records_created_by_user_id"), ["created_by_user_id"], unique=False)
        batch_op.create_foreign_key("fk_artifact_records_workspace_id_workspaces", "workspaces", ["workspace_id"], ["workspace_id"])
        batch_op.create_foreign_key("fk_artifact_records_created_by_user_id_users", "users", ["created_by_user_id"], ["user_id"])


def downgrade() -> None:
    with op.batch_alter_table("artifact_records") as batch_op:
        batch_op.drop_constraint("fk_artifact_records_created_by_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_artifact_records_workspace_id_workspaces", type_="foreignkey")
        batch_op.drop_index(op.f("ix_artifact_records_created_by_user_id"))
        batch_op.drop_index(op.f("ix_artifact_records_workspace_id"))
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("workspace_id")

    with op.batch_alter_table("review_events") as batch_op:
        batch_op.drop_constraint("fk_review_events_actor_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_review_events_workspace_id_workspaces", type_="foreignkey")
        batch_op.drop_index(op.f("ix_review_events_actor_user_id"))
        batch_op.drop_index(op.f("ix_review_events_workspace_id"))
        batch_op.drop_column("actor_user_id")
        batch_op.drop_column("workspace_id")

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("fk_jobs_created_by_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_jobs_workspace_id_workspaces", type_="foreignkey")
        batch_op.drop_index(op.f("ix_jobs_created_by_user_id"))
        batch_op.drop_index(op.f("ix_jobs_workspace_id"))
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("workspace_id")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_constraint("fk_sessions_created_by_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_sessions_workspace_id_workspaces", type_="foreignkey")
        batch_op.drop_index(op.f("ix_sessions_created_by_user_id"))
        batch_op.drop_index(op.f("ix_sessions_workspace_id"))
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("workspace_id")

    op.drop_index(op.f("ix_workspace_memberships_workspace_id"), table_name="workspace_memberships")
    op.drop_index(op.f("ix_workspace_memberships_user_id"), table_name="workspace_memberships")
    op.drop_table("workspace_memberships")

    op.drop_index(op.f("ix_workspaces_owner_user_id"), table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
