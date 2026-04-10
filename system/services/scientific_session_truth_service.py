from __future__ import annotations

from typing import Any

from system.contracts import (
    ControlledReuseState,
    EvidenceActivationPolicy,
    EvidenceFutureUse,
    EvidenceScope,
    EvidenceSupportLevel,
    EvidenceTruthStatus,
    EvidenceType,
    EvidenceUse,
    ModelingMode,
    ReviewStatus,
    TargetKind,
    validate_evidence_activation_policy,
    validate_evidence_record,
    validate_scientific_session_truth,
)
from system.db.repositories import ArtifactRepository, BeliefUpdateRepository, ClaimRepository, SessionRepository
from system.services.artifact_service import uploaded_session_dir, write_json_log
from system.services.claim_service import claim_refs_from_records, claims_summary_from_records, list_session_claims
from system.services.governed_review_service import (
    SUBJECT_TYPE_BELIEF_STATE,
    SUBJECT_TYPE_CONTINUITY_CLUSTER,
    SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER,
    build_governed_review_overlay,
    compose_belief_state_review_posture,
    compose_continuity_cluster_review_posture,
    compose_session_family_review_posture,
    list_subject_governed_reviews,
    sync_subject_governed_review_snapshot,
)
from system.services.experiment_request_service import (
    experiment_request_refs_from_records,
    experiment_request_summary_from_records,
    list_session_experiment_requests,
)
from system.services.experiment_result_service import (
    experiment_result_refs_from_records,
    experiment_result_summary_from_records,
    list_session_experiment_results,
)
from system.services.belief_update_service import (
    belief_update_refs_from_records,
    belief_update_summary_from_records,
    list_session_belief_updates,
)
from system.services.belief_state_service import (
    build_target_key,
    describe_belief_state_alignment,
    belief_state_reference_from_record,
    belief_state_summary_from_record,
    get_belief_state_for_target,
)
from system.services.run_metadata_service import build_run_provenance
from system.services.scientific_decision_service import build_scientific_decision_summary
from system.services.session_identity_service import build_session_identity
from system.services.support_quality_service import (
    REVIEW_REASON_APPROVED,
    REVIEW_REASON_CONTRADICTION,
    REVIEW_REASON_DEGRADED,
    REVIEW_REASON_DOWNGRADED,
    REVIEW_REASON_HISTORICAL,
    REVIEW_REASON_LOCAL_DEFAULT,
    REVIEW_REASON_QUARANTINED,
    REVIEW_REASON_SELECTIVE,
    REVIEW_REASON_STRONGER_TRUST_NEEDED,
    REVIEW_REASON_UNCONTROLLED_SOURCE,
    REVIEW_REASON_WEAK_PROVENANCE,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_BLOCKED,
    REVIEW_STATUS_CANDIDATE,
    REVIEW_STATUS_DEFERRED,
    REVIEW_STATUS_DOWNGRADED,
    REVIEW_STATUS_NOT_REVIEWED,
    REVIEW_STATUS_QUARANTINED,
    TRUST_TIER_CANDIDATE,
    TRUST_TIER_GOVERNED,
    TRUST_TIER_LOCAL_ONLY,
    assess_broader_reuse_posture,
    assess_continuity_cluster_promotion,
    assess_governed_evidence_posture,
    assess_governed_promotion_boundary,
    assess_provenance_confidence,
    BROADER_CONTINUITY_COHERENT,
    BROADER_CONTINUITY_CONTESTED,
    BROADER_CONTINUITY_HISTORICAL,
    BROADER_CONTINUITY_NONE,
    BROADER_CONTINUITY_SELECTIVE,
    BROADER_REUSE_CONTRADICTION_LIMITED,
    BROADER_REUSE_HISTORICAL_ONLY,
    BROADER_REUSE_LOCAL_ONLY,
    BROADER_REUSE_SELECTIVE,
    BROADER_REUSE_STRONG,
    FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED,
    FUTURE_REUSE_CANDIDACY_HISTORICAL_ONLY,
    FUTURE_REUSE_CANDIDACY_LOCAL_ONLY,
    FUTURE_REUSE_CANDIDACY_SELECTIVE,
    FUTURE_REUSE_CANDIDACY_STRONG,
    CONTINUITY_CLUSTER_PROMOTION_CANDIDATE,
    CONTINUITY_CLUSTER_SELECTIVE,
    CONTINUITY_CLUSTER_CONTEXT_ONLY,
    CONTINUITY_CLUSTER_CONTRADICTION_LIMITED,
    CONTINUITY_CLUSTER_HISTORICAL,
    CONTINUITY_CLUSTER_LOCAL_ONLY,
    PROMOTION_CANDIDATE_STRONG,
    PROMOTION_CANDIDATE_SELECTIVE,
    PROMOTION_CANDIDATE_CONTRADICTION_LIMITED,
    PROMOTION_CANDIDATE_HISTORICAL_ONLY,
    PROMOTION_CANDIDATE_CONTEXT_ONLY,
    PROMOTION_STABILITY_STABLE,
    PROMOTION_STABILITY_SELECTIVE,
    PROMOTION_STABILITY_UNSTABLE,
    PROMOTION_STABILITY_HISTORICAL,
    PROMOTION_STABILITY_INSUFFICIENT,
    PROMOTION_GATE_NOT_CANDIDATE,
    PROMOTION_GATE_BLOCKED,
    PROMOTION_GATE_SELECTIVE,
    PROMOTION_GATE_PROMOTABLE,
    PROMOTION_GATE_DOWNGRADED,
    PROMOTION_GATE_QUARANTINED,
    PROMOTION_BLOCK_NONE,
    PROMOTION_BLOCK_LOCAL_ONLY,
    PROMOTION_BLOCK_CONTEXT_ONLY,
    PROMOTION_BLOCK_SELECTIVE_ONLY,
    PROMOTION_BLOCK_CONTRADICTION,
    PROMOTION_BLOCK_DEGRADED,
    PROMOTION_BLOCK_HISTORICAL,
    PROMOTION_BLOCK_STABILITY,
    PROMOTION_BLOCK_DOWNGRADED,
    PROMOTION_BLOCK_QUARANTINED,
    PROVENANCE_CONFIDENCE_MODERATE,
    PROVENANCE_CONFIDENCE_STRONG,
    PROVENANCE_CONFIDENCE_UNKNOWN,
    PROVENANCE_CONFIDENCE_WEAK,
    SOURCE_CLASS_AFFILIATED,
    SOURCE_CLASS_AI_DERIVED,
    SOURCE_CLASS_CURATED,
    SOURCE_CLASS_DERIVED_EXTRACTED,
    SOURCE_CLASS_INTERNAL_GOVERNED,
    SOURCE_CLASS_UNCONTROLLED_UPLOAD,
    SOURCE_CLASS_UNKNOWN,
    classify_evidence_source_class,
    rollup_provenance_confidence,
)


claim_repository = ClaimRepository()
belief_update_repository = BeliefUpdateRepository()


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _target_key_for_truth(
    *,
    target_definition: dict[str, Any] | None,
    belief_state_record: dict[str, Any] | None = None,
) -> str:
    belief_state_record = belief_state_record if isinstance(belief_state_record, dict) else {}
    target_key = _clean_text(belief_state_record.get("target_key"))
    if target_key:
        return target_key
    return build_target_key(target_definition if isinstance(target_definition, dict) else {})


def _belief_state_subject_id(
    *,
    target_key: str,
    belief_state_record: dict[str, Any] | None = None,
) -> str:
    belief_state_record = belief_state_record if isinstance(belief_state_record, dict) else {}
    return _clean_text(belief_state_record.get("belief_state_id")) or f"belief_state::{target_key}"


def _continuity_cluster_subject_id(*, session_id: str, target_key: str) -> str:
    return f"continuity_cluster::{session_id}::{target_key or 'target_not_recorded'}"


def _session_family_subject_id(*, session_id: str, target_key: str) -> str:
    return f"session_family::{session_id}::{target_key or 'target_not_recorded'}"


def _overlay_belief_state_review(
    summary: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(summary)
    merged.update(
        {
            "trust_tier_label": overlay.get("trust_tier_label") or merged.get("trust_tier_label"),
            "provenance_confidence_label": overlay.get("provenance_confidence_label") or merged.get("provenance_confidence_label"),
            "governed_review_status_label": overlay.get("governed_review_status_label") or merged.get("governed_review_status_label"),
            "governed_review_status_summary": overlay.get("governed_review_status_summary") or merged.get("governed_review_status_summary"),
            "governed_review_reason_label": overlay.get("governed_review_reason_label") or merged.get("governed_review_reason_label"),
            "governed_review_reason_summary": overlay.get("governed_review_reason_summary") or merged.get("governed_review_reason_summary"),
            "governed_review_record_count": overlay.get("governed_review_record_count", 0),
            "governed_review_history_summary": overlay.get("governed_review_history_summary", ""),
            "promotion_audit_summary": overlay.get("promotion_audit_summary", ""),
        }
    )
    return merged


def _overlay_continuity_cluster_review(
    summary: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(summary)
    merged.update(
        {
            "continuity_cluster_review_status_label": overlay.get("governed_review_status_label")
            or merged.get("continuity_cluster_review_status_label"),
            "continuity_cluster_review_status_summary": overlay.get("governed_review_status_summary")
            or merged.get("continuity_cluster_review_status_summary"),
            "continuity_cluster_review_reason_label": overlay.get("governed_review_reason_label")
            or merged.get("continuity_cluster_review_reason_label"),
            "continuity_cluster_review_reason_summary": overlay.get("governed_review_reason_summary")
            or merged.get("continuity_cluster_review_reason_summary"),
            "continuity_cluster_review_record_count": overlay.get("governed_review_record_count", 0),
            "continuity_cluster_review_history_summary": overlay.get("governed_review_history_summary", ""),
            "continuity_cluster_promotion_audit_summary": overlay.get("promotion_audit_summary", ""),
        }
    )
    return merged


def _support_level(count: int, *, strong_threshold: int = 12, moderate_threshold: int = 4) -> str:
    if count > 0:
        return EvidenceSupportLevel.limited.value
    return EvidenceSupportLevel.contextual.value


def _support_level_for_evidence(
    *,
    evidence_type: str,
    truth_status: str,
    count: int,
) -> str:
    evidence_type = _clean_text(evidence_type).lower()
    truth_status = _clean_text(truth_status).lower()
    count = max(0, int(count))
    if count <= 0:
        return EvidenceSupportLevel.contextual.value
    if evidence_type in {
        EvidenceType.experimental_value.value,
        EvidenceType.binary_label.value,
        EvidenceType.learning_queue.value,
    } and truth_status in {
        EvidenceTruthStatus.observed.value,
        EvidenceTruthStatus.reviewed.value,
    }:
        return EvidenceSupportLevel.limited.value
    return EvidenceSupportLevel.contextual.value


def _label_source(target_definition: dict[str, Any], run_contract: dict[str, Any], measurement_summary: dict[str, Any]) -> str:
    return _clean_text(
        run_contract.get("label_source")
        or measurement_summary.get("label_source")
        or target_definition.get("label_source")
    ).lower()


def _candidate_count(decision_payload: dict[str, Any]) -> int:
    summary = decision_payload.get("summary") if isinstance(decision_payload, dict) else {}
    if isinstance(summary, dict):
        count = _safe_int(summary.get("candidate_count"), default=-1)
        if count >= 0:
            return count
    rows = decision_payload.get("top_experiments") if isinstance(decision_payload, dict) else []
    return len(rows) if isinstance(rows, list) else 0


def _human_review_count(review_summary: dict[str, Any]) -> int:
    counts = review_summary.get("counts") if isinstance(review_summary.get("counts"), dict) else {}
    return sum(
        _safe_int(counts.get(status), 0)
        for status in (
            ReviewStatus.under_review.value,
            ReviewStatus.approved.value,
            ReviewStatus.rejected.value,
            ReviewStatus.tested.value,
            ReviewStatus.ingested.value,
        )
    )


def _join_names(names: list[str]) -> str:
    cleaned = [_clean_text(name) for name in names if _clean_text(name)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _join_sentence(names: list[str], default: str = "Not recorded") -> str:
    cleaned = [_clean_text(name) for name in names if _clean_text(name)]
    if not cleaned:
        return default
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _evidence_review_context(record: dict[str, Any]) -> dict[str, str]:
    source_class = classify_evidence_source_class(
        evidence_type=record.get("evidence_type"),
        source=record.get("source"),
        truth_status=record.get("truth_status"),
    )
    provenance = assess_provenance_confidence(
        source_class_label=source_class["source_class_label"],
        source=record.get("source"),
        truth_status=record.get("truth_status"),
    )
    trust_posture = assess_governed_evidence_posture(
        source_class_label=source_class["source_class_label"],
        provenance_confidence_label=provenance["provenance_confidence_label"],
        candidate_context=_clean_text(record.get("future_use")) in {
            EvidenceFutureUse.may_inform_future_learning.value,
            EvidenceFutureUse.may_inform_future_ranking.value,
        },
        local_only_default=True,
    )
    return {
        **source_class,
        **provenance,
        **trust_posture,
    }


def _augment_belief_state_summary_with_broader_scope(
    belief_state_summary: dict[str, Any] | None,
    claims_summary: dict[str, Any] | None,
    *,
    belief_state_record: dict[str, Any] | None = None,
    evidence_activation_policy: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    belief_state_summary = belief_state_summary if isinstance(belief_state_summary, dict) else {}
    claims_summary = claims_summary if isinstance(claims_summary, dict) else {}
    belief_state_record = belief_state_record if isinstance(belief_state_record, dict) else {}
    evidence_activation_policy = evidence_activation_policy if isinstance(evidence_activation_policy, dict) else {}
    if not belief_state_summary:
        return belief_state_summary or None

    broader_scope = assess_broader_reuse_posture(
        active_support_count=_safe_int(belief_state_summary.get("active_claim_count"), 0),
        continuity_evidence_count=_safe_int(claims_summary.get("continuity_aligned_claim_count"), 0),
        governing_continuity_count=_safe_int(claims_summary.get("claims_with_active_governed_continuity_count"), 0),
        tentative_continuity_count=_safe_int(claims_summary.get("claims_with_tentative_active_continuity_count"), 0),
        contested_continuity_count=_safe_int(claims_summary.get("claims_with_contradiction_limited_reuse_count"), 0),
        historical_continuity_count=_safe_int(claims_summary.get("claims_with_historical_continuity_only_count"), 0),
        current_support_reuse_label=_clean_text(belief_state_summary.get("support_reuse_label")),
        contested_flag=bool(belief_state_summary.get("current_support_contested_flag")),
        degraded_flag=bool(belief_state_summary.get("current_posture_degraded_flag")),
        historical_stronger_flag=bool(belief_state_summary.get("historical_support_stronger_than_current_flag")),
    )

    augmented = dict(belief_state_summary)
    broader_target_reuse_label = broader_scope["broader_reuse_label"]
    broader_target_continuity_label = broader_scope["broader_continuity_label"]
    future_reuse_candidacy_label = broader_scope["future_reuse_candidacy_label"]
    cluster_scope = assess_continuity_cluster_promotion(
        active_support_count=_safe_int(belief_state_summary.get("active_claim_count"), 0),
        continuity_evidence_count=_safe_int(claims_summary.get("continuity_aligned_claim_count"), 0),
        governing_continuity_count=_safe_int(claims_summary.get("claims_with_active_governed_continuity_count"), 0),
        tentative_continuity_count=_safe_int(claims_summary.get("claims_with_tentative_active_continuity_count"), 0),
        contested_continuity_count=_safe_int(claims_summary.get("claims_with_contradiction_limited_reuse_count"), 0),
        historical_continuity_count=_safe_int(claims_summary.get("claims_with_historical_continuity_only_count"), 0),
        broader_reuse_label=broader_target_reuse_label,
        broader_continuity_label=broader_target_continuity_label,
        future_reuse_candidacy_label=future_reuse_candidacy_label,
        contested_flag=bool(belief_state_summary.get("current_support_contested_flag")),
        degraded_flag=bool(belief_state_summary.get("current_posture_degraded_flag")),
        historical_stronger_flag=bool(belief_state_summary.get("historical_support_stronger_than_current_flag")),
    )
    continuity_cluster_posture_label = cluster_scope["continuity_cluster_posture_label"]
    promotion_candidate_posture_label = cluster_scope["promotion_candidate_posture_label"]
    promotion_boundary = assess_governed_promotion_boundary(
        active_support_count=_safe_int(belief_state_summary.get("active_claim_count"), 0),
        continuity_evidence_count=_safe_int(claims_summary.get("continuity_aligned_claim_count"), 0),
        governing_continuity_count=_safe_int(claims_summary.get("claims_with_active_governed_continuity_count"), 0),
        tentative_continuity_count=_safe_int(claims_summary.get("claims_with_tentative_active_continuity_count"), 0),
        contested_continuity_count=_safe_int(claims_summary.get("claims_with_contradiction_limited_reuse_count"), 0),
        historical_continuity_count=_safe_int(claims_summary.get("claims_with_historical_continuity_only_count"), 0),
        broader_reuse_label=broader_target_reuse_label,
        broader_continuity_label=broader_target_continuity_label,
        continuity_cluster_posture_label=continuity_cluster_posture_label,
        promotion_candidate_posture_label=promotion_candidate_posture_label,
        contested_flag=bool(belief_state_summary.get("current_support_contested_flag")),
        degraded_flag=bool(belief_state_summary.get("current_posture_degraded_flag")),
        historical_stronger_flag=bool(belief_state_summary.get("historical_support_stronger_than_current_flag")),
    )
    promotion_stability_label = promotion_boundary["promotion_stability_label"]
    promotion_gate_status_label = promotion_boundary["promotion_gate_status_label"]
    promotion_block_reason_label = promotion_boundary["promotion_block_reason_label"]
    belief_state_metadata = (
        belief_state_record.get("metadata")
        if isinstance(belief_state_record.get("metadata"), dict)
        else {}
    )
    trust_tier_label = _clean_text(
        belief_state_summary.get("trust_tier_label")
        or belief_state_metadata.get("trust_tier_label")
        or claims_summary.get("trust_tier_label")
        or evidence_activation_policy.get("trust_tier_label"),
        default=TRUST_TIER_LOCAL_ONLY,
    )
    trust_tier_summary = _clean_text(
        belief_state_summary.get("trust_tier_summary")
        or belief_state_metadata.get("trust_tier_summary")
        or claims_summary.get("trust_tier_summary_text")
        or evidence_activation_policy.get("trust_tier_summary"),
    )
    provenance_confidence_label = _clean_text(
        belief_state_summary.get("provenance_confidence_label")
        or belief_state_metadata.get("provenance_confidence_label")
        or claims_summary.get("provenance_confidence_label")
        or evidence_activation_policy.get("provenance_confidence_label"),
        default=PROVENANCE_CONFIDENCE_UNKNOWN,
    )
    provenance_confidence_summary = _clean_text(
        belief_state_summary.get("provenance_confidence_summary")
        or belief_state_metadata.get("provenance_confidence_summary")
        or claims_summary.get("provenance_confidence_summary_text")
        or evidence_activation_policy.get("provenance_confidence_summary"),
    )
    governed_review_status_label = _clean_text(
        belief_state_summary.get("governed_review_status_label")
        or belief_state_metadata.get("governed_review_status_label")
        or claims_summary.get("governed_review_status_label")
        or evidence_activation_policy.get("governed_review_status_label"),
        default=REVIEW_STATUS_NOT_REVIEWED,
    )
    governed_review_status_summary = _clean_text(
        belief_state_summary.get("governed_review_status_summary")
        or belief_state_metadata.get("governed_review_status_summary")
        or claims_summary.get("governed_review_status_summary_text")
        or evidence_activation_policy.get("governed_review_status_summary"),
    )
    governed_review_reason_label = _clean_text(
        belief_state_summary.get("governed_review_reason_label")
        or belief_state_metadata.get("governed_review_reason_label")
        or claims_summary.get("governed_review_reason_label")
        or evidence_activation_policy.get("governed_review_reason_label"),
        default=REVIEW_REASON_LOCAL_DEFAULT,
    )
    governed_review_reason_summary = _clean_text(
        belief_state_summary.get("governed_review_reason_summary")
        or belief_state_metadata.get("governed_review_reason_summary")
        or claims_summary.get("governed_review_reason_summary_text")
        or evidence_activation_policy.get("governed_review_reason_summary"),
    )

    active_governed_continuity = _safe_int(claims_summary.get("claims_with_active_governed_continuity_count"), 0)
    tentative_continuity = _safe_int(claims_summary.get("claims_with_tentative_active_continuity_count"), 0)
    contested_histories = _safe_int(claims_summary.get("claims_with_contradiction_limited_reuse_count"), 0)
    historical_continuity = _safe_int(claims_summary.get("claims_with_historical_continuity_only_count"), 0)

    if broader_target_reuse_label == BROADER_REUSE_STRONG:
        broader_target_reuse_summary = (
            f"Broader target-scoped reuse is strongest when the current target picture stays coherent and {active_governed_continuity} related claim context"
            f"{'' if active_governed_continuity == 1 else 's'} still carry posture-governing continuity."
        )
    elif broader_target_reuse_label == BROADER_REUSE_CONTRADICTION_LIMITED:
        broader_target_reuse_summary = (
            "Broader target-scoped reuse should stay contradiction-limited because degraded present posture or contradiction-heavy related claim history weakens cleaner carryover."
        )
    elif broader_target_reuse_label == BROADER_REUSE_HISTORICAL_ONLY:
        broader_target_reuse_summary = (
            "Broader target-scoped reuse is mainly historical-only right now: older support remains informative, but it should not quietly drive stronger present reuse."
        )
    elif broader_target_reuse_label == BROADER_REUSE_SELECTIVE:
        broader_target_reuse_summary = (
            "Broader target-scoped reuse is selective: some target continuity exists, but current posture is not clean enough for stronger governed carryover."
        )
    else:
        broader_target_reuse_summary = (
            "Current target-scoped support is still mainly local to the present session picture. Stronger broader reuse would need clearer governed continuity first."
        )

    if broader_target_continuity_label == BROADER_CONTINUITY_COHERENT:
        broader_target_continuity_summary = (
            "The broader target continuity cluster is coherent: related claims reinforce one another under current posture-governing support."
        )
    elif broader_target_continuity_label == BROADER_CONTINUITY_CONTESTED:
        broader_target_continuity_summary = (
            f"The broader target continuity cluster is contested: {contested_histories} related claim path"
            f"{'' if contested_histories == 1 else 's'} currently add contradiction-limited carryover or degraded present posture."
        )
    elif broader_target_continuity_label == BROADER_CONTINUITY_HISTORICAL:
        broader_target_continuity_summary = (
            "The broader target continuity cluster is historical-heavy: prior target support remains informative, but mainly as historical context rather than stronger current reuse."
        )
    elif broader_target_continuity_label == BROADER_CONTINUITY_SELECTIVE:
        broader_target_continuity_summary = (
            f"The broader target continuity cluster is selective: {active_governed_continuity} posture-governing continuity path"
            f"{'' if active_governed_continuity == 1 else 's'}, {tentative_continuity} tentative path"
            f"{'' if tentative_continuity == 1 else 's'}, and {historical_continuity} historical-only path"
            f"{'' if historical_continuity == 1 else 's'} remain in the same bounded target context."
        )
    else:
        broader_target_continuity_summary = (
            "No meaningful broader target continuity cluster is established yet, so the current target picture should stay local and reviewable."
        )

    if future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_STRONG:
        future_reuse_candidacy_summary = (
            "This target picture now looks like a stronger later candidate for broader governed reuse because current posture and broader continuity both stay coherent."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_SELECTIVE:
        future_reuse_candidacy_summary = (
            "This target picture is only a selective future reuse candidate. Stronger continuity or cleaner present posture would still be needed for broader governed reuse."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED:
        future_reuse_candidacy_summary = (
            "Future target-level reuse candidacy is contradiction-limited because mixed or degraded history still weakens honest broader carryover."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_HISTORICAL_ONLY:
        future_reuse_candidacy_summary = (
            "Future target-level reuse candidacy is mainly historical-only right now: the history is informative, but it is not a strong current candidate for broader governed reuse."
        )
    else:
        future_reuse_candidacy_summary = (
            "Future target-level reuse candidacy remains local-only because the current support picture is still more useful for local review than for broader governed carryover."
        )

    if continuity_cluster_posture_label == CONTINUITY_CLUSTER_PROMOTION_CANDIDATE:
        continuity_cluster_posture_summary = (
            "This target-scoped session-family continuity cluster is a promotion candidate: current posture is coherent enough that broader governed carryover may later be justified."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_SELECTIVE:
        continuity_cluster_posture_summary = (
            "This target-scoped session-family continuity cluster is selective: it matters beyond local context, but it is still too bounded for stronger promotion."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTRADICTION_LIMITED:
        continuity_cluster_posture_summary = (
            "This target-scoped session-family continuity cluster is contradiction-limited: mixed, degraded, or contested history keeps it visible for review but not cleanly promotable."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_HISTORICAL:
        continuity_cluster_posture_summary = (
            "This target-scoped session-family continuity cluster is historical-heavy: it remains informative as context, but mainly through older continuity rather than stronger present posture."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTEXT_ONLY:
        continuity_cluster_posture_summary = (
            "This target-scoped session-family continuity cluster remains context-only right now: related continuity is visible, but it should not yet travel as a broader promotion candidate."
        )
    else:
        continuity_cluster_posture_summary = (
            "Continuity remains local-only at target scope right now, so the present picture should stay within local review boundaries."
        )

    if promotion_candidate_posture_label == PROMOTION_CANDIDATE_STRONG:
        promotion_candidate_posture_summary = (
            "This target-scoped continuity now looks like a stronger broader governed promotion candidate later if the current coherence holds."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_SELECTIVE:
        promotion_candidate_posture_summary = (
            "This target-scoped continuity is only a selective broader promotion candidate. Stronger or cleaner continuity would still be needed."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_CONTRADICTION_LIMITED:
        promotion_candidate_posture_summary = (
            "This target-scoped continuity is not a clean promotion candidate because contradiction-heavy or degraded history still limits governed carryover."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_HISTORICAL_ONLY:
        promotion_candidate_posture_summary = (
            "This target-scoped continuity is mainly historical promotion context right now, not a strong current broader promotion candidate."
        )
    else:
        promotion_candidate_posture_summary = (
            "This target-scoped continuity remains context-only rather than a broader governed promotion candidate."
        )

    if promotion_stability_label == PROMOTION_STABILITY_STABLE:
        promotion_stability_summary = (
            "This target-scoped continuity is stable enough for governed promotion review: current support and related continuity remain coherent under bounded rules."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_SELECTIVE:
        promotion_stability_summary = (
            "This target-scoped continuity is only selectively stable for promotion: it may matter later, but cleaner or broader stability would still be needed."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_UNSTABLE:
        promotion_stability_summary = (
            "This target-scoped continuity is unstable under contradiction pressure, so stronger promotion should remain blocked or quarantined."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_HISTORICAL:
        promotion_stability_summary = (
            "This target-scoped continuity is historical-heavy rather than stably current, so it should remain visible as context rather than a clean promotion basis."
        )
    else:
        promotion_stability_summary = (
            "This target-scoped continuity does not yet satisfy enough governed stability for broader promotion review."
        )

    if promotion_gate_status_label == PROMOTION_GATE_PROMOTABLE:
        promotion_gate_status_summary = (
            "This target-scoped continuity is promotable under bounded governed rules if the current coherent posture continues to hold."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_SELECTIVE:
        promotion_gate_status_summary = (
            "This target-scoped continuity is only selectively promotable under bounded governed rules and should still be carried with caution."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_DOWNGRADED:
        promotion_gate_status_summary = (
            "This target-scoped continuity has been downgraded from a stronger promotion posture because newer evidence now weakens how broadly it should carry."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_QUARANTINED:
        promotion_gate_status_summary = (
            "This target-scoped continuity is quarantined from stronger promotion because contradiction-heavy and degraded history make it too unstable."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_BLOCKED:
        promotion_gate_status_summary = (
            "This target-scoped continuity is still only a candidate and remains blocked from broader promotion under the current bounded rules."
        )
    else:
        promotion_gate_status_summary = (
            "This target-scoped continuity is not yet a governed promotion candidate and should remain local or contextual."
        )

    if promotion_block_reason_label == PROMOTION_BLOCK_NONE:
        promotion_block_reason_summary = (
            "No material promotion block is currently recorded for this target-scoped continuity picture."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_LOCAL_ONLY:
        promotion_block_reason_summary = (
            "This target-scoped support picture is still mainly local-only, so there is not enough broader continuity to justify promotion review."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_CONTEXT_ONLY:
        promotion_block_reason_summary = (
            "This target-scoped continuity remains context-only: it is useful for review, but not promotable under current governed rules."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_SELECTIVE_ONLY:
        promotion_block_reason_summary = (
            "This target-scoped continuity is selective only. It may matter later, but it is still too bounded for fully promotable posture."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_CONTRADICTION:
        promotion_block_reason_summary = (
            "This target-scoped continuity is blocked by contradiction-heavy history, so broader promotion should remain cautious."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_DEGRADED:
        promotion_block_reason_summary = (
            "This target-scoped continuity is blocked by degraded present posture, so earlier stronger continuity should not stay silently promotable."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_HISTORICAL:
        promotion_block_reason_summary = (
            "This target-scoped continuity is mainly historical-heavy right now, so its value is contextual rather than broadly promotable."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_DOWNGRADED:
        promotion_block_reason_summary = (
            "This target-scoped continuity was downgraded by newer contradictory or weaker present evidence, so its broader role should be reduced."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_QUARANTINED:
        promotion_block_reason_summary = (
            "This target-scoped continuity is quarantined because instability across present support and contradiction pressure makes stronger promotion unsafe."
        )
    else:
        promotion_block_reason_summary = (
            "This target-scoped continuity does not yet satisfy enough governed stability conditions for broader promotion."
        )

    belief_state_review_posture = compose_belief_state_review_posture(
        source_class_label=_clean_text(
            belief_state_summary.get("source_class_label")
            or claims_summary.get("source_class_label")
            or evidence_activation_policy.get("source_class_label")
        ),
        provenance_confidence_label=provenance_confidence_label,
        support_quality_label=_clean_text(belief_state_summary.get("support_quality_label")),
        governed_support_posture_label=_clean_text(belief_state_summary.get("governed_support_posture_label")),
        broader_target_reuse_label=broader_target_reuse_label,
        future_reuse_candidacy_label=future_reuse_candidacy_label,
        promotion_gate_status_label=promotion_gate_status_label,
        promotion_block_reason_label=promotion_block_reason_label,
        active_claim_count=_safe_int(belief_state_summary.get("active_claim_count"), 0),
        posture_governing_support_count=_safe_int(belief_state_summary.get("posture_governing_support_count"), 0),
        active_but_limited_support_count=_safe_int(belief_state_summary.get("active_but_limited_support_count"), 0),
        context_limited_support_count=_safe_int(belief_state_summary.get("context_limited_support_count"), 0),
        weak_or_unresolved_support_count=_safe_int(belief_state_summary.get("weak_or_unresolved_support_count"), 0),
        contested_flag=bool(belief_state_summary.get("current_support_contested_flag")),
        degraded_flag=bool(belief_state_summary.get("current_posture_degraded_flag")),
        historical_stronger_flag=bool(belief_state_summary.get("historical_support_stronger_than_current_flag")),
    )
    continuity_cluster_review_posture = compose_continuity_cluster_review_posture(
        source_class_label=_clean_text(
            belief_state_summary.get("source_class_label")
            or claims_summary.get("source_class_label")
            or evidence_activation_policy.get("source_class_label")
        ),
        provenance_confidence_label=provenance_confidence_label,
        broader_reuse_label=broader_target_reuse_label,
        broader_continuity_label=broader_target_continuity_label,
        future_reuse_candidacy_label=future_reuse_candidacy_label,
        continuity_cluster_posture_label=continuity_cluster_posture_label,
        promotion_gate_status_label=promotion_gate_status_label,
        promotion_block_reason_label=promotion_block_reason_label,
        continuity_evidence_count=_safe_int(claims_summary.get("continuity_aligned_claim_count"), 0),
        governing_continuity_count=active_governed_continuity,
        tentative_continuity_count=tentative_continuity,
        contested_continuity_count=contested_histories,
        historical_continuity_count=historical_continuity,
        contested_flag=bool(belief_state_summary.get("current_support_contested_flag")),
        degraded_flag=bool(belief_state_summary.get("current_posture_degraded_flag")),
        historical_stronger_flag=bool(belief_state_summary.get("historical_support_stronger_than_current_flag")),
    )

    augmented.update(
        {
            "broader_target_reuse_label": broader_target_reuse_label,
            "broader_target_reuse_summary": broader_target_reuse_summary,
            "broader_target_continuity_label": broader_target_continuity_label,
            "broader_target_continuity_summary": broader_target_continuity_summary,
            "future_reuse_candidacy_label": future_reuse_candidacy_label,
            "future_reuse_candidacy_summary": future_reuse_candidacy_summary,
            "continuity_cluster_posture_label": continuity_cluster_posture_label,
            "continuity_cluster_posture_summary": continuity_cluster_posture_summary,
            "promotion_candidate_posture_label": promotion_candidate_posture_label,
            "promotion_candidate_posture_summary": promotion_candidate_posture_summary,
            "promotion_stability_label": promotion_stability_label,
            "promotion_stability_summary": promotion_stability_summary,
            "promotion_gate_status_label": promotion_gate_status_label,
            "promotion_gate_status_summary": promotion_gate_status_summary,
            "promotion_block_reason_label": promotion_block_reason_label,
            "promotion_block_reason_summary": promotion_block_reason_summary,
            "trust_tier_label": belief_state_review_posture["trust_tier_label"],
            "trust_tier_summary": belief_state_review_posture["trust_tier_summary"],
            "provenance_confidence_label": provenance_confidence_label,
            "provenance_confidence_summary": provenance_confidence_summary,
            "governed_review_status_label": belief_state_review_posture["governed_review_status_label"],
            "governed_review_status_summary": belief_state_review_posture["governed_review_status_summary"],
            "governed_review_reason_label": belief_state_review_posture["governed_review_reason_label"],
            "governed_review_reason_summary": belief_state_review_posture["governed_review_reason_summary"],
            "governed_review_record_count": 0,
            "governed_review_history_summary": "",
            "promotion_audit_summary": "",
            "continuity_cluster_review_status_label": continuity_cluster_review_posture["governed_review_status_label"],
            "continuity_cluster_review_status_summary": continuity_cluster_review_posture["governed_review_status_summary"],
            "continuity_cluster_review_reason_label": continuity_cluster_review_posture["governed_review_reason_label"],
            "continuity_cluster_review_reason_summary": continuity_cluster_review_posture["governed_review_reason_summary"],
            "continuity_cluster_review_record_count": 0,
            "continuity_cluster_review_history_summary": "",
            "continuity_cluster_promotion_audit_summary": "",
            "carryover_guardrail_summary": belief_state_review_posture["carryover_guardrail_summary"],
        }
    )
    return augmented


def build_evidence_records(
    *,
    target_definition: dict[str, Any],
    modeling_mode: str,
    run_contract: dict[str, Any],
    analysis_report: dict[str, Any],
    decision_payload: dict[str, Any],
    review_summary: dict[str, Any],
    workspace_memory: dict[str, Any] | None = None,
    feedback_store: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    target_kind = _clean_text(target_definition.get("target_kind"), default=TargetKind.classification.value).lower()
    target_name = _clean_text(target_definition.get("target_name"), default="the session target")
    measurement_summary = analysis_report.get("measurement_summary") if isinstance(analysis_report.get("measurement_summary"), dict) else {}
    rows_with_values = _safe_int(measurement_summary.get("rows_with_values"), 0)
    rows_with_labels = _safe_int(measurement_summary.get("rows_with_labels"), 0)
    label_source = _label_source(target_definition, run_contract, measurement_summary)
    feature_signature = _clean_text(run_contract.get("feature_signature"))
    reference_basis = run_contract.get("reference_basis") if isinstance(run_contract.get("reference_basis"), dict) else {}
    candidate_count = _candidate_count(decision_payload)

    if rows_with_values > 0:
        records.append(
            validate_evidence_record(
                {
                    "name": "Observed experimental values",
                    "evidence_type": EvidenceType.experimental_value.value,
                    "truth_status": EvidenceTruthStatus.observed.value,
                    "source": "uploaded_dataset",
                    "scope": EvidenceScope.session_input.value,
                    "support_level": _support_level_for_evidence(
                        evidence_type=EvidenceType.experimental_value.value,
                        truth_status=EvidenceTruthStatus.observed.value,
                        count=rows_with_values,
                    ),
                    "current_use": EvidenceUse.active_modeling.value,
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": (
                        f"{rows_with_values} uploaded rows include observed numeric values. "
                        f"These values are active modeling evidence for {target_name}, not model output."
                    ),
                }
            )
        )

    if rows_with_labels > 0 and target_kind == TargetKind.classification.value:
        derived = label_source == "derived"
        records.append(
            validate_evidence_record(
                {
                    "name": "Derived class labels" if derived else "Observed binary labels",
                    "evidence_type": EvidenceType.derived_label.value if derived else EvidenceType.binary_label.value,
                    "truth_status": EvidenceTruthStatus.derived.value if derived else EvidenceTruthStatus.observed.value,
                    "source": "label_builder" if derived else "uploaded_dataset",
                    "scope": EvidenceScope.session_input.value,
                    "support_level": _support_level_for_evidence(
                        evidence_type=EvidenceType.derived_label.value if derived else EvidenceType.binary_label.value,
                        truth_status=EvidenceTruthStatus.derived.value if derived else EvidenceTruthStatus.observed.value,
                        count=rows_with_labels,
                    ),
                    "current_use": EvidenceUse.active_modeling.value,
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": (
                        f"{rows_with_labels} rows carry {'derived' if derived else 'observed'} class evidence. "
                        f"{'Derived labels are a transformation of measured data, not raw observation.' if derived else 'These labels directly support the current classification path.'}"
                    ),
                }
            )
        )

    if feature_signature and feature_signature != "not_recorded":
        records.append(
            validate_evidence_record(
                {
                    "name": "Computed chemistry features",
                    "evidence_type": EvidenceType.chemistry_feature.value,
                    "truth_status": EvidenceTruthStatus.computed.value,
                    "source": feature_signature,
                    "scope": EvidenceScope.session_input.value,
                    "support_level": EvidenceSupportLevel.contextual.value,
                    "current_use": (
                        EvidenceUse.active_modeling.value
                        if modeling_mode != ModelingMode.ranking_only.value
                        else EvidenceUse.active_ranking.value
                    ),
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": "RDKit descriptors and Morgan fingerprints are computed inputs to the current model or ranking workflow.",
                }
            )
        )

    if reference_basis:
        novelty_reference = _clean_text(reference_basis.get("novelty_reference"), default="reference_dataset_similarity")
        applicability_reference = _clean_text(reference_basis.get("applicability_reference"), default="reference_dataset_similarity")
        records.append(
            validate_evidence_record(
                {
                    "name": "Retrieved reference chemistry context",
                    "evidence_type": EvidenceType.reference_context.value,
                    "truth_status": EvidenceTruthStatus.retrieved.value,
                    "source": f"novelty={novelty_reference}; applicability={applicability_reference}",
                    "scope": EvidenceScope.reference_corpus.value,
                    "support_level": EvidenceSupportLevel.contextual.value,
                    "current_use": EvidenceUse.active_ranking.value,
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": "Reference-dataset similarity currently drives novelty and applicability support; it is retrieved context, not observed experimental truth.",
                }
            )
        )

    if modeling_mode != ModelingMode.ranking_only.value and candidate_count > 0:
        prediction_name = "Predicted continuous values" if target_kind == TargetKind.regression.value else "Predicted class judgments"
        records.append(
            validate_evidence_record(
                {
                    "name": prediction_name,
                    "evidence_type": EvidenceType.model_prediction.value,
                    "truth_status": EvidenceTruthStatus.predicted.value,
                    "source": _clean_text(run_contract.get("selected_model_name"), default="session_model"),
                    "scope": EvidenceScope.session_output.value,
                    "support_level": EvidenceSupportLevel.contextual.value,
                    "current_use": EvidenceUse.active_ranking.value,
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": (
                        "Model predictions are used to rank candidates, but they remain predictions rather than observed truth."
                    ),
                }
            )
        )

    human_review_count = _human_review_count(review_summary)
    if human_review_count > 0:
        records.append(
            validate_evidence_record(
                {
                    "name": "Human review outcomes",
                    "evidence_type": EvidenceType.human_review.value,
                    "truth_status": EvidenceTruthStatus.reviewed.value,
                    "source": "review_events",
                    "scope": EvidenceScope.session_summary.value,
                    "support_level": _support_level_for_evidence(
                        evidence_type=EvidenceType.human_review.value,
                        truth_status=EvidenceTruthStatus.reviewed.value,
                        count=human_review_count,
                    ),
                    "current_use": EvidenceUse.interpretation_only.value,
                    "future_use": EvidenceFutureUse.may_inform_future_learning.value,
                    "active_in_live_pipeline": False,
                    "summary": (
                        f"{human_review_count} human review outcome{'s' if human_review_count != 1 else ''} are stored for interpretation and continuity. "
                        "They do not automatically retrain the live model today."
                    ),
                }
            )
        )

    workspace_memory = workspace_memory if isinstance(workspace_memory, dict) else {}
    matched_memory = _safe_int(workspace_memory.get("matched_candidate_count"), 0)
    if matched_memory > 0:
        records.append(
            validate_evidence_record(
                {
                    "name": "Workspace feedback memory",
                    "evidence_type": EvidenceType.workspace_memory.value,
                    "truth_status": EvidenceTruthStatus.retrieved.value,
                    "source": "workspace_review_history",
                    "scope": EvidenceScope.workspace_history.value,
                    "support_level": _support_level_for_evidence(
                        evidence_type=EvidenceType.workspace_memory.value,
                        truth_status=EvidenceTruthStatus.retrieved.value,
                        count=matched_memory,
                    ),
                    "current_use": EvidenceUse.memory_only.value,
                    "future_use": EvidenceFutureUse.may_inform_future_learning.value,
                    "active_in_live_pipeline": False,
                    "summary": (
                        f"{matched_memory} current shortlist candidate{'s' if matched_memory != 1 else ''} have prior workspace feedback. "
                        "This memory changes interpretation and continuity, not live model weights."
                    ),
                }
            )
        )

    feedback_store = feedback_store if isinstance(feedback_store, dict) else {}
    queued_rows = _safe_int(feedback_store.get("queued_rows"), 0)
    if bool(feedback_store.get("consent_learning")) and queued_rows > 0:
        records.append(
            validate_evidence_record(
                {
                    "name": "Queued learning evidence",
                    "evidence_type": EvidenceType.learning_queue.value,
                    "truth_status": EvidenceTruthStatus.observed.value if label_source != "derived" else EvidenceTruthStatus.derived.value,
                    "source": "explicit_learning_queue",
                    "scope": EvidenceScope.session_summary.value,
                    "support_level": _support_level_for_evidence(
                        evidence_type=EvidenceType.learning_queue.value,
                        truth_status=EvidenceTruthStatus.observed.value if label_source != "derived" else EvidenceTruthStatus.derived.value,
                        count=queued_rows,
                    ),
                    "current_use": EvidenceUse.stored_not_active.value,
                    "future_use": EvidenceFutureUse.may_inform_future_learning.value,
                    "active_in_live_pipeline": False,
                    "summary": (
                        f"{queued_rows} consented labeled row{'s' if queued_rows != 1 else ''} were stored in the explicit learning queue. "
                        "They are not automatically consumed by the live decision pipeline yet."
                    ),
                }
            )
        )

    enriched_records: list[dict[str, Any]] = []
    for item in records:
        review_context = _evidence_review_context(item)
        enriched_records.append(validate_evidence_record({**item, **review_context}))
    return enriched_records


def build_evidence_loop_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    modeling = [item["name"] for item in records if item.get("current_use") == EvidenceUse.active_modeling.value]
    ranking = [item["name"] for item in records if item.get("current_use") == EvidenceUse.active_ranking.value]
    interpretation = [item["name"] for item in records if item.get("current_use") == EvidenceUse.interpretation_only.value]
    memory = [item["name"] for item in records if item.get("current_use") == EvidenceUse.memory_only.value]
    stored = [item["name"] for item in records if item.get("current_use") == EvidenceUse.stored_not_active.value]
    future_activation = [
        item["name"]
        for item in records
        if item.get("future_use") in {
            EvidenceFutureUse.may_inform_future_ranking.value,
            EvidenceFutureUse.may_inform_future_learning.value,
        }
    ]

    active_parts: list[str] = []
    if modeling:
        active_parts.append("modeling evidence from " + ", ".join(modeling))
    if ranking:
        active_parts.append("ranking context from " + ", ".join(ranking))
    if not active_parts:
        active_parts.append("policy-level ordering with limited explicit evidence inputs")

    summary = "Current recommendations use " + " and ".join(active_parts) + "."
    if interpretation or memory or stored:
        post_run_bits: list[str] = []
        if interpretation:
            post_run_bits.append("review evidence changes interpretation")
        if memory:
            post_run_bits.append("workspace carryover remains memory-only")
        if stored:
            post_run_bits.append("queued learning evidence is stored but not live")
        summary = f"{summary} " + "; ".join(post_run_bits).capitalize() + "."

    learning_boundary_note = (
        "Observed upload values and labels can drive the active model path. Review outcomes, workspace feedback, and queued learning rows are stored explicitly, but they do not automatically retrain or rerank the live pipeline yet."
    )
    boundary_bits: list[str] = []
    if modeling:
        boundary_bits.append(f"Active modeling uses {_join_names(modeling)}")
    if ranking:
        boundary_bits.append(f"active ranking context uses {_join_names(ranking)}")
    if interpretation:
        boundary_bits.append(f"{_join_names(interpretation)} remain interpretation-only")
    if memory:
        boundary_bits.append(f"{_join_names(memory)} remain memory-only")
    if stored:
        boundary_bits.append(f"{_join_names(stored)} are stored but not active")
    activation_boundary_summary = ". ".join(bit[:1].upper() + bit[1:] if bit else "" for bit in boundary_bits if bit)
    if activation_boundary_summary:
        activation_boundary_summary = activation_boundary_summary.rstrip(".") + "."
    if future_activation:
        future_note = f"Future activation candidates: {_join_names(future_activation)}."
        activation_boundary_summary = (
            f"{activation_boundary_summary} {future_note}".strip()
            if activation_boundary_summary
            else future_note
        )

    return {
        "summary": summary,
        "learning_boundary_note": learning_boundary_note,
        "activation_boundary_summary": activation_boundary_summary,
        "active_modeling_evidence": modeling,
        "active_ranking_evidence": ranking,
        "interpretation_only_evidence": interpretation,
        "memory_only_evidence": memory,
        "stored_not_active_evidence": stored,
        "future_activation_candidates": future_activation,
    }


def build_evidence_activation_policy(records: list[dict[str, Any]]) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    for item in records:
        evidence_type = _clean_text(item.get("evidence_type")).lower()
        current_use = _clean_text(item.get("current_use")).lower()
        future_use = _clean_text(item.get("future_use")).lower()
        name = _clean_text(item.get("name"), default="Evidence")
        support_level = _clean_text(item.get("support_level")).lower()
        truth_status = _clean_text(item.get("truth_status")).lower()

        model_training_allowed = current_use == EvidenceUse.active_modeling.value
        ranking_context_allowed = current_use == EvidenceUse.active_ranking.value
        interpretation_allowed = current_use in {
            EvidenceUse.interpretation_only.value,
            EvidenceUse.memory_only.value,
        } or evidence_type == EvidenceType.model_prediction.value
        comparison_allowed = evidence_type in {
            EvidenceType.experimental_value.value,
            EvidenceType.binary_label.value,
            EvidenceType.derived_label.value,
            EvidenceType.reference_context.value,
            EvidenceType.model_prediction.value,
            EvidenceType.human_review.value,
            EvidenceType.workspace_memory.value,
        }
        eligible_for_future_learning = future_use == EvidenceFutureUse.may_inform_future_learning.value
        memory_only = current_use == EvidenceUse.memory_only.value
        stored_only = current_use == EvidenceUse.stored_not_active.value
        currently_active = current_use in {
            EvidenceUse.active_modeling.value,
            EvidenceUse.active_ranking.value,
            EvidenceUse.interpretation_only.value,
            EvidenceUse.memory_only.value,
        }
        eligible_for_recommendation_reuse = False
        eligible_for_ranking_context = False
        requires_stronger_validation = False
        permanently_non_active = False
        ineligibility_reason = ""

        if evidence_type == EvidenceType.experimental_value.value:
            eligible_for_recommendation_reuse = True
            eligible_for_ranking_context = True
            eligible_for_future_learning = True
            requires_stronger_validation = support_level == EvidenceSupportLevel.limited.value
        elif evidence_type == EvidenceType.binary_label.value:
            eligible_for_recommendation_reuse = True
            eligible_for_ranking_context = True
            eligible_for_future_learning = True
            requires_stronger_validation = support_level == EvidenceSupportLevel.limited.value
        elif evidence_type == EvidenceType.derived_label.value:
            eligible_for_recommendation_reuse = True
            eligible_for_ranking_context = True
            eligible_for_future_learning = True
            requires_stronger_validation = True
            if truth_status == EvidenceTruthStatus.derived.value:
                ineligibility_reason = (
                    "Derived labels can support later activation only after stronger validation against observed outcomes."
                )
        elif evidence_type == EvidenceType.human_review.value:
            eligible_for_recommendation_reuse = True
            eligible_for_ranking_context = True
            eligible_for_future_learning = False
            requires_stronger_validation = True
            ineligibility_reason = (
                "Human review can support conservative reuse and continuity framing, but it is not automated model-learning evidence."
            )
        elif evidence_type == EvidenceType.learning_queue.value:
            eligible_for_future_learning = True
            requires_stronger_validation = truth_status == EvidenceTruthStatus.derived.value or support_level == EvidenceSupportLevel.limited.value
            if requires_stronger_validation:
                ineligibility_reason = (
                    "Queued learning evidence needs stronger validation before any future activation beyond storage."
                )
        elif evidence_type == EvidenceType.workspace_memory.value:
            eligible_for_future_learning = False
            permanently_non_active = True
            ineligibility_reason = (
                "Workspace memory is a continuity layer over prior review history, not standalone scientific learning evidence."
            )
        elif evidence_type == EvidenceType.model_prediction.value:
            eligible_for_future_learning = False
            permanently_non_active = True
            ineligibility_reason = "Predicted outputs are not observed truth and are not eligible as future learning evidence."
        elif evidence_type == EvidenceType.reference_context.value:
            eligible_for_future_learning = False
            permanently_non_active = True
            ineligibility_reason = (
                "Retrieved reference similarity is contextual support, not reusable empirical outcome evidence."
            )
        elif evidence_type == EvidenceType.chemistry_feature.value:
            eligible_for_future_learning = False
            permanently_non_active = True
            ineligibility_reason = (
                "Computed chemistry features are model inputs, not independent outcome evidence for future activation."
            )

        if not ineligibility_reason:
            if not eligible_for_future_learning and not model_training_allowed and not ranking_context_allowed and not interpretation_allowed:
                ineligibility_reason = "This evidence is recorded for traceability, not for stronger future activation."
            elif permanently_non_active:
                ineligibility_reason = "This evidence remains limited to its current contextual role."
        future_learning_eligible = eligible_for_future_learning

        activation_bits: list[str] = []
        if model_training_allowed:
            activation_bits.append("active in the current model path")
        if ranking_context_allowed:
            activation_bits.append("active in ranking context")
        if interpretation_allowed and not memory_only:
            activation_bits.append("active for recommendation interpretation")
        if comparison_allowed:
            activation_bits.append("available for comparison/read-across")
        if future_learning_eligible:
            activation_bits.append("eligible for future learning activation")
        if memory_only:
            activation_bits.append("memory-only")
        if stored_only:
            activation_bits.append("stored but not active")
        if not activation_bits:
            activation_bits.append("recorded without an active role")

        eligibility_bits: list[str] = []
        if eligible_for_recommendation_reuse:
            eligibility_bits.append("eligible for conservative recommendation reuse")
        if eligible_for_ranking_context:
            eligibility_bits.append("eligible for future ranking-context reuse")
        if eligible_for_future_learning:
            eligibility_bits.append("eligible for future learning consideration")
        if requires_stronger_validation:
            eligibility_bits.append("requires stronger validation before stronger activation")
        if permanently_non_active:
            eligibility_bits.append("not eligible for stronger future activation")
        if not eligibility_bits:
            eligibility_bits.append("not currently eligible for stronger future activation")

        rules.append(
            {
                "evidence_type": evidence_type,
                "name": name,
                "model_training_allowed": model_training_allowed,
                "ranking_context_allowed": ranking_context_allowed,
                "interpretation_allowed": interpretation_allowed,
                "comparison_allowed": comparison_allowed,
                "future_learning_eligible": future_learning_eligible,
                "eligible_for_recommendation_reuse": eligible_for_recommendation_reuse,
                "eligible_for_ranking_context": eligible_for_ranking_context,
                "eligible_for_future_learning": eligible_for_future_learning,
                "requires_stronger_validation": requires_stronger_validation,
                "memory_only": memory_only,
                "stored_only": stored_only,
                "permanently_non_active": permanently_non_active,
                "currently_active": currently_active,
                "ineligibility_reason": ineligibility_reason,
                "activation_summary": f"{name} is currently " + ", ".join(activation_bits) + ".",
                "eligibility_summary": f"{name} is " + ", ".join(eligibility_bits) + ".",
                "source_class_label": _clean_text(item.get("source_class_label")),
                "provenance_confidence_label": _clean_text(item.get("provenance_confidence_label")),
                "trust_tier_label": _clean_text(item.get("trust_tier_label")),
                "trust_tier_summary": _clean_text(item.get("trust_tier_summary")),
                "governed_review_status_label": _clean_text(item.get("governed_review_status_label")),
                "governed_review_status_summary": _clean_text(item.get("governed_review_status_summary")),
                "governed_review_reason_label": _clean_text(item.get("governed_review_reason_label")),
                "governed_review_reason_summary": _clean_text(item.get("governed_review_reason_summary")),
            }
        )

    ranking_names = [rule["name"] for rule in rules if rule["ranking_context_allowed"]]
    interpretation_names = [rule["name"] for rule in rules if rule["interpretation_allowed"]]
    learning_names = [rule["name"] for rule in rules if rule["future_learning_eligible"]]
    recommendation_reuse_names = [rule["name"] for rule in rules if rule["eligible_for_recommendation_reuse"]]
    future_ranking_names = [rule["name"] for rule in rules if rule["eligible_for_ranking_context"]]
    future_learning_names = [rule["name"] for rule in rules if rule["eligible_for_future_learning"]]
    permanently_non_active_names = [rule["name"] for rule in rules if rule["permanently_non_active"]]
    validation_required_names = [rule["name"] for rule in rules if rule["requires_stronger_validation"]]
    stored_names = [rule["name"] for rule in rules if rule["stored_only"]]
    source_class_labels = [_clean_text(rule.get("source_class_label")) for rule in rules]
    trust_labels = [_clean_text(rule.get("trust_tier_label")) for rule in rules]
    provenance_labels = [_clean_text(rule.get("provenance_confidence_label")) for rule in rules]
    review_status_labels = [_clean_text(rule.get("governed_review_status_label")) for rule in rules]
    review_reason_labels = [_clean_text(rule.get("governed_review_reason_label")) for rule in rules]
    trust_counts = {
        "local_only_count": sum(1 for label in trust_labels if label == TRUST_TIER_LOCAL_ONLY),
        "candidate_count": sum(1 for label in trust_labels if label == TRUST_TIER_CANDIDATE),
        "governed_count": sum(1 for label in trust_labels if label == TRUST_TIER_GOVERNED),
    }
    provenance_counts = rollup_provenance_confidence(provenance_labels)
    review_status_counts = {
        "approved_count": sum(1 for label in review_status_labels if label == REVIEW_STATUS_APPROVED),
        "blocked_count": sum(1 for label in review_status_labels if label == REVIEW_STATUS_BLOCKED),
        "deferred_count": sum(1 for label in review_status_labels if label == REVIEW_STATUS_DEFERRED),
        "candidate_count": sum(1 for label in review_status_labels if label == REVIEW_STATUS_CANDIDATE),
        "not_reviewed_count": sum(1 for label in review_status_labels if label == REVIEW_STATUS_NOT_REVIEWED),
        "downgraded_count": sum(1 for label in review_status_labels if label == REVIEW_STATUS_DOWNGRADED),
        "quarantined_count": sum(1 for label in review_status_labels if label == REVIEW_STATUS_QUARANTINED),
    }
    local_default_names = [
        rule["name"]
        for rule in rules
        if _clean_text(rule.get("governed_review_reason_label")) == REVIEW_REASON_LOCAL_DEFAULT
    ]
    source_class_counts = {
        "curated_count": sum(1 for label in source_class_labels if label == SOURCE_CLASS_CURATED),
        "internal_governed_count": sum(1 for label in source_class_labels if label == SOURCE_CLASS_INTERNAL_GOVERNED),
        "affiliated_count": sum(1 for label in source_class_labels if label == SOURCE_CLASS_AFFILIATED),
        "derived_count": sum(1 for label in source_class_labels if label == SOURCE_CLASS_DERIVED_EXTRACTED),
        "uncontrolled_count": sum(1 for label in source_class_labels if label == SOURCE_CLASS_UNCONTROLLED_UPLOAD),
        "ai_count": sum(1 for label in source_class_labels if label == SOURCE_CLASS_AI_DERIVED),
        "unknown_count": sum(1 for label in source_class_labels if label == SOURCE_CLASS_UNKNOWN),
    }

    summary_parts: list[str] = []
    if ranking_names:
        summary_parts.append(f"Ranking context currently uses {_join_sentence(ranking_names)}")
    if interpretation_names:
        summary_parts.append(f"recommendation interpretation uses {_join_sentence(interpretation_names)}")
    if recommendation_reuse_names:
        summary_parts.append(f"conservative recommendation reuse is currently eligible for {_join_sentence(recommendation_reuse_names)}")
    if future_learning_names:
        summary_parts.append(f"future learning eligibility is limited to {_join_sentence(future_learning_names)}")
    if permanently_non_active_names:
        summary_parts.append(f"{_join_sentence(permanently_non_active_names)} remain non-active beyond their current contextual role")
    if stored_names:
        summary_parts.append(f"{_join_sentence(stored_names)} remain stored but inactive")
    summary = ". ".join(part[:1].upper() + part[1:] if part else "" for part in summary_parts if part)
    if summary:
        summary = summary.rstrip(".") + "."

    if trust_counts["governed_count"] > 0:
        trust_tier_label = TRUST_TIER_GOVERNED
        trust_tier_summary = (
            f"{trust_counts['governed_count']} evidence source{'s' if trust_counts['governed_count'] != 1 else ''} currently meet the strongest bounded governed-trust posture, while {trust_counts['candidate_count']} remain candidate-only and {trust_counts['local_only_count']} remain local-only."
        )
    elif trust_counts["candidate_count"] > 0:
        trust_tier_label = TRUST_TIER_CANDIDATE
        trust_tier_summary = (
            f"{trust_counts['candidate_count']} evidence source{'s' if trust_counts['candidate_count'] != 1 else ''} are broader review candidates, but {trust_counts['local_only_count']} still remain local-only by default."
        )
    else:
        trust_tier_label = TRUST_TIER_LOCAL_ONLY
        trust_tier_summary = (
            "Current evidence remains local-only by default. Local value is immediate, but broader trust has not been earned yet."
        )

    if source_class_counts["unknown_count"] > 0:
        source_class_label = SOURCE_CLASS_UNKNOWN
        source_class_summary = (
            "At least part of the current evidence basis still has unknown source class, so broader influence stays conservative and explicitly local-first."
        )
    elif source_class_counts["ai_count"] > 0:
        source_class_label = SOURCE_CLASS_AI_DERIVED
        source_class_summary = (
            "Some current evidence is AI-derived interpretation, which can assist local reasoning but should not silently behave like direct trusted observation."
        )
    elif source_class_counts["uncontrolled_count"] > 0:
        source_class_label = SOURCE_CLASS_UNCONTROLLED_UPLOAD
        source_class_summary = (
            "Some current evidence comes from uncontrolled upload paths, so local usefulness is preserved while broader influence remains constrained."
        )
    elif source_class_counts["derived_count"] > 0:
        source_class_label = SOURCE_CLASS_DERIVED_EXTRACTED
        source_class_summary = (
            "Current evidence includes derived or retrieved context, which remains useful but weaker than a fully governed direct observation path."
        )
    elif source_class_counts["affiliated_count"] > 0:
        source_class_label = SOURCE_CLASS_AFFILIATED
        source_class_summary = (
            "Current evidence is grounded mainly in affiliated or partner sources, which can support review candidacy but still require bounded trust checks."
        )
    elif source_class_counts["internal_governed_count"] > 0:
        source_class_label = SOURCE_CLASS_INTERNAL_GOVERNED
        source_class_summary = (
            "Current evidence is grounded mainly in internally governed experimental sources linked into the workflow."
        )
    elif source_class_counts["curated_count"] > 0:
        source_class_label = SOURCE_CLASS_CURATED
        source_class_summary = (
            "Current evidence includes curated or benchmark-like sources, which are the strongest bounded source class currently visible."
        )
    else:
        source_class_label = SOURCE_CLASS_UNKNOWN
        source_class_summary = "No explicit evidence source class was recorded."

    if provenance_counts["strong_count"] > 0 and provenance_counts["weak_count"] <= provenance_counts["strong_count"]:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_STRONG
        provenance_confidence_summary = (
            f"Provenance is strongest for {provenance_counts['strong_count']} evidence source{'s' if provenance_counts['strong_count'] != 1 else ''}, although some weaker or unknown lineage still remains in the session record."
        )
    elif provenance_counts["moderate_count"] > 0:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_MODERATE
        provenance_confidence_summary = (
            "Session evidence has moderate provenance overall: some source lineage is visible, but not all evidence is strong enough for broader trust."
        )
    elif provenance_counts["weak_count"] > 0:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_WEAK
        provenance_confidence_summary = (
            "Session evidence is still weakly grounded for broader trust because too much of it comes from uncontrolled, derived, or otherwise weak-provenance sources."
        )
    else:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_UNKNOWN
        provenance_confidence_summary = (
            "Provenance confidence remains unknown overall because source lineage is too incomplete for stronger broader trust."
        )

    if review_status_counts["approved_count"] > 0:
        governed_review_status_label = REVIEW_STATUS_APPROVED
        governed_review_status_summary = (
            f"{review_status_counts['approved_count']} evidence source{'s' if review_status_counts['approved_count'] != 1 else ''} are currently approved for bounded broader governed consideration."
        )
        governed_review_reason_label = REVIEW_REASON_APPROVED
        governed_review_reason_summary = (
            "Approved broader consideration depends on bounded trust, provenance, and continuity rather than on row count or repetition."
        )
    elif review_status_counts["blocked_count"] > 0:
        governed_review_status_label = REVIEW_STATUS_BLOCKED
        governed_review_status_summary = (
            f"{review_status_counts['blocked_count']} evidence source{'s' if review_status_counts['blocked_count'] != 1 else ''} are currently blocked from stronger broader influence."
        )
        if REVIEW_REASON_WEAK_PROVENANCE in review_reason_labels:
            governed_review_reason_label = REVIEW_REASON_WEAK_PROVENANCE
            governed_review_reason_summary = "Weak or unknown provenance currently limits broader governed influence more than local usefulness."
        else:
            governed_review_reason_label = REVIEW_REASON_STRONGER_TRUST_NEEDED
            governed_review_reason_summary = "Broader influence remains blocked because stronger trust and continuity conditions are still needed."
    elif review_status_counts["deferred_count"] > 0 or review_status_counts["candidate_count"] > 0:
        governed_review_status_label = REVIEW_STATUS_DEFERRED if review_status_counts["deferred_count"] > 0 else REVIEW_STATUS_CANDIDATE
        governed_review_status_summary = (
            "Some evidence is review-candidate material for broader consideration, but broader trust remains deferred or candidate-only rather than approved."
        )
        if REVIEW_REASON_UNCONTROLLED_SOURCE in review_reason_labels:
            governed_review_reason_label = REVIEW_REASON_UNCONTROLLED_SOURCE
            governed_review_reason_summary = "Uncontrolled or weak source classes keep broader trust deferred even when local evidence is useful."
        else:
            governed_review_reason_label = REVIEW_REASON_STRONGER_TRUST_NEEDED
            governed_review_reason_summary = "Stronger trust and provenance would still be needed before broader influence should increase."
    else:
        governed_review_status_label = REVIEW_STATUS_NOT_REVIEWED
        governed_review_status_summary = "No broader governed review posture is recorded yet, so the current evidence should remain local-first."
        governed_review_reason_label = REVIEW_REASON_LOCAL_DEFAULT
        governed_review_reason_summary = "Local-only by default remains the governing boundary until stronger review conditions are satisfied."

    local_only_default_summary = (
        "Uploaded evidence is local-only by default. Local use is immediate, but broader influence requires stronger trust, provenance, continuity, and governed review."
    )
    anti_poisoning_summary = (
        "Repeated uploads, review counts, or stored rows do not earn broader influence by volume. Broader influence depends on source class, provenance confidence, governed review posture, and contradiction survival."
    )

    return validate_evidence_activation_policy(
        {
            "summary": summary,
            "ranking_context_summary": (
                f"Active ranking context is currently limited to {_join_sentence(ranking_names)}."
                if ranking_names
                else "No explicit ranking-context evidence is recorded."
            ),
            "interpretation_summary": (
                f"Recommendation interpretation currently uses {_join_sentence(interpretation_names)}."
                if interpretation_names
                else "No explicit interpretation-only evidence is recorded."
            ),
            "recommendation_reuse_summary": (
                f"Conservative recommendation reuse is currently eligible for {_join_sentence(recommendation_reuse_names)}."
                if recommendation_reuse_names
                else "No evidence is currently marked as eligible for recommendation reuse."
            ),
            "future_ranking_context_summary": (
                f"Future ranking-context reuse is currently limited to {_join_sentence(future_ranking_names)}."
                if future_ranking_names
                else "No evidence is currently marked as eligible for future ranking-context reuse."
            ),
            "learning_eligibility_summary": (
                f"Only {_join_sentence(learning_names)} are currently eligible for future learning activation."
                if learning_names
                else "No evidence is currently marked as future-learning eligible."
            ),
            "future_learning_eligibility_summary": (
                f"Future learning consideration is currently limited to {_join_sentence(future_learning_names)}."
                if future_learning_names
                else "No evidence is currently marked as eligible for future learning consideration."
            ),
            "stored_only_summary": (
                f"{_join_sentence(stored_names)} are stored but not active in the live pipeline."
                if stored_names
                else "No stored-only evidence is recorded."
            ),
            "permanently_non_active_summary": (
                f"{_join_sentence(permanently_non_active_names)} are not eligible for stronger future activation."
                if permanently_non_active_names
                else "No evidence is currently marked as permanently non-active."
            ),
            "source_class_label": source_class_label,
            "source_class_summary": source_class_summary,
            "trust_tier_label": trust_tier_label,
            "trust_tier_summary": trust_tier_summary,
            "provenance_confidence_label": provenance_confidence_label,
            "provenance_confidence_summary": provenance_confidence_summary,
            "governed_review_status_label": governed_review_status_label,
            "governed_review_status_summary": governed_review_status_summary,
            "governed_review_reason_label": governed_review_reason_label,
            "governed_review_reason_summary": governed_review_reason_summary,
            "local_only_default_summary": local_only_default_summary,
            "anti_poisoning_summary": anti_poisoning_summary,
            "rules": rules,
        }
    )


def build_controlled_reuse_state(
    *,
    evidence_activation_policy: dict[str, Any] | None,
    workspace_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence_activation_policy = evidence_activation_policy if isinstance(evidence_activation_policy, dict) else {}
    workspace_memory = workspace_memory if isinstance(workspace_memory, dict) else {}
    rules = evidence_activation_policy.get("rules") if isinstance(evidence_activation_policy.get("rules"), list) else []
    human_review_rule = next(
        (
            item
            for item in rules
            if _clean_text(item.get("evidence_type")).lower() == EvidenceType.human_review.value
        ),
        {},
    )
    matched_candidate_count = _safe_int(workspace_memory.get("matched_candidate_count"), 0)
    status_counts = workspace_memory.get("status_counts") if isinstance(workspace_memory.get("status_counts"), dict) else {}
    reusable_count = sum(_safe_int(status_counts.get(key), 0) for key in ("approved", "tested", "ingested"))
    stronger_count = sum(_safe_int(status_counts.get(key), 0) for key in ("tested", "ingested"))

    recommendation_reuse_active = bool(human_review_rule.get("eligible_for_recommendation_reuse")) and reusable_count > 0
    ranking_context_reuse_active = bool(human_review_rule.get("eligible_for_ranking_context")) and (
        stronger_count > 0 or reusable_count >= 2
    )
    interpretation_support_active = matched_candidate_count > 0

    reused_evidence = ["Human review outcomes"] if recommendation_reuse_active or ranking_context_reuse_active else []
    support_carriers = ["Workspace feedback memory"] if interpretation_support_active else []

    if recommendation_reuse_active:
        recommendation_reuse_summary = (
            f"Recommendation reuse is active for {matched_candidate_count} shortlist candidate"
            f"{'' if matched_candidate_count == 1 else 's'} because prior human review outcomes met the current reuse rule. "
            "This supports continuity across sessions without retraining the model."
        )
    else:
        recommendation_reuse_summary = (
            "No prior human review outcome is currently active for recommendation reuse in this session."
        )

    if ranking_context_reuse_active:
        ranking_context_reuse_summary = (
            "Ranking-context reuse is active for shortlist framing because prior human review outcomes provide stronger reusable continuity context. "
            "This does not change model outputs or weights."
        )
    else:
        ranking_context_reuse_summary = "No prior evidence is currently active for ranking-context reuse in this session."

    if interpretation_support_active:
        interpretation_support_summary = (
            f"Workspace feedback memory remains active as interpretation support for {matched_candidate_count} matched shortlist candidate"
            f"{'' if matched_candidate_count == 1 else 's'}."
        )
    else:
        interpretation_support_summary = "No matched prior workspace feedback is active for interpretation support in this session."

    inactive_boundary_summary = (
        "Workspace memory remains a continuity carrier only. Reuse-support signals do not retrain the model, replace observed evidence, or silently overwrite scores."
    )

    return ControlledReuseState(
        recommendation_reuse_active=recommendation_reuse_active,
        ranking_context_reuse_active=ranking_context_reuse_active,
        interpretation_support_active=interpretation_support_active,
        reused_evidence=reused_evidence,
        support_carriers=support_carriers,
        recommendation_reuse_summary=recommendation_reuse_summary,
        ranking_context_reuse_summary=ranking_context_reuse_summary,
        interpretation_support_summary=interpretation_support_summary,
        inactive_boundary_summary=inactive_boundary_summary,
    ).dict()


def build_scientific_session_truth(
    *,
    session_id: str,
    workspace_id: str | None = None,
    source_name: str | None = None,
    session_record: dict[str, Any] | None = None,
    upload_metadata: dict[str, Any] | None = None,
    analysis_report: dict[str, Any] | None = None,
    decision_payload: dict[str, Any] | None = None,
    review_queue: dict[str, Any] | None = None,
    workspace_memory: dict[str, Any] | None = None,
    current_job: dict[str, Any] | None = None,
    feedback_store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_record = session_record or {}
    upload_metadata = upload_metadata or {}
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}
    review_queue = review_queue or {}
    summary_metadata = session_record.get("summary_metadata") if isinstance(session_record.get("summary_metadata"), dict) else {}

    target_definition = _first_dict(
        decision_payload.get("target_definition"),
        analysis_report.get("target_definition"),
        upload_metadata.get("target_definition"),
        summary_metadata.get("target_definition"),
    )
    run_contract = _first_dict(
        analysis_report.get("run_contract"),
        decision_payload.get("run_contract"),
        summary_metadata.get("run_contract"),
    )
    comparison_anchors = _first_dict(
        analysis_report.get("comparison_anchors"),
        decision_payload.get("comparison_anchors"),
        summary_metadata.get("comparison_anchors"),
    )
    modeling_mode = _clean_text(
        analysis_report.get("modeling_mode")
        or decision_payload.get("modeling_mode")
        or summary_metadata.get("modeling_mode")
        or run_contract.get("modeling_mode"),
        default=ModelingMode.ranking_only.value,
    ).lower()
    decision_intent = _clean_text(
        analysis_report.get("decision_intent")
        or decision_payload.get("decision_intent")
        or summary_metadata.get("decision_intent"),
    ).lower()
    session_identity = build_session_identity(
        session_record=session_record,
        upload_metadata=upload_metadata,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        current_job=current_job,
    )
    run_provenance = build_run_provenance(
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
    )
    review_summary = review_queue.get("summary") if isinstance(review_queue.get("summary"), dict) else {}
    ranking_policy = analysis_report.get("ranking_policy") if isinstance(analysis_report.get("ranking_policy"), dict) else {}
    measurement_summary = analysis_report.get("measurement_summary") if isinstance(analysis_report.get("measurement_summary"), dict) else {}
    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report.get("ranking_diagnostics"), dict) else {}
    records = build_evidence_records(
        target_definition=target_definition,
        modeling_mode=modeling_mode,
        run_contract=run_contract,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        review_summary=review_summary,
        workspace_memory=workspace_memory,
        feedback_store=feedback_store,
    )
    evidence_loop = build_evidence_loop_summary(records)
    evidence_activation_policy = build_evidence_activation_policy(records)
    controlled_reuse = build_controlled_reuse_state(
        evidence_activation_policy=evidence_activation_policy,
        workspace_memory=workspace_memory,
    )
    effective_workspace_id = _clean_text(workspace_id or session_record.get("workspace_id"))
    claims = list_session_claims(session_id, workspace_id=effective_workspace_id) if effective_workspace_id else []
    prior_claims = (
        [
            claim
            for claim in claim_repository.list_claims(workspace_id=effective_workspace_id)
            if _clean_text(claim.get("session_id")) != session_id
        ]
        if effective_workspace_id
        else []
    )
    prior_belief_updates = (
        [
            update
            for update in belief_update_repository.list_belief_updates(workspace_id=effective_workspace_id)
            if _clean_text(update.get("session_id")) != session_id
        ]
        if effective_workspace_id
        else []
    )
    experiment_requests = (
        list_session_experiment_requests(session_id, workspace_id=effective_workspace_id)
        if effective_workspace_id
        else []
    )
    experiment_results = (
        list_session_experiment_results(session_id, workspace_id=effective_workspace_id)
        if effective_workspace_id
        else []
    )
    belief_updates = (
        list_session_belief_updates(session_id, workspace_id=effective_workspace_id)
        if effective_workspace_id
        else []
    )
    belief_state = (
        get_belief_state_for_target(
            workspace_id=effective_workspace_id,
            target_definition_snapshot=target_definition,
        )
        if effective_workspace_id and isinstance(target_definition, dict) and target_definition
        else None
    )
    belief_state_alignment = describe_belief_state_alignment(
        belief_state=belief_state,
        session_belief_updates=belief_updates,
    )
    bridge_state_notes = []
    if _clean_text(run_provenance.get("bridge_state_summary")):
        bridge_state_notes.append(_clean_text(run_provenance.get("bridge_state_summary")))
    for warning in analysis_report.get("warnings", []) if isinstance(analysis_report.get("warnings"), list) else []:
        text = _clean_text(warning)
        if text and text not in bridge_state_notes:
            bridge_state_notes.append(text)

    decision_summary = decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}
    claim_refs = claim_refs_from_records(
        claims,
        belief_updates=belief_updates,
        prior_claims=prior_claims,
        prior_belief_updates=prior_belief_updates,
    )
    claim_refs_by_id = {
        _clean_text(item.get("claim_id")): item
        for item in claim_refs
        if isinstance(item, dict) and _clean_text(item.get("claim_id"))
    }
    claims_summary = claims_summary_from_records(
        claims,
        belief_updates=belief_updates,
        prior_claims=prior_claims,
        prior_belief_updates=prior_belief_updates,
    )
    experiment_request_refs = experiment_request_refs_from_records(
        experiment_requests,
        claim_refs_by_id=claim_refs_by_id,
    )
    experiment_request_summary = experiment_request_summary_from_records(
        experiment_requests,
        claim_refs_by_id=claim_refs_by_id,
    )
    experiment_result_refs = experiment_result_refs_from_records(experiment_results)
    linked_result_summary = experiment_result_summary_from_records(experiment_results)
    belief_update_summary = belief_update_summary_from_records(belief_updates)
    belief_state_summary = belief_state_summary_from_record(belief_state) if isinstance(belief_state, dict) else None
    belief_state_summary = _augment_belief_state_summary_with_broader_scope(
        belief_state_summary,
        claims_summary,
        belief_state_record=belief_state,
        evidence_activation_policy=evidence_activation_policy,
    )
    target_key = _target_key_for_truth(
        target_definition=target_definition,
        belief_state_record=belief_state,
    )
    if effective_workspace_id and isinstance(belief_state_summary, dict) and target_key:
        belief_state_subject_id = _belief_state_subject_id(
            target_key=target_key,
            belief_state_record=belief_state,
        )
        sync_subject_governed_review_snapshot(
            {
                "workspace_id": effective_workspace_id,
                "session_id": session_id,
                "subject_type": SUBJECT_TYPE_BELIEF_STATE,
                "subject_id": belief_state_subject_id,
                "target_key": target_key,
                "source_class_label": _clean_text(
                    belief_state_summary.get("source_class_label")
                    or claims_summary.get("source_class_label")
                    or evidence_activation_policy.get("source_class_label")
                ),
                "provenance_confidence_label": _clean_text(
                    belief_state_summary.get("provenance_confidence_label"),
                    default=PROVENANCE_CONFIDENCE_UNKNOWN,
                ),
                "trust_tier_label": _clean_text(
                    belief_state_summary.get("trust_tier_label"),
                    default=TRUST_TIER_LOCAL_ONLY,
                ),
                "review_status_label": _clean_text(
                    belief_state_summary.get("governed_review_status_label"),
                    default=REVIEW_STATUS_NOT_REVIEWED,
                ),
                "review_reason_label": _clean_text(
                    belief_state_summary.get("governed_review_reason_label"),
                    default=REVIEW_REASON_LOCAL_DEFAULT,
                ),
                "review_reason_summary": _clean_text(belief_state_summary.get("governed_review_reason_summary")),
                "promotion_gate_status_label": _clean_text(belief_state_summary.get("promotion_gate_status_label")),
                "promotion_block_reason_label": _clean_text(belief_state_summary.get("promotion_block_reason_label")),
                "decision_summary": _clean_text(
                    belief_state_summary.get("governed_review_status_summary")
                    or belief_state_summary.get("governed_review_reason_summary")
                ),
                "recorded_by": "scientific_session_truth",
                "metadata": {
                    "layer": SUBJECT_TYPE_BELIEF_STATE,
                    "support_quality_label": _clean_text(belief_state_summary.get("support_quality_label")),
                    "governed_support_posture_label": _clean_text(belief_state_summary.get("governed_support_posture_label")),
                    "broader_target_reuse_label": _clean_text(belief_state_summary.get("broader_target_reuse_label")),
                    "broader_target_continuity_label": _clean_text(belief_state_summary.get("broader_target_continuity_label")),
                    "future_reuse_candidacy_label": _clean_text(belief_state_summary.get("future_reuse_candidacy_label")),
                    "carryover_guardrail_summary": _clean_text(belief_state_summary.get("carryover_guardrail_summary")),
                },
            }
        )
        belief_state_overlay = build_governed_review_overlay(
            list_subject_governed_reviews(
                workspace_id=effective_workspace_id,
                subject_type=SUBJECT_TYPE_BELIEF_STATE,
                subject_id=belief_state_subject_id,
            ),
            fallback_fields={
                "source_class_label": _clean_text(
                    belief_state_summary.get("source_class_label")
                    or claims_summary.get("source_class_label")
                    or evidence_activation_policy.get("source_class_label")
                ),
                "trust_tier_label": _clean_text(belief_state_summary.get("trust_tier_label")),
                "provenance_confidence_label": _clean_text(belief_state_summary.get("provenance_confidence_label")),
                "governed_review_status_label": _clean_text(belief_state_summary.get("governed_review_status_label")),
                "governed_review_reason_label": _clean_text(belief_state_summary.get("governed_review_reason_label")),
                "governed_review_reason_summary": _clean_text(belief_state_summary.get("governed_review_reason_summary")),
                "promotion_gate_status_label": _clean_text(belief_state_summary.get("promotion_gate_status_label")),
                "promotion_block_reason_label": _clean_text(belief_state_summary.get("promotion_block_reason_label")),
            },
            subject_label="This belief-state posture",
        )
        belief_state_summary = _overlay_belief_state_review(belief_state_summary, belief_state_overlay)

        continuity_cluster_posture = compose_continuity_cluster_review_posture(
            source_class_label=_clean_text(
                claims_summary.get("source_class_label")
                or evidence_activation_policy.get("source_class_label")
            ),
            provenance_confidence_label=_clean_text(
                belief_state_summary.get("provenance_confidence_label"),
                default=PROVENANCE_CONFIDENCE_UNKNOWN,
            ),
            broader_reuse_label=_clean_text(belief_state_summary.get("broader_target_reuse_label")),
            broader_continuity_label=_clean_text(belief_state_summary.get("broader_target_continuity_label")),
            future_reuse_candidacy_label=_clean_text(belief_state_summary.get("future_reuse_candidacy_label")),
            continuity_cluster_posture_label=_clean_text(belief_state_summary.get("continuity_cluster_posture_label")),
            promotion_gate_status_label=_clean_text(belief_state_summary.get("promotion_gate_status_label")),
            promotion_block_reason_label=_clean_text(belief_state_summary.get("promotion_block_reason_label")),
            continuity_evidence_count=_safe_int(claims_summary.get("continuity_aligned_claim_count"), 0),
            governing_continuity_count=_safe_int(claims_summary.get("claims_with_active_governed_continuity_count"), 0),
            tentative_continuity_count=_safe_int(claims_summary.get("claims_with_tentative_active_continuity_count"), 0),
            contested_continuity_count=_safe_int(claims_summary.get("claims_with_contradiction_limited_reuse_count"), 0),
            historical_continuity_count=_safe_int(claims_summary.get("claims_with_historical_continuity_only_count"), 0),
            contested_flag=bool(belief_state_summary.get("current_support_contested_flag")),
            degraded_flag=bool(belief_state_summary.get("current_posture_degraded_flag")),
            historical_stronger_flag=bool(belief_state_summary.get("historical_support_stronger_than_current_flag")),
        )
        continuity_subject_id = _continuity_cluster_subject_id(session_id=session_id, target_key=target_key)
        sync_subject_governed_review_snapshot(
            {
                "workspace_id": effective_workspace_id,
                "session_id": session_id,
                "subject_type": SUBJECT_TYPE_CONTINUITY_CLUSTER,
                "subject_id": continuity_subject_id,
                "target_key": target_key,
                "source_class_label": _clean_text(
                    claims_summary.get("source_class_label")
                    or evidence_activation_policy.get("source_class_label")
                ),
                "provenance_confidence_label": _clean_text(
                    belief_state_summary.get("provenance_confidence_label"),
                    default=PROVENANCE_CONFIDENCE_UNKNOWN,
                ),
                "trust_tier_label": _clean_text(continuity_cluster_posture.get("trust_tier_label"), default=TRUST_TIER_LOCAL_ONLY),
                "review_status_label": _clean_text(
                    continuity_cluster_posture.get("governed_review_status_label"),
                    default=REVIEW_STATUS_NOT_REVIEWED,
                ),
                "review_reason_label": _clean_text(
                    continuity_cluster_posture.get("governed_review_reason_label"),
                    default=REVIEW_REASON_LOCAL_DEFAULT,
                ),
                "review_reason_summary": _clean_text(continuity_cluster_posture.get("governed_review_reason_summary")),
                "promotion_gate_status_label": _clean_text(belief_state_summary.get("promotion_gate_status_label")),
                "promotion_block_reason_label": _clean_text(belief_state_summary.get("promotion_block_reason_label")),
                "decision_summary": _clean_text(continuity_cluster_posture.get("decision_summary")),
                "recorded_by": "scientific_session_truth",
                "metadata": {
                    "layer": SUBJECT_TYPE_CONTINUITY_CLUSTER,
                    "continuity_cluster_posture_label": _clean_text(belief_state_summary.get("continuity_cluster_posture_label")),
                    "promotion_candidate_posture_label": _clean_text(belief_state_summary.get("promotion_candidate_posture_label")),
                    "broader_target_continuity_label": _clean_text(belief_state_summary.get("broader_target_continuity_label")),
                    "carryover_guardrail_summary": _clean_text(continuity_cluster_posture.get("carryover_guardrail_summary")),
                },
            }
        )
        continuity_overlay = build_governed_review_overlay(
            list_subject_governed_reviews(
                workspace_id=effective_workspace_id,
                subject_type=SUBJECT_TYPE_CONTINUITY_CLUSTER,
                subject_id=continuity_subject_id,
            ),
            fallback_fields={
                "source_class_label": _clean_text(
                    claims_summary.get("source_class_label")
                    or evidence_activation_policy.get("source_class_label")
                ),
                "trust_tier_label": _clean_text(continuity_cluster_posture.get("trust_tier_label")),
                "provenance_confidence_label": _clean_text(belief_state_summary.get("provenance_confidence_label")),
                "governed_review_status_label": _clean_text(continuity_cluster_posture.get("governed_review_status_label")),
                "governed_review_reason_label": _clean_text(continuity_cluster_posture.get("governed_review_reason_label")),
                "governed_review_reason_summary": _clean_text(continuity_cluster_posture.get("governed_review_reason_summary")),
                "promotion_gate_status_label": _clean_text(belief_state_summary.get("promotion_gate_status_label")),
                "promotion_block_reason_label": _clean_text(belief_state_summary.get("promotion_block_reason_label")),
            },
            subject_label="This continuity cluster",
        )
        belief_state_summary = _overlay_continuity_cluster_review(belief_state_summary, continuity_overlay)
    payload = {
        "session_id": session_id,
        "workspace_id": _clean_text(workspace_id or session_record.get("workspace_id")),
        "source_name": _clean_text(source_name or session_record.get("source_name") or upload_metadata.get("filename")),
        "generated_at": _clean_text(
            decision_payload.get("source_updated_at")
            or analysis_report.get("source_updated_at")
            or decision_payload.get("generated_at")
        ),
        "session_identity": session_identity,
        "target_definition": target_definition,
        "decision_intent": decision_intent or None,
        "modeling_mode": modeling_mode or None,
        "run_contract": run_contract,
        "comparison_anchors": comparison_anchors,
        "evidence_records": records,
        "evidence_loop": evidence_loop,
        "evidence_activation_policy": evidence_activation_policy,
        "controlled_reuse": controlled_reuse,
        "claim_refs": claim_refs,
        "claims_summary": claims_summary,
        "experiment_request_refs": experiment_request_refs,
        "experiment_request_summary": experiment_request_summary,
        "experiment_result_refs": experiment_result_refs,
        "linked_result_summary": linked_result_summary,
        "belief_update_refs": belief_update_refs_from_records(belief_updates),
        "belief_update_summary": belief_update_summary,
        "belief_state_ref": belief_state_reference_from_record(belief_state) if isinstance(belief_state, dict) else None,
        "belief_state_summary": belief_state_summary,
        "belief_state_alignment_label": _clean_text(belief_state_alignment.get("label")),
        "belief_state_alignment_summary": _clean_text(belief_state_alignment.get("summary")),
        "bridge_state_notes": bridge_state_notes,
        "core_outputs": {
            "candidate_count": _candidate_count(decision_payload),
            "top_experiment_value": _safe_float(decision_summary.get("top_experiment_value")),
            "recommendation_summary": _clean_text(analysis_report.get("top_level_recommendation_summary")),
            "warning_count": len(analysis_report.get("warnings") or []) if isinstance(analysis_report.get("warnings"), list) else 0,
            "measurement_summary": measurement_summary,
            "ranking_diagnostics": ranking_diagnostics,
        },
        "decision_policy_summary": {
            "primary_score": _clean_text(ranking_policy.get("primary_score")),
            "primary_score_label": _clean_text(ranking_policy.get("primary_score_label")),
            "formula_label": _clean_text(ranking_policy.get("formula_label")),
            "formula_summary": _clean_text(ranking_policy.get("formula_summary")),
        },
        "review_summary": review_summary,
        "comparison_ready": bool(comparison_anchors.get("comparison_ready")),
        "contract_versions": _first_dict(
            analysis_report.get("contract_versions"),
            decision_payload.get("contract_versions"),
            summary_metadata.get("contract_versions"),
        ),
    }
    payload["scientific_decision_summary"] = build_scientific_decision_summary(payload)
    if effective_workspace_id and target_key:
        session_family_posture = compose_session_family_review_posture(
            source_class_label=_clean_text(
                claims_summary.get("source_class_label")
                or evidence_activation_policy.get("source_class_label")
            ),
            provenance_confidence_label=_clean_text(
                payload["scientific_decision_summary"].get("provenance_confidence_label"),
                default=PROVENANCE_CONFIDENCE_UNKNOWN,
            ),
            broader_governed_reuse_label=_clean_text(payload["scientific_decision_summary"].get("broader_governed_reuse_label")),
            broader_continuity_label=_clean_text(payload["scientific_decision_summary"].get("broader_continuity_label")),
            future_reuse_candidacy_label=_clean_text(payload["scientific_decision_summary"].get("future_reuse_candidacy_label")),
            promotion_gate_status_label=_clean_text(payload["scientific_decision_summary"].get("promotion_gate_status_label")),
            promotion_block_reason_label=_clean_text(payload["scientific_decision_summary"].get("promotion_block_reason_label")),
            belief_state_review_status_label=_clean_text(belief_state_summary.get("governed_review_status_label")) if isinstance(belief_state_summary, dict) else "",
            continuity_cluster_review_status_label=_clean_text(belief_state_summary.get("continuity_cluster_review_status_label")) if isinstance(belief_state_summary, dict) else "",
            active_support_count=_safe_int(claims_summary.get("claims_with_active_support_count"), 0),
            claims_with_active_governed_continuity_count=_safe_int(claims_summary.get("claims_with_active_governed_continuity_count"), 0),
            claims_with_tentative_active_continuity_count=_safe_int(claims_summary.get("claims_with_tentative_active_continuity_count"), 0),
            claims_with_contradiction_limited_reuse_count=_safe_int(claims_summary.get("claims_with_contradiction_limited_reuse_count"), 0),
            claims_with_historical_continuity_only_count=_safe_int(claims_summary.get("claims_with_historical_continuity_only_count"), 0),
            claims_with_no_governed_support_count=_safe_int(claims_summary.get("claims_with_no_governed_support_count"), 0),
            contested_flag=bool(payload["scientific_decision_summary"].get("current_support_contested_flag")),
            degraded_flag=bool(payload["scientific_decision_summary"].get("current_posture_degraded_flag")),
            historical_stronger_flag=bool(payload["scientific_decision_summary"].get("historical_support_stronger_than_current_flag")),
        )
        session_family_subject_id = _session_family_subject_id(session_id=session_id, target_key=target_key)
        sync_subject_governed_review_snapshot(
            {
                "workspace_id": effective_workspace_id,
                "session_id": session_id,
                "subject_type": SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER,
                "subject_id": session_family_subject_id,
                "target_key": target_key,
                "source_class_label": _clean_text(
                    claims_summary.get("source_class_label")
                    or evidence_activation_policy.get("source_class_label")
                ),
                "provenance_confidence_label": _clean_text(
                    payload["scientific_decision_summary"].get("provenance_confidence_label"),
                    default=PROVENANCE_CONFIDENCE_UNKNOWN,
                ),
                "trust_tier_label": _clean_text(session_family_posture.get("trust_tier_label"), default=TRUST_TIER_LOCAL_ONLY),
                "review_status_label": _clean_text(
                    session_family_posture.get("governed_review_status_label"),
                    default=REVIEW_STATUS_NOT_REVIEWED,
                ),
                "review_reason_label": _clean_text(
                    session_family_posture.get("governed_review_reason_label"),
                    default=REVIEW_REASON_LOCAL_DEFAULT,
                ),
                "review_reason_summary": _clean_text(session_family_posture.get("governed_review_reason_summary")),
                "promotion_gate_status_label": _clean_text(payload["scientific_decision_summary"].get("promotion_gate_status_label")),
                "promotion_block_reason_label": _clean_text(payload["scientific_decision_summary"].get("promotion_block_reason_label")),
                "decision_summary": _clean_text(session_family_posture.get("decision_summary")),
                "recorded_by": "scientific_session_truth",
                "metadata": {
                    "layer": SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER,
                    "broader_governed_reuse_label": _clean_text(payload["scientific_decision_summary"].get("broader_governed_reuse_label")),
                    "broader_continuity_label": _clean_text(payload["scientific_decision_summary"].get("broader_continuity_label")),
                    "future_reuse_candidacy_label": _clean_text(payload["scientific_decision_summary"].get("future_reuse_candidacy_label")),
                    "carryover_guardrail_summary": _clean_text(session_family_posture.get("carryover_guardrail_summary")),
                },
            }
        )
        session_family_overlay = build_governed_review_overlay(
            list_subject_governed_reviews(
                workspace_id=effective_workspace_id,
                subject_type=SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER,
                subject_id=session_family_subject_id,
            ),
            fallback_fields={
                "source_class_label": _clean_text(
                    claims_summary.get("source_class_label")
                    or evidence_activation_policy.get("source_class_label")
                ),
                "trust_tier_label": _clean_text(session_family_posture.get("trust_tier_label")),
                "provenance_confidence_label": _clean_text(payload["scientific_decision_summary"].get("provenance_confidence_label")),
                "governed_review_status_label": _clean_text(session_family_posture.get("governed_review_status_label")),
                "governed_review_reason_label": _clean_text(session_family_posture.get("governed_review_reason_label")),
                "governed_review_reason_summary": _clean_text(session_family_posture.get("governed_review_reason_summary")),
                "promotion_gate_status_label": _clean_text(payload["scientific_decision_summary"].get("promotion_gate_status_label")),
                "promotion_block_reason_label": _clean_text(payload["scientific_decision_summary"].get("promotion_block_reason_label")),
            },
            subject_label="This session-family carryover picture",
        )
        payload["scientific_decision_summary"].update(
            {
                "trust_tier_label": session_family_overlay.get("trust_tier_label") or payload["scientific_decision_summary"].get("trust_tier_label"),
                "provenance_confidence_label": session_family_overlay.get("provenance_confidence_label") or payload["scientific_decision_summary"].get("provenance_confidence_label"),
                "governed_review_status_label": session_family_overlay.get("governed_review_status_label") or payload["scientific_decision_summary"].get("governed_review_status_label"),
                "governed_review_status_summary": session_family_posture.get("governed_review_status_summary") or payload["scientific_decision_summary"].get("governed_review_status_summary"),
                "governed_review_reason_label": session_family_overlay.get("governed_review_reason_label") or payload["scientific_decision_summary"].get("governed_review_reason_label"),
                "governed_review_reason_summary": session_family_overlay.get("governed_review_reason_summary") or payload["scientific_decision_summary"].get("governed_review_reason_summary"),
                "session_family_review_status_label": session_family_overlay.get("governed_review_status_label") or session_family_posture.get("governed_review_status_label"),
                "session_family_review_status_summary": session_family_posture.get("governed_review_status_summary"),
                "session_family_review_reason_label": session_family_overlay.get("governed_review_reason_label") or session_family_posture.get("governed_review_reason_label"),
                "session_family_review_reason_summary": session_family_overlay.get("governed_review_reason_summary") or session_family_posture.get("governed_review_reason_summary"),
                "session_family_review_record_count": session_family_overlay.get("governed_review_record_count", 0),
                "session_family_review_history_summary": session_family_overlay.get("governed_review_history_summary", ""),
                "session_family_promotion_audit_summary": session_family_overlay.get("promotion_audit_summary", ""),
                "carryover_guardrail_summary": session_family_posture.get("carryover_guardrail_summary", ""),
            }
        )
    return validate_scientific_session_truth(payload)


def persist_scientific_session_truth(
    payload: dict[str, Any],
    *,
    session_id: str,
    workspace_id: str | None = None,
    created_by_user_id: str | None = None,
    register_artifact: bool = False,
) -> str:
    validated = validate_scientific_session_truth(payload)
    target_dir = uploaded_session_dir(session_id, create=True)
    path = target_dir / "scientific_session_truth.json"
    write_json_log(path, validated)
    SessionRepository().upsert_session(
        session_id=session_id,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        summary_metadata={"scientific_session_truth": validated},
    )
    if register_artifact:
        ArtifactRepository().register_artifact(
            artifact_type="scientific_session_truth_json",
            path=path,
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            metadata={
                "comparison_ready": bool(validated.get("comparison_ready")),
                "evidence_records": len(validated.get("evidence_records") or []),
                "claims": int(((validated.get("claims_summary") or {}).get("claim_count")) or 0),
                "experiment_requests": int(
                    (((validated.get("experiment_request_summary") or {}).get("request_count")) or 0)
                ),
                "experiment_results": int(
                    (((validated.get("linked_result_summary") or {}).get("result_count")) or 0)
                ),
                "belief_updates": int(
                    (((validated.get("belief_update_summary") or {}).get("update_count")) or 0)
                ),
                "belief_state_active_claims": int(
                    (((validated.get("belief_state_summary") or {}).get("active_claim_count")) or 0)
                ),
                "belief_state_accepted_updates": int(
                    (((validated.get("belief_state_summary") or {}).get("accepted_update_count")) or 0)
                ),
                "belief_state_proposed_updates": int(
                    (((validated.get("belief_state_summary") or {}).get("proposed_update_count")) or 0)
                ),
                "belief_state_superseded_updates": int(
                    (((validated.get("belief_state_summary") or {}).get("superseded_update_count")) or 0)
                ),
                "belief_state_alignment_label": _clean_text(validated.get("belief_state_alignment_label")),
            },
        )
    return str(path)


__all__ = [
    "build_controlled_reuse_state",
    "build_evidence_activation_policy",
    "build_evidence_records",
    "build_evidence_loop_summary",
    "build_scientific_session_truth",
    "persist_scientific_session_truth",
]
