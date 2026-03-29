"""create control plane metadata tables

Revision ID: 20260326_0001
Revises: None
Create Date: 2026-03-26 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_name", sa.String(length=512), nullable=False),
        sa.Column("input_type", sa.String(length=128), nullable=False),
        sa.Column("latest_job_id", sa.String(length=128), nullable=True),
        sa.Column("upload_metadata", sa.JSON(), nullable=False),
        sa.Column("summary_metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("progress_message", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("artifact_refs", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(op.f("ix_jobs_session_id"), "jobs", ["session_id"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)

    op.create_table(
        "review_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_id", sa.String(length=256), nullable=False),
        sa.Column("smiles", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=256), nullable=False),
        sa.Column("reviewer", sa.String(length=256), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_events_candidate_id"), "review_events", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_review_events_session_id"), "review_events", ["session_id"], unique=False)
    op.create_index(op.f("ix_review_events_status"), "review_events", ["status"], unique=False)

    op.create_table(
        "artifact_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("job_id", sa.String(length=128), nullable=True),
        sa.Column("artifact_type", sa.String(length=128), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.job_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path", name="uq_artifact_records_path"),
    )
    op.create_index(op.f("ix_artifact_records_artifact_type"), "artifact_records", ["artifact_type"], unique=False)
    op.create_index(op.f("ix_artifact_records_job_id"), "artifact_records", ["job_id"], unique=False)
    op.create_index(op.f("ix_artifact_records_path"), "artifact_records", ["path"], unique=False)
    op.create_index(op.f("ix_artifact_records_session_id"), "artifact_records", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_artifact_records_session_id"), table_name="artifact_records")
    op.drop_index(op.f("ix_artifact_records_path"), table_name="artifact_records")
    op.drop_index(op.f("ix_artifact_records_job_id"), table_name="artifact_records")
    op.drop_index(op.f("ix_artifact_records_artifact_type"), table_name="artifact_records")
    op.drop_table("artifact_records")

    op.drop_index(op.f("ix_review_events_status"), table_name="review_events")
    op.drop_index(op.f("ix_review_events_session_id"), table_name="review_events")
    op.drop_index(op.f("ix_review_events_candidate_id"), table_name="review_events")
    op.drop_table("review_events")

    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_session_id"), table_name="jobs")
    op.drop_table("jobs")

    op.drop_table("sessions")
