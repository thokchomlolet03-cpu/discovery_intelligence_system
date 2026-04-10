from __future__ import annotations

from typing import Any


RESULT_SUPPORT_QUALITY_STRONG = "Stronger bounded interpretation"
RESULT_SUPPORT_QUALITY_LIMITED_NUMERIC = "Numeric-rule-based but limited"
RESULT_SUPPORT_QUALITY_CAUTION = "Screening or provisional caution"
RESULT_SUPPORT_QUALITY_CONTEXT_LIMITED = "Context-limited interpretation"
RESULT_SUPPORT_QUALITY_UNRESOLVED = "Unresolved under current basis"

RESULT_DECISION_USEFUL_FOLLOW_UP = "Can inform bounded follow-up"
RESULT_DECISION_USEFUL_CLARIFY = "Useful for clarification, still limited"
RESULT_DECISION_USEFUL_GATHER = "Gather stronger evidence before stronger follow-up"

SUPPORT_QUALITY_DECISION_USEFUL = "Decision-useful active support"
SUPPORT_QUALITY_ACTIVE_LIMITED = "Active but limited support"
SUPPORT_QUALITY_CONTEXT_LIMITED = "Context-limited active support"
SUPPORT_QUALITY_WEAK = "Weak or unresolved active support"

SUPPORT_DECISION_USEFUL_FOLLOW_UP = "Can justify bounded follow-up"
SUPPORT_DECISION_USEFUL_CLARIFY = "Clarify before stronger follow-up"
SUPPORT_DECISION_USEFUL_GATHER = "Gather stronger evidence before stronger follow-up"

GOVERNED_SUPPORT_POSTURE_GOVERNING = "Accepted and posture-governing"
GOVERNED_SUPPORT_POSTURE_ACCEPTED_LIMITED = "Accepted but limited-weight in current posture"
GOVERNED_SUPPORT_POSTURE_TENTATIVE = "Current support remains tentative"
GOVERNED_SUPPORT_POSTURE_HISTORICAL = "Historical only, not posture-governing"
GOVERNED_SUPPORT_POSTURE_INACTIVE = "Not posture-governing"

SUPPORT_COHERENCE_COHERENT = "Coherent current support"
SUPPORT_COHERENCE_CONTESTED = "Current support is contested"
SUPPORT_COHERENCE_DEGRADED = "Current posture is degraded"
SUPPORT_COHERENCE_CONTESTED_DEGRADED = "Contested and degraded current support"
SUPPORT_COHERENCE_MIXED = "Mixed active support"
SUPPORT_COHERENCE_HISTORICAL_STRONGER = "Historical support is stronger than current"
SUPPORT_COHERENCE_NONE = "No coherent current support"

SUPPORT_REUSE_STRONG = "Strongly reusable governed support"
SUPPORT_REUSE_SELECTIVE = "Selectively reusable support"
SUPPORT_REUSE_CONTRADICTION_LIMITED = "Reuse with contradiction caution"
SUPPORT_REUSE_WEAK = "Weakly reusable current support"
SUPPORT_REUSE_HISTORICAL_ONLY = "Historical-only for reuse"
SUPPORT_REUSE_NOT_READY = "Not yet suitable for strong governed reuse"

BROADER_REUSE_STRONG = "Broader reuse is strong under coherent current support"
BROADER_REUSE_SELECTIVE = "Broader reuse is selective"
BROADER_REUSE_CONTRADICTION_LIMITED = "Broader reuse is contradiction-limited"
BROADER_REUSE_HISTORICAL_ONLY = "Broader reuse is historical-only"
BROADER_REUSE_LOCAL_ONLY = "Support is locally meaningful, not broadly governing"

BROADER_CONTINUITY_COHERENT = "Coherent broader continuity cluster"
BROADER_CONTINUITY_SELECTIVE = "Selective broader continuity cluster"
BROADER_CONTINUITY_CONTESTED = "Contested broader continuity cluster"
BROADER_CONTINUITY_HISTORICAL = "Historical-heavy broader continuity cluster"
BROADER_CONTINUITY_NONE = "No broader continuity cluster"

FUTURE_REUSE_CANDIDACY_STRONG = "Stronger future governed reuse candidacy"
FUTURE_REUSE_CANDIDACY_SELECTIVE = "Selective future reuse candidacy"
FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED = "Contradiction-limited future reuse candidacy"
FUTURE_REUSE_CANDIDACY_HISTORICAL_ONLY = "Historical-only future reuse context"
FUTURE_REUSE_CANDIDACY_LOCAL_ONLY = "Local-only future reuse context"

CONTINUITY_CLUSTER_PROMOTION_CANDIDATE = "Promotion-candidate continuity cluster"
CONTINUITY_CLUSTER_SELECTIVE = "Selective continuity cluster"
CONTINUITY_CLUSTER_CONTEXT_ONLY = "Context-only continuity cluster"
CONTINUITY_CLUSTER_CONTRADICTION_LIMITED = "Contradiction-limited continuity cluster"
CONTINUITY_CLUSTER_HISTORICAL = "Historical-heavy continuity cluster"
CONTINUITY_CLUSTER_LOCAL_ONLY = "Local-only continuity cluster"

PROMOTION_CANDIDATE_STRONG = "Stronger broader governed reuse candidate"
PROMOTION_CANDIDATE_SELECTIVE = "Selective broader governed reuse candidate"
PROMOTION_CANDIDATE_CONTRADICTION_LIMITED = "Contradiction-limited promotion candidate"
PROMOTION_CANDIDATE_HISTORICAL_ONLY = "Historical-only promotion context"
PROMOTION_CANDIDATE_CONTEXT_ONLY = "Context-only continuity, not a promotion candidate"

PROMOTION_STABILITY_STABLE = "Stable enough for governed promotion review"
PROMOTION_STABILITY_SELECTIVE = "Only selectively stable for promotion"
PROMOTION_STABILITY_UNSTABLE = "Unstable under contradiction pressure"
PROMOTION_STABILITY_HISTORICAL = "Historical-heavy and not stably current"
PROMOTION_STABILITY_INSUFFICIENT = "Insufficient continuity stability"

PROMOTION_GATE_NOT_CANDIDATE = "Not a governed promotion candidate"
PROMOTION_GATE_BLOCKED = "Candidate but blocked from promotion"
PROMOTION_GATE_SELECTIVE = "Selectively promotable under bounded governed rules"
PROMOTION_GATE_PROMOTABLE = "Promotable under bounded governed rules"
PROMOTION_GATE_DOWNGRADED = "Downgraded from stronger promotion posture"
PROMOTION_GATE_QUARANTINED = "Quarantined from stronger promotion"

PROMOTION_BLOCK_NONE = "No material promotion block recorded"
PROMOTION_BLOCK_LOCAL_ONLY = "Local-only meaning"
PROMOTION_BLOCK_CONTEXT_ONLY = "Context-only continuity"
PROMOTION_BLOCK_SELECTIVE_ONLY = "Selective continuity only"
PROMOTION_BLOCK_CONTRADICTION = "Contradiction-heavy history"
PROMOTION_BLOCK_DEGRADED = "Degraded present posture"
PROMOTION_BLOCK_HISTORICAL = "Historical-heavy continuity"
PROMOTION_BLOCK_STABILITY = "Insufficient governed stability"
PROMOTION_BLOCK_DOWNGRADED = "Downgraded by newer contradictory evidence"
PROMOTION_BLOCK_QUARANTINED = "Quarantined by unstable continuity"

SOURCE_CLASS_CURATED = "Trusted benchmark or curated source"
SOURCE_CLASS_INTERNAL_GOVERNED = "Internal governed experimental source"
SOURCE_CLASS_AFFILIATED = "Partner or affiliated source"
SOURCE_CLASS_UNCONTROLLED_UPLOAD = "User-uploaded uncontrolled source"
SOURCE_CLASS_DERIVED_EXTRACTED = "Derived or extracted source"
SOURCE_CLASS_AI_DERIVED = "AI-derived interpretation"
SOURCE_CLASS_UNKNOWN = "Unknown-origin structured input"

PROVENANCE_CONFIDENCE_STRONG = "Strong provenance"
PROVENANCE_CONFIDENCE_MODERATE = "Moderate provenance"
PROVENANCE_CONFIDENCE_WEAK = "Weak provenance"
PROVENANCE_CONFIDENCE_UNKNOWN = "Unknown provenance"

TRUST_TIER_LOCAL_ONLY = "Local-only evidence"
TRUST_TIER_CANDIDATE = "Candidate evidence"
TRUST_TIER_GOVERNED = "Governed-trusted evidence"

REVIEW_STATUS_NOT_REVIEWED = "Not reviewed for broader influence"
REVIEW_STATUS_CANDIDATE = "Review candidate"
REVIEW_STATUS_APPROVED = "Reviewed and approved for broader governed consideration"
REVIEW_STATUS_BLOCKED = "Reviewed and blocked"
REVIEW_STATUS_DEFERRED = "Reviewed and deferred"
REVIEW_STATUS_DOWNGRADED = "Reviewed and downgraded later"
REVIEW_STATUS_QUARANTINED = "Reviewed and quarantined later"

REVIEW_REASON_LOCAL_DEFAULT = "Local-only by default"
REVIEW_REASON_WEAK_PROVENANCE = "Weak or unknown provenance"
REVIEW_REASON_UNCONTROLLED_SOURCE = "Uncontrolled source class"
REVIEW_REASON_STRONGER_TRUST_NEEDED = "Stronger trust needed before broader influence"
REVIEW_REASON_APPROVED = "Approved for bounded broader governed consideration"
REVIEW_REASON_CONTRADICTION = "Contradiction-heavy history limits broader influence"
REVIEW_REASON_DEGRADED = "Degraded present posture limits broader influence"
REVIEW_REASON_HISTORICAL = "Historical-heavy continuity remains contextual"
REVIEW_REASON_DOWNGRADED = "Newer weakening evidence triggered downgrade"
REVIEW_REASON_QUARANTINED = "Unstable continuity triggered quarantine"
REVIEW_REASON_SELECTIVE = "Selective continuity remains too bounded"

RESULT_CONTEXT_LIMITATION_NONE = "No material target-context limitation recorded"
RESULT_CONTEXT_LIMITATION_ASSAY = "Assay context limited"
RESULT_CONTEXT_LIMITATION_UNIT = "Unit alignment limited"
RESULT_CONTEXT_LIMITATION_ALIGNED = "Target context aligned or not explicitly constrained"

_WEAK_INPUT_LABEL = "Weak interpretation basis"
_STRONG_INPUT_LABEL = "Stronger interpretation basis"
_SPARSE_ASSAY_LABEL = "Sparse assay context"
_WEAK_ASSAY_LABEL = "Weak assay alignment"
_NO_TARGET_RULE_ALIGNMENT = "No target rule alignment"
_NUMERIC_UNRESOLVED_LABEL = "Unresolved under current numeric basis"


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _normalized_unit(value: Any) -> str:
    return _clean_text(value).lower().replace("μ", "u").replace("µ", "u").replace(" ", "")


def classify_result_context_limitation(
    result: dict[str, Any] | None,
    *,
    bounded_numeric_interpretation: bool,
) -> dict[str, str]:
    result = result if isinstance(result, dict) else {}
    target_definition = (
        result.get("target_definition_snapshot") if isinstance(result.get("target_definition_snapshot"), dict) else {}
    )
    assay_context = _clean_text(result.get("assay_context"))
    target_assay = _clean_text(target_definition.get("assay_context"))
    target_unit = _normalized_unit(target_definition.get("measurement_unit"))
    observed_unit = _normalized_unit(result.get("measurement_unit"))

    if bounded_numeric_interpretation and target_unit:
        if not observed_unit:
            return {
                "result_context_limitation_label": RESULT_CONTEXT_LIMITATION_UNIT,
                "result_context_limitation_summary": (
                    "The current target definition expects a measurement unit, but the recorded numeric result does not include a matching unit."
                ),
            }
        if (
            observed_unit != target_unit
            and target_unit not in observed_unit
            and observed_unit not in target_unit
        ):
            return {
                "result_context_limitation_label": RESULT_CONTEXT_LIMITATION_UNIT,
                "result_context_limitation_summary": (
                    "The recorded numeric result does not align cleanly with the current target unit, so interpretation should remain context-limited."
                ),
            }

    if target_assay:
        normalized_target_assay = target_assay.lower()
        normalized_assay_context = assay_context.lower()
        if not normalized_assay_context:
            return {
                "result_context_limitation_label": RESULT_CONTEXT_LIMITATION_ASSAY,
                "result_context_limitation_summary": (
                    "The current target definition expects assay context, but none was recorded with this observed result."
                ),
            }
        if (
            normalized_assay_context != normalized_target_assay
            and normalized_target_assay not in normalized_assay_context
            and normalized_assay_context not in normalized_target_assay
        ):
            return {
                "result_context_limitation_label": RESULT_CONTEXT_LIMITATION_ASSAY,
                "result_context_limitation_summary": (
                    "Recorded assay context does not align closely enough with the target-scoped assay expectation."
                ),
            }

    if assay_context:
        return {
            "result_context_limitation_label": RESULT_CONTEXT_LIMITATION_ALIGNED,
            "result_context_limitation_summary": (
                "Assay context is recorded and can be reviewed against the current target context."
            ),
        }
    return {
        "result_context_limitation_label": RESULT_CONTEXT_LIMITATION_NONE,
        "result_context_limitation_summary": "",
    }


def classify_result_support_quality(
    *,
    result_quality: str,
    has_observed_label: bool,
    bounded_numeric_interpretation: bool,
    unresolved_numeric_interpretation: bool,
    context_limitation_label: str,
    context_limitation_summary: str = "",
) -> dict[str, str]:
    quality_token = _clean_text(result_quality, default="provisional").lower()
    limitation_label = _clean_text(
        context_limitation_label,
        default=RESULT_CONTEXT_LIMITATION_NONE,
    )

    if unresolved_numeric_interpretation:
        return {
            "result_support_quality_label": RESULT_SUPPORT_QUALITY_UNRESOLVED,
            "result_support_quality_summary": (
                "A result is recorded, but its current support usefulness remains unresolved under the available target basis."
            ),
            "result_decision_usefulness_label": RESULT_DECISION_USEFUL_GATHER,
        }
    if limitation_label in {RESULT_CONTEXT_LIMITATION_ASSAY, RESULT_CONTEXT_LIMITATION_UNIT}:
        summary = "A result is recorded, but target-context limitations keep its current support usefulness cautious."
        if context_limitation_summary:
            summary += f" {context_limitation_summary}"
        return {
            "result_support_quality_label": RESULT_SUPPORT_QUALITY_CONTEXT_LIMITED,
            "result_support_quality_summary": summary,
            "result_decision_usefulness_label": RESULT_DECISION_USEFUL_CLARIFY,
        }
    if bounded_numeric_interpretation:
        return {
            "result_support_quality_label": RESULT_SUPPORT_QUALITY_LIMITED_NUMERIC,
            "result_support_quality_summary": (
                "A numeric result can be read under the current target rule, but that numeric path should still be treated as bounded rather than strongly conclusive."
            ),
            "result_decision_usefulness_label": RESULT_DECISION_USEFUL_CLARIFY,
        }
    if quality_token in {"screening", "provisional"}:
        return {
            "result_support_quality_label": RESULT_SUPPORT_QUALITY_CAUTION,
            "result_support_quality_summary": (
                "A result is recorded, but screening or provisional quality keeps its support usefulness limited for present decision-making."
            ),
            "result_decision_usefulness_label": RESULT_DECISION_USEFUL_GATHER,
        }
    if has_observed_label:
        return {
            "result_support_quality_label": RESULT_SUPPORT_QUALITY_STRONG,
            "result_support_quality_summary": (
                "A direct observed outcome is recorded under a cleaner current basis, so it can more usefully inform bounded follow-up without implying proof."
            ),
            "result_decision_usefulness_label": RESULT_DECISION_USEFUL_FOLLOW_UP,
        }
    return {
        "result_support_quality_label": RESULT_SUPPORT_QUALITY_CAUTION,
        "result_support_quality_summary": (
            "A result is recorded, but its present usefulness remains cautious because the basis is still limited."
        ),
        "result_decision_usefulness_label": RESULT_DECISION_USEFUL_CLARIFY,
    }


def classify_belief_update_support_quality(update: dict[str, Any] | None) -> dict[str, str]:
    update = update if isinstance(update, dict) else {}
    metadata = update.get("metadata") if isinstance(update.get("metadata"), dict) else {}
    support_input_quality_label = _clean_text(
        update.get("support_input_quality_label") or metadata.get("support_input_quality_label")
    )
    assay_context_alignment_label = _clean_text(
        update.get("assay_context_alignment_label") or metadata.get("assay_context_alignment_label")
    )
    result_interpretation_basis = _clean_text(
        update.get("result_interpretation_basis") or metadata.get("result_interpretation_basis")
    )
    numeric_result_resolution_label = _clean_text(
        update.get("numeric_result_resolution_label") or metadata.get("numeric_result_resolution_label")
    )
    target_rule_alignment_label = _clean_text(
        update.get("target_rule_alignment_label") or metadata.get("target_rule_alignment_label")
    )
    linked_result_quality = _clean_text(metadata.get("linked_result_quality"), default="provisional").lower()
    update_direction = _clean_text(update.get("update_direction")).lower()

    if (
        update_direction == "unresolved"
        or support_input_quality_label == _WEAK_INPUT_LABEL
        or numeric_result_resolution_label == _NUMERIC_UNRESOLVED_LABEL
    ):
        return {
            "support_quality_label": SUPPORT_QUALITY_WEAK,
            "support_quality_summary": (
                "An active support update exists, but the current evidence basis remains weak or unresolved under the available target context."
            ),
            "support_decision_usefulness_label": SUPPORT_DECISION_USEFUL_GATHER,
        }
    if assay_context_alignment_label in {_SPARSE_ASSAY_LABEL, _WEAK_ASSAY_LABEL} or target_rule_alignment_label == _NO_TARGET_RULE_ALIGNMENT:
        return {
            "support_quality_label": SUPPORT_QUALITY_CONTEXT_LIMITED,
            "support_quality_summary": (
                "Active support exists, but assay or target-context limitations keep the current support picture cautious."
            ),
            "support_decision_usefulness_label": SUPPORT_DECISION_USEFUL_CLARIFY,
        }
    if result_interpretation_basis == "Numeric outcome under current target rule":
        return {
            "support_quality_label": SUPPORT_QUALITY_ACTIVE_LIMITED,
            "support_quality_summary": (
                "Active support exists, but it still depends on bounded numeric interpretation, so it should support clarification more than strong present follow-up."
            ),
            "support_decision_usefulness_label": SUPPORT_DECISION_USEFUL_CLARIFY,
        }
    if support_input_quality_label == _STRONG_INPUT_LABEL and linked_result_quality == "confirmatory":
        return {
            "support_quality_label": SUPPORT_QUALITY_DECISION_USEFUL,
            "support_quality_summary": (
                "Active support is grounded in a stronger-basis observed outcome and is decision-useful enough for bounded follow-up."
            ),
            "support_decision_usefulness_label": SUPPORT_DECISION_USEFUL_FOLLOW_UP,
        }
    return {
        "support_quality_label": SUPPORT_QUALITY_ACTIVE_LIMITED,
        "support_quality_summary": (
            "Active support exists, but it remains limited because the current result basis is still cautious or not yet strong enough for stronger follow-up."
        ),
        "support_decision_usefulness_label": SUPPORT_DECISION_USEFUL_CLARIFY,
    }


def classify_governed_support_posture(update: dict[str, Any] | None) -> dict[str, str]:
    update = update if isinstance(update, dict) else {}
    metadata = update.get("metadata") if isinstance(update.get("metadata"), dict) else {}
    governance_status = _clean_text(
        update.get("governance_status") or metadata.get("governance_status")
    ).lower()
    support_quality_label = _clean_text(
        update.get("support_quality_label") or metadata.get("support_quality_label")
    )
    if not support_quality_label:
        support_quality_label = classify_belief_update_support_quality(update).get("support_quality_label", "")

    if governance_status == "superseded":
        return {
            "governed_support_posture_label": GOVERNED_SUPPORT_POSTURE_HISTORICAL,
            "governed_support_posture_summary": (
                "This support update remains historically informative, but superseded support should not govern present posture."
            ),
        }
    if governance_status == "rejected":
        return {
            "governed_support_posture_label": GOVERNED_SUPPORT_POSTURE_INACTIVE,
            "governed_support_posture_summary": (
                "This support update does not govern current posture because it was rejected."
            ),
        }
    if governance_status == "accepted":
        if support_quality_label == SUPPORT_QUALITY_DECISION_USEFUL:
            return {
                "governed_support_posture_label": GOVERNED_SUPPORT_POSTURE_GOVERNING,
                "governed_support_posture_summary": (
                    "This support update is accepted and decision-useful enough to help govern present posture for bounded follow-up."
                ),
            }
        return {
            "governed_support_posture_label": GOVERNED_SUPPORT_POSTURE_ACCEPTED_LIMITED,
            "governed_support_posture_summary": (
                "This support update is accepted, but its limited or context-limited basis means it should count only weakly in present posture."
            ),
        }
    if governance_status == "proposed":
        return {
            "governed_support_posture_label": GOVERNED_SUPPORT_POSTURE_TENTATIVE,
            "governed_support_posture_summary": (
                "This support update is active, but it remains proposed and should stay tentative until stronger governed confirmation exists."
            ),
        }
    return {
        "governed_support_posture_label": GOVERNED_SUPPORT_POSTURE_INACTIVE,
        "governed_support_posture_summary": (
            "This support update does not currently govern present posture."
        ),
    }


def quality_bucket_for_label(label: Any) -> str:
    token = _clean_text(label)
    if token in {RESULT_SUPPORT_QUALITY_STRONG, SUPPORT_QUALITY_DECISION_USEFUL}:
        return "decision_useful"
    if token in {
        RESULT_SUPPORT_QUALITY_LIMITED_NUMERIC,
        RESULT_SUPPORT_QUALITY_CAUTION,
        SUPPORT_QUALITY_ACTIVE_LIMITED,
    }:
        return "limited"
    if token in {RESULT_SUPPORT_QUALITY_CONTEXT_LIMITED, SUPPORT_QUALITY_CONTEXT_LIMITED}:
        return "context_limited"
    if token in {RESULT_SUPPORT_QUALITY_UNRESOLVED, SUPPORT_QUALITY_WEAK}:
        return "weak"
    return ""


def rollup_quality_labels(labels: list[Any]) -> dict[str, int]:
    counts = {
        "decision_useful_count": 0,
        "limited_count": 0,
        "context_limited_count": 0,
        "weak_count": 0,
    }
    for label in labels:
        bucket = quality_bucket_for_label(label)
        if bucket:
            counts[f"{bucket}_count"] += 1
    return counts


def governed_support_posture_bucket_for_label(label: Any) -> str:
    token = _clean_text(label)
    if token == GOVERNED_SUPPORT_POSTURE_GOVERNING:
        return "governing"
    if token == GOVERNED_SUPPORT_POSTURE_ACCEPTED_LIMITED:
        return "accepted_limited"
    if token == GOVERNED_SUPPORT_POSTURE_TENTATIVE:
        return "tentative"
    if token == GOVERNED_SUPPORT_POSTURE_HISTORICAL:
        return "historical"
    if token == GOVERNED_SUPPORT_POSTURE_INACTIVE:
        return "inactive"
    return ""


def rollup_governed_support_postures(labels: list[Any]) -> dict[str, int]:
    counts = {
        "governing_count": 0,
        "accepted_limited_count": 0,
        "tentative_count": 0,
        "historical_count": 0,
        "inactive_count": 0,
    }
    for label in labels:
        bucket = governed_support_posture_bucket_for_label(label)
        if bucket:
            counts[f"{bucket}_count"] += 1
    return counts


def classify_evidence_source_class(
    *,
    evidence_type: Any = "",
    source: Any = "",
    truth_status: Any = "",
    result_source: Any = "",
    linked_claim_id: Any = "",
    linked_request_id: Any = "",
    created_by: Any = "",
) -> dict[str, str]:
    evidence_type_token = _clean_text(evidence_type).lower()
    source_token = _clean_text(source).lower()
    truth_status_token = _clean_text(truth_status).lower()
    result_source_token = _clean_text(result_source).lower()
    created_by_token = _clean_text(created_by).lower()
    has_governed_link = bool(_clean_text(linked_claim_id) or _clean_text(linked_request_id))

    if any(token in source_token for token in ("benchmark", "curated", "trusted_dataset", "reference_dataset")):
        label = SOURCE_CLASS_CURATED
        summary = "This evidence comes from a more curated or benchmark-like source and can support stronger bounded trust than a raw uncontrolled upload."
    elif result_source_token == "external_record" or "partner" in source_token or "affiliate" in source_token:
        label = SOURCE_CLASS_AFFILIATED
        summary = "This evidence comes from a partner or affiliated source, so it may support broader review candidacy but still needs bounded trust checks."
    elif has_governed_link and result_source_token in {"manual_entry", "uploaded_result"}:
        label = SOURCE_CLASS_INTERNAL_GOVERNED
        summary = "This evidence is linked into an internal governed experiment/request path, so it has a stronger session-traceable basis than an uncontrolled upload."
    elif evidence_type_token in {"derived_label", "reference_context", "workspace_memory"} or truth_status_token in {"derived", "retrieved"}:
        label = SOURCE_CLASS_DERIVED_EXTRACTED
        summary = "This evidence is derived, extracted, or retrieved context rather than a direct controlled observation."
    elif evidence_type_token == "model_prediction" or "ai" in source_token or created_by_token in {"ai", "system_ai"}:
        label = SOURCE_CLASS_AI_DERIVED
        summary = "This evidence is AI-derived or model-derived interpretation and should not behave like direct observed truth."
    elif result_source_token == "uploaded_result" or source_token in {"uploaded_dataset", "user_upload", "manual_upload"}:
        label = SOURCE_CLASS_UNCONTROLLED_UPLOAD
        summary = "This evidence came from a user-controlled upload path and should remain local-first unless stronger trust is earned later."
    elif source_token:
        label = SOURCE_CLASS_UNKNOWN
        summary = "This evidence has a recorded source, but its broader trust class remains unknown under the current bounded rules."
    else:
        label = SOURCE_CLASS_UNKNOWN
        summary = "The source class is not clearly recorded, so broader trust should remain conservative."
    return {
        "source_class_label": label,
        "source_class_summary": summary,
    }


def assess_provenance_confidence(
    *,
    source_class_label: Any = "",
    source: Any = "",
    truth_status: Any = "",
    ingested_by: Any = "",
    linked_claim_id: Any = "",
    linked_request_id: Any = "",
) -> dict[str, str]:
    source_class = _clean_text(source_class_label)
    source_token = _clean_text(source)
    truth_status_token = _clean_text(truth_status).lower()
    ingested_by_token = _clean_text(ingested_by)
    has_lineage = bool(_clean_text(linked_claim_id) or _clean_text(linked_request_id))

    if source_class in {SOURCE_CLASS_CURATED, SOURCE_CLASS_INTERNAL_GOVERNED} and source_token and (has_lineage or ingested_by_token):
        label = PROVENANCE_CONFIDENCE_STRONG
        summary = "Provenance is relatively strong for the current bounded system: the source is identifiable and the evidence stays linked into a governed workflow."
    elif source_class in {SOURCE_CLASS_AFFILIATED, SOURCE_CLASS_DERIVED_EXTRACTED} and source_token:
        label = PROVENANCE_CONFIDENCE_MODERATE
        summary = "Provenance is moderate: the source path is visible, but the evidence is still partly dependent on external or derived context."
    elif source_class in {SOURCE_CLASS_UNCONTROLLED_UPLOAD, SOURCE_CLASS_AI_DERIVED}:
        label = PROVENANCE_CONFIDENCE_WEAK
        summary = "Provenance is weak for broader influence: the evidence may still be useful locally, but source control or derivation limits stronger trust."
    elif truth_status_token in {"predicted", "derived"}:
        label = PROVENANCE_CONFIDENCE_WEAK
        summary = "Provenance is weak because the current evidence is derived or predicted rather than a clearly governed direct observation."
    else:
        label = PROVENANCE_CONFIDENCE_UNKNOWN
        summary = "Provenance confidence is unknown because the source and lineage are not explicit enough for stronger broader trust."
    return {
        "provenance_confidence_label": label,
        "provenance_confidence_summary": summary,
    }


def rollup_provenance_confidence(labels: list[Any]) -> dict[str, int]:
    counts = {
        "strong_count": 0,
        "moderate_count": 0,
        "weak_count": 0,
        "unknown_count": 0,
    }
    for label in labels:
        token = _clean_text(label)
        if token == PROVENANCE_CONFIDENCE_STRONG:
            counts["strong_count"] += 1
        elif token == PROVENANCE_CONFIDENCE_MODERATE:
            counts["moderate_count"] += 1
        elif token == PROVENANCE_CONFIDENCE_WEAK:
            counts["weak_count"] += 1
        elif token == PROVENANCE_CONFIDENCE_UNKNOWN:
            counts["unknown_count"] += 1
    return counts


def assess_governed_evidence_posture(
    *,
    source_class_label: Any = "",
    provenance_confidence_label: Any = "",
    promotion_gate_status_label: Any = "",
    promotion_block_reason_label: Any = "",
    active_support_count: int = 0,
    accepted_support_count: int = 0,
    candidate_context: bool = False,
    contested_flag: bool = False,
    degraded_flag: bool = False,
    historical_stronger_flag: bool = False,
    local_only_default: bool = True,
) -> dict[str, str]:
    source_class = _clean_text(source_class_label)
    provenance = _clean_text(provenance_confidence_label)
    promotion_gate = _clean_text(promotion_gate_status_label)
    promotion_block = _clean_text(promotion_block_reason_label)

    trust_tier_label = TRUST_TIER_LOCAL_ONLY
    trust_tier_summary = (
        "This evidence remains local-only by default. It can shape local reasoning, but it has not earned stronger broader influence."
    )
    review_status_label = REVIEW_STATUS_NOT_REVIEWED
    review_status_summary = (
        "No broader governed review posture is recorded yet, so this evidence should remain local-first."
    )
    review_reason_label = REVIEW_REASON_LOCAL_DEFAULT
    review_reason_summary = (
        "Uploaded or session-derived evidence is local-only by default until stronger trust, provenance, and continuity conditions are satisfied."
    )

    if promotion_gate == PROMOTION_GATE_QUARANTINED:
        trust_tier_label = TRUST_TIER_CANDIDATE
        trust_tier_summary = (
            "This evidence history remains visible as a broader candidate context, but it is currently quarantined from stronger broader influence."
        )
        review_status_label = REVIEW_STATUS_QUARANTINED
        review_status_summary = (
            "Governed review posture is quarantined because continuity is too unstable for stronger broader influence right now."
        )
        review_reason_label = REVIEW_REASON_QUARANTINED
        review_reason_summary = (
            "Broader influence is quarantined because contradiction-heavy or unstable continuity makes promotion unsafe under bounded rules."
        )
    elif promotion_gate == PROMOTION_GATE_DOWNGRADED:
        trust_tier_label = TRUST_TIER_CANDIDATE
        trust_tier_summary = (
            "This evidence had stronger broader-candidate posture earlier, but it has been downgraded and should not keep silent broader influence."
        )
        review_status_label = REVIEW_STATUS_DOWNGRADED
        review_status_summary = (
            "Governed review posture was downgraded later because newer weakening evidence reduced broader trust."
        )
        review_reason_label = REVIEW_REASON_DOWNGRADED
        review_reason_summary = (
            "Broader trust posture was reduced because newer evidence weakened the previously cleaner continuity picture."
        )
    elif promotion_gate == PROMOTION_GATE_PROMOTABLE and provenance in {PROVENANCE_CONFIDENCE_STRONG, PROVENANCE_CONFIDENCE_MODERATE} and source_class in {
        SOURCE_CLASS_CURATED,
        SOURCE_CLASS_INTERNAL_GOVERNED,
        SOURCE_CLASS_AFFILIATED,
    } and active_support_count > 0 and accepted_support_count > 0 and not contested_flag and not degraded_flag and not historical_stronger_flag:
        trust_tier_label = TRUST_TIER_GOVERNED
        trust_tier_summary = (
            "This evidence has earned governed-trusted posture for bounded broader consideration because trust basis, provenance, and continuity remain strong enough under current rules."
        )
        review_status_label = REVIEW_STATUS_APPROVED
        review_status_summary = (
            "Governed review posture is approved for broader governed consideration, while still remaining bounded rather than final truth."
        )
        review_reason_label = REVIEW_REASON_APPROVED
        review_reason_summary = (
            "The current evidence basis is strong enough for bounded broader governed consideration because source class, provenance, and continuity all remain sufficiently coherent."
        )
    elif promotion_gate in {PROMOTION_GATE_SELECTIVE, PROMOTION_GATE_BLOCKED, PROMOTION_GATE_PROMOTABLE} or candidate_context:
        trust_tier_label = TRUST_TIER_CANDIDATE
        if provenance in {PROVENANCE_CONFIDENCE_WEAK, PROVENANCE_CONFIDENCE_UNKNOWN}:
            review_status_label = REVIEW_STATUS_BLOCKED
            review_status_summary = (
                "This evidence is a review candidate, but weaker provenance keeps it blocked from stronger broader trust."
            )
            review_reason_label = REVIEW_REASON_WEAK_PROVENANCE
            review_reason_summary = (
                "Broader influence is blocked because provenance remains weak or unknown even though the continuity history is still locally useful."
            )
            trust_tier_summary = (
                "This evidence is interesting enough to review, but weak provenance keeps it from earning governed-trusted broader influence."
            )
        elif source_class in {SOURCE_CLASS_UNCONTROLLED_UPLOAD, SOURCE_CLASS_UNKNOWN, SOURCE_CLASS_AI_DERIVED} and local_only_default:
            review_status_label = REVIEW_STATUS_DEFERRED
            review_status_summary = (
                "This evidence is a review candidate, but broader trust is deferred because the source class is too uncontrolled for stronger promotion today."
            )
            review_reason_label = REVIEW_REASON_UNCONTROLLED_SOURCE
            review_reason_summary = (
                "Broader trust is deferred because the current source class is uncontrolled, AI-derived, or otherwise too weak for stronger governed influence."
            )
            trust_tier_summary = (
                "This evidence can inform local reasoning and bounded review, but it remains only a candidate until the source basis becomes stronger."
            )
        elif promotion_gate == PROMOTION_GATE_BLOCKED:
            review_status_label = REVIEW_STATUS_BLOCKED
            review_status_summary = (
                "This evidence is a broader candidate, but it remains blocked under bounded governed rules."
            )
            if promotion_block == PROMOTION_BLOCK_CONTRADICTION:
                review_reason_label = REVIEW_REASON_CONTRADICTION
                review_reason_summary = (
                    "Broader influence is blocked because contradiction-heavy history weakens continuity too sharply."
                )
            elif promotion_block == PROMOTION_BLOCK_DEGRADED:
                review_reason_label = REVIEW_REASON_DEGRADED
                review_reason_summary = (
                    "Broader influence is blocked because degraded present posture makes earlier stronger continuity unsafe to keep promoting."
                )
            elif promotion_block == PROMOTION_BLOCK_HISTORICAL:
                review_reason_label = REVIEW_REASON_HISTORICAL
                review_reason_summary = (
                    "Broader influence is blocked because the continuity picture is mainly historical-heavy rather than stably current."
                )
            else:
                review_reason_label = REVIEW_REASON_STRONGER_TRUST_NEEDED
                review_reason_summary = (
                    "Broader influence is blocked because stronger trust and continuity conditions are still needed."
                )
            trust_tier_summary = (
                "This evidence remains a broader review candidate, but current contradiction, degradation, or limited stability keep it out of governed-trusted posture."
            )
        elif promotion_gate == PROMOTION_GATE_SELECTIVE:
            review_status_label = REVIEW_STATUS_DEFERRED
            review_status_summary = (
                "This evidence is selectively promotable in principle, but broader trust should stay cautious and reviewable."
            )
            review_reason_label = REVIEW_REASON_SELECTIVE
            review_reason_summary = (
                "Broader influence remains selective only because continuity is usable but still too bounded for cleaner governed trust."
            )
            trust_tier_summary = (
                "This evidence has some broader candidate value, but it should still travel selectively rather than as fully governed-trusted evidence."
            )
        else:
            review_status_label = REVIEW_STATUS_CANDIDATE
            review_status_summary = (
                "This evidence is a review candidate for broader governed consideration, but it has not been elevated into governed-trusted posture."
            )
            review_reason_label = REVIEW_REASON_STRONGER_TRUST_NEEDED
            review_reason_summary = (
                "Stronger trust, provenance, or continuity would still be needed before broader influence should increase."
            )
            trust_tier_summary = (
                "This evidence has enough bounded value to enter review-candidate posture, but it has not earned governed-trusted broader influence."
            )
    elif provenance in {PROVENANCE_CONFIDENCE_WEAK, PROVENANCE_CONFIDENCE_UNKNOWN}:
        review_reason_label = REVIEW_REASON_WEAK_PROVENANCE
        review_reason_summary = (
            "This evidence remains local-first because weak or unknown provenance should not silently behave like broader trust."
        )
        trust_tier_summary = (
            "This evidence may still be useful locally, but weak or unknown provenance keeps it out of broader trust posture."
        )

    return {
        "trust_tier_label": trust_tier_label,
        "trust_tier_summary": trust_tier_summary,
        "governed_review_status_label": review_status_label,
        "governed_review_status_summary": review_status_summary,
        "governed_review_reason_label": review_reason_label,
        "governed_review_reason_summary": review_reason_summary,
    }


def classify_belief_update_contradiction_role(update: dict[str, Any] | None) -> dict[str, str]:
    update = update if isinstance(update, dict) else {}
    metadata = update.get("metadata") if isinstance(update.get("metadata"), dict) else {}
    governance_status = _clean_text(
        update.get("governance_status") or metadata.get("governance_status")
    ).lower()
    update_direction = _clean_text(update.get("update_direction") or metadata.get("update_direction")).lower()
    support_quality_label = _clean_text(
        update.get("support_quality_label") or metadata.get("support_quality_label")
    )
    if not support_quality_label:
        support_quality_label = classify_belief_update_support_quality(update).get("support_quality_label", "")
    governed_posture_label = _clean_text(
        update.get("governed_support_posture_label") or metadata.get("governed_support_posture_label")
    )
    if not governed_posture_label:
        governed_posture_label = classify_governed_support_posture(update).get("governed_support_posture_label", "")

    if governance_status == "superseded":
        return {
            "contradiction_role_label": "Historical context only",
            "contradiction_role_summary": (
                "This support update remains visible historically, but it no longer governs present posture after supersession."
            ),
        }
    if governance_status == "rejected":
        return {
            "contradiction_role_label": "Not current support",
            "contradiction_role_summary": (
                "This support update does not contribute to current posture because it was rejected."
            ),
        }
    if update_direction == "weakened":
        if governance_status == "accepted":
            return {
                "contradiction_role_label": "Applies contradiction pressure",
                "contradiction_role_summary": (
                    "This accepted support update weakens the current claim picture and should reduce present posture without implying disproof."
                ),
            }
        return {
            "contradiction_role_label": "Tentative contradiction pressure",
            "contradiction_role_summary": (
                "This proposed support update points toward weakening, so it adds contradiction pressure while current posture remains tentative."
            ),
        }
    if update_direction == "unresolved":
        return {
            "contradiction_role_label": "Keeps current posture contested",
            "contradiction_role_summary": (
                "This support update does not cleanly strengthen the current claim picture, so it keeps present posture more contested and clarification-heavy."
            ),
        }
    if governed_posture_label == GOVERNED_SUPPORT_POSTURE_GOVERNING:
        return {
            "contradiction_role_label": "Reinforces current posture",
            "contradiction_role_summary": (
                "This accepted support update reinforces current posture strongly enough to help govern bounded follow-up."
            ),
        }
    if governed_posture_label == GOVERNED_SUPPORT_POSTURE_ACCEPTED_LIMITED:
        return {
            "contradiction_role_label": "Adds limited current support",
            "contradiction_role_summary": (
                "This accepted support update adds current support, but only with limited present weight because the basis remains cautious."
            ),
        }
    if support_quality_label in {SUPPORT_QUALITY_CONTEXT_LIMITED, SUPPORT_QUALITY_WEAK}:
        return {
            "contradiction_role_label": "Keeps current posture tentative",
            "contradiction_role_summary": (
                "This active support update keeps present posture tentative because its basis is still context-limited or weak."
            ),
        }
    return {
        "contradiction_role_label": "Adds tentative current support",
        "contradiction_role_summary": (
            "This active support update adds current support on paper, but it should stay tentative until the evidence picture is cleaner."
        ),
    }


def assess_support_coherence(
    *,
    active_count: int,
    accepted_count: int,
    strengthened_count: int,
    weakened_count: int,
    unresolved_count: int,
    support_quality_counts: dict[str, int] | None = None,
    posture_counts: dict[str, int] | None = None,
    historical_decision_useful_count: int = 0,
    superseded_count: int = 0,
) -> dict[str, Any]:
    support_quality_counts = support_quality_counts if isinstance(support_quality_counts, dict) else {}
    posture_counts = posture_counts if isinstance(posture_counts, dict) else {}
    decision_useful_count = int(support_quality_counts.get("decision_useful_count") or 0)
    limited_count = int(support_quality_counts.get("limited_count") or 0)
    context_limited_count = int(support_quality_counts.get("context_limited_count") or 0)
    weak_count = int(support_quality_counts.get("weak_count") or 0)
    governing_count = int(posture_counts.get("governing_count") or 0)
    accepted_limited_count = int(posture_counts.get("accepted_limited_count") or 0)
    tentative_count = int(posture_counts.get("tentative_count") or 0)

    contradiction_pressure_count = max(0, weakened_count) + max(0, unresolved_count)
    limited_or_tentative_count = accepted_limited_count + tentative_count + context_limited_count + weak_count
    contested_flag = active_count > 0 and (
        contradiction_pressure_count > 0
        or (governing_count > 0 and limited_or_tentative_count > 0)
        or (strengthened_count > 0 and weakened_count > 0)
    )
    historical_stronger_than_current_flag = historical_decision_useful_count > 0 and (
        governing_count <= 0
        or decision_useful_count < historical_decision_useful_count
    )
    degraded_flag = active_count > 0 and (
        weakened_count > 0
        or historical_stronger_than_current_flag
        or (governing_count <= 0 and accepted_count > 0 and accepted_limited_count > 0)
    )
    if active_count <= 0:
        if historical_decision_useful_count > 0 or superseded_count > 0:
            coherence_label = SUPPORT_COHERENCE_HISTORICAL_STRONGER
            coherence_summary = (
                "No coherent current support governs present posture; historically stronger support remains visible, but only as context."
            )
        else:
            coherence_label = SUPPORT_COHERENCE_NONE
            coherence_summary = "No coherent current support is recorded yet for this posture."
    elif contested_flag and degraded_flag:
        coherence_label = SUPPORT_COHERENCE_CONTESTED_DEGRADED
        coherence_summary = (
            "Current support is both contested and degraded: mixed or weakening updates reduce how strongly it should shape present posture."
        )
    elif degraded_flag:
        coherence_label = SUPPORT_COHERENCE_DEGRADED
        coherence_summary = (
            "Current posture is degraded: active support still exists, but weakening evidence or stronger historical context reduces present decision strength."
        )
    elif contested_flag:
        coherence_label = SUPPORT_COHERENCE_CONTESTED
        coherence_summary = (
            "Current support is contested: mixed active updates add contradiction pressure, so present posture should remain more cautious."
        )
    elif governing_count > 0 and limited_or_tentative_count <= 0 and weakened_count <= 0 and unresolved_count <= 0:
        coherence_label = SUPPORT_COHERENCE_COHERENT
        coherence_summary = (
            "Current support is coherent enough to help govern present posture under the available evidence."
        )
    elif accepted_limited_count > 0 or tentative_count > 0 or limited_count > 0 or context_limited_count > 0:
        coherence_label = SUPPORT_COHERENCE_MIXED
        coherence_summary = (
            "Current support is active but mixed across stronger, limited, or tentative updates, so present posture should stay bounded."
        )
    else:
        coherence_label = SUPPORT_COHERENCE_NONE
        coherence_summary = (
            "Current support records exist, but they do not add up to a coherent present posture yet."
        )

    weakly_reusable_count = limited_or_tentative_count + contradiction_pressure_count
    if active_count <= 0:
        if historical_decision_useful_count > 0 or superseded_count > 0:
            reuse_label = SUPPORT_REUSE_HISTORICAL_ONLY
            reuse_summary = (
                "Support remains historically informative, but it should not be treated as current governed reuse."
            )
        else:
            reuse_label = SUPPORT_REUSE_NOT_READY
            reuse_summary = (
                "Current support is not yet suitable for strong governed reuse because a coherent active support picture is absent."
            )
    elif coherence_label == SUPPORT_COHERENCE_COHERENT and governing_count > 0:
        reuse_label = SUPPORT_REUSE_STRONG
        reuse_summary = (
            "Current support is coherent and posture-governing enough to be the cleanest basis for future bounded governed reuse."
        )
    elif contested_flag or degraded_flag:
        reuse_label = SUPPORT_REUSE_CONTRADICTION_LIMITED
        reuse_summary = (
            "Current support should be reused only with contradiction caution because mixed or weakening evidence reduces how cleanly it carries forward."
        )
    elif weakly_reusable_count > 0:
        reuse_label = SUPPORT_REUSE_WEAK
        reuse_summary = (
            "Current support remains only weakly reusable because limited, tentative, or context-limited updates still dominate the active picture."
        )
    else:
        reuse_label = SUPPORT_REUSE_SELECTIVE
        reuse_summary = (
            "Current support can be reused selectively, but the present evidence picture is still bounded rather than cleanly strong."
        )

    return {
        "support_coherence_label": coherence_label,
        "support_coherence_summary": coherence_summary,
        "support_reuse_label": reuse_label,
        "support_reuse_summary": reuse_summary,
        "current_support_contested_flag": contested_flag,
        "current_posture_degraded_flag": degraded_flag,
        "historical_support_stronger_than_current_flag": historical_stronger_than_current_flag,
        "contradiction_pressure_count": contradiction_pressure_count,
        "weakly_reusable_support_count": weakly_reusable_count,
    }


def assess_broader_reuse_posture(
    *,
    active_support_count: int,
    continuity_evidence_count: int,
    governing_continuity_count: int = 0,
    tentative_continuity_count: int = 0,
    contested_continuity_count: int = 0,
    historical_continuity_count: int = 0,
    current_support_reuse_label: str = "",
    contested_flag: bool = False,
    degraded_flag: bool = False,
    historical_stronger_flag: bool = False,
) -> dict[str, str]:
    continuity_evidence_count = max(0, int(continuity_evidence_count))
    governing_continuity_count = max(0, int(governing_continuity_count))
    tentative_continuity_count = max(0, int(tentative_continuity_count))
    contested_continuity_count = max(0, int(contested_continuity_count))
    historical_continuity_count = max(0, int(historical_continuity_count))
    active_support_count = max(0, int(active_support_count))
    current_support_reuse_label = _clean_text(current_support_reuse_label)

    if continuity_evidence_count <= 0:
        broader_continuity_label = BROADER_CONTINUITY_NONE
    elif contested_flag or degraded_flag or contested_continuity_count > 0:
        broader_continuity_label = BROADER_CONTINUITY_CONTESTED
    elif (
        governing_continuity_count > 0
        and tentative_continuity_count <= 0
        and historical_continuity_count <= 0
        and contested_continuity_count <= 0
    ):
        broader_continuity_label = BROADER_CONTINUITY_COHERENT
    elif (
        historical_continuity_count > 0
        and governing_continuity_count <= 0
        and tentative_continuity_count <= 0
        and contested_continuity_count <= 0
    ):
        broader_continuity_label = BROADER_CONTINUITY_HISTORICAL
    else:
        broader_continuity_label = BROADER_CONTINUITY_SELECTIVE

    if active_support_count <= 0:
        if historical_continuity_count > 0 or historical_stronger_flag:
            broader_reuse_label = BROADER_REUSE_HISTORICAL_ONLY
        else:
            broader_reuse_label = BROADER_REUSE_LOCAL_ONLY
    elif (
        contested_flag
        or degraded_flag
        or contested_continuity_count > 0
        or current_support_reuse_label == SUPPORT_REUSE_CONTRADICTION_LIMITED
    ):
        broader_reuse_label = BROADER_REUSE_CONTRADICTION_LIMITED
    elif (
        broader_continuity_label == BROADER_CONTINUITY_COHERENT
        and governing_continuity_count > 0
        and current_support_reuse_label == SUPPORT_REUSE_STRONG
        and not historical_stronger_flag
    ):
        broader_reuse_label = BROADER_REUSE_STRONG
    elif continuity_evidence_count > 0:
        if broader_continuity_label == BROADER_CONTINUITY_HISTORICAL and historical_stronger_flag:
            broader_reuse_label = BROADER_REUSE_HISTORICAL_ONLY
        else:
            broader_reuse_label = BROADER_REUSE_SELECTIVE
    elif current_support_reuse_label == SUPPORT_REUSE_HISTORICAL_ONLY or historical_stronger_flag:
        broader_reuse_label = BROADER_REUSE_HISTORICAL_ONLY
    else:
        broader_reuse_label = BROADER_REUSE_LOCAL_ONLY

    if broader_reuse_label == BROADER_REUSE_STRONG:
        future_reuse_candidacy_label = FUTURE_REUSE_CANDIDACY_STRONG
    elif broader_reuse_label == BROADER_REUSE_SELECTIVE:
        future_reuse_candidacy_label = FUTURE_REUSE_CANDIDACY_SELECTIVE
    elif broader_reuse_label == BROADER_REUSE_CONTRADICTION_LIMITED:
        future_reuse_candidacy_label = FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED
    elif broader_reuse_label == BROADER_REUSE_HISTORICAL_ONLY:
        future_reuse_candidacy_label = FUTURE_REUSE_CANDIDACY_HISTORICAL_ONLY
    else:
        future_reuse_candidacy_label = FUTURE_REUSE_CANDIDACY_LOCAL_ONLY

    return {
        "broader_reuse_label": broader_reuse_label,
        "broader_continuity_label": broader_continuity_label,
        "future_reuse_candidacy_label": future_reuse_candidacy_label,
    }


def assess_continuity_cluster_promotion(
    *,
    active_support_count: int,
    continuity_evidence_count: int,
    governing_continuity_count: int = 0,
    tentative_continuity_count: int = 0,
    contested_continuity_count: int = 0,
    historical_continuity_count: int = 0,
    broader_reuse_label: str = "",
    broader_continuity_label: str = "",
    future_reuse_candidacy_label: str = "",
    contested_flag: bool = False,
    degraded_flag: bool = False,
    historical_stronger_flag: bool = False,
) -> dict[str, str]:
    active_support_count = max(0, int(active_support_count))
    continuity_evidence_count = max(0, int(continuity_evidence_count))
    governing_continuity_count = max(0, int(governing_continuity_count))
    tentative_continuity_count = max(0, int(tentative_continuity_count))
    contested_continuity_count = max(0, int(contested_continuity_count))
    historical_continuity_count = max(0, int(historical_continuity_count))
    broader_reuse_label = _clean_text(broader_reuse_label)
    broader_continuity_label = _clean_text(broader_continuity_label)
    future_reuse_candidacy_label = _clean_text(future_reuse_candidacy_label)

    if continuity_evidence_count <= 0:
        continuity_cluster_posture_label = CONTINUITY_CLUSTER_LOCAL_ONLY
        promotion_candidate_posture_label = PROMOTION_CANDIDATE_CONTEXT_ONLY
    elif (
        contested_flag
        or degraded_flag
        or contested_continuity_count > 0
        or broader_reuse_label == BROADER_REUSE_CONTRADICTION_LIMITED
        or broader_continuity_label == BROADER_CONTINUITY_CONTESTED
        or future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED
    ):
        continuity_cluster_posture_label = CONTINUITY_CLUSTER_CONTRADICTION_LIMITED
        promotion_candidate_posture_label = PROMOTION_CANDIDATE_CONTRADICTION_LIMITED
    elif (
        broader_continuity_label == BROADER_CONTINUITY_HISTORICAL
        or (
            historical_continuity_count > 0
            and governing_continuity_count <= 0
            and tentative_continuity_count <= 0
        )
        or (historical_stronger_flag and governing_continuity_count <= 0)
    ):
        continuity_cluster_posture_label = CONTINUITY_CLUSTER_HISTORICAL
        promotion_candidate_posture_label = PROMOTION_CANDIDATE_HISTORICAL_ONLY
    elif (
        active_support_count > 0
        and governing_continuity_count > 0
        and broader_reuse_label == BROADER_REUSE_STRONG
        and broader_continuity_label == BROADER_CONTINUITY_COHERENT
        and future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_STRONG
        and not historical_stronger_flag
    ):
        continuity_cluster_posture_label = CONTINUITY_CLUSTER_PROMOTION_CANDIDATE
        promotion_candidate_posture_label = PROMOTION_CANDIDATE_STRONG
    elif (
        active_support_count > 0
        and continuity_evidence_count > 0
        and (
            broader_reuse_label == BROADER_REUSE_SELECTIVE
            or broader_continuity_label == BROADER_CONTINUITY_SELECTIVE
            or future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_SELECTIVE
        )
        and governing_continuity_count > 0
    ):
        continuity_cluster_posture_label = CONTINUITY_CLUSTER_SELECTIVE
        promotion_candidate_posture_label = PROMOTION_CANDIDATE_SELECTIVE
    else:
        continuity_cluster_posture_label = CONTINUITY_CLUSTER_CONTEXT_ONLY
        promotion_candidate_posture_label = PROMOTION_CANDIDATE_CONTEXT_ONLY

    return {
        "continuity_cluster_posture_label": continuity_cluster_posture_label,
        "promotion_candidate_posture_label": promotion_candidate_posture_label,
    }


def assess_governed_promotion_boundary(
    *,
    active_support_count: int,
    continuity_evidence_count: int,
    governing_continuity_count: int = 0,
    tentative_continuity_count: int = 0,
    contested_continuity_count: int = 0,
    historical_continuity_count: int = 0,
    broader_reuse_label: str = "",
    broader_continuity_label: str = "",
    continuity_cluster_posture_label: str = "",
    promotion_candidate_posture_label: str = "",
    contested_flag: bool = False,
    degraded_flag: bool = False,
    historical_stronger_flag: bool = False,
) -> dict[str, str]:
    active_support_count = max(0, int(active_support_count))
    continuity_evidence_count = max(0, int(continuity_evidence_count))
    governing_continuity_count = max(0, int(governing_continuity_count))
    tentative_continuity_count = max(0, int(tentative_continuity_count))
    contested_continuity_count = max(0, int(contested_continuity_count))
    historical_continuity_count = max(0, int(historical_continuity_count))
    broader_reuse_label = _clean_text(broader_reuse_label)
    broader_continuity_label = _clean_text(broader_continuity_label)
    continuity_cluster_posture_label = _clean_text(continuity_cluster_posture_label)
    promotion_candidate_posture_label = _clean_text(promotion_candidate_posture_label)

    if continuity_evidence_count <= 0 or continuity_cluster_posture_label == CONTINUITY_CLUSTER_LOCAL_ONLY:
        promotion_stability_label = PROMOTION_STABILITY_INSUFFICIENT
        promotion_gate_status_label = PROMOTION_GATE_NOT_CANDIDATE
        promotion_block_reason_label = PROMOTION_BLOCK_LOCAL_ONLY
    elif (
        continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTEXT_ONLY
        or promotion_candidate_posture_label == PROMOTION_CANDIDATE_CONTEXT_ONLY
    ):
        promotion_stability_label = PROMOTION_STABILITY_INSUFFICIENT
        promotion_gate_status_label = PROMOTION_GATE_NOT_CANDIDATE
        promotion_block_reason_label = PROMOTION_BLOCK_CONTEXT_ONLY
    elif (
        contested_flag
        and degraded_flag
        and (
            continuity_cluster_posture_label in {
                CONTINUITY_CLUSTER_PROMOTION_CANDIDATE,
                CONTINUITY_CLUSTER_SELECTIVE,
                CONTINUITY_CLUSTER_CONTRADICTION_LIMITED,
            }
            or promotion_candidate_posture_label
            in {
                PROMOTION_CANDIDATE_STRONG,
                PROMOTION_CANDIDATE_SELECTIVE,
                PROMOTION_CANDIDATE_CONTRADICTION_LIMITED,
            }
        )
    ):
        promotion_stability_label = PROMOTION_STABILITY_UNSTABLE
        promotion_gate_status_label = PROMOTION_GATE_QUARANTINED
        promotion_block_reason_label = PROMOTION_BLOCK_QUARANTINED
    elif historical_stronger_flag and promotion_candidate_posture_label in {
        PROMOTION_CANDIDATE_STRONG,
        PROMOTION_CANDIDATE_SELECTIVE,
    }:
        promotion_stability_label = (
            PROMOTION_STABILITY_HISTORICAL
            if broader_continuity_label == BROADER_CONTINUITY_HISTORICAL or historical_continuity_count > 0
            else PROMOTION_STABILITY_UNSTABLE
        )
        promotion_gate_status_label = PROMOTION_GATE_DOWNGRADED
        promotion_block_reason_label = PROMOTION_BLOCK_DOWNGRADED
    elif degraded_flag and promotion_candidate_posture_label == PROMOTION_CANDIDATE_STRONG:
        promotion_stability_label = PROMOTION_STABILITY_UNSTABLE
        promotion_gate_status_label = PROMOTION_GATE_DOWNGRADED
        promotion_block_reason_label = PROMOTION_BLOCK_DEGRADED
    elif (
        contested_flag
        or contested_continuity_count > 0
        or broader_reuse_label == BROADER_REUSE_CONTRADICTION_LIMITED
        or promotion_candidate_posture_label == PROMOTION_CANDIDATE_CONTRADICTION_LIMITED
        or continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTRADICTION_LIMITED
    ):
        promotion_stability_label = PROMOTION_STABILITY_UNSTABLE
        promotion_gate_status_label = PROMOTION_GATE_BLOCKED
        promotion_block_reason_label = PROMOTION_BLOCK_CONTRADICTION
    elif (
        broader_continuity_label == BROADER_CONTINUITY_HISTORICAL
        or promotion_candidate_posture_label == PROMOTION_CANDIDATE_HISTORICAL_ONLY
        or continuity_cluster_posture_label == CONTINUITY_CLUSTER_HISTORICAL
        or (
            historical_continuity_count > 0
            and governing_continuity_count <= 0
            and tentative_continuity_count <= 0
        )
    ):
        promotion_stability_label = PROMOTION_STABILITY_HISTORICAL
        promotion_gate_status_label = PROMOTION_GATE_BLOCKED
        promotion_block_reason_label = PROMOTION_BLOCK_HISTORICAL
    elif (
        promotion_candidate_posture_label == PROMOTION_CANDIDATE_STRONG
        and continuity_cluster_posture_label == CONTINUITY_CLUSTER_PROMOTION_CANDIDATE
        and broader_reuse_label == BROADER_REUSE_STRONG
        and broader_continuity_label == BROADER_CONTINUITY_COHERENT
        and active_support_count > 0
        and governing_continuity_count > 0
        and not tentative_continuity_count
        and not historical_continuity_count
    ):
        promotion_stability_label = PROMOTION_STABILITY_STABLE
        promotion_gate_status_label = PROMOTION_GATE_PROMOTABLE
        promotion_block_reason_label = PROMOTION_BLOCK_NONE
    elif (
        promotion_candidate_posture_label in {PROMOTION_CANDIDATE_STRONG, PROMOTION_CANDIDATE_SELECTIVE}
        and continuity_cluster_posture_label in {
            CONTINUITY_CLUSTER_PROMOTION_CANDIDATE,
            CONTINUITY_CLUSTER_SELECTIVE,
        }
        and active_support_count > 0
        and governing_continuity_count > 0
    ):
        promotion_stability_label = PROMOTION_STABILITY_SELECTIVE
        promotion_gate_status_label = PROMOTION_GATE_SELECTIVE
        promotion_block_reason_label = PROMOTION_BLOCK_SELECTIVE_ONLY
    elif promotion_candidate_posture_label in {
        PROMOTION_CANDIDATE_STRONG,
        PROMOTION_CANDIDATE_SELECTIVE,
        PROMOTION_CANDIDATE_CONTRADICTION_LIMITED,
        PROMOTION_CANDIDATE_HISTORICAL_ONLY,
    }:
        promotion_stability_label = PROMOTION_STABILITY_INSUFFICIENT
        promotion_gate_status_label = PROMOTION_GATE_BLOCKED
        promotion_block_reason_label = PROMOTION_BLOCK_STABILITY
    else:
        promotion_stability_label = PROMOTION_STABILITY_INSUFFICIENT
        promotion_gate_status_label = PROMOTION_GATE_NOT_CANDIDATE
        promotion_block_reason_label = PROMOTION_BLOCK_CONTEXT_ONLY

    return {
        "promotion_stability_label": promotion_stability_label,
        "promotion_gate_status_label": promotion_gate_status_label,
        "promotion_block_reason_label": promotion_block_reason_label,
    }


__all__ = [
    "RESULT_CONTEXT_LIMITATION_ALIGNED",
    "RESULT_CONTEXT_LIMITATION_ASSAY",
    "RESULT_CONTEXT_LIMITATION_NONE",
    "RESULT_CONTEXT_LIMITATION_UNIT",
    "RESULT_DECISION_USEFUL_CLARIFY",
    "RESULT_DECISION_USEFUL_FOLLOW_UP",
    "RESULT_DECISION_USEFUL_GATHER",
    "RESULT_SUPPORT_QUALITY_CAUTION",
    "RESULT_SUPPORT_QUALITY_CONTEXT_LIMITED",
    "RESULT_SUPPORT_QUALITY_LIMITED_NUMERIC",
    "RESULT_SUPPORT_QUALITY_STRONG",
    "RESULT_SUPPORT_QUALITY_UNRESOLVED",
    "SUPPORT_DECISION_USEFUL_CLARIFY",
    "SUPPORT_DECISION_USEFUL_FOLLOW_UP",
    "SUPPORT_DECISION_USEFUL_GATHER",
    "GOVERNED_SUPPORT_POSTURE_ACCEPTED_LIMITED",
    "GOVERNED_SUPPORT_POSTURE_GOVERNING",
    "GOVERNED_SUPPORT_POSTURE_HISTORICAL",
    "GOVERNED_SUPPORT_POSTURE_INACTIVE",
    "GOVERNED_SUPPORT_POSTURE_TENTATIVE",
    "SUPPORT_QUALITY_ACTIVE_LIMITED",
    "SUPPORT_QUALITY_CONTEXT_LIMITED",
    "SUPPORT_QUALITY_DECISION_USEFUL",
    "SUPPORT_QUALITY_WEAK",
    "classify_belief_update_support_quality",
    "classify_belief_update_contradiction_role",
    "classify_governed_support_posture",
    "classify_result_context_limitation",
    "classify_result_support_quality",
    "assess_support_coherence",
    "governed_support_posture_bucket_for_label",
    "quality_bucket_for_label",
    "rollup_governed_support_postures",
    "rollup_quality_labels",
    "SUPPORT_COHERENCE_COHERENT",
    "SUPPORT_COHERENCE_CONTESTED",
    "SUPPORT_COHERENCE_CONTESTED_DEGRADED",
    "SUPPORT_COHERENCE_DEGRADED",
    "SUPPORT_COHERENCE_HISTORICAL_STRONGER",
    "SUPPORT_COHERENCE_MIXED",
    "SUPPORT_COHERENCE_NONE",
    "SUPPORT_REUSE_CONTRADICTION_LIMITED",
    "SUPPORT_REUSE_HISTORICAL_ONLY",
    "SUPPORT_REUSE_NOT_READY",
    "SUPPORT_REUSE_SELECTIVE",
    "SUPPORT_REUSE_STRONG",
    "SUPPORT_REUSE_WEAK",
    "BROADER_CONTINUITY_COHERENT",
    "BROADER_CONTINUITY_CONTESTED",
    "BROADER_CONTINUITY_HISTORICAL",
    "BROADER_CONTINUITY_NONE",
    "BROADER_CONTINUITY_SELECTIVE",
    "BROADER_REUSE_CONTRADICTION_LIMITED",
    "BROADER_REUSE_HISTORICAL_ONLY",
    "BROADER_REUSE_LOCAL_ONLY",
    "BROADER_REUSE_SELECTIVE",
    "BROADER_REUSE_STRONG",
    "FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED",
    "FUTURE_REUSE_CANDIDACY_HISTORICAL_ONLY",
    "FUTURE_REUSE_CANDIDACY_LOCAL_ONLY",
    "FUTURE_REUSE_CANDIDACY_SELECTIVE",
    "FUTURE_REUSE_CANDIDACY_STRONG",
    "CONTINUITY_CLUSTER_PROMOTION_CANDIDATE",
    "CONTINUITY_CLUSTER_SELECTIVE",
    "CONTINUITY_CLUSTER_CONTEXT_ONLY",
    "CONTINUITY_CLUSTER_CONTRADICTION_LIMITED",
    "CONTINUITY_CLUSTER_HISTORICAL",
    "CONTINUITY_CLUSTER_LOCAL_ONLY",
    "PROMOTION_CANDIDATE_STRONG",
    "PROMOTION_CANDIDATE_SELECTIVE",
    "PROMOTION_CANDIDATE_CONTRADICTION_LIMITED",
    "PROMOTION_CANDIDATE_HISTORICAL_ONLY",
    "PROMOTION_CANDIDATE_CONTEXT_ONLY",
    "PROMOTION_STABILITY_STABLE",
    "PROMOTION_STABILITY_SELECTIVE",
    "PROMOTION_STABILITY_UNSTABLE",
    "PROMOTION_STABILITY_HISTORICAL",
    "PROMOTION_STABILITY_INSUFFICIENT",
    "PROMOTION_GATE_NOT_CANDIDATE",
    "PROMOTION_GATE_BLOCKED",
    "PROMOTION_GATE_SELECTIVE",
    "PROMOTION_GATE_PROMOTABLE",
    "PROMOTION_GATE_DOWNGRADED",
    "PROMOTION_GATE_QUARANTINED",
    "PROMOTION_BLOCK_NONE",
    "PROMOTION_BLOCK_LOCAL_ONLY",
    "PROMOTION_BLOCK_CONTEXT_ONLY",
    "PROMOTION_BLOCK_SELECTIVE_ONLY",
    "PROMOTION_BLOCK_CONTRADICTION",
    "PROMOTION_BLOCK_DEGRADED",
    "PROMOTION_BLOCK_HISTORICAL",
    "PROMOTION_BLOCK_STABILITY",
    "PROMOTION_BLOCK_DOWNGRADED",
    "PROMOTION_BLOCK_QUARANTINED",
    "SOURCE_CLASS_CURATED",
    "SOURCE_CLASS_INTERNAL_GOVERNED",
    "SOURCE_CLASS_AFFILIATED",
    "SOURCE_CLASS_UNCONTROLLED_UPLOAD",
    "SOURCE_CLASS_DERIVED_EXTRACTED",
    "SOURCE_CLASS_AI_DERIVED",
    "SOURCE_CLASS_UNKNOWN",
    "PROVENANCE_CONFIDENCE_STRONG",
    "PROVENANCE_CONFIDENCE_MODERATE",
    "PROVENANCE_CONFIDENCE_WEAK",
    "PROVENANCE_CONFIDENCE_UNKNOWN",
    "TRUST_TIER_LOCAL_ONLY",
    "TRUST_TIER_CANDIDATE",
    "TRUST_TIER_GOVERNED",
    "REVIEW_STATUS_NOT_REVIEWED",
    "REVIEW_STATUS_CANDIDATE",
    "REVIEW_STATUS_APPROVED",
    "REVIEW_STATUS_BLOCKED",
    "REVIEW_STATUS_DEFERRED",
    "REVIEW_STATUS_DOWNGRADED",
    "REVIEW_STATUS_QUARANTINED",
    "REVIEW_REASON_LOCAL_DEFAULT",
    "REVIEW_REASON_WEAK_PROVENANCE",
    "REVIEW_REASON_UNCONTROLLED_SOURCE",
    "REVIEW_REASON_STRONGER_TRUST_NEEDED",
    "REVIEW_REASON_APPROVED",
    "REVIEW_REASON_CONTRADICTION",
    "REVIEW_REASON_DEGRADED",
    "REVIEW_REASON_HISTORICAL",
    "REVIEW_REASON_DOWNGRADED",
    "REVIEW_REASON_QUARANTINED",
    "REVIEW_REASON_SELECTIVE",
    "classify_evidence_source_class",
    "assess_provenance_confidence",
    "rollup_provenance_confidence",
    "assess_governed_evidence_posture",
    "assess_broader_reuse_posture",
    "assess_continuity_cluster_promotion",
    "assess_governed_promotion_boundary",
]
