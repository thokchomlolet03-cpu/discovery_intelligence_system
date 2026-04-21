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


class TargetDefinitionRecordModel(Base):
    __tablename__ = "target_definition_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True, unique=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    target_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    target_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="classification")
    optimization_direction: Mapped[str] = mapped_column(String(64), nullable=False, default="classify")
    measurement_column: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    label_column: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    measurement_unit: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    scientific_meaning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assay_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dataset_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    mapping_confidence: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    success_definition: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class EvidenceRecordModel(Base):
    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    smiles: Mapped[str] = mapped_column(Text, nullable=False, default="")
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    assay: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    target_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    observed_value: Mapped[float | None] = mapped_column(nullable=True)
    observed_label: Mapped[int | None] = mapped_column(nullable=True)
    source_row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_column: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ModelOutputRecordModel(Base):
    __tablename__ = "model_output_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    smiles: Mapped[str] = mapped_column(Text, nullable=False, default="")
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    target_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    model_family: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    model_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    calibration_method: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    training_scope: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    model_source: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    model_source_role: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    baseline_fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bridge_state_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    uncertainty: Mapped[float | None] = mapped_column(nullable=True)
    predicted_value: Mapped[float | None] = mapped_column(nullable=True)
    prediction_dispersion: Mapped[float | None] = mapped_column(nullable=True)
    novelty: Mapped[float | None] = mapped_column(nullable=True)
    applicability_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    diagnostics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RecommendationRecordModel(Base):
    __tablename__ = "recommendation_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    smiles: Mapped[str] = mapped_column(Text, nullable=False, default="")
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    decision_intent: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    modeling_mode: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    scoring_mode: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    bucket: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    risk: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="suggested", index=True)
    priority_score: Mapped[float | None] = mapped_column(nullable=True)
    experiment_value: Mapped[float | None] = mapped_column(nullable=True)
    acquisition_score: Mapped[float | None] = mapped_column(nullable=True)
    rationale_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rationale_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    policy_trace_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recommendation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    normalized_explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    governance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class CarryoverRecordModel(Base):
    __tablename__ = "carryover_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    source_session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    source_candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    target_candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    smiles: Mapped[str] = mapped_column(Text, nullable=False, default="")
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    carryover_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="review_memory")
    match_basis: Mapped[str] = mapped_column(String(64), nullable=False, default="canonical_smiles")
    review_event_id: Mapped[int | None] = mapped_column(ForeignKey("review_events.id"), nullable=True, index=True)
    source_status: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_action: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_reviewer: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    source_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class CanonicalRunMetadataModel(Base):
    __tablename__ = "canonical_run_metadata_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True, unique=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    source_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    input_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    decision_intent: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    modeling_mode: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    scoring_mode: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    run_contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    comparison_anchors_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ranking_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ranking_diagnostics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    trust_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class CanonicalCandidateStateModel(Base):
    __tablename__ = "canonical_candidate_state_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    smiles: Mapped[str] = mapped_column(Text, nullable=False, default="")
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    identity_context_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    predictive_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recommendation_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    governance_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    carryover_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    trust_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ClaimModel(Base):
    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    run_metadata_session_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    claim_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="candidate")
    claim_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    claim_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    claim_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_basis: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    support_links_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ClaimEvidenceLinkModel(Base):
    __tablename__ = "claim_evidence_links"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    link_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    linked_object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    linked_object_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ContradictionModel(Base):
    __tablename__ = "contradictions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contradiction_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    contradiction_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="claim", index=True)
    contradiction_type: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    source_object_type: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    source_object_id: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="unresolved", index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ExperimentRequestModel(Base):
    __tablename__ = "experiment_requests"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tested_claim_id: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requested_measurement: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    experiment_intent: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    epistemic_goal_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    existing_context_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    strengthening_outcome_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weakening_outcome_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_learning_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    linked_claim_evidence_snapshot_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    protocol_context_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="requested")
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ExperimentResultModel(Base):
    __tablename__ = "experiment_results"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    observed_value: Mapped[float | None] = mapped_column(nullable=True)
    observed_label: Mapped[int | None] = mapped_column(nullable=True)
    result_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="recorded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class BeliefUpdateModel(Base):
    __tablename__ = "belief_updates"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    update_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    result_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    update_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pre_belief_state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    post_belief_state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    deterministic_rule: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    revision_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="bounded_contradiction_aware")
    contradiction_pressure: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    support_balance_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    revision_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    triggering_contradiction_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    triggering_source_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class BeliefStateModel(Base):
    __tablename__ = "belief_states"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    belief_state_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current_state: Mapped[str] = mapped_column(String(64), nullable=False, default="unresolved")
    current_strength: Mapped[str] = mapped_column(String(64), nullable=False, default="tentative")
    support_basis_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contradiction_pressure: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    support_balance_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    latest_revision_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    latest_update_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    provenance_markers_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
