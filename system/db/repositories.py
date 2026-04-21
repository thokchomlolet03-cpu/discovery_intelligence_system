from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError

from system.contracts import (
    validate_artifact_pointer,
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
    ClaimEvidenceLinkModel,
    ContradictionModel,
    MaterialGoalSpecificationModel,
    BeliefStateModel,
    BeliefUpdateModel,
    BillingWebhookEventModel,
    CanonicalCandidateStateModel,
    CanonicalRunMetadataModel,
    ClaimModel,
    CarryoverRecordModel,
    EvidenceRecordModel,
    ExperimentRequestModel,
    ExperimentResultModel,
    JobModel,
    ModelOutputRecordModel,
    RecommendationRecordModel,
    ReviewEventModel,
    SessionModel,
    TargetDefinitionRecordModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
    WorkspaceUsageEventModel,
)
from system.scientific_state.contracts import (
    BeliefStateRecord,
    BeliefUpdateRecord,
    CanonicalCandidateStateRecord,
    CanonicalRunMetadataRecord,
    CarryoverRecord,
    ClaimRecord,
    ClaimEvidenceLinkRecord,
    ContradictionRecord,
    EvidenceRecord,
    ExperimentRequestRecord,
    ExperimentResultRecord,
    MaterialGoalSpecificationRecord,
    ModelOutputRecord,
    RecommendationRecord,
    TargetDefinitionRecord,
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


def _target_definition_record_payload(record: TargetDefinitionRecordModel) -> dict[str, Any]:
    return TargetDefinitionRecord(
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        target_name=record.target_name,
        target_kind=record.target_kind,
        optimization_direction=record.optimization_direction,
        measurement_column=record.measurement_column,
        label_column=record.label_column,
        measurement_unit=record.measurement_unit,
        scientific_meaning=record.scientific_meaning,
        assay_context=record.assay_context,
        dataset_type=record.dataset_type,
        mapping_confidence=record.mapping_confidence,
        success_definition=record.success_definition,
        target_notes=record.target_notes,
        source_payload=record.source_payload or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _evidence_record_payload(record: EvidenceRecordModel) -> dict[str, Any]:
    return EvidenceRecord(
        record_id=record.id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        evidence_type=record.evidence_type,
        entity_id=record.entity_id,
        candidate_id=record.candidate_id,
        smiles=record.smiles,
        canonical_smiles=record.canonical_smiles,
        assay=record.assay,
        target_name=record.target_name,
        observed_value=record.observed_value,
        observed_label=record.observed_label,
        source_row_index=record.source_row_index,
        source_column=record.source_column,
        provenance=record.provenance_json or {},
        payload=record.payload_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _model_output_record_payload(record: ModelOutputRecordModel) -> dict[str, Any]:
    return ModelOutputRecord(
        record_id=record.id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        candidate_id=record.candidate_id,
        smiles=record.smiles,
        canonical_smiles=record.canonical_smiles,
        target_name=record.target_name,
        model_name=record.model_name,
        model_family=record.model_family,
        model_kind=record.model_kind,
        calibration_method=record.calibration_method,
        training_scope=record.training_scope,
        model_source=record.model_source,
        model_source_role=record.model_source_role,
        baseline_fallback_used=record.baseline_fallback_used,
        bridge_state_summary=record.bridge_state_summary,
        confidence=record.confidence,
        uncertainty=record.uncertainty,
        predicted_value=record.predicted_value,
        prediction_dispersion=record.prediction_dispersion,
        novelty=record.novelty,
        applicability=record.applicability_json or {},
        provenance=record.provenance_json or {},
        diagnostics=record.diagnostics_json or {},
        payload=record.payload_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _recommendation_record_payload(record: RecommendationRecordModel) -> dict[str, Any]:
    return RecommendationRecord(
        record_id=record.id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        candidate_id=record.candidate_id,
        smiles=record.smiles,
        canonical_smiles=record.canonical_smiles,
        rank=record.rank,
        decision_intent=record.decision_intent,
        modeling_mode=record.modeling_mode,
        scoring_mode=record.scoring_mode,
        bucket=record.bucket,
        risk=record.risk,
        status=record.status,
        priority_score=record.priority_score,
        experiment_value=record.experiment_value,
        acquisition_score=record.acquisition_score,
        rationale_summary=record.rationale_summary,
        rationale=record.rationale_json or {},
        policy_trace=record.policy_trace_json or {},
        recommendation=record.recommendation_json or {},
        normalized_explanation=record.normalized_explanation_json or {},
        governance=record.governance_json or {},
        payload=record.payload_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _carryover_record_payload(record: CarryoverRecordModel) -> dict[str, Any]:
    return CarryoverRecord(
        workspace_id=record.workspace_id,
        session_id=record.session_id,
        created_by_user_id=record.created_by_user_id or "",
        source_session_id=record.source_session_id,
        source_candidate_id=record.source_candidate_id,
        target_candidate_id=record.target_candidate_id,
        smiles=record.smiles,
        canonical_smiles=record.canonical_smiles,
        carryover_kind=record.carryover_kind,
        match_basis=record.match_basis,
        review_event_id=record.review_event_id,
        source_status=record.source_status,
        source_action=record.source_action,
        source_note=record.source_note,
        source_reviewer=record.source_reviewer,
        source_reviewed_at=record.source_reviewed_at,
        payload=record.payload_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _canonical_run_metadata_payload(record: CanonicalRunMetadataModel) -> dict[str, Any]:
    return CanonicalRunMetadataRecord(
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        source_name=record.source_name,
        input_type=record.input_type,
        decision_intent=record.decision_intent,
        modeling_mode=record.modeling_mode,
        scoring_mode=record.scoring_mode,
        run_contract=record.run_contract_json or {},
        comparison_anchors=record.comparison_anchors_json or {},
        ranking_policy=record.ranking_policy_json or {},
        ranking_diagnostics=record.ranking_diagnostics_json or {},
        trust_summary=record.trust_summary_json or {},
        provenance_markers=record.provenance_markers_json or {},
        source_payload=record.source_payload_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _canonical_candidate_state_payload(record: CanonicalCandidateStateModel) -> dict[str, Any]:
    return CanonicalCandidateStateRecord(
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        candidate_id=record.candidate_id,
        smiles=record.smiles,
        canonical_smiles=record.canonical_smiles,
        rank=record.rank,
        identity_context=record.identity_context_json or {},
        evidence_summary=record.evidence_summary_json or {},
        predictive_summary=record.predictive_summary_json or {},
        recommendation_summary=record.recommendation_summary_json or {},
        governance_summary=record.governance_summary_json or {},
        carryover_summary=record.carryover_summary_json or {},
        trust_summary=record.trust_summary_json or {},
        provenance_markers=record.provenance_markers_json or {},
        source_payload=record.source_payload_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _claim_payload(record: ClaimModel) -> dict[str, Any]:
    return ClaimRecord(
        claim_id=record.claim_id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        candidate_id=record.candidate_id,
        canonical_smiles=record.canonical_smiles,
        run_metadata_session_id=record.run_metadata_session_id,
        claim_scope=record.claim_scope,
        claim_type=record.claim_type,
        claim_text=record.claim_text,
        claim_summary=record.claim_summary_json or {},
        source_basis=record.source_basis,
        support_links=record.support_links_json or {},
        status=record.status,
        provenance_markers=record.provenance_markers_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _claim_evidence_link_payload(record: ClaimEvidenceLinkModel) -> dict[str, Any]:
    return ClaimEvidenceLinkRecord(
        link_id=record.link_id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        claim_id=record.claim_id,
        linked_object_type=record.linked_object_type,
        linked_object_id=record.linked_object_id,
        relation_type=record.relation_type,
        summary=record.summary,
        provenance_markers=record.provenance_markers_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _contradiction_payload(record: ContradictionModel) -> dict[str, Any]:
    return ContradictionRecord(
        contradiction_id=record.contradiction_id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        claim_id=record.claim_id,
        contradiction_scope=record.contradiction_scope,
        contradiction_type=record.contradiction_type,
        source_object_type=record.source_object_type,
        source_object_id=record.source_object_id,
        status=record.status,
        summary=record.summary,
        provenance_markers=record.provenance_markers_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _experiment_request_payload(record: ExperimentRequestModel) -> dict[str, Any]:
    return ExperimentRequestRecord(
        request_id=record.request_id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        claim_id=record.claim_id,
        tested_claim_id=record.tested_claim_id,
        candidate_id=record.candidate_id,
        canonical_smiles=record.canonical_smiles,
        objective=record.objective,
        rationale=record.rationale,
        requested_measurement=record.requested_measurement,
        experiment_intent=record.experiment_intent,
        epistemic_goal_summary=record.epistemic_goal_summary,
        existing_context_summary=record.existing_context_summary,
        strengthening_outcome_description=record.strengthening_outcome_description,
        weakening_outcome_description=record.weakening_outcome_description,
        expected_learning_value=record.expected_learning_value,
        linked_claim_evidence_snapshot=record.linked_claim_evidence_snapshot_json or [],
        protocol_context_summary=record.protocol_context_summary,
        status=record.status,
        provenance_markers=record.provenance_markers_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _experiment_result_payload(record: ExperimentResultModel) -> dict[str, Any]:
    return ExperimentResultRecord(
        result_id=record.result_id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        request_id=record.request_id,
        claim_id=record.claim_id,
        candidate_id=record.candidate_id,
        canonical_smiles=record.canonical_smiles,
        outcome=record.outcome,
        observed_value=record.observed_value,
        observed_label=record.observed_label,
        result_summary=record.result_summary_json or {},
        provenance_markers=record.provenance_markers_json or {},
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _belief_update_payload(record: BeliefUpdateModel) -> dict[str, Any]:
    return BeliefUpdateRecord(
        update_id=record.update_id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        claim_id=record.claim_id,
        result_id=record.result_id,
        update_reason=record.update_reason,
        pre_belief_state=record.pre_belief_state_json or {},
        post_belief_state=record.post_belief_state_json or {},
        deterministic_rule=record.deterministic_rule,
        revision_mode=record.revision_mode,
        contradiction_pressure=record.contradiction_pressure,
        support_balance_summary=record.support_balance_summary,
        revision_rationale=record.revision_rationale,
        triggering_contradiction_ids=record.triggering_contradiction_ids_json or [],
        triggering_source_summary=record.triggering_source_summary,
        provenance_markers=record.provenance_markers_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _belief_state_payload(record: BeliefStateModel) -> dict[str, Any]:
    return BeliefStateRecord(
        belief_state_id=record.belief_state_id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        claim_id=record.claim_id,
        current_state=record.current_state,
        current_strength=record.current_strength,
        support_basis_summary=record.support_basis_summary,
        contradiction_pressure=record.contradiction_pressure,
        support_balance_summary=record.support_balance_summary,
        latest_revision_rationale=record.latest_revision_rationale,
        latest_update_id=record.latest_update_id,
        status=record.status,
        provenance_markers=record.provenance_markers_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


def _material_goal_specification_payload(record: MaterialGoalSpecificationModel) -> dict[str, Any]:
    return MaterialGoalSpecificationRecord(
        goal_id=record.goal_id,
        session_id=record.session_id,
        workspace_id=record.workspace_id,
        created_by_user_id=record.created_by_user_id or "",
        raw_user_goal=record.raw_user_goal,
        domain_scope=record.domain_scope,
        requirement_status=record.requirement_status,
        structured_requirements=record.structured_requirements_json or {},
        missing_critical_requirements=record.missing_critical_requirements_json or [],
        clarification_questions=record.clarification_questions_json or [],
        scientific_target_summary=record.scientific_target_summary,
        provenance_markers=record.provenance_markers_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).dict()


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


class ScientificStateRepository:
    def __init__(self, session_repository: SessionRepository | None = None) -> None:
        self.session_repository = session_repository or SessionRepository()

    def _workspace_id(self, session_id: str, workspace_id: str | None) -> str:
        if workspace_id:
            return workspace_id
        try:
            return self.session_repository.get_session(session_id)["workspace_id"]
        except FileNotFoundError:
            return LEGACY_WORKSPACE_ID

    def upsert_target_definition(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = TargetDefinitionRecord(**payload).dict()
        workspace_id = self._workspace_id(record_payload["session_id"], record_payload.get("workspace_id"))
        with session_scope() as db:
            statement = select(TargetDefinitionRecordModel).where(
                TargetDefinitionRecordModel.session_id == record_payload["session_id"]
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = TargetDefinitionRecordModel(
                    session_id=record_payload["session_id"],
                    workspace_id=workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    created_at=record_payload["created_at"],
                )
            record.workspace_id = workspace_id
            record.created_by_user_id = record_payload.get("created_by_user_id") or record.created_by_user_id
            record.target_name = record_payload["target_name"]
            record.target_kind = record_payload["target_kind"]
            record.optimization_direction = record_payload["optimization_direction"]
            record.measurement_column = record_payload["measurement_column"]
            record.label_column = record_payload["label_column"]
            record.measurement_unit = record_payload["measurement_unit"]
            record.scientific_meaning = record_payload["scientific_meaning"]
            record.assay_context = record_payload["assay_context"]
            record.dataset_type = record_payload["dataset_type"]
            record.mapping_confidence = record_payload["mapping_confidence"]
            record.success_definition = record_payload["success_definition"]
            record.target_notes = record_payload["target_notes"]
            record.source_payload = record_payload["source_payload"]
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _target_definition_record_payload(record)

    def replace_evidence_records(self, *, session_id: str, workspace_id: str | None, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        effective_workspace_id = self._workspace_id(session_id, workspace_id)
        with session_scope() as db:
            db.query(EvidenceRecordModel).filter(EvidenceRecordModel.session_id == session_id).delete()
            created: list[dict[str, Any]] = []
            for payload in payloads:
                record_payload = EvidenceRecord(**payload, session_id=session_id, workspace_id=effective_workspace_id).dict()
                record = EvidenceRecordModel(
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    evidence_type=record_payload["evidence_type"],
                    entity_id=record_payload["entity_id"],
                    candidate_id=record_payload["candidate_id"],
                    smiles=record_payload["smiles"],
                    canonical_smiles=record_payload["canonical_smiles"],
                    assay=record_payload["assay"],
                    target_name=record_payload["target_name"],
                    observed_value=record_payload["observed_value"],
                    observed_label=record_payload["observed_label"],
                    source_row_index=record_payload["source_row_index"],
                    source_column=record_payload["source_column"],
                    provenance_json=record_payload["provenance"],
                    payload_json=record_payload["payload"],
                    created_at=record_payload["created_at"],
                    updated_at=record_payload["updated_at"],
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                created.append(_evidence_record_payload(record))
            return created

    def replace_model_outputs(self, *, session_id: str, workspace_id: str | None, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        effective_workspace_id = self._workspace_id(session_id, workspace_id)
        with session_scope() as db:
            db.query(ModelOutputRecordModel).filter(ModelOutputRecordModel.session_id == session_id).delete()
            created: list[dict[str, Any]] = []
            for payload in payloads:
                record_payload = ModelOutputRecord(**payload, session_id=session_id, workspace_id=effective_workspace_id).dict()
                record = ModelOutputRecordModel(
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    candidate_id=record_payload["candidate_id"],
                    smiles=record_payload["smiles"],
                    canonical_smiles=record_payload["canonical_smiles"],
                    target_name=record_payload["target_name"],
                    model_name=record_payload["model_name"],
                    model_family=record_payload["model_family"],
                    model_kind=record_payload["model_kind"],
                    calibration_method=record_payload["calibration_method"],
                    training_scope=record_payload["training_scope"],
                    model_source=record_payload["model_source"],
                    model_source_role=record_payload["model_source_role"],
                    baseline_fallback_used=record_payload["baseline_fallback_used"],
                    bridge_state_summary=record_payload["bridge_state_summary"],
                    confidence=record_payload["confidence"],
                    uncertainty=record_payload["uncertainty"],
                    predicted_value=record_payload["predicted_value"],
                    prediction_dispersion=record_payload["prediction_dispersion"],
                    novelty=record_payload["novelty"],
                    applicability_json=record_payload["applicability"],
                    provenance_json=record_payload["provenance"],
                    diagnostics_json=record_payload["diagnostics"],
                    payload_json=record_payload["payload"],
                    created_at=record_payload["created_at"],
                    updated_at=record_payload["updated_at"],
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                created.append(_model_output_record_payload(record))
            return created

    def replace_recommendations(self, *, session_id: str, workspace_id: str | None, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        effective_workspace_id = self._workspace_id(session_id, workspace_id)
        with session_scope() as db:
            db.query(RecommendationRecordModel).filter(RecommendationRecordModel.session_id == session_id).delete()
            created: list[dict[str, Any]] = []
            for payload in payloads:
                record_payload = RecommendationRecord(**payload, session_id=session_id, workspace_id=effective_workspace_id).dict()
                record = RecommendationRecordModel(
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    candidate_id=record_payload["candidate_id"],
                    smiles=record_payload["smiles"],
                    canonical_smiles=record_payload["canonical_smiles"],
                    rank=record_payload["rank"],
                    decision_intent=record_payload["decision_intent"],
                    modeling_mode=record_payload["modeling_mode"],
                    scoring_mode=record_payload["scoring_mode"],
                    bucket=record_payload["bucket"],
                    risk=record_payload["risk"],
                    status=record_payload["status"],
                    priority_score=record_payload["priority_score"],
                    experiment_value=record_payload["experiment_value"],
                    acquisition_score=record_payload["acquisition_score"],
                    rationale_summary=record_payload["rationale_summary"],
                    rationale_json=record_payload["rationale"],
                    policy_trace_json=record_payload["policy_trace"],
                    recommendation_json=record_payload["recommendation"],
                    normalized_explanation_json=record_payload["normalized_explanation"],
                    governance_json=record_payload["governance"],
                    payload_json=record_payload["payload"],
                    created_at=record_payload["created_at"],
                    updated_at=record_payload["updated_at"],
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                created.append(_recommendation_record_payload(record))
            return created

    def replace_carryover_records(self, *, session_id: str, workspace_id: str | None, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        effective_workspace_id = self._workspace_id(session_id, workspace_id)
        with session_scope() as db:
            db.query(CarryoverRecordModel).filter(CarryoverRecordModel.session_id == session_id).delete()
            created: list[dict[str, Any]] = []
            for payload in payloads:
                record_payload = CarryoverRecord(**payload, session_id=session_id, workspace_id=effective_workspace_id).dict()
                record = CarryoverRecordModel(
                    workspace_id=effective_workspace_id,
                    session_id=session_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    source_session_id=record_payload["source_session_id"],
                    source_candidate_id=record_payload["source_candidate_id"],
                    target_candidate_id=record_payload["target_candidate_id"],
                    smiles=record_payload["smiles"],
                    canonical_smiles=record_payload["canonical_smiles"],
                    carryover_kind=record_payload["carryover_kind"],
                    match_basis=record_payload["match_basis"],
                    review_event_id=record_payload["review_event_id"],
                    source_status=record_payload["source_status"],
                    source_action=record_payload["source_action"],
                    source_note=record_payload["source_note"],
                    source_reviewer=record_payload["source_reviewer"],
                    source_reviewed_at=record_payload["source_reviewed_at"],
                    payload_json=record_payload["payload"],
                    created_at=record_payload["created_at"],
                    updated_at=record_payload["updated_at"],
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                created.append(_carryover_record_payload(record))
            return created

    def upsert_run_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = CanonicalRunMetadataRecord(**payload).dict()
        workspace_id = self._workspace_id(record_payload["session_id"], record_payload.get("workspace_id"))
        with session_scope() as db:
            statement = select(CanonicalRunMetadataModel).where(
                CanonicalRunMetadataModel.session_id == record_payload["session_id"]
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = CanonicalRunMetadataModel(
                    session_id=record_payload["session_id"],
                    workspace_id=workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    created_at=record_payload["created_at"],
                )
            record.workspace_id = workspace_id
            record.created_by_user_id = record_payload.get("created_by_user_id") or record.created_by_user_id
            record.source_name = record_payload["source_name"]
            record.input_type = record_payload["input_type"]
            record.decision_intent = record_payload["decision_intent"]
            record.modeling_mode = record_payload["modeling_mode"]
            record.scoring_mode = record_payload["scoring_mode"]
            record.run_contract_json = record_payload["run_contract"]
            record.comparison_anchors_json = record_payload["comparison_anchors"]
            record.ranking_policy_json = record_payload["ranking_policy"]
            record.ranking_diagnostics_json = record_payload["ranking_diagnostics"]
            record.trust_summary_json = record_payload["trust_summary"]
            record.provenance_markers_json = record_payload["provenance_markers"]
            record.source_payload_json = record_payload["source_payload"]
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _canonical_run_metadata_payload(record)

    def replace_candidate_states(self, *, session_id: str, workspace_id: str | None, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        effective_workspace_id = self._workspace_id(session_id, workspace_id)
        with session_scope() as db:
            db.query(CanonicalCandidateStateModel).filter(CanonicalCandidateStateModel.session_id == session_id).delete()
            created: list[dict[str, Any]] = []
            for payload in payloads:
                record_payload = CanonicalCandidateStateRecord(**payload, session_id=session_id, workspace_id=effective_workspace_id).dict()
                record = CanonicalCandidateStateModel(
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    candidate_id=record_payload["candidate_id"],
                    smiles=record_payload["smiles"],
                    canonical_smiles=record_payload["canonical_smiles"],
                    rank=record_payload["rank"],
                    identity_context_json=record_payload["identity_context"],
                    evidence_summary_json=record_payload["evidence_summary"],
                    predictive_summary_json=record_payload["predictive_summary"],
                    recommendation_summary_json=record_payload["recommendation_summary"],
                    governance_summary_json=record_payload["governance_summary"],
                    carryover_summary_json=record_payload["carryover_summary"],
                    trust_summary_json=record_payload["trust_summary"],
                    provenance_markers_json=record_payload["provenance_markers"],
                    source_payload_json=record_payload["source_payload"],
                    created_at=record_payload["created_at"],
                    updated_at=record_payload["updated_at"],
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                created.append(_canonical_candidate_state_payload(record))
            return created

    def list_evidence_records(self, *, session_id: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(EvidenceRecordModel).where(EvidenceRecordModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(EvidenceRecordModel.workspace_id == workspace_id)
            statement = statement.order_by(EvidenceRecordModel.id.asc())
            return [_evidence_record_payload(row) for row in db.execute(statement).scalars().all()]

    def list_model_outputs(self, *, session_id: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ModelOutputRecordModel).where(ModelOutputRecordModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ModelOutputRecordModel.workspace_id == workspace_id)
            statement = statement.order_by(ModelOutputRecordModel.id.asc())
            return [_model_output_record_payload(row) for row in db.execute(statement).scalars().all()]

    def list_recommendations(self, *, session_id: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(RecommendationRecordModel).where(RecommendationRecordModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(RecommendationRecordModel.workspace_id == workspace_id)
            statement = statement.order_by(RecommendationRecordModel.rank.asc(), RecommendationRecordModel.id.asc())
            return [_recommendation_record_payload(row) for row in db.execute(statement).scalars().all()]

    def get_target_definition(self, *, session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(TargetDefinitionRecordModel).where(TargetDefinitionRecordModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(TargetDefinitionRecordModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No scientific target definition found for '{session_id}'.")
            return _target_definition_record_payload(record)

    def list_carryover_records(self, *, session_id: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(CarryoverRecordModel).where(CarryoverRecordModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(CarryoverRecordModel.workspace_id == workspace_id)
            statement = statement.order_by(CarryoverRecordModel.updated_at.asc(), CarryoverRecordModel.id.asc())
            return [_carryover_record_payload(row) for row in db.execute(statement).scalars().all()]

    def recommendation_state_map(self, *, session_id: str, workspace_id: str | None = None) -> dict[str, dict[str, Any]]:
        rows = self.list_recommendations(session_id=session_id, workspace_id=workspace_id)
        return {
            f"{str(item.get('candidate_id') or '')}::{str(item.get('canonical_smiles') or item.get('smiles') or '')}": item
            for item in rows
        }

    def get_run_metadata(self, *, session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(CanonicalRunMetadataModel).where(CanonicalRunMetadataModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(CanonicalRunMetadataModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No canonical run metadata found for '{session_id}'.")
            return _canonical_run_metadata_payload(record)

    def list_candidate_states(self, *, session_id: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(CanonicalCandidateStateModel).where(CanonicalCandidateStateModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(CanonicalCandidateStateModel.workspace_id == workspace_id)
            statement = statement.order_by(CanonicalCandidateStateModel.rank.asc(), CanonicalCandidateStateModel.id.asc())
            return [_canonical_candidate_state_payload(row) for row in db.execute(statement).scalars().all()]

    def replace_claims(self, *, session_id: str, workspace_id: str | None, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        effective_workspace_id = self._workspace_id(session_id, workspace_id)
        with session_scope() as db:
            db.query(ClaimModel).filter(ClaimModel.session_id == session_id).delete()
            created: list[dict[str, Any]] = []
            for payload in payloads:
                record_payload = ClaimRecord(**payload, session_id=session_id, workspace_id=effective_workspace_id).dict()
                record = ClaimModel(
                    claim_id=record_payload["claim_id"],
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    candidate_id=record_payload["candidate_id"],
                    canonical_smiles=record_payload["canonical_smiles"],
                    run_metadata_session_id=record_payload["run_metadata_session_id"],
                    claim_scope=record_payload["claim_scope"],
                    claim_type=record_payload["claim_type"],
                    claim_text=record_payload["claim_text"],
                    claim_summary_json=record_payload["claim_summary"],
                    source_basis=record_payload["source_basis"],
                    support_links_json=record_payload["support_links"],
                    status=record_payload["status"],
                    provenance_markers_json=record_payload["provenance_markers"],
                    created_at=record_payload["created_at"],
                    updated_at=record_payload["updated_at"],
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                created.append(_claim_payload(record))
            return created

    def replace_claim_evidence_links(self, *, session_id: str, workspace_id: str | None, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        effective_workspace_id = self._workspace_id(session_id, workspace_id)
        with session_scope() as db:
            db.query(ClaimEvidenceLinkModel).filter(ClaimEvidenceLinkModel.session_id == session_id).delete()
            created: list[dict[str, Any]] = []
            for payload in payloads:
                record_payload = ClaimEvidenceLinkRecord(**payload, session_id=session_id, workspace_id=effective_workspace_id).dict()
                record = ClaimEvidenceLinkModel(
                    link_id=record_payload["link_id"],
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    claim_id=record_payload["claim_id"],
                    linked_object_type=record_payload["linked_object_type"],
                    linked_object_id=record_payload["linked_object_id"],
                    relation_type=record_payload["relation_type"],
                    summary=record_payload["summary"],
                    provenance_markers_json=record_payload["provenance_markers"],
                    created_at=record_payload["created_at"],
                    updated_at=record_payload["updated_at"],
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                created.append(_claim_evidence_link_payload(record))
            return created

    def list_claims(self, *, session_id: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ClaimModel).where(ClaimModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ClaimModel.workspace_id == workspace_id)
            statement = statement.order_by(ClaimModel.created_at.asc(), ClaimModel.id.asc())
            return [_claim_payload(row) for row in db.execute(statement).scalars().all()]

    def get_claim(self, *, claim_id: str) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(ClaimModel).where(ClaimModel.claim_id == claim_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No claim found for '{claim_id}'.")
            return _claim_payload(record)

    def list_claim_evidence_links(
        self,
        *,
        claim_id: str | None = None,
        session_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ClaimEvidenceLinkModel)
            if claim_id is not None:
                statement = statement.where(ClaimEvidenceLinkModel.claim_id == claim_id)
            if session_id is not None:
                statement = statement.where(ClaimEvidenceLinkModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ClaimEvidenceLinkModel.workspace_id == workspace_id)
            statement = statement.order_by(ClaimEvidenceLinkModel.created_at.asc(), ClaimEvidenceLinkModel.id.asc())
            return [_claim_evidence_link_payload(row) for row in db.execute(statement).scalars().all()]

    def replace_contradictions(self, *, session_id: str, workspace_id: str | None, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        effective_workspace_id = self._workspace_id(session_id, workspace_id)
        with session_scope() as db:
            db.query(ContradictionModel).filter(ContradictionModel.session_id == session_id).delete()
            created: list[dict[str, Any]] = []
            for payload in payloads:
                record_payload = ContradictionRecord(**payload, session_id=session_id, workspace_id=effective_workspace_id).dict()
                record = ContradictionModel(
                    contradiction_id=record_payload["contradiction_id"],
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    claim_id=record_payload.get("claim_id", ""),
                    contradiction_scope=record_payload.get("contradiction_scope", "claim"),
                    contradiction_type=record_payload["contradiction_type"],
                    source_object_type=record_payload["source_object_type"],
                    source_object_id=record_payload["source_object_id"],
                    status=record_payload.get("status", "unresolved"),
                    summary=record_payload.get("summary", ""),
                    provenance_markers_json=record_payload.get("provenance_markers", {}),
                    created_at=record_payload["created_at"],
                    updated_at=record_payload["updated_at"],
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                created.append(_contradiction_payload(record))
            return created

    def upsert_material_goal_specification(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = MaterialGoalSpecificationRecord(**payload).dict()
        with session_scope() as db:
            statement = select(MaterialGoalSpecificationModel).where(MaterialGoalSpecificationModel.session_id == record_payload["session_id"])
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = MaterialGoalSpecificationModel(
                    goal_id=record_payload["goal_id"],
                    session_id=record_payload["session_id"],
                    workspace_id=record_payload["workspace_id"],
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    created_at=record_payload["created_at"],
                )
            record.workspace_id = record_payload["workspace_id"]
            record.created_by_user_id = record_payload.get("created_by_user_id") or record.created_by_user_id
            record.raw_user_goal = record_payload["raw_user_goal"]
            record.domain_scope = record_payload["domain_scope"]
            record.requirement_status = record_payload["requirement_status"]
            record.structured_requirements_json = record_payload["structured_requirements"]
            record.missing_critical_requirements_json = record_payload["missing_critical_requirements"]
            record.clarification_questions_json = record_payload["clarification_questions"]
            record.scientific_target_summary = record_payload["scientific_target_summary"]
            record.provenance_markers_json = record_payload["provenance_markers"]
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _material_goal_specification_payload(record)

    def get_material_goal_specification(self, *, session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(MaterialGoalSpecificationModel).where(MaterialGoalSpecificationModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(MaterialGoalSpecificationModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No material goal specification found for '{session_id}'.")
            return _material_goal_specification_payload(record)

    def list_contradictions(
        self,
        *,
        claim_id: str | None = None,
        session_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ContradictionModel)
            if claim_id is not None:
                statement = statement.where(ContradictionModel.claim_id == claim_id)
            if session_id is not None:
                statement = statement.where(ContradictionModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ContradictionModel.workspace_id == workspace_id)
            statement = statement.order_by(ContradictionModel.created_at.asc(), ContradictionModel.id.asc())
            return [_contradiction_payload(row) for row in db.execute(statement).scalars().all()]

    def update_contradiction_status(self, *, contradiction_id: str, status: str) -> dict[str, Any]:
        with session_scope() as db:
            record = db.execute(select(ContradictionModel).where(ContradictionModel.contradiction_id == contradiction_id)).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No contradiction found for '{contradiction_id}'.")
            record.status = status
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _contradiction_payload(record)

    def record_experiment_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = ExperimentRequestRecord(**payload).dict()
        with session_scope() as db:
            record = ExperimentRequestModel(
                request_id=record_payload["request_id"],
                session_id=record_payload["session_id"],
                workspace_id=record_payload["workspace_id"],
                created_by_user_id=record_payload.get("created_by_user_id") or None,
                claim_id=record_payload["claim_id"],
                tested_claim_id=record_payload.get("tested_claim_id", ""),
                candidate_id=record_payload["candidate_id"],
                canonical_smiles=record_payload["canonical_smiles"],
                objective=record_payload["objective"],
                rationale=record_payload["rationale"],
                requested_measurement=record_payload["requested_measurement"],
                experiment_intent=record_payload.get("experiment_intent", ""),
                epistemic_goal_summary=record_payload.get("epistemic_goal_summary", ""),
                existing_context_summary=record_payload.get("existing_context_summary", ""),
                strengthening_outcome_description=record_payload.get("strengthening_outcome_description", ""),
                weakening_outcome_description=record_payload.get("weakening_outcome_description", ""),
                expected_learning_value=record_payload.get("expected_learning_value", ""),
                linked_claim_evidence_snapshot_json=record_payload.get("linked_claim_evidence_snapshot", []),
                protocol_context_summary=record_payload.get("protocol_context_summary", ""),
                status=record_payload["status"],
                provenance_markers_json=record_payload["provenance_markers"],
                created_at=record_payload["created_at"],
                updated_at=record_payload["updated_at"],
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _experiment_request_payload(record)

    def update_experiment_request_status(self, *, request_id: str, status: str) -> dict[str, Any]:
        with session_scope() as db:
            record = db.execute(select(ExperimentRequestModel).where(ExperimentRequestModel.request_id == request_id)).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No experiment request found for '{request_id}'.")
            record.status = status
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _experiment_request_payload(record)

    def list_experiment_requests(self, *, claim_id: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ExperimentRequestModel)
            if claim_id is not None:
                statement = statement.where(ExperimentRequestModel.claim_id == claim_id)
            if session_id is not None:
                statement = statement.where(ExperimentRequestModel.session_id == session_id)
            statement = statement.order_by(ExperimentRequestModel.created_at.asc(), ExperimentRequestModel.id.asc())
            return [_experiment_request_payload(row) for row in db.execute(statement).scalars().all()]

    def record_experiment_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = ExperimentResultRecord(**payload).dict()
        with session_scope() as db:
            record = ExperimentResultModel(
                result_id=record_payload["result_id"],
                session_id=record_payload["session_id"],
                workspace_id=record_payload["workspace_id"],
                created_by_user_id=record_payload.get("created_by_user_id") or None,
                request_id=record_payload["request_id"],
                claim_id=record_payload["claim_id"],
                candidate_id=record_payload["candidate_id"],
                canonical_smiles=record_payload["canonical_smiles"],
                outcome=record_payload["outcome"],
                observed_value=record_payload["observed_value"],
                observed_label=record_payload["observed_label"],
                result_summary_json=record_payload["result_summary"],
                provenance_markers_json=record_payload["provenance_markers"],
                status=record_payload["status"],
                created_at=record_payload["created_at"],
                updated_at=record_payload["updated_at"],
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _experiment_result_payload(record)

    def list_experiment_results(self, *, request_id: str | None = None, claim_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ExperimentResultModel)
            if request_id is not None:
                statement = statement.where(ExperimentResultModel.request_id == request_id)
            if claim_id is not None:
                statement = statement.where(ExperimentResultModel.claim_id == claim_id)
            statement = statement.order_by(ExperimentResultModel.created_at.asc(), ExperimentResultModel.id.asc())
            return [_experiment_result_payload(row) for row in db.execute(statement).scalars().all()]

    def record_belief_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = BeliefUpdateRecord(**payload).dict()
        with session_scope() as db:
            record = BeliefUpdateModel(
                update_id=record_payload["update_id"],
                session_id=record_payload["session_id"],
                workspace_id=record_payload["workspace_id"],
                created_by_user_id=record_payload.get("created_by_user_id") or None,
                claim_id=record_payload["claim_id"],
                result_id=record_payload["result_id"],
                update_reason=record_payload["update_reason"],
                pre_belief_state_json=record_payload["pre_belief_state"],
                post_belief_state_json=record_payload["post_belief_state"],
                deterministic_rule=record_payload["deterministic_rule"],
                revision_mode=record_payload["revision_mode"],
                contradiction_pressure=record_payload["contradiction_pressure"],
                support_balance_summary=record_payload["support_balance_summary"],
                revision_rationale=record_payload["revision_rationale"],
                triggering_contradiction_ids_json=record_payload["triggering_contradiction_ids"],
                triggering_source_summary=record_payload["triggering_source_summary"],
                provenance_markers_json=record_payload["provenance_markers"],
                created_at=record_payload["created_at"],
                updated_at=record_payload["updated_at"],
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _belief_update_payload(record)

    def list_belief_updates(self, *, claim_id: str | None = None, result_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(BeliefUpdateModel)
            if claim_id is not None:
                statement = statement.where(BeliefUpdateModel.claim_id == claim_id)
            if result_id is not None:
                statement = statement.where(BeliefUpdateModel.result_id == result_id)
            statement = statement.order_by(BeliefUpdateModel.created_at.asc(), BeliefUpdateModel.id.asc())
            return [_belief_update_payload(row) for row in db.execute(statement).scalars().all()]

    def upsert_belief_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = BeliefStateRecord(**payload).dict()
        with session_scope() as db:
            statement = select(BeliefStateModel).where(BeliefStateModel.claim_id == record_payload["claim_id"])
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = BeliefStateModel(
                    belief_state_id=record_payload["belief_state_id"],
                    session_id=record_payload["session_id"],
                    workspace_id=record_payload["workspace_id"],
                    created_by_user_id=record_payload.get("created_by_user_id") or None,
                    claim_id=record_payload["claim_id"],
                    created_at=record_payload["created_at"],
                )
            record.current_state = record_payload["current_state"]
            record.current_strength = record_payload["current_strength"]
            record.support_basis_summary = record_payload["support_basis_summary"]
            record.contradiction_pressure = record_payload["contradiction_pressure"]
            record.support_balance_summary = record_payload["support_balance_summary"]
            record.latest_revision_rationale = record_payload["latest_revision_rationale"]
            record.latest_update_id = record_payload["latest_update_id"]
            record.status = record_payload["status"]
            record.provenance_markers_json = record_payload["provenance_markers"]
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _belief_state_payload(record)

    def get_belief_state(self, *, claim_id: str) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(BeliefStateModel).where(BeliefStateModel.claim_id == claim_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No belief state found for claim '{claim_id}'.")
            return _belief_state_payload(record)


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
