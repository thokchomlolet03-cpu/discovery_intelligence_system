from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    BeliefStateReference,
    validate_belief_state_record,
    validate_belief_state_reference,
    validate_belief_state_summary,
)
from system.db.repositories import BeliefStateRepository, BeliefUpdateRepository, ClaimRepository
from system.services.support_quality_service import (
    assess_support_coherence,
    classify_governed_support_posture,
    rollup_governed_support_postures,
    SUPPORT_QUALITY_CONTEXT_LIMITED,
    SUPPORT_QUALITY_DECISION_USEFUL,
    SUPPORT_QUALITY_WEAK,
    classify_belief_update_support_quality,
    rollup_quality_labels,
)


belief_state_repository = BeliefStateRepository()
belief_update_repository = BeliefUpdateRepository()
claim_repository = ClaimRepository()


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


def build_target_key(target_definition: dict[str, Any] | None) -> str:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    parts = [
        _clean_text(target_definition.get("target_name"), default="target_not_recorded").lower(),
        _clean_text(target_definition.get("target_kind"), default="classification").lower(),
        _clean_text(target_definition.get("optimization_direction"), default="classify").lower(),
        _clean_text(target_definition.get("measurement_column")).lower(),
        _clean_text(target_definition.get("dataset_type")).lower(),
    ]
    return "|".join(part for part in parts if part)


def _claim_target_definition(claim_payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = claim_payload.get("target_definition_snapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def _governance_mix_label(*, accepted_count: int, proposed_count: int) -> str:
    if accepted_count <= 0 and proposed_count <= 0:
        return "No tracked support"
    if accepted_count <= 0:
        return "Mostly proposed"
    if proposed_count <= 0:
        return "Mostly accepted"
    if accepted_count >= proposed_count * 2:
        return "Mostly accepted"
    if proposed_count >= accepted_count * 2:
        return "Mostly proposed"
    return "Mixed governance"


def _support_basis_mix_from_updates(updates: list[dict[str, Any]]) -> dict[str, Any]:
    observed_label_support_count = 0
    numeric_rule_based_support_count = 0
    unresolved_basis_count = 0
    weak_basis_count = 0
    for update in updates:
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

    total = len(updates)
    if total <= 0:
        return {
            "support_basis_mix_label": "No support basis recorded",
            "support_basis_mix_summary": "No active support-basis composition is recorded yet for the current target-scoped picture.",
            "observed_label_support_count": 0,
            "numeric_rule_based_support_count": 0,
            "unresolved_basis_count": 0,
            "weak_basis_count": 0,
        }
    if (
        observed_label_support_count > 0
        and observed_label_support_count >= max(numeric_rule_based_support_count, unresolved_basis_count)
        and observed_label_support_count >= weak_basis_count
        and numeric_rule_based_support_count == 0
    ):
        label = "Grounded mostly in observed labels"
        summary = (
            f"The current support picture is grounded mostly in observed labels ({observed_label_support_count}) and remains bounded rather than final."
        )
    elif (
        numeric_rule_based_support_count > 0
        and numeric_rule_based_support_count >= max(observed_label_support_count, unresolved_basis_count)
        and numeric_rule_based_support_count >= weak_basis_count
        and observed_label_support_count == 0
    ):
        label = "Includes bounded numeric interpretation"
        summary = (
            f"The current support picture includes bounded numeric interpretation under current target rules ({numeric_rule_based_support_count}) and should still be read cautiously."
        )
    elif unresolved_basis_count > 0 and unresolved_basis_count >= max(observed_label_support_count, numeric_rule_based_support_count):
        label = "Mostly unresolved or weak-basis"
        summary = (
            f"The current support picture remains largely tentative because {unresolved_basis_count} active support change"
            f"{'' if unresolved_basis_count == 1 else 's'} remain unresolved under the current basis."
        )
    else:
        label = "Mixed support basis"
        summary = (
            f"The current support picture uses a mixed basis: {observed_label_support_count} observed-label, "
            f"{numeric_rule_based_support_count} numeric-rule-based, {unresolved_basis_count} unresolved, and "
            f"{weak_basis_count} weak-basis active support change{'s' if weak_basis_count != 1 else ''}."
        )
    return {
        "support_basis_mix_label": label,
        "support_basis_mix_summary": summary,
        "observed_label_support_count": observed_label_support_count,
        "numeric_rule_based_support_count": numeric_rule_based_support_count,
        "unresolved_basis_count": unresolved_basis_count,
        "weak_basis_count": weak_basis_count,
    }


def _belief_state_strength_summary(
    *,
    active_claim_count: int,
    accepted_count: int,
    proposed_count: int,
    supported_claim_count: int,
    weakened_claim_count: int,
    support_quality_counts: dict[str, int] | None = None,
    posture_counts: dict[str, int] | None = None,
    historical_decision_useful_count: int = 0,
    coherence: dict[str, Any] | None = None,
) -> str:
    support_quality_counts = support_quality_counts if isinstance(support_quality_counts, dict) else {}
    posture_counts = posture_counts if isinstance(posture_counts, dict) else {}
    coherence = coherence if isinstance(coherence, dict) else {}
    if active_claim_count <= 0:
        return "No tracked support picture is recorded yet."
    if bool(coherence.get("current_support_contested_flag")) and bool(coherence.get("current_posture_degraded_flag")):
        return "The current support picture is both contested and degraded, so mixed or weakening evidence should materially reduce present decision strength."
    if bool(coherence.get("current_posture_degraded_flag")):
        return "The current support picture remains active, but weakening evidence or stronger historical support degrades present posture."
    if bool(coherence.get("current_support_contested_flag")):
        return "The current support picture is active but contested, so present posture should stay more cautious than the existence of active records alone suggests."
    if int(posture_counts.get("governing_count") or 0) > 0:
        return "The current support picture includes accepted support that is strong enough to help govern present posture, while still remaining bounded and non-final."
    if int(posture_counts.get("accepted_limited_count") or 0) > 0:
        return "The current support picture includes accepted support, but that accepted support is still limited or context-limited and should count only weakly in present posture."
    if historical_decision_useful_count > 0 and int(posture_counts.get("governing_count") or 0) <= 0:
        return "The current support picture has been materially weakened because stronger prior support is now historical only rather than current."
    if int(posture_counts.get("tentative_count") or 0) > 0 and accepted_count <= 0:
        return "The current support picture is active, but it remains tentative because current support is still proposed rather than posture-governing."
    if int(support_quality_counts.get("weak_count") or 0) >= max(
        int(support_quality_counts.get("decision_useful_count") or 0),
        int(support_quality_counts.get("limited_count") or 0),
        int(support_quality_counts.get("context_limited_count") or 0),
    ) and int(support_quality_counts.get("weak_count") or 0) > 0:
        return "The current support picture is active, but much of it remains weak or unresolved under the current basis."
    if int(support_quality_counts.get("context_limited_count") or 0) > 0 and int(
        support_quality_counts.get("context_limited_count") or 0
    ) >= max(
        int(support_quality_counts.get("decision_useful_count") or 0),
        int(support_quality_counts.get("limited_count") or 0),
        int(support_quality_counts.get("weak_count") or 0),
    ):
        return "The current support picture is active, but assay or target-context limitations keep it from being strongly decision-useful yet."
    if int(support_quality_counts.get("decision_useful_count") or 0) > 0 and accepted_count > 0:
        return "The current support picture includes some decision-useful active support, but it still remains bounded and non-final."
    if accepted_count <= 0:
        return "The current support picture is tentative because it is built entirely from proposed support-change records."
    if accepted_count >= 3 and accepted_count >= proposed_count and supported_claim_count > weakened_claim_count:
        return "The current support picture is more grounded because multiple accepted updates point in a similar direction, but it remains non-final."
    if accepted_count >= 2 and proposed_count <= accepted_count:
        return "The current support picture has some accepted grounding, but it is still limited and should be read cautiously."
    return "The current support picture is mixed because accepted and proposed support changes are both contributing."


def _belief_state_readiness_summary(
    *,
    active_claim_count: int,
    accepted_count: int,
    proposed_count: int,
    support_quality_counts: dict[str, int] | None = None,
    posture_counts: dict[str, int] | None = None,
    historical_decision_useful_count: int = 0,
    coherence: dict[str, Any] | None = None,
) -> str:
    support_quality_counts = support_quality_counts if isinstance(support_quality_counts, dict) else {}
    posture_counts = posture_counts if isinstance(posture_counts, dict) else {}
    coherence = coherence if isinstance(coherence, dict) else {}
    if active_claim_count <= 0:
        return "No strong belief context is recorded yet for read-across."
    if bool(coherence.get("current_support_contested_flag")) and bool(coherence.get("current_posture_degraded_flag")):
        return "Read-across should stay clarification-heavy because current support is contested and degraded rather than cleanly reusable."
    if bool(coherence.get("current_posture_degraded_flag")):
        return "Read-across should stay cautious because current posture is degraded by weakening evidence or stronger historical context."
    if bool(coherence.get("current_support_contested_flag")):
        return "Read-across remains cautious because mixed active support adds contradiction pressure to the present support picture."
    if int(posture_counts.get("governing_count") or 0) > 0:
        return "Read-across and bounded follow-up are more reasonable because some current support is accepted and posture-governing under the available evidence."
    if historical_decision_useful_count > 0 and int(posture_counts.get("governing_count") or 0) <= 0:
        return "Read-across should stay cautious because stronger prior support is now historical only, so current posture is weaker than the history alone suggests."
    if int(posture_counts.get("accepted_limited_count") or 0) > 0:
        return "Read-across remains cautious because accepted current support is still limited or context-limited rather than fully posture-governing."
    if int(posture_counts.get("tentative_count") or 0) > 0:
        return "Read-across remains cautious because current support is still proposed and tentative."
    if int(support_quality_counts.get("decision_useful_count") or 0) > 0:
        return "Read-across and bounded follow-up are more reasonable because some current support is decision-useful under the available evidence."
    if int(support_quality_counts.get("context_limited_count") or 0) > 0:
        return "Read-across remains partial because active support is still context-limited and better suited to clarification than strong follow-up."
    if int(support_quality_counts.get("weak_count") or 0) > 0:
        return "Read-across remains weak because much of the current support picture is still weak or unresolved."
    if accepted_count <= 0:
        return "Read-across remains weak because the current support picture is entirely proposed."
    if accepted_count == 1 and proposed_count <= 1:
        return "Read-across is still partial because only one accepted support-change record is available."
    if accepted_count >= 2 and active_claim_count >= 3:
        return "Read-across is stronger because multiple accepted updates contribute to the current target-scoped support picture."
    return "Read-across is partial because some accepted support exists, but the picture remains update-light."


def _belief_state_alignment(
    *,
    belief_state: dict[str, Any] | None,
    session_belief_updates: list[dict[str, Any]] | None,
) -> tuple[str, str]:
    belief_state = belief_state if isinstance(belief_state, dict) else {}
    session_belief_updates = session_belief_updates if isinstance(session_belief_updates, list) else []
    basis_mix_label = _clean_text(
        belief_state.get("support_basis_mix_label") or ((belief_state.get("metadata") or {}).get("support_basis_mix_label"))
    ).lower()
    basis_phrase = ""
    if basis_mix_label:
        basis_phrase = f" The current support picture is {basis_mix_label}."
    if not belief_state:
        return ("No belief state", "No target-scoped belief state is recorded yet, so read-across against a current support picture is not available.")

    accepted_in_state = _safe_int((belief_state.get("metadata") or {}).get("accepted_update_count"), 0)
    if not session_belief_updates:
        if accepted_in_state > 0:
            return (
                "Weak read-across",
                "A target-scoped belief picture exists, but this session does not add a belief update, so alignment with the current support picture remains weak." + basis_phrase,
            )
        return (
            "No strong belief context yet",
            "This target has only tentative or absent support-change records, so there is no strong belief context for read-across yet.",
        )

    proposed_count = 0
    accepted_count = 0
    rejected_count = 0
    superseded_count = 0
    strengthened_count = 0
    weakened_count = 0
    unresolved_count = 0
    for update in session_belief_updates:
        if not isinstance(update, dict):
            continue
        governance = _clean_text(update.get("governance_status")).lower()
        if governance == "accepted":
            accepted_count += 1
        elif governance == "proposed":
            proposed_count += 1
        elif governance == "superseded":
            superseded_count += 1
            continue
        elif governance == "rejected":
            rejected_count += 1
            continue
        direction = _clean_text(update.get("update_direction")).lower()
        if direction == "strengthened":
            strengthened_count += 1
        elif direction == "weakened":
            weakened_count += 1
        elif direction == "unresolved":
            unresolved_count += 1

    if accepted_count <= 0 and proposed_count <= 0 and superseded_count > 0 and rejected_count <= 0:
        return (
            "Weak read-across",
            "This session currently contributes only superseded historical support-change records, so it does not add active governed support to the current target-scoped picture." + basis_phrase,
        )
    if accepted_count <= 0 and proposed_count <= 0 and rejected_count > 0:
        return (
            "Weak read-across",
            "This session currently contributes only rejected support-change records, so it does not add governed support to the active target-scoped picture." + basis_phrase,
        )

    if weakened_count > 0 and strengthened_count <= 0:
        return (
            "Partial alignment",
            "This session weakens part of the current support picture, so read-across should stay cautious rather than be treated as contradiction or proof." + basis_phrase,
        )
    if unresolved_count > 0 and strengthened_count <= 0 and weakened_count <= 0:
        return (
            "Partial alignment",
            "This session adds unresolved evidence to the current support picture rather than clearly strengthening or weakening it." + basis_phrase,
        )
    if strengthened_count > 0 and weakened_count <= 0:
        if accepted_count > 0 and accepted_in_state > 0:
            return (
                "Strong alignment",
                "This session aligns with the current support picture and includes accepted support-change records, but that still does not make the picture final truth." + basis_phrase,
            )
        return (
            "Partial alignment",
            "This session aligns with the current support picture, but the added support remains mostly proposed or otherwise limited." + basis_phrase,
        )
    if strengthened_count > 0 and weakened_count > 0:
        return (
            "Partial alignment",
            "This session both strengthens and weakens parts of the current support picture, so read-across is mixed rather than strong." + basis_phrase,
        )
    return (
        "Weak read-across",
        "This session does not add enough directional support-change context for strong read-across against the current belief picture." + basis_phrase,
    )


def _active_updates_for_target(*, workspace_id: str, target_key: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, int]]:
    updates = belief_update_repository.list_belief_updates(workspace_id=workspace_id)
    latest_by_claim: dict[str, dict[str, Any]] = {}
    target_definition_snapshot: dict[str, Any] = {}
    rejected_count = 0
    superseded_count = 0
    historical_decision_useful_count = 0
    for update in updates:
        if not isinstance(update, dict):
            continue
        claim_id = _clean_text(update.get("claim_id"))
        if not claim_id:
            continue
        try:
            claim_payload = claim_repository.get_claim(claim_id, workspace_id=workspace_id)
        except FileNotFoundError:
            continue
        claim_target_definition = _claim_target_definition(claim_payload)
        if build_target_key(claim_target_definition) != target_key:
            continue
        governance = _clean_text(update.get("governance_status")).lower()
        if governance == "rejected":
            rejected_count += 1
        if governance == "superseded":
            superseded_count += 1
            support_quality_label = _clean_text(
                update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label")
            )
            if not support_quality_label:
                support_quality_label = classify_belief_update_support_quality(update).get("support_quality_label", "")
            if support_quality_label == SUPPORT_QUALITY_DECISION_USEFUL:
                historical_decision_useful_count += 1
        if governance in {"rejected", "superseded"}:
            continue
        if not target_definition_snapshot:
            target_definition_snapshot = claim_target_definition
        current = latest_by_claim.get(claim_id)
        if current is None or _clean_text(update.get("created_at")) > _clean_text(current.get("created_at")):
            latest_by_claim[claim_id] = update
    latest_updates = sorted(
        latest_by_claim.values(),
        key=lambda item: _clean_text(item.get("created_at")),
        reverse=True,
    )
    counts = {
        "accepted_update_count": sum(
            1 for update in latest_updates if _clean_text(update.get("governance_status")).lower() == "accepted"
        ),
        "proposed_update_count": sum(
            1 for update in latest_updates if _clean_text(update.get("governance_status")).lower() == "proposed"
        ),
        "rejected_update_count": rejected_count,
        "superseded_update_count": superseded_count,
        "historical_decision_useful_support_count": historical_decision_useful_count,
    }
    return latest_updates, target_definition_snapshot, counts


def belief_state_reference_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return validate_belief_state_reference(
        {
            "belief_state_id": record.get("belief_state_id"),
            "target_key": record.get("target_key"),
            "summary_text": record.get("summary_text"),
            "active_claim_count": record.get("active_claim_count"),
            "supported_claim_count": record.get("supported_claim_count"),
            "weakened_claim_count": record.get("weakened_claim_count"),
            "unresolved_claim_count": record.get("unresolved_claim_count"),
            "last_updated_at": record.get("last_updated_at"),
            "last_update_source": record.get("last_update_source"),
            "version": record.get("version"),
        }
    )


def belief_state_summary_from_record(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return validate_belief_state_summary(
        {
            "summary_text": record.get("summary_text"),
            "support_distribution_summary": record.get("support_distribution_summary"),
            "governance_scope_summary": record.get("governance_scope_summary"),
            "chronology_summary_text": record.get("chronology_summary_text") or metadata.get("chronology_summary_text"),
            "support_basis_mix_label": record.get("support_basis_mix_label") or metadata.get("support_basis_mix_label"),
            "support_basis_mix_summary": record.get("support_basis_mix_summary") or metadata.get("support_basis_mix_summary"),
            "support_quality_label": record.get("support_quality_label") or metadata.get("support_quality_label"),
            "support_quality_summary": record.get("support_quality_summary") or metadata.get("support_quality_summary"),
            "governed_support_posture_label": record.get("governed_support_posture_label")
            or metadata.get("governed_support_posture_label"),
            "governed_support_posture_summary": record.get("governed_support_posture_summary")
            or metadata.get("governed_support_posture_summary"),
            "support_coherence_label": record.get("support_coherence_label") or metadata.get("support_coherence_label"),
            "support_coherence_summary": record.get("support_coherence_summary") or metadata.get("support_coherence_summary"),
            "support_reuse_label": record.get("support_reuse_label") or metadata.get("support_reuse_label"),
            "support_reuse_summary": record.get("support_reuse_summary") or metadata.get("support_reuse_summary"),
            "broader_target_reuse_label": record.get("broader_target_reuse_label")
            or metadata.get("broader_target_reuse_label"),
            "broader_target_reuse_summary": record.get("broader_target_reuse_summary")
            or metadata.get("broader_target_reuse_summary"),
            "broader_target_continuity_label": record.get("broader_target_continuity_label")
            or metadata.get("broader_target_continuity_label"),
            "broader_target_continuity_summary": record.get("broader_target_continuity_summary")
            or metadata.get("broader_target_continuity_summary"),
            "future_reuse_candidacy_label": record.get("future_reuse_candidacy_label")
            or metadata.get("future_reuse_candidacy_label"),
            "future_reuse_candidacy_summary": record.get("future_reuse_candidacy_summary")
            or metadata.get("future_reuse_candidacy_summary"),
            "continuity_cluster_posture_label": record.get("continuity_cluster_posture_label")
            or metadata.get("continuity_cluster_posture_label"),
            "continuity_cluster_posture_summary": record.get("continuity_cluster_posture_summary")
            or metadata.get("continuity_cluster_posture_summary"),
            "promotion_candidate_posture_label": record.get("promotion_candidate_posture_label")
            or metadata.get("promotion_candidate_posture_label"),
            "promotion_candidate_posture_summary": record.get("promotion_candidate_posture_summary")
            or metadata.get("promotion_candidate_posture_summary"),
            "promotion_stability_label": record.get("promotion_stability_label")
            or metadata.get("promotion_stability_label"),
            "promotion_stability_summary": record.get("promotion_stability_summary")
            or metadata.get("promotion_stability_summary"),
            "promotion_gate_status_label": record.get("promotion_gate_status_label")
            or metadata.get("promotion_gate_status_label"),
            "promotion_gate_status_summary": record.get("promotion_gate_status_summary")
            or metadata.get("promotion_gate_status_summary"),
            "promotion_block_reason_label": record.get("promotion_block_reason_label")
            or metadata.get("promotion_block_reason_label"),
            "promotion_block_reason_summary": record.get("promotion_block_reason_summary")
            or metadata.get("promotion_block_reason_summary"),
            "trust_tier_label": record.get("trust_tier_label") or metadata.get("trust_tier_label"),
            "trust_tier_summary": record.get("trust_tier_summary") or metadata.get("trust_tier_summary"),
            "provenance_confidence_label": record.get("provenance_confidence_label")
            or metadata.get("provenance_confidence_label"),
            "provenance_confidence_summary": record.get("provenance_confidence_summary")
            or metadata.get("provenance_confidence_summary"),
            "governed_review_status_label": record.get("governed_review_status_label")
            or metadata.get("governed_review_status_label"),
            "governed_review_status_summary": record.get("governed_review_status_summary")
            or metadata.get("governed_review_status_summary"),
            "governed_review_reason_label": record.get("governed_review_reason_label")
            or metadata.get("governed_review_reason_label"),
            "governed_review_reason_summary": record.get("governed_review_reason_summary")
            or metadata.get("governed_review_reason_summary"),
            "belief_state_strength_summary": record.get("belief_state_strength_summary")
            or metadata.get("belief_state_strength_summary"),
            "belief_state_readiness_summary": record.get("belief_state_readiness_summary")
            or metadata.get("belief_state_readiness_summary"),
            "governance_mix_label": record.get("governance_mix_label") or metadata.get("governance_mix_label"),
            "active_claim_count": record.get("active_claim_count"),
            "supported_claim_count": record.get("supported_claim_count"),
            "weakened_claim_count": record.get("weakened_claim_count"),
            "unresolved_claim_count": record.get("unresolved_claim_count"),
            "accepted_update_count": metadata.get("accepted_update_count"),
            "proposed_update_count": metadata.get("proposed_update_count"),
            "rejected_update_count": metadata.get("rejected_update_count"),
            "superseded_update_count": metadata.get("superseded_update_count"),
            "observed_label_support_count": metadata.get("observed_label_support_count"),
            "numeric_rule_based_support_count": metadata.get("numeric_rule_based_support_count"),
            "unresolved_basis_count": metadata.get("unresolved_basis_count"),
            "weak_basis_count": metadata.get("weak_basis_count"),
            "decision_useful_active_support_count": metadata.get("decision_useful_active_support_count"),
            "active_but_limited_support_count": metadata.get("active_but_limited_support_count"),
            "context_limited_support_count": metadata.get("context_limited_support_count"),
            "weak_or_unresolved_support_count": metadata.get("weak_or_unresolved_support_count"),
            "posture_governing_support_count": metadata.get("posture_governing_support_count"),
            "tentative_current_support_count": metadata.get("tentative_current_support_count"),
            "accepted_limited_support_count": metadata.get("accepted_limited_support_count"),
            "historical_non_governing_support_count": metadata.get("historical_non_governing_support_count"),
            "contradiction_pressure_count": metadata.get("contradiction_pressure_count"),
            "weakly_reusable_support_count": metadata.get("weakly_reusable_support_count"),
            "current_support_contested_flag": metadata.get("current_support_contested_flag"),
            "current_posture_degraded_flag": metadata.get("current_posture_degraded_flag"),
            "historical_support_stronger_than_current_flag": metadata.get("historical_support_stronger_than_current_flag"),
            "last_updated_at": record.get("last_updated_at"),
            "last_update_source": record.get("last_update_source"),
        }
    )


def build_belief_state_record(
    *,
    workspace_id: str,
    target_definition_snapshot: dict[str, Any] | None,
    latest_updates: list[dict[str, Any]],
    governance_counts: dict[str, int] | None = None,
    previous_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_definition_snapshot = target_definition_snapshot if isinstance(target_definition_snapshot, dict) else {}
    governance_counts = governance_counts if isinstance(governance_counts, dict) else {}
    target_key = build_target_key(target_definition_snapshot)
    if not target_key:
        raise ValueError("BeliefState requires a target definition snapshot with a stable target key.")
    active_claim_count = len(latest_updates)
    supported_claim_count = sum(1 for update in latest_updates if _clean_text(update.get("update_direction")).lower() == "strengthened")
    weakened_claim_count = sum(1 for update in latest_updates if _clean_text(update.get("update_direction")).lower() == "weakened")
    unresolved_claim_count = sum(1 for update in latest_updates if _clean_text(update.get("update_direction")).lower() == "unresolved")
    proposed_count = _safe_int(governance_counts.get("proposed_update_count"), 0)
    accepted_count = _safe_int(governance_counts.get("accepted_update_count"), 0)
    rejected_count = _safe_int(governance_counts.get("rejected_update_count"), 0)
    superseded_count = _safe_int(governance_counts.get("superseded_update_count"), 0)
    historical_decision_useful_count = _safe_int(governance_counts.get("historical_decision_useful_support_count"), 0)
    last_update = latest_updates[0] if latest_updates else {}
    last_updated_at = last_update.get("created_at") or _utc_now()
    last_update_source = "latest belief update"
    if _clean_text(last_update.get("experiment_result_id")):
        last_update_source = "latest belief update linked to an observed result"
    target_name = _clean_text(target_definition_snapshot.get("target_name"), default="the current target objective")
    governance_mix_label = _governance_mix_label(accepted_count=accepted_count, proposed_count=proposed_count)
    support_basis_mix = _support_basis_mix_from_updates(latest_updates)
    support_quality_counts = rollup_quality_labels(
        [
            (update.get("support_quality_label") or (update.get("metadata") or {}).get("support_quality_label"))
            or classify_belief_update_support_quality(update).get("support_quality_label")
            for update in latest_updates
        ]
    )
    posture_counts = rollup_governed_support_postures(
        [
            (update.get("governed_support_posture_label") or (update.get("metadata") or {}).get("governed_support_posture_label"))
            or classify_governed_support_posture(update).get("governed_support_posture_label")
            for update in latest_updates
        ]
    )
    coherence = assess_support_coherence(
        active_count=active_claim_count,
        accepted_count=accepted_count,
        strengthened_count=supported_claim_count,
        weakened_count=weakened_claim_count,
        unresolved_count=unresolved_claim_count,
        support_quality_counts=support_quality_counts,
        posture_counts=posture_counts,
        historical_decision_useful_count=historical_decision_useful_count,
        superseded_count=superseded_count,
    )
    if active_claim_count <= 0:
        support_quality_label = "No active support quality yet"
        support_quality_summary = "No active governed support picture is recorded yet for this target."
    elif support_quality_counts["decision_useful_count"] > 0 and support_quality_counts["weak_count"] <= 0 and support_quality_counts["context_limited_count"] <= 0:
        support_quality_label = "Current support includes decision-useful grounding"
        support_quality_summary = (
            f"{support_quality_counts['decision_useful_count']} active support change"
            f"{'' if support_quality_counts['decision_useful_count'] == 1 else 's'} currently look decision-useful enough for bounded follow-up."
        )
    elif support_quality_counts["weak_count"] >= max(
        support_quality_counts["decision_useful_count"],
        support_quality_counts["limited_count"],
        support_quality_counts["context_limited_count"],
    ) and support_quality_counts["weak_count"] > 0:
        support_quality_label = "Current support remains weak or unresolved"
        support_quality_summary = (
            f"{support_quality_counts['weak_count']} active support change"
            f"{'' if support_quality_counts['weak_count'] == 1 else 's'} remain weak or unresolved under the current basis."
        )
    elif support_quality_counts["context_limited_count"] >= max(
        support_quality_counts["decision_useful_count"],
        support_quality_counts["limited_count"],
        support_quality_counts["weak_count"],
    ) and support_quality_counts["context_limited_count"] > 0:
        support_quality_label = "Current support is context-limited"
        support_quality_summary = (
            f"{support_quality_counts['context_limited_count']} active support change"
            f"{'' if support_quality_counts['context_limited_count'] == 1 else 's'} still depend on assay or target-context clarification."
        )
    else:
        support_quality_label = "Current support remains active but limited"
        support_quality_summary = (
            f"{support_quality_counts['limited_count']} active support change"
            f"{'' if support_quality_counts['limited_count'] == 1 else 's'} remain present but still limited for stronger follow-up."
        )
    if active_claim_count <= 0:
        governed_support_posture_label = "No current posture-governing support"
        governed_support_posture_summary = "No active governed support currently governs present posture for this target."
    elif posture_counts["governing_count"] > 0:
        governed_support_posture_label = "Current support governs present posture"
        governed_support_posture_summary = (
            f"{posture_counts['governing_count']} accepted support change"
            f"{'' if posture_counts['governing_count'] == 1 else 's'} currently govern present posture for bounded follow-up."
        )
        if posture_counts["tentative_count"] > 0 or posture_counts["accepted_limited_count"] > 0:
            governed_support_posture_summary += (
                f" {posture_counts['tentative_count']} active change"
                f"{'' if posture_counts['tentative_count'] == 1 else 's'} remain tentative and "
                f"{posture_counts['accepted_limited_count']} accepted change"
                f"{'' if posture_counts['accepted_limited_count'] == 1 else 's'} count only weakly."
            )
    elif posture_counts["accepted_limited_count"] > 0:
        governed_support_posture_label = "Accepted support remains limited-weight"
        governed_support_posture_summary = (
            f"{posture_counts['accepted_limited_count']} accepted support change"
            f"{'' if posture_counts['accepted_limited_count'] == 1 else 's'} remain too limited or context-limited to govern present posture strongly."
        )
    elif posture_counts["tentative_count"] > 0:
        governed_support_posture_label = "Current support remains tentative"
        governed_support_posture_summary = (
            f"{posture_counts['tentative_count']} active support change"
            f"{'' if posture_counts['tentative_count'] == 1 else 's'} remain proposed, so present posture should stay cautious."
        )
    else:
        governed_support_posture_label = "Historical support only"
        governed_support_posture_summary = (
            "Only historical or otherwise non-posture-governing support remains visible for this target."
        )
    if historical_decision_useful_count > 0 and posture_counts["governing_count"] <= 0:
        governed_support_posture_summary += (
            f" {historical_decision_useful_count} superseded support change"
            f"{'' if historical_decision_useful_count == 1 else 's'} previously looked more decision-useful, but now remain historical only."
        )
    belief_state_strength_summary = _belief_state_strength_summary(
        active_claim_count=active_claim_count,
        accepted_count=accepted_count,
        proposed_count=proposed_count,
        supported_claim_count=supported_claim_count,
        weakened_claim_count=weakened_claim_count,
        support_quality_counts=support_quality_counts,
        posture_counts=posture_counts,
        historical_decision_useful_count=historical_decision_useful_count,
        coherence=coherence,
    )
    belief_state_readiness_summary = _belief_state_readiness_summary(
        active_claim_count=active_claim_count,
        accepted_count=accepted_count,
        proposed_count=proposed_count,
        support_quality_counts=support_quality_counts,
        posture_counts=posture_counts,
        historical_decision_useful_count=historical_decision_useful_count,
        coherence=coherence,
    )
    summary_text = (
        f"Current belief state for {target_name} tracks {active_claim_count} active claim{'s' if active_claim_count != 1 else ''}: "
        f"{supported_claim_count} strengthened, {weakened_claim_count} weakened, and {unresolved_claim_count} unresolved. "
        "This is a bounded support summary, not final scientific truth or live learning state."
    )
    support_distribution_summary = (
        f"Supported {supported_claim_count}, weakened {weakened_claim_count}, unresolved {unresolved_claim_count} across "
        f"{active_claim_count} currently tracked claim{'s' if active_claim_count != 1 else ''}."
    )
    governance_scope_summary = (
        f"Current picture includes {accepted_count} accepted and {proposed_count} proposed belief update"
        f"{'' if accepted_count + proposed_count == 1 else 's'}; rejected and superseded updates are excluded. "
        f"Governance mix: {governance_mix_label.lower()}. "
        f"{posture_counts['governing_count']} currently govern posture, {posture_counts['tentative_count']} remain tentative, and {posture_counts['accepted_limited_count']} accepted update"
        f"{'' if posture_counts['accepted_limited_count'] == 1 else 's'} count only weakly."
    )
    governance_scope_summary += (
        f" {coherence['contradiction_pressure_count']} active update"
        f"{'' if coherence['contradiction_pressure_count'] == 1 else 's'} add contradiction pressure."
    )
    chronology_summary_text = (
        f"Current support picture relies on {active_claim_count} active claim-linked support change"
        f"{'' if active_claim_count == 1 else 's'} and keeps {superseded_count} superseded plus {rejected_count} rejected historical record"
        f"{'' if superseded_count + rejected_count == 1 else 's'} visible for context."
    )
    previous_version = _safe_int((previous_record or {}).get("version"), 0)
    return validate_belief_state_record(
        {
            "belief_state_id": _clean_text((previous_record or {}).get("belief_state_id")),
            "workspace_id": workspace_id,
            "target_key": target_key,
            "target_definition_snapshot": target_definition_snapshot,
            "summary_text": summary_text,
            "active_claim_count": active_claim_count,
            "supported_claim_count": supported_claim_count,
            "weakened_claim_count": weakened_claim_count,
            "unresolved_claim_count": unresolved_claim_count,
            "last_updated_at": last_updated_at,
            "last_update_source": last_update_source,
            "version": max(1, previous_version + 1),
            "latest_belief_update_refs": latest_updates[:3],
            "support_distribution_summary": support_distribution_summary,
            "governance_scope_summary": governance_scope_summary,
            "chronology_summary_text": chronology_summary_text,
            "support_basis_mix_label": support_basis_mix["support_basis_mix_label"],
            "support_basis_mix_summary": support_basis_mix["support_basis_mix_summary"],
            "observed_label_support_count": support_basis_mix["observed_label_support_count"],
            "numeric_rule_based_support_count": support_basis_mix["numeric_rule_based_support_count"],
            "unresolved_basis_count": support_basis_mix["unresolved_basis_count"],
            "weak_basis_count": support_basis_mix["weak_basis_count"],
            "support_quality_label": support_quality_label,
            "support_quality_summary": support_quality_summary,
            "decision_useful_active_support_count": support_quality_counts["decision_useful_count"],
            "active_but_limited_support_count": support_quality_counts["limited_count"],
            "context_limited_support_count": support_quality_counts["context_limited_count"],
            "weak_or_unresolved_support_count": support_quality_counts["weak_count"],
            "governed_support_posture_label": governed_support_posture_label,
            "governed_support_posture_summary": governed_support_posture_summary,
            "posture_governing_support_count": posture_counts["governing_count"],
            "tentative_current_support_count": posture_counts["tentative_count"],
            "accepted_limited_support_count": posture_counts["accepted_limited_count"],
            "historical_non_governing_support_count": superseded_count,
            "support_coherence_label": coherence["support_coherence_label"],
            "support_coherence_summary": coherence["support_coherence_summary"],
            "support_reuse_label": coherence["support_reuse_label"],
            "support_reuse_summary": coherence["support_reuse_summary"],
            "contradiction_pressure_count": coherence["contradiction_pressure_count"],
            "weakly_reusable_support_count": coherence["weakly_reusable_support_count"],
            "current_support_contested_flag": coherence["current_support_contested_flag"],
            "current_posture_degraded_flag": coherence["current_posture_degraded_flag"],
            "historical_support_stronger_than_current_flag": coherence["historical_support_stronger_than_current_flag"],
            "belief_state_strength_summary": belief_state_strength_summary,
            "belief_state_readiness_summary": belief_state_readiness_summary,
            "governance_mix_label": governance_mix_label,
            "metadata": {
                "accepted_update_count": accepted_count,
                "proposed_update_count": proposed_count,
                "rejected_update_count": rejected_count,
                "superseded_update_count": superseded_count,
                "chronology_summary_text": chronology_summary_text,
                "support_basis_mix_label": support_basis_mix["support_basis_mix_label"],
                "support_basis_mix_summary": support_basis_mix["support_basis_mix_summary"],
                "observed_label_support_count": support_basis_mix["observed_label_support_count"],
                "numeric_rule_based_support_count": support_basis_mix["numeric_rule_based_support_count"],
                "unresolved_basis_count": support_basis_mix["unresolved_basis_count"],
                "weak_basis_count": support_basis_mix["weak_basis_count"],
                "support_quality_label": support_quality_label,
                "support_quality_summary": support_quality_summary,
                "decision_useful_active_support_count": support_quality_counts["decision_useful_count"],
                "active_but_limited_support_count": support_quality_counts["limited_count"],
                "context_limited_support_count": support_quality_counts["context_limited_count"],
                "weak_or_unresolved_support_count": support_quality_counts["weak_count"],
                "governed_support_posture_label": governed_support_posture_label,
                "governed_support_posture_summary": governed_support_posture_summary,
                "posture_governing_support_count": posture_counts["governing_count"],
                "tentative_current_support_count": posture_counts["tentative_count"],
                "accepted_limited_support_count": posture_counts["accepted_limited_count"],
                "historical_non_governing_support_count": superseded_count,
                "support_coherence_label": coherence["support_coherence_label"],
                "support_coherence_summary": coherence["support_coherence_summary"],
                "support_reuse_label": coherence["support_reuse_label"],
                "support_reuse_summary": coherence["support_reuse_summary"],
                "contradiction_pressure_count": coherence["contradiction_pressure_count"],
                "weakly_reusable_support_count": coherence["weakly_reusable_support_count"],
                "current_support_contested_flag": coherence["current_support_contested_flag"],
                "current_posture_degraded_flag": coherence["current_posture_degraded_flag"],
                "historical_support_stronger_than_current_flag": coherence["historical_support_stronger_than_current_flag"],
                "belief_state_strength_summary": belief_state_strength_summary,
                "belief_state_readiness_summary": belief_state_readiness_summary,
                "governance_mix_label": governance_mix_label,
            },
        }
    )


def refresh_belief_state(
    *,
    workspace_id: str,
    target_definition_snapshot: dict[str, Any] | None = None,
    claim_id: str = "",
) -> dict[str, Any] | None:
    if not target_definition_snapshot and claim_id:
        claim_payload = claim_repository.get_claim(claim_id, workspace_id=workspace_id)
        target_definition_snapshot = _claim_target_definition(claim_payload)
    target_definition_snapshot = target_definition_snapshot if isinstance(target_definition_snapshot, dict) else {}
    target_key = build_target_key(target_definition_snapshot)
    if not target_key:
        return None
    latest_updates, effective_target_definition, governance_counts = _active_updates_for_target(
        workspace_id=workspace_id,
        target_key=target_key,
    )
    if not latest_updates:
        belief_state_repository.delete_belief_state(workspace_id=workspace_id, target_key=target_key)
        return None
    try:
        previous = belief_state_repository.get_belief_state(workspace_id=workspace_id, target_key=target_key)
    except FileNotFoundError:
        previous = None
    payload = build_belief_state_record(
        workspace_id=workspace_id,
        target_definition_snapshot=effective_target_definition or target_definition_snapshot,
        latest_updates=latest_updates,
        governance_counts=governance_counts,
        previous_record=previous,
    )
    return belief_state_repository.upsert_belief_state(payload)


def get_belief_state_for_target(
    *,
    workspace_id: str,
    target_definition_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    target_key = build_target_key(target_definition_snapshot)
    if not target_key:
        return None
    try:
        return belief_state_repository.get_belief_state(workspace_id=workspace_id, target_key=target_key)
    except FileNotFoundError:
        return None


def describe_belief_state_alignment(
    *,
    belief_state: dict[str, Any] | None,
    session_belief_updates: list[dict[str, Any]] | None,
) -> dict[str, str]:
    label, summary = _belief_state_alignment(
        belief_state=belief_state,
        session_belief_updates=session_belief_updates,
    )
    return {
        "label": label,
        "summary": summary,
    }


__all__ = [
    "describe_belief_state_alignment",
    "belief_state_reference_from_record",
    "belief_state_summary_from_record",
    "build_target_key",
    "get_belief_state_for_target",
    "refresh_belief_state",
]
