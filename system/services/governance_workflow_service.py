from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    validate_governance_inbox,
    validate_governance_inbox_item,
    validate_governance_inbox_summary,
)
from system.services.governed_review_service import (
    build_governed_review_overlay,
    REVIEW_ORIGIN_DERIVED,
    REVIEW_ORIGIN_MANUAL,
    SUBJECT_TYPE_BELIEF_STATE,
    SUBJECT_TYPE_CLAIM,
    SUBJECT_TYPE_CONTINUITY_CLUSTER,
    SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER,
    list_subject_governed_reviews,
)
from system.services.support_quality_service import (
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_BLOCKED,
    REVIEW_STATUS_CANDIDATE,
    REVIEW_STATUS_DEFERRED,
    REVIEW_STATUS_DOWNGRADED,
    REVIEW_STATUS_NOT_REVIEWED,
    REVIEW_STATUS_QUARANTINED,
)


LAYER_LABELS = {
    SUBJECT_TYPE_CLAIM: "Claim",
    SUBJECT_TYPE_BELIEF_STATE: "Belief-state",
    SUBJECT_TYPE_CONTINUITY_CLUSTER: "Continuity cluster",
    SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER: "Session-family carryover",
}

LAYER_PRIORITY_BASE = {
    SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER: 90,
    SUBJECT_TYPE_CONTINUITY_CLUSTER: 76,
    SUBJECT_TYPE_BELIEF_STATE: 68,
    SUBJECT_TYPE_CLAIM: 42,
}

PRIORITY_IMMEDIATE = "Immediate attention"
PRIORITY_SOON = "Review soon"
PRIORITY_WATCH = "Watch list"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_truthy(value: Any) -> bool:
    return bool(value)


def _status_rank(status_label: str) -> int:
    status = _clean_text(status_label).lower()
    if status == REVIEW_STATUS_QUARANTINED:
        return 6
    if status == REVIEW_STATUS_DOWNGRADED:
        return 5
    if status == REVIEW_STATUS_BLOCKED:
        return 4
    if status == REVIEW_STATUS_DEFERRED:
        return 3
    if status == REVIEW_STATUS_APPROVED:
        return 2
    if status == REVIEW_STATUS_CANDIDATE:
        return 1
    return 0


def _priority_label(score: int) -> str:
    if score >= 120:
        return PRIORITY_IMMEDIATE
    if score >= 82:
        return PRIORITY_SOON
    return PRIORITY_WATCH


def _origin_summary(origin_label: str, reviewer_label: str, manual_action_label: str) -> str:
    if origin_label == REVIEW_ORIGIN_MANUAL:
        reviewer = _clean_text(reviewer_label, default="a reviewer")
        action = _clean_text(manual_action_label).replace("_", " ").strip()
        if action:
            return f"Current effective posture is explicitly controlled by {reviewer} through a manual {action}."
        return f"Current effective posture is explicitly controlled by {reviewer} rather than by derived posture alone."
    return "Current effective posture is still governed by the derived bridge-state rules because no active manual override is controlling this layer."


def _reviewer_attribution_summary(
    *,
    effective_origin_label: str,
    manual_review_reviewer_label: str,
    manual_action_label: str,
    review_record_count: int,
    manual_review_record_count: int,
    has_superseded_history: bool,
) -> str:
    if effective_origin_label == REVIEW_ORIGIN_MANUAL:
        reviewer = _clean_text(manual_review_reviewer_label, default="a reviewer")
        action = _clean_text(manual_action_label).replace("_", " ").strip()
        base = f"Manual review currently governs this layer through {reviewer}"
        if action:
            base += f" via {action}"
        base += "."
    elif manual_review_record_count > 0:
        reviewer = _clean_text(manual_review_reviewer_label)
        if reviewer:
            base = f"Derived posture currently governs this layer, but {reviewer} has prior manual review history here."
        else:
            base = "Derived posture currently governs this layer, but prior manual review history exists here."
    else:
        base = "This layer is still governed by derived posture only."
    if has_superseded_history:
        base += " Earlier reviewed posture remains visible as superseded history."
    elif review_record_count > 1:
        base += " Multiple review records are preserved in the audit trail."
    return base


def _has_superseded_history(records: list[dict[str, Any]]) -> bool:
    for record in records:
        if not isinstance(record, dict):
            continue
        if not _is_truthy(record.get("active")):
            return True
        if _clean_text(record.get("supersedes_review_record_id")):
            return True
    return False


def _canonicalize_context_with_overlay(context: dict[str, Any]) -> dict[str, Any]:
    workspace_id = _clean_text(context.get("workspace_id"))
    subject_type = _clean_text(context.get("subject_type"))
    subject_id = _clean_text(context.get("subject_id"))
    if not (workspace_id and subject_type and subject_id):
        return dict(context)
    records = list_subject_governed_reviews(
        workspace_id=workspace_id,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    overlay = build_governed_review_overlay(
        records,
        fallback_fields={
            "source_class_label": context.get("source_class_label", ""),
            "trust_tier_label": context.get("trust_tier_label", ""),
            "provenance_confidence_label": context.get("provenance_confidence_label", ""),
            "governed_review_status_label": context.get("effective_review_status_label", ""),
            "governed_review_reason_label": context.get("effective_review_reason_label", ""),
            "governed_review_reason_summary": context.get("effective_review_reason_summary", ""),
            "promotion_gate_status_label": context.get("promotion_gate_status_label", ""),
            "promotion_block_reason_label": context.get("promotion_block_reason_label", ""),
        },
        subject_label=_clean_text(context.get("layer_label"), default="Governance layer"),
    )
    merged = dict(context)
    merged.update(
        {
            "source_class_label": _clean_text(overlay.get("source_class_label") or merged.get("source_class_label")),
            "trust_tier_label": _clean_text(overlay.get("trust_tier_label") or merged.get("trust_tier_label")),
            "provenance_confidence_label": _clean_text(
                overlay.get("provenance_confidence_label") or merged.get("provenance_confidence_label")
            ),
            "effective_review_status_label": _clean_text(
                overlay.get("governed_review_status_label") or merged.get("effective_review_status_label")
            ),
            "effective_review_status_summary": _clean_text(
                overlay.get("governed_review_status_summary") or merged.get("effective_review_status_summary")
            ),
            "effective_review_reason_label": _clean_text(
                overlay.get("governed_review_reason_label") or merged.get("effective_review_reason_label")
            ),
            "effective_review_reason_summary": _clean_text(
                overlay.get("governed_review_reason_summary") or merged.get("effective_review_reason_summary")
            ),
            "effective_review_origin_label": _clean_text(
                overlay.get("effective_governed_review_origin_label") or merged.get("effective_review_origin_label"),
                default=REVIEW_ORIGIN_DERIVED,
            ),
            "effective_review_origin_summary": _clean_text(
                overlay.get("effective_governed_review_origin_summary") or merged.get("effective_review_origin_summary")
            ),
            "derived_review_status_label": _clean_text(
                overlay.get("derived_governed_review_status_label") or merged.get("derived_review_status_label")
            ),
            "derived_review_status_summary": _clean_text(
                overlay.get("derived_governed_review_status_summary") or merged.get("derived_review_status_summary")
            ),
            "derived_review_reason_label": _clean_text(
                overlay.get("derived_governed_review_reason_label") or merged.get("derived_review_reason_label")
            ),
            "derived_review_reason_summary": _clean_text(
                overlay.get("derived_governed_review_reason_summary") or merged.get("derived_review_reason_summary")
            ),
            "manual_review_status_label": _clean_text(
                overlay.get("manual_governed_review_status_label") or merged.get("manual_review_status_label")
            ),
            "manual_review_status_summary": _clean_text(
                overlay.get("manual_governed_review_status_summary") or merged.get("manual_review_status_summary")
            ),
            "manual_review_reason_label": _clean_text(
                overlay.get("manual_governed_review_reason_label") or merged.get("manual_review_reason_label")
            ),
            "manual_review_reason_summary": _clean_text(
                overlay.get("manual_governed_review_reason_summary") or merged.get("manual_review_reason_summary")
            ),
            "manual_review_action_label": _clean_text(
                overlay.get("manual_governed_review_action_label") or merged.get("manual_review_action_label")
            ),
            "manual_review_reviewer_label": _clean_text(
                overlay.get("manual_governed_review_reviewer_label") or merged.get("manual_review_reviewer_label")
            ),
            "manual_review_note": _clean_text(overlay.get("manual_governed_review_note")),
            "manual_review_note_summary": _clean_text(overlay.get("manual_governed_review_note_summary")),
            "manual_review_reopen_revise_summary": _clean_text(
                overlay.get("manual_governed_review_reopen_revise_summary")
            ),
            "effective_review_note": _clean_text(overlay.get("effective_governed_review_note")),
            "effective_review_note_summary": _clean_text(overlay.get("effective_governed_review_note_summary")),
            "carryover_effect_summary": _clean_text(overlay.get("effective_carryover_effect_summary")),
            "consistency_summary": _clean_text(overlay.get("governed_review_consistency_summary")),
            "review_record_count": int(overlay.get("governed_review_record_count", 0) or 0),
            "manual_review_record_count": int(overlay.get("manual_governed_review_record_count", 0) or 0),
            "review_records": records,
        }
    )
    return merged


def _related_target_key(scientific_truth: dict[str, Any]) -> str:
    belief_state_ref = scientific_truth.get("belief_state_ref") if isinstance(scientific_truth.get("belief_state_ref"), dict) else {}
    return _clean_text(belief_state_ref.get("target_key"))


def _claim_subject_context(
    *,
    scientific_truth: dict[str, Any],
    claim: dict[str, Any],
) -> dict[str, Any]:
    evidence_activation_policy = (
        scientific_truth.get("evidence_activation_policy")
        if isinstance(scientific_truth.get("evidence_activation_policy"), dict)
        else {}
    )
    return {
        "workspace_id": _clean_text(scientific_truth.get("workspace_id")),
        "session_id": _clean_text(scientific_truth.get("session_id")),
        "subject_type": SUBJECT_TYPE_CLAIM,
        "subject_id": _clean_text(claim.get("claim_id")),
        "subject_label": _clean_text(
            claim.get("claim_statement")
            or claim.get("candidate_id")
            or claim.get("candidate_label")
            or claim.get("claim_id")
        ),
        "target_key": _related_target_key(scientific_truth),
        "candidate_id": _clean_text(claim.get("candidate_id")),
        "candidate_label": _clean_text(claim.get("candidate_id") or claim.get("candidate_label")),
        "layer_label": LAYER_LABELS[SUBJECT_TYPE_CLAIM],
        "source_class_label": _clean_text(
            claim.get("claim_source_class_label") or evidence_activation_policy.get("source_class_label")
        ),
        "source_class_summary": _clean_text(claim.get("claim_source_class_summary")),
        "provenance_confidence_label": _clean_text(claim.get("claim_provenance_confidence_label")),
        "provenance_confidence_summary": _clean_text(claim.get("claim_provenance_confidence_summary")),
        "trust_tier_label": _clean_text(claim.get("claim_trust_tier_label")),
        "trust_tier_summary": _clean_text(claim.get("claim_trust_tier_summary")),
        "promotion_gate_status_label": _clean_text(claim.get("claim_promotion_gate_status_label")),
        "promotion_gate_status_summary": _clean_text(claim.get("claim_promotion_gate_status_summary")),
        "promotion_block_reason_label": _clean_text(claim.get("claim_promotion_block_reason_label")),
        "promotion_block_reason_summary": _clean_text(claim.get("claim_promotion_block_reason_summary")),
        "effective_review_status_label": _clean_text(claim.get("claim_governed_review_status_label")),
        "effective_review_status_summary": _clean_text(claim.get("claim_governed_review_status_summary")),
        "effective_review_reason_label": _clean_text(claim.get("claim_governed_review_reason_label")),
        "effective_review_reason_summary": _clean_text(claim.get("claim_governed_review_reason_summary")),
        "effective_review_origin_label": _clean_text(claim.get("claim_effective_governed_review_origin_label"), default=REVIEW_ORIGIN_DERIVED),
        "effective_review_origin_summary": _clean_text(claim.get("claim_effective_governed_review_origin_summary")),
        "derived_review_status_label": _clean_text(claim.get("claim_derived_governed_review_status_label")),
        "derived_review_status_summary": _clean_text(claim.get("claim_derived_governed_review_status_summary")),
        "derived_review_reason_label": _clean_text(claim.get("claim_derived_governed_review_reason_label")),
        "derived_review_reason_summary": _clean_text(claim.get("claim_derived_governed_review_reason_summary")),
        "manual_review_status_label": _clean_text(claim.get("claim_manual_governed_review_status_label")),
        "manual_review_status_summary": _clean_text(claim.get("claim_manual_governed_review_status_summary")),
        "manual_review_reason_label": _clean_text(claim.get("claim_manual_governed_review_reason_label")),
        "manual_review_reason_summary": _clean_text(claim.get("claim_manual_governed_review_reason_summary")),
        "manual_review_action_label": _clean_text(claim.get("claim_manual_governed_review_action_label")),
        "manual_review_reviewer_label": _clean_text(claim.get("claim_manual_governed_review_reviewer_label")),
        "local_usefulness_summary": _clean_text(
            claim.get("claim_actionability_summary")
            or claim.get("claim_support_quality_summary")
            or claim.get("claim_support_basis_mix_summary")
        ),
        "broader_carryover_summary": _clean_text(
            claim.get("claim_broader_reuse_summary")
            or claim.get("claim_governed_review_status_summary")
            or claim.get("claim_promotion_gate_status_summary")
        ),
        "future_influence_summary": _clean_text(
            claim.get("claim_future_reuse_candidacy_summary")
            or claim.get("claim_promotion_candidate_posture_summary")
            or claim.get("claim_next_step_summary")
        ),
        "contradiction_context_summary": _clean_text(
            claim.get("claim_support_coherence_summary")
            or claim.get("claim_governed_review_reason_summary")
        ),
        "carryover_guardrail_summary": _clean_text(
            claim.get("claim_promotion_audit_summary")
            or claim.get("claim_governed_review_history_summary")
            or claim.get("claim_governed_review_reason_summary")
        ),
    }


def _belief_state_subject_context(*, scientific_truth: dict[str, Any]) -> dict[str, Any]:
    summary = scientific_truth.get("belief_state_summary") if isinstance(scientific_truth.get("belief_state_summary"), dict) else {}
    evidence_activation_policy = (
        scientific_truth.get("evidence_activation_policy")
        if isinstance(scientific_truth.get("evidence_activation_policy"), dict)
        else {}
    )
    return {
        "workspace_id": _clean_text(scientific_truth.get("workspace_id")),
        "session_id": _clean_text(scientific_truth.get("session_id")),
        "subject_type": SUBJECT_TYPE_BELIEF_STATE,
        "subject_id": _clean_text(summary.get("governed_review_subject_id")),
        "subject_label": "Current belief-state posture",
        "target_key": _related_target_key(scientific_truth),
        "candidate_id": "",
        "candidate_label": "",
        "layer_label": LAYER_LABELS[SUBJECT_TYPE_BELIEF_STATE],
        "source_class_label": _clean_text(summary.get("source_class_label") or evidence_activation_policy.get("source_class_label")),
        "source_class_summary": _clean_text(summary.get("source_class_summary")),
        "provenance_confidence_label": _clean_text(summary.get("provenance_confidence_label")),
        "provenance_confidence_summary": _clean_text(summary.get("provenance_confidence_summary")),
        "trust_tier_label": _clean_text(summary.get("trust_tier_label")),
        "trust_tier_summary": _clean_text(summary.get("trust_tier_summary")),
        "promotion_gate_status_label": _clean_text(summary.get("promotion_gate_status_label")),
        "promotion_gate_status_summary": _clean_text(summary.get("promotion_gate_status_summary")),
        "promotion_block_reason_label": _clean_text(summary.get("promotion_block_reason_label")),
        "promotion_block_reason_summary": _clean_text(summary.get("promotion_block_reason_summary")),
        "effective_review_status_label": _clean_text(summary.get("governed_review_status_label")),
        "effective_review_status_summary": _clean_text(summary.get("governed_review_status_summary")),
        "effective_review_reason_label": _clean_text(summary.get("governed_review_reason_label")),
        "effective_review_reason_summary": _clean_text(summary.get("governed_review_reason_summary")),
        "effective_review_origin_label": _clean_text(summary.get("effective_governed_review_origin_label"), default=REVIEW_ORIGIN_DERIVED),
        "effective_review_origin_summary": _clean_text(summary.get("effective_governed_review_origin_summary")),
        "derived_review_status_label": _clean_text(summary.get("derived_governed_review_status_label")),
        "derived_review_status_summary": _clean_text(summary.get("derived_governed_review_status_summary")),
        "derived_review_reason_label": _clean_text(summary.get("derived_governed_review_reason_label")),
        "derived_review_reason_summary": _clean_text(summary.get("derived_governed_review_reason_summary")),
        "manual_review_status_label": _clean_text(summary.get("manual_governed_review_status_label")),
        "manual_review_status_summary": _clean_text(summary.get("manual_governed_review_status_summary")),
        "manual_review_reason_label": _clean_text(summary.get("manual_governed_review_reason_label")),
        "manual_review_reason_summary": _clean_text(summary.get("manual_governed_review_reason_summary")),
        "manual_review_action_label": _clean_text(summary.get("manual_governed_review_action_label")),
        "manual_review_reviewer_label": _clean_text(summary.get("manual_governed_review_reviewer_label")),
        "local_usefulness_summary": _clean_text(
            summary.get("belief_state_strength_summary") or summary.get("belief_state_readiness_summary")
        ),
        "broader_carryover_summary": _clean_text(
            summary.get("broader_target_reuse_summary") or summary.get("governed_review_status_summary")
        ),
        "future_influence_summary": _clean_text(
            summary.get("future_reuse_candidacy_summary") or summary.get("promotion_candidate_posture_summary")
        ),
        "contradiction_context_summary": _clean_text(
            summary.get("support_coherence_summary") or summary.get("governed_review_reason_summary")
        ),
        "carryover_guardrail_summary": _clean_text(summary.get("carryover_guardrail_summary")),
    }


def _continuity_cluster_subject_context(*, scientific_truth: dict[str, Any]) -> dict[str, Any]:
    summary = scientific_truth.get("belief_state_summary") if isinstance(scientific_truth.get("belief_state_summary"), dict) else {}
    evidence_activation_policy = (
        scientific_truth.get("evidence_activation_policy")
        if isinstance(scientific_truth.get("evidence_activation_policy"), dict)
        else {}
    )
    return {
        "workspace_id": _clean_text(scientific_truth.get("workspace_id")),
        "session_id": _clean_text(scientific_truth.get("session_id")),
        "subject_type": SUBJECT_TYPE_CONTINUITY_CLUSTER,
        "subject_id": _clean_text(summary.get("continuity_cluster_review_subject_id")),
        "subject_label": "Current continuity cluster",
        "target_key": _related_target_key(scientific_truth),
        "candidate_id": "",
        "candidate_label": "",
        "layer_label": LAYER_LABELS[SUBJECT_TYPE_CONTINUITY_CLUSTER],
        "source_class_label": _clean_text(summary.get("source_class_label") or evidence_activation_policy.get("source_class_label")),
        "source_class_summary": _clean_text(summary.get("source_class_summary")),
        "provenance_confidence_label": _clean_text(summary.get("provenance_confidence_label")),
        "provenance_confidence_summary": _clean_text(summary.get("provenance_confidence_summary")),
        "trust_tier_label": _clean_text(summary.get("trust_tier_label")),
        "trust_tier_summary": _clean_text(summary.get("trust_tier_summary")),
        "promotion_gate_status_label": _clean_text(summary.get("promotion_gate_status_label")),
        "promotion_gate_status_summary": _clean_text(summary.get("promotion_gate_status_summary")),
        "promotion_block_reason_label": _clean_text(summary.get("promotion_block_reason_label")),
        "promotion_block_reason_summary": _clean_text(summary.get("promotion_block_reason_summary")),
        "effective_review_status_label": _clean_text(summary.get("continuity_cluster_review_status_label")),
        "effective_review_status_summary": _clean_text(summary.get("continuity_cluster_review_status_summary")),
        "effective_review_reason_label": _clean_text(summary.get("continuity_cluster_review_reason_label")),
        "effective_review_reason_summary": _clean_text(summary.get("continuity_cluster_review_reason_summary")),
        "effective_review_origin_label": _clean_text(summary.get("continuity_cluster_effective_review_origin_label"), default=REVIEW_ORIGIN_DERIVED),
        "effective_review_origin_summary": _clean_text(summary.get("continuity_cluster_effective_review_origin_summary")),
        "derived_review_status_label": _clean_text(summary.get("continuity_cluster_derived_review_status_label")),
        "derived_review_status_summary": _clean_text(summary.get("continuity_cluster_derived_review_status_summary")),
        "derived_review_reason_label": _clean_text(summary.get("continuity_cluster_derived_review_reason_label")),
        "derived_review_reason_summary": _clean_text(summary.get("continuity_cluster_derived_review_reason_summary")),
        "manual_review_status_label": _clean_text(summary.get("continuity_cluster_manual_review_status_label")),
        "manual_review_status_summary": _clean_text(summary.get("continuity_cluster_manual_review_status_summary")),
        "manual_review_reason_label": _clean_text(summary.get("continuity_cluster_manual_review_reason_label")),
        "manual_review_reason_summary": _clean_text(summary.get("continuity_cluster_manual_review_reason_summary")),
        "manual_review_action_label": _clean_text(summary.get("continuity_cluster_manual_review_action_label")),
        "manual_review_reviewer_label": _clean_text(summary.get("continuity_cluster_manual_review_reviewer_label")),
        "local_usefulness_summary": _clean_text(summary.get("continuity_cluster_posture_summary")),
        "broader_carryover_summary": _clean_text(
            summary.get("continuity_cluster_review_status_summary") or summary.get("broader_target_continuity_summary")
        ),
        "future_influence_summary": _clean_text(
            summary.get("promotion_candidate_posture_summary") or summary.get("future_reuse_candidacy_summary")
        ),
        "contradiction_context_summary": _clean_text(
            summary.get("continuity_cluster_review_reason_summary") or summary.get("support_coherence_summary")
        ),
        "carryover_guardrail_summary": _clean_text(
            summary.get("continuity_cluster_promotion_audit_summary") or summary.get("continuity_cluster_review_history_summary")
        ),
    }


def _session_family_subject_context(*, scientific_truth: dict[str, Any]) -> dict[str, Any]:
    summary = (
        scientific_truth.get("scientific_decision_summary")
        if isinstance(scientific_truth.get("scientific_decision_summary"), dict)
        else {}
    )
    evidence_activation_policy = (
        scientific_truth.get("evidence_activation_policy")
        if isinstance(scientific_truth.get("evidence_activation_policy"), dict)
        else {}
    )
    return {
        "workspace_id": _clean_text(scientific_truth.get("workspace_id")),
        "session_id": _clean_text(scientific_truth.get("session_id")),
        "subject_type": SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER,
        "subject_id": _clean_text(summary.get("session_family_review_subject_id")),
        "subject_label": "Current session-family carryover",
        "target_key": _related_target_key(scientific_truth),
        "candidate_id": "",
        "candidate_label": "",
        "layer_label": LAYER_LABELS[SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER],
        "source_class_label": _clean_text(summary.get("source_class_label") or evidence_activation_policy.get("source_class_label")),
        "source_class_summary": _clean_text(summary.get("source_class_summary")),
        "provenance_confidence_label": _clean_text(summary.get("provenance_confidence_label")),
        "provenance_confidence_summary": _clean_text(summary.get("provenance_confidence_summary")),
        "trust_tier_label": _clean_text(summary.get("trust_tier_label")),
        "trust_tier_summary": _clean_text(summary.get("trust_tier_summary")),
        "promotion_gate_status_label": _clean_text(summary.get("promotion_gate_status_label")),
        "promotion_gate_status_summary": _clean_text(summary.get("promotion_gate_status_summary")),
        "promotion_block_reason_label": _clean_text(summary.get("promotion_block_reason_label")),
        "promotion_block_reason_summary": _clean_text(summary.get("promotion_block_reason_summary")),
        "effective_review_status_label": _clean_text(summary.get("session_family_review_status_label")),
        "effective_review_status_summary": _clean_text(summary.get("session_family_review_status_summary")),
        "effective_review_reason_label": _clean_text(summary.get("session_family_review_reason_label")),
        "effective_review_reason_summary": _clean_text(summary.get("session_family_review_reason_summary")),
        "effective_review_origin_label": _clean_text(summary.get("session_family_effective_review_origin_label"), default=REVIEW_ORIGIN_DERIVED),
        "effective_review_origin_summary": _clean_text(summary.get("session_family_effective_review_origin_summary")),
        "derived_review_status_label": _clean_text(summary.get("session_family_derived_review_status_label")),
        "derived_review_status_summary": _clean_text(summary.get("session_family_derived_review_status_summary")),
        "derived_review_reason_label": _clean_text(summary.get("session_family_derived_review_reason_label")),
        "derived_review_reason_summary": _clean_text(summary.get("session_family_derived_review_reason_summary")),
        "manual_review_status_label": _clean_text(summary.get("session_family_manual_review_status_label")),
        "manual_review_status_summary": _clean_text(summary.get("session_family_manual_review_status_summary")),
        "manual_review_reason_label": _clean_text(summary.get("session_family_manual_review_reason_label")),
        "manual_review_reason_summary": _clean_text(summary.get("session_family_manual_review_reason_summary")),
        "manual_review_action_label": _clean_text(summary.get("session_family_manual_review_action_label")),
        "manual_review_reviewer_label": _clean_text(summary.get("session_family_manual_review_reviewer_label")),
        "local_usefulness_summary": _clean_text(
            summary.get("decision_status_summary") or summary.get("current_support_quality_summary")
        ),
        "broader_carryover_summary": _clean_text(
            summary.get("session_family_review_status_summary") or summary.get("broader_governed_reuse_summary")
        ),
        "future_influence_summary": _clean_text(
            summary.get("future_reuse_candidacy_summary") or summary.get("promotion_candidate_posture_summary")
        ),
        "contradiction_context_summary": _clean_text(
            summary.get("session_family_review_reason_summary")
            or summary.get("current_support_coherence_summary")
            or summary.get("continuity_cluster_posture_summary")
        ),
        "carryover_guardrail_summary": _clean_text(summary.get("carryover_guardrail_summary")),
    }


def resolve_governance_subject_context(
    *,
    scientific_truth: dict[str, Any],
    subject_type: str,
    subject_id: str,
) -> dict[str, Any]:
    truth = scientific_truth if isinstance(scientific_truth, dict) else {}
    if subject_type == SUBJECT_TYPE_CLAIM:
        for claim in truth.get("claim_refs") or []:
            if not isinstance(claim, dict):
                continue
            if _clean_text(claim.get("claim_id")) == _clean_text(subject_id):
                return _canonicalize_context_with_overlay(_claim_subject_context(scientific_truth=truth, claim=claim))
        raise FileNotFoundError(f"Claim governance subject '{subject_id}' is not present in current scientific truth.")
    if subject_type == SUBJECT_TYPE_BELIEF_STATE:
        context = _belief_state_subject_context(scientific_truth=truth)
        if _clean_text(context.get("subject_id")) != _clean_text(subject_id):
            raise FileNotFoundError(f"Belief-state governance subject '{subject_id}' is not present in current scientific truth.")
        return _canonicalize_context_with_overlay(context)
    if subject_type == SUBJECT_TYPE_CONTINUITY_CLUSTER:
        context = _continuity_cluster_subject_context(scientific_truth=truth)
        if _clean_text(context.get("subject_id")) != _clean_text(subject_id):
            raise FileNotFoundError(f"Continuity-cluster governance subject '{subject_id}' is not present in current scientific truth.")
        return _canonicalize_context_with_overlay(context)
    if subject_type == SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER:
        context = _session_family_subject_context(scientific_truth=truth)
        if _clean_text(context.get("subject_id")) != _clean_text(subject_id):
            raise FileNotFoundError(f"Session-family governance subject '{subject_id}' is not present in current scientific truth.")
        return _canonicalize_context_with_overlay(context)
    raise FileNotFoundError(f"Unsupported governance subject type '{subject_type}'.")


def _subject_needs_inbox_attention(context: dict[str, Any]) -> bool:
    effective_status = _clean_text(context.get("effective_review_status_label")).lower()
    derived_status = _clean_text(context.get("derived_review_status_label")).lower()
    manual_status = _clean_text(context.get("manual_review_status_label")).lower()
    manual_origin = _clean_text(context.get("effective_review_origin_label")) == REVIEW_ORIGIN_MANUAL
    provenance_label = _clean_text(context.get("provenance_confidence_label")).lower().replace("_", " ")
    weak_provenance = provenance_label in {"weak provenance", "unknown provenance"}
    promotion_gate = _clean_text(context.get("promotion_gate_status_label")).lower()
    contradiction_context = _clean_text(context.get("contradiction_context_summary")).lower()
    local_summary = _clean_text(context.get("local_usefulness_summary")).lower()
    derived_manual_mismatch = bool(derived_status and manual_status and derived_status != manual_status)
    broader_gate_active = bool(promotion_gate) and not ("not" in promotion_gate and "candidate" in promotion_gate)
    if manual_origin or derived_manual_mismatch:
        return True
    if effective_status in {
        REVIEW_STATUS_BLOCKED,
        REVIEW_STATUS_DEFERRED,
        REVIEW_STATUS_DOWNGRADED,
        REVIEW_STATUS_QUARANTINED,
        REVIEW_STATUS_CANDIDATE,
    }:
        return True
    if broader_gate_active:
        return True
    if weak_provenance and ("useful" in local_summary or "action" in local_summary):
        return True
    if "contradiction" in contradiction_context or "degraded" in contradiction_context or "historical" in contradiction_context:
        return True
    return False


def _reason_tags(context: dict[str, Any], records: list[dict[str, Any]]) -> list[str]:
    tags: list[str] = []
    effective_status = _clean_text(context.get("effective_review_status_label")).lower()
    derived_status = _clean_text(context.get("derived_review_status_label")).lower()
    manual_status = _clean_text(context.get("manual_review_status_label")).lower()
    effective_origin = _clean_text(context.get("effective_review_origin_label"), default=REVIEW_ORIGIN_DERIVED)
    provenance = _clean_text(context.get("provenance_confidence_label")).lower().replace("_", " ")
    contradiction = _clean_text(context.get("contradiction_context_summary")).lower()
    local_usefulness = _clean_text(context.get("local_usefulness_summary")).lower()
    broader = _clean_text(context.get("broader_carryover_summary")).lower()
    future = _clean_text(context.get("future_influence_summary")).lower()

    if effective_origin == REVIEW_ORIGIN_MANUAL:
        tags.append("manual_governance")
    if derived_status and manual_status and derived_status != manual_status:
        tags.append("manual_vs_derived_mismatch")
    if effective_status in {REVIEW_STATUS_BLOCKED, REVIEW_STATUS_DEFERRED, REVIEW_STATUS_DOWNGRADED, REVIEW_STATUS_QUARANTINED}:
        tags.append("broader_carryover_restricted")
    if provenance in {"weak provenance", "unknown provenance"}:
        tags.append("weak_provenance")
    if "contradiction" in contradiction:
        tags.append("contradiction_pressure")
    if "degraded" in contradiction:
        tags.append("degraded_state")
    if "historical" in contradiction or "historical" in broader or "historical" in future:
        tags.append("historical_weight")
    if ("useful" in local_usefulness or "action" in local_usefulness) and effective_status in {
        REVIEW_STATUS_BLOCKED,
        REVIEW_STATUS_DEFERRED,
        REVIEW_STATUS_DOWNGRADED,
        REVIEW_STATUS_QUARANTINED,
    }:
        tags.append("strong_local_but_bounded")
    if _has_superseded_history(records):
        tags.append("superseded_history")
    if effective_origin != REVIEW_ORIGIN_MANUAL and _status_rank(derived_status) >= _status_rank(REVIEW_STATUS_CANDIDATE):
        tags.append("derived_review_only")
    return tags


def _attention_summary(context: dict[str, Any], reason_tags: list[str]) -> str:
    layer_label = _clean_text(context.get("layer_label"), default="Governance layer")
    effective_status = _clean_text(context.get("effective_review_status_label"), default=REVIEW_STATUS_NOT_REVIEWED)
    manual_status = _clean_text(context.get("manual_review_status_label"))
    derived_status = _clean_text(context.get("derived_review_status_label"))
    effective_origin = _clean_text(context.get("effective_review_origin_label"), default=REVIEW_ORIGIN_DERIVED)
    mismatch = "manual_vs_derived_mismatch" in reason_tags
    if mismatch:
        return (
            f"{layer_label} needs attention because derived posture suggests {derived_status or 'not recorded'}, "
            f"but the current manual posture is {manual_status or effective_status}."
        )
    if effective_origin == REVIEW_ORIGIN_MANUAL:
        reviewer = _clean_text(context.get("manual_review_reviewer_label"), default="a reviewer")
        return (
            f"{layer_label} remains on the governance worklist because {reviewer} manually set the current effective posture to "
            f"{manual_status or effective_status} and cross-layer carryover should stay inspectable."
        )
    if effective_status in {REVIEW_STATUS_BLOCKED, REVIEW_STATUS_QUARANTINED}:
        return f"{layer_label} is limiting broader carryover right now and should stay visible for reviewer inspection."
    if effective_status == REVIEW_STATUS_DOWNGRADED:
        return f"{layer_label} was downgraded from a stronger posture and should be re-checked before broader carryover expands again."
    if effective_status == REVIEW_STATUS_DEFERRED:
        return f"{layer_label} remains deferred and may need explicit reviewer judgment before broader carryover changes."
    if effective_status == REVIEW_STATUS_CANDIDATE:
        return f"{layer_label} looks reviewable for broader carryover, but it is still derived-only and not yet manually bounded."
    return f"{layer_label} stays on the governance worklist because broader carryover remains materially affected at this layer."


def _priority_score(context: dict[str, Any], reason_tags: list[str], records: list[dict[str, Any]]) -> int:
    score = LAYER_PRIORITY_BASE.get(_clean_text(context.get("subject_type")), 35)
    effective_status = _clean_text(context.get("effective_review_status_label")).lower()
    if effective_status == REVIEW_STATUS_QUARANTINED:
        score += 42
    elif effective_status == REVIEW_STATUS_DOWNGRADED:
        score += 34
    elif effective_status == REVIEW_STATUS_BLOCKED:
        score += 30
    elif effective_status == REVIEW_STATUS_DEFERRED:
        score += 22
    elif effective_status == REVIEW_STATUS_CANDIDATE:
        score += 16
    elif effective_status == REVIEW_STATUS_APPROVED:
        score += 8
    if "manual_vs_derived_mismatch" in reason_tags:
        score += 26
    if "manual_governance" in reason_tags:
        score += 12
    if "contradiction_pressure" in reason_tags:
        score += 16
    if "degraded_state" in reason_tags:
        score += 14
    if "weak_provenance" in reason_tags:
        score += 12
    if "historical_weight" in reason_tags:
        score += 10
    if "strong_local_but_bounded" in reason_tags:
        score += 12
    if "superseded_history" in reason_tags:
        score += 8
    if "derived_review_only" in reason_tags:
        score += 10
    if len(records) > 2:
        score += 4
    return score


def _detail_url(session_id: str, subject_type: str, subject_id: str) -> str:
    return f"/governance?session_id={session_id}&item_id={subject_type}:{subject_id}"


def _build_inbox_item(
    *,
    session_item: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any] | None:
    subject_id = _clean_text(context.get("subject_id"))
    subject_type = _clean_text(context.get("subject_type"))
    workspace_id = _clean_text(context.get("workspace_id"))
    session_id = _clean_text(context.get("session_id"))
    if not (workspace_id and session_id and subject_type and subject_id):
        return None
    records = context.get("review_records") if isinstance(context.get("review_records"), list) else list_subject_governed_reviews(
        workspace_id=workspace_id,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    if not _subject_needs_inbox_attention(context):
        return None
    review_record_count = len(records)
    manual_review_record_count = sum(
        1
        for record in records
        if _clean_text(record.get("review_origin_label"), default=REVIEW_ORIGIN_DERIVED) == REVIEW_ORIGIN_MANUAL
    )
    reason_tags = _reason_tags(context, records)
    priority_score = _priority_score(context, reason_tags, records)
    manual_action_label = _clean_text(context.get("manual_review_action_label"))
    manual_review_reviewer_label = _clean_text(context.get("manual_review_reviewer_label"))
    effective_origin_label = _clean_text(context.get("effective_review_origin_label"), default=REVIEW_ORIGIN_DERIVED)
    effective_origin_summary = _clean_text(context.get("effective_review_origin_summary"))
    if not effective_origin_summary:
        effective_origin_summary = _origin_summary(
            effective_origin_label,
            manual_review_reviewer_label,
            manual_action_label,
        )
    payload = {
        "item_id": f"{subject_type}:{subject_id}",
        "workspace_id": workspace_id,
        "session_id": session_id,
        "session_label": _clean_text(session_item.get("source_name") or session_item.get("session_label") or session_id),
        "source_name": _clean_text(session_item.get("source_name")),
        "subject_type": subject_type,
        "subject_id": subject_id,
        "layer_label": _clean_text(context.get("layer_label"), default=LAYER_LABELS.get(subject_type, "Governance layer")),
        "target_key": _clean_text(context.get("target_key")),
        "candidate_id": _clean_text(context.get("candidate_id")),
        "candidate_label": _clean_text(context.get("candidate_label") or context.get("subject_label")),
        "priority_rank": priority_score,
        "priority_label": _priority_label(priority_score),
        "attention_label": "Needs review",
        "attention_summary": _attention_summary(context, reason_tags),
        "effective_review_status_label": _clean_text(context.get("effective_review_status_label"), default=REVIEW_STATUS_NOT_REVIEWED),
        "effective_review_status_summary": _clean_text(
            context.get("effective_review_status_summary") or context.get("effective_review_reason_summary")
        ),
        "effective_review_origin_label": effective_origin_label,
        "effective_review_origin_summary": effective_origin_summary,
        "derived_review_status_label": _clean_text(context.get("derived_review_status_label")),
        "manual_review_status_label": _clean_text(context.get("manual_review_status_label")),
        "manual_review_action_label": manual_action_label,
        "manual_review_reviewer_label": manual_review_reviewer_label,
        "manual_review_note": _clean_text(context.get("manual_review_note")),
        "manual_review_note_summary": _clean_text(context.get("manual_review_note_summary")),
        "manual_review_reopen_revise_summary": _clean_text(context.get("manual_review_reopen_revise_summary")),
        "reviewer_attribution_summary": _reviewer_attribution_summary(
            effective_origin_label=effective_origin_label,
            manual_review_reviewer_label=manual_review_reviewer_label,
            manual_action_label=manual_action_label,
            review_record_count=review_record_count,
            manual_review_record_count=manual_review_record_count,
            has_superseded_history=_has_superseded_history(records),
        ),
        "trust_tier_label": _clean_text(context.get("trust_tier_label")),
        "provenance_confidence_label": _clean_text(context.get("provenance_confidence_label")),
        "source_class_label": _clean_text(context.get("source_class_label")),
        "local_usefulness_summary": _clean_text(context.get("local_usefulness_summary")),
        "broader_carryover_summary": _clean_text(context.get("broader_carryover_summary")),
        "future_influence_summary": _clean_text(context.get("future_influence_summary")),
        "contradiction_context_summary": _clean_text(context.get("contradiction_context_summary")),
        "carryover_guardrail_summary": _clean_text(context.get("carryover_guardrail_summary")),
        "carryover_effect_summary": _clean_text(context.get("carryover_effect_summary")),
        "consistency_summary": _clean_text(context.get("consistency_summary")),
        "promotion_gate_status_label": _clean_text(context.get("promotion_gate_status_label")),
        "promotion_block_reason_label": _clean_text(context.get("promotion_block_reason_label")),
        "review_record_count": review_record_count,
        "manual_review_record_count": manual_review_record_count,
        "related_session_count": 0,
        "manual_mismatch_flag": "manual_vs_derived_mismatch" in reason_tags,
        "reason_tags": reason_tags,
        "detail_url": _detail_url(session_id, subject_type, subject_id),
        "discovery_url": f"/discovery?session_id={session_id}",
        "dashboard_url": f"/dashboard?session_id={session_id}",
    }
    return validate_governance_inbox_item(payload)


def collect_governance_inbox_items_for_session_item(
    session_item: dict[str, Any],
) -> list[dict[str, Any]]:
    scientific_truth = (
        session_item.get("scientific_session_truth")
        if isinstance(session_item.get("scientific_session_truth"), dict)
        else {}
    )
    if not scientific_truth:
        return []
    subjects: list[dict[str, Any]] = []
    belief_state = _belief_state_subject_context(scientific_truth=scientific_truth)
    continuity = _continuity_cluster_subject_context(scientific_truth=scientific_truth)
    session_family = _session_family_subject_context(scientific_truth=scientific_truth)
    for context in (session_family, continuity, belief_state):
        if _clean_text(context.get("subject_id")):
            subjects.append(context)
    for claim in scientific_truth.get("claim_refs") or []:
        if not isinstance(claim, dict):
            continue
        context = _claim_subject_context(scientific_truth=scientific_truth, claim=claim)
        if _clean_text(context.get("subject_id")):
            subjects.append(context)
    items: list[dict[str, Any]] = []
    for context in subjects:
        inbox_item = _build_inbox_item(session_item=session_item, context=context)
        if inbox_item is not None:
            items.append(inbox_item)
    return items


def _annotate_related_session_counts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts_by_target: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        target_key = _clean_text(item.get("target_key"))
        if not target_key:
            continue
        counts_by_target[target_key] = counts_by_target.get(target_key, 0) + 1
    annotated: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        target_key = _clean_text(row.get("target_key"))
        related_count = counts_by_target.get(target_key, 1) - 1 if target_key else 0
        row["related_session_count"] = max(0, related_count)
        annotated.append(validate_governance_inbox_item(row))
    return annotated


def build_governance_inbox(
    session_items: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_items: list[dict[str, Any]] = []
    for session_item in session_items:
        if not isinstance(session_item, dict):
            continue
        raw_items.extend(collect_governance_inbox_items_for_session_item(session_item))
    raw_items = _annotate_related_session_counts(raw_items)
    ordered = sorted(
        raw_items,
        key=lambda item: (
            -_safe_int(item.get("priority_rank")),
            -_status_rank(_clean_text(item.get("effective_review_status_label"))),
            _clean_text(item.get("session_label")),
            _clean_text(item.get("item_id")),
        ),
    )
    ranked_items: list[dict[str, Any]] = []
    for index, item in enumerate(ordered, start=1):
        row = dict(item)
        row["priority_rank"] = index
        ranked_items.append(validate_governance_inbox_item(row))
    immediate_attention_count = sum(1 for item in ranked_items if item.get("priority_label") == PRIORITY_IMMEDIATE)
    review_soon_count = sum(1 for item in ranked_items if item.get("priority_label") == PRIORITY_SOON)
    watch_list_count = sum(1 for item in ranked_items if item.get("priority_label") == PRIORITY_WATCH)
    manual_override_count = sum(
        1 for item in ranked_items if _clean_text(item.get("effective_review_origin_label")) == REVIEW_ORIGIN_MANUAL
    )
    manual_mismatch_count = sum(1 for item in ranked_items if _is_truthy(item.get("manual_mismatch_flag")))
    blocked_or_quarantined_count = sum(
        1
        for item in ranked_items
        if _clean_text(item.get("effective_review_status_label")) in {REVIEW_STATUS_BLOCKED, REVIEW_STATUS_QUARANTINED}
    )
    session_family_count = sum(
        1 for item in ranked_items if _clean_text(item.get("subject_type")) == SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER
    )
    summary = validate_governance_inbox_summary(
        {
            "generated_at": _utc_now(),
            "item_count": len(ranked_items),
            "immediate_attention_count": immediate_attention_count,
            "review_soon_count": review_soon_count,
            "watch_list_count": watch_list_count,
            "manual_override_count": manual_override_count,
            "manual_mismatch_count": manual_mismatch_count,
            "blocked_or_quarantined_count": blocked_or_quarantined_count,
            "session_family_count": session_family_count,
            "summary_text": (
                f"{len(ranked_items)} governance inbox item{'s' if len(ranked_items) != 1 else ''}; "
                f"{immediate_attention_count} immediate, {review_soon_count} review soon, {watch_list_count} watch list."
                if ranked_items
                else "No governance inbox items currently need reviewer attention."
            ),
        }
    )
    groups = {
        "immediate_attention": [item for item in ranked_items if item.get("priority_label") == PRIORITY_IMMEDIATE],
        "review_soon": [item for item in ranked_items if item.get("priority_label") == PRIORITY_SOON],
        "watch_list": [item for item in ranked_items if item.get("priority_label") == PRIORITY_WATCH],
    }
    return validate_governance_inbox(
        {
            "generated_at": summary.get("generated_at"),
            "summary": summary,
            "items": ranked_items,
            "groups": groups,
        }
    )


def build_session_governance_summary(
    session_item: dict[str, Any],
) -> dict[str, Any]:
    inbox = build_governance_inbox([session_item])
    top_item = (inbox.get("items") or [None])[0] if isinstance(inbox.get("items"), list) else None
    effective_label = _clean_text((top_item or {}).get("effective_review_status_label"))
    attention_summary = _clean_text((top_item or {}).get("attention_summary"))
    return {
        "item_count": _safe_int((inbox.get("summary") or {}).get("item_count")),
        "priority_label": _clean_text((top_item or {}).get("priority_label")),
        "effective_review_status_label": effective_label,
        "attention_summary": attention_summary or _clean_text((inbox.get("summary") or {}).get("summary_text")),
        "manual_override_count": _safe_int((inbox.get("summary") or {}).get("manual_override_count")),
        "manual_mismatch_count": _safe_int((inbox.get("summary") or {}).get("manual_mismatch_count")),
        "detail_url": _clean_text((top_item or {}).get("detail_url")),
        "items": list(inbox.get("items") or [])[:6],
        "summary_text": _clean_text((inbox.get("summary") or {}).get("summary_text")),
    }


def build_governance_workbench(
    *,
    session_history: dict[str, Any],
    selected_item_id: str = "",
    selected_session_id: str = "",
) -> dict[str, Any]:
    items = list(session_history.get("items") or []) if isinstance(session_history, dict) else []
    inbox = build_governance_inbox(items)
    selected_item = None
    ordered_items = list(inbox.get("items") or [])
    selected_item_id = _clean_text(selected_item_id)
    selected_session_id = _clean_text(selected_session_id)
    if selected_item_id:
        selected_item = next((item for item in ordered_items if _clean_text(item.get("item_id")) == selected_item_id), None)
    if selected_item is None and selected_session_id:
        selected_item = next((item for item in ordered_items if _clean_text(item.get("session_id")) == selected_session_id), None)
    if selected_item is None and ordered_items:
        selected_item = ordered_items[0]
    selected_session = None
    if selected_item is not None:
        selected_session = next(
            (item for item in items if _clean_text(item.get("session_id")) == _clean_text(selected_item.get("session_id"))),
            None,
        )
    elif selected_session_id:
        selected_session = next((item for item in items if _clean_text(item.get("session_id")) == selected_session_id), None)
    if selected_session is None and items:
        selected_session = items[0]
    related_items: list[dict[str, Any]] = []
    if selected_item is not None:
        target_key = _clean_text(selected_item.get("target_key"))
        session_id = _clean_text(selected_item.get("session_id"))
        for item in ordered_items:
            if _clean_text(item.get("item_id")) == _clean_text(selected_item.get("item_id")):
                continue
            if target_key and _clean_text(item.get("target_key")) == target_key:
                related_items.append(item)
                continue
            if _clean_text(item.get("session_id")) == session_id:
                related_items.append(item)
    recent_manual_items = [
        item for item in ordered_items if _clean_text(item.get("effective_review_origin_label")) == REVIEW_ORIGIN_MANUAL
    ][:5]
    return {
        "inbox": inbox,
        "selected_item": selected_item or {},
        "selected_session": selected_session or {},
        "related_items": related_items[:8],
        "recent_manual_items": recent_manual_items,
        "selection_summary": (
            _clean_text((selected_item or {}).get("attention_summary"))
            or _clean_text((inbox.get("summary") or {}).get("summary_text"))
        ),
    }


__all__ = [
    "build_governance_inbox",
    "build_governance_workbench",
    "build_session_governance_summary",
    "collect_governance_inbox_items_for_session_item",
    "resolve_governance_subject_context",
]
