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
    record_id: int | None = None
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
    record_id: int | None = None
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
    record_id: int | None = None
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


class ClaimEvidenceLinkRecord(ScientificStateModel):
    link_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    claim_id: str
    linked_object_type: str
    linked_object_id: str
    relation_type: str
    summary: str = ""
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ContradictionRecord(ScientificStateModel):
    contradiction_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    claim_id: str = ""
    contradiction_scope: str = "claim"
    contradiction_type: str
    source_object_type: str
    source_object_id: str
    status: str = "unresolved"
    summary: str = ""
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MaterialGoalSpecificationRecord(ScientificStateModel):
    goal_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    raw_user_goal: str
    domain_scope: str = "polymer_material"
    requirement_status: str = "insufficient_needs_clarification"
    structured_requirements: dict[str, Any] = Field(default_factory=dict)
    missing_critical_requirements: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    scientific_target_summary: str = ""
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MaterialGoalEvidenceLineRecord(ScientificStateModel):
    source_object_type: str
    source_object_id: str
    candidate_id: str = ""
    canonical_smiles: str = ""
    relation_to_goal: str = ""
    evidence_kind: str = ""
    summary: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    observed_value: float | None = None
    observed_label: int | None = None
    predicted_value: float | None = None
    confidence: float | None = None
    uncertainty: float | None = None
    rank: int | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class MaterialGoalCandidateDirectionRecord(ScientificStateModel):
    direction_id: str
    direction_label: str
    direction_type: str = "candidate_linked_direction"
    candidate_id: str = ""
    canonical_smiles: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    support_strength: str = "thin"
    supporting_evidence_lines: list[MaterialGoalEvidenceLineRecord] = Field(default_factory=list)
    limitation_lines: list[str] = Field(default_factory=list)
    contradiction_indicators: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_match_summary: str = ""


class MaterialGoalEvidenceResultRecord(ScientificStateModel):
    goal_id: str = ""
    session_id: str
    workspace_id: str
    retrieval_status: str = "not_attempted"
    retrieval_sufficiency: str = "no_grounded_evidence"
    query_summary: dict[str, Any] = Field(default_factory=dict)
    candidate_material_directions: list[MaterialGoalCandidateDirectionRecord] = Field(default_factory=list)
    supporting_evidence_lines: list[MaterialGoalEvidenceLineRecord] = Field(default_factory=list)
    limitation_lines: list[str] = Field(default_factory=list)
    contradiction_indicators: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ExperimentRequestRecord(ScientificStateModel):
    request_id: str
    session_id: str
    workspace_id: str
    created_by_user_id: str = ""
    claim_id: str
    tested_claim_id: str = ""
    candidate_id: str = ""
    canonical_smiles: str = ""
    objective: str = ""
    rationale: str = ""
    requested_measurement: str = ""
    experiment_intent: str = ""
    epistemic_goal_summary: str = ""
    existing_context_summary: str = ""
    strengthening_outcome_description: str = ""
    weakening_outcome_description: str = ""
    expected_learning_value: str = ""
    linked_claim_evidence_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    protocol_context_summary: str = ""
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
    revision_mode: str = "bounded_contradiction_aware"
    contradiction_pressure: str = "none"
    support_balance_summary: str = ""
    revision_rationale: str = ""
    triggering_contradiction_ids: list[str] = Field(default_factory=list)
    triggering_source_summary: str = ""
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
    contradiction_pressure: str = "none"
    support_balance_summary: str = ""
    latest_revision_rationale: str = ""
    latest_update_id: str = ""
    status: str = "active"
    provenance_markers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
