from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError

from system.contracts import (
    validate_artifact_pointer,
    validate_belief_state_record,
    validate_belief_update_record,
    validate_claim_record,
    validate_experiment_result_record,
    validate_experiment_request_record,
    validate_governed_review_record,
    validate_job_state,
    validate_review_event_record,
    validate_session_metadata,
    validate_user_record,
    validate_workspace_membership_record,
    validate_workspace_record,
    validate_workspace_usage_event_record,
)
from system.db.models import (
    ArtifactRecordModel,
    BeliefStateModel,
    BeliefUpdateModel,
    BillingWebhookEventModel,
    ClaimModel,
    ExperimentResultModel,
    ExperimentRequestModel,
    GovernedReviewRecordModel,
    JobModel,
    ReviewEventModel,
    SessionModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
    WorkspaceUsageEventModel,
)
from system.db.session import session_scope


LEGACY_WORKSPACE_ID = "legacy_workspace"
DEFAULT_WORKSPACE_ROLE = "member"
_UNSET = object()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _merge_dicts(existing: dict[str, Any] | None, incoming: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(existing or {})
    if incoming:
        merged.update(dict(incoming))
    return merged


def _normalize_path(value: str | Path) -> str:
    from system.services.artifact_service import ensure_safe_artifact_path

    return str(ensure_safe_artifact_path(value, require_exists=True))


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _user_payload(record: UserModel) -> dict[str, Any]:
    return validate_user_record(
        {
            "user_id": record.user_id,
            "email": record.email,
            "display_name": record.display_name,
            "is_active": record.is_active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _workspace_payload(record: WorkspaceModel) -> dict[str, Any]:
    return validate_workspace_record(
        {
            "workspace_id": record.workspace_id,
            "name": record.name,
            "owner_user_id": record.owner_user_id or "",
            "plan_tier": record.plan_tier,
            "plan_status": record.plan_status,
            "trial_ends_at": record.trial_ends_at,
            "current_period_ends_at": record.current_period_ends_at,
            "external_billing_provider": record.external_billing_provider or "",
            "external_customer_ref": record.external_customer_ref or "",
            "external_subscription_ref": record.external_subscription_ref or "",
            "external_price_ref": record.external_price_ref or "",
            "provider_subscription_status": record.provider_subscription_status or "",
            "billing_synced_at": record.billing_synced_at,
            "billing_metadata": record.billing_metadata or {},
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _membership_payload(record: WorkspaceMembershipModel) -> dict[str, Any]:
    return validate_workspace_membership_record(
        {
            "workspace_id": record.workspace_id,
            "user_id": record.user_id,
            "role": record.role,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _session_payload(record: SessionModel) -> dict[str, Any]:
    return validate_session_metadata(
        {
            "session_id": record.session_id,
            "workspace_id": record.workspace_id,
            "created_by_user_id": record.created_by_user_id or "",
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "source_name": record.source_name,
            "input_type": record.input_type,
            "latest_job_id": record.latest_job_id or "",
            "upload_metadata": record.upload_metadata or {},
            "summary_metadata": record.summary_metadata or {},
        }
    )


def _job_payload(record: JobModel) -> dict[str, Any]:
    return validate_job_state(
        {
            "job_id": record.job_id,
            "session_id": record.session_id,
            "workspace_id": record.workspace_id,
            "created_by_user_id": record.created_by_user_id or "",
            "status": record.status,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "job_type": record.job_type,
            "progress_stage": record.progress_stage,
            "progress_percent": record.progress_percent,
            "progress_message": record.progress_message,
            "error": record.error,
            "artifact_refs": record.artifact_refs or {},
        }
    )


def _review_payload(record: ReviewEventModel) -> dict[str, Any]:
    return validate_review_event_record(
        {
            "session_id": record.session_id,
            "workspace_id": record.workspace_id,
            "candidate_id": record.candidate_id,
            "smiles": record.smiles,
            "action": record.action,
            "previous_status": record.previous_status,
            "status": record.status,
            "note": record.note,
            "timestamp": record.timestamp,
            "reviewed_at": record.reviewed_at,
            "actor": record.actor,
            "reviewer": record.reviewer,
            "actor_user_id": record.actor_user_id or "",
            "metadata": record.metadata_json or {},
        }
    )


def _claim_payload(record: ClaimModel) -> dict[str, Any]:
    return validate_claim_record(
        {
            "claim_id": record.claim_id,
            "workspace_id": record.workspace_id,
            "session_id": record.session_id,
            "candidate_id": record.candidate_id,
            "candidate_reference": record.candidate_reference or {},
            "target_definition_snapshot": record.target_definition_snapshot or {},
            "claim_type": record.claim_type,
            "claim_text": record.claim_text,
            "bounded_scope": record.bounded_scope,
            "support_level": record.support_level,
            "evidence_basis_summary": record.evidence_basis_summary,
            "source_recommendation_rank": record.source_recommendation_rank,
            "status": record.status,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "created_by": record.created_by,
            "created_by_user_id": record.created_by_user_id or "",
            "reviewed_at": record.reviewed_at,
            "reviewed_by": record.reviewed_by,
            "metadata": record.metadata_json or {},
        }
    )


def _experiment_request_payload(record: ExperimentRequestModel) -> dict[str, Any]:
    return validate_experiment_request_record(
        {
            "experiment_request_id": record.experiment_request_id,
            "workspace_id": record.workspace_id,
            "session_id": record.session_id,
            "claim_id": record.claim_id,
            "candidate_id": record.candidate_id,
            "candidate_reference": record.candidate_reference or {},
            "target_definition_snapshot": record.target_definition_snapshot or {},
            "requested_measurement": record.requested_measurement,
            "requested_direction": record.requested_direction,
            "rationale_summary": record.rationale_summary,
            "priority_tier": record.priority_tier,
            "status": record.status,
            "requested_at": record.requested_at,
            "requested_by": record.requested_by,
            "requested_by_user_id": record.requested_by_user_id or "",
            "notes": record.notes,
            "metadata": record.metadata_json or {},
        }
    )


def _experiment_result_payload(record: ExperimentResultModel) -> dict[str, Any]:
    return validate_experiment_result_record(
        {
            "experiment_result_id": record.experiment_result_id,
            "workspace_id": record.workspace_id,
            "session_id": record.session_id,
            "source_experiment_request_id": record.source_experiment_request_id or "",
            "source_claim_id": record.source_claim_id or "",
            "candidate_id": record.candidate_id,
            "candidate_reference": record.candidate_reference or {},
            "target_definition_snapshot": record.target_definition_snapshot or {},
            "observed_value": record.observed_value,
            "observed_label": record.observed_label,
            "measurement_unit": record.measurement_unit,
            "assay_context": record.assay_context,
            "result_quality": record.result_quality,
            "result_source": record.result_source,
            "ingested_at": record.ingested_at,
            "ingested_by": record.ingested_by,
            "ingested_by_user_id": record.ingested_by_user_id or "",
            "notes": record.notes,
            "metadata": record.metadata_json or {},
        }
    )


def _belief_update_payload(record: BeliefUpdateModel) -> dict[str, Any]:
    governance_status = record.governance_status
    active_for_belief_state = governance_status in {"accepted", "proposed"}
    metadata = record.metadata_json or {}
    if governance_status == "accepted":
        chronology_label = "Current accepted support change"
    elif governance_status == "proposed":
        chronology_label = "Current proposed support change"
    elif governance_status == "superseded":
        chronology_label = "Historical superseded support change"
    elif governance_status == "rejected":
        chronology_label = "Historical rejected support change"
    else:
        chronology_label = ""
    return validate_belief_update_record(
        {
            "belief_update_id": record.belief_update_id,
            "workspace_id": record.workspace_id,
            "session_id": record.session_id,
            "claim_id": record.claim_id,
            "experiment_result_id": record.experiment_result_id or "",
            "candidate_id": record.candidate_id,
            "candidate_label": record.candidate_label,
            "previous_support_level": record.previous_support_level,
            "updated_support_level": record.updated_support_level,
            "update_direction": record.update_direction,
            "update_reason": record.update_reason,
            "support_input_quality_label": metadata.get("support_input_quality_label", ""),
            "support_input_quality_summary": metadata.get("support_input_quality_summary", ""),
            "assay_context_alignment_label": metadata.get("assay_context_alignment_label", ""),
            "result_interpretation_basis": metadata.get("result_interpretation_basis", ""),
            "numeric_result_basis_label": metadata.get("numeric_result_basis_label", ""),
            "numeric_result_basis_summary": metadata.get("numeric_result_basis_summary", ""),
            "numeric_result_resolution_label": metadata.get("numeric_result_resolution_label", ""),
            "numeric_result_interpretation_label": metadata.get("numeric_result_interpretation_label", ""),
            "target_rule_alignment_label": metadata.get("target_rule_alignment_label", ""),
            "governance_status": governance_status,
            "chronology_label": chronology_label,
            "active_for_belief_state": active_for_belief_state,
            "created_at": record.created_at,
            "created_by": record.created_by,
            "created_by_user_id": record.created_by_user_id or "",
            "reviewed_at": record.reviewed_at,
            "reviewed_by": record.reviewed_by,
            "metadata": metadata,
        }
    )


def _belief_state_payload(record: BeliefStateModel) -> dict[str, Any]:
    metadata = record.metadata_json or {}
    return validate_belief_state_record(
        {
            "belief_state_id": record.belief_state_id,
            "workspace_id": record.workspace_id,
            "target_key": record.target_key,
            "target_definition_snapshot": record.target_definition_snapshot or {},
            "summary_text": record.summary_text,
            "active_claim_count": record.active_claim_count,
            "supported_claim_count": record.supported_claim_count,
            "weakened_claim_count": record.weakened_claim_count,
            "unresolved_claim_count": record.unresolved_claim_count,
            "last_updated_at": record.last_updated_at,
            "last_update_source": record.last_update_source,
            "version": record.version,
            "latest_belief_update_refs": record.latest_belief_update_refs or [],
            "support_distribution_summary": record.support_distribution_summary,
            "governance_scope_summary": record.governance_scope_summary,
            "chronology_summary_text": metadata.get("chronology_summary_text", ""),
            "support_basis_mix_label": metadata.get("support_basis_mix_label", ""),
            "support_basis_mix_summary": metadata.get("support_basis_mix_summary", ""),
            "observed_label_support_count": metadata.get("observed_label_support_count", 0),
            "numeric_rule_based_support_count": metadata.get("numeric_rule_based_support_count", 0),
            "unresolved_basis_count": metadata.get("unresolved_basis_count", 0),
            "weak_basis_count": metadata.get("weak_basis_count", 0),
            "belief_state_strength_summary": metadata.get("belief_state_strength_summary", ""),
            "belief_state_readiness_summary": metadata.get("belief_state_readiness_summary", ""),
            "governance_mix_label": metadata.get("governance_mix_label", ""),
            "metadata": metadata,
        }
    )


def _artifact_payload(record: ArtifactRecordModel) -> dict[str, Any]:
    return validate_artifact_pointer(
        {
            "session_id": record.session_id or "",
            "job_id": record.job_id or "",
            "workspace_id": record.workspace_id,
            "created_by_user_id": record.created_by_user_id or "",
            "artifact_type": record.artifact_type,
            "path": record.path,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "metadata": record.metadata_json or {},
        }
    )


def _governed_review_payload(record: GovernedReviewRecordModel) -> dict[str, Any]:
    return validate_governed_review_record(
        {
            "review_record_id": record.review_record_id,
            "workspace_id": record.workspace_id,
            "session_id": record.session_id or "",
            "subject_type": record.subject_type,
            "subject_id": record.subject_id,
            "target_key": record.target_key,
            "candidate_id": record.candidate_id,
            "active": record.active,
            "source_class_label": record.source_class_label,
            "provenance_confidence_label": record.provenance_confidence_label,
            "trust_tier_label": record.trust_tier_label,
            "review_origin_label": record.review_origin_label,
            "manual_action_label": record.manual_action_label,
            "reviewer_label": record.reviewer_label,
            "review_status_label": record.review_status_label,
            "review_reason_label": record.review_reason_label,
            "review_reason_summary": record.review_reason_summary,
            "promotion_gate_status_label": record.promotion_gate_status_label,
            "promotion_block_reason_label": record.promotion_block_reason_label,
            "decision_outcome": record.decision_outcome,
            "decision_summary": record.decision_summary,
            "supersedes_review_record_id": record.supersedes_review_record_id or "",
            "recorded_at": record.recorded_at,
            "recorded_by": record.recorded_by,
            "actor_user_id": record.actor_user_id or "",
            "reviewer_user_id": record.reviewer_user_id or "",
            "metadata": record.metadata_json or {},
        }
    )


def _workspace_usage_payload(record: WorkspaceUsageEventModel) -> dict[str, Any]:
    return validate_workspace_usage_event_record(
        {
            "workspace_id": record.workspace_id,
            "event_type": record.event_type,
            "quantity": record.quantity,
            "created_at": record.created_at,
            "session_id": record.session_id or "",
            "job_id": record.job_id or "",
            "metadata": record.metadata_json or {},
        }
    )


class UserRepository:
    def count_users(self) -> int:
        with session_scope() as db:
            return int(db.execute(select(func.count()).select_from(UserModel)).scalar_one())

    def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str = "",
        is_active: bool = True,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            record = UserModel(
                user_id=user_id or _make_id("user"),
                email=str(email).strip().lower(),
                display_name=str(display_name).strip(),
                password_hash=password_hash,
                is_active=bool(is_active),
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _user_payload(record)

    def get_user(self, user_id: str) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(UserModel, user_id)
            if record is None:
                raise FileNotFoundError(f"No persisted user found for '{user_id}'.")
            return _user_payload(record)

    def get_user_credentials_by_email(self, email: str) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(UserModel).where(UserModel.email == str(email).strip().lower())
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted user found for '{email}'.")
            return {
                **_user_payload(record),
                "password_hash": record.password_hash,
            }

    def set_user_active(self, user_id: str, *, is_active: bool) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(UserModel, user_id)
            if record is None:
                raise FileNotFoundError(f"No persisted user found for '{user_id}'.")
            record.is_active = bool(is_active)
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _user_payload(record)


class WorkspaceRepository:
    def create_workspace(
        self,
        *,
        name: str,
        owner_user_id: str | None = None,
        plan_tier: str = "free",
        plan_status: str = "active",
        trial_ends_at: datetime | None = None,
        current_period_ends_at: datetime | None = None,
        external_billing_provider: str | None = None,
        external_customer_ref: str | None = None,
        external_subscription_ref: str | None = None,
        external_price_ref: str | None = None,
        provider_subscription_status: str | None = None,
        billing_synced_at: datetime | None = None,
        billing_metadata: dict[str, Any] | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            record = WorkspaceModel(
                workspace_id=workspace_id or _make_id("ws"),
                name=str(name).strip(),
                owner_user_id=owner_user_id or None,
                plan_tier=str(plan_tier).strip().lower() or "free",
                plan_status=str(plan_status).strip().lower() or "active",
                trial_ends_at=trial_ends_at,
                current_period_ends_at=current_period_ends_at,
                external_billing_provider=str(external_billing_provider or "").strip().lower() or None,
                external_customer_ref=str(external_customer_ref or "").strip() or None,
                external_subscription_ref=str(external_subscription_ref or "").strip() or None,
                external_price_ref=str(external_price_ref or "").strip() or None,
                provider_subscription_status=str(provider_subscription_status or "").strip().lower() or None,
                billing_synced_at=billing_synced_at,
                billing_metadata=dict(billing_metadata or {}),
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _workspace_payload(record)

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(WorkspaceModel, workspace_id)
            if record is None:
                raise FileNotFoundError(f"No persisted workspace found for '{workspace_id}'.")
            return _workspace_payload(record)

    def update_workspace_plan(
        self,
        workspace_id: str,
        *,
        plan_tier: str | None = None,
        plan_status: str | None = None,
        trial_ends_at: datetime | None | object = _UNSET,
        current_period_ends_at: datetime | None | object = _UNSET,
        external_billing_provider: str | None | object = _UNSET,
        external_customer_ref: str | None | object = _UNSET,
        external_subscription_ref: str | None | object = _UNSET,
        external_price_ref: str | None | object = _UNSET,
        provider_subscription_status: str | None | object = _UNSET,
        billing_synced_at: datetime | None | object = _UNSET,
        billing_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(WorkspaceModel, workspace_id)
            if record is None:
                raise FileNotFoundError(f"No persisted workspace found for '{workspace_id}'.")
            if plan_tier is not None:
                record.plan_tier = str(plan_tier).strip().lower() or "free"
            if plan_status is not None:
                record.plan_status = str(plan_status).strip().lower() or "active"
            if trial_ends_at is not _UNSET:
                record.trial_ends_at = trial_ends_at
            if current_period_ends_at is not _UNSET:
                record.current_period_ends_at = current_period_ends_at
            if external_billing_provider is not _UNSET:
                record.external_billing_provider = str(external_billing_provider or "").strip().lower() or None
            if external_customer_ref is not _UNSET:
                record.external_customer_ref = str(external_customer_ref or "").strip() or None
            if external_subscription_ref is not _UNSET:
                record.external_subscription_ref = str(external_subscription_ref or "").strip() or None
            if external_price_ref is not _UNSET:
                record.external_price_ref = str(external_price_ref or "").strip() or None
            if provider_subscription_status is not _UNSET:
                record.provider_subscription_status = str(provider_subscription_status or "").strip().lower() or None
            if billing_synced_at is not _UNSET:
                record.billing_synced_at = billing_synced_at
            if billing_metadata is not None:
                record.billing_metadata = _merge_dicts(record.billing_metadata, billing_metadata)
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _workspace_payload(record)

    def get_workspace_by_external_subscription_ref(
        self,
        external_subscription_ref: str,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(WorkspaceModel).where(
                WorkspaceModel.external_subscription_ref == str(external_subscription_ref).strip()
            )
            if provider is not None:
                statement = statement.where(WorkspaceModel.external_billing_provider == str(provider).strip().lower())
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(
                    f"No persisted workspace found for subscription '{external_subscription_ref}'."
                )
            return _workspace_payload(record)

    def get_workspace_by_external_customer_ref(
        self,
        external_customer_ref: str,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(WorkspaceModel).where(
                WorkspaceModel.external_customer_ref == str(external_customer_ref).strip()
            )
            if provider is not None:
                statement = statement.where(WorkspaceModel.external_billing_provider == str(provider).strip().lower())
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(
                    f"No persisted workspace found for customer '{external_customer_ref}'."
                )
            return _workspace_payload(record)

    def add_membership(self, *, workspace_id: str, user_id: str, role: str = DEFAULT_WORKSPACE_ROLE) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(WorkspaceMembershipModel).where(
                WorkspaceMembershipModel.workspace_id == workspace_id,
                WorkspaceMembershipModel.user_id == user_id,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = WorkspaceMembershipModel(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role=str(role).strip().lower(),
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
            else:
                record.role = str(role).strip().lower()
                record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _membership_payload(record)

    def get_membership(self, *, workspace_id: str, user_id: str) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(WorkspaceMembershipModel).where(
                WorkspaceMembershipModel.workspace_id == workspace_id,
                WorkspaceMembershipModel.user_id == user_id,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"User '{user_id}' is not a member of workspace '{workspace_id}'.")
            return _membership_payload(record)

    def remove_membership(self, *, workspace_id: str, user_id: str) -> None:
        with session_scope() as db:
            statement = select(WorkspaceMembershipModel).where(
                WorkspaceMembershipModel.workspace_id == workspace_id,
                WorkspaceMembershipModel.user_id == user_id,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"User '{user_id}' is not a member of workspace '{workspace_id}'.")
            db.delete(record)

    def list_user_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = (
                select(WorkspaceMembershipModel, WorkspaceModel)
                .join(WorkspaceModel, WorkspaceMembershipModel.workspace_id == WorkspaceModel.workspace_id)
                .where(WorkspaceMembershipModel.user_id == user_id)
                .order_by(WorkspaceModel.created_at.asc())
            )
            rows = db.execute(statement).all()
            return [
                {
                    "workspace": _workspace_payload(workspace),
                    "membership": _membership_payload(membership),
                }
                for membership, workspace in rows
            ]

    def user_has_workspace(self, *, workspace_id: str, user_id: str) -> bool:
        try:
            self.get_membership(workspace_id=workspace_id, user_id=user_id)
        except FileNotFoundError:
            return False
        return True

    def get_user_workspace(self, *, user_id: str, workspace_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        if workspace_id:
            membership = self.get_membership(workspace_id=workspace_id, user_id=user_id)
            workspace = self.get_workspace(workspace_id)
            return workspace, membership

        options = self.list_user_workspaces(user_id)
        if not options:
            raise FileNotFoundError(f"User '{user_id}' is not a member of any workspace.")
        first = options[0]
        return first["workspace"], first["membership"]

    def count_members(self, workspace_id: str) -> int:
        with session_scope() as db:
            statement = select(func.count()).select_from(WorkspaceMembershipModel).where(
                WorkspaceMembershipModel.workspace_id == workspace_id
            )
            return int(db.execute(statement).scalar_one())


class SessionRepository:
    def upsert_session(
        self,
        *,
        session_id: str,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        source_name: str | None = None,
        input_type: str | None = None,
        latest_job_id: str | None = None,
        upload_metadata: dict[str, Any] | None = None,
        summary_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        effective_workspace_id = workspace_id or LEGACY_WORKSPACE_ID
        with session_scope() as db:
            record = db.get(SessionModel, session_id)
            if record is None:
                record = SessionModel(
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=created_by_user_id or None,
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                    source_name="",
                    input_type="",
                    latest_job_id=None,
                    upload_metadata={},
                    summary_metadata={},
                )
            elif workspace_id is not None and record.workspace_id != effective_workspace_id:
                raise ValueError(
                    f"Session '{session_id}' already belongs to workspace '{record.workspace_id}' and cannot be reassigned."
                )
            if workspace_id is not None:
                record.workspace_id = effective_workspace_id
            if created_by_user_id is not None:
                record.created_by_user_id = str(created_by_user_id) or None
            if source_name is not None:
                record.source_name = str(source_name)
            if input_type is not None:
                record.input_type = str(input_type)
            if latest_job_id is not None:
                record.latest_job_id = str(latest_job_id) or None
            if upload_metadata is not None:
                record.upload_metadata = _merge_dicts(record.upload_metadata, upload_metadata)
            if summary_metadata is not None:
                record.summary_metadata = _merge_dicts(record.summary_metadata, summary_metadata)
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _session_payload(record)

    def get_session(self, session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(SessionModel).where(SessionModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(SessionModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted session metadata found for '{session_id}'.")
            return _session_payload(record)

    def count_sessions(self, workspace_id: str) -> int:
        with session_scope() as db:
            statement = select(func.count()).select_from(SessionModel).where(SessionModel.workspace_id == workspace_id)
            return int(db.execute(statement).scalar_one())

    def list_sessions(self, workspace_id: str, *, limit: int | None = 25) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = (
                select(SessionModel)
                .where(SessionModel.workspace_id == workspace_id)
                .order_by(desc(SessionModel.updated_at), desc(SessionModel.created_at))
            )
            if limit is not None:
                statement = statement.limit(int(limit))
            rows = db.execute(statement).scalars().all()
            return [_session_payload(row) for row in rows]


class JobRepository:
    def __init__(self, session_repository: SessionRepository | None = None) -> None:
        self.session_repository = session_repository or SessionRepository()

    def create_job(
        self,
        *,
        session_id: str,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        job_id: str,
        status: str,
        created_at: datetime,
        updated_at: datetime,
        job_type: str = "analysis",
        progress_stage: str = "queued",
        progress_percent: int = 0,
        progress_message: str = "",
        error: str = "",
        artifact_refs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if workspace_id is None:
            try:
                workspace_id = self.session_repository.get_session(session_id)["workspace_id"]
            except FileNotFoundError:
                workspace_id = LEGACY_WORKSPACE_ID
        self.session_repository.upsert_session(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            latest_job_id=job_id,
        )
        payload = validate_job_state(
            {
                "job_id": job_id,
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "status": status,
                "created_at": created_at,
                "updated_at": updated_at,
                "job_type": job_type,
                "progress_stage": progress_stage,
                "progress_percent": progress_percent,
                "progress_message": progress_message,
                "error": error,
                "artifact_refs": artifact_refs or {},
            }
        )
        with session_scope() as db:
            record = JobModel(
                job_id=payload["job_id"],
                session_id=payload["session_id"],
                workspace_id=payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                created_by_user_id=payload.get("created_by_user_id") or None,
                status=payload["status"],
                created_at=_to_datetime(payload["created_at"]),
                updated_at=_to_datetime(payload["updated_at"]),
                job_type=payload.get("job_type", ""),
                progress_stage=payload.get("progress_stage", "queued"),
                progress_percent=int(payload.get("progress_percent", 0)),
                progress_message=payload.get("progress_message", ""),
                error=payload.get("error", ""),
                artifact_refs=payload.get("artifact_refs", {}),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _job_payload(record)

    def get_job(self, job_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(JobModel).where(JobModel.job_id == job_id)
            if workspace_id is not None:
                statement = statement.where(JobModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted job metadata found for '{job_id}'.")
            return _job_payload(record)

    def update_job(self, job_id: str, **changes: Any) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(JobModel, job_id)
            if record is None:
                raise FileNotFoundError(f"No persisted job metadata found for '{job_id}'.")
            current = _job_payload(record)
            if "workspace_id" in changes and str(changes["workspace_id"] or "") != str(current.get("workspace_id") or ""):
                raise ValueError("Job workspace ownership is immutable.")
            if "created_by_user_id" in changes and str(changes["created_by_user_id"] or "") != str(current.get("created_by_user_id") or ""):
                raise ValueError("Job creator attribution is immutable.")
            payload = validate_job_state(
                {
                    **current,
                    **changes,
                    "job_id": current["job_id"],
                    "session_id": current["session_id"],
                    "workspace_id": changes.get("workspace_id", current.get("workspace_id", LEGACY_WORKSPACE_ID)),
                    "created_by_user_id": changes.get("created_by_user_id", current.get("created_by_user_id", "")),
                    "updated_at": _utc_now(),
                    "artifact_refs": changes.get("artifact_refs", current.get("artifact_refs", {})),
                }
            )
            record.workspace_id = payload.get("workspace_id") or LEGACY_WORKSPACE_ID
            record.created_by_user_id = payload.get("created_by_user_id") or None
            record.status = payload["status"]
            record.updated_at = _to_datetime(payload["updated_at"])
            record.job_type = payload.get("job_type", "")
            record.progress_stage = payload.get("progress_stage", "queued")
            record.progress_percent = int(payload.get("progress_percent", 0))
            record.progress_message = payload.get("progress_message", "")
            record.error = payload.get("error", "")
            record.artifact_refs = payload.get("artifact_refs", {})
            db.add(record)
            db.flush()
            db.refresh(record)
            return _job_payload(record)


class ReviewRepository:
    def __init__(self, session_repository: SessionRepository | None = None) -> None:
        self.session_repository = session_repository or SessionRepository()

    def record_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = validate_review_event_record(payload)
        if not record_payload.get("workspace_id"):
            try:
                record_payload["workspace_id"] = self.session_repository.get_session(record_payload["session_id"])["workspace_id"]
            except FileNotFoundError:
                record_payload["workspace_id"] = LEGACY_WORKSPACE_ID
        self.session_repository.upsert_session(
            session_id=record_payload["session_id"],
            workspace_id=record_payload["workspace_id"],
        )
        with session_scope() as db:
            record = ReviewEventModel(
                session_id=record_payload["session_id"],
                workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                candidate_id=record_payload["candidate_id"],
                smiles=record_payload["smiles"],
                action=record_payload["action"],
                previous_status=record_payload.get("previous_status"),
                status=record_payload["status"],
                note=record_payload.get("note", ""),
                timestamp=_to_datetime(record_payload["timestamp"]),
                reviewed_at=_to_datetime(record_payload["reviewed_at"]),
                actor=record_payload.get("actor", "unassigned"),
                reviewer=record_payload.get("reviewer", "unassigned"),
                actor_user_id=record_payload.get("actor_user_id") or None,
                metadata_json=record_payload.get("metadata", {}),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _review_payload(record)

    def record_reviews(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for payload in payloads:
            created.append(self.record_review(payload))
        return created

    def list_reviews(self, session_id: str | None = None, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ReviewEventModel).order_by(ReviewEventModel.reviewed_at.asc(), ReviewEventModel.id.asc())
            if session_id is not None:
                statement = statement.where(ReviewEventModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ReviewEventModel.workspace_id == workspace_id)
            rows = db.execute(statement).scalars().all()
            return [_review_payload(row) for row in rows]


class GovernedReviewRepository:
    def __init__(self, session_repository: SessionRepository | None = None) -> None:
        self.session_repository = session_repository or SessionRepository()

    def record_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = validate_governed_review_record(payload)
        workspace_id = record_payload.get("workspace_id") or ""
        session_id = record_payload.get("session_id") or ""
        review_origin_label = record_payload.get("review_origin_label") or "derived"
        if not workspace_id and session_id:
            try:
                workspace_id = self.session_repository.get_session(session_id)["workspace_id"]
            except FileNotFoundError:
                workspace_id = LEGACY_WORKSPACE_ID
            record_payload["workspace_id"] = workspace_id
        elif not workspace_id:
            workspace_id = LEGACY_WORKSPACE_ID
            record_payload["workspace_id"] = workspace_id
        if session_id:
            self.session_repository.upsert_session(
                session_id=session_id,
                workspace_id=workspace_id,
            )
        with session_scope() as db:
            if record_payload.get("active"):
                current_active = db.execute(
                    select(GovernedReviewRecordModel).where(
                        GovernedReviewRecordModel.workspace_id == workspace_id,
                        GovernedReviewRecordModel.subject_type == record_payload["subject_type"],
                        GovernedReviewRecordModel.subject_id == record_payload["subject_id"],
                        GovernedReviewRecordModel.review_origin_label == review_origin_label,
                        GovernedReviewRecordModel.active.is_(True),
                    )
                ).scalar_one_or_none()
                if current_active is not None:
                    current_active.active = False
                    db.add(current_active)
                    if not record_payload.get("supersedes_review_record_id"):
                        record_payload["supersedes_review_record_id"] = current_active.review_record_id
            record = GovernedReviewRecordModel(
                review_record_id=record_payload["review_record_id"] or _make_id("govreview"),
                workspace_id=workspace_id,
                session_id=session_id or None,
                subject_type=record_payload["subject_type"],
                subject_id=record_payload["subject_id"],
                target_key=record_payload.get("target_key", ""),
                candidate_id=record_payload.get("candidate_id", ""),
                active=bool(record_payload.get("active", True)),
                source_class_label=record_payload.get("source_class_label", ""),
                provenance_confidence_label=record_payload.get("provenance_confidence_label", ""),
                trust_tier_label=record_payload.get("trust_tier_label", ""),
                review_origin_label=review_origin_label,
                manual_action_label=record_payload.get("manual_action_label", ""),
                reviewer_label=record_payload.get("reviewer_label", ""),
                review_status_label=record_payload.get("review_status_label", ""),
                review_reason_label=record_payload.get("review_reason_label", ""),
                review_reason_summary=record_payload.get("review_reason_summary", ""),
                promotion_gate_status_label=record_payload.get("promotion_gate_status_label", ""),
                promotion_block_reason_label=record_payload.get("promotion_block_reason_label", ""),
                decision_outcome=record_payload.get("decision_outcome", ""),
                decision_summary=record_payload.get("decision_summary", ""),
                supersedes_review_record_id=record_payload.get("supersedes_review_record_id") or None,
                recorded_at=_to_datetime(record_payload["recorded_at"]),
                recorded_by=record_payload.get("recorded_by", "system") or "system",
                actor_user_id=record_payload.get("actor_user_id") or None,
                reviewer_user_id=record_payload.get("reviewer_user_id") or None,
                metadata_json=record_payload.get("metadata", {}),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _governed_review_payload(record)

    def list_reviews(
        self,
        *,
        workspace_id: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        session_id: str | None = None,
        review_origin_label: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(GovernedReviewRecordModel).order_by(
                GovernedReviewRecordModel.recorded_at.asc(),
                GovernedReviewRecordModel.review_record_id.asc(),
            )
            if workspace_id is not None:
                statement = statement.where(GovernedReviewRecordModel.workspace_id == workspace_id)
            if subject_type is not None:
                statement = statement.where(GovernedReviewRecordModel.subject_type == subject_type)
            if subject_id is not None:
                statement = statement.where(GovernedReviewRecordModel.subject_id == subject_id)
            if session_id is not None:
                statement = statement.where(GovernedReviewRecordModel.session_id == session_id)
            if review_origin_label is not None:
                statement = statement.where(GovernedReviewRecordModel.review_origin_label == review_origin_label)
            if active_only:
                statement = statement.where(GovernedReviewRecordModel.active.is_(True))
            rows = db.execute(statement).scalars().all()
            return [_governed_review_payload(row) for row in rows]

    def get_latest_active_review(
        self,
        *,
        workspace_id: str,
        subject_type: str,
        subject_id: str,
        review_origin_label: str | None = None,
    ) -> dict[str, Any] | None:
        with session_scope() as db:
            statement = (
                select(GovernedReviewRecordModel)
                .where(
                    GovernedReviewRecordModel.workspace_id == workspace_id,
                    GovernedReviewRecordModel.subject_type == subject_type,
                    GovernedReviewRecordModel.subject_id == subject_id,
                    GovernedReviewRecordModel.active.is_(True),
                )
                .order_by(
                    desc(GovernedReviewRecordModel.recorded_at),
                    desc(GovernedReviewRecordModel.review_record_id),
                )
            )
            if review_origin_label is not None:
                statement = statement.where(GovernedReviewRecordModel.review_origin_label == review_origin_label)
            record = db.execute(statement).scalars().first()
            if record is None:
                return None
            return _governed_review_payload(record)


class ClaimRepository:
    def __init__(self, session_repository: SessionRepository | None = None) -> None:
        self.session_repository = session_repository or SessionRepository()

    def upsert_claim(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = validate_claim_record(payload)
        if not record_payload.get("workspace_id"):
            try:
                record_payload["workspace_id"] = self.session_repository.get_session(record_payload["session_id"])["workspace_id"]
            except FileNotFoundError:
                record_payload["workspace_id"] = LEGACY_WORKSPACE_ID
        self.session_repository.upsert_session(
            session_id=record_payload["session_id"],
            workspace_id=record_payload["workspace_id"],
            created_by_user_id=record_payload.get("created_by_user_id") or None,
        )
        with session_scope() as db:
            statement = select(ClaimModel).where(
                ClaimModel.workspace_id == (record_payload["workspace_id"] or LEGACY_WORKSPACE_ID),
                ClaimModel.session_id == record_payload["session_id"],
                ClaimModel.candidate_id == record_payload["candidate_id"],
                ClaimModel.claim_type == record_payload["claim_type"],
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = ClaimModel(
                    claim_id=record_payload["claim_id"] or _make_id("claim"),
                    session_id=record_payload["session_id"],
                    workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    candidate_id=record_payload["candidate_id"],
                    candidate_reference=record_payload.get("candidate_reference") or {},
                    target_definition_snapshot=record_payload.get("target_definition_snapshot") or {},
                    claim_type=record_payload["claim_type"],
                    claim_text=record_payload["claim_text"],
                    bounded_scope=record_payload["bounded_scope"],
                    support_level=record_payload["support_level"],
                    evidence_basis_summary=record_payload.get("evidence_basis_summary", ""),
                    source_recommendation_rank=int(record_payload.get("source_recommendation_rank", 0) or 0),
                    status=record_payload["status"],
                    created_at=_to_datetime(record_payload["created_at"]),
                    updated_at=_to_datetime(record_payload["updated_at"]),
                    created_by=record_payload.get("created_by", "system") or "system",
                    reviewed_at=_to_datetime(record_payload["reviewed_at"]) if record_payload.get("reviewed_at") else None,
                    reviewed_by=record_payload.get("reviewed_by", ""),
                    metadata_json=record_payload.get("metadata", {}),
                )
            else:
                record.candidate_reference = record_payload.get("candidate_reference") or {}
                record.target_definition_snapshot = record_payload.get("target_definition_snapshot") or {}
                record.claim_text = record_payload["claim_text"]
                record.bounded_scope = record_payload["bounded_scope"]
                record.support_level = record_payload["support_level"]
                record.evidence_basis_summary = record_payload.get("evidence_basis_summary", "")
                record.source_recommendation_rank = int(record_payload.get("source_recommendation_rank", 0) or 0)
                record.status = record_payload["status"]
                record.updated_at = _to_datetime(record_payload["updated_at"])
                record.created_by = record_payload.get("created_by", record.created_by) or record.created_by
                if record_payload.get("created_by_user_id") is not None:
                    record.created_by_user_id = record_payload.get("created_by_user_id") or None
                record.reviewed_at = _to_datetime(record_payload["reviewed_at"]) if record_payload.get("reviewed_at") else None
                record.reviewed_by = record_payload.get("reviewed_by", "")
                record.metadata_json = record_payload.get("metadata", {})
            db.add(record)
            db.flush()
            db.refresh(record)
            return _claim_payload(record)

    def list_claims(self, session_id: str | None = None, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ClaimModel).order_by(
                ClaimModel.source_recommendation_rank.asc(),
                ClaimModel.created_at.asc(),
                ClaimModel.claim_id.asc(),
            )
            if session_id is not None:
                statement = statement.where(ClaimModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ClaimModel.workspace_id == workspace_id)
            rows = db.execute(statement).scalars().all()
            return [_claim_payload(row) for row in rows]

    def get_claim(self, claim_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(ClaimModel).where(ClaimModel.claim_id == claim_id)
            if workspace_id is not None:
                statement = statement.where(ClaimModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted claim found for '{claim_id}'.")
            return _claim_payload(record)


class ExperimentRequestRepository:
    def __init__(
        self,
        session_repository: SessionRepository | None = None,
        claim_repository: ClaimRepository | None = None,
    ) -> None:
        self.session_repository = session_repository or SessionRepository()
        self.claim_repository = claim_repository or ClaimRepository(session_repository=self.session_repository)

    def upsert_experiment_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = validate_experiment_request_record(payload)
        if not record_payload.get("workspace_id"):
            try:
                record_payload["workspace_id"] = self.session_repository.get_session(record_payload["session_id"])["workspace_id"]
            except FileNotFoundError:
                record_payload["workspace_id"] = LEGACY_WORKSPACE_ID
        self.session_repository.upsert_session(
            session_id=record_payload["session_id"],
            workspace_id=record_payload["workspace_id"],
            created_by_user_id=record_payload.get("requested_by_user_id") or None,
        )
        claim_payload = self.claim_repository.get_claim(
            record_payload["claim_id"],
            workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
        )
        with session_scope() as db:
            statement = select(ExperimentRequestModel).where(
                ExperimentRequestModel.workspace_id == (record_payload["workspace_id"] or LEGACY_WORKSPACE_ID),
                ExperimentRequestModel.session_id == record_payload["session_id"],
                ExperimentRequestModel.claim_id == record_payload["claim_id"],
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = ExperimentRequestModel(
                    experiment_request_id=record_payload["experiment_request_id"] or _make_id("expreq"),
                    session_id=record_payload["session_id"],
                    workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                    claim_id=claim_payload["claim_id"],
                    requested_by_user_id=record_payload.get("requested_by_user_id") or None,
                    candidate_id=record_payload["candidate_id"],
                    candidate_reference=record_payload.get("candidate_reference") or {},
                    target_definition_snapshot=record_payload.get("target_definition_snapshot") or {},
                    requested_measurement=record_payload.get("requested_measurement", ""),
                    requested_direction=record_payload.get("requested_direction", ""),
                    rationale_summary=record_payload.get("rationale_summary", ""),
                    priority_tier=record_payload.get("priority_tier", "medium"),
                    status=record_payload.get("status", "proposed"),
                    requested_at=_to_datetime(record_payload["requested_at"]),
                    requested_by=record_payload.get("requested_by", "system") or "system",
                    notes=record_payload.get("notes", ""),
                    metadata_json=record_payload.get("metadata", {}),
                )
            else:
                record.requested_by_user_id = record_payload.get("requested_by_user_id") or None
                record.candidate_id = record_payload["candidate_id"]
                record.candidate_reference = record_payload.get("candidate_reference") or {}
                record.target_definition_snapshot = record_payload.get("target_definition_snapshot") or {}
                record.requested_measurement = record_payload.get("requested_measurement", "")
                record.requested_direction = record_payload.get("requested_direction", "")
                record.rationale_summary = record_payload.get("rationale_summary", "")
                record.priority_tier = record_payload.get("priority_tier", "medium")
                record.status = record_payload.get("status", "proposed")
                record.requested_at = _to_datetime(record_payload["requested_at"])
                record.requested_by = record_payload.get("requested_by", record.requested_by) or record.requested_by
                record.notes = record_payload.get("notes", "")
                record.metadata_json = record_payload.get("metadata", {})
            db.add(record)
            db.flush()
            db.refresh(record)
            return _experiment_request_payload(record)

    def list_experiment_requests(
        self,
        session_id: str | None = None,
        workspace_id: str | None = None,
        claim_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ExperimentRequestModel).order_by(
                ExperimentRequestModel.priority_tier.asc(),
                ExperimentRequestModel.requested_at.asc(),
                ExperimentRequestModel.experiment_request_id.asc(),
            )
            if session_id is not None:
                statement = statement.where(ExperimentRequestModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ExperimentRequestModel.workspace_id == workspace_id)
            if claim_id is not None:
                statement = statement.where(ExperimentRequestModel.claim_id == claim_id)
            rows = db.execute(statement).scalars().all()
            return [_experiment_request_payload(row) for row in rows]

    def get_experiment_request(self, experiment_request_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(ExperimentRequestModel).where(
                ExperimentRequestModel.experiment_request_id == experiment_request_id
            )
            if workspace_id is not None:
                statement = statement.where(ExperimentRequestModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted experiment request found for '{experiment_request_id}'.")
            return _experiment_request_payload(record)


class ExperimentResultRepository:
    def __init__(
        self,
        session_repository: SessionRepository | None = None,
        claim_repository: ClaimRepository | None = None,
        experiment_request_repository: ExperimentRequestRepository | None = None,
    ) -> None:
        self.session_repository = session_repository or SessionRepository()
        self.claim_repository = claim_repository or ClaimRepository(session_repository=self.session_repository)
        self.experiment_request_repository = experiment_request_repository or ExperimentRequestRepository(
            session_repository=self.session_repository,
            claim_repository=self.claim_repository,
        )

    def create_experiment_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = validate_experiment_result_record(payload)
        if not record_payload.get("workspace_id"):
            try:
                record_payload["workspace_id"] = self.session_repository.get_session(record_payload["session_id"])["workspace_id"]
            except FileNotFoundError:
                record_payload["workspace_id"] = LEGACY_WORKSPACE_ID
        self.session_repository.upsert_session(
            session_id=record_payload["session_id"],
            workspace_id=record_payload["workspace_id"],
            created_by_user_id=record_payload.get("ingested_by_user_id") or None,
        )
        if record_payload.get("source_claim_id"):
            self.claim_repository.get_claim(
                record_payload["source_claim_id"],
                workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
            )
        if record_payload.get("source_experiment_request_id"):
            self.experiment_request_repository.get_experiment_request(
                record_payload["source_experiment_request_id"],
                workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
            )

        with session_scope() as db:
            record = ExperimentResultModel(
                experiment_result_id=record_payload["experiment_result_id"] or _make_id("expres"),
                session_id=record_payload["session_id"],
                workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                source_experiment_request_id=record_payload.get("source_experiment_request_id") or None,
                source_claim_id=record_payload.get("source_claim_id") or None,
                ingested_by_user_id=record_payload.get("ingested_by_user_id") or None,
                candidate_id=record_payload["candidate_id"],
                candidate_reference=record_payload.get("candidate_reference") or {},
                target_definition_snapshot=record_payload.get("target_definition_snapshot") or {},
                observed_value=record_payload.get("observed_value"),
                observed_label=record_payload.get("observed_label", ""),
                measurement_unit=record_payload.get("measurement_unit", ""),
                assay_context=record_payload.get("assay_context", ""),
                result_quality=record_payload.get("result_quality", "provisional"),
                result_source=record_payload.get("result_source", "manual_entry"),
                ingested_at=_to_datetime(record_payload["ingested_at"]),
                ingested_by=record_payload.get("ingested_by", ""),
                notes=record_payload.get("notes", ""),
                metadata_json=record_payload.get("metadata", {}),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _experiment_result_payload(record)

    def list_experiment_results(
        self,
        *,
        session_id: str | None = None,
        workspace_id: str | None = None,
        source_experiment_request_id: str | None = None,
        source_claim_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ExperimentResultModel).order_by(
                desc(ExperimentResultModel.ingested_at),
                ExperimentResultModel.experiment_result_id.asc(),
            )
            if session_id is not None:
                statement = statement.where(ExperimentResultModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ExperimentResultModel.workspace_id == workspace_id)
            if source_experiment_request_id is not None:
                statement = statement.where(
                    ExperimentResultModel.source_experiment_request_id == source_experiment_request_id
                )
            if source_claim_id is not None:
                statement = statement.where(ExperimentResultModel.source_claim_id == source_claim_id)
            rows = db.execute(statement).scalars().all()
            return [_experiment_result_payload(row) for row in rows]

    def get_experiment_result(self, experiment_result_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(ExperimentResultModel).where(
                ExperimentResultModel.experiment_result_id == experiment_result_id
            )
            if workspace_id is not None:
                statement = statement.where(ExperimentResultModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted experiment result found for '{experiment_result_id}'.")
            return _experiment_result_payload(record)


class BeliefUpdateRepository:
    def __init__(
        self,
        session_repository: SessionRepository | None = None,
        claim_repository: ClaimRepository | None = None,
        experiment_result_repository: ExperimentResultRepository | None = None,
    ) -> None:
        self.session_repository = session_repository or SessionRepository()
        self.claim_repository = claim_repository or ClaimRepository(session_repository=self.session_repository)
        self.experiment_result_repository = experiment_result_repository or ExperimentResultRepository(
            session_repository=self.session_repository,
            claim_repository=self.claim_repository,
        )

    def upsert_belief_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = validate_belief_update_record(payload)
        if not record_payload.get("workspace_id"):
            try:
                record_payload["workspace_id"] = self.session_repository.get_session(record_payload["session_id"])["workspace_id"]
            except FileNotFoundError:
                record_payload["workspace_id"] = LEGACY_WORKSPACE_ID
        self.session_repository.upsert_session(
            session_id=record_payload["session_id"],
            workspace_id=record_payload["workspace_id"],
            created_by_user_id=record_payload.get("created_by_user_id") or None,
        )
        self.claim_repository.get_claim(
            record_payload["claim_id"],
            workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
        )
        if record_payload.get("experiment_result_id"):
            self.experiment_result_repository.get_experiment_result(
                record_payload["experiment_result_id"],
                workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
            )

        with session_scope() as db:
            statement = select(BeliefUpdateModel).where(
                BeliefUpdateModel.workspace_id == (record_payload["workspace_id"] or LEGACY_WORKSPACE_ID),
                BeliefUpdateModel.claim_id == record_payload["claim_id"],
                BeliefUpdateModel.experiment_result_id == (record_payload.get("experiment_result_id") or None),
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = BeliefUpdateModel(
                    belief_update_id=record_payload["belief_update_id"] or _make_id("belief"),
                    session_id=record_payload["session_id"],
                    workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                    claim_id=record_payload["claim_id"],
                    experiment_result_id=record_payload.get("experiment_result_id") or None,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    candidate_id=record_payload.get("candidate_id", ""),
                    candidate_label=record_payload.get("candidate_label", ""),
                    previous_support_level=record_payload.get("previous_support_level", "limited"),
                    updated_support_level=record_payload.get("updated_support_level", "limited"),
                    update_direction=record_payload.get("update_direction", "unresolved"),
                    update_reason=record_payload.get("update_reason", ""),
                    governance_status=record_payload.get("governance_status", "proposed"),
                    created_at=_to_datetime(record_payload["created_at"]),
                    created_by=record_payload.get("created_by", ""),
                    reviewed_at=_to_datetime(record_payload["reviewed_at"]) if record_payload.get("reviewed_at") else None,
                    reviewed_by=record_payload.get("reviewed_by", ""),
                    metadata_json=record_payload.get("metadata", {}),
                )
            else:
                record.session_id = record_payload["session_id"]
                record.created_by_user_id = record_payload.get("created_by_user_id") or None
                record.candidate_id = record_payload.get("candidate_id", "")
                record.candidate_label = record_payload.get("candidate_label", "")
                record.previous_support_level = record_payload.get("previous_support_level", "limited")
                record.updated_support_level = record_payload.get("updated_support_level", "limited")
                record.update_direction = record_payload.get("update_direction", "unresolved")
                record.update_reason = record_payload.get("update_reason", "")
                record.governance_status = record_payload.get("governance_status", "proposed")
                record.created_at = _to_datetime(record_payload["created_at"])
                record.created_by = record_payload.get("created_by", record.created_by) or record.created_by
                record.reviewed_at = _to_datetime(record_payload["reviewed_at"]) if record_payload.get("reviewed_at") else None
                record.reviewed_by = record_payload.get("reviewed_by", "")
                record.metadata_json = record_payload.get("metadata", {})
            db.add(record)
            db.flush()
            db.refresh(record)
            return _belief_update_payload(record)

    def list_belief_updates(
        self,
        *,
        session_id: str | None = None,
        workspace_id: str | None = None,
        claim_id: str | None = None,
        experiment_result_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(BeliefUpdateModel).order_by(
                desc(BeliefUpdateModel.created_at),
                BeliefUpdateModel.belief_update_id.asc(),
            )
            if session_id is not None:
                statement = statement.where(BeliefUpdateModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(BeliefUpdateModel.workspace_id == workspace_id)
            if claim_id is not None:
                statement = statement.where(BeliefUpdateModel.claim_id == claim_id)
            if experiment_result_id is not None:
                statement = statement.where(BeliefUpdateModel.experiment_result_id == experiment_result_id)
            rows = db.execute(statement).scalars().all()
            return [_belief_update_payload(row) for row in rows]

    def get_belief_update(self, belief_update_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(BeliefUpdateModel).where(BeliefUpdateModel.belief_update_id == belief_update_id)
            if workspace_id is not None:
                statement = statement.where(BeliefUpdateModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted belief update found for '{belief_update_id}'.")
            return _belief_update_payload(record)

    def update_belief_update_governance(
        self,
        *,
        belief_update_id: str,
        workspace_id: str,
        governance_status: str,
        reviewed_at: datetime,
        reviewed_by: str,
        metadata_updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(BeliefUpdateModel).where(
                BeliefUpdateModel.belief_update_id == belief_update_id,
                BeliefUpdateModel.workspace_id == workspace_id,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted belief update found for '{belief_update_id}'.")
            payload = _belief_update_payload(record)
            merged_metadata = dict(payload.get("metadata") or {})
            if isinstance(metadata_updates, dict):
                merged_metadata.update(metadata_updates)
            updated_payload = validate_belief_update_record(
                {
                    **payload,
                    "governance_status": governance_status,
                    "reviewed_at": reviewed_at,
                    "reviewed_by": reviewed_by,
                    "metadata": merged_metadata,
                }
            )
            record.governance_status = updated_payload["governance_status"]
            record.reviewed_at = _to_datetime(updated_payload["reviewed_at"]) if updated_payload.get("reviewed_at") else None
            record.reviewed_by = updated_payload.get("reviewed_by", "")
            record.metadata_json = updated_payload.get("metadata", {})
            db.add(record)
            db.flush()
            db.refresh(record)
            return _belief_update_payload(record)


class BeliefStateRepository:
    def __init__(self, session_repository: SessionRepository | None = None) -> None:
        self.session_repository = session_repository or SessionRepository()

    def upsert_belief_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = validate_belief_state_record(payload)
        with session_scope() as db:
            statement = select(BeliefStateModel).where(
                BeliefStateModel.workspace_id == (record_payload["workspace_id"] or LEGACY_WORKSPACE_ID),
                BeliefStateModel.target_key == record_payload["target_key"],
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = BeliefStateModel(
                    belief_state_id=record_payload["belief_state_id"] or _make_id("beliefstate"),
                    workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                    target_key=record_payload["target_key"],
                    target_definition_snapshot=record_payload.get("target_definition_snapshot") or {},
                    summary_text=record_payload.get("summary_text", ""),
                    active_claim_count=int(record_payload.get("active_claim_count", 0) or 0),
                    supported_claim_count=int(record_payload.get("supported_claim_count", 0) or 0),
                    weakened_claim_count=int(record_payload.get("weakened_claim_count", 0) or 0),
                    unresolved_claim_count=int(record_payload.get("unresolved_claim_count", 0) or 0),
                    last_updated_at=_to_datetime(record_payload["last_updated_at"]),
                    last_update_source=record_payload.get("last_update_source", ""),
                    version=int(record_payload.get("version", 1) or 1),
                    latest_belief_update_refs=record_payload.get("latest_belief_update_refs") or [],
                    support_distribution_summary=record_payload.get("support_distribution_summary", ""),
                    governance_scope_summary=record_payload.get("governance_scope_summary", ""),
                    metadata_json=record_payload.get("metadata", {}),
                )
            else:
                record.target_definition_snapshot = record_payload.get("target_definition_snapshot") or {}
                record.summary_text = record_payload.get("summary_text", "")
                record.active_claim_count = int(record_payload.get("active_claim_count", 0) or 0)
                record.supported_claim_count = int(record_payload.get("supported_claim_count", 0) or 0)
                record.weakened_claim_count = int(record_payload.get("weakened_claim_count", 0) or 0)
                record.unresolved_claim_count = int(record_payload.get("unresolved_claim_count", 0) or 0)
                record.last_updated_at = _to_datetime(record_payload["last_updated_at"])
                record.last_update_source = record_payload.get("last_update_source", "")
                record.version = int(record_payload.get("version", record.version) or record.version or 1)
                record.latest_belief_update_refs = record_payload.get("latest_belief_update_refs") or []
                record.support_distribution_summary = record_payload.get("support_distribution_summary", "")
                record.governance_scope_summary = record_payload.get("governance_scope_summary", "")
                record.metadata_json = record_payload.get("metadata", {})
            db.add(record)
            db.flush()
            db.refresh(record)
            return _belief_state_payload(record)

    def get_belief_state(self, *, workspace_id: str, target_key: str) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(BeliefStateModel).where(
                BeliefStateModel.workspace_id == workspace_id,
                BeliefStateModel.target_key == target_key,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted belief state found for target '{target_key}'.")
            return _belief_state_payload(record)

    def delete_belief_state(self, *, workspace_id: str, target_key: str) -> bool:
        with session_scope() as db:
            statement = select(BeliefStateModel).where(
                BeliefStateModel.workspace_id == workspace_id,
                BeliefStateModel.target_key == target_key,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                return False
            db.delete(record)
            db.flush()
            return True

    def list_belief_states(self, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(BeliefStateModel).order_by(
                desc(BeliefStateModel.last_updated_at),
                BeliefStateModel.target_key.asc(),
            )
            if workspace_id is not None:
                statement = statement.where(BeliefStateModel.workspace_id == workspace_id)
            rows = db.execute(statement).scalars().all()
            return [_belief_state_payload(row) for row in rows]


class WorkspaceUsageRepository:
    def record_event(
        self,
        *,
        workspace_id: str,
        event_type: str,
        quantity: int = 1,
        session_id: str | None = None,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        payload = validate_workspace_usage_event_record(
            {
                "workspace_id": workspace_id,
                "event_type": event_type,
                "quantity": quantity,
                "created_at": created_at or _utc_now(),
                "session_id": session_id or "",
                "job_id": job_id or "",
                "metadata": metadata or {},
            }
        )
        with session_scope() as db:
            record = WorkspaceUsageEventModel(
                workspace_id=payload["workspace_id"],
                event_type=payload["event_type"],
                quantity=int(payload.get("quantity", 1)),
                created_at=_to_datetime(payload["created_at"]),
                session_id=payload.get("session_id") or None,
                job_id=payload.get("job_id") or None,
                metadata_json=payload.get("metadata", {}),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _workspace_usage_payload(record)

    def sum_quantity(
        self,
        *,
        workspace_id: str,
        event_type: str,
        created_at_gte: datetime | None = None,
        created_at_lt: datetime | None = None,
    ) -> int:
        with session_scope() as db:
            statement = select(func.coalesce(func.sum(WorkspaceUsageEventModel.quantity), 0)).where(
                WorkspaceUsageEventModel.workspace_id == workspace_id,
                WorkspaceUsageEventModel.event_type == str(event_type).strip().lower(),
            )
            if created_at_gte is not None:
                statement = statement.where(WorkspaceUsageEventModel.created_at >= created_at_gte)
            if created_at_lt is not None:
                statement = statement.where(WorkspaceUsageEventModel.created_at < created_at_lt)
            return int(db.execute(statement).scalar_one())

    def count_events(
        self,
        *,
        workspace_id: str,
        event_type: str,
        created_at_gte: datetime | None = None,
        created_at_lt: datetime | None = None,
    ) -> int:
        with session_scope() as db:
            statement = select(func.count()).select_from(WorkspaceUsageEventModel).where(
                WorkspaceUsageEventModel.workspace_id == workspace_id,
                WorkspaceUsageEventModel.event_type == str(event_type).strip().lower(),
            )
            if created_at_gte is not None:
                statement = statement.where(WorkspaceUsageEventModel.created_at >= created_at_gte)
            if created_at_lt is not None:
                statement = statement.where(WorkspaceUsageEventModel.created_at < created_at_lt)
            return int(db.execute(statement).scalar_one())

    def list_events(
        self,
        *,
        workspace_id: str,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(WorkspaceUsageEventModel).where(
                WorkspaceUsageEventModel.workspace_id == workspace_id
            ).order_by(WorkspaceUsageEventModel.created_at.asc(), WorkspaceUsageEventModel.id.asc())
            if event_type is not None:
                statement = statement.where(WorkspaceUsageEventModel.event_type == str(event_type).strip().lower())
            rows = db.execute(statement).scalars().all()
            return [_workspace_usage_payload(row) for row in rows]


class BillingWebhookEventRepository:
    def has_event(self, *, provider: str, event_id: str) -> bool:
        with session_scope() as db:
            statement = select(BillingWebhookEventModel.id).where(
                BillingWebhookEventModel.provider == str(provider).strip().lower(),
                BillingWebhookEventModel.event_id == str(event_id).strip(),
            )
            return db.execute(statement).scalar_one_or_none() is not None

    def record_processed_event(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        workspace_id: str | None = None,
        payload: dict[str, Any] | None = None,
        processed_at: datetime | None = None,
    ) -> bool:
        with session_scope() as db:
            record = BillingWebhookEventModel(
                provider=str(provider).strip().lower(),
                event_id=str(event_id).strip(),
                event_type=str(event_type).strip().lower(),
                workspace_id=str(workspace_id or "").strip() or None,
                processed_at=processed_at or _utc_now(),
                payload_json=dict(payload or {}),
            )
            db.add(record)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                return False
            return True

    def list_events(self, *, provider: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(BillingWebhookEventModel).order_by(
                BillingWebhookEventModel.processed_at.asc(),
                BillingWebhookEventModel.id.asc(),
            )
            if provider is not None:
                statement = statement.where(BillingWebhookEventModel.provider == str(provider).strip().lower())
            rows = db.execute(statement).scalars().all()
            return [
                {
                    "provider": row.provider,
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "workspace_id": row.workspace_id or "",
                    "processed_at": row.processed_at,
                    "payload": row.payload_json or {},
                }
                for row in rows
            ]


class ArtifactRepository:
    def __init__(
        self,
        session_repository: SessionRepository | None = None,
        job_repository: JobRepository | None = None,
    ) -> None:
        self.session_repository = session_repository or SessionRepository()
        self.job_repository = job_repository or JobRepository(session_repository=self.session_repository)

    def _resolve_workspace_id(self, *, session_id: str | None, job_id: str | None, workspace_id: str | None) -> str:
        if workspace_id:
            return workspace_id
        if session_id:
            try:
                return self.session_repository.get_session(session_id)["workspace_id"]
            except FileNotFoundError:
                pass
        if job_id:
            try:
                return self.job_repository.get_job(job_id)["workspace_id"]
            except FileNotFoundError:
                pass
        return LEGACY_WORKSPACE_ID

    def register_artifact(
        self,
        *,
        artifact_type: str,
        path: str | Path,
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_path = _normalize_path(path)
        if session_id:
            self.session_repository.upsert_session(session_id=session_id, workspace_id=workspace_id, created_by_user_id=created_by_user_id)
        effective_workspace_id = self._resolve_workspace_id(session_id=session_id, job_id=job_id, workspace_id=workspace_id)
        timestamp = _utc_now()

        with session_scope() as db:
            statement = select(ArtifactRecordModel).where(ArtifactRecordModel.path == normalized_path)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = ArtifactRecordModel(
                    artifact_type=str(artifact_type),
                    path=normalized_path,
                    session_id=session_id,
                    job_id=job_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=created_by_user_id or None,
                    created_at=timestamp,
                    updated_at=timestamp,
                    metadata_json=dict(metadata or {}),
                )
            else:
                if record.workspace_id != effective_workspace_id:
                    raise ValueError("Artifact metadata cannot be reassigned across workspaces.")
                if session_id and record.session_id and record.session_id != session_id:
                    raise ValueError("Artifact metadata cannot be reassigned across sessions.")
                if job_id and record.job_id and record.job_id != job_id and record.session_id != session_id:
                    raise ValueError("Artifact metadata cannot be reassigned across jobs.")
                record.artifact_type = str(artifact_type)
                record.session_id = session_id or record.session_id
                record.job_id = job_id or record.job_id
                record.workspace_id = effective_workspace_id
                record.created_by_user_id = created_by_user_id or record.created_by_user_id
                record.updated_at = timestamp
                record.metadata_json = _merge_dicts(record.metadata_json, metadata)

            db.add(record)
            db.flush()
            db.refresh(record)
            return _artifact_payload(record)

    def register_artifacts(
        self,
        *,
        artifact_refs: dict[str, Any],
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        metadata_by_type: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        saved: list[dict[str, Any]] = []
        for artifact_type, value in dict(artifact_refs or {}).items():
            path_text = str(value or "").strip()
            if not path_text or artifact_type.endswith("_url") or "://" in path_text:
                continue
            try:
                _normalize_path(path_text)
            except ValueError as exc:
                if str(exc) == "Artifact path must point to a file.":
                    continue
                raise
            saved.append(
                self.register_artifact(
                    artifact_type=artifact_type,
                    path=path_text,
                    session_id=session_id,
                    job_id=job_id,
                    workspace_id=workspace_id,
                    created_by_user_id=created_by_user_id,
                    metadata=(metadata_by_type or {}).get(artifact_type),
                )
            )
        return saved

    def get_latest_artifact(
        self,
        *,
        artifact_type: str,
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any] | None:
        with session_scope() as db:
            statement = select(ArtifactRecordModel).where(ArtifactRecordModel.artifact_type == artifact_type)
            if session_id is not None:
                statement = statement.where(ArtifactRecordModel.session_id == session_id)
            if job_id is not None:
                statement = statement.where(ArtifactRecordModel.job_id == job_id)
            if workspace_id is not None:
                statement = statement.where(ArtifactRecordModel.workspace_id == workspace_id)
            statement = statement.order_by(desc(ArtifactRecordModel.updated_at), desc(ArtifactRecordModel.id))
            record = db.execute(statement).scalars().first()
            return _artifact_payload(record) if record is not None else None

    def get_latest_artifact_path(
        self,
        *,
        artifact_type: str,
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
    ) -> Path | None:
        artifact = self.get_latest_artifact(
            artifact_type=artifact_type,
            session_id=session_id,
            job_id=job_id,
            workspace_id=workspace_id,
        )
        if not artifact:
            return None
        try:
            from system.services.artifact_service import ensure_safe_artifact_path

            return ensure_safe_artifact_path(artifact["path"], require_exists=True)
        except (FileNotFoundError, ValueError):
            return None

    def list_artifacts(
        self,
        *,
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ArtifactRecordModel).order_by(ArtifactRecordModel.updated_at.asc(), ArtifactRecordModel.id.asc())
            if session_id is not None:
                statement = statement.where(ArtifactRecordModel.session_id == session_id)
            if job_id is not None:
                statement = statement.where(ArtifactRecordModel.job_id == job_id)
            if workspace_id is not None:
                statement = statement.where(ArtifactRecordModel.workspace_id == workspace_id)
            rows = db.execute(statement).scalars().all()
            return [_artifact_payload(row) for row in rows]
