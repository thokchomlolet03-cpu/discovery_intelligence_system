from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    BeliefUpdateGovernanceStatus,
    ClaimStatus,
    ClaimType,
    EvidenceSupportLevel,
    validate_claim_record,
    validate_claim_reference,
    validate_claims_summary,
    validate_scientific_session_truth,
)
from system.db.repositories import ClaimRepository
from system.db.repositories import BeliefUpdateRepository
from system.services.governed_review_service import (
    SUBJECT_TYPE_CLAIM,
    build_governed_review_overlay,
    latest_subject_governed_review,
    list_subject_governed_reviews,
    record_subject_governed_review,
)
from system.services.support_quality_service import (
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
    assess_support_coherence,
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
    SOURCE_CLASS_AI_DERIVED,
    SOURCE_CLASS_AFFILIATED,
    SOURCE_CLASS_CURATED,
    SOURCE_CLASS_DERIVED_EXTRACTED,
    SOURCE_CLASS_INTERNAL_GOVERNED,
    SOURCE_CLASS_UNCONTROLLED_UPLOAD,
    SOURCE_CLASS_UNKNOWN,
    GOVERNED_SUPPORT_POSTURE_ACCEPTED_LIMITED,
    GOVERNED_SUPPORT_POSTURE_GOVERNING,
    GOVERNED_SUPPORT_POSTURE_HISTORICAL,
    GOVERNED_SUPPORT_POSTURE_TENTATIVE,
    SUPPORT_QUALITY_CONTEXT_LIMITED,
    SUPPORT_QUALITY_DECISION_USEFUL,
    SUPPORT_QUALITY_WEAK,
    classify_belief_update_support_quality,
    classify_governed_support_posture,
    rollup_governed_support_postures,
    rollup_provenance_confidence,
    rollup_quality_labels,
)


claim_repository = ClaimRepository()
belief_update_repository = BeliefUpdateRepository()
DEFAULT_CLAIM_LIMIT = 5


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


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _candidate_label(candidate: dict[str, Any]) -> str:
    candidate_id = _clean_text(
        candidate.get("candidate_id") or candidate.get("molecule_id") or candidate.get("polymer")
    )
    smiles = _clean_text(candidate.get("canonical_smiles") or candidate.get("smiles"))
    if candidate_id and smiles and candidate_id != smiles:
        return f"{candidate_id} ({smiles})"
    return candidate_id or smiles or "candidate"


def _support_level(candidate: dict[str, Any]) -> str:
    trust_label = _clean_text(
        candidate.get("trust_label")
        or ((candidate.get("rationale") or {}) if isinstance(candidate.get("rationale"), dict) else {}).get("trust_label")
    ).lower()
    if trust_label == "stronger trust":
        return EvidenceSupportLevel.strong.value
    if trust_label == "mixed trust":
        return EvidenceSupportLevel.moderate.value
    return EvidenceSupportLevel.limited.value


def _claim_text(candidate: dict[str, Any], target_definition: dict[str, Any], target_name: str) -> str:
    label = _candidate_label(candidate)
    target_kind = _clean_text(target_definition.get("target_kind"), default="classification").lower()
    optimization = _clean_text(target_definition.get("optimization_direction"), default="classify").lower()
    if target_kind == "regression":
        if optimization == "minimize":
            return f"Under the current session evidence, {label} is a plausible follow-up candidate to test for lower {target_name}."
        return f"Under the current session evidence, {label} is a plausible follow-up candidate to test for higher {target_name}."
    return f"Under the current session evidence, {label} is a plausible follow-up candidate to test against the current {target_name} objective."


def _bounded_scope(candidate: dict[str, Any], target_definition: dict[str, Any]) -> str:
    target_name = _clean_text(target_definition.get("target_name"), default="target objective")
    domain_status = _clean_text(candidate.get("domain_status"))
    scope = (
        f"This proposed claim is scoped to the current session, the recorded {target_name} target definition, and the current recommendation evidence. "
        "It is not experimental confirmation or causal proof."
    )
    if domain_status == "out_of_domain":
        return f"{scope} Chemistry support is weaker because this candidate sits outside stronger reference coverage."
    if domain_status == "near_boundary":
        return f"{scope} Chemistry support is mixed because this candidate sits near the current applicability boundary."
    return scope


def _evidence_basis_summary(candidate: dict[str, Any], scientific_truth: dict[str, Any]) -> str:
    evidence_loop = scientific_truth.get("evidence_loop") if isinstance(scientific_truth, dict) else {}
    evidence_loop = evidence_loop if isinstance(evidence_loop, dict) else {}
    modeling = _clean_list(evidence_loop.get("active_modeling_evidence"))
    ranking = _clean_list(evidence_loop.get("active_ranking_evidence"))
    parts: list[str] = []
    if modeling:
        parts.append(f"Modeling uses {', '.join(modeling[:2])}")
    if ranking:
        parts.append(f"ranking uses {', '.join(ranking[:2])}")
    primary_driver = _clean_text(
        candidate.get("rationale_primary_driver")
        or ((candidate.get("rationale") or {}) if isinstance(candidate.get("rationale"), dict) else {}).get("primary_driver")
    )
    if primary_driver:
        parts.append(primary_driver)
    if not parts:
        parts.append("Derived from the current session evidence, model output, and recommendation policy")
    return ". ".join(part.rstrip(".") for part in parts if part).strip() + "."


def build_claim_record(
    *,
    session_id: str,
    workspace_id: str,
    candidate: dict[str, Any],
    target_definition: dict[str, Any] | None,
    scientific_truth: dict[str, Any] | None,
    created_by_user_id: str | None = None,
    created_by: str = "system",
) -> dict[str, Any]:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    scientific_truth = scientific_truth if isinstance(scientific_truth, dict) else {}
    candidate_id = _clean_text(candidate.get("candidate_id") or candidate.get("molecule_id") or candidate.get("polymer"))
    target_name = _clean_text(target_definition.get("target_name"), default="target objective")
    timestamp = _utc_now()
    return validate_claim_record(
        {
            "claim_id": "",
            "workspace_id": workspace_id,
            "session_id": session_id,
            "candidate_id": candidate_id,
            "candidate_reference": {
                "candidate_id": candidate_id,
                "candidate_label": _candidate_label(candidate),
                "smiles": _clean_text(candidate.get("smiles")),
                "canonical_smiles": _clean_text(candidate.get("canonical_smiles") or candidate.get("smiles")),
                "rank": _safe_int(candidate.get("rank"), 0),
            },
            "target_definition_snapshot": target_definition,
            "claim_type": ClaimType.recommendation_assertion.value,
            "claim_text": _claim_text(candidate, target_definition, target_name),
            "bounded_scope": _bounded_scope(candidate, target_definition),
            "support_level": _support_level(candidate),
            "evidence_basis_summary": _evidence_basis_summary(candidate, scientific_truth),
            "source_recommendation_rank": _safe_int(candidate.get("rank"), 0),
            "status": ClaimStatus.proposed.value,
            "created_at": timestamp,
            "updated_at": timestamp,
            "created_by": _clean_text(created_by, default="system"),
            "created_by_user_id": _clean_text(created_by_user_id),
            "reviewed_at": None,
            "reviewed_by": "",
            "metadata": {
                "target_name": target_name,
                "support_driver": _clean_text(candidate.get("rationale_primary_driver")),
                "trust_label": _clean_text(candidate.get("trust_label")),
            },
        }
    )


def create_session_claims(
    *,
    session_id: str,
    workspace_id: str,
    decision_payload: dict[str, Any] | None,
    scientific_truth: dict[str, Any] | None,
    created_by_user_id: str | None = None,
    created_by: str = "system",
    limit: int = DEFAULT_CLAIM_LIMIT,
) -> list[dict[str, Any]]:
    decision_payload = decision_payload if isinstance(decision_payload, dict) else {}
    scientific_truth = scientific_truth if isinstance(scientific_truth, dict) else {}
    target_definition = (
        scientific_truth.get("target_definition") if isinstance(scientific_truth.get("target_definition"), dict) else {}
    ) or (decision_payload.get("target_definition") if isinstance(decision_payload.get("target_definition"), dict) else {})
    rows = decision_payload.get("top_experiments") if isinstance(decision_payload.get("top_experiments"), list) else []
    created: list[dict[str, Any]] = []
    for candidate in rows[: max(0, int(limit))]:
        if not isinstance(candidate, dict):
            continue
        candidate_id = _clean_text(candidate.get("candidate_id") or candidate.get("molecule_id") or candidate.get("polymer"))
        if not candidate_id:
            continue
        payload = build_claim_record(
            session_id=session_id,
            workspace_id=workspace_id,
            candidate=candidate,
            target_definition=target_definition,
            scientific_truth=scientific_truth,
            created_by_user_id=created_by_user_id,
            created_by=created_by,
        )
        created_claim = claim_repository.upsert_claim(payload)
        sync_claim_governed_review_snapshot(
            claim_id=_clean_text(created_claim.get("claim_id")),
            workspace_id=workspace_id,
            recorded_by=created_by,
            actor_user_id=created_by_user_id,
        )
        created.append(created_claim)
    return created


def list_session_claims(session_id: str, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
    return claim_repository.list_claims(session_id=session_id, workspace_id=workspace_id)


def sync_claim_governed_review_snapshot(
    *,
    claim_id: str,
    workspace_id: str,
    recorded_by: str = "system",
    actor_user_id: str | None = None,
) -> dict[str, Any] | None:
    claim_id = _clean_text(claim_id)
    workspace_id = _clean_text(workspace_id)
    if not claim_id or not workspace_id:
        return None
    claim = claim_repository.get_claim(claim_id, workspace_id=workspace_id)
    all_claims = claim_repository.list_claims(workspace_id=workspace_id)
    same_session_claims = [
        item for item in all_claims if _clean_text(item.get("session_id")) == _clean_text(claim.get("session_id"))
    ]
    prior_claims = [
        item
        for item in all_claims
        if _clean_text(item.get("claim_id")) != claim_id
        and _clean_text(item.get("session_id")) != _clean_text(claim.get("session_id"))
    ]
    all_belief_updates = belief_update_repository.list_belief_updates(workspace_id=workspace_id)
    current_session_belief_updates = [
        item for item in all_belief_updates if _clean_text(item.get("session_id")) == _clean_text(claim.get("session_id"))
    ]
    prior_belief_updates = [
        item for item in all_belief_updates if _clean_text(item.get("session_id")) != _clean_text(claim.get("session_id"))
    ]
    refs = claim_refs_from_records(
        [claim],
        belief_updates=current_session_belief_updates,
        prior_claims=prior_claims,
        prior_belief_updates=prior_belief_updates,
        include_governed_review_overlay=False,
    )
    if not refs:
        return None
    ref = refs[0]
    latest = latest_subject_governed_review(
        workspace_id=workspace_id,
        subject_type=SUBJECT_TYPE_CLAIM,
        subject_id=claim_id,
    )
    comparable_fields = {
        "source_class_label": _clean_text(ref.get("claim_source_class_label")),
        "provenance_confidence_label": _clean_text(ref.get("claim_provenance_confidence_label")),
        "trust_tier_label": _clean_text(ref.get("claim_trust_tier_label")),
        "review_status_label": _clean_text(ref.get("claim_governed_review_status_label")),
        "review_reason_label": _clean_text(ref.get("claim_governed_review_reason_label")),
        "review_reason_summary": _clean_text(ref.get("claim_governed_review_reason_summary")),
        "promotion_gate_status_label": _clean_text(ref.get("claim_promotion_gate_status_label")),
        "promotion_block_reason_label": _clean_text(ref.get("claim_promotion_block_reason_label")),
    }
    if latest and all(
        _clean_text(latest.get(key)) == value
        for key, value in comparable_fields.items()
    ):
        return latest
    decision_summary = (
        f"{_clean_text(ref.get('claim_governed_review_status_summary'))} "
        f"{_clean_text(ref.get('claim_promotion_gate_status_summary'))}"
    ).strip()
    return record_subject_governed_review(
        {
            "workspace_id": workspace_id,
            "session_id": _clean_text(claim.get("session_id")),
            "subject_type": SUBJECT_TYPE_CLAIM,
            "subject_id": claim_id,
            "target_key": _claim_target_key_from_record(claim),
            "candidate_id": _clean_text(claim.get("candidate_id")),
            "source_class_label": comparable_fields["source_class_label"],
            "provenance_confidence_label": comparable_fields["provenance_confidence_label"],
            "trust_tier_label": comparable_fields["trust_tier_label"],
            "review_status_label": comparable_fields["review_status_label"],
            "review_reason_label": comparable_fields["review_reason_label"],
            "review_reason_summary": comparable_fields["review_reason_summary"],
            "promotion_gate_status_label": comparable_fields["promotion_gate_status_label"],
            "promotion_block_reason_label": comparable_fields["promotion_block_reason_label"],
            "decision_summary": decision_summary,
            "recorded_by": _clean_text(recorded_by, default="system"),
            "actor_user_id": _clean_text(actor_user_id),
            "metadata": {
                "claim_text": _clean_text(ref.get("claim_text")),
                "claim_support_role_label": _clean_text(ref.get("claim_support_role_label")),
                "current_support_count": _safe_int(ref.get("current_support_count")),
                "historical_support_count": _safe_int(ref.get("historical_support_count")),
                "claim_trust_tier_summary": _clean_text(ref.get("claim_trust_tier_summary")),
                "claim_promotion_gate_status_summary": _clean_text(ref.get("claim_promotion_gate_status_summary")),
                "claim_promotion_block_reason_summary": _clean_text(ref.get("claim_promotion_block_reason_summary")),
            },
        }
    )


def _updates_by_claim(belief_updates: list[dict[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for update in belief_updates if isinstance(belief_updates, list) else []:
        if not isinstance(update, dict):
            continue
        claim_id = _clean_text(update.get("claim_id"))
        if not claim_id:
            continue
        grouped.setdefault(claim_id, []).append(update)
    return grouped


def _claim_target_key(target_definition: dict[str, Any] | None) -> str:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    target_name = _clean_text(target_definition.get("target_name")).lower()
    target_kind = _clean_text(target_definition.get("target_kind")).lower()
    direction = _clean_text(target_definition.get("optimization_direction")).lower()
    if not target_name:
        return ""
    return "|".join(part for part in (target_name, target_kind, direction) if part)


def _claim_target_key_from_record(claim: dict[str, Any]) -> str:
    target_definition = (
        claim.get("target_definition_snapshot")
        if isinstance(claim.get("target_definition_snapshot"), dict)
        else {}
    )
    return _claim_target_key(target_definition)


def _claim_continuity_keys(claim: dict[str, Any]) -> set[str]:
    candidate_reference = claim.get("candidate_reference") if isinstance(claim.get("candidate_reference"), dict) else {}
    keys = {
        _clean_text(claim.get("candidate_id")).lower(),
        _clean_text(candidate_reference.get("candidate_id")).lower(),
        _clean_text(candidate_reference.get("canonical_smiles")).lower(),
        _clean_text(candidate_reference.get("smiles")).lower(),
    }
    return {key for key in keys if key}


def _prior_claims_by_target(prior_claims: list[dict[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for claim in prior_claims if isinstance(prior_claims, list) else []:
        if not isinstance(claim, dict):
            continue
        target_key = _claim_target_key_from_record(claim)
        if not target_key:
            continue
        grouped.setdefault(target_key, []).append(claim)
    return grouped


def _prior_update_counts_for_claim(
    claim_id: str,
    *,
    prior_updates_by_claim: dict[str, list[dict[str, Any]]],
) -> tuple[int, int, int]:
    updates = prior_updates_by_claim.get(claim_id, [])
    active_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower()
        in {
            BeliefUpdateGovernanceStatus.proposed.value,
            BeliefUpdateGovernanceStatus.accepted.value,
        }
    )
    historical_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
    )
    rejected_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.rejected.value
    )
    return active_count, historical_count, rejected_count


def _claim_read_across_fields(
    claim: dict[str, Any],
    prior_claims_for_target: list[dict[str, Any]] | None,
    *,
    prior_updates_by_claim: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    prior_claims_for_target = [
        prior_claim
        for prior_claim in (prior_claims_for_target if isinstance(prior_claims_for_target, list) else [])
        if isinstance(prior_claim, dict)
    ]
    prior_updates_by_claim = prior_updates_by_claim if isinstance(prior_updates_by_claim, dict) else {}
    prior_count = len(prior_claims_for_target)
    if prior_count <= 0:
        return {
            "claim_read_across_label": "No prior claim context",
            "claim_read_across_summary": (
                "No strong prior target-scoped claim context is recorded for this claim, so claim read-across remains bounded."
            ),
            "claim_prior_context_count": 0,
            "claim_prior_support_quality_label": "No useful prior claim context",
            "claim_prior_support_quality_summary": (
                "No useful prior governed claim context is recorded for this claim yet."
            ),
            "claim_prior_active_support_count": 0,
            "claim_prior_historical_support_count": 0,
            "claim_exact_match_context_count": 0,
            "claim_prior_posture_governing_continuity_count": 0,
            "claim_prior_tentative_active_continuity_count": 0,
            "claim_prior_contested_continuity_count": 0,
            "claim_prior_historical_continuity_count": 0,
        }

    continuity_keys = _claim_continuity_keys(claim)
    exact_match_claims = [
        prior_claim
        for prior_claim in prior_claims_for_target
        if continuity_keys.intersection(_claim_continuity_keys(prior_claim))
    ]
    exact_match_count = len(exact_match_claims)
    prior_posture_governing_count = 0
    prior_tentative_active_count = 0
    prior_contested_continuity_count = 0
    prior_historical_support_count = 0
    prior_rejected_only_count = 0
    for prior_claim in exact_match_claims:
        prior_claim_id = _clean_text(prior_claim.get("claim_id"))
        matched_updates = prior_updates_by_claim.get(prior_claim_id, [])
        posture_counts = rollup_governed_support_postures(
            [
                (update.get("governed_support_posture_label") or (update.get("metadata") or {}).get("governed_support_posture_label"))
                or classify_governed_support_posture(update).get("governed_support_posture_label")
                for update in matched_updates
            ]
        )
        support_quality_counts = rollup_quality_labels(
            [
                (update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label"))
                or classify_belief_update_support_quality(update).get("support_quality_label")
                for update in matched_updates
                if _clean_text(update.get("governance_status")).lower()
                in {
                    BeliefUpdateGovernanceStatus.proposed.value,
                    BeliefUpdateGovernanceStatus.accepted.value,
                }
            ]
        )
        coherence = assess_support_coherence(
            active_count=sum(
                1
                for update in matched_updates
                if _clean_text(update.get("governance_status")).lower()
                in {
                    BeliefUpdateGovernanceStatus.proposed.value,
                    BeliefUpdateGovernanceStatus.accepted.value,
                }
            ),
            accepted_count=sum(
                1
                for update in matched_updates
                if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.accepted.value
            ),
            strengthened_count=sum(
                1
                for update in matched_updates
                if _clean_text(update.get("governance_status")).lower()
                in {
                    BeliefUpdateGovernanceStatus.proposed.value,
                    BeliefUpdateGovernanceStatus.accepted.value,
                }
                and _clean_text(update.get("update_direction")).lower() == "strengthened"
            ),
            weakened_count=sum(
                1
                for update in matched_updates
                if _clean_text(update.get("governance_status")).lower()
                in {
                    BeliefUpdateGovernanceStatus.proposed.value,
                    BeliefUpdateGovernanceStatus.accepted.value,
                }
                and _clean_text(update.get("update_direction")).lower() == "weakened"
            ),
            unresolved_count=sum(
                1
                for update in matched_updates
                if _clean_text(update.get("governance_status")).lower()
                in {
                    BeliefUpdateGovernanceStatus.proposed.value,
                    BeliefUpdateGovernanceStatus.accepted.value,
                }
                and _clean_text(update.get("update_direction")).lower() == "unresolved"
            ),
            support_quality_counts=support_quality_counts,
            posture_counts=posture_counts,
            historical_decision_useful_count=sum(
                1
                for update in matched_updates
                if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
                and (
                    _clean_text(update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label"))
                    or classify_belief_update_support_quality(update).get("support_quality_label")
                )
                == SUPPORT_QUALITY_DECISION_USEFUL
            ),
            superseded_count=sum(
                1
                for update in matched_updates
                if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
            ),
        )
        if posture_counts["governing_count"] > 0:
            if bool(coherence.get("current_support_contested_flag")) or bool(coherence.get("current_posture_degraded_flag")):
                prior_contested_continuity_count += 1
                continue
            prior_posture_governing_count += 1
            continue
        active_count, historical_count, rejected_count = _prior_update_counts_for_claim(
            prior_claim_id,
            prior_updates_by_claim=prior_updates_by_claim,
        )
        if active_count > 0:
            if bool(coherence.get("current_support_contested_flag")) or bool(coherence.get("current_posture_degraded_flag")):
                prior_contested_continuity_count += 1
                continue
            prior_tentative_active_count += 1
        elif historical_count > 0:
            prior_historical_support_count += 1
        elif rejected_count > 0:
            prior_rejected_only_count += 1
    if exact_match_count > 0:
        if prior_posture_governing_count > 0:
            quality_label = "Posture-governing continuity"
            quality_summary = (
                f"Prior continuity for this claim context includes {prior_posture_governing_count} claim record"
                f"{'' if prior_posture_governing_count == 1 else 's'} backed by accepted posture-governing support."
            )
            read_across_label = "Continuity-aligned claim"
            read_across_summary = (
                f"This claim aligns with {exact_match_count} prior target-scoped claim record"
                f"{'' if exact_match_count == 1 else 's'} for the same candidate context, including "
                f"{prior_posture_governing_count} with posture-governing current support. Read-across remains bounded and does not confirm claim identity."
            )
        elif prior_contested_continuity_count > 0:
            quality_label = "Discounted contested continuity"
            quality_summary = (
                f"Prior continuity for this claim context includes {prior_contested_continuity_count} matched claim record"
                f"{'' if prior_contested_continuity_count == 1 else 's'} with contested or degraded current support, so reuse should be discounted."
            )
            read_across_label = "Continuity-aligned claim"
            read_across_summary = (
                f"This claim aligns with {exact_match_count} prior target-scoped claim record"
                f"{'' if exact_match_count == 1 else 's'} for the same candidate context, but that continuity is under contradiction pressure or degraded current support. "
                "Read-across remains bounded and should be discounted relative to coherent posture-governing continuity."
            )
        elif prior_tentative_active_count > 0:
            quality_label = "Tentative active continuity"
            quality_summary = (
                f"Prior continuity for this claim context includes {prior_tentative_active_count} active claim record"
                f"{'' if prior_tentative_active_count == 1 else 's'}, but that current support remains tentative or limited rather than posture-governing."
            )
            read_across_label = "Continuity-aligned claim"
            read_across_summary = (
                f"This claim aligns with {exact_match_count} prior target-scoped claim record"
                f"{'' if exact_match_count == 1 else 's'} for the same candidate context, but that continuity is backed only by tentative or limited active support. "
                "Read-across remains bounded and should be discounted relative to posture-governing continuity."
            )
        elif prior_historical_support_count > 0:
            quality_label = "Historical continuity only"
            quality_summary = (
                f"Prior continuity for this claim context is historical only: {prior_historical_support_count} matched claim record"
                f"{'' if prior_historical_support_count == 1 else 's'} currently carry superseded support history."
            )
            read_across_label = "Continuity-aligned claim"
            read_across_summary = (
                f"This claim aligns with {exact_match_count} prior target-scoped claim record"
                f"{'' if exact_match_count == 1 else 's'} for the same candidate context, but that continuity is backed only by historical support. "
                "Read-across remains bounded and does not confirm claim identity."
            )
        else:
            quality_label = "Sparse prior claim context"
            quality_summary = (
                f"Prior continuity for this claim context is sparse: {exact_match_count} matched claim record"
                f"{'' if exact_match_count == 1 else 's'} exist, but they do not currently carry active or historical governed support."
            )
            read_across_label = "Weak prior claim alignment"
            read_across_summary = (
                f"This claim has matching prior target-scoped claim context across {exact_match_count} record"
                f"{'' if exact_match_count == 1 else 's'}, but without strong governed continuity behind it. Read-across remains bounded."
            )
        return {
            "claim_read_across_label": read_across_label,
            "claim_read_across_summary": read_across_summary,
            "claim_prior_context_count": prior_count,
            "claim_prior_support_quality_label": quality_label,
            "claim_prior_support_quality_summary": quality_summary,
            "claim_prior_active_support_count": prior_posture_governing_count + prior_tentative_active_count,
            "claim_prior_historical_support_count": prior_historical_support_count,
            "claim_exact_match_context_count": exact_match_count,
            "claim_prior_posture_governing_continuity_count": prior_posture_governing_count,
            "claim_prior_tentative_active_continuity_count": prior_tentative_active_count,
            "claim_prior_contested_continuity_count": prior_contested_continuity_count,
            "claim_prior_historical_continuity_count": prior_historical_support_count,
        }

    if prior_count >= 3:
        return {
            "claim_read_across_label": "New claim context",
            "claim_read_across_summary": (
                f"This claim adds new candidate context relative to {prior_count} prior target-scoped claim record"
                f"{'' if prior_count == 1 else 's'}. No strong prior governed continuity exists for this exact claim context."
            ),
            "claim_prior_context_count": prior_count,
            "claim_prior_support_quality_label": "Sparse prior claim context",
            "claim_prior_support_quality_summary": (
                f"Prior target-scoped claim context exists across {prior_count} record"
                f"{'' if prior_count == 1 else 's'}, but none provide strong governed continuity for this exact claim context."
            ),
            "claim_prior_active_support_count": 0,
            "claim_prior_historical_support_count": 0,
            "claim_exact_match_context_count": 0,
            "claim_prior_posture_governing_continuity_count": 0,
            "claim_prior_tentative_active_continuity_count": 0,
            "claim_prior_contested_continuity_count": 0,
            "claim_prior_historical_continuity_count": 0,
        }

    return {
        "claim_read_across_label": "Weak prior claim alignment",
        "claim_read_across_summary": (
            f"This claim has only weak prior claim alignment across {prior_count} prior target-scoped claim record"
            f"{'' if prior_count == 1 else 's'}. Read-across remains bounded."
        ),
        "claim_prior_context_count": prior_count,
        "claim_prior_support_quality_label": "Sparse prior claim context",
        "claim_prior_support_quality_summary": (
            f"Only sparse prior target-scoped claim context is recorded across {prior_count} record"
            f"{'' if prior_count == 1 else 's'}, so continuity remains weak."
        ),
        "claim_prior_active_support_count": 0,
        "claim_prior_historical_support_count": 0,
        "claim_exact_match_context_count": 0,
        "claim_prior_posture_governing_continuity_count": 0,
        "claim_prior_tentative_active_continuity_count": 0,
        "claim_prior_contested_continuity_count": 0,
        "claim_prior_historical_continuity_count": 0,
    }


def _claim_broader_reuse_fields(
    claim: dict[str, Any],
    *,
    chronology: dict[str, Any] | None,
    support_coherence: dict[str, Any] | None,
    read_across: dict[str, Any] | None,
) -> dict[str, str]:
    claim = claim if isinstance(claim, dict) else {}
    chronology = chronology if isinstance(chronology, dict) else {}
    support_coherence = support_coherence if isinstance(support_coherence, dict) else {}
    read_across = read_across if isinstance(read_across, dict) else {}
    candidate_label = _clean_text(
        ((claim.get("candidate_reference") or {}) if isinstance(claim.get("candidate_reference"), dict) else {}).get(
            "candidate_label"
        )
        or claim.get("candidate_id"),
        default="This claim",
    )
    exact_match_count = _safe_int(read_across.get("claim_exact_match_context_count"))
    governing_continuity_count = _safe_int(read_across.get("claim_prior_posture_governing_continuity_count"))
    tentative_continuity_count = _safe_int(read_across.get("claim_prior_tentative_active_continuity_count"))
    contested_continuity_count = _safe_int(read_across.get("claim_prior_contested_continuity_count"))
    historical_continuity_count = _safe_int(read_across.get("claim_prior_historical_continuity_count"))
    broader = assess_broader_reuse_posture(
        active_support_count=_safe_int(chronology.get("current_support_count")),
        continuity_evidence_count=exact_match_count,
        governing_continuity_count=governing_continuity_count,
        tentative_continuity_count=tentative_continuity_count,
        contested_continuity_count=contested_continuity_count,
        historical_continuity_count=historical_continuity_count,
        current_support_reuse_label=_clean_text(support_coherence.get("claim_support_reuse_label")),
        contested_flag=bool(support_coherence.get("claim_current_support_contested_flag")),
        degraded_flag=bool(support_coherence.get("claim_current_posture_degraded_flag")),
        historical_stronger_flag=bool(support_coherence.get("claim_historical_support_stronger_than_current_flag")),
    )
    broader_reuse_label = broader["broader_reuse_label"]
    broader_continuity_label = broader["broader_continuity_label"]
    future_reuse_candidacy_label = broader["future_reuse_candidacy_label"]
    cluster_scope = assess_continuity_cluster_promotion(
        active_support_count=_safe_int(chronology.get("current_support_count")),
        continuity_evidence_count=exact_match_count,
        governing_continuity_count=governing_continuity_count,
        tentative_continuity_count=tentative_continuity_count,
        contested_continuity_count=contested_continuity_count,
        historical_continuity_count=historical_continuity_count,
        broader_reuse_label=broader_reuse_label,
        broader_continuity_label=broader_continuity_label,
        future_reuse_candidacy_label=future_reuse_candidacy_label,
        contested_flag=bool(support_coherence.get("claim_current_support_contested_flag")),
        degraded_flag=bool(support_coherence.get("claim_current_posture_degraded_flag")),
        historical_stronger_flag=bool(support_coherence.get("claim_historical_support_stronger_than_current_flag")),
    )
    continuity_cluster_posture_label = cluster_scope["continuity_cluster_posture_label"]
    promotion_candidate_posture_label = cluster_scope["promotion_candidate_posture_label"]
    promotion_boundary = assess_governed_promotion_boundary(
        active_support_count=_safe_int(chronology.get("current_support_count")),
        continuity_evidence_count=exact_match_count,
        governing_continuity_count=governing_continuity_count,
        tentative_continuity_count=tentative_continuity_count,
        contested_continuity_count=contested_continuity_count,
        historical_continuity_count=historical_continuity_count,
        broader_reuse_label=broader_reuse_label,
        broader_continuity_label=broader_continuity_label,
        continuity_cluster_posture_label=continuity_cluster_posture_label,
        promotion_candidate_posture_label=promotion_candidate_posture_label,
        contested_flag=bool(support_coherence.get("claim_current_support_contested_flag")),
        degraded_flag=bool(support_coherence.get("claim_current_posture_degraded_flag")),
        historical_stronger_flag=bool(support_coherence.get("claim_historical_support_stronger_than_current_flag")),
    )
    promotion_stability_label = promotion_boundary["promotion_stability_label"]
    promotion_gate_status_label = promotion_boundary["promotion_gate_status_label"]
    promotion_block_reason_label = promotion_boundary["promotion_block_reason_label"]

    if broader_reuse_label == BROADER_REUSE_STRONG:
        broader_reuse_summary = (
            f"{candidate_label} has coherent current support plus {governing_continuity_count} closely related claim context"
            f"{'' if governing_continuity_count == 1 else 's'} with posture-governing continuity, so broader governed reuse is stronger than this claim alone."
        )
    elif broader_reuse_label == BROADER_REUSE_CONTRADICTION_LIMITED:
        broader_reuse_summary = (
            f"{candidate_label} should influence related claims only cautiously because contested, degraded, or contradiction-heavy history limits cleaner broader reuse."
        )
    elif broader_reuse_label == BROADER_REUSE_HISTORICAL_ONLY:
        broader_reuse_summary = (
            f"{candidate_label} remains informative as historical broader context, but it should not be treated as strong current reuse across related claims."
        )
    elif broader_reuse_label == BROADER_REUSE_SELECTIVE:
        broader_reuse_summary = (
            f"{candidate_label} has some related-claim continuity, but broader reuse should stay selective because the surrounding continuity is limited, mixed, or partly historical."
        )
    else:
        broader_reuse_summary = (
            f"{candidate_label} is still mainly meaningful for this claim itself. Related-claim continuity is too sparse for broader governed reuse."
        )

    if broader_continuity_label == BROADER_CONTINUITY_COHERENT:
        future_prefix = "coherent broader continuity"
    elif broader_continuity_label == BROADER_CONTINUITY_CONTESTED:
        future_prefix = "contested broader continuity"
    elif broader_continuity_label == BROADER_CONTINUITY_HISTORICAL:
        future_prefix = "historical-heavy broader continuity"
    elif broader_continuity_label == BROADER_CONTINUITY_SELECTIVE:
        future_prefix = "selective broader continuity"
    else:
        future_prefix = "little broader continuity"

    if future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_STRONG:
        future_reuse_candidacy_summary = (
            f"{candidate_label} now looks like a stronger later candidate for broader governed reuse because current support and {future_prefix} are both present."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_SELECTIVE:
        future_reuse_candidacy_summary = (
            f"{candidate_label} is only a selective future reuse candidate. Stronger related-claim continuity or cleaner present posture would be needed for broader governed reuse."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED:
        future_reuse_candidacy_summary = (
            f"{candidate_label}'s future reuse candidacy is contradiction-limited because mixed or degraded history still weakens broader claim-to-claim carryover."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_HISTORICAL_ONLY:
        future_reuse_candidacy_summary = (
            f"{candidate_label}'s broader value is mainly historical context right now, so future governed reuse should not be treated as current-ready."
        )
    else:
        future_reuse_candidacy_summary = (
            f"{candidate_label} is currently a local-only support history. Broader future reuse would need clearer related-claim continuity first."
        )

    if continuity_cluster_posture_label == CONTINUITY_CLUSTER_PROMOTION_CANDIDATE:
        continuity_cluster_posture_summary = (
            f"{candidate_label} belongs to a promotion-candidate claim-family continuity cluster: current support is coherent enough that related claim context may later justify broader governed promotion."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_SELECTIVE:
        continuity_cluster_posture_summary = (
            f"{candidate_label} sits in a selective claim-family continuity cluster: there is enough governed continuity to matter, but it remains too bounded for stronger promotion."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTRADICTION_LIMITED:
        continuity_cluster_posture_summary = (
            f"{candidate_label} sits in a contradiction-limited claim-family continuity cluster: mixed, contested, or degraded history keeps the cluster visible but not cleanly promotable."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_HISTORICAL:
        continuity_cluster_posture_summary = (
            f"{candidate_label} sits in a historical-heavy claim-family continuity cluster: earlier continuity remains informative, but mainly as historical context rather than stronger current carryover."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTEXT_ONLY:
        continuity_cluster_posture_summary = (
            f"{candidate_label} has claim-family continuity that remains context-only right now. Related history is visible, but it should not travel far beyond contextual read-across."
        )
    else:
        continuity_cluster_posture_summary = (
            f"{candidate_label} does not yet sit in a meaningful broader claim-family continuity cluster, so support remains local to this claim picture."
        )

    if promotion_candidate_posture_label == PROMOTION_CANDIDATE_STRONG:
        promotion_candidate_posture_summary = (
            f"{candidate_label} is a stronger broader governed promotion candidate later if the current claim-family continuity remains coherent."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_SELECTIVE:
        promotion_candidate_posture_summary = (
            f"{candidate_label} is only a selective broader promotion candidate. Stronger or cleaner claim-family continuity would still be needed."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_CONTRADICTION_LIMITED:
        promotion_candidate_posture_summary = (
            f"{candidate_label} is not a clean promotion candidate because contradiction-heavy or degraded continuity still limits governed carryover."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_HISTORICAL_ONLY:
        promotion_candidate_posture_summary = (
            f"{candidate_label} contributes mainly historical promotion context right now. That continuity should inform review, not behave like a current broader promotion candidate."
        )
    else:
        promotion_candidate_posture_summary = (
            f"{candidate_label}'s continuity is still context-only rather than a broader governed promotion candidate."
        )

    if promotion_stability_label == PROMOTION_STABILITY_STABLE:
        promotion_stability_summary = (
            f"{candidate_label}'s claim-family continuity is stable enough for governed promotion review: current support and related continuity remain coherent under bounded rules."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_SELECTIVE:
        promotion_stability_summary = (
            f"{candidate_label}'s claim-family continuity is only selectively stable: there is enough governed continuity to matter, but stronger promotion would still require cleaner or broader support stability."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_UNSTABLE:
        promotion_stability_summary = (
            f"{candidate_label}'s claim-family continuity is unstable under contradiction pressure, so broader promotion should remain blocked or quarantined for now."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_HISTORICAL:
        promotion_stability_summary = (
            f"{candidate_label}'s claim-family continuity is historical-heavy rather than stably current, so it should remain review context rather than a clean promotion basis."
        )
    else:
        promotion_stability_summary = (
            f"{candidate_label}'s claim-family continuity does not yet show enough governed stability for broader promotion review."
        )

    if promotion_gate_status_label == PROMOTION_GATE_PROMOTABLE:
        promotion_gate_status_summary = (
            f"{candidate_label}'s claim-family continuity is promotable under bounded governed rules if the current coherent posture continues to hold."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_SELECTIVE:
        promotion_gate_status_summary = (
            f"{candidate_label}'s claim-family continuity is only selectively promotable: it may justify bounded broader carryover later, but still with caution."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_DOWNGRADED:
        promotion_gate_status_summary = (
            f"{candidate_label}'s claim-family continuity has been downgraded from a stronger promotion posture because newer evidence now weakens how cleanly the continuity should travel."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_QUARANTINED:
        promotion_gate_status_summary = (
            f"{candidate_label}'s claim-family continuity is quarantined from stronger promotion because contradiction-heavy and degraded history make the cluster too unstable."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_BLOCKED:
        promotion_gate_status_summary = (
            f"{candidate_label}'s claim-family continuity is still only a candidate and remains blocked from broader promotion under the current bounded rules."
        )
    else:
        promotion_gate_status_summary = (
            f"{candidate_label}'s claim-family continuity is not yet a governed promotion candidate and should remain local or contextual."
        )

    if promotion_block_reason_label == PROMOTION_BLOCK_NONE:
        promotion_block_reason_summary = (
            f"No material promotion block is currently recorded for {candidate_label}'s claim-family continuity."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_LOCAL_ONLY:
        promotion_block_reason_summary = (
            f"{candidate_label}'s support history is still mainly local-only, so there is not enough broader continuity to justify promotion review."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_CONTEXT_ONLY:
        promotion_block_reason_summary = (
            f"{candidate_label}'s related continuity remains context-only: it is useful for review, but not promotable under current governed rules."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_SELECTIVE_ONLY:
        promotion_block_reason_summary = (
            f"{candidate_label}'s continuity is still selective only. That continuity may matter later, but it is not broad or clean enough for fully promotable posture."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_CONTRADICTION:
        promotion_block_reason_summary = (
            f"{candidate_label}'s promotion boundary is limited by contradiction-heavy history, so broader promotion should remain blocked."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_DEGRADED:
        promotion_block_reason_summary = (
            f"{candidate_label}'s promotion boundary is limited by degraded present posture, so earlier stronger continuity should not stay silently promotable."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_HISTORICAL:
        promotion_block_reason_summary = (
            f"{candidate_label}'s continuity is mainly historical-heavy right now, so its value is contextual rather than broadly promotable."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_DOWNGRADED:
        promotion_block_reason_summary = (
            f"{candidate_label}'s continuity was downgraded by newer contradictory or weaker present evidence, so its broader role should be reduced rather than silently preserved."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_QUARANTINED:
        promotion_block_reason_summary = (
            f"{candidate_label}'s continuity is quarantined because instability across present support and contradiction pressure makes stronger promotion unsafe."
        )
    else:
        promotion_block_reason_summary = (
            f"{candidate_label}'s continuity does not yet satisfy enough governed stability conditions for broader promotion."
        )

    return {
        "claim_broader_reuse_label": broader_reuse_label,
        "claim_broader_reuse_summary": broader_reuse_summary,
        "claim_future_reuse_candidacy_label": future_reuse_candidacy_label,
        "claim_future_reuse_candidacy_summary": future_reuse_candidacy_summary,
        "claim_continuity_cluster_posture_label": continuity_cluster_posture_label,
        "claim_continuity_cluster_posture_summary": continuity_cluster_posture_summary,
        "claim_promotion_candidate_posture_label": promotion_candidate_posture_label,
        "claim_promotion_candidate_posture_summary": promotion_candidate_posture_summary,
        "claim_promotion_stability_label": promotion_stability_label,
        "claim_promotion_stability_summary": promotion_stability_summary,
        "claim_promotion_gate_status_label": promotion_gate_status_label,
        "claim_promotion_gate_status_summary": promotion_gate_status_summary,
        "claim_promotion_block_reason_label": promotion_block_reason_label,
        "claim_promotion_block_reason_summary": promotion_block_reason_summary,
    }


def _claim_source_class_fields(
    claim: dict[str, Any],
    *,
    updates: list[dict[str, Any]] | None,
) -> dict[str, str]:
    claim = claim if isinstance(claim, dict) else {}
    updates = updates if isinstance(updates, list) else []
    candidate_label = _clean_text(
        ((claim.get("candidate_reference") or {}) if isinstance(claim.get("candidate_reference"), dict) else {}).get(
            "candidate_label"
        )
        or claim.get("candidate_id"),
        default="This claim",
    )
    labels = [
        _clean_text((update.get("metadata") or {}).get("source_class_label"))
        for update in updates
        if isinstance(update, dict)
    ]
    labels = [label for label in labels if label]
    precedence = [
        SOURCE_CLASS_UNKNOWN,
        SOURCE_CLASS_AI_DERIVED,
        SOURCE_CLASS_UNCONTROLLED_UPLOAD,
        SOURCE_CLASS_DERIVED_EXTRACTED,
        SOURCE_CLASS_AFFILIATED,
        SOURCE_CLASS_INTERNAL_GOVERNED,
        SOURCE_CLASS_CURATED,
    ]
    if not labels:
        label = SOURCE_CLASS_UNKNOWN
        summary = (
            f"{candidate_label} does not yet have a claim-level governed evidence source path, so source class stays unknown and broader trust remains conservative."
        )
    else:
        label = min(labels, key=lambda item: precedence.index(item) if item in precedence else 0)
        mixed_source_classes = len(set(labels)) > 1
        if label == SOURCE_CLASS_CURATED:
            summary = (
                f"{candidate_label} is currently supported by curated or benchmark-like governed evidence, which is the strongest bounded source class present for this claim."
            )
        elif label == SOURCE_CLASS_INTERNAL_GOVERNED:
            summary = (
                f"{candidate_label} is currently supported by internally governed experimental evidence linked into the claim workflow."
            )
        elif label == SOURCE_CLASS_AFFILIATED:
            summary = (
                f"{candidate_label} currently depends on partner or affiliated evidence paths, so broader trust remains bounded even when the source is visible."
            )
        elif label == SOURCE_CLASS_DERIVED_EXTRACTED:
            summary = (
                f"{candidate_label} currently depends on derived, extracted, or retrieved context rather than only direct governed observation."
            )
        elif label == SOURCE_CLASS_UNCONTROLLED_UPLOAD:
            summary = (
                f"{candidate_label} currently depends on uncontrolled uploaded evidence, so it may remain locally useful while broader trust stays constrained."
            )
        elif label == SOURCE_CLASS_AI_DERIVED:
            summary = (
                f"{candidate_label} currently depends on AI-derived interpretation, which should remain bounded and non-authoritative for broader influence."
            )
        else:
            summary = (
                f"{candidate_label}'s governed source class remains unknown, so stronger broader trust should not be inferred from the current record alone."
            )
        if mixed_source_classes:
            summary += " Mixed source classes are present, so the claim is summarized conservatively using the weakest currently visible source path."
    return {
        "claim_source_class_label": label,
        "claim_source_class_summary": summary,
    }


def _claim_trust_review_fields(
    claim: dict[str, Any],
    *,
    chronology: dict[str, Any] | None,
    support_coherence: dict[str, Any] | None,
    broader_reuse: dict[str, Any] | None,
    updates: list[dict[str, Any]] | None,
) -> dict[str, str]:
    claim = claim if isinstance(claim, dict) else {}
    chronology = chronology if isinstance(chronology, dict) else {}
    support_coherence = support_coherence if isinstance(support_coherence, dict) else {}
    broader_reuse = broader_reuse if isinstance(broader_reuse, dict) else {}
    updates = updates if isinstance(updates, list) else []
    candidate_label = _clean_text(
        ((claim.get("candidate_reference") or {}) if isinstance(claim.get("candidate_reference"), dict) else {}).get(
            "candidate_label"
        )
        or claim.get("candidate_id"),
        default="This claim",
    )
    source_class = _claim_source_class_fields(claim, updates=updates)
    provenance_counts = rollup_provenance_confidence(
        [
            (update.get("metadata") or {}).get("provenance_confidence_label")
            for update in updates
            if isinstance(update, dict)
        ]
    )
    if provenance_counts["strong_count"] > 0:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_STRONG
        provenance_confidence_summary = (
            f"{candidate_label} is supported by at least {provenance_counts['strong_count']} stronger-provenance evidence path, which helps bounded broader trust."
        )
    elif provenance_counts["moderate_count"] > 0:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_MODERATE
        provenance_confidence_summary = (
            f"{candidate_label} has moderate provenance support overall: some lineage is visible, but broader trust should still stay cautious."
        )
    elif provenance_counts["weak_count"] > 0:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_WEAK
        provenance_confidence_summary = (
            f"{candidate_label} remains weakly grounded for broader influence because current evidence provenance is mostly uncontrolled or otherwise limited."
        )
    else:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_UNKNOWN
        provenance_confidence_summary = (
            f"{candidate_label} does not yet have enough explicit provenance detail for stronger broader trust."
        )

    posture = assess_governed_evidence_posture(
        source_class_label=source_class["claim_source_class_label"],
        provenance_confidence_label=provenance_confidence_label,
        promotion_gate_status_label=_clean_text(broader_reuse.get("claim_promotion_gate_status_label")),
        promotion_block_reason_label=_clean_text(broader_reuse.get("claim_promotion_block_reason_label")),
        active_support_count=_safe_int(chronology.get("current_support_count")),
        accepted_support_count=sum(
            1
            for update in updates
            if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.accepted.value
        ),
        candidate_context=bool(_safe_int(chronology.get("current_support_count")) or _safe_int(chronology.get("historical_support_count"))),
        contested_flag=bool(support_coherence.get("claim_current_support_contested_flag")),
        degraded_flag=bool(support_coherence.get("claim_current_posture_degraded_flag")),
        historical_stronger_flag=bool(support_coherence.get("claim_historical_support_stronger_than_current_flag")),
        local_only_default=True,
    )

    trust_tier_label = posture["trust_tier_label"]
    if trust_tier_label == TRUST_TIER_GOVERNED:
        trust_tier_summary = (
            f"{candidate_label} now has governed-trusted evidence posture for bounded broader consideration because claim support, provenance, and promotion boundary all remain sufficiently strong."
        )
    elif trust_tier_label == TRUST_TIER_CANDIDATE:
        trust_tier_summary = (
            f"{candidate_label} has candidate-level broader trust posture: it is important enough to review for broader influence, but it has not earned governed-trusted status."
        )
    else:
        trust_tier_summary = (
            f"{candidate_label}'s evidence remains local-only by default. It can shape local reasoning now, but broader influence has not been earned."
        )

    review_status_label = posture["governed_review_status_label"]
    review_reason_label = posture["governed_review_reason_label"]
    review_status_summary = posture["governed_review_status_summary"]
    review_reason_summary = posture["governed_review_reason_summary"]
    if review_status_label == REVIEW_STATUS_APPROVED:
        review_status_summary = (
            f"{candidate_label} is approved for bounded broader governed consideration, while still remaining explicitly non-final."
        )
        review_reason_summary = (
            f"{candidate_label}'s current trust basis is strong enough for bounded broader consideration because provenance and continuity remain coherent."
        )
    elif review_status_label == REVIEW_STATUS_BLOCKED:
        review_status_summary = (
            f"{candidate_label} is a broader review candidate, but it remains blocked from stronger broader influence right now."
        )
    elif review_status_label == REVIEW_STATUS_DEFERRED:
        review_status_summary = (
            f"{candidate_label} is review-candidate material, but broader trust is deferred until stronger provenance or continuity is available."
        )
    elif review_status_label == REVIEW_STATUS_DOWNGRADED:
        review_status_summary = (
            f"{candidate_label} was previously closer to broader trust, but newer evidence has downgraded that posture."
        )
    elif review_status_label == REVIEW_STATUS_QUARANTINED:
        review_status_summary = (
            f"{candidate_label} remains visible as context, but broader trust is quarantined because the continuity picture is too unstable."
        )
    elif review_status_label == REVIEW_STATUS_CANDIDATE:
        review_status_summary = (
            f"{candidate_label} is a broader review candidate only; stronger evidence trust would still be needed before broader influence should increase."
        )
    else:
        review_status_summary = (
            f"{candidate_label} has no broader governed review posture yet and should remain local-first."
        )

    if review_reason_label == REVIEW_REASON_WEAK_PROVENANCE:
        review_reason_summary = f"Weak or unknown provenance currently keeps {candidate_label} out of stronger broader trust."
    elif review_reason_label == REVIEW_REASON_CONTRADICTION:
        review_reason_summary = f"Contradiction-heavy history currently blocks {candidate_label} from stronger broader influence."
    elif review_reason_label == REVIEW_REASON_DEGRADED:
        review_reason_summary = f"Degraded present posture keeps {candidate_label} from behaving like trusted broader carryover."
    elif review_reason_label == REVIEW_REASON_HISTORICAL:
        review_reason_summary = f"{candidate_label}'s broader value is mainly historical context right now, not current broader trust."
    elif review_reason_label == REVIEW_REASON_SELECTIVE:
        review_reason_summary = f"{candidate_label}'s broader continuity remains too selective and bounded for cleaner broader trust."
    elif review_reason_label == REVIEW_REASON_DOWNGRADED:
        review_reason_summary = f"Newer weakening evidence downgraded {candidate_label}'s broader-trust posture."
    elif review_reason_label == REVIEW_REASON_QUARANTINED:
        review_reason_summary = f"Instability across contradiction-heavy continuity quarantines {candidate_label} from stronger broader influence."
    elif review_reason_label == REVIEW_REASON_APPROVED:
        review_reason_summary = f"{candidate_label} is allowed bounded broader consideration because stronger trust and continuity conditions currently hold."
    elif review_reason_label == REVIEW_REASON_LOCAL_DEFAULT:
        review_reason_summary = f"{candidate_label} remains local-only by default until stronger broader-trust conditions are satisfied."
    elif review_reason_label == REVIEW_REASON_STRONGER_TRUST_NEEDED:
        review_reason_summary = f"{candidate_label} would need stronger trust, provenance, or continuity before broader influence should increase."

    return {
        "claim_source_class_label": source_class["claim_source_class_label"],
        "claim_source_class_summary": source_class["claim_source_class_summary"],
        "claim_trust_tier_label": trust_tier_label,
        "claim_trust_tier_summary": trust_tier_summary,
        "claim_provenance_confidence_label": provenance_confidence_label,
        "claim_provenance_confidence_summary": provenance_confidence_summary,
        "claim_governed_review_status_label": review_status_label,
        "claim_governed_review_status_summary": review_status_summary,
        "claim_governed_review_reason_label": review_reason_label,
        "claim_governed_review_reason_summary": review_reason_summary,
    }


def _claim_chronology_fields(updates: list[dict[str, Any]] | None) -> dict[str, Any]:
    updates = updates if isinstance(updates, list) else []
    current_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower()
        in {
            BeliefUpdateGovernanceStatus.proposed.value,
            BeliefUpdateGovernanceStatus.accepted.value,
        }
    )
    historical_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
    )
    rejected_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.rejected.value
    )
    if current_count > 0:
        label = "Active governed support"
        summary = (
            f"This claim currently has {current_count} active governed support change"
            f"{'' if current_count == 1 else 's'}"
        )
        extras: list[str] = []
        if historical_count:
            extras.append(
                f"{historical_count} superseded historical record{'' if historical_count == 1 else 's'}"
            )
        if rejected_count:
            extras.append(
                f"{rejected_count} rejected record{'' if rejected_count == 1 else 's'}"
            )
        if extras:
            summary = f"{summary} and keeps {' plus '.join(extras)} visible for context."
        else:
            summary = f"{summary}."
    elif historical_count > 0 and rejected_count <= 0:
        label = "Historical support only"
        summary = (
            f"This claim currently has no active governed support and keeps {historical_count} superseded historical record"
            f"{'' if historical_count == 1 else 's'} visible."
        )
    elif rejected_count > 0 and historical_count <= 0:
        label = "Rejected support only"
        summary = (
            f"This claim currently has no active governed support and keeps {rejected_count} rejected support record"
            f"{'' if rejected_count == 1 else 's'} visible."
        )
    elif historical_count > 0 or rejected_count > 0:
        label = "Historical or rejected support only"
        history_total = historical_count + rejected_count
        summary = (
            f"This claim currently has no active governed support and keeps {history_total} historical or rejected support record"
            f"{'' if history_total == 1 else 's'} visible."
        )
    else:
        label = "No governed support yet"
        summary = "This claim does not currently have a governed support-change record."
    return {
        "claim_support_role_label": label,
        "current_support_count": current_count,
        "historical_support_count": historical_count,
        "rejected_support_count": rejected_count,
        "claim_chronology_summary_text": summary,
    }


def _claim_support_basis_fields(updates: list[dict[str, Any]] | None) -> dict[str, Any]:
    updates = updates if isinstance(updates, list) else []
    active_updates = [
        update
        for update in updates
        if _clean_text(update.get("governance_status")).lower()
        in {
            BeliefUpdateGovernanceStatus.proposed.value,
            BeliefUpdateGovernanceStatus.accepted.value,
        }
    ]
    if not active_updates:
        return {
            "claim_support_basis_mix_label": "No governed support yet",
            "claim_support_basis_mix_summary": (
                "This claim has no active governed support change, so no current support-basis mix is recorded."
            ),
            "claim_observed_label_support_count": 0,
            "claim_numeric_rule_based_support_count": 0,
            "claim_unresolved_basis_count": 0,
            "claim_weak_basis_count": 0,
        }

    observed_label_support_count = 0
    numeric_rule_based_support_count = 0
    unresolved_basis_count = 0
    weak_basis_count = 0
    for update in active_updates:
        if not isinstance(update, dict):
            continue
        metadata = update.get("metadata") if isinstance(update.get("metadata"), dict) else {}
        interpretation_basis = _clean_text(update.get("result_interpretation_basis") or metadata.get("result_interpretation_basis"))
        support_input_quality_label = _clean_text(
            update.get("support_input_quality_label") or metadata.get("support_input_quality_label")
        )
        numeric_result_resolution_label = _clean_text(
            update.get("numeric_result_resolution_label") or metadata.get("numeric_result_resolution_label")
        )
        update_direction = _clean_text(update.get("update_direction"))
        if interpretation_basis == "Observed label":
            observed_label_support_count += 1
        elif interpretation_basis == "Numeric outcome under current target rule":
            numeric_rule_based_support_count += 1
        if support_input_quality_label == "Weak interpretation basis":
            weak_basis_count += 1
        if update_direction == "unresolved" or numeric_result_resolution_label == "Unresolved under current numeric basis":
            unresolved_basis_count += 1

    if (
        observed_label_support_count > 0
        and observed_label_support_count >= max(numeric_rule_based_support_count, unresolved_basis_count)
        and observed_label_support_count >= weak_basis_count
        and numeric_rule_based_support_count == 0
    ):
        label = "Grounded mostly in observed labels"
        summary = (
            f"This claim's current governed support is grounded mostly in observed labels ({observed_label_support_count}) and remains bounded rather than final."
        )
    elif (
        numeric_rule_based_support_count > 0
        and numeric_rule_based_support_count >= max(observed_label_support_count, unresolved_basis_count)
        and numeric_rule_based_support_count >= weak_basis_count
        and observed_label_support_count == 0
    ):
        label = "Includes bounded numeric interpretation"
        summary = (
            f"This claim's current governed support includes bounded numeric interpretation under current target rules ({numeric_rule_based_support_count}) and should still be read cautiously."
        )
    elif unresolved_basis_count > 0 and unresolved_basis_count >= max(
        observed_label_support_count,
        numeric_rule_based_support_count,
    ):
        label = "Mostly unresolved or weak-basis"
        summary = (
            f"This claim's current governed support remains largely tentative because {unresolved_basis_count} active support change"
            f"{'' if unresolved_basis_count == 1 else 's'} remain unresolved under the current basis."
        )
    else:
        label = "Mixed support basis"
        summary = (
            f"This claim's current governed support uses a mixed basis: {observed_label_support_count} observed-label, "
            f"{numeric_rule_based_support_count} numeric-rule-based, {unresolved_basis_count} unresolved, and "
            f"{weak_basis_count} weak-basis support change{'s' if weak_basis_count != 1 else ''}."
        )

    return {
        "claim_support_basis_mix_label": label,
        "claim_support_basis_mix_summary": summary,
        "claim_observed_label_support_count": observed_label_support_count,
        "claim_numeric_rule_based_support_count": numeric_rule_based_support_count,
        "claim_unresolved_basis_count": unresolved_basis_count,
        "claim_weak_basis_count": weak_basis_count,
    }


def _claim_support_quality_fields(
    claim: dict[str, Any],
    updates: list[dict[str, Any]] | None,
    *,
    chronology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claim = claim if isinstance(claim, dict) else {}
    updates = updates if isinstance(updates, list) else []
    chronology = chronology if isinstance(chronology, dict) else _claim_chronology_fields(updates)
    current_support_count = _safe_int(chronology.get("current_support_count"))
    historical_support_count = _safe_int(chronology.get("historical_support_count"))
    candidate_label = _clean_text(
        ((claim.get("candidate_reference") or {}) if isinstance(claim.get("candidate_reference"), dict) else {}).get(
            "candidate_label"
        )
        or claim.get("candidate_id"),
        default="This claim",
    )
    if current_support_count <= 0:
        if historical_support_count > 0:
            return {
                "claim_support_quality_label": "Historical support context only",
                "claim_support_quality_summary": (
                    f"{candidate_label} keeps historical support context visible, but no current active support quality can be attributed to it now."
                ),
            }
        return {
            "claim_support_quality_label": "No active support quality yet",
            "claim_support_quality_summary": (
                f"{candidate_label} does not yet have active governed support, so no current support-quality picture is available."
            ),
        }

    active_updates = [
        update
        for update in updates
        if _clean_text(update.get("governance_status")).lower()
        in {
            BeliefUpdateGovernanceStatus.proposed.value,
            BeliefUpdateGovernanceStatus.accepted.value,
        }
    ]
    support_quality_counts = rollup_quality_labels(
        [
            (update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label"))
            or classify_belief_update_support_quality(update).get("support_quality_label")
            for update in active_updates
        ]
    )
    if support_quality_counts["decision_useful_count"] > 0 and support_quality_counts["weak_count"] <= 0 and support_quality_counts["context_limited_count"] <= 0:
        return {
            "claim_support_quality_label": "Decision-useful current active support",
            "claim_support_quality_summary": (
                f"{candidate_label} currently has active support that is decision-useful enough for bounded follow-up, while still remaining bounded rather than final."
            ),
        }
    if support_quality_counts["weak_count"] >= max(
        support_quality_counts["decision_useful_count"],
        support_quality_counts["limited_count"],
        support_quality_counts["context_limited_count"],
    ) and support_quality_counts["weak_count"] > 0:
        return {
            "claim_support_quality_label": "Weak or provisional current support",
            "claim_support_quality_summary": (
                f"{candidate_label} currently has active support, but much of it remains weak or unresolved under the available basis."
            ),
        }
    if support_quality_counts["context_limited_count"] >= max(
        support_quality_counts["decision_useful_count"],
        support_quality_counts["limited_count"],
        support_quality_counts["weak_count"],
    ) and support_quality_counts["context_limited_count"] > 0:
        return {
            "claim_support_quality_label": "Context-limited current support",
            "claim_support_quality_summary": (
                f"{candidate_label} currently has active support, but assay or target-context limits keep that support from being strongly decision-useful yet."
            ),
        }
    if support_quality_counts["decision_useful_count"] > 0:
        return {
            "claim_support_quality_label": "Mixed-strength current support",
            "claim_support_quality_summary": (
                f"{candidate_label} currently has some decision-useful active support, but it is still mixed with more limited active support and should be read cautiously."
            ),
        }
    return {
        "claim_support_quality_label": "Current active support remains limited",
        "claim_support_quality_summary": (
            f"{candidate_label} currently has active governed support, but that support remains limited for stronger follow-up."
        ),
    }


def _claim_governed_support_posture_fields(
    claim: dict[str, Any],
    updates: list[dict[str, Any]] | None,
    *,
    chronology: dict[str, Any] | None = None,
    support_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claim = claim if isinstance(claim, dict) else {}
    updates = updates if isinstance(updates, list) else []
    chronology = chronology if isinstance(chronology, dict) else _claim_chronology_fields(updates)
    support_quality = support_quality if isinstance(support_quality, dict) else _claim_support_quality_fields(
        claim,
        updates,
        chronology=chronology,
    )
    current_support_count = _safe_int(chronology.get("current_support_count"))
    historical_support_count = _safe_int(chronology.get("historical_support_count"))
    rejected_support_count = _safe_int(chronology.get("rejected_support_count"))
    candidate_label = _clean_text(
        ((claim.get("candidate_reference") or {}) if isinstance(claim.get("candidate_reference"), dict) else {}).get(
            "candidate_label"
        )
        or claim.get("candidate_id"),
        default="This claim",
    )
    posture_counts = rollup_governed_support_postures(
        [
            (update.get("governed_support_posture_label") or (update.get("metadata") or {}).get("governed_support_posture_label"))
            or classify_governed_support_posture(update).get("governed_support_posture_label")
            for update in updates
        ]
    )
    historical_decision_useful_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
        and (
            _clean_text(update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label"))
            or classify_belief_update_support_quality(update).get("support_quality_label")
        )
        == SUPPORT_QUALITY_DECISION_USEFUL
    )
    if current_support_count <= 0:
        if historical_decision_useful_count > 0:
            return {
                "claim_governed_support_posture_label": "Historical support remains informative, not current",
                "claim_governed_support_posture_summary": (
                    f"{candidate_label} keeps historically informative support visible, but stronger prior support is now superseded and no longer governs present posture."
                ),
            }
        if historical_support_count > 0:
            return {
                "claim_governed_support_posture_label": "Historical support only",
                "claim_governed_support_posture_summary": (
                    f"{candidate_label} keeps historical support visible for context, but none of it currently governs present posture."
                ),
            }
        if rejected_support_count > 0:
            return {
                "claim_governed_support_posture_label": "No current governed basis",
                "claim_governed_support_posture_summary": (
                    f"{candidate_label} has no current governed basis; only rejected support history remains visible."
                ),
            }
        return {
            "claim_governed_support_posture_label": "No current governed basis",
            "claim_governed_support_posture_summary": (
                f"{candidate_label} does not yet have support that governs present posture."
            ),
        }
    if posture_counts["governing_count"] > 0:
        summary = (
            f"{candidate_label} currently has accepted support that governs present posture for bounded follow-up."
        )
        if historical_decision_useful_count > 0:
            summary += (
                f" {historical_decision_useful_count} older support record"
                f"{'' if historical_decision_useful_count == 1 else 's'} remain historical only after supersession."
            )
        return {
            "claim_governed_support_posture_label": "Current support governs present posture",
            "claim_governed_support_posture_summary": summary,
        }
    if posture_counts["accepted_limited_count"] > 0:
        return {
            "claim_governed_support_posture_label": "Accepted support remains limited-weight",
            "claim_governed_support_posture_summary": (
                f"{candidate_label} has accepted support, but that support is still limited or context-limited and should count only weakly in present posture."
            ),
        }
    if posture_counts["tentative_count"] > 0:
        if _clean_text(support_quality.get("claim_support_quality_label")) == "Context-limited current support":
            return {
                "claim_governed_support_posture_label": "Current support is context-limited and tentative",
                "claim_governed_support_posture_summary": (
                    f"{candidate_label} has current support, but it remains proposed and context-limited rather than posture-governing."
                ),
            }
        return {
            "claim_governed_support_posture_label": "Current support remains tentative",
            "claim_governed_support_posture_summary": (
                f"{candidate_label} has current support on paper, but it remains proposed and should stay tentative in present posture."
            ),
        }
    return {
        "claim_governed_support_posture_label": "Current support remains tentative",
        "claim_governed_support_posture_summary": (
            f"{candidate_label} has current support records, but none currently govern present posture strongly."
        ),
    }


def _claim_support_coherence_fields(
    claim: dict[str, Any],
    updates: list[dict[str, Any]] | None,
    *,
    chronology: dict[str, Any] | None = None,
    support_quality: dict[str, Any] | None = None,
    governed_posture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claim = claim if isinstance(claim, dict) else {}
    updates = updates if isinstance(updates, list) else []
    chronology = chronology if isinstance(chronology, dict) else _claim_chronology_fields(updates)
    support_quality = support_quality if isinstance(support_quality, dict) else _claim_support_quality_fields(
        claim,
        updates,
        chronology=chronology,
    )
    governed_posture = governed_posture if isinstance(governed_posture, dict) else _claim_governed_support_posture_fields(
        claim,
        updates,
        chronology=chronology,
        support_quality=support_quality,
    )
    active_updates = [
        update
        for update in updates
        if _clean_text(update.get("governance_status")).lower()
        in {
            BeliefUpdateGovernanceStatus.proposed.value,
            BeliefUpdateGovernanceStatus.accepted.value,
        }
    ]
    posture_counts = rollup_governed_support_postures(
        [
            (update.get("governed_support_posture_label") or (update.get("metadata") or {}).get("governed_support_posture_label"))
            or classify_governed_support_posture(update).get("governed_support_posture_label")
            for update in updates
        ]
    )
    support_quality_counts = rollup_quality_labels(
        [
            (update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label"))
            or classify_belief_update_support_quality(update).get("support_quality_label")
            for update in active_updates
        ]
    )
    historical_decision_useful_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
        and (
            _clean_text(update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label"))
            or classify_belief_update_support_quality(update).get("support_quality_label")
        )
        == SUPPORT_QUALITY_DECISION_USEFUL
    )
    coherence = assess_support_coherence(
        active_count=_safe_int(chronology.get("current_support_count")),
        accepted_count=sum(
            1
            for update in active_updates
            if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.accepted.value
        ),
        strengthened_count=sum(
            1 for update in active_updates if _clean_text(update.get("update_direction")).lower() == "strengthened"
        ),
        weakened_count=sum(
            1 for update in active_updates if _clean_text(update.get("update_direction")).lower() == "weakened"
        ),
        unresolved_count=sum(
            1 for update in active_updates if _clean_text(update.get("update_direction")).lower() == "unresolved"
        ),
        support_quality_counts=support_quality_counts,
        posture_counts=posture_counts,
        historical_decision_useful_count=historical_decision_useful_count,
        superseded_count=_safe_int(chronology.get("historical_support_count")),
    )
    candidate_label = _clean_text(
        ((claim.get("candidate_reference") or {}) if isinstance(claim.get("candidate_reference"), dict) else {}).get(
            "candidate_label"
        )
        or claim.get("candidate_id"),
        default="This claim",
    )
    support_coherence_summary = coherence["support_coherence_summary"]
    if candidate_label and support_coherence_summary:
        support_coherence_summary = f"{candidate_label}: {support_coherence_summary[0].lower()}{support_coherence_summary[1:]}"
    support_reuse_summary = coherence["support_reuse_summary"]
    if candidate_label and support_reuse_summary:
        support_reuse_summary = f"{candidate_label}: {support_reuse_summary[0].lower()}{support_reuse_summary[1:]}"
    return {
        "claim_support_coherence_label": coherence["support_coherence_label"],
        "claim_support_coherence_summary": support_coherence_summary,
        "claim_support_reuse_label": coherence["support_reuse_label"],
        "claim_support_reuse_summary": support_reuse_summary,
        "claim_current_support_contested_flag": coherence["current_support_contested_flag"],
        "claim_current_posture_degraded_flag": coherence["current_posture_degraded_flag"],
        "claim_historical_support_stronger_than_current_flag": coherence["historical_support_stronger_than_current_flag"],
        "claim_contradiction_pressure_count": coherence["contradiction_pressure_count"],
        "claim_weakly_reusable_support_count": coherence["weakly_reusable_support_count"],
    }


def _claim_actionability_fields(
    claim: dict[str, Any],
    updates: list[dict[str, Any]] | None,
    *,
    chronology: dict[str, Any] | None = None,
    support_basis: dict[str, Any] | None = None,
    support_quality: dict[str, Any] | None = None,
    governed_posture: dict[str, Any] | None = None,
    support_coherence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claim = claim if isinstance(claim, dict) else {}
    updates = updates if isinstance(updates, list) else []
    chronology = chronology if isinstance(chronology, dict) else _claim_chronology_fields(updates)
    support_basis = support_basis if isinstance(support_basis, dict) else _claim_support_basis_fields(updates)
    support_quality = support_quality if isinstance(support_quality, dict) else _claim_support_quality_fields(
        claim,
        updates,
        chronology=chronology,
    )
    governed_posture = governed_posture if isinstance(governed_posture, dict) else _claim_governed_support_posture_fields(
        claim,
        updates,
        chronology=chronology,
        support_quality=support_quality,
    )
    support_coherence = support_coherence if isinstance(support_coherence, dict) else _claim_support_coherence_fields(
        claim,
        updates,
        chronology=chronology,
        support_quality=support_quality,
        governed_posture=governed_posture,
    )

    current_support_count = _safe_int(chronology.get("current_support_count"))
    historical_support_count = _safe_int(chronology.get("historical_support_count"))
    rejected_support_count = _safe_int(chronology.get("rejected_support_count"))
    observed_label_support_count = _safe_int(support_basis.get("claim_observed_label_support_count"))
    numeric_rule_based_support_count = _safe_int(support_basis.get("claim_numeric_rule_based_support_count"))
    unresolved_basis_count = _safe_int(support_basis.get("claim_unresolved_basis_count"))
    weak_basis_count = _safe_int(support_basis.get("claim_weak_basis_count"))
    basis_label = _clean_text(support_basis.get("claim_support_basis_mix_label"))
    support_quality_label = _clean_text(support_quality.get("claim_support_quality_label"))
    governed_posture_label = _clean_text(governed_posture.get("claim_governed_support_posture_label"))
    coherence_label = _clean_text(support_coherence.get("claim_support_coherence_label"))
    contested_flag = bool(support_coherence.get("claim_current_support_contested_flag"))
    degraded_flag = bool(support_coherence.get("claim_current_posture_degraded_flag"))
    historical_stronger_flag = bool(support_coherence.get("claim_historical_support_stronger_than_current_flag"))
    historical_decision_useful_count = sum(
        1
        for update in updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
        and (
            _clean_text(update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label"))
            or classify_belief_update_support_quality(update).get("support_quality_label")
        )
        == SUPPORT_QUALITY_DECISION_USEFUL
    )

    active_updates = [
        update
        for update in updates
        if _clean_text(update.get("governance_status")).lower()
        in {
            BeliefUpdateGovernanceStatus.proposed.value,
            BeliefUpdateGovernanceStatus.accepted.value,
        }
    ]
    accepted_active_count = sum(
        1
        for update in active_updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.accepted.value
    )
    proposed_active_count = sum(
        1
        for update in active_updates
        if _clean_text(update.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.proposed.value
    )
    has_historical_context = historical_support_count > 0
    has_rejected_only_context = rejected_support_count > 0 and current_support_count <= 0 and historical_support_count <= 0
    has_mixed_current_historical_context = current_support_count > 0 and historical_support_count > 0
    candidate_label = _clean_text(
        ((claim.get("candidate_reference") or {}) if isinstance(claim.get("candidate_reference"), dict) else {}).get(
            "candidate_label"
        )
        or claim.get("candidate_id"),
        default="This claim",
    )
    active_support_actionability_label = "No current active support"
    historical_support_actionability_label = "No historical support context"

    if current_support_count <= 0:
        if historical_support_count > 0:
            actionability_label = "Historically interesting, not currently action-ready"
            actionability_summary = (
                f"{candidate_label} remains historically interesting because only superseded support records are still visible, but that historical context should not drive current priority on its own."
            )
            if historical_decision_useful_count > 0:
                actionability_summary += (
                    f" {historical_decision_useful_count} superseded support record"
                    f"{'' if historical_decision_useful_count == 1 else 's'} previously looked more decision-useful, but that stronger basis is no longer current."
                )
            actionability_basis_label = "Historical interest only"
            actionability_basis_summary = (
                f"{candidate_label}'s current actionability is historical-context only: no active governed support remains, and {historical_support_count} superseded support record"
                f"{'' if historical_support_count == 1 else 's'} stay visible for context."
            )
            next_step_label = "Historically interesting, gather fresh evidence first"
            next_step_summary = (
                "Treat this claim as historical context for now and gather fresh evidence before prioritizing follow-up."
            )
            historical_support_actionability_label = "Historical context only"
            historical_interest_only_flag = True
        elif has_rejected_only_context:
            actionability_label = "No active governed support"
            actionability_summary = (
                f"{candidate_label} currently has no active governed support and only rejected support history, so it should not drive priority on its own."
            )
            actionability_basis_label = "No active governed support"
            actionability_basis_summary = (
                f"{candidate_label}'s current actionability has no active governed basis: only rejected support history is recorded."
            )
            next_step_label = "Insufficient governed basis"
            next_step_summary = (
                "Do not prioritize this claim from rejected-only history; gather a new governed support change before revisiting follow-up."
            )
            historical_interest_only_flag = False
        else:
            actionability_label = "No governed support yet"
            actionability_summary = (
                f"{candidate_label} does not yet have active governed support, so the current claim picture remains bounded and not action-ready."
            )
            actionability_basis_label = "No active governed support"
            actionability_basis_summary = (
                f"{candidate_label}'s current actionability has no active governed basis yet."
            )
            next_step_label = "Insufficient governed basis"
            next_step_summary = (
                "Gather an observed result or a governed support change before using this claim to drive follow-up priority."
            )
            historical_interest_only_flag = False
    elif degraded_flag and contested_flag:
        actionability_label = "Mixed basis, needs clarifying experiment"
        actionability_summary = (
            f"{candidate_label} still has current support records, but mixed and weakening evidence now contest and degrade present posture."
        )
        actionability_basis_label = "Contested and degraded current basis"
        actionability_basis_summary = (
            f"{candidate_label}'s current support is active on paper, but contradiction pressure means it should not drive strong follow-up."
        )
        next_step_label = "Clarify with targeted experiment"
        next_step_summary = (
            "Use a targeted clarifying experiment to separate reinforcing evidence from weakening evidence before stronger follow-up."
        )
        active_support_actionability_label = "Current active support is contested"
        if historical_stronger_flag or has_historical_context:
            historical_support_actionability_label = "Historical context remains stronger than current"
        historical_interest_only_flag = False
    elif degraded_flag or historical_stronger_flag:
        actionability_label = "Promising but needs stronger evidence"
        actionability_summary = (
            f"{candidate_label} still has some current support, but present posture is degraded by weakening evidence or stronger historical support."
        )
        actionability_basis_label = "Degraded current basis"
        actionability_basis_summary = (
            f"{candidate_label}'s current actionability should be discounted because present support is weaker than the surrounding evidence history suggests."
        )
        next_step_label = "Gather stronger evidence before stronger follow-up"
        next_step_summary = (
            "Gather stronger fresh evidence before treating this claim as current follow-up guidance."
        )
        active_support_actionability_label = "Current active support remains limited"
        if historical_stronger_flag:
            historical_support_actionability_label = "Historical context remains stronger than current"
        historical_interest_only_flag = False
    elif contested_flag:
        actionability_label = "Mixed basis, needs clarifying experiment"
        actionability_summary = (
            f"{candidate_label} has current support, but contradiction pressure from mixed active updates keeps the present basis contested."
        )
        actionability_basis_label = "Contested current basis"
        actionability_basis_summary = (
            f"{candidate_label}'s current actionability depends on active support that is not coherent enough to justify strong follow-up yet."
        )
        next_step_label = "Clarify with targeted experiment"
        next_step_summary = (
            "Use a targeted clarifying experiment to resolve contradiction pressure before treating this claim as stronger current guidance."
        )
        active_support_actionability_label = "Current active support is contested"
        if has_historical_context:
            historical_support_actionability_label = "Historical context still contributes"
        historical_interest_only_flag = False
    elif (
        support_quality_label == "Weak or provisional current support"
        or basis_label == "Mostly unresolved or weak-basis"
        or weak_basis_count >= current_support_count
        or unresolved_basis_count >= current_support_count
    ):
        actionability_label = "Weak-basis, do not prioritize yet"
        actionability_summary = (
            f"{candidate_label} remains largely tentative because its active governed support is still weak, provisional, or unresolved under the current evidence basis."
        )
        actionability_basis_label = "Current active support basis"
        actionability_basis_summary = (
            f"{candidate_label}'s current actionability depends on active governed support, but that active basis remains too weak or unresolved to justify priority."
        )
        next_step_label = "Do not prioritize yet"
        next_step_summary = (
            "Do not prioritize this claim yet; gather stronger observed support before moving it toward follow-up."
        )
        active_support_actionability_label = "Current active support remains limited"
        if has_historical_context:
            historical_support_actionability_label = "Historical context still contributes"
        historical_interest_only_flag = False
    elif (
        governed_posture_label == "Current support governs present posture"
        and support_quality_label == "Decision-useful current active support"
        and basis_label == "Grounded mostly in observed labels"
        and accepted_active_count > 0
        and unresolved_basis_count <= 0
        and weak_basis_count <= 0
    ):
        actionability_label = "Action-ready from current active support"
        if has_mixed_current_historical_context:
            actionability_summary = (
                f"{candidate_label} has current active governed support grounded mostly in observed labels, including {accepted_active_count} accepted support change"
                f"{'' if accepted_active_count == 1 else 's'}, so bounded follow-up is reasonable now while older historical support stays contextual only."
            )
            actionability_basis_label = "Current active support basis"
            actionability_basis_summary = (
                f"{candidate_label}'s present actionability is driven by {current_support_count} active governed support change"
                f"{'' if current_support_count == 1 else 's'}, while {historical_support_count} superseded historical record"
                f"{'' if historical_support_count == 1 else 's'} remain context only."
            )
        else:
            actionability_summary = (
                f"{candidate_label} has active governed support grounded mostly in observed labels, including {accepted_active_count} accepted support change"
                f"{'' if accepted_active_count == 1 else 's'}, so bounded follow-up is reasonable without implying proof."
            )
            actionability_basis_label = "Current active support basis"
            actionability_basis_summary = (
                f"{candidate_label}'s present actionability is grounded in current active governed support rather than historical context."
            )
        next_step_label = "Follow-up experiment is reasonable now"
        next_step_summary = (
            "A bounded follow-up experiment is reasonable now, while keeping the claim explicitly separate from validated truth."
        )
        active_support_actionability_label = "Current active support is decision-useful"
        if has_historical_context:
            historical_support_actionability_label = "Historical context remains secondary"
        historical_interest_only_flag = False
    elif governed_posture_label == "Accepted support remains limited-weight":
        actionability_label = "Promising but needs stronger evidence"
        actionability_summary = (
            f"{candidate_label} has accepted support, but that accepted support is still too limited or context-limited to fully justify follow-up."
        )
        actionability_basis_label = "Accepted but limited current basis"
        actionability_basis_summary = (
            f"{candidate_label}'s current actionability depends on accepted support, but that support counts only weakly in present posture."
        )
        next_step_label = "Gather stronger evidence before stronger follow-up"
        next_step_summary = (
            "Use the accepted support as bounded context, but gather stronger or cleaner evidence before treating the claim as follow-up-ready."
        )
        active_support_actionability_label = "Current active support remains limited"
        if has_historical_context:
            historical_support_actionability_label = "Historical context still contributes"
        historical_interest_only_flag = False
    elif governed_posture_label in {
        "Current support remains tentative",
        "Current support is context-limited and tentative",
    }:
        if support_quality_label == "Context-limited current support":
            actionability_label = "Mixed basis, needs clarifying experiment"
            actionability_summary = (
                f"{candidate_label} has current support, but it remains both tentative and context-limited, so clarification is more appropriate than stronger follow-up."
            )
            actionability_basis_label = "Tentative current support basis"
            actionability_basis_summary = (
                f"{candidate_label}'s current actionability depends on proposed support that is still context-limited and not yet posture-governing."
            )
            next_step_label = "Clarify with targeted experiment"
            next_step_summary = (
                "Use a targeted clarifying experiment to reduce context ambiguity before revisiting stronger follow-up."
            )
            active_support_actionability_label = "Current active support is context-limited"
        else:
            actionability_label = "Promising but needs stronger evidence"
            actionability_summary = (
                f"{candidate_label} has current support, but that support remains tentative rather than posture-governing, so it should not yet drive strong follow-up."
            )
            actionability_basis_label = "Tentative current support basis"
            actionability_basis_summary = (
                f"{candidate_label}'s current actionability depends on active support that is still proposed and tentative."
            )
            next_step_label = "Strengthen current support first"
            next_step_summary = (
                "Gather stronger or accepted support before treating this claim as present follow-up guidance."
            )
            active_support_actionability_label = "Current active support remains limited"
        if has_historical_context:
            historical_support_actionability_label = "Historical context still contributes"
        historical_interest_only_flag = False
    elif support_quality_label == "Context-limited current support":
        actionability_label = "Mixed basis, needs clarifying experiment"
        actionability_summary = (
            f"{candidate_label} has active support, but assay or target-context limitations keep that support from being clean enough for stronger follow-up."
        )
        actionability_basis_label = "Current active support basis"
        actionability_basis_summary = (
            f"{candidate_label}'s current actionability depends on active governed support, but the support is still context-limited and better suited to clarification."
        )
        next_step_label = "Clarify with targeted experiment"
        next_step_summary = (
            "Use a targeted clarifying experiment to reduce assay or target-context ambiguity before treating this claim as action-ready."
        )
        active_support_actionability_label = "Current active support is context-limited"
        if has_historical_context:
            historical_support_actionability_label = "Historical context still contributes"
        historical_interest_only_flag = False
    elif (
        has_mixed_current_historical_context
        and (
            support_quality_label == "Mixed-strength current support"
            or support_quality_label == "Current active support remains limited"
            or support_quality_label == "Context-limited current support"
            or basis_label == "Mixed support basis"
            or unresolved_basis_count > 0
            or weak_basis_count > 0
            or proposed_active_count > 0
            or governed_posture_label != "Current support governs present posture"
        )
    ):
        actionability_label = "Mixed current/historical basis"
        actionability_summary = (
            f"{candidate_label} has some current active support, but it is mixed with historical context and still needs clarification before it should drive priority."
        )
        actionability_basis_label = "Mixed current/historical basis"
        actionability_basis_summary = (
            f"{candidate_label}'s current actionability depends on {current_support_count} active governed support change"
            f"{'' if current_support_count == 1 else 's'} while {historical_support_count} superseded historical record"
            f"{'' if historical_support_count == 1 else 's'} remain in the background, so active support should be clarified rather than assumed strong."
        )
        next_step_label = "Clarify with targeted experiment"
        next_step_summary = (
            "Use a targeted clarifying experiment to separate current active support from historical context before treating this claim as action-ready."
        )
        active_support_actionability_label = "Current active support remains limited"
        historical_support_actionability_label = "Historical context still contributes"
        historical_interest_only_flag = False
    elif (
        support_quality_label == "Mixed-strength current support"
        or support_quality_label == "Current active support remains limited"
        or support_quality_label == "Context-limited current support"
        or basis_label == "Mixed support basis"
        or (
            current_support_count > 0
            and (observed_label_support_count > 0 or numeric_rule_based_support_count > 0)
            and (unresolved_basis_count > 0 or weak_basis_count > 0)
        )
    ):
        actionability_label = "Mixed basis, needs clarifying experiment"
        actionability_summary = (
            f"{candidate_label} has active governed support, but the current basis is mixed across stronger and weaker signals, so clarification is more appropriate than immediate prioritization."
        )
        actionability_basis_label = "Current active support basis"
        actionability_basis_summary = (
            f"{candidate_label}'s current actionability depends on active governed support, but the active basis is mixed and still needs clarification."
        )
        next_step_label = "Clarify with targeted experiment"
        next_step_summary = (
            "Use a targeted clarifying experiment to reduce ambiguity before treating this claim as action-ready."
        )
        active_support_actionability_label = "Current active support remains limited"
        if has_historical_context:
            historical_support_actionability_label = "Historical context still contributes"
        historical_interest_only_flag = False
    else:
        actionability_label = "Promising but needs stronger evidence"
        if has_mixed_current_historical_context:
            actionability_summary = (
                f"{candidate_label} has some current active support, but it is not yet strong enough to outweigh the need for fresh evidence beyond its historical context."
            )
            actionability_basis_label = "Mixed current/historical basis"
            actionability_basis_summary = (
                f"{candidate_label}'s actionability is currently mixed: active governed support exists, but historical context is still doing too much of the explanatory work."
            )
            historical_support_actionability_label = "Historical context still contributes"
        else:
            actionability_summary = (
                f"{candidate_label} has some active governed support, but the current basis is not strong enough to treat it as action-ready for follow-up."
            )
            actionability_basis_label = "Current active support basis"
            actionability_basis_summary = (
                f"{candidate_label}'s present actionability depends on active governed support, but that active basis is still limited."
            )
        if numeric_rule_based_support_count > 0 and observed_label_support_count <= 0:
            next_step_summary = (
                "Gather stronger observed evidence first; bounded numeric interpretation helps, but it should stay cautious under the current target rule."
            )
        elif proposed_active_count > 0 and accepted_active_count <= 0:
            next_step_summary = (
                "Gather stronger evidence first; current support remains proposed and should not yet drive priority on its own."
            )
        else:
            next_step_summary = (
                "Gather stronger evidence first before moving this claim into higher-priority follow-up."
            )
        next_step_label = "Gather stronger evidence first"
        active_support_actionability_label = "Current active support remains limited"
        historical_interest_only_flag = False

    return {
        "claim_actionability_label": actionability_label,
        "claim_actionability_summary": actionability_summary,
        "claim_actionability_basis_label": actionability_basis_label,
        "claim_actionability_basis_summary": actionability_basis_summary,
        "claim_active_support_actionability_label": active_support_actionability_label,
        "claim_historical_support_actionability_label": historical_support_actionability_label,
        "claim_historical_interest_only_flag": historical_interest_only_flag,
        "claim_next_step_label": next_step_label,
        "claim_next_step_summary": next_step_summary,
    }


def _claim_reference_payload(
    claim: dict[str, Any],
    *,
    updates_by_claim: dict[str, list[dict[str, Any]]],
    prior_claims_by_target: dict[str, list[dict[str, Any]]],
    prior_updates_by_claim: dict[str, list[dict[str, Any]]],
    include_governed_review_overlay: bool = True,
) -> dict[str, Any] | None:
    if not isinstance(claim, dict):
        return None
    candidate_reference = claim.get("candidate_reference") if isinstance(claim.get("candidate_reference"), dict) else {}
    candidate_label = _clean_text(
        candidate_reference.get("candidate_label") or claim.get("candidate_id"),
        default="This claim",
    )
    claim_updates = updates_by_claim.get(_clean_text(claim.get("claim_id")), [])
    chronology = _claim_chronology_fields(claim_updates)
    support_basis = _claim_support_basis_fields(claim_updates)
    support_quality = _claim_support_quality_fields(
        claim,
        claim_updates,
        chronology=chronology,
    )
    governed_posture = _claim_governed_support_posture_fields(
        claim,
        claim_updates,
        chronology=chronology,
        support_quality=support_quality,
    )
    support_coherence = _claim_support_coherence_fields(
        claim,
        claim_updates,
        chronology=chronology,
        support_quality=support_quality,
        governed_posture=governed_posture,
    )
    read_across = _claim_read_across_fields(
        claim,
        prior_claims_by_target.get(_claim_target_key_from_record(claim), []),
        prior_updates_by_claim=prior_updates_by_claim,
    )
    broader_reuse = _claim_broader_reuse_fields(
        claim,
        chronology=chronology,
        support_coherence=support_coherence,
        read_across=read_across,
    )
    trust_review = _claim_trust_review_fields(
        claim,
        chronology=chronology,
        support_coherence=support_coherence,
        broader_reuse=broader_reuse,
        updates=claim_updates,
    )
    actionability = _claim_actionability_fields(
        claim,
        claim_updates,
        chronology=chronology,
        support_basis=support_basis,
        support_quality=support_quality,
        governed_posture=governed_posture,
        support_coherence=support_coherence,
    )
    payload: dict[str, Any] = {
        "claim_id": claim.get("claim_id"),
        "candidate_id": claim.get("candidate_id"),
        "candidate_label": candidate_label,
        "claim_type": claim.get("claim_type"),
        "claim_text": claim.get("claim_text"),
        "support_level": claim.get("support_level"),
        "status": claim.get("status"),
        "source_recommendation_rank": claim.get("source_recommendation_rank"),
        "claim_support_role_label": chronology.get("claim_support_role_label"),
        "current_support_count": chronology.get("current_support_count"),
        "historical_support_count": chronology.get("historical_support_count"),
        "rejected_support_count": chronology.get("rejected_support_count"),
        "claim_chronology_summary_text": chronology.get("claim_chronology_summary_text"),
        "claim_support_basis_mix_label": support_basis.get("claim_support_basis_mix_label"),
        "claim_support_basis_mix_summary": support_basis.get("claim_support_basis_mix_summary"),
        "claim_observed_label_support_count": support_basis.get("claim_observed_label_support_count"),
        "claim_numeric_rule_based_support_count": support_basis.get("claim_numeric_rule_based_support_count"),
        "claim_unresolved_basis_count": support_basis.get("claim_unresolved_basis_count"),
        "claim_weak_basis_count": support_basis.get("claim_weak_basis_count"),
        "claim_support_quality_label": support_quality.get("claim_support_quality_label"),
        "claim_support_quality_summary": support_quality.get("claim_support_quality_summary"),
        "claim_governed_support_posture_label": governed_posture.get("claim_governed_support_posture_label"),
        "claim_governed_support_posture_summary": governed_posture.get("claim_governed_support_posture_summary"),
        "claim_support_coherence_label": support_coherence.get("claim_support_coherence_label"),
        "claim_support_coherence_summary": support_coherence.get("claim_support_coherence_summary"),
        "claim_support_reuse_label": support_coherence.get("claim_support_reuse_label"),
        "claim_support_reuse_summary": support_coherence.get("claim_support_reuse_summary"),
        "claim_current_support_contested_flag": support_coherence.get("claim_current_support_contested_flag"),
        "claim_current_posture_degraded_flag": support_coherence.get("claim_current_posture_degraded_flag"),
        "claim_historical_support_stronger_than_current_flag": support_coherence.get("claim_historical_support_stronger_than_current_flag"),
        "claim_broader_reuse_label": broader_reuse.get("claim_broader_reuse_label"),
        "claim_broader_reuse_summary": broader_reuse.get("claim_broader_reuse_summary"),
        "claim_future_reuse_candidacy_label": broader_reuse.get("claim_future_reuse_candidacy_label"),
        "claim_future_reuse_candidacy_summary": broader_reuse.get("claim_future_reuse_candidacy_summary"),
        "claim_continuity_cluster_posture_label": broader_reuse.get("claim_continuity_cluster_posture_label"),
        "claim_continuity_cluster_posture_summary": broader_reuse.get("claim_continuity_cluster_posture_summary"),
        "claim_promotion_candidate_posture_label": broader_reuse.get("claim_promotion_candidate_posture_label"),
        "claim_promotion_candidate_posture_summary": broader_reuse.get("claim_promotion_candidate_posture_summary"),
        "claim_promotion_stability_label": broader_reuse.get("claim_promotion_stability_label"),
        "claim_promotion_stability_summary": broader_reuse.get("claim_promotion_stability_summary"),
        "claim_promotion_gate_status_label": broader_reuse.get("claim_promotion_gate_status_label"),
        "claim_promotion_gate_status_summary": broader_reuse.get("claim_promotion_gate_status_summary"),
        "claim_promotion_block_reason_label": broader_reuse.get("claim_promotion_block_reason_label"),
        "claim_promotion_block_reason_summary": broader_reuse.get("claim_promotion_block_reason_summary"),
        "claim_source_class_label": trust_review.get("claim_source_class_label"),
        "claim_source_class_summary": trust_review.get("claim_source_class_summary"),
        "claim_trust_tier_label": trust_review.get("claim_trust_tier_label"),
        "claim_trust_tier_summary": trust_review.get("claim_trust_tier_summary"),
        "claim_provenance_confidence_label": trust_review.get("claim_provenance_confidence_label"),
        "claim_provenance_confidence_summary": trust_review.get("claim_provenance_confidence_summary"),
        "claim_governed_review_status_label": trust_review.get("claim_governed_review_status_label"),
        "claim_governed_review_status_summary": trust_review.get("claim_governed_review_status_summary"),
        "claim_governed_review_reason_label": trust_review.get("claim_governed_review_reason_label"),
        "claim_governed_review_reason_summary": trust_review.get("claim_governed_review_reason_summary"),
        "claim_read_across_label": read_across.get("claim_read_across_label"),
        "claim_read_across_summary": read_across.get("claim_read_across_summary"),
        "claim_prior_context_count": read_across.get("claim_prior_context_count"),
        "claim_prior_support_quality_label": read_across.get("claim_prior_support_quality_label"),
        "claim_prior_support_quality_summary": read_across.get("claim_prior_support_quality_summary"),
        "claim_prior_active_support_count": read_across.get("claim_prior_active_support_count"),
        "claim_prior_historical_support_count": read_across.get("claim_prior_historical_support_count"),
        "claim_actionability_label": actionability.get("claim_actionability_label"),
        "claim_actionability_summary": actionability.get("claim_actionability_summary"),
        "claim_actionability_basis_label": actionability.get("claim_actionability_basis_label"),
        "claim_actionability_basis_summary": actionability.get("claim_actionability_basis_summary"),
        "claim_active_support_actionability_label": actionability.get("claim_active_support_actionability_label"),
        "claim_historical_support_actionability_label": actionability.get("claim_historical_support_actionability_label"),
        "claim_historical_interest_only_flag": actionability.get("claim_historical_interest_only_flag"),
        "claim_next_step_label": actionability.get("claim_next_step_label"),
        "claim_next_step_summary": actionability.get("claim_next_step_summary"),
        "created_at": claim.get("created_at"),
    }
    review_overlay = build_governed_review_overlay(
        list_subject_governed_reviews(
            workspace_id=_clean_text(claim.get("workspace_id")) or None,
            subject_type=SUBJECT_TYPE_CLAIM,
            subject_id=_clean_text(claim.get("claim_id")),
        )
        if include_governed_review_overlay
        else [],
        fallback_fields={
            "source_class_label": payload.get("claim_source_class_label"),
            "trust_tier_label": payload.get("claim_trust_tier_label"),
            "provenance_confidence_label": payload.get("claim_provenance_confidence_label"),
            "governed_review_status_label": payload.get("claim_governed_review_status_label"),
            "governed_review_reason_label": payload.get("claim_governed_review_reason_label"),
            "governed_review_reason_summary": payload.get("claim_governed_review_reason_summary"),
            "promotion_gate_status_label": payload.get("claim_promotion_gate_status_label"),
            "promotion_block_reason_label": payload.get("claim_promotion_block_reason_label"),
        },
        subject_label=candidate_label,
    )
    payload.update(
        {
            "claim_source_class_label": review_overlay.get("source_class_label") or payload.get("claim_source_class_label"),
            "claim_trust_tier_label": review_overlay.get("trust_tier_label") or payload.get("claim_trust_tier_label"),
            "claim_provenance_confidence_label": review_overlay.get("provenance_confidence_label") or payload.get("claim_provenance_confidence_label"),
            "claim_governed_review_status_label": review_overlay.get("governed_review_status_label") or payload.get("claim_governed_review_status_label"),
            "claim_governed_review_reason_label": review_overlay.get("governed_review_reason_label") or payload.get("claim_governed_review_reason_label"),
            "claim_governed_review_reason_summary": review_overlay.get("governed_review_reason_summary") or payload.get("claim_governed_review_reason_summary"),
            "claim_governed_review_record_count": review_overlay.get("governed_review_record_count", 0),
            "claim_governed_review_history_summary": review_overlay.get("governed_review_history_summary", ""),
            "claim_promotion_audit_summary": review_overlay.get("promotion_audit_summary", ""),
        }
    )
    return payload


def claim_refs_from_records(
    claims: list[dict[str, Any]],
    *,
    belief_updates: list[dict[str, Any]] | None = None,
    prior_claims: list[dict[str, Any]] | None = None,
    prior_belief_updates: list[dict[str, Any]] | None = None,
    include_governed_review_overlay: bool = True,
) -> list[dict[str, Any]]:
    updates_by_claim = _updates_by_claim(belief_updates)
    prior_claims_by_target = _prior_claims_by_target(prior_claims)
    prior_updates_by_claim = _updates_by_claim(prior_belief_updates)
    refs: list[dict[str, Any]] = []
    for claim in claims:
        payload = _claim_reference_payload(
            claim,
            updates_by_claim=updates_by_claim,
            prior_claims_by_target=prior_claims_by_target,
            prior_updates_by_claim=prior_updates_by_claim,
            include_governed_review_overlay=include_governed_review_overlay,
        )
        if payload is not None:
            refs.append(validate_claim_reference(payload))
    return refs


def claims_summary_from_records(
    claims: list[dict[str, Any]],
    *,
    belief_updates: list[dict[str, Any]] | None = None,
    prior_claims: list[dict[str, Any]] | None = None,
    prior_belief_updates: list[dict[str, Any]] | None = None,
    include_governed_review_overlay: bool = True,
) -> dict[str, Any]:
    total = len(claims)
    proposed = sum(1 for claim in claims if _clean_text(claim.get("status")).lower() == ClaimStatus.proposed.value)
    accepted = sum(1 for claim in claims if _clean_text(claim.get("status")).lower() == ClaimStatus.accepted.value)
    rejected = sum(1 for claim in claims if _clean_text(claim.get("status")).lower() == ClaimStatus.rejected.value)
    superseded = sum(1 for claim in claims if _clean_text(claim.get("status")).lower() == ClaimStatus.superseded.value)
    claim_refs = claim_refs_from_records(
        claims,
        belief_updates=belief_updates,
        prior_claims=prior_claims,
        prior_belief_updates=prior_belief_updates,
        include_governed_review_overlay=include_governed_review_overlay,
    )
    claims_with_active_support_count = sum(1 for claim in claim_refs if int(claim.get("current_support_count") or 0) > 0)
    claims_with_historical_support_only_count = sum(
        1
        for claim in claim_refs
        if int(claim.get("current_support_count") or 0) <= 0
        and int(claim.get("historical_support_count") or 0) > 0
        and int(claim.get("rejected_support_count") or 0) <= 0
    )
    claims_with_rejected_support_only_count = sum(
        1
        for claim in claim_refs
        if int(claim.get("current_support_count") or 0) <= 0
        and int(claim.get("historical_support_count") or 0) <= 0
        and int(claim.get("rejected_support_count") or 0) > 0
    )
    claims_with_no_governed_support_count = sum(
        1
        for claim in claim_refs
        if int(claim.get("current_support_count") or 0) <= 0
        and int(claim.get("historical_support_count") or 0) <= 0
        and int(claim.get("rejected_support_count") or 0) <= 0
    )
    continuity_aligned_claim_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_read_across_label")) == "Continuity-aligned claim"
    )
    new_claim_context_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_read_across_label")) == "New claim context"
    )
    weak_prior_alignment_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_read_across_label")) == "Weak prior claim alignment"
    )
    no_prior_claim_context_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_read_across_label")) == "No prior claim context"
    )
    claims_with_active_governed_continuity_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_prior_support_quality_label")) == "Posture-governing continuity"
    )
    claims_with_tentative_active_continuity_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_prior_support_quality_label")) == "Tentative active continuity"
    )
    claims_with_historical_continuity_only_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_prior_support_quality_label")) == "Historical continuity only"
    )
    claims_with_sparse_prior_context_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_prior_support_quality_label")) == "Sparse prior claim context"
    )
    claims_with_no_useful_prior_context_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_prior_support_quality_label")) == "No useful prior claim context"
    )
    claims_mostly_observed_label_grounded_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_support_basis_mix_label")) == "Grounded mostly in observed labels"
    )
    claims_with_numeric_rule_based_support_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_support_basis_mix_label")) == "Includes bounded numeric interpretation"
    )
    claims_with_weak_basis_support_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_support_basis_mix_label")) == "Mostly unresolved or weak-basis"
    )
    claims_with_mixed_support_basis_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_support_basis_mix_label")) == "Mixed support basis"
    )
    claims_with_decision_useful_active_support_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_support_quality_label")) == "Decision-useful current active support"
    )
    claims_with_limited_active_support_quality_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_support_quality_label")) in {
            "Current active support remains limited",
            "Mixed-strength current support",
        }
    )
    claims_with_context_limited_active_support_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_support_quality_label")) == "Context-limited current support"
    )
    claims_with_weak_or_unresolved_active_support_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_support_quality_label")) == "Weak or provisional current support"
    )
    claims_with_posture_governing_support_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_governed_support_posture_label")) == "Current support governs present posture"
    )
    claims_with_tentative_current_support_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_governed_support_posture_label"))
        in {"Current support remains tentative", "Current support is context-limited and tentative"}
    )
    claims_with_accepted_limited_support_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_governed_support_posture_label")) == "Accepted support remains limited-weight"
    )
    claims_with_historical_non_governing_support_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_governed_support_posture_label"))
        in {"Historical support remains informative, not current", "Historical support only"}
    )
    claims_with_contested_current_support_count = sum(
        1 for claim in claim_refs if bool(claim.get("claim_current_support_contested_flag"))
    )
    claims_with_degraded_current_posture_count = sum(
        1 for claim in claim_refs if bool(claim.get("claim_current_posture_degraded_flag"))
    )
    claims_with_historical_stronger_than_current_count = sum(
        1 for claim in claim_refs if bool(claim.get("claim_historical_support_stronger_than_current_flag"))
    )
    claims_with_contradiction_limited_reuse_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_support_reuse_label")) == "Reuse with contradiction caution"
    )
    claims_with_strong_broader_reuse_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_broader_reuse_label")) == BROADER_REUSE_STRONG
    )
    claims_with_selective_broader_reuse_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_broader_reuse_label")) == BROADER_REUSE_SELECTIVE
    )
    claims_with_local_only_broader_reuse_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_broader_reuse_label")) == BROADER_REUSE_LOCAL_ONLY
    )
    claims_with_historical_only_broader_reuse_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_broader_reuse_label")) == BROADER_REUSE_HISTORICAL_ONLY
    )
    claims_with_stronger_future_reuse_candidacy_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_future_reuse_candidacy_label")) == FUTURE_REUSE_CANDIDACY_STRONG
    )
    claims_with_selective_future_reuse_candidacy_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_future_reuse_candidacy_label")) == FUTURE_REUSE_CANDIDACY_SELECTIVE
    )
    claims_in_promotion_candidate_continuity_cluster_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_continuity_cluster_posture_label")) == CONTINUITY_CLUSTER_PROMOTION_CANDIDATE
    )
    claims_in_selective_continuity_cluster_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_continuity_cluster_posture_label")) == CONTINUITY_CLUSTER_SELECTIVE
    )
    claims_in_context_only_continuity_cluster_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_continuity_cluster_posture_label")) == CONTINUITY_CLUSTER_CONTEXT_ONLY
    )
    claims_in_contradiction_limited_continuity_cluster_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_continuity_cluster_posture_label")) == CONTINUITY_CLUSTER_CONTRADICTION_LIMITED
    )
    claims_in_historical_continuity_cluster_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_continuity_cluster_posture_label")) == CONTINUITY_CLUSTER_HISTORICAL
    )
    claims_in_local_only_continuity_cluster_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_continuity_cluster_posture_label")) == CONTINUITY_CLUSTER_LOCAL_ONLY
    )
    claims_with_stronger_promotion_candidate_posture_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_candidate_posture_label")) == PROMOTION_CANDIDATE_STRONG
    )
    claims_with_selective_promotion_candidate_posture_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_candidate_posture_label")) == PROMOTION_CANDIDATE_SELECTIVE
    )
    claims_with_stable_promotion_boundary_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_stability_label")) == PROMOTION_STABILITY_STABLE
    )
    claims_with_selective_promotion_stability_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_stability_label")) == PROMOTION_STABILITY_SELECTIVE
    )
    claims_with_unstable_promotion_boundary_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_stability_label")) == PROMOTION_STABILITY_UNSTABLE
    )
    claims_with_historical_promotion_boundary_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_stability_label")) == PROMOTION_STABILITY_HISTORICAL
    )
    claims_with_promotable_gate_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_gate_status_label")) == PROMOTION_GATE_PROMOTABLE
    )
    claims_with_selective_promotion_gate_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_gate_status_label")) == PROMOTION_GATE_SELECTIVE
    )
    claims_with_blocked_promotion_gate_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_gate_status_label")) == PROMOTION_GATE_BLOCKED
    )
    claims_with_downgraded_promotion_gate_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_gate_status_label")) == PROMOTION_GATE_DOWNGRADED
    )
    claims_with_quarantined_promotion_gate_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_gate_status_label")) == PROMOTION_GATE_QUARANTINED
    )
    claims_blocked_by_contradiction_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_block_reason_label")) == PROMOTION_BLOCK_CONTRADICTION
    )
    claims_blocked_by_historical_continuity_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_block_reason_label")) == PROMOTION_BLOCK_HISTORICAL
    )
    claims_blocked_by_context_only_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_promotion_block_reason_label"))
        in {PROMOTION_BLOCK_CONTEXT_ONLY, PROMOTION_BLOCK_LOCAL_ONLY}
    )
    claims_with_weakly_reusable_support_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_support_reuse_label"))
        in {"Weakly reusable current support", "Selectively reusable support"}
    )
    claims_action_ready_follow_up_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_actionability_label"))
        in {"Action-ready for bounded follow-up", "Action-ready from current active support"}
    )
    claims_promising_but_need_stronger_evidence_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_actionability_label")) == "Promising but needs stronger evidence"
    )
    claims_need_clarifying_experiment_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_actionability_label"))
        in {"Mixed basis, needs clarifying experiment", "Mixed current/historical basis"}
    )
    claims_do_not_prioritize_yet_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_actionability_label")) == "Weak-basis, do not prioritize yet"
    )
    claims_with_insufficient_governed_basis_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_actionability_label"))
        in {
            "No governed support yet",
            "No active governed support",
            "Historically interesting, not currently action-ready",
        }
    )
    claims_action_ready_from_active_support_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_active_support_actionability_label"))
        == "Current active support is decision-useful"
    )
    claims_with_active_but_limited_actionability_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_active_support_actionability_label")) in {
            "Current active support remains limited",
            "Current active support is context-limited",
        }
        and _clean_text(claim.get("claim_actionability_label")) != "Mixed current/historical basis"
    )
    claims_historically_interesting_count = sum(
        1 for claim in claim_refs if bool(claim.get("claim_historical_interest_only_flag"))
    )
    claims_with_mixed_current_historical_actionability_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_actionability_label")) == "Mixed current/historical basis"
    )
    claims_with_no_active_governed_support_actionability_count = sum(
        1
        for claim in claim_refs
        if _clean_text(claim.get("claim_active_support_actionability_label")) == "No current active support"
        and not bool(claim.get("claim_historical_interest_only_flag"))
    )
    if total:
        summary_text = (
            f"{total} proposed claim{'' if total == 1 else 's'} were derived from the current shortlist. "
            "Claims remain bounded recommendation-derived assertions, not experimental confirmation."
        )
    else:
        summary_text = "No session claims have been recorded."
    if total:
        chronology_bits: list[str] = []
        if claims_with_active_support_count:
            chronology_bits.append(
                f"{claims_with_active_support_count} claim{'' if claims_with_active_support_count == 1 else 's'} with active governed support"
            )
        if claims_with_historical_support_only_count:
            chronology_bits.append(
                f"{claims_with_historical_support_only_count} historical-only"
            )
        if claims_with_rejected_support_only_count:
            chronology_bits.append(
                f"{claims_with_rejected_support_only_count} rejected-only"
            )
        if claims_with_no_governed_support_count:
            chronology_bits.append(
                f"{claims_with_no_governed_support_count} with no governed support yet"
            )
        chronology_summary_text = (
            "Claim-level support chronology remains bounded: " + ", ".join(chronology_bits) + "."
            if chronology_bits
            else "No claim-level support chronology is recorded yet."
        )
    else:
        chronology_summary_text = "No claim-level support chronology is recorded yet."
    if total:
        support_basis_parts: list[str] = []
        if claims_mostly_observed_label_grounded_count:
            support_basis_parts.append(
                f"{claims_mostly_observed_label_grounded_count} grounded mostly in observed labels"
            )
        if claims_with_numeric_rule_based_support_count:
            support_basis_parts.append(
                f"{claims_with_numeric_rule_based_support_count} with bounded numeric interpretation"
            )
        if claims_with_weak_basis_support_count:
            support_basis_parts.append(
                f"{claims_with_weak_basis_support_count} mostly unresolved or weak-basis"
            )
        if claims_with_mixed_support_basis_count:
            support_basis_parts.append(
                f"{claims_with_mixed_support_basis_count} mixed-basis"
            )
        if claims_with_decision_useful_active_support_count:
            support_basis_parts.append(
                f"{claims_with_decision_useful_active_support_count} with decision-useful active support"
            )
        if claims_with_posture_governing_support_count:
            support_basis_parts.append(
                f"{claims_with_posture_governing_support_count} posture-governing now"
            )
        if claims_with_tentative_current_support_count:
            support_basis_parts.append(
                f"{claims_with_tentative_current_support_count} still tentative"
            )
        if claims_with_accepted_limited_support_count:
            support_basis_parts.append(
                f"{claims_with_accepted_limited_support_count} accepted but limited-weight"
            )
        if claims_with_contested_current_support_count:
            support_basis_parts.append(
                f"{claims_with_contested_current_support_count} contested"
            )
        if claims_with_degraded_current_posture_count:
            support_basis_parts.append(
                f"{claims_with_degraded_current_posture_count} degraded"
            )
        if claims_with_context_limited_active_support_count:
            support_basis_parts.append(
                f"{claims_with_context_limited_active_support_count} context-limited"
            )
        if claims_with_weak_or_unresolved_active_support_count:
            support_basis_parts.append(
                f"{claims_with_weak_or_unresolved_active_support_count} weak or provisional"
            )
        if claims_with_no_governed_support_count:
            support_basis_parts.append(
                f"{claims_with_no_governed_support_count} with no governed support yet"
            )
        claim_support_basis_summary_text = (
            "Claim support-basis composition remains bounded: " + ", ".join(support_basis_parts) + "."
            if support_basis_parts
            else "No claim-level support-basis composition is recorded yet."
        )
    else:
        claim_support_basis_summary_text = "No claim-level support-basis composition is recorded yet."
    if total:
        actionability_parts: list[str] = []
        if claims_action_ready_follow_up_count:
            actionability_parts.append(
                f"{claims_action_ready_follow_up_count} action-ready from current active support"
            )
        if claims_promising_but_need_stronger_evidence_count:
            actionability_parts.append(
                f"{claims_promising_but_need_stronger_evidence_count} promising but needing stronger evidence"
            )
        if claims_need_clarifying_experiment_count:
            actionability_parts.append(
                f"{claims_need_clarifying_experiment_count} needing clarifying experiment"
            )
        if claims_do_not_prioritize_yet_count:
            actionability_parts.append(
                f"{claims_do_not_prioritize_yet_count} weak-basis and not ready to prioritize"
            )
        if claims_with_insufficient_governed_basis_count:
            actionability_parts.append(
                f"{claims_with_insufficient_governed_basis_count} with insufficient governed basis"
            )
        if claims_historically_interesting_count:
            actionability_parts.append(
                f"{claims_historically_interesting_count} historically interesting and needing fresh evidence"
            )
        claim_actionability_summary_text = (
            "Claim actionability remains bounded: " + ", ".join(actionability_parts) + "."
            if actionability_parts
            else "No bounded claim actionability guidance is recorded yet."
        )
    else:
        claim_actionability_summary_text = "No bounded claim actionability guidance is recorded yet."
    if total:
        actionability_basis_parts: list[str] = []
        if claims_action_ready_from_active_support_count:
            actionability_basis_parts.append(
                f"{claims_action_ready_from_active_support_count} action-ready from current active support"
            )
        if claims_with_active_but_limited_actionability_count:
            actionability_basis_parts.append(
                f"{claims_with_active_but_limited_actionability_count} with active support that remains limited"
            )
        if claims_with_contested_current_support_count:
            actionability_basis_parts.append(
                f"{claims_with_contested_current_support_count} contested current support"
            )
        if claims_with_degraded_current_posture_count:
            actionability_basis_parts.append(
                f"{claims_with_degraded_current_posture_count} degraded current posture"
            )
        if claims_with_historical_stronger_than_current_count:
            actionability_basis_parts.append(
                f"{claims_with_historical_stronger_than_current_count} with historical support stronger than current"
            )
        if claims_with_posture_governing_support_count:
            actionability_basis_parts.append(
                f"{claims_with_posture_governing_support_count} posture-governing now"
            )
        if claims_with_tentative_current_support_count:
            actionability_basis_parts.append(
                f"{claims_with_tentative_current_support_count} with current support still tentative"
            )
        if claims_with_accepted_limited_support_count:
            actionability_basis_parts.append(
                f"{claims_with_accepted_limited_support_count} accepted but limited-weight"
            )
        if claims_historically_interesting_count:
            actionability_basis_parts.append(
                f"{claims_historically_interesting_count} historically interesting and needing fresh evidence"
            )
        if claims_with_mixed_current_historical_actionability_count:
            actionability_basis_parts.append(
                f"{claims_with_mixed_current_historical_actionability_count} with mixed current/historical action basis"
            )
        if claims_with_no_active_governed_support_actionability_count:
            actionability_basis_parts.append(
                f"{claims_with_no_active_governed_support_actionability_count} with no active governed support at all"
            )
        claim_actionability_basis_summary_text = (
            "Claim actionability basis remains bounded: " + ", ".join(actionability_basis_parts) + "."
            if actionability_basis_parts
            else "No bounded claim actionability basis is recorded yet."
        )
    else:
        claim_actionability_basis_summary_text = "No bounded claim actionability basis is recorded yet."
    if total:
        if claims_with_contradiction_limited_reuse_count and not claims_with_active_governed_continuity_count:
            read_across_summary_text = (
                "This session has a contested broader continuity cluster: prior claim context exists, but contradiction-heavy or degraded present posture discounts broader reuse."
            )
        elif claims_with_active_governed_continuity_count and not new_claim_context_count and not weak_prior_alignment_count:
            read_across_summary_text = (
                "This session shows a coherent broader continuity cluster within bounded target scope: prior claim context is reinforced by posture-governing continuity, but read-across remains bounded rather than general truth."
            )
        elif claims_with_tentative_active_continuity_count and not claims_with_active_governed_continuity_count:
            read_across_summary_text = (
                "This session has a selective broader continuity cluster: prior claim context exists, but it is backed mainly by tentative or limited active support and should stay discounted."
            )
        elif claims_with_historical_continuity_only_count and not claims_with_active_governed_continuity_count:
            read_across_summary_text = (
                "This session has a historical-heavy broader continuity cluster: prior claim context remains informative, but mainly as historical context rather than strong current reuse."
            )
        elif new_claim_context_count > continuity_aligned_claim_count:
            read_across_summary_text = (
                "This session introduces new claim context relative to prior target-scoped claims. Read-across remains bounded."
            )
        elif weak_prior_alignment_count and not continuity_aligned_claim_count:
            read_across_summary_text = (
                "This session has only weak prior claim alignment for part of its claim set. Read-across remains bounded."
            )
        elif no_prior_claim_context_count == total:
            read_across_summary_text = (
                "No strong prior target-scoped claim context is recorded yet for this session."
            )
        else:
            parts: list[str] = []
            if claims_with_active_governed_continuity_count:
                parts.append(f"{claims_with_active_governed_continuity_count} posture-governing continuity")
            if claims_with_tentative_active_continuity_count:
                parts.append(f"{claims_with_tentative_active_continuity_count} tentative-active continuity")
            if claims_with_contradiction_limited_reuse_count:
                parts.append(f"{claims_with_contradiction_limited_reuse_count} discounted contested continuity")
            if claims_with_historical_continuity_only_count:
                parts.append(f"{claims_with_historical_continuity_only_count} historical-only continuity")
            if new_claim_context_count:
                parts.append(f"{new_claim_context_count} new-context")
            if weak_prior_alignment_count:
                parts.append(f"{weak_prior_alignment_count} weak-alignment")
            if claims_with_sparse_prior_context_count:
                parts.append(f"{claims_with_sparse_prior_context_count} sparse-prior-context")
            if claims_with_no_useful_prior_context_count:
                parts.append(f"{claims_with_no_useful_prior_context_count} with no useful prior context")
            read_across_summary_text = (
                "Claim read-across remains bounded: " + ", ".join(parts) + "."
                if parts
                else "No claim read-across context is recorded yet."
            )
    else:
        read_across_summary_text = "No claim read-across context is recorded yet."

    broader_scope = assess_broader_reuse_posture(
        active_support_count=claims_with_active_support_count,
        continuity_evidence_count=continuity_aligned_claim_count,
        governing_continuity_count=claims_with_active_governed_continuity_count,
        tentative_continuity_count=claims_with_tentative_active_continuity_count,
        contested_continuity_count=claims_with_contradiction_limited_reuse_count,
        historical_continuity_count=claims_with_historical_continuity_only_count,
        current_support_reuse_label=(
            "Reuse with contradiction caution"
            if claims_with_contradiction_limited_reuse_count > 0
            else "Strongly reusable governed support"
            if claims_with_posture_governing_support_count > 0
            and claims_with_active_governed_continuity_count > 0
            and claims_with_contested_current_support_count <= 0
            and claims_with_degraded_current_posture_count <= 0
            else "Selectively reusable support"
            if continuity_aligned_claim_count > 0
            else "Weakly reusable current support"
            if claims_with_active_support_count > 0
            else "Historical-only for reuse"
            if claims_with_historical_support_only_count > 0
            else "Not yet suitable for strong governed reuse"
        ),
        contested_flag=claims_with_contested_current_support_count > 0,
        degraded_flag=claims_with_degraded_current_posture_count > 0,
        historical_stronger_flag=claims_with_historical_stronger_than_current_count > 0,
    )
    broader_reuse_label = broader_scope["broader_reuse_label"]
    broader_continuity_label = broader_scope["broader_continuity_label"]
    future_reuse_candidacy_label = broader_scope["future_reuse_candidacy_label"]
    cluster_scope = assess_continuity_cluster_promotion(
        active_support_count=claims_with_active_support_count,
        continuity_evidence_count=continuity_aligned_claim_count,
        governing_continuity_count=claims_with_active_governed_continuity_count,
        tentative_continuity_count=claims_with_tentative_active_continuity_count,
        contested_continuity_count=claims_with_contradiction_limited_reuse_count,
        historical_continuity_count=claims_with_historical_continuity_only_count,
        broader_reuse_label=broader_reuse_label,
        broader_continuity_label=broader_continuity_label,
        future_reuse_candidacy_label=future_reuse_candidacy_label,
        contested_flag=claims_with_contested_current_support_count > 0,
        degraded_flag=claims_with_degraded_current_posture_count > 0,
        historical_stronger_flag=claims_with_historical_stronger_than_current_count > 0,
    )
    continuity_cluster_posture_label = cluster_scope["continuity_cluster_posture_label"]
    promotion_candidate_posture_label = cluster_scope["promotion_candidate_posture_label"]
    promotion_boundary = assess_governed_promotion_boundary(
        active_support_count=claims_with_active_support_count,
        continuity_evidence_count=continuity_aligned_claim_count,
        governing_continuity_count=claims_with_active_governed_continuity_count,
        tentative_continuity_count=claims_with_tentative_active_continuity_count,
        contested_continuity_count=claims_with_contradiction_limited_reuse_count,
        historical_continuity_count=claims_with_historical_continuity_only_count,
        broader_reuse_label=broader_reuse_label,
        broader_continuity_label=broader_continuity_label,
        continuity_cluster_posture_label=continuity_cluster_posture_label,
        promotion_candidate_posture_label=promotion_candidate_posture_label,
        contested_flag=claims_with_contested_current_support_count > 0,
        degraded_flag=claims_with_degraded_current_posture_count > 0,
        historical_stronger_flag=claims_with_historical_stronger_than_current_count > 0,
    )
    promotion_stability_label = promotion_boundary["promotion_stability_label"]
    promotion_gate_status_label = promotion_boundary["promotion_gate_status_label"]
    promotion_block_reason_label = promotion_boundary["promotion_block_reason_label"]

    if broader_reuse_label == BROADER_REUSE_STRONG:
        broader_reuse_summary_text = (
            f"Broader claim reuse is strongest where current posture is coherent: {claims_with_strong_broader_reuse_count} claim"
            f"{'' if claims_with_strong_broader_reuse_count == 1 else 's'} currently combine posture-governing support with coherent related-claim continuity."
        )
    elif broader_reuse_label == BROADER_REUSE_CONTRADICTION_LIMITED:
        broader_reuse_summary_text = (
            "Broader claim reuse should stay contradiction-limited because contested, degraded, or contradiction-heavy histories weaken how honestly support should carry across related claims."
        )
    elif broader_reuse_label == BROADER_REUSE_HISTORICAL_ONLY:
        broader_reuse_summary_text = (
            "Broader claim reuse is mostly historical-only right now: earlier support remains informative as context, but it should not silently behave like strong current reuse."
        )
    elif broader_reuse_label == BROADER_REUSE_SELECTIVE:
        broader_reuse_summary_text = (
            f"Broader claim reuse is selective: {claims_with_selective_broader_reuse_count} claim"
            f"{'' if claims_with_selective_broader_reuse_count == 1 else 's'} have some related-claim continuity, but stronger broader reuse would need cleaner present posture or stronger continuity."
        )
    else:
        broader_reuse_summary_text = (
            f"Current claim support is still mainly local to the individual claim picture: {claims_with_local_only_broader_reuse_count} claim"
            f"{'' if claims_with_local_only_broader_reuse_count == 1 else 's'} remain locally meaningful without enough governed continuity for broader reuse."
        )

    if broader_continuity_label == BROADER_CONTINUITY_COHERENT:
        broader_continuity_summary_text = (
            "The broader continuity cluster is coherent within bounded target scope: related claims reinforce one another under posture-governing current support."
        )
    elif broader_continuity_label == BROADER_CONTINUITY_CONTESTED:
        broader_continuity_summary_text = (
            "The broader continuity cluster is contested: related claim context exists, but contradiction pressure or degraded present posture means it should be discounted."
        )
    elif broader_continuity_label == BROADER_CONTINUITY_HISTORICAL:
        broader_continuity_summary_text = (
            "The broader continuity cluster is historical-heavy: prior support context remains visible, but it is doing more historical explanatory work than current reuse work."
        )
    elif broader_continuity_label == BROADER_CONTINUITY_SELECTIVE:
        broader_continuity_summary_text = (
            "The broader continuity cluster is selective: some related claims line up, but current continuity is mixed across tentative, limited, or partial support."
        )
    else:
        broader_continuity_summary_text = (
            "No meaningful broader continuity cluster is established yet, so support should stay local to individual claims."
        )

    if future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_STRONG:
        future_reuse_candidacy_summary_text = (
            f"{claims_with_stronger_future_reuse_candidacy_count} claim"
            f"{'' if claims_with_stronger_future_reuse_candidacy_count == 1 else 's'} now look like stronger later candidates for broader governed reuse if the bounded current posture holds."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_SELECTIVE:
        future_reuse_candidacy_summary_text = (
            f"Future broader reuse candidacy is selective: {claims_with_selective_future_reuse_candidacy_count} claim"
            f"{'' if claims_with_selective_future_reuse_candidacy_count == 1 else 's'} may later support broader governed reuse, but stronger continuity or cleaner current posture would still be needed."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED:
        future_reuse_candidacy_summary_text = (
            "Future broader reuse candidacy is contradiction-limited because contested or degraded histories still outweigh cleaner governed carryover."
        )
    elif future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_HISTORICAL_ONLY:
        future_reuse_candidacy_summary_text = (
            "Future broader reuse candidacy is mostly historical-only right now: the history is informative, but it is not a strong current candidate for broader governed reuse."
        )
    else:
        future_reuse_candidacy_summary_text = (
            "Future broader reuse candidacy remains local-only because claim history is still more useful for local review than for broader governed carryover."
        )

    if continuity_cluster_posture_label == CONTINUITY_CLUSTER_PROMOTION_CANDIDATE:
        continuity_cluster_posture_summary_text = (
            f"The claim-family continuity cluster is a promotion candidate: {claims_in_promotion_candidate_continuity_cluster_count} claim"
            f"{'' if claims_in_promotion_candidate_continuity_cluster_count == 1 else 's'} currently sit in coherent broader continuity with posture-governing support."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_SELECTIVE:
        continuity_cluster_posture_summary_text = (
            f"The claim-family continuity cluster is selective: {claims_in_selective_continuity_cluster_count} claim"
            f"{'' if claims_in_selective_continuity_cluster_count == 1 else 's'} have enough continuity to matter, but not enough for stronger broader promotion."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTRADICTION_LIMITED:
        continuity_cluster_posture_summary_text = (
            f"The claim-family continuity cluster is contradiction-limited: {claims_in_contradiction_limited_continuity_cluster_count} claim"
            f"{'' if claims_in_contradiction_limited_continuity_cluster_count == 1 else 's'} carry continuity under contested or degraded history, so the cluster should remain visible but not over-promoted."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_HISTORICAL:
        continuity_cluster_posture_summary_text = (
            f"The claim-family continuity cluster is historical-heavy: {claims_in_historical_continuity_cluster_count} claim"
            f"{'' if claims_in_historical_continuity_cluster_count == 1 else 's'} mainly contribute historical context rather than stronger current promotion posture."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTEXT_ONLY:
        continuity_cluster_posture_summary_text = (
            f"The claim-family continuity cluster remains context-only: {claims_in_context_only_continuity_cluster_count} claim"
            f"{'' if claims_in_context_only_continuity_cluster_count == 1 else 's'} have related continuity visible for review, but that continuity should not yet travel as a broader governed promotion candidate."
        )
    else:
        continuity_cluster_posture_summary_text = (
            f"Continuity remains local-only for {claims_in_local_only_continuity_cluster_count} claim"
            f"{'' if claims_in_local_only_continuity_cluster_count == 1 else 's'}, so broader cluster promotion is not yet justified."
        )

    if promotion_candidate_posture_label == PROMOTION_CANDIDATE_STRONG:
        promotion_candidate_posture_summary_text = (
            f"{claims_with_stronger_promotion_candidate_posture_count} claim"
            f"{'' if claims_with_stronger_promotion_candidate_posture_count == 1 else 's'} now look like stronger broader governed promotion candidates if the current coherence holds."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_SELECTIVE:
        promotion_candidate_posture_summary_text = (
            f"Promotion-candidate posture is selective only: {claims_with_selective_promotion_candidate_posture_count} claim"
            f"{'' if claims_with_selective_promotion_candidate_posture_count == 1 else 's'} may later matter beyond local context, but stronger continuity or cleaner current support would still be needed."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_CONTRADICTION_LIMITED:
        promotion_candidate_posture_summary_text = (
            "Promotion-candidate posture is contradiction-limited because contested or degraded continuity still weakens honest broader governed carryover."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_HISTORICAL_ONLY:
        promotion_candidate_posture_summary_text = (
            "Promotion-candidate posture is historical-only right now: the continuity remains informative context, but it should not be treated as a current broader governed promotion candidate."
        )
    else:
        promotion_candidate_posture_summary_text = (
            "Promotion-candidate posture remains context-only right now because current continuity is still more useful for review context than for broader governed promotion."
        )

    if promotion_stability_label == PROMOTION_STABILITY_STABLE:
        promotion_stability_summary_text = (
            f"Claim-family continuity is stable enough for promotion review: {claims_with_stable_promotion_boundary_count} claim"
            f"{'' if claims_with_stable_promotion_boundary_count == 1 else 's'} currently keep coherent governed continuity without material contradiction pressure."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_SELECTIVE:
        promotion_stability_summary_text = (
            f"Claim-family continuity is only selectively stable: {claims_with_selective_promotion_stability_count} claim"
            f"{'' if claims_with_selective_promotion_stability_count == 1 else 's'} may later support bounded promotion, but stronger or cleaner stability would still be needed."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_UNSTABLE:
        promotion_stability_summary_text = (
            f"Claim-family continuity is unstable under contradiction pressure: {claims_with_unstable_promotion_boundary_count} claim"
            f"{'' if claims_with_unstable_promotion_boundary_count == 1 else 's'} currently sit in mixed or degrading continuity that should stay blocked or quarantined."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_HISTORICAL:
        promotion_stability_summary_text = (
            f"Claim-family continuity is historical-heavy rather than stably current: {claims_with_historical_promotion_boundary_count} claim"
            f"{'' if claims_with_historical_promotion_boundary_count == 1 else 's'} mainly contribute historical continuity context."
        )
    else:
        promotion_stability_summary_text = (
            "Claim-family continuity does not yet satisfy enough governed stability for broader promotion review."
        )

    if promotion_gate_status_label == PROMOTION_GATE_PROMOTABLE:
        promotion_gate_status_summary_text = (
            f"{claims_with_promotable_gate_count} claim"
            f"{'' if claims_with_promotable_gate_count == 1 else 's'} now sit in continuity clusters that are promotable under bounded governed rules if the current coherence holds."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_SELECTIVE:
        promotion_gate_status_summary_text = (
            f"Promotion-gate posture is selective: {claims_with_selective_promotion_gate_count} claim"
            f"{'' if claims_with_selective_promotion_gate_count == 1 else 's'} may justify bounded broader carryover later, but only with caution."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_DOWNGRADED:
        promotion_gate_status_summary_text = (
            f"Promotion-gate posture has been downgraded for {claims_with_downgraded_promotion_gate_count} claim"
            f"{'' if claims_with_downgraded_promotion_gate_count == 1 else 's'} because newer evidence now weakens stronger prior promotion posture."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_QUARANTINED:
        promotion_gate_status_summary_text = (
            f"Promotion-gate posture is quarantined for {claims_with_quarantined_promotion_gate_count} claim"
            f"{'' if claims_with_quarantined_promotion_gate_count == 1 else 's'} because contradiction-heavy and degraded continuity make stronger promotion unsafe."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_BLOCKED:
        promotion_gate_status_summary_text = (
            f"Promotion-gate posture remains blocked for {claims_with_blocked_promotion_gate_count} claim"
            f"{'' if claims_with_blocked_promotion_gate_count == 1 else 's'} even though some broader continuity may be visible."
        )
    else:
        promotion_gate_status_summary_text = (
            "Claim-family continuity is not yet a governed promotion candidate and should remain local or contextual."
        )

    if promotion_block_reason_label == PROMOTION_BLOCK_NONE:
        promotion_block_reason_summary_text = (
            "No material promotion block is currently recorded for the claim-family continuity picture."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_LOCAL_ONLY:
        promotion_block_reason_summary_text = (
            f"Promotion remains blocked because {claims_blocked_by_context_only_count} claim"
            f"{'' if claims_blocked_by_context_only_count == 1 else 's'} still have only local or context-only meaning."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_CONTEXT_ONLY:
        promotion_block_reason_summary_text = (
            f"Promotion remains blocked because {claims_blocked_by_context_only_count} claim"
            f"{'' if claims_blocked_by_context_only_count == 1 else 's'} still sit in context-only continuity rather than a promotable broader cluster."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_SELECTIVE_ONLY:
        promotion_block_reason_summary_text = (
            "Promotion remains limited because the current continuity is selective only: it matters beyond local context, but is still too bounded for cleaner promotion."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_CONTRADICTION:
        promotion_block_reason_summary_text = (
            f"Promotion remains blocked by contradiction-heavy history across {claims_blocked_by_contradiction_count} claim"
            f"{'' if claims_blocked_by_contradiction_count == 1 else 's'}, so broader carryover should remain cautious."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_DEGRADED:
        promotion_block_reason_summary_text = (
            "Promotion remains limited by degraded present posture, so earlier stronger continuity should not stay silently promotable."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_HISTORICAL:
        promotion_block_reason_summary_text = (
            f"Promotion remains historical-only for {claims_blocked_by_historical_continuity_count} claim"
            f"{'' if claims_blocked_by_historical_continuity_count == 1 else 's'}: the continuity remains visible, but mainly as historical context."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_DOWNGRADED:
        promotion_block_reason_summary_text = (
            "Promotion was downgraded by newer contradictory or weaker present evidence, so broader governed carryover should be reduced rather than preserved."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_QUARANTINED:
        promotion_block_reason_summary_text = (
            "Promotion is quarantined because current continuity is too unstable under contradiction-heavy and degraded history."
        )
    else:
        promotion_block_reason_summary_text = (
            "Promotion remains blocked because the current continuity picture does not yet satisfy enough governed stability conditions."
        )
    claims_with_local_only_trust_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_trust_tier_label")) == TRUST_TIER_LOCAL_ONLY
    )
    claims_with_candidate_trust_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_trust_tier_label")) == TRUST_TIER_CANDIDATE
    )
    claims_with_governed_trust_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_trust_tier_label")) == TRUST_TIER_GOVERNED
    )
    claims_with_strong_provenance_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_provenance_confidence_label")) == PROVENANCE_CONFIDENCE_STRONG
    )
    claims_with_moderate_provenance_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_provenance_confidence_label")) == PROVENANCE_CONFIDENCE_MODERATE
    )
    claims_with_weak_provenance_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_provenance_confidence_label")) == PROVENANCE_CONFIDENCE_WEAK
    )
    claims_with_approved_review_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_governed_review_status_label")) == REVIEW_STATUS_APPROVED
    )
    claims_with_blocked_review_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_governed_review_status_label")) == REVIEW_STATUS_BLOCKED
    )
    claims_with_deferred_review_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_governed_review_status_label")) in {REVIEW_STATUS_DEFERRED, REVIEW_STATUS_CANDIDATE}
    )
    claims_with_downgraded_review_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_governed_review_status_label")) == REVIEW_STATUS_DOWNGRADED
    )
    claims_with_quarantined_review_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_governed_review_status_label")) == REVIEW_STATUS_QUARANTINED
    )
    claims_with_unknown_source_class_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_source_class_label")) == SOURCE_CLASS_UNKNOWN
    )
    claims_with_ai_source_class_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_source_class_label")) == SOURCE_CLASS_AI_DERIVED
    )
    claims_with_uncontrolled_source_class_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_source_class_label")) == SOURCE_CLASS_UNCONTROLLED_UPLOAD
    )
    claims_with_derived_source_class_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_source_class_label")) == SOURCE_CLASS_DERIVED_EXTRACTED
    )
    claims_with_affiliated_source_class_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_source_class_label")) == SOURCE_CLASS_AFFILIATED
    )
    claims_with_internal_governed_source_class_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_source_class_label")) == SOURCE_CLASS_INTERNAL_GOVERNED
    )
    claims_with_curated_source_class_count = sum(
        1 for claim in claim_refs if _clean_text(claim.get("claim_source_class_label")) == SOURCE_CLASS_CURATED
    )
    governed_review_record_count = sum(_safe_int(claim.get("claim_governed_review_record_count")) for claim in claim_refs)

    if claims_with_governed_trust_count > 0:
        trust_tier_label = TRUST_TIER_GOVERNED
        trust_tier_summary_text = (
            f"{claims_with_governed_trust_count} claim{'' if claims_with_governed_trust_count == 1 else 's'} now rest on governed-trusted evidence posture for bounded broader consideration."
        )
    elif claims_with_candidate_trust_count > 0:
        trust_tier_label = TRUST_TIER_CANDIDATE
        trust_tier_summary_text = (
            f"{claims_with_candidate_trust_count} claim{'' if claims_with_candidate_trust_count == 1 else 's'} are broader trust candidates, but stronger trust is still needed before broader influence should increase."
        )
    else:
        trust_tier_label = TRUST_TIER_LOCAL_ONLY
        trust_tier_summary_text = (
            f"Claim evidence remains local-only by default across {claims_with_local_only_trust_count} claim{'' if claims_with_local_only_trust_count == 1 else 's'}, so local usefulness is separated from broader influence."
        )

    if claims_with_strong_provenance_count > 0:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_STRONG
        provenance_confidence_summary_text = (
            f"{claims_with_strong_provenance_count} claim{'' if claims_with_strong_provenance_count == 1 else 's'} have stronger provenance grounding for bounded broader trust."
        )
    elif claims_with_moderate_provenance_count > 0:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_MODERATE
        provenance_confidence_summary_text = (
            "Claim-family provenance is moderate overall: some lineage is visible, but broader trust should still stay reviewable."
        )
    elif claims_with_weak_provenance_count > 0:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_WEAK
        provenance_confidence_summary_text = (
            "Claim-family provenance remains weak for broader influence, so local usefulness should not be mistaken for stronger broader trust."
        )
    else:
        provenance_confidence_label = PROVENANCE_CONFIDENCE_UNKNOWN
        provenance_confidence_summary_text = (
            "Claim-family provenance confidence remains unknown because explicit source lineage is still too thin for stronger broader trust."
        )

    if claims_with_unknown_source_class_count > 0:
        source_class_label = SOURCE_CLASS_UNKNOWN
        source_class_summary_text = (
            "At least part of the current claim family still has unknown source class, so broader trust should stay conservative rather than inferred from volume."
        )
    elif claims_with_ai_source_class_count > 0:
        source_class_label = SOURCE_CLASS_AI_DERIVED
        source_class_summary_text = (
            "Some current claim support still depends on AI-derived interpretation, so broader influence should remain bounded and reviewable."
        )
    elif claims_with_uncontrolled_source_class_count > 0:
        source_class_label = SOURCE_CLASS_UNCONTROLLED_UPLOAD
        source_class_summary_text = (
            "Some current claim support still depends on uncontrolled uploaded evidence, so local usefulness is preserved without granting stronger broader influence."
        )
    elif claims_with_derived_source_class_count > 0:
        source_class_label = SOURCE_CLASS_DERIVED_EXTRACTED
        source_class_summary_text = (
            "Current claim-family support includes derived or retrieved context, which is useful but still weaker than a fully governed direct observation path."
        )
    elif claims_with_affiliated_source_class_count > 0:
        source_class_label = SOURCE_CLASS_AFFILIATED
        source_class_summary_text = (
            "Current claim-family support is grounded mainly in affiliated or partner evidence paths, so broader trust remains bounded even when provenance is visible."
        )
    elif claims_with_internal_governed_source_class_count > 0:
        source_class_label = SOURCE_CLASS_INTERNAL_GOVERNED
        source_class_summary_text = (
            "Current claim-family support is grounded mainly in internally governed experimental evidence linked into the reviewable workflow."
        )
    elif claims_with_curated_source_class_count > 0:
        source_class_label = SOURCE_CLASS_CURATED
        source_class_summary_text = (
            "Current claim-family support includes curated or benchmark-like evidence paths, which is the strongest bounded source class currently visible."
        )
    else:
        source_class_label = SOURCE_CLASS_UNKNOWN
        source_class_summary_text = (
            "No claim-family source class has been established yet, so the current posture should remain local-first."
        )

    if claims_with_approved_review_count > 0:
        governed_review_status_label = REVIEW_STATUS_APPROVED
        governed_review_status_summary_text = (
            f"{claims_with_approved_review_count} claim{'' if claims_with_approved_review_count == 1 else 's'} are currently approved for bounded broader governed consideration."
        )
        governed_review_reason_label = REVIEW_REASON_APPROVED
        governed_review_reason_summary_text = (
            "Approved broader consideration depends on trust, provenance, and continuity quality rather than on volume."
        )
    elif claims_with_quarantined_review_count > 0:
        governed_review_status_label = REVIEW_STATUS_QUARANTINED
        governed_review_status_summary_text = (
            "Some claim-family continuity remains quarantined from stronger broader influence because instability is too high."
        )
        governed_review_reason_label = REVIEW_REASON_QUARANTINED
        governed_review_reason_summary_text = (
            "Contradiction-heavy or unstable continuity keeps broader influence quarantined even when local value remains."
        )
    elif claims_with_downgraded_review_count > 0:
        governed_review_status_label = REVIEW_STATUS_DOWNGRADED
        governed_review_status_summary_text = (
            "Some claim-family continuity has been downgraded from a stronger broader-trust posture after newer weakening evidence."
        )
        governed_review_reason_label = REVIEW_REASON_DOWNGRADED
        governed_review_reason_summary_text = (
            "Downgrade keeps weakened evidence visible as history without letting older stronger posture silently remain current."
        )
    elif claims_with_blocked_review_count > 0:
        governed_review_status_label = REVIEW_STATUS_BLOCKED
        governed_review_status_summary_text = (
            "Claim-family broader influence remains blocked for part of the current claim set."
        )
        governed_review_reason_label = REVIEW_REASON_STRONGER_TRUST_NEEDED
        governed_review_reason_summary_text = (
            "Blocked broader influence reflects weak provenance, contradiction pressure, degraded posture, or still-bounded continuity."
        )
    elif claims_with_deferred_review_count > 0:
        governed_review_status_label = REVIEW_STATUS_DEFERRED
        governed_review_status_summary_text = (
            "Claim-family broader influence is still deferred or candidate-only rather than approved."
        )
        governed_review_reason_label = REVIEW_REASON_STRONGER_TRUST_NEEDED
        governed_review_reason_summary_text = (
            "Stronger trust and review conditions would still be needed before broader influence should increase."
        )
    else:
        governed_review_status_label = REVIEW_STATUS_NOT_REVIEWED
        governed_review_status_summary_text = (
            "Claims remain local-first with no broader governed review posture yet."
        )
        governed_review_reason_label = REVIEW_REASON_LOCAL_DEFAULT
        governed_review_reason_summary_text = (
            "Local-only by default remains the governing trust boundary until stronger broader-review conditions are satisfied."
        )

    if governed_review_record_count > 0:
        governed_review_history_summary_text = (
            f"{governed_review_record_count} governed review record"
            f"{'' if governed_review_record_count == 1 else 's'} now preserve approval, block, defer, downgrade, or quarantine history across the current claim family."
        )
    else:
        governed_review_history_summary_text = (
            "No persisted governed review history exists yet for this claim family, so current posture is still coming from live bridge-state rollups."
        )
    promotion_audit_summary_text = (
        f"Promotion boundary currently reads as {promotion_gate_status_label.lower() or 'not recorded'}"
        f" with block reason {promotion_block_reason_label.lower() or 'not recorded'}."
    )
    if claims_with_downgraded_review_count > 0 or claims_with_quarantined_review_count > 0:
        promotion_audit_summary_text += (
            f" {claims_with_downgraded_review_count} downgraded and {claims_with_quarantined_review_count} quarantined claim"
            f"{'' if claims_with_downgraded_review_count + claims_with_quarantined_review_count == 1 else 's'} keep reversal visible instead of silently preserving older stronger posture."
        )

    return validate_claims_summary(
        {
            "claim_count": total,
            "proposed_count": proposed,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "superseded_count": superseded,
            "claims_with_active_support_count": claims_with_active_support_count,
            "claims_with_historical_support_only_count": claims_with_historical_support_only_count,
            "claims_with_rejected_support_only_count": claims_with_rejected_support_only_count,
            "claims_with_no_governed_support_count": claims_with_no_governed_support_count,
            "continuity_aligned_claim_count": continuity_aligned_claim_count,
            "new_claim_context_count": new_claim_context_count,
            "weak_prior_alignment_count": weak_prior_alignment_count,
            "no_prior_claim_context_count": no_prior_claim_context_count,
            "claims_with_active_governed_continuity_count": claims_with_active_governed_continuity_count,
            "claims_with_tentative_active_continuity_count": claims_with_tentative_active_continuity_count,
            "claims_with_historical_continuity_only_count": claims_with_historical_continuity_only_count,
            "claims_with_sparse_prior_context_count": claims_with_sparse_prior_context_count,
            "claims_with_no_useful_prior_context_count": claims_with_no_useful_prior_context_count,
            "claims_mostly_observed_label_grounded_count": claims_mostly_observed_label_grounded_count,
            "claims_with_numeric_rule_based_support_count": claims_with_numeric_rule_based_support_count,
            "claims_with_weak_basis_support_count": claims_with_weak_basis_support_count,
            "claims_with_mixed_support_basis_count": claims_with_mixed_support_basis_count,
            "claims_with_decision_useful_active_support_count": claims_with_decision_useful_active_support_count,
            "claims_with_limited_active_support_quality_count": claims_with_limited_active_support_quality_count,
            "claims_with_context_limited_active_support_count": claims_with_context_limited_active_support_count,
            "claims_with_weak_or_unresolved_active_support_count": claims_with_weak_or_unresolved_active_support_count,
            "claims_with_posture_governing_support_count": claims_with_posture_governing_support_count,
            "claims_with_tentative_current_support_count": claims_with_tentative_current_support_count,
            "claims_with_accepted_limited_support_count": claims_with_accepted_limited_support_count,
            "claims_with_historical_non_governing_support_count": claims_with_historical_non_governing_support_count,
            "claims_with_contested_current_support_count": claims_with_contested_current_support_count,
            "claims_with_degraded_current_posture_count": claims_with_degraded_current_posture_count,
            "claims_with_historical_stronger_than_current_count": claims_with_historical_stronger_than_current_count,
            "claims_with_contradiction_limited_reuse_count": claims_with_contradiction_limited_reuse_count,
            "claims_with_weakly_reusable_support_count": claims_with_weakly_reusable_support_count,
            "claims_action_ready_follow_up_count": claims_action_ready_follow_up_count,
            "claims_promising_but_need_stronger_evidence_count": claims_promising_but_need_stronger_evidence_count,
            "claims_need_clarifying_experiment_count": claims_need_clarifying_experiment_count,
            "claims_do_not_prioritize_yet_count": claims_do_not_prioritize_yet_count,
            "claims_with_insufficient_governed_basis_count": claims_with_insufficient_governed_basis_count,
            "claims_action_ready_from_active_support_count": claims_action_ready_from_active_support_count,
            "claims_with_active_but_limited_actionability_count": claims_with_active_but_limited_actionability_count,
            "claims_historically_interesting_count": claims_historically_interesting_count,
            "claims_with_mixed_current_historical_actionability_count": claims_with_mixed_current_historical_actionability_count,
            "claims_with_no_active_governed_support_actionability_count": claims_with_no_active_governed_support_actionability_count,
            "summary_text": summary_text,
            "chronology_summary_text": chronology_summary_text,
            "claim_support_basis_summary_text": claim_support_basis_summary_text,
            "claim_actionability_summary_text": claim_actionability_summary_text,
            "claim_actionability_basis_summary_text": claim_actionability_basis_summary_text,
            "read_across_summary_text": read_across_summary_text,
            "broader_reuse_label": broader_reuse_label,
            "broader_reuse_summary_text": broader_reuse_summary_text,
            "broader_continuity_label": broader_continuity_label,
            "broader_continuity_summary_text": broader_continuity_summary_text,
            "future_reuse_candidacy_label": future_reuse_candidacy_label,
            "future_reuse_candidacy_summary_text": future_reuse_candidacy_summary_text,
            "continuity_cluster_posture_label": continuity_cluster_posture_label,
            "continuity_cluster_posture_summary_text": continuity_cluster_posture_summary_text,
            "promotion_candidate_posture_label": promotion_candidate_posture_label,
            "promotion_candidate_posture_summary_text": promotion_candidate_posture_summary_text,
            "promotion_stability_label": promotion_stability_label,
            "promotion_stability_summary_text": promotion_stability_summary_text,
            "promotion_gate_status_label": promotion_gate_status_label,
            "promotion_gate_status_summary_text": promotion_gate_status_summary_text,
            "promotion_block_reason_label": promotion_block_reason_label,
            "promotion_block_reason_summary_text": promotion_block_reason_summary_text,
            "source_class_label": source_class_label,
            "source_class_summary_text": source_class_summary_text,
            "trust_tier_label": trust_tier_label,
            "trust_tier_summary_text": trust_tier_summary_text,
            "provenance_confidence_label": provenance_confidence_label,
            "provenance_confidence_summary_text": provenance_confidence_summary_text,
            "governed_review_status_label": governed_review_status_label,
            "governed_review_status_summary_text": governed_review_status_summary_text,
            "governed_review_reason_label": governed_review_reason_label,
            "governed_review_reason_summary_text": governed_review_reason_summary_text,
            "governed_review_record_count": governed_review_record_count,
            "governed_review_history_summary_text": governed_review_history_summary_text,
            "promotion_audit_summary_text": promotion_audit_summary_text,
            "top_claims": claim_refs[:3],
        }
    )


def attach_claims_to_scientific_session_truth(
    scientific_truth: dict[str, Any],
    claims: list[dict[str, Any]],
    *,
    belief_updates: list[dict[str, Any]] | None = None,
    prior_claims: list[dict[str, Any]] | None = None,
    prior_belief_updates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(scientific_truth, dict):
        return scientific_truth
    updated = dict(scientific_truth)
    updated["claim_refs"] = claim_refs_from_records(
        claims,
        belief_updates=belief_updates,
        prior_claims=prior_claims,
        prior_belief_updates=prior_belief_updates,
    )
    updated["claims_summary"] = claims_summary_from_records(
        claims,
        belief_updates=belief_updates,
        prior_claims=prior_claims,
        prior_belief_updates=prior_belief_updates,
    )
    return validate_scientific_session_truth(updated)


__all__ = [
    "attach_claims_to_scientific_session_truth",
    "build_claim_record",
    "claim_refs_from_records",
    "claims_summary_from_records",
    "create_session_claims",
    "list_session_claims",
    "sync_claim_governed_review_snapshot",
]
