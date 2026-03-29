from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from system.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    source_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    input_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    latest_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    upload_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    summary_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class JobModel(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    progress_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    artifact_refs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ReviewEventModel(Base):
    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    smiles: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    actor: Mapped[str] = mapped_column(String(256), nullable=False, default="unassigned")
    reviewer: Mapped[str] = mapped_column(String(256), nullable=False, default="unassigned")
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ArtifactRecordModel(Base):
    __tablename__ = "artifact_records"
    __table_args__ = (UniqueConstraint("path", name="uq_artifact_records_path"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.session_id"), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.job_id"), nullable=True, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class WorkspaceModel(Base):
    __tablename__ = "workspaces"

    workspace_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    plan_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="free", index=True)
    plan_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_billing_provider: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    external_customer_ref: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    external_subscription_ref: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    external_price_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    provider_subscription_status: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    billing_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class WorkspaceMembershipModel(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_memberships_workspace_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class WorkspaceUsageEventModel(Base):
    __tablename__ = "workspace_usage_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.session_id"), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.job_id"), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class BillingWebhookEventModel(Base):
    __tablename__ = "billing_webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_billing_webhook_events_provider_event"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=True, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
