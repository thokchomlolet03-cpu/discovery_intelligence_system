from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScientificStateModel(BaseModel):
    class Config:
        extra = "forbid"
        validate_assignment = True


class TargetDefinitionRecord(ScientificStateModel):
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    target_name: str = ""
    target_kind: str = "classification"
    optimization_direction: str = "classify"
    measurement_column: str = ""
    label_column: str = ""
    measurement_unit: str = ""
    scientific_meaning: str = ""
    assay_context: str = ""
    dataset_type: str = ""
    mapping_confidence: str = ""
    derived_label_rule: dict[str, Any] | None = None
    success_definition: str = ""
    target_notes: str = ""
    source_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EvidenceRecord(ScientificStateModel):
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    evidence_type: str
    entity_id: str = ""
    candidate_id: str = ""
    smiles: str = ""
    canonical_smiles: str = ""
    assay: str = ""
    target_name: str = ""
    observed_value: float | None = None
    observed_label: int | None = None
    source_row_index: int | None = None
    source_column: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ModelOutputRecord(ScientificStateModel):
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    candidate_id: str
    smiles: str = ""
    canonical_smiles: str = ""
    target_name: str = ""
    model_name: str = ""
    model_family: str = ""
    model_kind: str = ""
    calibration_method: str = ""
    training_scope: str = ""
    model_source: str = ""
    model_source_role: str = ""
    baseline_fallback_used: bool = False
    bridge_state_summary: str = ""
    confidence: float | None = None
    uncertainty: float | None = None
    predicted_value: float | None = None
    prediction_dispersion: float | None = None
    novelty: float | None = None
    applicability: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RecommendationRecord(ScientificStateModel):
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    candidate_id: str
    smiles: str = ""
    canonical_smiles: str = ""
    rank: int = 0
    decision_intent: str = ""
    modeling_mode: str = ""
    scoring_mode: str = ""
    bucket: str = ""
    risk: str = ""
    status: str = "suggested"
    priority_score: float | None = None
    experiment_value: float | None = None
    acquisition_score: float | None = None
    rationale_summary: str = ""
    rationale: dict[str, Any] = Field(default_factory=dict)
    policy_trace: dict[str, Any] = Field(default_factory=dict)
    recommendation: dict[str, Any] = Field(default_factory=dict)
    normalized_explanation: dict[str, Any] = Field(default_factory=dict)
    governance: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CarryoverRecord(ScientificStateModel):
    workspace_id: str
    session_id: str
    created_by_user_id: str = ""
    source_session_id: str
    source_candidate_id: str = ""
    target_candidate_id: str = ""
    smiles: str = ""
    canonical_smiles: str = ""
    carryover_kind: str = "review_memory"
    match_basis: str = "canonical_smiles"
    review_event_id: int | None = None
    source_status: str = ""
    source_action: str = ""
    source_note: str = ""
    source_reviewer: str = ""
    source_reviewed_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CanonicalRunMetadataRecord(ScientificStateModel):
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    source_name: str = ""
    input_type: str = ""
    decision_intent: str = ""
    modeling_mode: str = ""
    scoring_mode: str = ""
    run_contract: dict[str, Any] = Field(default_factory=dict)
    comparison_anchors: dict[str, Any] = Field(default_factory=dict)
    ranking_policy: dict[str, Any] = Field(default_factory=dict)
    ranking_diagnostics: dict[str, Any] = Field(default_factory=dict)
    trust_summary: dict[str, Any] = Field(default_factory=dict)
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    source_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CanonicalCandidateStateRecord(ScientificStateModel):
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    candidate_id: str
    smiles: str = ""
    canonical_smiles: str = ""
    rank: int = 0
    identity_context: dict[str, Any] = Field(default_factory=dict)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    predictive_summary: dict[str, Any] = Field(default_factory=dict)
    recommendation_summary: dict[str, Any] = Field(default_factory=dict)
    governance_summary: dict[str, Any] = Field(default_factory=dict)
    carryover_summary: dict[str, Any] = Field(default_factory=dict)
    trust_summary: dict[str, Any] = Field(default_factory=dict)
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    source_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ClaimRecord(ScientificStateModel):
    claim_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    candidate_id: str = ""
    canonical_smiles: str = ""
    run_metadata_session_id: str = ""
    claim_scope: str = "candidate"
    claim_type: str = ""
    claim_text: str = ""
    claim_summary: dict[str, Any] = Field(default_factory=dict)
    source_basis: str = ""
    support_links: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ExperimentRequestRecord(ScientificStateModel):
    request_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    claim_id: str
    candidate_id: str = ""
    canonical_smiles: str = ""
    objective: str = ""
    rationale: str = ""
    requested_measurement: str = ""
    status: str = "requested"
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ExperimentResultRecord(ScientificStateModel):
    result_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    request_id: str
    claim_id: str
    candidate_id: str = ""
    canonical_smiles: str = ""
    outcome: str = ""
    observed_value: float | None = None
    observed_label: int | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    status: str = "recorded"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BeliefUpdateRecord(ScientificStateModel):
    update_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    claim_id: str
    result_id: str
    update_reason: str = ""
    pre_belief_state: dict[str, Any] = Field(default_factory=dict)
    post_belief_state: dict[str, Any] = Field(default_factory=dict)
    deterministic_rule: str = ""
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class BeliefStateRecord(ScientificStateModel):
    belief_state_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    claim_id: str
    current_state: str = "unresolved"
    current_strength: str = "tentative"
    support_basis_summary: str = ""
    latest_update_id: str = ""
    status: str = "active"
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
