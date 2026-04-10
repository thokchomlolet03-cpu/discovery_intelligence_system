from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from system.contracts import validate_governed_review_record
from system.db.repositories import GovernedReviewRepository
from system.services.support_quality_service import (
    BROADER_CONTINUITY_COHERENT,
    BROADER_CONTINUITY_CONTESTED,
    BROADER_CONTINUITY_HISTORICAL,
    BROADER_REUSE_CONTRADICTION_LIMITED,
    BROADER_REUSE_HISTORICAL_ONLY,
    BROADER_REUSE_LOCAL_ONLY,
    BROADER_REUSE_SELECTIVE,
    BROADER_REUSE_STRONG,
    CONTINUITY_CLUSTER_CONTEXT_ONLY,
    CONTINUITY_CLUSTER_CONTRADICTION_LIMITED,
    CONTINUITY_CLUSTER_HISTORICAL,
    CONTINUITY_CLUSTER_LOCAL_ONLY,
    CONTINUITY_CLUSTER_PROMOTION_CANDIDATE,
    CONTINUITY_CLUSTER_SELECTIVE,
    FUTURE_REUSE_CANDIDACY_LOCAL_ONLY,
    FUTURE_REUSE_CANDIDACY_SELECTIVE,
    FUTURE_REUSE_CANDIDACY_STRONG,
    GOVERNED_SUPPORT_POSTURE_GOVERNING,
    PROMOTION_BLOCK_CONTRADICTION,
    PROMOTION_BLOCK_DEGRADED,
    PROMOTION_BLOCK_HISTORICAL,
    PROMOTION_GATE_BLOCKED,
    PROMOTION_GATE_DOWNGRADED,
    PROMOTION_GATE_NOT_CANDIDATE,
    PROMOTION_GATE_PROMOTABLE,
    PROMOTION_GATE_QUARANTINED,
    PROMOTION_GATE_SELECTIVE,
    PROVENANCE_CONFIDENCE_MODERATE,
    PROVENANCE_CONFIDENCE_STRONG,
    PROVENANCE_CONFIDENCE_UNKNOWN,
    PROVENANCE_CONFIDENCE_WEAK,
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
    SOURCE_CLASS_AI_DERIVED,
    SOURCE_CLASS_UNCONTROLLED_UPLOAD,
    SOURCE_CLASS_UNKNOWN,
    SUPPORT_QUALITY_DECISION_USEFUL,
    TRUST_TIER_CANDIDATE,
    TRUST_TIER_GOVERNED,
    TRUST_TIER_LOCAL_ONLY,
    assess_governed_evidence_posture,
)


SUBJECT_TYPE_CLAIM = "claim"
SUBJECT_TYPE_BELIEF_STATE = "belief_state"
SUBJECT_TYPE_CONTINUITY_CLUSTER = "continuity_cluster"
SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER = "session_family_carryover"

governed_review_repository = GovernedReviewRepository()


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


def _latest_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for record in records:
        if not isinstance(record, dict):
            continue
        if latest is None:
            latest = record
            continue
        current_at = str(record.get("recorded_at") or "")
        latest_at = str(latest.get("recorded_at") or "")
        if current_at >= latest_at:
            latest = record
    return latest


def _decision_outcome(
    *,
    trust_tier_label: str,
    review_status_label: str,
    promotion_gate_status_label: str,
) -> str:
    review_status = _clean_text(review_status_label).lower()
    promotion_gate = _clean_text(promotion_gate_status_label).lower()
    trust_tier = _clean_text(trust_tier_label).lower()
    if "quarantined" in review_status or "quarantined" in promotion_gate:
        return "quarantined"
    if "downgraded" in review_status or "downgraded" in promotion_gate:
        return "downgraded"
    if "blocked" in review_status:
        return "blocked"
    if "deferred" in review_status:
        return "deferred"
    if "approved" in review_status:
        return "approved"
    if "candidate" in review_status or "candidate" in trust_tier:
        return "candidate"
    return "local_only"


def _json_signature(value: Any) -> str:
    try:
        return json.dumps(value or {}, sort_keys=True, default=str)
    except TypeError:
        return json.dumps({}, sort_keys=True)


def _stronger_provenance(label: Any) -> bool:
    return _clean_text(label) in {PROVENANCE_CONFIDENCE_STRONG, PROVENANCE_CONFIDENCE_MODERATE}


def _weak_provenance(label: Any) -> bool:
    return _clean_text(label) in {PROVENANCE_CONFIDENCE_WEAK, PROVENANCE_CONFIDENCE_UNKNOWN}


def _uncontrolled_source(label: Any) -> bool:
    return _clean_text(label) in {
        SOURCE_CLASS_UNCONTROLLED_UPLOAD,
        SOURCE_CLASS_AI_DERIVED,
        SOURCE_CLASS_UNKNOWN,
    }


def _fallback_review_status_summary(
    *,
    layer_name: str,
    review_status_label: str,
    review_reason_label: str,
) -> str:
    if review_status_label == REVIEW_STATUS_APPROVED:
        return f"{layer_name} is approved for bounded broader carryover consideration."
    if review_status_label == REVIEW_STATUS_BLOCKED:
        return f"{layer_name} is currently blocked from stronger broader carryover."
    if review_status_label == REVIEW_STATUS_DEFERRED:
        return f"{layer_name} remains reviewable, but broader carryover is deferred under the current bounded rules."
    if review_status_label == REVIEW_STATUS_DOWNGRADED:
        return f"{layer_name} was downgraded from a stronger broader-carryover posture."
    if review_status_label == REVIEW_STATUS_QUARANTINED:
        return f"{layer_name} is quarantined from stronger broader influence right now."
    if review_status_label == REVIEW_STATUS_CANDIDATE:
        return f"{layer_name} is a review candidate for broader carryover, but not an approved broader state."
    if review_reason_label == REVIEW_REASON_LOCAL_DEFAULT:
        return f"{layer_name} remains local-only by default until broader carryover is earned."
    return f"{layer_name} does not yet have a stronger broader-carryover review posture."


def _fallback_review_reason_summary(
    *,
    layer_name: str,
    review_reason_label: str,
) -> str:
    if review_reason_label == REVIEW_REASON_APPROVED:
        return f"{layer_name} currently has enough coherence, trust, provenance, and review support for bounded broader carryover."
    if review_reason_label == REVIEW_REASON_WEAK_PROVENANCE:
        return f"{layer_name} remains locally useful, but weak or unknown provenance keeps broader carryover blocked."
    if review_reason_label == REVIEW_REASON_UNCONTROLLED_SOURCE:
        return f"{layer_name} remains review-candidate material only because uncontrolled source basis keeps broader carryover cautious."
    if review_reason_label == REVIEW_REASON_CONTRADICTION:
        return f"{layer_name} is blocked because contradiction-heavy history weakens broader carryover too sharply."
    if review_reason_label == REVIEW_REASON_DEGRADED:
        return f"{layer_name} is blocked because degraded present posture makes broader carryover unsafe to strengthen."
    if review_reason_label == REVIEW_REASON_HISTORICAL:
        return f"{layer_name} is mainly historical context rather than a stably current broader-carryover basis."
    if review_reason_label == REVIEW_REASON_DOWNGRADED:
        return f"Newer weakening evidence reduced the earlier broader-carryover posture for {layer_name.lower()}."
    if review_reason_label == REVIEW_REASON_QUARANTINED:
        return f"{layer_name} is quarantined because instability or contradiction pressure makes stronger broader influence unsafe."
    if review_reason_label == REVIEW_REASON_SELECTIVE:
        return f"{layer_name} remains selectively useful, but still too bounded for cleaner broader carryover."
    if review_reason_label == REVIEW_REASON_LOCAL_DEFAULT:
        return f"{layer_name} remains local-only by default until stronger broader-review conditions are satisfied."
    return f"Stronger trust, provenance, or continuity would still be needed before {layer_name.lower()} should travel further."


def _decision_summary_for_layer(
    *,
    layer_name: str,
    trust_tier_label: str,
    review_status_label: str,
    review_reason_summary: str,
) -> str:
    trust_phrase = _clean_text(trust_tier_label, default=TRUST_TIER_LOCAL_ONLY).lower()
    if review_status_label == REVIEW_STATUS_APPROVED:
        return f"{layer_name} is approved for bounded broader carryover under {trust_phrase}. {review_reason_summary}"
    if review_status_label == REVIEW_STATUS_BLOCKED:
        return f"{layer_name} is blocked from stronger broader carryover under {trust_phrase}. {review_reason_summary}"
    if review_status_label == REVIEW_STATUS_DEFERRED:
        return f"{layer_name} remains deferred for broader carryover under {trust_phrase}. {review_reason_summary}"
    if review_status_label == REVIEW_STATUS_DOWNGRADED:
        return f"{layer_name} was downgraded from a stronger broader-carryover posture. {review_reason_summary}"
    if review_status_label == REVIEW_STATUS_QUARANTINED:
        return f"{layer_name} is quarantined from stronger broader influence. {review_reason_summary}"
    if review_status_label == REVIEW_STATUS_CANDIDATE:
        return f"{layer_name} is a broader-carryover review candidate under {trust_phrase}. {review_reason_summary}"
    return f"{layer_name} remains local-only by default. {review_reason_summary}"


def _compose_layer_review_posture(
    *,
    layer_name: str,
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
    allow_approval: bool = False,
    local_only_reason: str = "",
    selective_reason: str = "",
    contradiction_reason: str = "",
    degraded_reason: str = "",
    historical_reason: str = "",
    default_reason: str = "",
) -> dict[str, str]:
    posture = assess_governed_evidence_posture(
        source_class_label=source_class_label,
        provenance_confidence_label=provenance_confidence_label,
        promotion_gate_status_label=promotion_gate_status_label,
        promotion_block_reason_label=promotion_block_reason_label,
        active_support_count=active_support_count,
        accepted_support_count=accepted_support_count,
        candidate_context=candidate_context,
        contested_flag=contested_flag,
        degraded_flag=degraded_flag,
        historical_stronger_flag=historical_stronger_flag,
        local_only_default=True,
    )

    trust_tier_label = _clean_text(posture.get("trust_tier_label"), default=TRUST_TIER_LOCAL_ONLY)
    trust_tier_summary = _clean_text(posture.get("trust_tier_summary"))
    review_status_label = _clean_text(posture.get("governed_review_status_label"), default=REVIEW_STATUS_NOT_REVIEWED)
    review_status_summary = _clean_text(posture.get("governed_review_status_summary"))
    review_reason_label = _clean_text(posture.get("governed_review_reason_label"), default=REVIEW_REASON_LOCAL_DEFAULT)
    review_reason_summary = _clean_text(posture.get("governed_review_reason_summary"))
    promotion_gate = _clean_text(promotion_gate_status_label)

    if promotion_gate == PROMOTION_GATE_PROMOTABLE and not allow_approval:
        trust_tier_label = TRUST_TIER_CANDIDATE if candidate_context else TRUST_TIER_LOCAL_ONLY
        trust_tier_summary = (
            f"{layer_name} looks locally coherent enough to review, but it has not earned approved broader carryover at this layer."
        )
        review_status_label = REVIEW_STATUS_DEFERRED if candidate_context else REVIEW_STATUS_NOT_REVIEWED
        review_reason_label = REVIEW_REASON_STRONGER_TRUST_NEEDED if candidate_context else REVIEW_REASON_LOCAL_DEFAULT
        review_status_summary = (
            f"{layer_name} remains deferred because stronger cross-layer coherence would still be needed before broader carryover should increase."
        )
        review_reason_summary = default_reason or (
            f"Claim-level or lower-layer strength is not enough on its own for {layer_name.lower()} to earn broader carryover."
        )

    if promotion_gate == PROMOTION_GATE_NOT_CANDIDATE and not candidate_context:
        trust_tier_label = TRUST_TIER_LOCAL_ONLY
        review_status_label = REVIEW_STATUS_NOT_REVIEWED
        review_reason_label = REVIEW_REASON_LOCAL_DEFAULT
        review_status_summary = (
            f"{layer_name} remains local-only by default because broader carryover is not yet a credible candidate at this layer."
        )
        review_reason_summary = local_only_reason or (
            f"{layer_name} can stay locally useful without being treated as a broader-carryover unit."
        )

    if review_status_label == REVIEW_STATUS_BLOCKED and review_reason_label == REVIEW_REASON_CONTRADICTION and contradiction_reason:
        review_reason_summary = contradiction_reason
    elif review_status_label == REVIEW_STATUS_BLOCKED and review_reason_label == REVIEW_REASON_DEGRADED and degraded_reason:
        review_reason_summary = degraded_reason
    elif review_status_label == REVIEW_STATUS_BLOCKED and review_reason_label == REVIEW_REASON_HISTORICAL and historical_reason:
        review_reason_summary = historical_reason
    elif review_status_label == REVIEW_STATUS_DEFERRED and review_reason_label == REVIEW_REASON_SELECTIVE and selective_reason:
        review_reason_summary = selective_reason
    elif review_status_label == REVIEW_STATUS_NOT_REVIEWED and review_reason_label == REVIEW_REASON_LOCAL_DEFAULT and local_only_reason:
        review_reason_summary = local_only_reason

    if not review_status_summary:
        review_status_summary = _fallback_review_status_summary(
            layer_name=layer_name,
            review_status_label=review_status_label,
            review_reason_label=review_reason_label,
        )
    if not review_reason_summary:
        review_reason_summary = _fallback_review_reason_summary(
            layer_name=layer_name,
            review_reason_label=review_reason_label,
        )
    if not trust_tier_summary:
        if trust_tier_label == TRUST_TIER_GOVERNED:
            trust_tier_summary = f"{layer_name} has earned the strongest bounded broader-carryover trust posture currently supported by the code."
        elif trust_tier_label == TRUST_TIER_CANDIDATE:
            trust_tier_summary = f"{layer_name} remains reviewable as a broader-carryover candidate, but not as governed-trusted carryover."
        else:
            trust_tier_summary = f"{layer_name} remains local-only by default."

    return {
        "trust_tier_label": trust_tier_label,
        "trust_tier_summary": trust_tier_summary,
        "governed_review_status_label": review_status_label,
        "governed_review_status_summary": review_status_summary,
        "governed_review_reason_label": review_reason_label,
        "governed_review_reason_summary": review_reason_summary,
        "decision_summary": _decision_summary_for_layer(
            layer_name=layer_name,
            trust_tier_label=trust_tier_label,
            review_status_label=review_status_label,
            review_reason_summary=review_reason_summary,
        ),
    }


def compose_belief_state_review_posture(
    *,
    source_class_label: Any = "",
    provenance_confidence_label: Any = "",
    support_quality_label: Any = "",
    governed_support_posture_label: Any = "",
    broader_target_reuse_label: Any = "",
    future_reuse_candidacy_label: Any = "",
    promotion_gate_status_label: Any = "",
    promotion_block_reason_label: Any = "",
    active_claim_count: int = 0,
    posture_governing_support_count: int = 0,
    active_but_limited_support_count: int = 0,
    context_limited_support_count: int = 0,
    weak_or_unresolved_support_count: int = 0,
    contested_flag: bool = False,
    degraded_flag: bool = False,
    historical_stronger_flag: bool = False,
) -> dict[str, str]:
    broader_reuse_label = _clean_text(broader_target_reuse_label)
    future_reuse_label = _clean_text(future_reuse_candidacy_label)
    support_quality = _clean_text(support_quality_label)
    governed_posture = _clean_text(governed_support_posture_label)
    weak_fragment_count = (
        _safe_int(active_but_limited_support_count)
        + _safe_int(context_limited_support_count)
        + _safe_int(weak_or_unresolved_support_count)
    )
    candidate_context = (
        broader_reuse_label != BROADER_REUSE_LOCAL_ONLY
        or future_reuse_label != FUTURE_REUSE_CANDIDACY_LOCAL_ONLY
        or _clean_text(promotion_gate_status_label) != PROMOTION_GATE_NOT_CANDIDATE
    )
    allow_approval = (
        _clean_text(promotion_gate_status_label) == PROMOTION_GATE_PROMOTABLE
        and support_quality == SUPPORT_QUALITY_DECISION_USEFUL
        and governed_posture == GOVERNED_SUPPORT_POSTURE_GOVERNING
        and _safe_int(posture_governing_support_count) > 0
        and not contested_flag
        and not degraded_flag
        and not historical_stronger_flag
        and broader_reuse_label == BROADER_REUSE_STRONG
        and _stronger_provenance(provenance_confidence_label)
        and not _uncontrolled_source(source_class_label)
    )
    posture = _compose_layer_review_posture(
        layer_name="Belief-state broader review",
        source_class_label=source_class_label,
        provenance_confidence_label=provenance_confidence_label,
        promotion_gate_status_label=promotion_gate_status_label,
        promotion_block_reason_label=promotion_block_reason_label,
        active_support_count=_safe_int(active_claim_count),
        accepted_support_count=_safe_int(posture_governing_support_count),
        candidate_context=candidate_context,
        contested_flag=contested_flag,
        degraded_flag=degraded_flag,
        historical_stronger_flag=historical_stronger_flag,
        allow_approval=allow_approval,
        local_only_reason=(
            "Belief-state posture can guide local review immediately, but broader carryover should not be inferred until stronger target-scoped coherence is earned."
        ),
        selective_reason=(
            "Belief-state posture is selectively reusable, but it remains too bounded for cleaner broader carryover at the target-scoped level."
        ),
        contradiction_reason=(
            "Belief-state broader carryover is blocked because contradiction-heavy active support weakens the current target-scoped picture."
        ),
        degraded_reason=(
            "Belief-state broader carryover is blocked because degraded present posture means earlier stronger support should not keep broader influence."
        ),
        historical_reason=(
            "Belief-state broader carryover remains historical-heavy, so older support stays visible as context rather than current broader influence."
        ),
        default_reason=(
            "Belief-state broader carryover requires stronger target-scoped coherence than claim-level trust alone."
        ),
    )
    if weak_fragment_count >= max(2, _safe_int(posture_governing_support_count) + 1) and _safe_int(posture_governing_support_count) <= 0:
        posture["carryover_guardrail_summary"] = (
            "Multiple weak or limited belief-state fragments do not simulate approved broader carryover. Broader carryover still depends on posture-governing support, coherence, provenance, and review."
        )
        if posture["governed_review_status_label"] in {REVIEW_STATUS_CANDIDATE, REVIEW_STATUS_NOT_REVIEWED}:
            posture["trust_tier_label"] = TRUST_TIER_CANDIDATE if candidate_context else TRUST_TIER_LOCAL_ONLY
            posture["governed_review_status_label"] = REVIEW_STATUS_DEFERRED if candidate_context else REVIEW_STATUS_NOT_REVIEWED
            posture["governed_review_reason_label"] = REVIEW_REASON_STRONGER_TRUST_NEEDED if candidate_context else REVIEW_REASON_LOCAL_DEFAULT
            posture["governed_review_status_summary"] = (
                "Belief-state broader review remains deferred because weak or limited multiplicity should not silently act like stronger broader carryover."
            )
            posture["governed_review_reason_summary"] = posture["carryover_guardrail_summary"]
            posture["decision_summary"] = _decision_summary_for_layer(
                layer_name="Belief-state broader review",
                trust_tier_label=posture["trust_tier_label"],
                review_status_label=posture["governed_review_status_label"],
                review_reason_summary=posture["governed_review_reason_summary"],
            )
    else:
        posture["carryover_guardrail_summary"] = (
            "Belief-state broader carryover depends on target-scoped coherence, trust, provenance, and review rather than on how many weak updates exist."
        )
    return posture


def compose_continuity_cluster_review_posture(
    *,
    source_class_label: Any = "",
    provenance_confidence_label: Any = "",
    broader_reuse_label: Any = "",
    broader_continuity_label: Any = "",
    future_reuse_candidacy_label: Any = "",
    continuity_cluster_posture_label: Any = "",
    promotion_gate_status_label: Any = "",
    promotion_block_reason_label: Any = "",
    continuity_evidence_count: int = 0,
    governing_continuity_count: int = 0,
    tentative_continuity_count: int = 0,
    contested_continuity_count: int = 0,
    historical_continuity_count: int = 0,
    contested_flag: bool = False,
    degraded_flag: bool = False,
    historical_stronger_flag: bool = False,
) -> dict[str, str]:
    cluster_label = _clean_text(continuity_cluster_posture_label)
    broader_label = _clean_text(broader_reuse_label)
    broader_continuity = _clean_text(broader_continuity_label)
    future_label = _clean_text(future_reuse_candidacy_label)
    candidate_context = (
        cluster_label not in {CONTINUITY_CLUSTER_LOCAL_ONLY, CONTINUITY_CLUSTER_CONTEXT_ONLY, ""}
        or future_label != FUTURE_REUSE_CANDIDACY_LOCAL_ONLY
        or _clean_text(promotion_gate_status_label) != PROMOTION_GATE_NOT_CANDIDATE
    )
    allow_approval = (
        cluster_label == CONTINUITY_CLUSTER_PROMOTION_CANDIDATE
        and broader_label == BROADER_REUSE_STRONG
        and broader_continuity == BROADER_CONTINUITY_COHERENT
        and _clean_text(promotion_gate_status_label) == PROMOTION_GATE_PROMOTABLE
        and _safe_int(governing_continuity_count) > 0
        and _safe_int(contested_continuity_count) <= 0
        and _safe_int(historical_continuity_count) <= 0
        and not contested_flag
        and not degraded_flag
        and not historical_stronger_flag
        and _stronger_provenance(provenance_confidence_label)
        and not _uncontrolled_source(source_class_label)
    )
    posture = _compose_layer_review_posture(
        layer_name="Continuity-cluster review",
        source_class_label=source_class_label,
        provenance_confidence_label=provenance_confidence_label,
        promotion_gate_status_label=promotion_gate_status_label,
        promotion_block_reason_label=promotion_block_reason_label,
        active_support_count=_safe_int(continuity_evidence_count),
        accepted_support_count=_safe_int(governing_continuity_count),
        candidate_context=candidate_context,
        contested_flag=contested_flag or _safe_int(contested_continuity_count) > 0,
        degraded_flag=degraded_flag,
        historical_stronger_flag=historical_stronger_flag or _safe_int(historical_continuity_count) > 0,
        allow_approval=allow_approval,
        local_only_reason=(
            "Continuity remains local or context-only right now, so the cluster should stay visible without behaving like approved broader carryover."
        ),
        selective_reason=(
            "Continuity remains selective only, so this cluster can inform bounded review without traveling as stronger broader carryover."
        ),
        contradiction_reason=(
            "Continuity-cluster broader carryover is blocked because contradiction-heavy continuity fragments should not be aggregated into a stronger broader state."
        ),
        degraded_reason=(
            "Continuity-cluster broader carryover is blocked because degraded present posture makes earlier stronger continuity unsafe to keep carrying forward."
        ),
        historical_reason=(
            "Continuity-cluster posture is historical-heavy, so it remains visible as context but not as approved broader carryover."
        ),
        default_reason=(
            "Continuity-cluster approval requires cleaner continuity than the presence of multiple related fragments alone."
        ),
    )
    if cluster_label in {CONTINUITY_CLUSTER_LOCAL_ONLY, CONTINUITY_CLUSTER_CONTEXT_ONLY} and _clean_text(promotion_gate_status_label) not in {
        PROMOTION_GATE_DOWNGRADED,
        PROMOTION_GATE_QUARANTINED,
    }:
        posture["trust_tier_label"] = TRUST_TIER_LOCAL_ONLY
        posture["governed_review_status_label"] = REVIEW_STATUS_NOT_REVIEWED
        posture["governed_review_reason_label"] = REVIEW_REASON_LOCAL_DEFAULT
        posture["governed_review_status_summary"] = (
            "Continuity-cluster review is not yet active because the current continuity picture remains local-only or context-only."
        )
        posture["governed_review_reason_summary"] = (
            "Context-only continuity should stay visible without quietly turning into broader carryover."
        )
    elif cluster_label == CONTINUITY_CLUSTER_CONTRADICTION_LIMITED and posture["governed_review_status_label"] not in {
        REVIEW_STATUS_DOWNGRADED,
        REVIEW_STATUS_QUARANTINED,
    }:
        posture["trust_tier_label"] = TRUST_TIER_CANDIDATE
        posture["governed_review_status_label"] = REVIEW_STATUS_BLOCKED
        posture["governed_review_reason_label"] = REVIEW_REASON_CONTRADICTION
        posture["governed_review_status_summary"] = (
            "Continuity-cluster review is blocked because contradiction-heavy continuity should not behave like approved broader carryover."
        )
        posture["governed_review_reason_summary"] = (
            "Contradiction-heavy continuity remains informative, but it should stay blocked from stronger broader influence."
        )
    elif cluster_label == CONTINUITY_CLUSTER_HISTORICAL and posture["governed_review_status_label"] not in {
        REVIEW_STATUS_DOWNGRADED,
        REVIEW_STATUS_QUARANTINED,
    }:
        posture["trust_tier_label"] = TRUST_TIER_CANDIDATE
        posture["governed_review_status_label"] = REVIEW_STATUS_BLOCKED
        posture["governed_review_reason_label"] = REVIEW_REASON_HISTORICAL
        posture["governed_review_status_summary"] = (
            "Continuity-cluster review is blocked because historical-heavy continuity should not silently keep current broader influence."
        )
        posture["governed_review_reason_summary"] = (
            "Historical continuity remains visible as context, not as approved broader carryover."
        )
    elif cluster_label == CONTINUITY_CLUSTER_SELECTIVE and posture["governed_review_status_label"] not in {
        REVIEW_STATUS_APPROVED,
        REVIEW_STATUS_DOWNGRADED,
        REVIEW_STATUS_QUARANTINED,
    }:
        posture["trust_tier_label"] = TRUST_TIER_CANDIDATE
        posture["governed_review_status_label"] = REVIEW_STATUS_DEFERRED
        posture["governed_review_reason_label"] = REVIEW_REASON_SELECTIVE
        posture["governed_review_status_summary"] = (
            "Continuity-cluster review remains deferred because the cluster is selectively useful but still too bounded for cleaner broader carryover."
        )
        posture["governed_review_reason_summary"] = (
            "Selective continuity can support bounded review without being treated as stronger session-family carryover."
        )

    if _safe_int(tentative_continuity_count) + _safe_int(contested_continuity_count) >= max(2, _safe_int(governing_continuity_count) + 1):
        posture["carryover_guardrail_summary"] = (
            "Many tentative or contradiction-limited continuity fragments do not simulate a stronger continuity cluster. Broader carryover still depends on stable, governing continuity."
        )
    else:
        posture["carryover_guardrail_summary"] = (
            "Continuity-cluster carryover depends on stable continuity and review, not on how many weakly aligned fragments accumulate."
        )
    posture["decision_summary"] = _decision_summary_for_layer(
        layer_name="Continuity-cluster review",
        trust_tier_label=posture["trust_tier_label"],
        review_status_label=posture["governed_review_status_label"],
        review_reason_summary=posture["governed_review_reason_summary"],
    )
    return posture


def compose_session_family_review_posture(
    *,
    source_class_label: Any = "",
    provenance_confidence_label: Any = "",
    broader_governed_reuse_label: Any = "",
    broader_continuity_label: Any = "",
    future_reuse_candidacy_label: Any = "",
    promotion_gate_status_label: Any = "",
    promotion_block_reason_label: Any = "",
    belief_state_review_status_label: Any = "",
    continuity_cluster_review_status_label: Any = "",
    active_support_count: int = 0,
    claims_with_active_governed_continuity_count: int = 0,
    claims_with_tentative_active_continuity_count: int = 0,
    claims_with_contradiction_limited_reuse_count: int = 0,
    claims_with_historical_continuity_only_count: int = 0,
    claims_with_no_governed_support_count: int = 0,
    contested_flag: bool = False,
    degraded_flag: bool = False,
    historical_stronger_flag: bool = False,
) -> dict[str, str]:
    broader_reuse = _clean_text(broader_governed_reuse_label)
    broader_continuity = _clean_text(broader_continuity_label)
    future_reuse = _clean_text(future_reuse_candidacy_label)
    belief_state_review = _clean_text(belief_state_review_status_label)
    continuity_review = _clean_text(continuity_cluster_review_status_label)
    candidate_context = (
        broader_reuse != BROADER_REUSE_LOCAL_ONLY
        or future_reuse != FUTURE_REUSE_CANDIDACY_LOCAL_ONLY
        or _clean_text(promotion_gate_status_label) != PROMOTION_GATE_NOT_CANDIDATE
    )
    allow_approval = (
        broader_reuse == BROADER_REUSE_STRONG
        and broader_continuity == BROADER_CONTINUITY_COHERENT
        and future_reuse == FUTURE_REUSE_CANDIDACY_STRONG
        and _clean_text(promotion_gate_status_label) == PROMOTION_GATE_PROMOTABLE
        and belief_state_review == REVIEW_STATUS_APPROVED
        and continuity_review == REVIEW_STATUS_APPROVED
        and _safe_int(claims_with_active_governed_continuity_count) > 0
        and not contested_flag
        and not degraded_flag
        and not historical_stronger_flag
        and _stronger_provenance(provenance_confidence_label)
        and not _uncontrolled_source(source_class_label)
    )
    posture = _compose_layer_review_posture(
        layer_name="Session-family carryover review",
        source_class_label=source_class_label,
        provenance_confidence_label=provenance_confidence_label,
        promotion_gate_status_label=promotion_gate_status_label,
        promotion_block_reason_label=promotion_block_reason_label,
        active_support_count=_safe_int(active_support_count),
        accepted_support_count=_safe_int(claims_with_active_governed_continuity_count),
        candidate_context=candidate_context,
        contested_flag=contested_flag,
        degraded_flag=degraded_flag,
        historical_stronger_flag=historical_stronger_flag,
        allow_approval=allow_approval,
        local_only_reason=(
            "This session remains useful locally by default, but session-family carryover should not be inferred until broader coherence survives review."
        ),
        selective_reason=(
            "Session-family carryover remains selective only. The session can still inform bounded read-across without becoming approved broader carryover."
        ),
        contradiction_reason=(
            "Session-family broader carryover is blocked because contradiction-heavy or degraded broader state should not be aggregated into stronger influence."
        ),
        degraded_reason=(
            "Session-family broader carryover is blocked because degraded present posture weakens the current broader state too much."
        ),
        historical_reason=(
            "This session-family picture is mainly historical context, so it should stay visible without behaving like current approved carryover."
        ),
        default_reason=(
            "Session-family carryover requires belief-state and continuity-cluster approval, not just stronger individual claims."
        ),
    )
    if belief_state_review not in {REVIEW_STATUS_APPROVED, ""} and posture["governed_review_status_label"] == REVIEW_STATUS_APPROVED:
        posture["trust_tier_label"] = TRUST_TIER_CANDIDATE
        posture["governed_review_status_label"] = REVIEW_STATUS_DEFERRED
        posture["governed_review_reason_label"] = REVIEW_REASON_STRONGER_TRUST_NEEDED
        posture["governed_review_status_summary"] = (
            "Session-family carryover remains deferred because belief-state posture is not yet approved for bounded broader carryover."
        )
        posture["governed_review_reason_summary"] = (
            "Claim-level or evidence-level strength is not enough on its own for session-family carryover to be approved."
        )
    if continuity_review in {REVIEW_STATUS_BLOCKED, REVIEW_STATUS_QUARANTINED} and posture["governed_review_status_label"] not in {
        REVIEW_STATUS_DOWNGRADED,
        REVIEW_STATUS_QUARANTINED,
    }:
        posture["trust_tier_label"] = TRUST_TIER_CANDIDATE
        posture["governed_review_status_label"] = REVIEW_STATUS_BLOCKED if continuity_review == REVIEW_STATUS_BLOCKED else REVIEW_STATUS_QUARANTINED
        posture["governed_review_reason_label"] = REVIEW_REASON_CONTRADICTION if continuity_review == REVIEW_STATUS_BLOCKED else REVIEW_REASON_QUARANTINED
        posture["governed_review_status_summary"] = (
            "Session-family carryover cannot be approved because the continuity-cluster layer is currently blocked or quarantined."
        )
        posture["governed_review_reason_summary"] = (
            "Broader carryover should not outrun an unstable continuity cluster."
        )
    elif broader_reuse == BROADER_REUSE_HISTORICAL_ONLY and posture["governed_review_status_label"] not in {
        REVIEW_STATUS_DOWNGRADED,
        REVIEW_STATUS_QUARANTINED,
    }:
        posture["trust_tier_label"] = TRUST_TIER_CANDIDATE
        posture["governed_review_status_label"] = REVIEW_STATUS_BLOCKED
        posture["governed_review_reason_label"] = REVIEW_REASON_HISTORICAL
        posture["governed_review_status_summary"] = (
            "Session-family carryover is blocked because the broader state is historical-heavy rather than strongly current."
        )
        posture["governed_review_reason_summary"] = (
            "Historical broader context remains visible without being treated as current approved carryover."
        )
    elif broader_reuse == BROADER_REUSE_CONTRADICTION_LIMITED and posture["governed_review_status_label"] not in {
        REVIEW_STATUS_DOWNGRADED,
        REVIEW_STATUS_QUARANTINED,
    }:
        posture["trust_tier_label"] = TRUST_TIER_CANDIDATE
        posture["governed_review_status_label"] = REVIEW_STATUS_BLOCKED
        posture["governed_review_reason_label"] = REVIEW_REASON_CONTRADICTION
        posture["governed_review_status_summary"] = (
            "Session-family carryover is blocked because contradiction-limited broader reuse should not behave like stronger governed carryover."
        )
        posture["governed_review_reason_summary"] = (
            "Broader carryover requires coherence, not just many locally useful fragments."
        )
    elif broader_reuse == BROADER_REUSE_SELECTIVE or future_reuse == FUTURE_REUSE_CANDIDACY_SELECTIVE or continuity_review == REVIEW_STATUS_DEFERRED:
        posture["trust_tier_label"] = TRUST_TIER_CANDIDATE
        posture["governed_review_status_label"] = REVIEW_STATUS_DEFERRED
        posture["governed_review_reason_label"] = REVIEW_REASON_SELECTIVE
        posture["governed_review_status_summary"] = (
            "Session-family carryover remains deferred because the broader state is selectively useful but still too bounded for cleaner approval."
        )
        posture["governed_review_reason_summary"] = (
            "Selective broader reuse keeps session-family influence reviewable rather than broadly approved."
        )

    weak_multiplicity = (
        _safe_int(claims_with_tentative_active_continuity_count)
        + _safe_int(claims_with_contradiction_limited_reuse_count)
        + _safe_int(claims_with_historical_continuity_only_count)
        + _safe_int(claims_with_no_governed_support_count)
    )
    if weak_multiplicity >= max(2, _safe_int(claims_with_active_governed_continuity_count) + 1):
        posture["carryover_guardrail_summary"] = (
            "Many weak local claims or continuity fragments do not simulate approved session-family carryover. Broader carryover still depends on coherent belief-state, stable continuity, provenance, and review."
        )
    else:
        posture["carryover_guardrail_summary"] = (
            "Session-family carryover depends on coherent reviewed state, not on volume of locally useful fragments."
        )
    posture["decision_summary"] = _decision_summary_for_layer(
        layer_name="Session-family carryover review",
        trust_tier_label=posture["trust_tier_label"],
        review_status_label=posture["governed_review_status_label"],
        review_reason_summary=posture["governed_review_reason_summary"],
    )
    return posture


def list_subject_governed_reviews(
    *,
    workspace_id: str | None = None,
    subject_type: str,
    subject_id: str,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    return governed_review_repository.list_reviews(
        workspace_id=workspace_id,
        subject_type=subject_type,
        subject_id=subject_id,
        active_only=active_only,
    )


def latest_subject_governed_review(
    *,
    workspace_id: str,
    subject_type: str,
    subject_id: str,
) -> dict[str, Any] | None:
    return governed_review_repository.get_latest_active_review(
        workspace_id=workspace_id,
        subject_type=subject_type,
        subject_id=subject_id,
    )


def record_subject_governed_review(
    payload: dict[str, Any],
) -> dict[str, Any]:
    clean_payload = validate_governed_review_record(
        {
            "review_record_id": "",
            "workspace_id": payload.get("workspace_id", ""),
            "session_id": payload.get("session_id", ""),
            "subject_type": payload.get("subject_type", ""),
            "subject_id": payload.get("subject_id", ""),
            "target_key": payload.get("target_key", ""),
            "candidate_id": payload.get("candidate_id", ""),
            "active": payload.get("active", True),
            "source_class_label": payload.get("source_class_label", ""),
            "provenance_confidence_label": payload.get("provenance_confidence_label", ""),
            "trust_tier_label": payload.get("trust_tier_label", ""),
            "review_status_label": payload.get("review_status_label", ""),
            "review_reason_label": payload.get("review_reason_label", ""),
            "review_reason_summary": payload.get("review_reason_summary", ""),
            "promotion_gate_status_label": payload.get("promotion_gate_status_label", ""),
            "promotion_block_reason_label": payload.get("promotion_block_reason_label", ""),
            "decision_outcome": payload.get("decision_outcome", ""),
            "decision_summary": payload.get("decision_summary", ""),
            "supersedes_review_record_id": payload.get("supersedes_review_record_id", ""),
            "recorded_at": payload.get("recorded_at") or _utc_now(),
            "recorded_by": payload.get("recorded_by", "system"),
            "actor_user_id": payload.get("actor_user_id", ""),
            "metadata": payload.get("metadata", {}),
        }
    )
    if not _clean_text(clean_payload.get("decision_outcome")):
        clean_payload["decision_outcome"] = _decision_outcome(
            trust_tier_label=_clean_text(clean_payload.get("trust_tier_label")),
            review_status_label=_clean_text(clean_payload.get("review_status_label")),
            promotion_gate_status_label=_clean_text(clean_payload.get("promotion_gate_status_label")),
        )
    return governed_review_repository.record_review(clean_payload)


def sync_subject_governed_review_snapshot(
    payload: dict[str, Any],
) -> dict[str, Any]:
    clean_payload = validate_governed_review_record(
        {
            "review_record_id": "",
            "workspace_id": payload.get("workspace_id", ""),
            "session_id": payload.get("session_id", ""),
            "subject_type": payload.get("subject_type", ""),
            "subject_id": payload.get("subject_id", ""),
            "target_key": payload.get("target_key", ""),
            "candidate_id": payload.get("candidate_id", ""),
            "active": payload.get("active", True),
            "source_class_label": payload.get("source_class_label", ""),
            "provenance_confidence_label": payload.get("provenance_confidence_label", ""),
            "trust_tier_label": payload.get("trust_tier_label", ""),
            "review_status_label": payload.get("review_status_label", ""),
            "review_reason_label": payload.get("review_reason_label", ""),
            "review_reason_summary": payload.get("review_reason_summary", ""),
            "promotion_gate_status_label": payload.get("promotion_gate_status_label", ""),
            "promotion_block_reason_label": payload.get("promotion_block_reason_label", ""),
            "decision_outcome": payload.get("decision_outcome", ""),
            "decision_summary": payload.get("decision_summary", ""),
            "supersedes_review_record_id": payload.get("supersedes_review_record_id", ""),
            "recorded_at": payload.get("recorded_at") or _utc_now(),
            "recorded_by": payload.get("recorded_by", "system"),
            "actor_user_id": payload.get("actor_user_id", ""),
            "metadata": payload.get("metadata", {}),
        }
    )
    if not _clean_text(clean_payload.get("decision_outcome")):
        clean_payload["decision_outcome"] = _decision_outcome(
            trust_tier_label=_clean_text(clean_payload.get("trust_tier_label")),
            review_status_label=_clean_text(clean_payload.get("review_status_label")),
            promotion_gate_status_label=_clean_text(clean_payload.get("promotion_gate_status_label")),
        )
    workspace_id = _clean_text(clean_payload.get("workspace_id"))
    subject_type = _clean_text(clean_payload.get("subject_type"))
    subject_id = _clean_text(clean_payload.get("subject_id"))
    latest = (
        latest_subject_governed_review(
            workspace_id=workspace_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        if workspace_id and subject_type and subject_id
        else None
    )
    comparable_fields = (
        "source_class_label",
        "provenance_confidence_label",
        "trust_tier_label",
        "review_status_label",
        "review_reason_label",
        "review_reason_summary",
        "promotion_gate_status_label",
        "promotion_block_reason_label",
        "decision_outcome",
        "decision_summary",
        "target_key",
        "candidate_id",
        "recorded_by",
    )
    if latest:
        unchanged = all(
            _clean_text(latest.get(field)) == _clean_text(clean_payload.get(field))
            for field in comparable_fields
        ) and _json_signature(latest.get("metadata")) == _json_signature(clean_payload.get("metadata"))
        if unchanged:
            return latest
    return record_subject_governed_review(clean_payload)


def build_governed_review_overlay(
    records: list[dict[str, Any]] | None,
    *,
    fallback_fields: dict[str, Any] | None = None,
    subject_label: str = "This evidence",
) -> dict[str, Any]:
    records = [record for record in (records or []) if isinstance(record, dict)]
    fallback_fields = fallback_fields if isinstance(fallback_fields, dict) else {}
    latest = _latest_record(records)
    history_count = len(records)
    active_count = sum(1 for record in records if bool(record.get("active")))
    source_class_label = _clean_text(
        (latest or {}).get("source_class_label") or fallback_fields.get("source_class_label")
    )
    trust_tier_label = _clean_text(
        (latest or {}).get("trust_tier_label") or fallback_fields.get("trust_tier_label")
    )
    provenance_confidence_label = _clean_text(
        (latest or {}).get("provenance_confidence_label") or fallback_fields.get("provenance_confidence_label")
    )
    review_status_label = _clean_text(
        (latest or {}).get("review_status_label") or fallback_fields.get("governed_review_status_label")
    )
    review_reason_label = _clean_text(
        (latest or {}).get("review_reason_label") or fallback_fields.get("governed_review_reason_label")
    )
    review_reason_summary = _clean_text(
        (latest or {}).get("review_reason_summary") or fallback_fields.get("governed_review_reason_summary")
    )
    promotion_gate_status_label = _clean_text(
        (latest or {}).get("promotion_gate_status_label") or fallback_fields.get("promotion_gate_status_label")
    )
    promotion_block_reason_label = _clean_text(
        (latest or {}).get("promotion_block_reason_label") or fallback_fields.get("promotion_block_reason_label")
    )

    if latest:
        history_summary = (
            f"{subject_label} has {history_count} governed review record"
            f"{'' if history_count == 1 else 's'}; latest posture is {review_status_label or 'not recorded'}"
            f" under {trust_tier_label or 'local-only'}."
        )
        if active_count <= 0:
            history_summary += " No active broader-influence posture remains current."
    elif fallback_fields:
        history_summary = (
            f"{subject_label} does not yet have a persisted governed review record. "
            "Current trust and review posture is still computed from the live bridge-state rules."
        )
    else:
        history_summary = ""

    if latest:
        decision_outcome = _clean_text(latest.get("decision_outcome"), default="local_only").replace("_", " ")
        promotion_audit_summary = (
            f"Latest promotion outcome is {decision_outcome}."
            f" Gate: {promotion_gate_status_label or 'not recorded'}."
            f" Block reason: {promotion_block_reason_label or 'not recorded'}."
        )
        superseded_count = sum(1 for record in records if _clean_text(record.get("supersedes_review_record_id")))
        if superseded_count > 0:
            promotion_audit_summary += (
                f" {superseded_count} earlier promotion-relevant posture"
                f"{'' if superseded_count == 1 else 's'} were superseded rather than silently retained."
            )
    elif fallback_fields:
        promotion_audit_summary = (
            f"Promotion posture is currently computed as {promotion_gate_status_label or 'not recorded'}"
            f" with block reason {promotion_block_reason_label or 'not recorded'}, but no persisted audit record exists yet."
        )
    else:
        promotion_audit_summary = ""

    return {
        "source_class_label": source_class_label,
        "trust_tier_label": trust_tier_label,
        "provenance_confidence_label": provenance_confidence_label,
        "governed_review_status_label": review_status_label,
        "governed_review_reason_label": review_reason_label,
        "governed_review_reason_summary": review_reason_summary,
        "promotion_gate_status_label": promotion_gate_status_label,
        "promotion_block_reason_label": promotion_block_reason_label,
        "governed_review_record_count": history_count,
        "governed_review_history_summary": history_summary,
        "promotion_audit_summary": promotion_audit_summary,
        "latest_governed_review_record": latest,
    }


__all__ = [
    "SUBJECT_TYPE_CLAIM",
    "SUBJECT_TYPE_BELIEF_STATE",
    "SUBJECT_TYPE_CONTINUITY_CLUSTER",
    "SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER",
    "build_governed_review_overlay",
    "compose_belief_state_review_posture",
    "compose_continuity_cluster_review_posture",
    "compose_session_family_review_posture",
    "latest_subject_governed_review",
    "list_subject_governed_reviews",
    "record_subject_governed_review",
    "sync_subject_governed_review_snapshot",
]
