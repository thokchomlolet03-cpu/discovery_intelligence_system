from __future__ import annotations

from typing import Any

from system.contracts import validate_scientific_decision_summary
from system.services.governed_review_service import compose_session_family_review_posture
from system.services.support_quality_service import (
    assess_continuity_cluster_promotion,
    assess_governed_promotion_boundary,
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
)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_scientific_decision_summary(scientific_truth: dict[str, Any] | None) -> dict[str, Any]:
    scientific_truth = scientific_truth if isinstance(scientific_truth, dict) else {}
    claims_summary = scientific_truth.get("claims_summary") if isinstance(scientific_truth.get("claims_summary"), dict) else {}
    request_summary = (
        scientific_truth.get("experiment_request_summary")
        if isinstance(scientific_truth.get("experiment_request_summary"), dict)
        else {}
    )
    result_summary = (
        scientific_truth.get("linked_result_summary")
        if isinstance(scientific_truth.get("linked_result_summary"), dict)
        else {}
    )
    belief_update_summary = (
        scientific_truth.get("belief_update_summary")
        if isinstance(scientific_truth.get("belief_update_summary"), dict)
        else {}
    )
    belief_state_summary = (
        scientific_truth.get("belief_state_summary")
        if isinstance(scientific_truth.get("belief_state_summary"), dict)
        else {}
    )
    evidence_activation_policy = (
        scientific_truth.get("evidence_activation_policy")
        if isinstance(scientific_truth.get("evidence_activation_policy"), dict)
        else {}
    )

    active_ready = _safe_int(claims_summary.get("claims_action_ready_from_active_support_count"))
    active_limited = _safe_int(claims_summary.get("claims_with_active_but_limited_actionability_count"))
    historical_only = _safe_int(claims_summary.get("claims_historically_interesting_count"))
    mixed_current_historical = _safe_int(
        claims_summary.get("claims_with_mixed_current_historical_actionability_count")
    )
    no_active = _safe_int(claims_summary.get("claims_with_no_active_governed_support_actionability_count"))
    insufficient_basis = _safe_int(claims_summary.get("claims_with_insufficient_governed_basis_count"))
    active_support_claims = _safe_int(claims_summary.get("claims_with_active_support_count"))

    result_count = _safe_int(result_summary.get("result_count"))
    bounded_numeric = _safe_int(result_summary.get("bounded_numeric_interpretation_count"))
    unresolved_numeric = _safe_int(result_summary.get("unresolved_numeric_interpretation_count"))
    cautious_quality = _safe_int(result_summary.get("cautious_result_quality_count"))
    assay_context_recorded = _safe_int(result_summary.get("assay_context_recorded_count"))
    decision_useful_results = _safe_int(result_summary.get("decision_useful_result_count"))
    limited_results = _safe_int(result_summary.get("limited_result_support_count"))
    context_limited_results = _safe_int(result_summary.get("context_limited_result_count"))
    unresolved_results = _safe_int(result_summary.get("unresolved_result_support_count"))
    update_count = _safe_int(belief_update_summary.get("update_count"))
    active_updates = _safe_int(belief_update_summary.get("active_count"))
    decision_useful_active_support = _safe_int(belief_update_summary.get("decision_useful_active_support_count"))
    limited_active_support = _safe_int(belief_update_summary.get("active_but_limited_support_count"))
    context_limited_active_support = _safe_int(belief_update_summary.get("context_limited_active_support_count"))
    weak_active_support = _safe_int(belief_update_summary.get("weak_or_unresolved_active_support_count"))
    posture_governing_support = _safe_int(belief_update_summary.get("posture_governing_support_count"))
    tentative_active_support = _safe_int(belief_update_summary.get("tentative_active_support_count"))
    accepted_limited_support = _safe_int(belief_update_summary.get("accepted_limited_weight_support_count"))
    historical_non_governing_support = _safe_int(belief_update_summary.get("historical_non_governing_support_count"))
    contradiction_pressure = _safe_int(belief_update_summary.get("contradiction_pressure_count"))
    weakly_reusable_support = _safe_int(belief_update_summary.get("weakly_reusable_support_count"))
    contested_support = bool(belief_update_summary.get("current_support_contested_flag"))
    degraded_posture = bool(belief_update_summary.get("current_posture_degraded_flag"))
    historical_stronger = bool(belief_update_summary.get("historical_support_stronger_than_current_flag"))
    active_belief_claims = _safe_int(belief_state_summary.get("active_claim_count"))
    belief_state_support_quality_label = _clean_text(belief_state_summary.get("support_quality_label"))
    belief_state_support_quality_summary = _clean_text(belief_state_summary.get("support_quality_summary"))
    belief_state_governed_posture_label = _clean_text(belief_state_summary.get("governed_support_posture_label"))
    belief_state_governed_posture_summary = _clean_text(belief_state_summary.get("governed_support_posture_summary"))
    belief_state_support_coherence_label = _clean_text(belief_state_summary.get("support_coherence_label"))
    belief_state_support_coherence_summary = _clean_text(belief_state_summary.get("support_coherence_summary"))
    belief_state_support_reuse_label = _clean_text(belief_state_summary.get("support_reuse_label"))
    belief_state_support_reuse_summary = _clean_text(belief_state_summary.get("support_reuse_summary"))
    belief_state_contested_flag = bool(belief_state_summary.get("current_support_contested_flag"))
    belief_state_degraded_flag = bool(belief_state_summary.get("current_posture_degraded_flag"))
    belief_state_historical_stronger_flag = bool(
        belief_state_summary.get("historical_support_stronger_than_current_flag")
    )

    decision_status_label = "No governed support picture yet"
    decision_status_summary = (
        "This session does not yet show a governed claim-support picture, so use the shortlist as bounded context rather than a follow-up-ready scientific state."
    )
    current_support_quality_label = "No active support quality yet"
    current_support_quality_summary = (
        "No active governed support quality is recorded yet, so the current session picture is still mainly a recommendation and review surface."
    )
    current_governed_support_posture_label = "No current posture-governing support"
    current_governed_support_posture_summary = (
        "No active governed support currently governs present posture for this session."
    )
    current_support_coherence_label = "No coherent current support"
    current_support_coherence_summary = (
        "No coherent current support is recorded yet, so the current session picture should stay bounded and review-oriented."
    )
    current_support_reuse_label = "Not yet suitable for strong governed reuse"
    current_support_reuse_summary = (
        "Current support is not yet suitable for strong governed reuse because the active evidence picture is still incomplete."
    )
    broader_governed_reuse_label = "Support is locally meaningful, not broadly governing"
    broader_governed_reuse_summary = (
        "Current support may still be locally useful, but broader governed reuse has not yet been established across related claim or target contexts."
    )
    broader_continuity_label = "No broader continuity cluster"
    broader_continuity_summary = (
        "No meaningful broader continuity cluster is established yet, so read-across should stay bounded and local."
    )
    future_reuse_candidacy_label = "Local-only future reuse context"
    future_reuse_candidacy_summary = (
        "Future broader reuse candidacy remains local-only until cleaner continuity or stronger governed carryover appears."
    )
    continuity_cluster_posture_label = "Local-only continuity cluster"
    continuity_cluster_posture_summary = (
        "Continuity remains local-only right now, so the current session picture should stay within local review boundaries."
    )
    promotion_candidate_posture_label = "Context-only continuity, not a promotion candidate"
    promotion_candidate_posture_summary = (
        "Current continuity is still context-only rather than a broader governed promotion candidate."
    )
    promotion_stability_label = "Insufficient continuity stability"
    promotion_stability_summary = (
        "Current continuity does not yet satisfy enough governed stability for broader promotion review."
    )
    promotion_gate_status_label = "Not a governed promotion candidate"
    promotion_gate_status_summary = (
        "Current continuity is not yet promotable under bounded governed rules and should remain local or contextual."
    )
    promotion_block_reason_label = "Context-only continuity"
    promotion_block_reason_summary = (
        "Current continuity remains context-only, so broader promotion is not yet justified."
    )
    trust_tier_label = "Local-only evidence"
    trust_tier_summary = (
        "Current evidence remains local-only by default. Local usefulness is immediate, but broader influence has not yet been earned."
    )
    provenance_confidence_label = "Unknown provenance"
    provenance_confidence_summary = (
        "Provenance confidence for broader influence remains unknown or incomplete at the session-family level."
    )
    governed_review_status_label = "Not reviewed for broader influence"
    governed_review_status_summary = (
        "No broader governed review posture is recorded yet, so the session-family picture should remain local-first."
    )
    governed_review_reason_label = "Local-only by default"
    governed_review_reason_summary = (
        "The current session-family picture remains local-only by default until stronger trust, provenance, and review conditions are satisfied."
    )
    next_step_label = "Establish governed support first"
    next_step_summary = (
        "Start by reviewing the shortlist claims and recording fresh governed evidence before treating any claim as current decision support."
    )

    if belief_state_contested_flag and belief_state_degraded_flag:
        decision_status_label = "Contested and degraded current posture"
        decision_status_summary = (
            "Current support records still exist, but mixed and weakening evidence now contest and degrade present posture."
        )
        if contradiction_pressure > 0:
            decision_status_summary += (
                f" {contradiction_pressure} active support update"
                f"{'' if contradiction_pressure == 1 else 's'} currently add contradiction pressure."
            )
        next_step_label = "Clarify mixed evidence before stronger follow-up"
        next_step_summary = (
            "Use clarification-heavy follow-up and gather cleaner evidence before treating the session as currently follow-up-worthy."
        )
    elif belief_state_degraded_flag or historical_stronger:
        decision_status_label = "Degraded current posture"
        decision_status_summary = (
            "Current support remains active, but weakening evidence or stronger historical support means present posture should be treated as degraded rather than cleanly strong."
        )
        next_step_label = "Gather stronger evidence before stronger posture"
        next_step_summary = (
            "Gather stronger fresh evidence before treating the session as stronger current decision support."
        )
    elif belief_state_contested_flag or contested_support:
        decision_status_label = "Contested current posture"
        decision_status_summary = (
            "Current support is active on paper, but mixed updates keep the present evidence picture contested and more clarification-heavy."
        )
        next_step_label = "Clarify current support before stronger follow-up"
        next_step_summary = (
            "Use targeted clarification to reduce contradiction pressure before treating the session as cleanly follow-up-ready."
        )
    elif posture_governing_support > 0 or active_ready > 0:
        decision_status_label = "Active governed follow-up basis"
        decision_status_summary = (
            f"{max(active_ready, posture_governing_support)} claim-linked support path{'s are' if max(active_ready, posture_governing_support) != 1 else ' is'} currently posture-governing under active governed support. "
            "Current usefulness is coming from the present active support picture rather than historical context alone."
        )
        if mixed_current_historical > 0 or historical_only > 0:
            decision_status_summary += (
                f" {mixed_current_historical} claim{'s' if mixed_current_historical != 1 else ''} still carry mixed current/historical basis and "
                f"{historical_only} remain historically interesting only."
            )
        next_step_label = "Bounded follow-up is reasonable now"
        next_step_summary = (
            "Use confirmatory or targeted follow-up where active support already exists, while keeping claims explicitly separate from validated truth."
        )
    elif accepted_limited_support > 0:
        decision_status_label = "Accepted support remains limited-weight"
        decision_status_summary = (
            f"{accepted_limited_support} accepted support update{'s' if accepted_limited_support != 1 else ''} currently count only weakly in present posture because the current basis remains limited or context-limited."
        )
        next_step_label = "Gather stronger evidence before stronger posture"
        next_step_summary = (
            "Use the accepted support as bounded context, but gather stronger or cleaner evidence before treating the session as strongly follow-up-ready."
        )
    elif tentative_active_support > 0 or active_limited > 0:
        decision_status_label = "Current active basis remains tentative"
        decision_status_summary = (
            f"{max(tentative_active_support, active_limited)} active support path{'s' if max(tentative_active_support, active_limited) != 1 else ' has'} some current governed support, "
            "but the present basis remains tentative and should not yet be treated as posture-governing."
        )
        next_step_label = "Strengthen current support first"
        next_step_summary = (
            "A bounded strengthening experiment is reasonable, but current support should still be treated as tentative rather than follow-up-ready."
        )
    elif mixed_current_historical > 0:
        decision_status_label = "Mixed current/historical claim picture"
        decision_status_summary = (
            f"{mixed_current_historical} claim{'s show' if mixed_current_historical != 1 else ' shows'} a mixed current and historical support picture. "
            "The current basis is not yet clean enough to read as straightforward present actionability."
        )
        next_step_label = "Clarify with targeted experiment"
        next_step_summary = (
            "Use a clarifying experiment to separate present support from older context before treating the claim as current decision support."
        )
    elif historical_only > 0:
        decision_status_label = "Historical-interest claim picture"
        decision_status_summary = (
            f"{historical_only} claim{'s remain' if historical_only != 1 else ' remains'} historically interesting, "
            "but current usefulness is coming from older support context rather than active governed support."
        )
        if historical_non_governing_support > 0:
            decision_status_summary += (
                f" {historical_non_governing_support} superseded support record"
                f"{'' if historical_non_governing_support == 1 else 's'} remain historically informative but not posture-governing."
            )
        next_step_label = "Gather fresh evidence before acting"
        next_step_summary = (
            "Treat historical support as context only and gather fresh governed evidence before acting on the claim now."
        )
    elif no_active > 0 or insufficient_basis > 0:
        decision_status_label = "No active governed claim support"
        decision_status_summary = (
            "Claims are present, but none currently have active governed support strong enough to justify present follow-up."
        )
        next_step_label = "Treat current claims as bounded context"
        next_step_summary = (
            "Use the shortlist and claims to focus review, but do not treat them as active decision support until governed evidence is refreshed."
        )
    elif active_support_claims > 0 or active_updates > 0 or active_belief_claims > 0:
        decision_status_label = "Support revision is underway"
        decision_status_summary = (
            "The session now carries active support revision, but the current claim picture remains better suited to review than to direct follow-up commitment."
        )
        next_step_label = "Review support changes before acting"
        next_step_summary = (
            "Use the updated belief state and claim summaries to decide whether any claim has moved from context into bounded follow-up readiness."
        )

    if belief_state_support_quality_label:
        current_support_quality_label = belief_state_support_quality_label
        current_support_quality_summary = belief_state_support_quality_summary
    elif decision_useful_active_support > 0 and weak_active_support <= 0 and context_limited_active_support <= 0:
        current_support_quality_label = "Current support includes decision-useful grounding"
        current_support_quality_summary = (
            f"{decision_useful_active_support} active support update"
            f"{'' if decision_useful_active_support == 1 else 's'} currently look decision-useful enough for bounded follow-up."
        )
    elif weak_active_support >= max(decision_useful_active_support, limited_active_support, context_limited_active_support) and weak_active_support > 0:
        current_support_quality_label = "Current support remains weak or unresolved"
        current_support_quality_summary = (
            f"{weak_active_support} active support update"
            f"{'' if weak_active_support == 1 else 's'} remain weak or unresolved under the current basis."
        )
    elif context_limited_active_support >= max(decision_useful_active_support, limited_active_support, weak_active_support) and context_limited_active_support > 0:
        current_support_quality_label = "Current support is context-limited"
        current_support_quality_summary = (
            f"{context_limited_active_support} active support update"
            f"{'' if context_limited_active_support == 1 else 's'} still depend on assay or target-context clarification."
        )
    elif limited_active_support > 0:
        current_support_quality_label = "Current support remains active but limited"
        current_support_quality_summary = (
            f"{limited_active_support} active support update"
            f"{'' if limited_active_support == 1 else 's'} remain present but still limited for stronger follow-up."
        )
    if belief_state_governed_posture_label:
        current_governed_support_posture_label = belief_state_governed_posture_label
        current_governed_support_posture_summary = belief_state_governed_posture_summary
    elif posture_governing_support > 0:
        current_governed_support_posture_label = "Current support governs present posture"
        current_governed_support_posture_summary = (
            f"{posture_governing_support} accepted support update"
            f"{'' if posture_governing_support == 1 else 's'} currently govern present posture for bounded follow-up."
        )
    elif accepted_limited_support > 0:
        current_governed_support_posture_label = "Accepted support remains limited-weight"
        current_governed_support_posture_summary = (
            f"{accepted_limited_support} accepted support update"
            f"{'' if accepted_limited_support == 1 else 's'} remain too limited or context-limited to govern present posture strongly."
        )
    elif tentative_active_support > 0:
        current_governed_support_posture_label = "Current support remains tentative"
        current_governed_support_posture_summary = (
            f"{tentative_active_support} active support update"
            f"{'' if tentative_active_support == 1 else 's'} remain proposed, so present posture should stay cautious."
        )
    elif historical_non_governing_support > 0:
        current_governed_support_posture_label = "Historical support only"
        current_governed_support_posture_summary = (
            f"{historical_non_governing_support} superseded support record"
            f"{'' if historical_non_governing_support == 1 else 's'} remain historically informative but do not govern present posture."
        )
    if belief_state_support_coherence_label:
        current_support_coherence_label = belief_state_support_coherence_label
        current_support_coherence_summary = belief_state_support_coherence_summary
    elif contested_support and degraded_posture:
        current_support_coherence_label = "Contested and degraded current support"
        current_support_coherence_summary = (
            "Current support is both contested and degraded, so mixed evidence should materially reduce present decision strength."
        )
    elif degraded_posture or historical_stronger:
        current_support_coherence_label = "Current posture is degraded"
        current_support_coherence_summary = (
            "Current support remains active, but weakening evidence or stronger historical context reduces how strongly it should matter now."
        )
    elif contested_support:
        current_support_coherence_label = "Current support is contested"
        current_support_coherence_summary = (
            "Current support is active, but contradiction pressure keeps the present picture contested rather than cleanly strong."
        )
    elif posture_governing_support > 0:
        current_support_coherence_label = "Coherent current support"
        current_support_coherence_summary = (
            "Current support is coherent enough to help govern present posture under the available evidence."
        )
    if belief_state_support_reuse_label:
        current_support_reuse_label = belief_state_support_reuse_label
        current_support_reuse_summary = belief_state_support_reuse_summary
    elif contested_support or degraded_posture:
        current_support_reuse_label = "Reuse with contradiction caution"
        current_support_reuse_summary = (
            "Current support should be reused only with contradiction caution because mixed or weakening evidence reduces how cleanly it carries forward."
        )
    elif weakly_reusable_support > 0:
        current_support_reuse_label = "Weakly reusable current support"
        current_support_reuse_summary = (
            "Current support remains only weakly reusable because limited, tentative, or context-limited updates still dominate the active picture."
        )
    elif posture_governing_support > 0:
        current_support_reuse_label = "Strongly reusable governed support"
        current_support_reuse_summary = (
            "Current support is the cleanest basis for future bounded governed reuse because it is coherent and posture-governing."
        )

    belief_state_broader_reuse_label = _clean_text(belief_state_summary.get("broader_target_reuse_label"))
    belief_state_broader_reuse_summary = _clean_text(belief_state_summary.get("broader_target_reuse_summary"))
    belief_state_broader_continuity_label = _clean_text(belief_state_summary.get("broader_target_continuity_label"))
    belief_state_broader_continuity_summary = _clean_text(
        belief_state_summary.get("broader_target_continuity_summary")
    )
    belief_state_future_reuse_candidacy_label = _clean_text(
        belief_state_summary.get("future_reuse_candidacy_label")
    )
    belief_state_future_reuse_candidacy_summary = _clean_text(
        belief_state_summary.get("future_reuse_candidacy_summary")
    )
    belief_state_continuity_cluster_posture_label = _clean_text(
        belief_state_summary.get("continuity_cluster_posture_label")
    )
    belief_state_continuity_cluster_posture_summary = _clean_text(
        belief_state_summary.get("continuity_cluster_posture_summary")
    )
    belief_state_promotion_candidate_posture_label = _clean_text(
        belief_state_summary.get("promotion_candidate_posture_label")
    )
    belief_state_promotion_candidate_posture_summary = _clean_text(
        belief_state_summary.get("promotion_candidate_posture_summary")
    )
    belief_state_promotion_stability_label = _clean_text(
        belief_state_summary.get("promotion_stability_label")
    )
    belief_state_promotion_stability_summary = _clean_text(
        belief_state_summary.get("promotion_stability_summary")
    )
    belief_state_promotion_gate_status_label = _clean_text(
        belief_state_summary.get("promotion_gate_status_label")
    )
    belief_state_promotion_gate_status_summary = _clean_text(
        belief_state_summary.get("promotion_gate_status_summary")
    )
    belief_state_promotion_block_reason_label = _clean_text(
        belief_state_summary.get("promotion_block_reason_label")
    )
    belief_state_promotion_block_reason_summary = _clean_text(
        belief_state_summary.get("promotion_block_reason_summary")
    )
    claims_broader_reuse_label = _clean_text(claims_summary.get("broader_reuse_label"))
    claims_broader_reuse_summary = _clean_text(claims_summary.get("broader_reuse_summary_text"))
    claims_broader_continuity_label = _clean_text(claims_summary.get("broader_continuity_label"))
    claims_broader_continuity_summary = _clean_text(claims_summary.get("broader_continuity_summary_text"))
    claims_future_reuse_candidacy_label = _clean_text(claims_summary.get("future_reuse_candidacy_label"))
    claims_future_reuse_candidacy_summary = _clean_text(
        claims_summary.get("future_reuse_candidacy_summary_text")
    )
    claims_continuity_cluster_posture_label = _clean_text(claims_summary.get("continuity_cluster_posture_label"))
    claims_continuity_cluster_posture_summary = _clean_text(
        claims_summary.get("continuity_cluster_posture_summary_text")
    )
    claims_promotion_candidate_posture_label = _clean_text(
        claims_summary.get("promotion_candidate_posture_label")
    )
    claims_promotion_candidate_posture_summary = _clean_text(
        claims_summary.get("promotion_candidate_posture_summary_text")
    )
    claims_promotion_stability_label = _clean_text(claims_summary.get("promotion_stability_label"))
    claims_promotion_stability_summary = _clean_text(
        claims_summary.get("promotion_stability_summary_text")
    )
    claims_promotion_gate_status_label = _clean_text(claims_summary.get("promotion_gate_status_label"))
    claims_promotion_gate_status_summary = _clean_text(
        claims_summary.get("promotion_gate_status_summary_text")
    )
    claims_promotion_block_reason_label = _clean_text(claims_summary.get("promotion_block_reason_label"))
    claims_promotion_block_reason_summary = _clean_text(
        claims_summary.get("promotion_block_reason_summary_text")
    )
    trust_tier_label = _clean_text(
        belief_state_summary.get("trust_tier_label")
        or claims_summary.get("trust_tier_label")
        or evidence_activation_policy.get("trust_tier_label"),
        default=trust_tier_label,
    )
    trust_tier_summary = _clean_text(
        belief_state_summary.get("trust_tier_summary")
        or claims_summary.get("trust_tier_summary_text")
        or evidence_activation_policy.get("trust_tier_summary"),
        default=trust_tier_summary,
    )
    provenance_confidence_label = _clean_text(
        belief_state_summary.get("provenance_confidence_label")
        or claims_summary.get("provenance_confidence_label")
        or evidence_activation_policy.get("provenance_confidence_label"),
        default=provenance_confidence_label,
    )
    provenance_confidence_summary = _clean_text(
        belief_state_summary.get("provenance_confidence_summary")
        or claims_summary.get("provenance_confidence_summary_text")
        or evidence_activation_policy.get("provenance_confidence_summary"),
        default=provenance_confidence_summary,
    )
    governed_review_status_label = _clean_text(
        belief_state_summary.get("governed_review_status_label")
        or claims_summary.get("governed_review_status_label")
        or evidence_activation_policy.get("governed_review_status_label"),
        default=governed_review_status_label,
    )
    governed_review_status_summary = _clean_text(
        belief_state_summary.get("governed_review_status_summary")
        or claims_summary.get("governed_review_status_summary_text")
        or evidence_activation_policy.get("governed_review_status_summary"),
        default=governed_review_status_summary,
    )
    governed_review_reason_label = _clean_text(
        belief_state_summary.get("governed_review_reason_label")
        or claims_summary.get("governed_review_reason_label")
        or evidence_activation_policy.get("governed_review_reason_label"),
        default=governed_review_reason_label,
    )
    governed_review_reason_summary = _clean_text(
        belief_state_summary.get("governed_review_reason_summary")
        or claims_summary.get("governed_review_reason_summary_text")
        or evidence_activation_policy.get("governed_review_reason_summary"),
        default=governed_review_reason_summary,
    )

    if belief_state_broader_reuse_label:
        broader_governed_reuse_label = belief_state_broader_reuse_label
        broader_governed_reuse_summary = belief_state_broader_reuse_summary or broader_governed_reuse_summary
    elif claims_broader_reuse_label:
        broader_governed_reuse_label = claims_broader_reuse_label
        broader_governed_reuse_summary = claims_broader_reuse_summary or broader_governed_reuse_summary
    elif current_support_reuse_label == "Reuse with contradiction caution":
        broader_governed_reuse_label = BROADER_REUSE_CONTRADICTION_LIMITED
        broader_governed_reuse_summary = (
            "Broader governed reuse should stay contradiction-limited because current support is contested or degraded even if local support still exists."
        )
    elif current_support_reuse_label == "Strongly reusable governed support":
        broader_governed_reuse_label = BROADER_REUSE_LOCAL_ONLY
        broader_governed_reuse_summary = (
            "Current support is strong locally, but that does not automatically make it strongly reusable across related claim or target contexts."
        )

    if belief_state_broader_continuity_label:
        broader_continuity_label = belief_state_broader_continuity_label
        broader_continuity_summary = belief_state_broader_continuity_summary or broader_continuity_summary
    elif claims_broader_continuity_label:
        broader_continuity_label = claims_broader_continuity_label
        broader_continuity_summary = claims_broader_continuity_summary or broader_continuity_summary

    if belief_state_future_reuse_candidacy_label:
        future_reuse_candidacy_label = belief_state_future_reuse_candidacy_label
        future_reuse_candidacy_summary = (
            belief_state_future_reuse_candidacy_summary or future_reuse_candidacy_summary
        )
    elif claims_future_reuse_candidacy_label:
        future_reuse_candidacy_label = claims_future_reuse_candidacy_label
        future_reuse_candidacy_summary = (
            claims_future_reuse_candidacy_summary or future_reuse_candidacy_summary
        )

    if belief_state_continuity_cluster_posture_label:
        continuity_cluster_posture_label = belief_state_continuity_cluster_posture_label
        continuity_cluster_posture_summary = (
            belief_state_continuity_cluster_posture_summary or continuity_cluster_posture_summary
        )
    elif claims_continuity_cluster_posture_label:
        continuity_cluster_posture_label = claims_continuity_cluster_posture_label
        continuity_cluster_posture_summary = (
            claims_continuity_cluster_posture_summary or continuity_cluster_posture_summary
        )

    if belief_state_promotion_candidate_posture_label:
        promotion_candidate_posture_label = belief_state_promotion_candidate_posture_label
        promotion_candidate_posture_summary = (
            belief_state_promotion_candidate_posture_summary or promotion_candidate_posture_summary
        )
    elif claims_promotion_candidate_posture_label:
        promotion_candidate_posture_label = claims_promotion_candidate_posture_label
        promotion_candidate_posture_summary = (
            claims_promotion_candidate_posture_summary or promotion_candidate_posture_summary
        )
    if belief_state_promotion_stability_label:
        promotion_stability_label = belief_state_promotion_stability_label
        promotion_stability_summary = belief_state_promotion_stability_summary or promotion_stability_summary
    elif claims_promotion_stability_label:
        promotion_stability_label = claims_promotion_stability_label
        promotion_stability_summary = claims_promotion_stability_summary or promotion_stability_summary

    if belief_state_promotion_gate_status_label:
        promotion_gate_status_label = belief_state_promotion_gate_status_label
        promotion_gate_status_summary = (
            belief_state_promotion_gate_status_summary or promotion_gate_status_summary
        )
    elif claims_promotion_gate_status_label:
        promotion_gate_status_label = claims_promotion_gate_status_label
        promotion_gate_status_summary = claims_promotion_gate_status_summary or promotion_gate_status_summary

    if belief_state_promotion_block_reason_label:
        promotion_block_reason_label = belief_state_promotion_block_reason_label
        promotion_block_reason_summary = (
            belief_state_promotion_block_reason_summary or promotion_block_reason_summary
        )
    elif claims_promotion_block_reason_label:
        promotion_block_reason_label = claims_promotion_block_reason_label
        promotion_block_reason_summary = (
            claims_promotion_block_reason_summary or promotion_block_reason_summary
        )

    if (
        not belief_state_promotion_candidate_posture_label
        and not claims_promotion_candidate_posture_label
    ):
        cluster_scope = assess_continuity_cluster_promotion(
            active_support_count=active_support_claims,
            continuity_evidence_count=_safe_int(claims_summary.get("continuity_aligned_claim_count")),
            governing_continuity_count=_safe_int(
                claims_summary.get("claims_with_active_governed_continuity_count")
            ),
            tentative_continuity_count=_safe_int(
                claims_summary.get("claims_with_tentative_active_continuity_count")
            ),
            contested_continuity_count=_safe_int(
                claims_summary.get("claims_with_contradiction_limited_reuse_count")
            ),
            historical_continuity_count=_safe_int(
                claims_summary.get("claims_with_historical_continuity_only_count")
            ),
            broader_reuse_label=broader_governed_reuse_label,
            broader_continuity_label=broader_continuity_label,
            future_reuse_candidacy_label=future_reuse_candidacy_label,
            contested_flag=belief_state_contested_flag or contested_support,
            degraded_flag=belief_state_degraded_flag or degraded_posture,
            historical_stronger_flag=belief_state_historical_stronger_flag or historical_stronger,
        )
        continuity_cluster_posture_label = cluster_scope["continuity_cluster_posture_label"]
        promotion_candidate_posture_label = cluster_scope["promotion_candidate_posture_label"]
    if (
        not belief_state_promotion_stability_label
        and not claims_promotion_stability_label
        and not belief_state_promotion_gate_status_label
        and not claims_promotion_gate_status_label
    ):
        promotion_boundary = assess_governed_promotion_boundary(
            active_support_count=active_support_claims,
            continuity_evidence_count=_safe_int(claims_summary.get("continuity_aligned_claim_count")),
            governing_continuity_count=_safe_int(
                claims_summary.get("claims_with_active_governed_continuity_count")
            ),
            tentative_continuity_count=_safe_int(
                claims_summary.get("claims_with_tentative_active_continuity_count")
            ),
            contested_continuity_count=_safe_int(
                claims_summary.get("claims_with_contradiction_limited_reuse_count")
            ),
            historical_continuity_count=_safe_int(
                claims_summary.get("claims_with_historical_continuity_only_count")
            ),
            broader_reuse_label=broader_governed_reuse_label,
            broader_continuity_label=broader_continuity_label,
            continuity_cluster_posture_label=continuity_cluster_posture_label,
            promotion_candidate_posture_label=promotion_candidate_posture_label,
            contested_flag=belief_state_contested_flag or contested_support,
            degraded_flag=belief_state_degraded_flag or degraded_posture,
            historical_stronger_flag=belief_state_historical_stronger_flag or historical_stronger,
        )
        promotion_stability_label = promotion_boundary["promotion_stability_label"]
        promotion_gate_status_label = promotion_boundary["promotion_gate_status_label"]
        promotion_block_reason_label = promotion_boundary["promotion_block_reason_label"]

    if broader_governed_reuse_label == BROADER_REUSE_STRONG and broader_continuity_label == BROADER_CONTINUITY_COHERENT:
        broader_governed_reuse_summary = broader_governed_reuse_summary or (
            "Broader governed reuse is strongest here because current posture is coherent and related continuity also remains coherent."
        )
    elif broader_governed_reuse_label == BROADER_REUSE_SELECTIVE and broader_continuity_label in {
        BROADER_CONTINUITY_SELECTIVE,
        BROADER_CONTINUITY_HISTORICAL,
    }:
        broader_governed_reuse_summary = broader_governed_reuse_summary or (
            "Broader governed reuse is only selective: some continuity exists, but it is too mixed, limited, or historical-heavy for stronger carryover."
        )
    elif broader_governed_reuse_label == BROADER_REUSE_HISTORICAL_ONLY:
        broader_governed_reuse_summary = broader_governed_reuse_summary or (
            "Broader governed reuse is mainly historical-only: older support remains informative, but it should not behave like strong current reuse."
        )
    elif broader_governed_reuse_label == BROADER_REUSE_LOCAL_ONLY and current_support_reuse_label:
        broader_governed_reuse_summary = broader_governed_reuse_summary or (
            "Current support may still matter locally, but broader governed reuse is not yet justified by the related continuity picture."
        )

    if broader_continuity_label == BROADER_CONTINUITY_CONTESTED and not broader_continuity_summary:
        broader_continuity_summary = (
            "Broader continuity exists, but contested or degraded present posture means the continuity cluster should be discounted."
        )
    elif broader_continuity_label == BROADER_CONTINUITY_NONE and not broader_continuity_summary:
        broader_continuity_summary = (
            "No meaningful broader continuity cluster is established yet, so current support should stay local and reviewable."
        )

    if future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_STRONG and not future_reuse_candidacy_summary:
        future_reuse_candidacy_summary = (
            "This session now looks like a stronger later candidate for broader governed reuse if the bounded current posture remains coherent."
        )
    elif (
        future_reuse_candidacy_label == FUTURE_REUSE_CANDIDACY_CONTRADICTION_LIMITED
        and not future_reuse_candidacy_summary
    ):
        future_reuse_candidacy_summary = (
            "Future broader reuse candidacy is contradiction-limited because mixed or degraded history still weakens broader carryover."
        )

    if continuity_cluster_posture_label == CONTINUITY_CLUSTER_PROMOTION_CANDIDATE and not continuity_cluster_posture_summary:
        continuity_cluster_posture_summary = (
            "This session-family continuity cluster is a promotion candidate because current support and broader continuity both remain coherent enough to matter beyond local context."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_SELECTIVE and not continuity_cluster_posture_summary:
        continuity_cluster_posture_summary = (
            "This session-family continuity cluster is selective: it matters beyond local context, but it remains too bounded for stronger promotion."
        )
    elif (
        continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTRADICTION_LIMITED
        and not continuity_cluster_posture_summary
    ):
        continuity_cluster_posture_summary = (
            "This session-family continuity cluster is contradiction-limited because contested or degraded continuity keeps it visible for review but not cleanly promotable."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_HISTORICAL and not continuity_cluster_posture_summary:
        continuity_cluster_posture_summary = (
            "This session-family continuity cluster is historical-heavy: it remains informative as context, but mainly through older continuity rather than stronger present posture."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_CONTEXT_ONLY and not continuity_cluster_posture_summary:
        continuity_cluster_posture_summary = (
            "This session-family continuity cluster remains context-only right now: related continuity is visible, but it should not yet travel as a broader promotion candidate."
        )
    elif continuity_cluster_posture_label == CONTINUITY_CLUSTER_LOCAL_ONLY and not continuity_cluster_posture_summary:
        continuity_cluster_posture_summary = (
            "Continuity remains local-only right now, so the current session picture should stay within local review boundaries."
        )

    if promotion_candidate_posture_label == PROMOTION_CANDIDATE_STRONG and not promotion_candidate_posture_summary:
        promotion_candidate_posture_summary = (
            "This session now looks like a stronger broader governed promotion candidate later if the current coherence holds."
        )
    elif (
        promotion_candidate_posture_label == PROMOTION_CANDIDATE_SELECTIVE
        and not promotion_candidate_posture_summary
    ):
        promotion_candidate_posture_summary = (
            "This session is only a selective broader promotion candidate. Stronger or cleaner continuity would still be needed."
        )
    elif (
        promotion_candidate_posture_label == PROMOTION_CANDIDATE_CONTRADICTION_LIMITED
        and not promotion_candidate_posture_summary
    ):
        promotion_candidate_posture_summary = (
            "This session is not a clean promotion candidate because contradiction-heavy or degraded continuity still limits governed carryover."
        )
    elif (
        promotion_candidate_posture_label == PROMOTION_CANDIDATE_HISTORICAL_ONLY
        and not promotion_candidate_posture_summary
    ):
        promotion_candidate_posture_summary = (
            "This session is mainly historical promotion context right now, not a strong current broader promotion candidate."
        )
    elif promotion_candidate_posture_label == PROMOTION_CANDIDATE_CONTEXT_ONLY and not promotion_candidate_posture_summary:
        promotion_candidate_posture_summary = (
            "This session's continuity remains context-only rather than a broader governed promotion candidate."
        )

    if promotion_stability_label == PROMOTION_STABILITY_STABLE and not promotion_stability_summary:
        promotion_stability_summary = (
            "Current session-family continuity is stable enough for governed promotion review because present support and related continuity remain coherent under bounded rules."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_SELECTIVE and not promotion_stability_summary:
        promotion_stability_summary = (
            "Current session-family continuity is only selectively stable for promotion: it may matter later, but stronger or cleaner stability would still be needed."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_UNSTABLE and not promotion_stability_summary:
        promotion_stability_summary = (
            "Current session-family continuity is unstable under contradiction pressure, so stronger promotion should remain blocked or quarantined."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_HISTORICAL and not promotion_stability_summary:
        promotion_stability_summary = (
            "Current session-family continuity is historical-heavy rather than stably current, so it should remain contextual rather than a clean promotion basis."
        )
    elif promotion_stability_label == PROMOTION_STABILITY_INSUFFICIENT and not promotion_stability_summary:
        promotion_stability_summary = (
            "Current session-family continuity does not yet satisfy enough governed stability for broader promotion review."
        )

    if promotion_gate_status_label == PROMOTION_GATE_PROMOTABLE and not promotion_gate_status_summary:
        promotion_gate_status_summary = (
            "Current session-family continuity is promotable under bounded governed rules if the present coherent posture continues to hold."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_SELECTIVE and not promotion_gate_status_summary:
        promotion_gate_status_summary = (
            "Current session-family continuity is only selectively promotable under bounded governed rules and should still be carried with caution."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_DOWNGRADED and not promotion_gate_status_summary:
        promotion_gate_status_summary = (
            "Current session-family continuity has been downgraded from a stronger promotion posture because newer evidence now weakens how broadly it should carry."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_QUARANTINED and not promotion_gate_status_summary:
        promotion_gate_status_summary = (
            "Current session-family continuity is quarantined from stronger promotion because contradiction-heavy and degraded history make it too unstable."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_BLOCKED and not promotion_gate_status_summary:
        promotion_gate_status_summary = (
            "Current session-family continuity is still only a candidate and remains blocked from broader promotion under the current bounded rules."
        )
    elif promotion_gate_status_label == PROMOTION_GATE_NOT_CANDIDATE and not promotion_gate_status_summary:
        promotion_gate_status_summary = (
            "Current session-family continuity is not yet a governed promotion candidate and should remain local or contextual."
        )

    if promotion_block_reason_label == PROMOTION_BLOCK_NONE and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "No material promotion block is currently recorded for the session-family continuity picture."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_LOCAL_ONLY and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion remains blocked because the current support picture is still mainly local-only."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_CONTEXT_ONLY and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion remains blocked because the current continuity is still context-only rather than a promotable broader cluster."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_SELECTIVE_ONLY and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion remains limited because the current continuity is selective only: it matters beyond local context, but is still too bounded for cleaner promotion."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_CONTRADICTION and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion remains blocked by contradiction-heavy history, so broader carryover should stay cautious."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_DEGRADED and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion remains limited by degraded present posture, so earlier stronger continuity should not stay silently promotable."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_HISTORICAL and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion remains historical-only right now: the continuity is visible, but mainly as older context rather than a stronger current promotion basis."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_DOWNGRADED and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion was downgraded by newer contradictory or weaker present evidence, so broader governed carryover should be reduced rather than preserved."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_QUARANTINED and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion is quarantined because current continuity is too unstable under contradiction-heavy and degraded history."
        )
    elif promotion_block_reason_label == PROMOTION_BLOCK_STABILITY and not promotion_block_reason_summary:
        promotion_block_reason_summary = (
            "Promotion remains blocked because the current continuity picture does not yet satisfy enough governed stability conditions."
        )

    result_state_label = "No linked observed results yet"
    result_state_summary = (
        "No observed results are linked to this session yet, so claim usefulness still depends on pre-result evidence and prior support context."
    )
    if result_count > 0:
        result_state_label = "Observed results recorded"
        result_state_summary = (
            f"{result_count} observed result{'s are' if result_count != 1 else ' is'} linked to this session."
        )
        result_bits: list[str] = []
        if bounded_numeric > 0:
            result_bits.append(
                f"{bounded_numeric} numeric result{'s can' if bounded_numeric != 1 else ' can'} be interpreted under the current target rule"
            )
        if unresolved_numeric > 0:
            result_bits.append(
                f"{unresolved_numeric} numeric result{'s remain' if unresolved_numeric != 1 else ' remains'} unresolved under the current numeric basis"
            )
        if cautious_quality > 0:
            result_bits.append(
                f"{cautious_quality} result{'s still carry' if cautious_quality != 1 else ' still carries'} provisional or screening-quality caution"
            )
        if assay_context_recorded > 0:
            result_bits.append(
                f"{assay_context_recorded} result{'s include' if assay_context_recorded != 1 else ' includes'} recorded assay context"
            )
        if decision_useful_results > 0 or limited_results > 0 or context_limited_results > 0 or unresolved_results > 0:
            result_bits.append(
                f"{decision_useful_results} more decision-useful, {limited_results} limited, {context_limited_results} context-limited, and {unresolved_results} unresolved for present support use"
            )
        if result_bits:
            result_state_summary += " " + "; ".join(result_bits) + "."
        if update_count > 0:
            result_state_summary += (
                f" {update_count} belief update{'s have' if update_count != 1 else ' has'} already been recorded, keeping observed outcomes separate from final truth."
            )

    if _safe_int(request_summary.get("request_count")) > 0 and "no linked observed results yet" in result_state_label.lower():
        result_state_summary += " Proposed experiment requests are already present, but they remain recommendations rather than completed lab work."

    session_family_posture = compose_session_family_review_posture(
        source_class_label=_clean_text(
            belief_state_summary.get("source_class_label")
            or claims_summary.get("source_class_label")
            or evidence_activation_policy.get("source_class_label")
        ),
        provenance_confidence_label=provenance_confidence_label,
        broader_governed_reuse_label=broader_governed_reuse_label,
        broader_continuity_label=broader_continuity_label,
        future_reuse_candidacy_label=future_reuse_candidacy_label,
        promotion_gate_status_label=promotion_gate_status_label,
        promotion_block_reason_label=promotion_block_reason_label,
        belief_state_review_status_label=_clean_text(belief_state_summary.get("governed_review_status_label")),
        continuity_cluster_review_status_label=_clean_text(
            belief_state_summary.get("continuity_cluster_review_status_label")
        ),
        active_support_count=active_support_claims,
        claims_with_active_governed_continuity_count=_safe_int(
            claims_summary.get("claims_with_active_governed_continuity_count")
        ),
        claims_with_tentative_active_continuity_count=_safe_int(
            claims_summary.get("claims_with_tentative_active_continuity_count")
        ),
        claims_with_contradiction_limited_reuse_count=_safe_int(
            claims_summary.get("claims_with_contradiction_limited_reuse_count")
        ),
        claims_with_historical_continuity_only_count=_safe_int(
            claims_summary.get("claims_with_historical_continuity_only_count")
        ),
        claims_with_no_governed_support_count=_safe_int(
            claims_summary.get("claims_with_no_governed_support_count")
        ),
        contested_flag=belief_state_contested_flag or contested_support,
        degraded_flag=belief_state_degraded_flag or degraded_posture,
        historical_stronger_flag=belief_state_historical_stronger_flag or historical_stronger,
    )
    trust_tier_label = _clean_text(session_family_posture.get("trust_tier_label"), default=trust_tier_label)
    trust_tier_summary = _clean_text(session_family_posture.get("trust_tier_summary"), default=trust_tier_summary)
    governed_review_status_label = _clean_text(
        session_family_posture.get("governed_review_status_label"),
        default=governed_review_status_label,
    )
    governed_review_status_summary = _clean_text(
        session_family_posture.get("governed_review_status_summary"),
        default=governed_review_status_summary,
    )
    governed_review_reason_label = _clean_text(
        session_family_posture.get("governed_review_reason_label"),
        default=governed_review_reason_label,
    )
    governed_review_reason_summary = _clean_text(
        session_family_posture.get("governed_review_reason_summary"),
        default=governed_review_reason_summary,
    )

    return validate_scientific_decision_summary(
        {
            "decision_status_label": decision_status_label,
            "decision_status_summary": decision_status_summary,
            "current_support_quality_label": current_support_quality_label,
            "current_support_quality_summary": current_support_quality_summary,
            "current_governed_support_posture_label": current_governed_support_posture_label,
            "current_governed_support_posture_summary": current_governed_support_posture_summary,
            "current_support_coherence_label": current_support_coherence_label,
            "current_support_coherence_summary": current_support_coherence_summary,
            "current_support_reuse_label": current_support_reuse_label,
            "current_support_reuse_summary": current_support_reuse_summary,
            "broader_governed_reuse_label": broader_governed_reuse_label,
            "broader_governed_reuse_summary": broader_governed_reuse_summary,
            "broader_continuity_label": broader_continuity_label,
            "broader_continuity_summary": broader_continuity_summary,
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
            "trust_tier_label": trust_tier_label,
            "trust_tier_summary": trust_tier_summary,
            "provenance_confidence_label": provenance_confidence_label,
            "provenance_confidence_summary": provenance_confidence_summary,
            "governed_review_status_label": governed_review_status_label,
            "governed_review_status_summary": governed_review_status_summary,
            "governed_review_reason_label": governed_review_reason_label,
            "governed_review_reason_summary": governed_review_reason_summary,
            "session_family_review_status_label": governed_review_status_label,
            "session_family_review_status_summary": governed_review_status_summary,
            "session_family_review_reason_label": governed_review_reason_label,
            "session_family_review_reason_summary": governed_review_reason_summary,
            "session_family_review_record_count": 0,
            "session_family_review_history_summary": "",
            "session_family_promotion_audit_summary": "",
            "carryover_guardrail_summary": _clean_text(session_family_posture.get("carryover_guardrail_summary")),
            "current_support_contested_flag": belief_state_contested_flag or contested_support,
            "current_posture_degraded_flag": belief_state_degraded_flag or degraded_posture,
            "historical_support_stronger_than_current_flag": belief_state_historical_stronger_flag or historical_stronger,
            "next_step_label": next_step_label,
            "next_step_summary": next_step_summary,
            "result_state_label": result_state_label,
            "result_state_summary": result_state_summary,
        }
    )


__all__ = ["build_scientific_decision_summary"]
