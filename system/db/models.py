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


class ClaimModel(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("workspace_id", "session_id", "candidate_id", "claim_type", name="uq_claims_session_candidate_type"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    candidate_reference: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target_definition_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    bounded_scope: Mapped[str] = mapped_column(Text, nullable=False, default="")
    support_level: Mapped[str] = mapped_column(String(32), nullable=False, default="limited", index=True)
    evidence_basis_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_recommendation_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_by: Mapped[str] = mapped_column(String(256), nullable=False, default="system")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ExperimentRequestModel(Base):
    __tablename__ = "experiment_requests"
    __table_args__ = (
        UniqueConstraint("workspace_id", "session_id", "claim_id", name="uq_experiment_requests_session_claim"),
    )

    experiment_request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id"), nullable=False, index=True)
    requested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    candidate_reference: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target_definition_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    requested_measurement: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    requested_direction: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    rationale_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="medium", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    requested_by: Mapped[str] = mapped_column(String(256), nullable=False, default="system")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ExperimentResultModel(Base):
    __tablename__ = "experiment_results"

    experiment_result_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    source_experiment_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiment_requests.experiment_request_id"),
        nullable=True,
        index=True,
    )
    source_claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.claim_id"), nullable=True, index=True)
    ingested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    candidate_reference: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target_definition_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    observed_value: Mapped[float | None] = mapped_column(nullable=True)
    observed_label: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    measurement_unit: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    assay_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_quality: Mapped[str] = mapped_column(String(32), nullable=False, default="provisional", index=True)
    result_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_entry", index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    ingested_by: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class BeliefUpdateModel(Base):
    __tablename__ = "belief_updates"
    __table_args__ = (
        UniqueConstraint("workspace_id", "claim_id", "experiment_result_id", name="uq_belief_updates_claim_result"),
    )

    belief_update_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id"), nullable=False, index=True)
    experiment_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiment_results.experiment_result_id"),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    candidate_label: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    previous_support_level: Mapped[str] = mapped_column(String(32), nullable=False, default="limited", index=True)
    updated_support_level: Mapped[str] = mapped_column(String(32), nullable=False, default="limited", index=True)
    update_direction: Mapped[str] = mapped_column(String(32), nullable=False, default="unresolved", index=True)
    update_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    governance_status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_by: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class BeliefStateModel(Base):
    __tablename__ = "belief_states"
    __table_args__ = (
        UniqueConstraint("workspace_id", "target_key", name="uq_belief_states_workspace_target"),
    )

    belief_state_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    target_definition_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supported_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weakened_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unresolved_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_update_source: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    latest_belief_update_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    support_distribution_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    governance_scope_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
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
