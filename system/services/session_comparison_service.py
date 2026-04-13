from __future__ import annotations

from typing import Any

from system.services.run_metadata_service import comparison_anchor_summary
from system.services.belief_update_service import support_role_from_belief_update_summary


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _humanize_token(value: Any, default: str = "Not recorded") -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return default
    return cleaned.replace("_", " ").strip().title()


def _normalized_target_key(value: Any) -> str:
    return _clean_text(value).lower()


def _as_bool(value: Any) -> bool:
    return bool(value)


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _join_compact(values: list[str], *, default: str = "Not recorded") -> str:
    cleaned = [_clean_text(value) for value in values if _clean_text(value)]
    if not cleaned:
        return default
    if len(cleaned) == 1:
        return cleaned[0]
    return ", ".join(cleaned[:3]) if len(cleaned) > 3 else ", ".join(cleaned)


def _scientific_truth(session: dict[str, Any]) -> dict[str, Any]:
    truth = session.get("scientific_session_truth") if isinstance(session.get("scientific_session_truth"), dict) else {}
    return truth


def _comparison_anchors(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    canonical = truth.get("comparison_anchors") if isinstance(truth.get("comparison_anchors"), dict) else {}
    if canonical:
        return canonical
    anchors = session.get("comparison_anchors") if isinstance(session.get("comparison_anchors"), dict) else {}
    return anchors


def _run_contract(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    contract = truth.get("run_contract") if isinstance(truth.get("run_contract"), dict) else {}
    return contract


def _evidence_loop(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    loop = truth.get("evidence_loop") if isinstance(truth.get("evidence_loop"), dict) else {}
    return loop


def _review_summary(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    summary = truth.get("review_summary") if isinstance(truth.get("review_summary"), dict) else {}
    return summary


def _claims_summary(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    summary = truth.get("claims_summary") if isinstance(truth.get("claims_summary"), dict) else {}
    return summary


def _claims_read_across_summary(session: dict[str, Any]) -> str:
    summary = _claims_summary(session)
    return _clean_text(summary.get("read_across_summary_text"))


def _evidence_activation_policy(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    policy = truth.get("evidence_activation_policy") if isinstance(truth.get("evidence_activation_policy"), dict) else {}
    return policy


def _bridge_state_notes(session: dict[str, Any]) -> list[str]:
    truth = _scientific_truth(session)
    return _clean_list(truth.get("bridge_state_notes"))


def _controlled_reuse(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    controlled_reuse = truth.get("controlled_reuse") if isinstance(truth.get("controlled_reuse"), dict) else {}
    if controlled_reuse:
        return controlled_reuse
    reuse = session.get("controlled_reuse") if isinstance(session.get("controlled_reuse"), dict) else {}
    return reuse


def _belief_state_summary(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    summary = truth.get("belief_state_summary") if isinstance(truth.get("belief_state_summary"), dict) else {}
    return summary


def _belief_update_summary(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    summary = truth.get("belief_update_summary") if isinstance(truth.get("belief_update_summary"), dict) else {}
    return summary


def _scientific_decision_summary(session: dict[str, Any]) -> dict[str, Any]:
    truth = _scientific_truth(session)
    summary = truth.get("scientific_decision_summary") if isinstance(truth.get("scientific_decision_summary"), dict) else {}
    if summary:
        return summary
    fallback = session.get("scientific_decision_summary") if isinstance(session.get("scientific_decision_summary"), dict) else {}
    return fallback


def _predictive_path_summary(session: dict[str, Any]) -> dict[str, Any]:
    summary = session.get("predictive_path_summary") if isinstance(session.get("predictive_path_summary"), dict) else {}
    return summary


def _predictive_evaluation_contract(session: dict[str, Any]) -> dict[str, Any]:
    summary = _predictive_path_summary(session)
    contract = summary.get("evaluation_contract") if isinstance(summary.get("evaluation_contract"), dict) else {}
    return contract


def _belief_state_alignment_label(session: dict[str, Any]) -> str:
    truth = _scientific_truth(session)
    return _clean_text(truth.get("belief_state_alignment_label") or session.get("belief_state_alignment_label"))


def _belief_state_alignment_summary(session: dict[str, Any]) -> str:
    truth = _scientific_truth(session)
    return _clean_text(truth.get("belief_state_alignment_summary") or session.get("belief_state_alignment_summary"))


def _basis_source_label(session: dict[str, Any]) -> str:
    explicit = _clean_text(session.get("scientific_truth_source_label"))
    if explicit:
        return explicit
    if _scientific_truth(session):
        return "Canonical scientific session truth"
    return "Compatibility reconstruction"


def _evidence_basis_label(session: dict[str, Any]) -> str:
    evidence_loop = _evidence_loop(session)
    modeling = _clean_list(evidence_loop.get("active_modeling_evidence"))
    ranking = _clean_list(evidence_loop.get("active_ranking_evidence"))
    parts: list[str] = []
    if modeling:
        parts.append(f"Modeling: {_join_compact(modeling)}")
    if ranking:
        parts.append(f"Ranking: {_join_compact(ranking)}")
    if not parts:
        return "Evidence basis not explicitly recorded."
    return " / ".join(parts)


def _activation_boundary_summary(session: dict[str, Any]) -> str:
    evidence_loop = _evidence_loop(session)
    summary = _clean_text(evidence_loop.get("activation_boundary_summary"))
    if summary:
        return summary
    interpretation = _clean_list(evidence_loop.get("interpretation_only_evidence"))
    memory = _clean_list(evidence_loop.get("memory_only_evidence"))
    stored = _clean_list(evidence_loop.get("stored_not_active_evidence"))
    future = _clean_list(evidence_loop.get("future_activation_candidates"))
    bits: list[str] = []
    if interpretation:
        bits.append(f"Interpretation-only: {_join_compact(interpretation)}")
    if memory:
        bits.append(f"Memory-only: {_join_compact(memory)}")
    if stored:
        bits.append(f"Stored not active: {_join_compact(stored)}")
    if future:
        bits.append(f"Future candidates: {_join_compact(future)}")
    return " / ".join(bits) if bits else "No explicit activation boundary recorded."


def _comparison_basis_label(session: dict[str, Any]) -> str:
    anchors = _comparison_anchors(session)
    return comparison_anchor_summary(anchors)


def _activation_policy_summary(session: dict[str, Any]) -> str:
    policy = _evidence_activation_policy(session)
    return _clean_text(policy.get("summary"), default="No explicit selective evidence-use policy recorded.")


def _interpretation_evidence_label(session: dict[str, Any]) -> str:
    policy = _evidence_activation_policy(session)
    summary = _clean_text(policy.get("interpretation_summary"))
    if summary:
        return summary
    evidence_loop = _evidence_loop(session)
    interpretation = _clean_list(evidence_loop.get("interpretation_only_evidence"))
    memory = _clean_list(evidence_loop.get("memory_only_evidence"))
    parts: list[str] = []
    if interpretation:
        parts.append(f"Interpretation: {_join_compact(interpretation)}")
    if memory:
        parts.append(f"Memory: {_join_compact(memory)}")
    return " / ".join(parts) if parts else "No explicit interpretation evidence recorded."


def _recommendation_reuse_summary(session: dict[str, Any]) -> str:
    policy = _evidence_activation_policy(session)
    return _clean_text(
        policy.get("recommendation_reuse_summary"),
        default="No evidence is currently marked as eligible for recommendation reuse.",
    )


def _future_ranking_context_summary(session: dict[str, Any]) -> str:
    policy = _evidence_activation_policy(session)
    return _clean_text(
        policy.get("future_ranking_context_summary"),
        default="No evidence is currently marked as eligible for future ranking-context reuse.",
    )


def _future_learning_eligibility_summary(session: dict[str, Any]) -> str:
    policy = _evidence_activation_policy(session)
    return _clean_text(
        policy.get("future_learning_eligibility_summary") or policy.get("learning_eligibility_summary"),
        default="No evidence is currently marked as eligible for future learning consideration.",
    )


def _permanently_non_active_summary(session: dict[str, Any]) -> str:
    policy = _evidence_activation_policy(session)
    return _clean_text(
        policy.get("permanently_non_active_summary"),
        default="No evidence is currently marked as permanently non-active.",
    )


def _controlled_reuse_summary(session: dict[str, Any]) -> str:
    reuse = _controlled_reuse(session)
    if not reuse:
        return "No controlled evidence reuse is recorded."
    parts = [
        _clean_text(reuse.get("recommendation_reuse_summary")),
        _clean_text(reuse.get("ranking_context_reuse_summary")),
        _clean_text(reuse.get("interpretation_support_summary")),
    ]
    summary = " ".join(part for part in parts if part)
    return summary or "No controlled evidence reuse is recorded."


def _belief_state_strength_summary(session: dict[str, Any]) -> str:
    summary = _belief_state_summary(session)
    return _clean_text(summary.get("belief_state_strength_summary"))


def _belief_state_readiness_summary(session: dict[str, Any]) -> str:
    summary = _belief_state_summary(session)
    return _clean_text(summary.get("belief_state_readiness_summary"))


def _belief_state_support_quality_label(session: dict[str, Any]) -> str:
    summary = _belief_state_summary(session)
    return _clean_text(summary.get("support_quality_label"))


def _belief_state_support_quality_summary(session: dict[str, Any]) -> str:
    summary = _belief_state_summary(session)
    return _clean_text(summary.get("support_quality_summary"))


def _belief_state_governed_support_posture_label(session: dict[str, Any]) -> str:
    summary = _belief_state_summary(session)
    return _clean_text(summary.get("governed_support_posture_label"))


def _belief_state_governed_support_posture_summary(session: dict[str, Any]) -> str:
    summary = _belief_state_summary(session)
    return _clean_text(summary.get("governed_support_posture_summary"))


def _belief_state_governance_label(session: dict[str, Any]) -> str:
    summary = _belief_state_summary(session)
    return _clean_text(summary.get("governance_mix_label"), default="Not recorded")


def _session_support_role(session: dict[str, Any]) -> tuple[str, str]:
    return support_role_from_belief_update_summary(_belief_update_summary(session))


def _belief_update_support_quality_label(session: dict[str, Any]) -> str:
    summary = _belief_update_summary(session)
    return _clean_text(summary.get("support_quality_label"))


def _belief_update_support_quality_summary(session: dict[str, Any]) -> str:
    summary = _belief_update_summary(session)
    return _clean_text(summary.get("support_quality_summary"))


def _belief_update_governed_support_posture_label(session: dict[str, Any]) -> str:
    summary = _belief_update_summary(session)
    return _clean_text(summary.get("governed_support_posture_label"))


def _belief_update_governed_support_posture_summary(session: dict[str, Any]) -> str:
    summary = _belief_update_summary(session)
    return _clean_text(summary.get("governed_support_posture_summary"))


def _comparison_rank(status: str) -> int:
    cleaned = _clean_text(status)
    if cleaned == "directly_comparable":
        return 0
    if cleaned == "partially_comparable":
        return 1
    return 2


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _candidate_key(row: dict[str, Any], fallback_index: int) -> str:
    canonical_smiles = _clean_text(row.get("canonical_smiles"))
    if canonical_smiles:
        return f"smiles::{canonical_smiles}"
    smiles = _clean_text(row.get("smiles"))
    if smiles:
        return f"smiles::{smiles}"
    candidate_id = _clean_text(row.get("candidate_id") or row.get("molecule_id") or row.get("polymer"))
    if candidate_id:
        return f"id::{candidate_id}"
    return f"rank::{fallback_index}"


def _candidate_label(row: dict[str, Any]) -> str:
    identifier = _clean_text(row.get("candidate_id") or row.get("molecule_id") or row.get("polymer"))
    smiles = _clean_text(row.get("canonical_smiles") or row.get("smiles"))
    if identifier and smiles and identifier != smiles:
        return f"{identifier} ({smiles})"
    return identifier or smiles or "candidate"


def build_candidate_preview(decision_payload: dict[str, Any] | None, *, limit: int = 5) -> list[dict[str, Any]]:
    decision_payload = decision_payload if isinstance(decision_payload, dict) else {}
    rows = decision_payload.get("top_experiments") if isinstance(decision_payload.get("top_experiments"), list) else []
    preview: list[dict[str, Any]] = []

    for index, row in enumerate(rows[:limit], start=1):
        if not isinstance(row, dict):
            continue
        rationale = row.get("rationale") if isinstance(row.get("rationale"), dict) else {}
        preview.append(
            {
                "key": _candidate_key(row, index),
                "rank_position": index,
                "candidate_id": _clean_text(row.get("candidate_id") or row.get("molecule_id") or row.get("polymer")),
                "label": _candidate_label(row),
                "smiles": _clean_text(row.get("smiles")),
                "canonical_smiles": _clean_text(row.get("canonical_smiles") or row.get("smiles")),
                "bucket": _clean_text(row.get("bucket") or row.get("selection_bucket"), default="unassigned").lower(),
                "trust_label": _clean_text(rationale.get("trust_label") or row.get("trust_label"), default="not_recorded").lower(),
                "priority_score": _safe_float(row.get("priority_score"), default=None),
                "experiment_value": _safe_float(row.get("experiment_value"), default=None),
                "signal_status_label": _clean_text(
                    ((row.get("score_semantics") or {}) if isinstance(row.get("score_semantics"), dict) else {}).get("signal_status_label")
                ),
                "bounded_uncertainty_score": _safe_float(
                    ((row.get("score_semantics") or {}) if isinstance(row.get("score_semantics"), dict) else {}).get("bounded_uncertainty_score"),
                    default=None,
                ),
                "neighbor_gap": _safe_float(
                    ((row.get("score_semantics") or {}) if isinstance(row.get("score_semantics"), dict) else {}).get("neighbor_gap"),
                    default=None,
                ),
            }
        )
    return preview


def _compare_candidate_previews(
    focus_preview: list[dict[str, Any]] | None,
    candidate_preview: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    focus_preview = focus_preview if isinstance(focus_preview, list) else []
    candidate_preview = candidate_preview if isinstance(candidate_preview, list) else []

    if not focus_preview and not candidate_preview:
        return {"summary": "", "differences": []}
    if focus_preview and not candidate_preview:
        return {
            "summary": "The focus shortlist preview is available, but the comparison shortlist preview is not.",
            "differences": [],
        }
    if candidate_preview and not focus_preview:
        return {
            "summary": "The comparison shortlist preview is available, but the focus shortlist preview is not.",
            "differences": [],
        }

    focus_by_key = {
        _clean_text(item.get("key")): item
        for item in focus_preview
        if isinstance(item, dict) and _clean_text(item.get("key"))
    }
    candidate_by_key = {
        _clean_text(item.get("key")): item
        for item in candidate_preview
        if isinstance(item, dict) and _clean_text(item.get("key"))
    }
    focus_order = [item["key"] for item in focus_preview if isinstance(item, dict) and _clean_text(item.get("key"))]
    candidate_order = [
        item["key"] for item in candidate_preview if isinstance(item, dict) and _clean_text(item.get("key"))
    ]
    shared_keys = [key for key in focus_order if key in candidate_by_key]
    focus_only = [focus_by_key[key] for key in focus_order if key not in candidate_by_key]
    candidate_only = [candidate_by_key[key] for key in candidate_order if key not in focus_by_key]

    window = min(len(focus_preview), len(candidate_preview))
    if shared_keys:
        summary = (
            f"{len(shared_keys)} of the top {window} leading candidates are shared across the compared shortlist previews."
        )
    else:
        summary = "No leading candidates are shared across the compared shortlist previews."

    differences: list[str] = []
    focus_lead = focus_preview[0] if focus_preview else {}
    candidate_lead = candidate_preview[0] if candidate_preview else {}
    if focus_lead and candidate_lead and _clean_text(focus_lead.get("key")) != _clean_text(candidate_lead.get("key")):
        differences.append(
            f"Lead candidate changed: {focus_lead.get('label') or 'focus lead'} vs {candidate_lead.get('label') or 'comparison lead'}."
        )

    if candidate_only:
        labels = ", ".join(str(item.get("label") or "candidate") for item in candidate_only[:2])
        differences.append(f"New in the comparison shortlist: {labels}.")

    if focus_only:
        labels = ", ".join(str(item.get("label") or "candidate") for item in focus_only[:2])
        differences.append(f"Not carried over from the focus shortlist: {labels}.")

    shared_shift_lines: list[str] = []
    for key in shared_keys:
        focus_item = focus_by_key.get(key) or {}
        candidate_item = candidate_by_key.get(key) or {}
        label = str(focus_item.get("label") or candidate_item.get("label") or "candidate")
        focus_bucket = _clean_text(focus_item.get("bucket"))
        candidate_bucket = _clean_text(candidate_item.get("bucket"))
        if focus_bucket and candidate_bucket and focus_bucket != candidate_bucket:
            shared_shift_lines.append(
                f"Shared candidate bucket changed for {label}: {_humanize_token(focus_bucket)} vs {_humanize_token(candidate_bucket)}."
            )
            continue
        focus_trust = _clean_text(focus_item.get("trust_label"))
        candidate_trust = _clean_text(candidate_item.get("trust_label"))
        if focus_trust and candidate_trust and focus_trust != candidate_trust:
            shared_shift_lines.append(
                f"Shared candidate trust changed for {label}: {_humanize_token(focus_trust)} vs {_humanize_token(candidate_trust)}."
            )
            continue
        focus_rank = focus_item.get("rank_position")
        candidate_rank = candidate_item.get("rank_position")
        try:
            focus_rank = int(focus_rank)
            candidate_rank = int(candidate_rank)
        except (TypeError, ValueError):
            focus_rank = candidate_rank = None
        if focus_rank is not None and candidate_rank is not None and abs(candidate_rank - focus_rank) >= 2:
            shared_shift_lines.append(
                f"Shared candidate rank shifted for {label}: {focus_rank} to {candidate_rank}."
            )
        focus_signal_status = _clean_text(focus_item.get("signal_status_label"))
        candidate_signal_status = _clean_text(candidate_item.get("signal_status_label"))
        if focus_signal_status and candidate_signal_status and focus_signal_status != candidate_signal_status:
            shared_shift_lines.append(
                f"Shared candidate signal status changed for {label}: {focus_signal_status.lower()} vs {candidate_signal_status.lower()}."
            )
            continue
        if len(shared_shift_lines) >= 2:
            break

    differences.extend(shared_shift_lines[:2])
    return {
        "summary": summary,
        "differences": differences[:5],
    }


def compare_session_basis(
    *,
    focus_session: dict[str, Any] | None,
    candidate_session: dict[str, Any] | None,
) -> dict[str, Any]:
    focus_session = focus_session if isinstance(focus_session, dict) else {}
    candidate_session = candidate_session if isinstance(candidate_session, dict) else {}
    focus_anchors = _comparison_anchors(focus_session)
    candidate_anchors = _comparison_anchors(candidate_session)
    focus_status = (
        focus_session.get("status_semantics") if isinstance(focus_session.get("status_semantics"), dict) else {}
    )
    candidate_status = (
        candidate_session.get("status_semantics")
        if isinstance(candidate_session.get("status_semantics"), dict)
        else {}
    )
    focus_outcome = (
        focus_session.get("outcome_profile") if isinstance(focus_session.get("outcome_profile"), dict) else {}
    )
    candidate_outcome = (
        candidate_session.get("outcome_profile") if isinstance(candidate_session.get("outcome_profile"), dict) else {}
    )
    focus_candidate_preview = (
        focus_session.get("candidate_preview") if isinstance(focus_session.get("candidate_preview"), list) else []
    )
    candidate_candidate_preview = (
        candidate_session.get("candidate_preview")
        if isinstance(candidate_session.get("candidate_preview"), list)
        else []
    )
    focus_evidence_loop = _evidence_loop(focus_session)
    candidate_evidence_loop = _evidence_loop(candidate_session)
    focus_activation_policy = _evidence_activation_policy(focus_session)
    candidate_activation_policy = _evidence_activation_policy(candidate_session)
    focus_review_summary = _review_summary(focus_session)
    candidate_review_summary = _review_summary(candidate_session)
    focus_bridge_state = _bridge_state_notes(focus_session)
    candidate_bridge_state = _bridge_state_notes(candidate_session)
    focus_controlled_reuse = _controlled_reuse(focus_session)
    candidate_controlled_reuse = _controlled_reuse(candidate_session)
    focus_claims = _claims_summary(focus_session)
    candidate_claims = _claims_summary(candidate_session)
    focus_belief_state = _belief_state_summary(focus_session)
    candidate_belief_state = _belief_state_summary(candidate_session)
    focus_decision_summary = _scientific_decision_summary(focus_session)
    candidate_decision_summary = _scientific_decision_summary(candidate_session)
    focus_support_role_label, focus_support_role_summary = _session_support_role(focus_session)
    candidate_support_role_label, candidate_support_role_summary = _session_support_role(candidate_session)
    focus_belief_alignment_label = _belief_state_alignment_label(focus_session)
    candidate_belief_alignment_label = _belief_state_alignment_label(candidate_session)
    focus_belief_alignment_summary = _belief_state_alignment_summary(focus_session)
    candidate_belief_alignment_summary = _belief_state_alignment_summary(candidate_session)
    focus_predictive_evaluation = _predictive_evaluation_contract(focus_session)
    candidate_predictive_evaluation = _predictive_evaluation_contract(candidate_session)

    matches: list[str] = []
    differences: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []
    outcome_differences: list[str] = []

    focus_target_name = _clean_text(focus_anchors.get("target_name"))
    candidate_target_name = _clean_text(candidate_anchors.get("target_name"))
    focus_target_kind = _clean_text(focus_anchors.get("target_kind"))
    candidate_target_kind = _clean_text(candidate_anchors.get("target_kind"))
    focus_direction = _clean_text(focus_anchors.get("optimization_direction"))
    candidate_direction = _clean_text(candidate_anchors.get("optimization_direction"))
    focus_mode = _clean_text(focus_anchors.get("modeling_mode"))
    candidate_mode = _clean_text(candidate_anchors.get("modeling_mode"))
    focus_intent = _clean_text(focus_anchors.get("decision_intent"))
    candidate_intent = _clean_text(candidate_anchors.get("decision_intent"))
    focus_policy = _clean_text(focus_anchors.get("scoring_policy_version"))
    candidate_policy = _clean_text(candidate_anchors.get("scoring_policy_version"))
    focus_model = _clean_text(focus_anchors.get("selected_model_name"))
    candidate_model = _clean_text(candidate_anchors.get("selected_model_name"))
    focus_scope = _clean_text(focus_anchors.get("training_scope"))
    candidate_scope = _clean_text(candidate_anchors.get("training_scope"))
    focus_measurement = _clean_text(focus_anchors.get("measurement_column"))
    candidate_measurement = _clean_text(candidate_anchors.get("measurement_column"))
    focus_label = _clean_text(focus_anchors.get("label_column"))
    candidate_label = _clean_text(candidate_anchors.get("label_column"))
    focus_dataset_type = _clean_text(focus_anchors.get("dataset_type"))
    candidate_dataset_type = _clean_text(candidate_anchors.get("dataset_type"))

    if focus_target_name and candidate_target_name and _normalized_target_key(focus_target_name) == _normalized_target_key(candidate_target_name):
        matches.append(f"Same target property: {focus_target_name}.")
    else:
        blockers.append(
            f"Target property differs: {focus_target_name or 'not recorded'} vs {candidate_target_name or 'not recorded'}."
        )

    if focus_target_kind and candidate_target_kind and focus_target_kind == candidate_target_kind:
        matches.append(f"Same target kind: {_humanize_token(focus_target_kind)}.")
    else:
        blockers.append(
            f"Target kind differs: {_humanize_token(focus_target_kind)} vs {_humanize_token(candidate_target_kind)}."
        )

    if focus_direction and candidate_direction and focus_direction == candidate_direction:
        matches.append(f"Same optimization goal: {_humanize_token(focus_direction)}.")
    elif focus_direction or candidate_direction:
        differences.append(
            f"Optimization goal differs: {_humanize_token(focus_direction)} vs {_humanize_token(candidate_direction)}."
        )

    if focus_mode and candidate_mode and focus_mode == candidate_mode:
        matches.append(f"Same modeling mode: {_humanize_token(focus_mode)}.")
    else:
        blockers.append(
            f"Modeling mode differs: {_humanize_token(focus_mode)} vs {_humanize_token(candidate_mode)}."
        )

    if focus_intent and candidate_intent and focus_intent == candidate_intent:
        matches.append(f"Same decision intent: {_humanize_token(focus_intent)}.")
    elif focus_intent or candidate_intent:
        differences.append(
            f"Decision intent differs: {_humanize_token(focus_intent)} vs {_humanize_token(candidate_intent)}."
        )

    if focus_policy and candidate_policy and focus_policy == candidate_policy:
        matches.append(f"Same scoring-policy version: {focus_policy}.")
    elif focus_policy or candidate_policy:
        differences.append(
            f"Scoring-policy version differs: {focus_policy or 'not recorded'} vs {candidate_policy or 'not recorded'}."
        )

    if focus_model and candidate_model and focus_model != candidate_model:
        differences.append(f"Model provenance differs: {focus_model} vs {candidate_model}.")
    elif focus_model and candidate_model:
        matches.append(f"Same recorded model name: {focus_model}.")

    if focus_scope and candidate_scope and focus_scope != candidate_scope:
        differences.append(
            f"Training scope differs: {_humanize_token(focus_scope)} vs {_humanize_token(candidate_scope)}."
        )
    elif focus_scope and candidate_scope:
        matches.append(f"Same training scope: {_humanize_token(focus_scope)}.")

    if focus_dataset_type and candidate_dataset_type and focus_dataset_type != candidate_dataset_type:
        differences.append(
            f"Dataset type differs: {_humanize_token(focus_dataset_type)} vs {_humanize_token(candidate_dataset_type)}."
        )

    focus_active_modeling = _clean_list(focus_evidence_loop.get("active_modeling_evidence"))
    candidate_active_modeling = _clean_list(candidate_evidence_loop.get("active_modeling_evidence"))
    if focus_active_modeling or candidate_active_modeling:
        if focus_active_modeling == candidate_active_modeling:
            if focus_active_modeling:
                matches.append(f"Same active modeling evidence: {_join_compact(focus_active_modeling)}.")
        else:
            differences.append(
                "Active modeling evidence differs: "
                f"{_join_compact(focus_active_modeling)} vs {_join_compact(candidate_active_modeling)}."
            )

    focus_active_ranking = _clean_list(focus_evidence_loop.get("active_ranking_evidence"))
    candidate_active_ranking = _clean_list(candidate_evidence_loop.get("active_ranking_evidence"))
    if focus_active_ranking or candidate_active_ranking:
        if focus_active_ranking == candidate_active_ranking:
            if focus_active_ranking:
                matches.append(f"Same active ranking context: {_join_compact(focus_active_ranking)}.")
        else:
            differences.append(
                "Active ranking context differs: "
                f"{_join_compact(focus_active_ranking)} vs {_join_compact(candidate_active_ranking)}."
            )

    focus_future_activation = _clean_list(focus_evidence_loop.get("future_activation_candidates"))
    candidate_future_activation = _clean_list(candidate_evidence_loop.get("future_activation_candidates"))
    if focus_future_activation or candidate_future_activation:
        if focus_future_activation != candidate_future_activation:
            cautions.append(
                "Future activation boundary differs: "
                f"{_join_compact(focus_future_activation)} vs {_join_compact(candidate_future_activation)}."
            )

    focus_interpretation_summary = _clean_text(focus_activation_policy.get("interpretation_summary"))
    candidate_interpretation_summary = _clean_text(candidate_activation_policy.get("interpretation_summary"))
    if focus_interpretation_summary or candidate_interpretation_summary:
        if focus_interpretation_summary != candidate_interpretation_summary:
            differences.append(
                "Selective interpretation use differs: "
                f"{focus_interpretation_summary or 'not recorded'} vs {candidate_interpretation_summary or 'not recorded'}."
            )

    focus_reuse_summary = _clean_text(focus_activation_policy.get("recommendation_reuse_summary"))
    candidate_reuse_summary = _clean_text(candidate_activation_policy.get("recommendation_reuse_summary"))
    if focus_reuse_summary or candidate_reuse_summary:
        if focus_reuse_summary != candidate_reuse_summary:
            cautions.append(
                "Recommendation-reuse eligibility differs: "
                f"{focus_reuse_summary or 'not recorded'} vs {candidate_reuse_summary or 'not recorded'}."
            )

    focus_reuse_active = _as_bool(focus_controlled_reuse.get("recommendation_reuse_active"))
    candidate_reuse_active = _as_bool(candidate_controlled_reuse.get("recommendation_reuse_active"))
    if focus_reuse_active != candidate_reuse_active:
        cautions.append(
            "Active recommendation reuse differs: "
            f"{'active' if focus_reuse_active else 'inactive'} vs {'active' if candidate_reuse_active else 'inactive'}."
        )

    focus_ranking_reuse_active = _as_bool(focus_controlled_reuse.get("ranking_context_reuse_active"))
    candidate_ranking_reuse_active = _as_bool(candidate_controlled_reuse.get("ranking_context_reuse_active"))
    if focus_ranking_reuse_active != candidate_ranking_reuse_active:
        cautions.append(
            "Active ranking-context reuse differs: "
            f"{'active' if focus_ranking_reuse_active else 'inactive'} vs {'active' if candidate_ranking_reuse_active else 'inactive'}."
        )

    focus_interpretation_support_active = _as_bool(focus_controlled_reuse.get("interpretation_support_active"))
    candidate_interpretation_support_active = _as_bool(candidate_controlled_reuse.get("interpretation_support_active"))
    if focus_interpretation_support_active != candidate_interpretation_support_active:
        differences.append(
            "Active interpretation support differs: "
            f"{'active' if focus_interpretation_support_active else 'inactive'} vs {'active' if candidate_interpretation_support_active else 'inactive'}."
        )

    focus_future_learning_summary = _clean_text(
        focus_activation_policy.get("future_learning_eligibility_summary")
        or focus_activation_policy.get("learning_eligibility_summary")
    )
    candidate_future_learning_summary = _clean_text(
        candidate_activation_policy.get("future_learning_eligibility_summary")
        or candidate_activation_policy.get("learning_eligibility_summary")
    )
    if focus_future_learning_summary or candidate_future_learning_summary:
        if focus_future_learning_summary != candidate_future_learning_summary:
            cautions.append(
                "Future-learning eligibility differs: "
                f"{focus_future_learning_summary or 'not recorded'} vs {candidate_future_learning_summary or 'not recorded'}."
            )

    if focus_measurement or candidate_measurement:
        if focus_measurement == candidate_measurement:
            if focus_measurement:
                matches.append(f"Same measurement column: {focus_measurement}.")
        else:
            differences.append(
                f"Measurement column differs: {focus_measurement or 'not recorded'} vs {candidate_measurement or 'not recorded'}."
            )

    if focus_label or candidate_label:
        if focus_label == candidate_label:
            if focus_label:
                matches.append(f"Same label column: {focus_label}.")
        else:
            differences.append(
                f"Label column differs: {focus_label or 'not recorded'} vs {candidate_label or 'not recorded'}."
            )

    focus_ready = _as_bool(focus_anchors.get("comparison_ready"))
    candidate_ready = _as_bool(candidate_anchors.get("comparison_ready"))
    if not focus_ready:
        cautions.append("The focus session is not fully comparison-ready.")
    if not candidate_ready:
        cautions.append("The comparison session is not fully comparison-ready.")

    focus_fallback = _clean_text(focus_anchors.get("fallback_reason"))
    candidate_fallback = _clean_text(candidate_anchors.get("fallback_reason"))
    if focus_fallback:
        cautions.append(f"Focus fallback recorded: {focus_fallback.replace('_', ' ')}.")
    if candidate_fallback:
        cautions.append(f"Comparison fallback recorded: {candidate_fallback.replace('_', ' ')}.")
    if focus_bridge_state or candidate_bridge_state:
        if focus_bridge_state != candidate_bridge_state:
            cautions.append(
                "Bridge-state behavior differs: "
                f"{_join_compact(focus_bridge_state)} vs {_join_compact(candidate_bridge_state)}."
            )
        else:
            cautions.append(f"Both sessions share the same bridge-state note: {_join_compact(focus_bridge_state)}.")

    if "trustworthy_recommendations" in candidate_status and not _as_bool(candidate_status.get("trustworthy_recommendations")):
        cautions.append("The comparison session does not currently have fully trustworthy recommendation artifacts.")
    if "viewable_artifacts" in candidate_status and not _as_bool(candidate_status.get("viewable_artifacts")):
        cautions.append("Saved artifacts are not fully viewable for the comparison session.")

    if focus_review_summary or candidate_review_summary:
        focus_review_total = sum(
            int(value or 0)
            for value in ((focus_review_summary.get("counts") if isinstance(focus_review_summary.get("counts"), dict) else {}).values())
        )
        candidate_review_total = sum(
            int(value or 0)
            for value in ((candidate_review_summary.get("counts") if isinstance(candidate_review_summary.get("counts"), dict) else {}).values())
        )
        if focus_review_total != candidate_review_total:
            differences.append(
                f"Recorded review state differs: {focus_review_total} saved review outcome(s) vs {candidate_review_total}."
            )

    focus_active_claims = int(focus_belief_state.get("active_claim_count") or 0)
    candidate_active_claims = int(candidate_belief_state.get("active_claim_count") or 0)
    focus_accepted_updates = int(focus_belief_state.get("accepted_update_count") or 0)
    candidate_accepted_updates = int(candidate_belief_state.get("accepted_update_count") or 0)
    focus_proposed_updates = int(focus_belief_state.get("proposed_update_count") or 0)
    candidate_proposed_updates = int(candidate_belief_state.get("proposed_update_count") or 0)
    focus_superseded_updates = int(focus_belief_state.get("superseded_update_count") or 0)
    candidate_superseded_updates = int(candidate_belief_state.get("superseded_update_count") or 0)
    if focus_active_claims or candidate_active_claims:
        if focus_active_claims != candidate_active_claims:
            cautions.append(
                f"Tracked belief-state coverage differs: {focus_active_claims} active claim(s) vs {candidate_active_claims}."
            )
        if focus_accepted_updates != candidate_accepted_updates or focus_proposed_updates != candidate_proposed_updates:
            cautions.append(
                "Belief-state governance differs: "
                f"{focus_accepted_updates} accepted / {focus_proposed_updates} proposed vs "
                f"{candidate_accepted_updates} accepted / {candidate_proposed_updates} proposed."
            )
        if focus_superseded_updates != candidate_superseded_updates:
            cautions.append(
                "Belief-state chronology differs: "
                f"{focus_superseded_updates} superseded support change(s) vs {candidate_superseded_updates}."
            )
        focus_belief_state_basis_label = _clean_text(focus_belief_state.get("support_basis_mix_label"))
        candidate_belief_state_basis_label = _clean_text(candidate_belief_state.get("support_basis_mix_label"))
        if focus_belief_state_basis_label != candidate_belief_state_basis_label:
            cautions.append(
                "Belief-state support basis differs: "
                f"{(focus_belief_state_basis_label or 'not recorded').lower()} vs {(candidate_belief_state_basis_label or 'not recorded').lower()}."
            )

    focus_belief_updates = _belief_update_summary(focus_session)
    candidate_belief_updates = _belief_update_summary(candidate_session)
    focus_active_updates = int(focus_belief_updates.get("active_count") or 0)
    candidate_active_updates = int(candidate_belief_updates.get("active_count") or 0)
    focus_historical_updates = int(focus_belief_updates.get("historical_count") or 0)
    candidate_historical_updates = int(candidate_belief_updates.get("historical_count") or 0)
    if focus_active_updates != candidate_active_updates:
        cautions.append(
            f"Current support-change coverage differs: {focus_active_updates} active belief update(s) vs {candidate_active_updates}."
        )
    if focus_historical_updates != candidate_historical_updates:
        differences.append(
            f"Historical support-change depth differs: {focus_historical_updates} historical record(s) vs {candidate_historical_updates}."
        )
    focus_update_basis_label = _clean_text(focus_belief_updates.get("support_basis_mix_label"))
    candidate_update_basis_label = _clean_text(candidate_belief_updates.get("support_basis_mix_label"))
    if focus_update_basis_label != candidate_update_basis_label:
        cautions.append(
            "Session support basis differs: "
            f"{(focus_update_basis_label or 'not recorded').lower()} vs {(candidate_update_basis_label or 'not recorded').lower()}."
        )
    focus_update_support_quality_label = _clean_text(focus_belief_updates.get("support_quality_label"))
    candidate_update_support_quality_label = _clean_text(candidate_belief_updates.get("support_quality_label"))
    if focus_update_support_quality_label != candidate_update_support_quality_label:
        cautions.append(
            "Current support quality differs: "
            f"{(focus_update_support_quality_label or 'not recorded').lower()} vs {(candidate_update_support_quality_label or 'not recorded').lower()}."
        )
    focus_update_governed_posture_label = _clean_text(focus_belief_updates.get("governed_support_posture_label"))
    candidate_update_governed_posture_label = _clean_text(candidate_belief_updates.get("governed_support_posture_label"))
    if focus_update_governed_posture_label != candidate_update_governed_posture_label:
        differences.append(
            "Governed support posture differs: "
            f"{(focus_update_governed_posture_label or 'not recorded').lower()} vs {(candidate_update_governed_posture_label or 'not recorded').lower()}."
        )
    focus_update_support_coherence_label = _clean_text(focus_belief_updates.get("support_coherence_label"))
    candidate_update_support_coherence_label = _clean_text(candidate_belief_updates.get("support_coherence_label"))
    if focus_update_support_coherence_label != candidate_update_support_coherence_label:
        cautions.append(
            "Support coherence differs: "
            f"{(focus_update_support_coherence_label or 'not recorded').lower()} vs {(candidate_update_support_coherence_label or 'not recorded').lower()}."
        )
    focus_update_support_reuse_label = _clean_text(focus_belief_updates.get("support_reuse_label"))
    candidate_update_support_reuse_label = _clean_text(candidate_belief_updates.get("support_reuse_label"))
    if focus_update_support_reuse_label != candidate_update_support_reuse_label:
        cautions.append(
            "Support reuse differs: "
            f"{(focus_update_support_reuse_label or 'not recorded').lower()} vs {(candidate_update_support_reuse_label or 'not recorded').lower()}."
        )
    focus_claims_active_support = int(focus_claims.get("claims_with_active_support_count") or 0)
    candidate_claims_active_support = int(candidate_claims.get("claims_with_active_support_count") or 0)
    focus_claims_historical_only = int(focus_claims.get("claims_with_historical_support_only_count") or 0)
    candidate_claims_historical_only = int(candidate_claims.get("claims_with_historical_support_only_count") or 0)
    focus_claims_no_governed_support = int(focus_claims.get("claims_with_no_governed_support_count") or 0)
    candidate_claims_no_governed_support = int(candidate_claims.get("claims_with_no_governed_support_count") or 0)
    focus_claims_continuity_aligned = int(focus_claims.get("continuity_aligned_claim_count") or 0)
    candidate_claims_continuity_aligned = int(candidate_claims.get("continuity_aligned_claim_count") or 0)
    focus_claims_new_context = int(focus_claims.get("new_claim_context_count") or 0)
    candidate_claims_new_context = int(candidate_claims.get("new_claim_context_count") or 0)
    focus_claims_weak_alignment = int(focus_claims.get("weak_prior_alignment_count") or 0)
    candidate_claims_weak_alignment = int(candidate_claims.get("weak_prior_alignment_count") or 0)
    focus_claims_no_prior_context = int(focus_claims.get("no_prior_claim_context_count") or 0)
    candidate_claims_no_prior_context = int(candidate_claims.get("no_prior_claim_context_count") or 0)
    focus_claims_active_governed_continuity = int(focus_claims.get("claims_with_active_governed_continuity_count") or 0)
    candidate_claims_active_governed_continuity = int(
        candidate_claims.get("claims_with_active_governed_continuity_count") or 0
    )
    focus_claims_tentative_active_continuity = int(
        focus_claims.get("claims_with_tentative_active_continuity_count") or 0
    )
    candidate_claims_tentative_active_continuity = int(
        candidate_claims.get("claims_with_tentative_active_continuity_count") or 0
    )
    focus_claims_historical_continuity_only = int(
        focus_claims.get("claims_with_historical_continuity_only_count") or 0
    )
    candidate_claims_historical_continuity_only = int(
        candidate_claims.get("claims_with_historical_continuity_only_count") or 0
    )
    focus_claims_sparse_prior_context = int(focus_claims.get("claims_with_sparse_prior_context_count") or 0)
    candidate_claims_sparse_prior_context = int(candidate_claims.get("claims_with_sparse_prior_context_count") or 0)
    focus_claims_no_useful_prior_context = int(
        focus_claims.get("claims_with_no_useful_prior_context_count") or 0
    )
    candidate_claims_no_useful_prior_context = int(
        candidate_claims.get("claims_with_no_useful_prior_context_count") or 0
    )
    focus_claims_observed_grounded = int(focus_claims.get("claims_mostly_observed_label_grounded_count") or 0)
    candidate_claims_observed_grounded = int(candidate_claims.get("claims_mostly_observed_label_grounded_count") or 0)
    focus_claims_numeric_grounded = int(focus_claims.get("claims_with_numeric_rule_based_support_count") or 0)
    candidate_claims_numeric_grounded = int(candidate_claims.get("claims_with_numeric_rule_based_support_count") or 0)
    focus_claims_weak_basis = int(focus_claims.get("claims_with_weak_basis_support_count") or 0)
    candidate_claims_weak_basis = int(candidate_claims.get("claims_with_weak_basis_support_count") or 0)
    focus_claims_mixed_basis = int(focus_claims.get("claims_with_mixed_support_basis_count") or 0)
    candidate_claims_mixed_basis = int(candidate_claims.get("claims_with_mixed_support_basis_count") or 0)
    focus_claims_posture_governing = int(focus_claims.get("claims_with_posture_governing_support_count") or 0)
    candidate_claims_posture_governing = int(candidate_claims.get("claims_with_posture_governing_support_count") or 0)
    focus_claims_tentative_support = int(focus_claims.get("claims_with_tentative_current_support_count") or 0)
    candidate_claims_tentative_support = int(candidate_claims.get("claims_with_tentative_current_support_count") or 0)
    focus_claims_accepted_limited_support = int(focus_claims.get("claims_with_accepted_limited_support_count") or 0)
    candidate_claims_accepted_limited_support = int(candidate_claims.get("claims_with_accepted_limited_support_count") or 0)
    focus_claims_contested_support = int(focus_claims.get("claims_with_contested_current_support_count") or 0)
    candidate_claims_contested_support = int(candidate_claims.get("claims_with_contested_current_support_count") or 0)
    focus_claims_degraded_support = int(focus_claims.get("claims_with_degraded_current_posture_count") or 0)
    candidate_claims_degraded_support = int(candidate_claims.get("claims_with_degraded_current_posture_count") or 0)
    focus_claims_historical_stronger = int(focus_claims.get("claims_with_historical_stronger_than_current_count") or 0)
    candidate_claims_historical_stronger = int(candidate_claims.get("claims_with_historical_stronger_than_current_count") or 0)
    focus_claims_contradiction_limited_reuse = int(
        focus_claims.get("claims_with_contradiction_limited_reuse_count") or 0
    )
    candidate_claims_contradiction_limited_reuse = int(
        candidate_claims.get("claims_with_contradiction_limited_reuse_count") or 0
    )
    focus_claims_action_ready = int(focus_claims.get("claims_action_ready_follow_up_count") or 0)
    candidate_claims_action_ready = int(candidate_claims.get("claims_action_ready_follow_up_count") or 0)
    focus_claims_need_stronger_evidence = int(
        focus_claims.get("claims_promising_but_need_stronger_evidence_count") or 0
    )
    candidate_claims_need_stronger_evidence = int(
        candidate_claims.get("claims_promising_but_need_stronger_evidence_count") or 0
    )
    focus_claims_need_clarifying_experiment = int(
        focus_claims.get("claims_need_clarifying_experiment_count") or 0
    )
    candidate_claims_need_clarifying_experiment = int(
        candidate_claims.get("claims_need_clarifying_experiment_count") or 0
    )
    focus_claims_do_not_prioritize = int(focus_claims.get("claims_do_not_prioritize_yet_count") or 0)
    candidate_claims_do_not_prioritize = int(candidate_claims.get("claims_do_not_prioritize_yet_count") or 0)
    focus_claims_insufficient_basis = int(focus_claims.get("claims_with_insufficient_governed_basis_count") or 0)
    candidate_claims_insufficient_basis = int(
        candidate_claims.get("claims_with_insufficient_governed_basis_count") or 0
    )
    focus_claims_action_ready_from_active = int(
        focus_claims.get("claims_action_ready_from_active_support_count") or 0
    )
    candidate_claims_action_ready_from_active = int(
        candidate_claims.get("claims_action_ready_from_active_support_count") or 0
    )
    focus_claims_active_limited = int(
        focus_claims.get("claims_with_active_but_limited_actionability_count") or 0
    )
    candidate_claims_active_limited = int(
        candidate_claims.get("claims_with_active_but_limited_actionability_count") or 0
    )
    focus_claims_historically_interesting = int(
        focus_claims.get("claims_historically_interesting_count") or 0
    )
    candidate_claims_historically_interesting = int(
        candidate_claims.get("claims_historically_interesting_count") or 0
    )
    focus_claims_mixed_current_historical = int(
        focus_claims.get("claims_with_mixed_current_historical_actionability_count") or 0
    )
    candidate_claims_mixed_current_historical = int(
        candidate_claims.get("claims_with_mixed_current_historical_actionability_count") or 0
    )
    focus_claims_no_active_actionability = int(
        focus_claims.get("claims_with_no_active_governed_support_actionability_count") or 0
    )
    candidate_claims_no_active_actionability = int(
        candidate_claims.get("claims_with_no_active_governed_support_actionability_count") or 0
    )
    if focus_claims_active_support != candidate_claims_active_support:
        cautions.append(
            "Claim-level active support differs: "
            f"{focus_claims_active_support} claim(s) with active governed support vs {candidate_claims_active_support}."
        )
    if focus_claims_historical_only != candidate_claims_historical_only:
        differences.append(
            "Claim-level historical support differs: "
            f"{focus_claims_historical_only} historical-only claim(s) vs {candidate_claims_historical_only}."
        )
    if focus_claims_no_governed_support != candidate_claims_no_governed_support:
        cautions.append(
            "Claim-level unsupported context differs: "
            f"{focus_claims_no_governed_support} claim(s) without governed support vs {candidate_claims_no_governed_support}."
        )
    if focus_claims_continuity_aligned != candidate_claims_continuity_aligned:
        cautions.append(
            "Claim continuity context differs: "
            f"{focus_claims_continuity_aligned} continuity-aligned claim(s) vs {candidate_claims_continuity_aligned}."
        )
    if focus_claims_active_governed_continuity != candidate_claims_active_governed_continuity:
        cautions.append(
            "Claim posture-governing continuity differs: "
            f"{focus_claims_active_governed_continuity} claim(s) vs {candidate_claims_active_governed_continuity}."
        )
    if focus_claims_tentative_active_continuity != candidate_claims_tentative_active_continuity:
        cautions.append(
            "Claim tentative-active continuity differs: "
            f"{focus_claims_tentative_active_continuity} claim(s) vs {candidate_claims_tentative_active_continuity}."
        )
    if focus_claims_historical_continuity_only != candidate_claims_historical_continuity_only:
        differences.append(
            "Claim historical-only continuity differs: "
            f"{focus_claims_historical_continuity_only} claim(s) vs {candidate_claims_historical_continuity_only}."
        )
    if focus_claims_new_context != candidate_claims_new_context:
        differences.append(
            "Claim new-context coverage differs: "
            f"{focus_claims_new_context} new-context claim(s) vs {candidate_claims_new_context}."
        )
    if focus_claims_weak_alignment != candidate_claims_weak_alignment:
        cautions.append(
            "Claim weak-alignment context differs: "
            f"{focus_claims_weak_alignment} weakly aligned claim(s) vs {candidate_claims_weak_alignment}."
        )
    if focus_claims_no_prior_context != candidate_claims_no_prior_context:
        cautions.append(
            "Claim prior-context coverage differs: "
            f"{focus_claims_no_prior_context} claim(s) with no prior context vs {candidate_claims_no_prior_context}."
        )
    if focus_claims_sparse_prior_context != candidate_claims_sparse_prior_context:
        cautions.append(
            "Claim sparse-prior-context coverage differs: "
            f"{focus_claims_sparse_prior_context} claim(s) vs {candidate_claims_sparse_prior_context}."
        )
    if focus_claims_no_useful_prior_context != candidate_claims_no_useful_prior_context:
        cautions.append(
            "Claim useful-prior-context coverage differs: "
            f"{focus_claims_no_useful_prior_context} claim(s) with no useful prior context vs {candidate_claims_no_useful_prior_context}."
        )
    if (
        focus_claims_observed_grounded != candidate_claims_observed_grounded
        or focus_claims_numeric_grounded != candidate_claims_numeric_grounded
        or focus_claims_weak_basis != candidate_claims_weak_basis
        or focus_claims_mixed_basis != candidate_claims_mixed_basis
        or focus_claims_posture_governing != candidate_claims_posture_governing
        or focus_claims_tentative_support != candidate_claims_tentative_support
        or focus_claims_accepted_limited_support != candidate_claims_accepted_limited_support
    ):
        cautions.append(
            "Claim support-basis composition differs: "
            f"{focus_claims_observed_grounded} observed-label-grounded / {focus_claims_numeric_grounded} numeric-rule / "
            f"{focus_claims_weak_basis} weak-basis / {focus_claims_mixed_basis} mixed / "
            f"{focus_claims_posture_governing} posture-governing / {focus_claims_tentative_support} tentative / "
            f"{focus_claims_accepted_limited_support} accepted-limited vs "
            f"{candidate_claims_observed_grounded} / {candidate_claims_numeric_grounded} / "
            f"{candidate_claims_weak_basis} / {candidate_claims_mixed_basis} / "
            f"{candidate_claims_posture_governing} / {candidate_claims_tentative_support} / "
            f"{candidate_claims_accepted_limited_support}."
        )
    if (
        focus_claims_contested_support != candidate_claims_contested_support
        or focus_claims_degraded_support != candidate_claims_degraded_support
        or focus_claims_historical_stronger != candidate_claims_historical_stronger
        or focus_claims_contradiction_limited_reuse != candidate_claims_contradiction_limited_reuse
    ):
        cautions.append(
            "Claim contradiction and reuse posture differs: "
            f"{focus_claims_contested_support} contested / {focus_claims_degraded_support} degraded / "
            f"{focus_claims_historical_stronger} historical-stronger / {focus_claims_contradiction_limited_reuse} contradiction-limited-reuse vs "
            f"{candidate_claims_contested_support} / {candidate_claims_degraded_support} / "
            f"{candidate_claims_historical_stronger} / {candidate_claims_contradiction_limited_reuse}."
        )
    if (
        focus_claims_action_ready != candidate_claims_action_ready
        or focus_claims_need_stronger_evidence != candidate_claims_need_stronger_evidence
        or focus_claims_need_clarifying_experiment != candidate_claims_need_clarifying_experiment
        or focus_claims_do_not_prioritize != candidate_claims_do_not_prioritize
        or focus_claims_insufficient_basis != candidate_claims_insufficient_basis
    ):
        cautions.append(
            "Claim actionability differs: "
            f"{focus_claims_action_ready} action-ready / {focus_claims_need_stronger_evidence} need-stronger-evidence / "
            f"{focus_claims_need_clarifying_experiment} need-clarification / {focus_claims_do_not_prioritize} do-not-prioritize / "
            f"{focus_claims_insufficient_basis} insufficient-basis vs "
            f"{candidate_claims_action_ready} / {candidate_claims_need_stronger_evidence} / "
            f"{candidate_claims_need_clarifying_experiment} / {candidate_claims_do_not_prioritize} / "
            f"{candidate_claims_insufficient_basis}."
        )
    if (
        focus_claims_action_ready_from_active != candidate_claims_action_ready_from_active
        or focus_claims_active_limited != candidate_claims_active_limited
        or focus_claims_historically_interesting != candidate_claims_historically_interesting
        or focus_claims_mixed_current_historical != candidate_claims_mixed_current_historical
        or focus_claims_no_active_actionability != candidate_claims_no_active_actionability
    ):
        differences.append(
            "Claim actionability basis differs: "
            f"{focus_claims_action_ready_from_active} action-ready-from-active / "
            f"{focus_claims_active_limited} active-but-limited / "
            f"{focus_claims_historically_interesting} historical-interest / "
            f"{focus_claims_mixed_current_historical} mixed-current-historical / "
            f"{focus_claims_no_active_actionability} no-active-support vs "
            f"{candidate_claims_action_ready_from_active} / "
            f"{candidate_claims_active_limited} / "
            f"{candidate_claims_historically_interesting} / "
            f"{candidate_claims_mixed_current_historical} / "
            f"{candidate_claims_no_active_actionability}."
        )
    if focus_support_role_label != candidate_support_role_label:
        cautions.append(
            "Support chronology role differs: "
            f"{focus_support_role_label.lower()} vs {candidate_support_role_label.lower()}."
        )
    if focus_support_role_summary or candidate_support_role_summary:
        if focus_support_role_summary != candidate_support_role_summary:
            differences.append(
                "Support chronology summary differs: "
                f"{focus_support_role_summary or 'not recorded'} vs {candidate_support_role_summary or 'not recorded'}."
            )
    focus_claims_read_across_summary = _clean_text(focus_claims.get("read_across_summary_text"))
    candidate_claims_read_across_summary = _clean_text(candidate_claims.get("read_across_summary_text"))
    if focus_claims_read_across_summary or candidate_claims_read_across_summary:
        if focus_claims_read_across_summary != candidate_claims_read_across_summary:
            differences.append(
                "Claim read-across summary differs: "
                f"{focus_claims_read_across_summary or 'not recorded'} vs {candidate_claims_read_across_summary or 'not recorded'}."
            )
    focus_claims_broader_reuse_label = _clean_text(focus_claims.get("broader_reuse_label"))
    candidate_claims_broader_reuse_label = _clean_text(candidate_claims.get("broader_reuse_label"))
    if focus_claims_broader_reuse_label or candidate_claims_broader_reuse_label:
        if focus_claims_broader_reuse_label != candidate_claims_broader_reuse_label:
            cautions.append(
                "Broader claim reuse posture differs: "
                f"{focus_claims_broader_reuse_label or 'not recorded'} vs {candidate_claims_broader_reuse_label or 'not recorded'}."
            )
    focus_claims_broader_continuity_label = _clean_text(focus_claims.get("broader_continuity_label"))
    candidate_claims_broader_continuity_label = _clean_text(candidate_claims.get("broader_continuity_label"))
    if focus_claims_broader_continuity_label or candidate_claims_broader_continuity_label:
        if focus_claims_broader_continuity_label != candidate_claims_broader_continuity_label:
            cautions.append(
                "Broader claim continuity differs: "
                f"{focus_claims_broader_continuity_label or 'not recorded'} vs {candidate_claims_broader_continuity_label or 'not recorded'}."
            )
    focus_claims_future_reuse_candidacy_label = _clean_text(focus_claims.get("future_reuse_candidacy_label"))
    candidate_claims_future_reuse_candidacy_label = _clean_text(candidate_claims.get("future_reuse_candidacy_label"))
    if focus_claims_future_reuse_candidacy_label or candidate_claims_future_reuse_candidacy_label:
        if focus_claims_future_reuse_candidacy_label != candidate_claims_future_reuse_candidacy_label:
            differences.append(
                "Future broader claim reuse candidacy differs: "
                f"{focus_claims_future_reuse_candidacy_label or 'not recorded'} vs {candidate_claims_future_reuse_candidacy_label or 'not recorded'}."
            )
    focus_claims_cluster_posture_label = _clean_text(focus_claims.get("continuity_cluster_posture_label"))
    candidate_claims_cluster_posture_label = _clean_text(candidate_claims.get("continuity_cluster_posture_label"))
    if focus_claims_cluster_posture_label or candidate_claims_cluster_posture_label:
        if focus_claims_cluster_posture_label != candidate_claims_cluster_posture_label:
            cautions.append(
                "Claim-family continuity-cluster posture differs: "
                f"{focus_claims_cluster_posture_label or 'not recorded'} vs {candidate_claims_cluster_posture_label or 'not recorded'}."
            )
    focus_claims_promotion_posture_label = _clean_text(focus_claims.get("promotion_candidate_posture_label"))
    candidate_claims_promotion_posture_label = _clean_text(candidate_claims.get("promotion_candidate_posture_label"))
    if focus_claims_promotion_posture_label or candidate_claims_promotion_posture_label:
        if focus_claims_promotion_posture_label != candidate_claims_promotion_posture_label:
            differences.append(
                "Claim-family promotion posture differs: "
                f"{focus_claims_promotion_posture_label or 'not recorded'} vs {candidate_claims_promotion_posture_label or 'not recorded'}."
            )
    focus_claims_promotion_stability_label = _clean_text(focus_claims.get("promotion_stability_label"))
    candidate_claims_promotion_stability_label = _clean_text(candidate_claims.get("promotion_stability_label"))
    if focus_claims_promotion_stability_label or candidate_claims_promotion_stability_label:
        if focus_claims_promotion_stability_label != candidate_claims_promotion_stability_label:
            cautions.append(
                "Claim-family promotion stability differs: "
                f"{focus_claims_promotion_stability_label or 'not recorded'} vs {candidate_claims_promotion_stability_label or 'not recorded'}."
            )
    focus_claims_promotion_gate_status_label = _clean_text(focus_claims.get("promotion_gate_status_label"))
    candidate_claims_promotion_gate_status_label = _clean_text(candidate_claims.get("promotion_gate_status_label"))
    if focus_claims_promotion_gate_status_label or candidate_claims_promotion_gate_status_label:
        if focus_claims_promotion_gate_status_label != candidate_claims_promotion_gate_status_label:
            differences.append(
                "Claim-family promotion gate differs: "
                f"{focus_claims_promotion_gate_status_label or 'not recorded'} vs {candidate_claims_promotion_gate_status_label or 'not recorded'}."
            )
    focus_claims_promotion_block_reason_label = _clean_text(focus_claims.get("promotion_block_reason_label"))
    candidate_claims_promotion_block_reason_label = _clean_text(candidate_claims.get("promotion_block_reason_label"))
    if focus_claims_promotion_block_reason_label or candidate_claims_promotion_block_reason_label:
        if focus_claims_promotion_block_reason_label != candidate_claims_promotion_block_reason_label:
            differences.append(
                "Claim-family promotion block reason differs: "
                f"{focus_claims_promotion_block_reason_label or 'not recorded'} vs {candidate_claims_promotion_block_reason_label or 'not recorded'}."
            )
    focus_claims_actionability_summary = _clean_text(focus_claims.get("claim_actionability_summary_text"))
    candidate_claims_actionability_summary = _clean_text(candidate_claims.get("claim_actionability_summary_text"))
    if focus_claims_actionability_summary or candidate_claims_actionability_summary:
        if focus_claims_actionability_summary != candidate_claims_actionability_summary:
            differences.append(
                "Claim actionability summary differs: "
                f"{focus_claims_actionability_summary or 'not recorded'} vs {candidate_claims_actionability_summary or 'not recorded'}."
            )
    focus_claims_actionability_basis_summary = _clean_text(focus_claims.get("claim_actionability_basis_summary_text"))
    candidate_claims_actionability_basis_summary = _clean_text(candidate_claims.get("claim_actionability_basis_summary_text"))
    if focus_claims_actionability_basis_summary or candidate_claims_actionability_basis_summary:
        if focus_claims_actionability_basis_summary != candidate_claims_actionability_basis_summary:
            differences.append(
                "Claim actionability-basis summary differs: "
                f"{focus_claims_actionability_basis_summary or 'not recorded'} vs {candidate_claims_actionability_basis_summary or 'not recorded'}."
            )
    focus_decision_status_label = _clean_text(focus_decision_summary.get("decision_status_label"))
    candidate_decision_status_label = _clean_text(candidate_decision_summary.get("decision_status_label"))
    if focus_decision_status_label or candidate_decision_status_label:
        if focus_decision_status_label != candidate_decision_status_label:
            differences.append(
                "Current scientific decision picture differs: "
                f"{focus_decision_status_label or 'not recorded'} vs {candidate_decision_status_label or 'not recorded'}."
            )
    focus_decision_support_quality_label = _clean_text(focus_decision_summary.get("current_support_quality_label"))
    candidate_decision_support_quality_label = _clean_text(candidate_decision_summary.get("current_support_quality_label"))
    if focus_decision_support_quality_label or candidate_decision_support_quality_label:
        if focus_decision_support_quality_label != candidate_decision_support_quality_label:
            differences.append(
                "Current support-quality grounding differs: "
                f"{focus_decision_support_quality_label or 'not recorded'} vs {candidate_decision_support_quality_label or 'not recorded'}."
            )
    focus_decision_governed_posture_label = _clean_text(focus_decision_summary.get("current_governed_support_posture_label"))
    candidate_decision_governed_posture_label = _clean_text(candidate_decision_summary.get("current_governed_support_posture_label"))
    if focus_decision_governed_posture_label or candidate_decision_governed_posture_label:
        if focus_decision_governed_posture_label != candidate_decision_governed_posture_label:
            differences.append(
                "Current governed-support posture differs: "
                f"{focus_decision_governed_posture_label or 'not recorded'} vs {candidate_decision_governed_posture_label or 'not recorded'}."
            )
    focus_decision_support_coherence_label = _clean_text(focus_decision_summary.get("current_support_coherence_label"))
    candidate_decision_support_coherence_label = _clean_text(candidate_decision_summary.get("current_support_coherence_label"))
    if focus_decision_support_coherence_label or candidate_decision_support_coherence_label:
        if focus_decision_support_coherence_label != candidate_decision_support_coherence_label:
            cautions.append(
                "Current support coherence differs: "
                f"{focus_decision_support_coherence_label or 'not recorded'} vs {candidate_decision_support_coherence_label or 'not recorded'}."
            )
    focus_decision_support_reuse_label = _clean_text(focus_decision_summary.get("current_support_reuse_label"))
    candidate_decision_support_reuse_label = _clean_text(candidate_decision_summary.get("current_support_reuse_label"))
    if focus_decision_support_reuse_label or candidate_decision_support_reuse_label:
        if focus_decision_support_reuse_label != candidate_decision_support_reuse_label:
            cautions.append(
                "Current support reuse differs: "
                f"{focus_decision_support_reuse_label or 'not recorded'} vs {candidate_decision_support_reuse_label or 'not recorded'}."
            )
    focus_decision_broader_reuse_label = _clean_text(focus_decision_summary.get("broader_governed_reuse_label"))
    candidate_decision_broader_reuse_label = _clean_text(candidate_decision_summary.get("broader_governed_reuse_label"))
    if focus_decision_broader_reuse_label or candidate_decision_broader_reuse_label:
        if focus_decision_broader_reuse_label != candidate_decision_broader_reuse_label:
            differences.append(
                "Broader governed reuse differs: "
                f"{focus_decision_broader_reuse_label or 'not recorded'} vs {candidate_decision_broader_reuse_label or 'not recorded'}."
            )
    focus_decision_broader_continuity_label = _clean_text(focus_decision_summary.get("broader_continuity_label"))
    candidate_decision_broader_continuity_label = _clean_text(candidate_decision_summary.get("broader_continuity_label"))
    if focus_decision_broader_continuity_label or candidate_decision_broader_continuity_label:
        if focus_decision_broader_continuity_label != candidate_decision_broader_continuity_label:
            cautions.append(
                "Broader continuity differs: "
                f"{focus_decision_broader_continuity_label or 'not recorded'} vs {candidate_decision_broader_continuity_label or 'not recorded'}."
            )
    focus_decision_future_reuse_candidacy_label = _clean_text(focus_decision_summary.get("future_reuse_candidacy_label"))
    candidate_decision_future_reuse_candidacy_label = _clean_text(candidate_decision_summary.get("future_reuse_candidacy_label"))
    if focus_decision_future_reuse_candidacy_label or candidate_decision_future_reuse_candidacy_label:
        if focus_decision_future_reuse_candidacy_label != candidate_decision_future_reuse_candidacy_label:
            differences.append(
                "Future broader governed reuse candidacy differs: "
                f"{focus_decision_future_reuse_candidacy_label or 'not recorded'} vs {candidate_decision_future_reuse_candidacy_label or 'not recorded'}."
            )
    focus_decision_cluster_posture_label = _clean_text(focus_decision_summary.get("continuity_cluster_posture_label"))
    candidate_decision_cluster_posture_label = _clean_text(candidate_decision_summary.get("continuity_cluster_posture_label"))
    if focus_decision_cluster_posture_label or candidate_decision_cluster_posture_label:
        if focus_decision_cluster_posture_label != candidate_decision_cluster_posture_label:
            cautions.append(
                "Session-family continuity-cluster posture differs: "
                f"{focus_decision_cluster_posture_label or 'not recorded'} vs {candidate_decision_cluster_posture_label or 'not recorded'}."
            )
    focus_decision_promotion_posture_label = _clean_text(focus_decision_summary.get("promotion_candidate_posture_label"))
    candidate_decision_promotion_posture_label = _clean_text(candidate_decision_summary.get("promotion_candidate_posture_label"))
    if focus_decision_promotion_posture_label or candidate_decision_promotion_posture_label:
        if focus_decision_promotion_posture_label != candidate_decision_promotion_posture_label:
            differences.append(
                "Session-family promotion posture differs: "
                f"{focus_decision_promotion_posture_label or 'not recorded'} vs {candidate_decision_promotion_posture_label or 'not recorded'}."
            )
    focus_decision_promotion_stability_label = _clean_text(focus_decision_summary.get("promotion_stability_label"))
    candidate_decision_promotion_stability_label = _clean_text(candidate_decision_summary.get("promotion_stability_label"))
    if focus_decision_promotion_stability_label or candidate_decision_promotion_stability_label:
        if focus_decision_promotion_stability_label != candidate_decision_promotion_stability_label:
            cautions.append(
                "Session-family promotion stability differs: "
                f"{focus_decision_promotion_stability_label or 'not recorded'} vs {candidate_decision_promotion_stability_label or 'not recorded'}."
            )
    focus_decision_promotion_gate_status_label = _clean_text(focus_decision_summary.get("promotion_gate_status_label"))
    candidate_decision_promotion_gate_status_label = _clean_text(candidate_decision_summary.get("promotion_gate_status_label"))
    if focus_decision_promotion_gate_status_label or candidate_decision_promotion_gate_status_label:
        if focus_decision_promotion_gate_status_label != candidate_decision_promotion_gate_status_label:
            differences.append(
                "Session-family promotion gate differs: "
                f"{focus_decision_promotion_gate_status_label or 'not recorded'} vs {candidate_decision_promotion_gate_status_label or 'not recorded'}."
            )
    focus_decision_promotion_block_reason_label = _clean_text(focus_decision_summary.get("promotion_block_reason_label"))
    candidate_decision_promotion_block_reason_label = _clean_text(candidate_decision_summary.get("promotion_block_reason_label"))
    if focus_decision_promotion_block_reason_label or candidate_decision_promotion_block_reason_label:
        if focus_decision_promotion_block_reason_label != candidate_decision_promotion_block_reason_label:
            differences.append(
                "Session-family promotion block reason differs: "
                f"{focus_decision_promotion_block_reason_label or 'not recorded'} vs {candidate_decision_promotion_block_reason_label or 'not recorded'}."
            )
    focus_session_family_review_status_label = _clean_text(focus_decision_summary.get("session_family_review_status_label"))
    candidate_session_family_review_status_label = _clean_text(candidate_decision_summary.get("session_family_review_status_label"))
    if focus_session_family_review_status_label or candidate_session_family_review_status_label:
        if focus_session_family_review_status_label != candidate_session_family_review_status_label:
            differences.append(
                "Session-family carryover review differs: "
                f"{focus_session_family_review_status_label or 'not recorded'} vs {candidate_session_family_review_status_label or 'not recorded'}."
            )
    focus_session_family_review_origin = _clean_text(focus_decision_summary.get("session_family_effective_review_origin_label"))
    candidate_session_family_review_origin = _clean_text(candidate_decision_summary.get("session_family_effective_review_origin_label"))
    if focus_session_family_review_origin or candidate_session_family_review_origin:
        if focus_session_family_review_origin != candidate_session_family_review_origin:
            cautions.append(
                "Session-family governance source differs: "
                f"{focus_session_family_review_origin or 'not recorded'} vs {candidate_session_family_review_origin or 'not recorded'}."
            )
    focus_next_step_label = _clean_text(focus_decision_summary.get("next_step_label"))
    candidate_next_step_label = _clean_text(candidate_decision_summary.get("next_step_label"))
    if focus_next_step_label or candidate_next_step_label:
        if focus_next_step_label != candidate_next_step_label:
            cautions.append(
                "Bounded next-step posture differs: "
                f"{focus_next_step_label or 'not recorded'} vs {candidate_next_step_label or 'not recorded'}."
            )

    focus_readiness = _clean_text(focus_belief_state.get("belief_state_readiness_summary"))
    candidate_readiness = _clean_text(candidate_belief_state.get("belief_state_readiness_summary"))
    if focus_readiness or candidate_readiness:
        if focus_readiness != candidate_readiness:
            cautions.append(
                "Belief-state readiness differs: "
                f"{focus_readiness or 'not recorded'} vs {candidate_readiness or 'not recorded'}."
            )

    if focus_belief_alignment_label or candidate_belief_alignment_label:
        if focus_belief_alignment_label != candidate_belief_alignment_label:
            cautions.append(
                "Current belief-picture alignment differs: "
                f"{focus_belief_alignment_label or 'not recorded'} vs {candidate_belief_alignment_label or 'not recorded'}."
            )
    if focus_belief_alignment_summary or candidate_belief_alignment_summary:
        if focus_belief_alignment_summary != candidate_belief_alignment_summary:
            differences.append(
                "Belief-picture read-across differs: "
                f"{focus_belief_alignment_summary or 'not recorded'} vs {candidate_belief_alignment_summary or 'not recorded'}."
            )
    focus_belief_state_governed_posture = _clean_text(focus_belief_state.get("governed_support_posture_label"))
    candidate_belief_state_governed_posture = _clean_text(candidate_belief_state.get("governed_support_posture_label"))
    if focus_belief_state_governed_posture or candidate_belief_state_governed_posture:
        if focus_belief_state_governed_posture != candidate_belief_state_governed_posture:
            cautions.append(
                "Belief-state governed posture differs: "
                f"{focus_belief_state_governed_posture or 'not recorded'} vs {candidate_belief_state_governed_posture or 'not recorded'}."
            )
    focus_belief_state_support_coherence = _clean_text(focus_belief_state.get("support_coherence_label"))
    candidate_belief_state_support_coherence = _clean_text(candidate_belief_state.get("support_coherence_label"))
    if focus_belief_state_support_coherence or candidate_belief_state_support_coherence:
        if focus_belief_state_support_coherence != candidate_belief_state_support_coherence:
            cautions.append(
                "Belief-state support coherence differs: "
                f"{focus_belief_state_support_coherence or 'not recorded'} vs {candidate_belief_state_support_coherence or 'not recorded'}."
            )
    focus_belief_state_broader_reuse_label = _clean_text(focus_belief_state.get("broader_target_reuse_label"))
    candidate_belief_state_broader_reuse_label = _clean_text(candidate_belief_state.get("broader_target_reuse_label"))
    if focus_belief_state_broader_reuse_label or candidate_belief_state_broader_reuse_label:
        if focus_belief_state_broader_reuse_label != candidate_belief_state_broader_reuse_label:
            differences.append(
                "Broader target reuse differs: "
                f"{focus_belief_state_broader_reuse_label or 'not recorded'} vs {candidate_belief_state_broader_reuse_label or 'not recorded'}."
            )
    focus_belief_state_broader_continuity_label = _clean_text(focus_belief_state.get("broader_target_continuity_label"))
    candidate_belief_state_broader_continuity_label = _clean_text(candidate_belief_state.get("broader_target_continuity_label"))
    if focus_belief_state_broader_continuity_label or candidate_belief_state_broader_continuity_label:
        if focus_belief_state_broader_continuity_label != candidate_belief_state_broader_continuity_label:
            cautions.append(
                "Broader target continuity differs: "
                f"{focus_belief_state_broader_continuity_label or 'not recorded'} vs {candidate_belief_state_broader_continuity_label or 'not recorded'}."
            )
    focus_belief_state_future_reuse_candidacy_label = _clean_text(focus_belief_state.get("future_reuse_candidacy_label"))
    candidate_belief_state_future_reuse_candidacy_label = _clean_text(candidate_belief_state.get("future_reuse_candidacy_label"))
    if focus_belief_state_future_reuse_candidacy_label or candidate_belief_state_future_reuse_candidacy_label:
        if focus_belief_state_future_reuse_candidacy_label != candidate_belief_state_future_reuse_candidacy_label:
            differences.append(
                "Future broader target reuse candidacy differs: "
                f"{focus_belief_state_future_reuse_candidacy_label or 'not recorded'} vs {candidate_belief_state_future_reuse_candidacy_label or 'not recorded'}."
            )
    focus_belief_state_cluster_posture_label = _clean_text(focus_belief_state.get("continuity_cluster_posture_label"))
    candidate_belief_state_cluster_posture_label = _clean_text(candidate_belief_state.get("continuity_cluster_posture_label"))
    if focus_belief_state_cluster_posture_label or candidate_belief_state_cluster_posture_label:
        if focus_belief_state_cluster_posture_label != candidate_belief_state_cluster_posture_label:
            cautions.append(
                "Target-scoped continuity-cluster posture differs: "
                f"{focus_belief_state_cluster_posture_label or 'not recorded'} vs {candidate_belief_state_cluster_posture_label or 'not recorded'}."
            )
    focus_belief_state_promotion_posture_label = _clean_text(focus_belief_state.get("promotion_candidate_posture_label"))
    candidate_belief_state_promotion_posture_label = _clean_text(candidate_belief_state.get("promotion_candidate_posture_label"))
    if focus_belief_state_promotion_posture_label or candidate_belief_state_promotion_posture_label:
        if focus_belief_state_promotion_posture_label != candidate_belief_state_promotion_posture_label:
            differences.append(
                "Target-scoped promotion posture differs: "
                f"{focus_belief_state_promotion_posture_label or 'not recorded'} vs {candidate_belief_state_promotion_posture_label or 'not recorded'}."
            )
    focus_belief_state_promotion_stability_label = _clean_text(focus_belief_state.get("promotion_stability_label"))
    candidate_belief_state_promotion_stability_label = _clean_text(candidate_belief_state.get("promotion_stability_label"))
    if focus_belief_state_promotion_stability_label or candidate_belief_state_promotion_stability_label:
        if focus_belief_state_promotion_stability_label != candidate_belief_state_promotion_stability_label:
            cautions.append(
                "Target-scoped promotion stability differs: "
                f"{focus_belief_state_promotion_stability_label or 'not recorded'} vs {candidate_belief_state_promotion_stability_label or 'not recorded'}."
            )
    focus_belief_state_promotion_gate_status_label = _clean_text(focus_belief_state.get("promotion_gate_status_label"))
    candidate_belief_state_promotion_gate_status_label = _clean_text(candidate_belief_state.get("promotion_gate_status_label"))
    if focus_belief_state_promotion_gate_status_label or candidate_belief_state_promotion_gate_status_label:
        if focus_belief_state_promotion_gate_status_label != candidate_belief_state_promotion_gate_status_label:
            differences.append(
                "Target-scoped promotion gate differs: "
                f"{focus_belief_state_promotion_gate_status_label or 'not recorded'} vs {candidate_belief_state_promotion_gate_status_label or 'not recorded'}."
            )
    focus_belief_state_promotion_block_reason_label = _clean_text(focus_belief_state.get("promotion_block_reason_label"))
    candidate_belief_state_promotion_block_reason_label = _clean_text(candidate_belief_state.get("promotion_block_reason_label"))
    if focus_belief_state_promotion_block_reason_label or candidate_belief_state_promotion_block_reason_label:
        if focus_belief_state_promotion_block_reason_label != candidate_belief_state_promotion_block_reason_label:
            differences.append(
                "Target-scoped promotion block reason differs: "
                f"{focus_belief_state_promotion_block_reason_label or 'not recorded'} vs {candidate_belief_state_promotion_block_reason_label or 'not recorded'}."
            )
    focus_belief_state_review_status_label = _clean_text(focus_belief_state.get("governed_review_status_label"))
    candidate_belief_state_review_status_label = _clean_text(candidate_belief_state.get("governed_review_status_label"))
    if focus_belief_state_review_status_label or candidate_belief_state_review_status_label:
        if focus_belief_state_review_status_label != candidate_belief_state_review_status_label:
            differences.append(
                "Belief-state broader review differs: "
                f"{focus_belief_state_review_status_label or 'not recorded'} vs {candidate_belief_state_review_status_label or 'not recorded'}."
            )
    focus_continuity_review_status_label = _clean_text(focus_belief_state.get("continuity_cluster_review_status_label"))
    candidate_continuity_review_status_label = _clean_text(candidate_belief_state.get("continuity_cluster_review_status_label"))
    if focus_continuity_review_status_label or candidate_continuity_review_status_label:
        if focus_continuity_review_status_label != candidate_continuity_review_status_label:
            cautions.append(
                "Continuity-cluster review differs: "
                f"{focus_continuity_review_status_label or 'not recorded'} vs {candidate_continuity_review_status_label or 'not recorded'}."
            )

    focus_bucket = _clean_text(focus_outcome.get("leading_bucket"))
    candidate_bucket = _clean_text(candidate_outcome.get("leading_bucket"))
    if focus_bucket and candidate_bucket and focus_bucket == candidate_bucket and focus_bucket != "unassigned":
        matches.append(f"Same leading shortlist bucket: {_humanize_token(focus_bucket)}.")
    elif focus_bucket or candidate_bucket:
        outcome_differences.append(
            f"Leading shortlist bucket differs: {_humanize_token(focus_bucket)} vs {_humanize_token(candidate_bucket)}."
        )

    focus_trust = _clean_text(focus_outcome.get("dominant_trust"))
    candidate_trust = _clean_text(candidate_outcome.get("dominant_trust"))
    if focus_trust and candidate_trust and focus_trust != candidate_trust:
        outcome_differences.append(
            f"Dominant trust profile differs: {_humanize_token(focus_trust)} vs {_humanize_token(candidate_trust)}."
        )

    focus_domain_rate = focus_outcome.get("out_of_domain_rate")
    candidate_domain_rate = candidate_outcome.get("out_of_domain_rate")
    if focus_domain_rate is not None and candidate_domain_rate is not None:
        try:
            focus_domain_rate = float(focus_domain_rate)
            candidate_domain_rate = float(candidate_domain_rate)
        except (TypeError, ValueError):
            focus_domain_rate = candidate_domain_rate = None
        if focus_domain_rate is not None and candidate_domain_rate is not None:
            delta = focus_domain_rate - candidate_domain_rate
            if abs(delta) >= 0.10:
                direction = "higher" if delta > 0 else "lower"
                outcome_differences.append(
                    f"Weak-support rate is {direction} by {abs(delta) * 100:.1f}%."
                )

    focus_rank_corr = focus_outcome.get("spearman_rank_correlation")
    candidate_rank_corr = candidate_outcome.get("spearman_rank_correlation")
    if focus_rank_corr is not None and candidate_rank_corr is not None:
        try:
            focus_rank_corr = float(focus_rank_corr)
            candidate_rank_corr = float(candidate_rank_corr)
        except (TypeError, ValueError):
            focus_rank_corr = candidate_rank_corr = None
        if focus_rank_corr is not None and candidate_rank_corr is not None:
            delta = focus_rank_corr - candidate_rank_corr
            if abs(delta) >= 0.10:
                direction = "higher" if delta > 0 else "lower"
                outcome_differences.append(
                    f"Rank correlation is {direction} by {abs(delta):.3f}."
                )

    candidate_comparison = _compare_candidate_previews(
        focus_candidate_preview,
        candidate_candidate_preview,
    )
    focus_top_gap = _safe_float(((focus_predictive_evaluation.get("offline_ranking_evaluation") or {}) if isinstance(focus_predictive_evaluation.get("offline_ranking_evaluation"), dict) else {}).get("top_gap"))
    candidate_top_gap = _safe_float(((candidate_predictive_evaluation.get("offline_ranking_evaluation") or {}) if isinstance(candidate_predictive_evaluation.get("offline_ranking_evaluation"), dict) else {}).get("top_gap"))
    if focus_top_gap is not None and candidate_top_gap is not None and abs(focus_top_gap - candidate_top_gap) >= 0.015:
        direction = "higher" if candidate_top_gap > focus_top_gap else "lower"
        outcome_differences.append(
            f"Top-gap separation is {direction} by {abs(candidate_top_gap - focus_top_gap):.3f}."
        )
    focus_too_close_rate = _safe_float(((focus_predictive_evaluation.get("offline_ranking_evaluation") or {}) if isinstance(focus_predictive_evaluation.get("offline_ranking_evaluation"), dict) else {}).get("too_close_rate"))
    candidate_too_close_rate = _safe_float(((candidate_predictive_evaluation.get("offline_ranking_evaluation") or {}) if isinstance(candidate_predictive_evaluation.get("offline_ranking_evaluation"), dict) else {}).get("too_close_rate"))
    if focus_too_close_rate is not None and candidate_too_close_rate is not None and abs(focus_too_close_rate - candidate_too_close_rate) >= 0.15:
        direction = "more" if candidate_too_close_rate > focus_too_close_rate else "less"
        outcome_differences.append(
            f"The comparison shortlist has {direction} too-close-to-separate pressure by {abs(candidate_too_close_rate - focus_too_close_rate) * 100:.1f}%."
        )
    outcome_preview_gap = bool(outcome_differences) and not (focus_candidate_preview and candidate_candidate_preview)
    if outcome_preview_gap:
        cautions.append("Outcome differences are summarized without shared shortlist preview support.")

    if blockers:
        status = "not_comparable"
        tone = "danger"
        label = "Not directly comparable"
        summary = "These sessions are not cleanly comparable because the scientific target or modeling method changed."
    elif differences or cautions or not (focus_ready and candidate_ready):
        status = "partially_comparable"
        tone = "warning"
        label = "Partially comparable"
        summary = "These sessions can be read across cautiously, but policy drift, provenance drift, or incomplete metadata weakens the comparison."
    else:
        status = "directly_comparable"
        tone = "success"
        label = "Directly comparable"
        summary = "These sessions share the same target, modeling mode, and policy contract closely enough for straightforward read-across."

    return {
        "status": status,
        "tone": tone,
        "label": label,
        "summary": summary,
        "basis_source_summary": (
            f"{_basis_source_label(focus_session)} vs {_basis_source_label(candidate_session)}."
            if _basis_source_label(focus_session) != _basis_source_label(candidate_session)
            else _basis_source_label(focus_session)
        ),
        "matches": matches[:5],
        "differences": differences[:12],
        "outcome_differences": outcome_differences[:5],
        "candidate_comparison_summary": candidate_comparison.get("summary") or "",
        "candidate_differences": candidate_comparison.get("differences") or [],
        "cautions": cautions[:20],
        "blockers": blockers[:5],
    }


def build_session_comparison_overview(
    *,
    focus_session: dict[str, Any] | None,
    items: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    focus_session = focus_session if isinstance(focus_session, dict) else {}
    items = items if isinstance(items, list) else []
    if not focus_session:
        return {
            "focus_session_id": "",
            "comparisons": [],
            "counts": {
                "directly_comparable": 0,
                "partially_comparable": 0,
                "not_comparable": 0,
            },
        }

    comparisons: list[dict[str, Any]] = []
    counts = {
        "directly_comparable": 0,
        "partially_comparable": 0,
        "not_comparable": 0,
    }

    for item in items:
        if item is focus_session:
            continue
        comparison = compare_session_basis(focus_session=focus_session, candidate_session=item)
        counts[comparison["status"]] += 1
        comparisons.append(
            {
                "session_id": item.get("session_id"),
                "source_name": item.get("source_name"),
                "comparison": comparison,
            }
        )

    return {
        "focus_session_id": focus_session.get("session_id") or "",
        "comparisons": comparisons,
        "counts": counts,
    }


def build_session_comparison_matrix(
    *,
    focus_session: dict[str, Any] | None,
    items: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    focus_session = focus_session if isinstance(focus_session, dict) else {}
    items = items if isinstance(items, list) else []
    if not focus_session:
        return {
            "focus_session_id": "",
            "rows": [],
            "counts": {
                "directly_comparable": 0,
                "partially_comparable": 0,
                "not_comparable": 0,
            },
        }

    focus_anchors = _comparison_anchors(focus_session)
    focus_rows_total = int(focus_session.get("rows_total") or 0)
    focus_value_rows = int(focus_session.get("rows_with_values") or 0)
    focus_candidate_count = int(focus_session.get("candidate_count") or 0)
    focus_top_experiment_value = focus_session.get("top_experiment_value")
    try:
        focus_top_experiment_value = float(focus_top_experiment_value)
    except (TypeError, ValueError):
        focus_top_experiment_value = None

    def _measurement_or_label(anchors: dict[str, Any]) -> str:
        measurement = _clean_text(anchors.get("measurement_column"))
        label = _clean_text(anchors.get("label_column"))
        if measurement:
            return f"Measurement: {measurement}"
        if label:
            return f"Label: {label}"
        return "Not recorded"

    def _row_for_item(item: dict[str, Any], comparison: dict[str, Any] | None, *, is_focus: bool) -> dict[str, Any]:
        comparison = comparison if isinstance(comparison, dict) else {}
        anchors = _comparison_anchors(item)
        outcome_profile = item.get("outcome_profile") if isinstance(item.get("outcome_profile"), dict) else {}
        top_experiment_value = item.get("top_experiment_value")
        try:
            top_experiment_value = float(top_experiment_value)
        except (TypeError, ValueError):
            top_experiment_value = None
        evidence_loop = _evidence_loop(item)
        activation_policy = _evidence_activation_policy(item)
        bridge_state_notes = _bridge_state_notes(item)
        controlled_reuse = _controlled_reuse(item)
        claims_summary = _claims_summary(item)
        belief_state = _belief_state_summary(item)
        belief_updates = _belief_update_summary(item)
        scientific_decision_summary = _scientific_decision_summary(item)
        governance_summary = item.get("governance_summary") if isinstance(item.get("governance_summary"), dict) else {}
        predictive_path_summary = _predictive_path_summary(item)
        session_support_role_label, session_support_role_summary = _session_support_role(item)

        if is_focus:
            comparison_payload = {
                "status": "focus",
                "tone": "muted",
                "label": "Focus session",
                "summary": "This row is the reference session that the matrix compares against.",
            }
        else:
            comparison_payload = comparison or {
                "status": "not_comparable",
                "tone": "muted",
                "label": "Comparison not recorded",
                "summary": "Comparison details were not recorded for this session.",
            }

        rows_total = int(item.get("rows_total") or 0)
        rows_with_values = int(item.get("rows_with_values") or 0)
        candidate_count = int(item.get("candidate_count") or 0)
        top_value_delta = None
        if (
            not is_focus
            and comparison_payload.get("status") in {"directly_comparable", "partially_comparable"}
            and top_experiment_value is not None
            and focus_top_experiment_value is not None
        ):
            top_value_delta = top_experiment_value - focus_top_experiment_value

        return {
            "session_id": item.get("session_id") or "",
            "source_name": item.get("source_name") or "",
            "is_focus": is_focus,
            "comparison": comparison_payload,
            "target_name": _clean_text(anchors.get("target_name"), default="Not recorded"),
            "target_kind_label": _humanize_token(anchors.get("target_kind")),
            "goal_label": _humanize_token(anchors.get("optimization_direction")),
            "measurement_or_label": _measurement_or_label(anchors),
            "modeling_mode_label": _humanize_token(anchors.get("modeling_mode")),
            "decision_intent_label": _humanize_token(anchors.get("decision_intent")),
            "policy_version": _clean_text(anchors.get("scoring_policy_version"), default="Not recorded"),
            "model_name": _clean_text(anchors.get("selected_model_name"), default="Not recorded"),
            "training_scope_label": _humanize_token(anchors.get("training_scope")),
            "rows_total": rows_total,
            "rows_total_delta": 0 if is_focus else rows_total - focus_rows_total,
            "rows_with_values": rows_with_values,
            "rows_with_values_delta": 0 if is_focus else rows_with_values - focus_value_rows,
            "candidate_count": candidate_count,
            "candidate_count_delta": 0 if is_focus else candidate_count - focus_candidate_count,
            "top_experiment_value": top_experiment_value,
            "top_experiment_value_delta": top_value_delta,
            "bucket_summary": _clean_text(outcome_profile.get("bucket_summary"), default="No bucket mix recorded."),
            "leading_bucket_label": _humanize_token(outcome_profile.get("leading_bucket")),
            "trust_summary": _clean_text(outcome_profile.get("trust_summary"), default="No trust profile recorded."),
            "dominant_trust_label": _humanize_token(outcome_profile.get("dominant_trust")),
            "diagnostics_summary": _clean_text(
                outcome_profile.get("diagnostics_summary"),
                default="No ranking diagnostics recorded.",
            ),
            "candidate_comparison_summary": _clean_text(
                comparison_payload.get("candidate_comparison_summary"),
                default="Reference shortlist preview." if is_focus else "Shortlist preview not compared.",
            ),
            "basis_source_label": _basis_source_label(item),
            "comparison_basis_label": _comparison_basis_label(item),
            "evidence_basis_label": _evidence_basis_label(item),
            "interpretation_evidence_label": _interpretation_evidence_label(item),
            "activation_boundary_summary": _activation_boundary_summary(item),
            "activation_policy_summary": _clean_text(activation_policy.get("summary")),
            "activation_policy_trust_tier_label": _clean_text(
                activation_policy.get("trust_tier_label"),
                default="Not recorded",
            ),
            "activation_policy_trust_tier_summary": _clean_text(
                activation_policy.get("trust_tier_summary")
            ),
            "activation_policy_provenance_confidence_label": _clean_text(
                activation_policy.get("provenance_confidence_label"),
                default="Not recorded",
            ),
            "activation_policy_provenance_confidence_summary": _clean_text(
                activation_policy.get("provenance_confidence_summary")
            ),
            "activation_policy_governed_review_status_label": _clean_text(
                activation_policy.get("governed_review_status_label"),
                default="Not recorded",
            ),
            "activation_policy_governed_review_status_summary": _clean_text(
                activation_policy.get("governed_review_status_summary")
            ),
            "activation_policy_governed_review_reason_label": _clean_text(
                activation_policy.get("governed_review_reason_label"),
                default="Not recorded",
            ),
            "activation_policy_governed_review_reason_summary": _clean_text(
                activation_policy.get("governed_review_reason_summary")
            ),
            "activation_policy_local_only_default_summary": _clean_text(
                activation_policy.get("local_only_default_summary")
            ),
            "activation_policy_anti_poisoning_summary": _clean_text(
                activation_policy.get("anti_poisoning_summary")
            ),
            "recommendation_reuse_summary": _recommendation_reuse_summary(item),
            "future_ranking_context_summary": _future_ranking_context_summary(item),
            "future_learning_eligibility_summary": _future_learning_eligibility_summary(item),
            "permanently_non_active_summary": _permanently_non_active_summary(item),
            "controlled_reuse_summary": _controlled_reuse_summary(item),
            "belief_state_strength_summary": _belief_state_strength_summary(item),
            "belief_state_readiness_summary": _belief_state_readiness_summary(item),
            "belief_state_governance_label": _belief_state_governance_label(item),
            "belief_state_alignment_label": _belief_state_alignment_label(item),
            "belief_state_alignment_summary": _belief_state_alignment_summary(item),
            "belief_state_support_basis_label": _clean_text(
                belief_state.get("support_basis_mix_label"),
                default="Not recorded",
            ),
            "belief_state_support_basis_summary": _clean_text(
                belief_state.get("support_basis_mix_summary")
            ),
            "belief_state_support_quality_label": _clean_text(
                belief_state.get("support_quality_label"),
                default="Not recorded",
            ),
            "belief_state_support_quality_summary": _clean_text(
                belief_state.get("support_quality_summary")
            ),
            "belief_state_governed_support_posture_label": _clean_text(
                belief_state.get("governed_support_posture_label"),
                default="Not recorded",
            ),
            "belief_state_governed_support_posture_summary": _clean_text(
                belief_state.get("governed_support_posture_summary")
            ),
            "belief_state_support_coherence_label": _clean_text(
                belief_state.get("support_coherence_label"),
                default="Not recorded",
            ),
            "belief_state_support_coherence_summary": _clean_text(
                belief_state.get("support_coherence_summary")
            ),
            "belief_state_support_reuse_label": _clean_text(
                belief_state.get("support_reuse_label"),
                default="Not recorded",
            ),
            "belief_state_support_reuse_summary": _clean_text(
                belief_state.get("support_reuse_summary")
            ),
            "belief_state_broader_target_reuse_label": _clean_text(
                belief_state.get("broader_target_reuse_label"),
                default="Not recorded",
            ),
            "belief_state_broader_target_reuse_summary": _clean_text(
                belief_state.get("broader_target_reuse_summary")
            ),
            "belief_state_broader_target_continuity_label": _clean_text(
                belief_state.get("broader_target_continuity_label"),
                default="Not recorded",
            ),
            "belief_state_broader_target_continuity_summary": _clean_text(
                belief_state.get("broader_target_continuity_summary")
            ),
            "belief_state_future_reuse_candidacy_label": _clean_text(
                belief_state.get("future_reuse_candidacy_label"),
                default="Not recorded",
            ),
            "belief_state_future_reuse_candidacy_summary": _clean_text(
                belief_state.get("future_reuse_candidacy_summary")
            ),
            "belief_state_continuity_cluster_posture_label": _clean_text(
                belief_state.get("continuity_cluster_posture_label"),
                default="Not recorded",
            ),
            "belief_state_continuity_cluster_posture_summary": _clean_text(
                belief_state.get("continuity_cluster_posture_summary")
            ),
            "belief_state_promotion_candidate_posture_label": _clean_text(
                belief_state.get("promotion_candidate_posture_label"),
                default="Not recorded",
            ),
            "belief_state_promotion_candidate_posture_summary": _clean_text(
                belief_state.get("promotion_candidate_posture_summary")
            ),
            "belief_state_promotion_stability_label": _clean_text(
                belief_state.get("promotion_stability_label"),
                default="Not recorded",
            ),
            "belief_state_promotion_stability_summary": _clean_text(
                belief_state.get("promotion_stability_summary")
            ),
            "belief_state_promotion_gate_status_label": _clean_text(
                belief_state.get("promotion_gate_status_label"),
                default="Not recorded",
            ),
            "belief_state_promotion_gate_status_summary": _clean_text(
                belief_state.get("promotion_gate_status_summary")
            ),
            "belief_state_promotion_block_reason_label": _clean_text(
                belief_state.get("promotion_block_reason_label"),
                default="Not recorded",
            ),
            "belief_state_promotion_block_reason_summary": _clean_text(
                belief_state.get("promotion_block_reason_summary")
            ),
            "belief_state_trust_tier_label": _clean_text(
                belief_state.get("trust_tier_label"),
                default="Not recorded",
            ),
            "belief_state_trust_tier_summary": _clean_text(
                belief_state.get("trust_tier_summary")
            ),
            "belief_state_provenance_confidence_label": _clean_text(
                belief_state.get("provenance_confidence_label"),
                default="Not recorded",
            ),
            "belief_state_provenance_confidence_summary": _clean_text(
                belief_state.get("provenance_confidence_summary")
            ),
            "belief_state_governed_review_status_label": _clean_text(
                belief_state.get("governed_review_status_label"),
                default="Not recorded",
            ),
            "belief_state_governed_review_status_summary": _clean_text(
                belief_state.get("governed_review_status_summary")
            ),
            "belief_state_governed_review_reason_label": _clean_text(
                belief_state.get("governed_review_reason_label"),
                default="Not recorded",
            ),
            "belief_state_governed_review_reason_summary": _clean_text(
                belief_state.get("governed_review_reason_summary")
            ),
            "belief_state_governed_review_record_count": int(
                belief_state.get("governed_review_record_count") or 0
            ),
            "belief_state_governed_review_history_summary": _clean_text(
                belief_state.get("governed_review_history_summary")
            ),
            "belief_state_promotion_audit_summary": _clean_text(
                belief_state.get("promotion_audit_summary")
            ),
            "belief_state_effective_governed_review_origin_label": _clean_text(
                belief_state.get("effective_governed_review_origin_label"),
                default="derived",
            ),
            "belief_state_effective_governed_review_origin_summary": _clean_text(
                belief_state.get("effective_governed_review_origin_summary")
            ),
            "belief_state_derived_governed_review_status_label": _clean_text(
                belief_state.get("derived_governed_review_status_label"),
                default="Not recorded",
            ),
            "belief_state_manual_governed_review_status_label": _clean_text(
                belief_state.get("manual_governed_review_status_label"),
                default="Not recorded",
            ),
            "belief_state_manual_governed_review_action_label": _clean_text(
                belief_state.get("manual_governed_review_action_label")
            ),
            "belief_state_manual_governed_review_reviewer_label": _clean_text(
                belief_state.get("manual_governed_review_reviewer_label")
            ),
            "belief_state_continuity_cluster_review_status_label": _clean_text(
                belief_state.get("continuity_cluster_review_status_label"),
                default="Not recorded",
            ),
            "belief_state_continuity_cluster_review_status_summary": _clean_text(
                belief_state.get("continuity_cluster_review_status_summary")
            ),
            "belief_state_continuity_cluster_review_reason_label": _clean_text(
                belief_state.get("continuity_cluster_review_reason_label"),
                default="Not recorded",
            ),
            "belief_state_continuity_cluster_review_reason_summary": _clean_text(
                belief_state.get("continuity_cluster_review_reason_summary")
            ),
            "belief_state_continuity_cluster_review_record_count": int(
                belief_state.get("continuity_cluster_review_record_count") or 0
            ),
            "belief_state_continuity_cluster_review_history_summary": _clean_text(
                belief_state.get("continuity_cluster_review_history_summary")
            ),
            "belief_state_continuity_cluster_promotion_audit_summary": _clean_text(
                belief_state.get("continuity_cluster_promotion_audit_summary")
            ),
            "belief_state_continuity_cluster_effective_review_origin_label": _clean_text(
                belief_state.get("continuity_cluster_effective_review_origin_label"),
                default="derived",
            ),
            "belief_state_continuity_cluster_effective_review_origin_summary": _clean_text(
                belief_state.get("continuity_cluster_effective_review_origin_summary")
            ),
            "belief_state_continuity_cluster_derived_review_status_label": _clean_text(
                belief_state.get("continuity_cluster_derived_review_status_label"),
                default="Not recorded",
            ),
            "belief_state_continuity_cluster_manual_review_status_label": _clean_text(
                belief_state.get("continuity_cluster_manual_review_status_label"),
                default="Not recorded",
            ),
            "belief_state_continuity_cluster_manual_review_action_label": _clean_text(
                belief_state.get("continuity_cluster_manual_review_action_label")
            ),
            "belief_state_continuity_cluster_manual_review_reviewer_label": _clean_text(
                belief_state.get("continuity_cluster_manual_review_reviewer_label")
            ),
            "belief_state_carryover_guardrail_summary": _clean_text(
                belief_state.get("carryover_guardrail_summary")
            ),
            "belief_update_chronology_label": _clean_text(
                belief_updates.get("chronology_mix_label"),
                default="Not recorded",
            ),
            "belief_update_chronology_summary": _clean_text(
                belief_updates.get("chronology_summary_text")
            ),
            "belief_update_support_basis_label": _clean_text(
                belief_updates.get("support_basis_mix_label"),
                default="Not recorded",
            ),
            "belief_update_support_basis_summary": _clean_text(
                belief_updates.get("support_basis_mix_summary")
            ),
            "belief_update_support_quality_label": _clean_text(
                belief_updates.get("support_quality_label"),
                default="Not recorded",
            ),
            "belief_update_support_quality_summary": _clean_text(
                belief_updates.get("support_quality_summary")
            ),
            "belief_update_governed_support_posture_label": _clean_text(
                belief_updates.get("governed_support_posture_label"),
                default="Not recorded",
            ),
            "belief_update_governed_support_posture_summary": _clean_text(
                belief_updates.get("governed_support_posture_summary")
            ),
            "belief_update_support_coherence_label": _clean_text(
                belief_updates.get("support_coherence_label"),
                default="Not recorded",
            ),
            "belief_update_support_coherence_summary": _clean_text(
                belief_updates.get("support_coherence_summary")
            ),
            "belief_update_support_reuse_label": _clean_text(
                belief_updates.get("support_reuse_label"),
                default="Not recorded",
            ),
            "belief_update_support_reuse_summary": _clean_text(
                belief_updates.get("support_reuse_summary")
            ),
            "scientific_decision_status_label": _clean_text(
                scientific_decision_summary.get("decision_status_label"),
                default="Not recorded",
            ),
            "scientific_decision_status_summary": _clean_text(
                scientific_decision_summary.get("decision_status_summary")
            ),
            "scientific_decision_current_support_quality_label": _clean_text(
                scientific_decision_summary.get("current_support_quality_label"),
                default="Not recorded",
            ),
            "scientific_decision_current_support_quality_summary": _clean_text(
                scientific_decision_summary.get("current_support_quality_summary")
            ),
            "scientific_decision_current_governed_support_posture_label": _clean_text(
                scientific_decision_summary.get("current_governed_support_posture_label"),
                default="Not recorded",
            ),
            "scientific_decision_current_governed_support_posture_summary": _clean_text(
                scientific_decision_summary.get("current_governed_support_posture_summary")
            ),
            "scientific_decision_current_support_coherence_label": _clean_text(
                scientific_decision_summary.get("current_support_coherence_label"),
                default="Not recorded",
            ),
            "scientific_decision_current_support_coherence_summary": _clean_text(
                scientific_decision_summary.get("current_support_coherence_summary")
            ),
            "scientific_decision_current_support_reuse_label": _clean_text(
                scientific_decision_summary.get("current_support_reuse_label"),
                default="Not recorded",
            ),
            "scientific_decision_current_support_reuse_summary": _clean_text(
                scientific_decision_summary.get("current_support_reuse_summary")
            ),
            "scientific_decision_broader_governed_reuse_label": _clean_text(
                scientific_decision_summary.get("broader_governed_reuse_label"),
                default="Not recorded",
            ),
            "scientific_decision_broader_governed_reuse_summary": _clean_text(
                scientific_decision_summary.get("broader_governed_reuse_summary")
            ),
            "scientific_decision_broader_continuity_label": _clean_text(
                scientific_decision_summary.get("broader_continuity_label"),
                default="Not recorded",
            ),
            "scientific_decision_broader_continuity_summary": _clean_text(
                scientific_decision_summary.get("broader_continuity_summary")
            ),
            "scientific_decision_future_reuse_candidacy_label": _clean_text(
                scientific_decision_summary.get("future_reuse_candidacy_label"),
                default="Not recorded",
            ),
            "scientific_decision_future_reuse_candidacy_summary": _clean_text(
                scientific_decision_summary.get("future_reuse_candidacy_summary")
            ),
            "scientific_decision_continuity_cluster_posture_label": _clean_text(
                scientific_decision_summary.get("continuity_cluster_posture_label"),
                default="Not recorded",
            ),
            "scientific_decision_continuity_cluster_posture_summary": _clean_text(
                scientific_decision_summary.get("continuity_cluster_posture_summary")
            ),
            "scientific_decision_promotion_candidate_posture_label": _clean_text(
                scientific_decision_summary.get("promotion_candidate_posture_label"),
                default="Not recorded",
            ),
            "scientific_decision_promotion_candidate_posture_summary": _clean_text(
                scientific_decision_summary.get("promotion_candidate_posture_summary")
            ),
            "scientific_decision_promotion_stability_label": _clean_text(
                scientific_decision_summary.get("promotion_stability_label"),
                default="Not recorded",
            ),
            "scientific_decision_promotion_stability_summary": _clean_text(
                scientific_decision_summary.get("promotion_stability_summary")
            ),
            "scientific_decision_promotion_gate_status_label": _clean_text(
                scientific_decision_summary.get("promotion_gate_status_label"),
                default="Not recorded",
            ),
            "scientific_decision_promotion_gate_status_summary": _clean_text(
                scientific_decision_summary.get("promotion_gate_status_summary")
            ),
            "scientific_decision_promotion_block_reason_label": _clean_text(
                scientific_decision_summary.get("promotion_block_reason_label"),
                default="Not recorded",
            ),
            "scientific_decision_promotion_block_reason_summary": _clean_text(
                scientific_decision_summary.get("promotion_block_reason_summary")
            ),
            "scientific_decision_trust_tier_label": _clean_text(
                scientific_decision_summary.get("trust_tier_label"),
                default="Not recorded",
            ),
            "scientific_decision_trust_tier_summary": _clean_text(
                scientific_decision_summary.get("trust_tier_summary")
            ),
            "scientific_decision_provenance_confidence_label": _clean_text(
                scientific_decision_summary.get("provenance_confidence_label"),
                default="Not recorded",
            ),
            "scientific_decision_provenance_confidence_summary": _clean_text(
                scientific_decision_summary.get("provenance_confidence_summary")
            ),
            "scientific_decision_governed_review_status_label": _clean_text(
                scientific_decision_summary.get("governed_review_status_label"),
                default="Not recorded",
            ),
            "scientific_decision_governed_review_status_summary": _clean_text(
                scientific_decision_summary.get("governed_review_status_summary")
            ),
            "scientific_decision_governed_review_reason_label": _clean_text(
                scientific_decision_summary.get("governed_review_reason_label"),
                default="Not recorded",
            ),
            "scientific_decision_governed_review_reason_summary": _clean_text(
                scientific_decision_summary.get("governed_review_reason_summary")
            ),
            "scientific_decision_session_family_review_status_label": _clean_text(
                scientific_decision_summary.get("session_family_review_status_label"),
                default="Not recorded",
            ),
            "scientific_decision_session_family_review_status_summary": _clean_text(
                scientific_decision_summary.get("session_family_review_status_summary")
            ),
            "scientific_decision_session_family_review_reason_label": _clean_text(
                scientific_decision_summary.get("session_family_review_reason_label"),
                default="Not recorded",
            ),
            "scientific_decision_session_family_review_reason_summary": _clean_text(
                scientific_decision_summary.get("session_family_review_reason_summary")
            ),
            "scientific_decision_session_family_review_record_count": int(
                scientific_decision_summary.get("session_family_review_record_count") or 0
            ),
            "scientific_decision_session_family_review_history_summary": _clean_text(
                scientific_decision_summary.get("session_family_review_history_summary")
            ),
            "scientific_decision_session_family_promotion_audit_summary": _clean_text(
                scientific_decision_summary.get("session_family_promotion_audit_summary")
            ),
            "scientific_decision_session_family_effective_review_origin_label": _clean_text(
                scientific_decision_summary.get("session_family_effective_review_origin_label"),
                default="derived",
            ),
            "scientific_decision_session_family_effective_review_origin_summary": _clean_text(
                scientific_decision_summary.get("session_family_effective_review_origin_summary")
            ),
            "scientific_decision_session_family_derived_review_status_label": _clean_text(
                scientific_decision_summary.get("session_family_derived_review_status_label"),
                default="Not recorded",
            ),
            "scientific_decision_session_family_manual_review_status_label": _clean_text(
                scientific_decision_summary.get("session_family_manual_review_status_label"),
                default="Not recorded",
            ),
            "scientific_decision_session_family_manual_review_action_label": _clean_text(
                scientific_decision_summary.get("session_family_manual_review_action_label")
            ),
            "scientific_decision_session_family_manual_review_reviewer_label": _clean_text(
                scientific_decision_summary.get("session_family_manual_review_reviewer_label")
            ),
            "governance_attention_label": _clean_text(
                governance_summary.get("priority_label"),
                default="Not recorded",
            ),
            "governance_attention_summary": _clean_text(governance_summary.get("attention_summary")),
            "governance_item_count": int(governance_summary.get("item_count") or 0),
            "governance_manual_override_count": int(governance_summary.get("manual_override_count") or 0),
            "governance_manual_mismatch_count": int(governance_summary.get("manual_mismatch_count") or 0),
            "governance_detail_url": _clean_text(governance_summary.get("detail_url")),
            "predictive_path_summary": _clean_text(predictive_path_summary.get("summary_text")),
            "predictive_task_summary": _clean_text(
                ((predictive_path_summary.get("task_contract") or {}) if isinstance(predictive_path_summary.get("task_contract"), dict) else {}).get("task_summary")
            ),
            "predictive_model_signal_summary": _clean_text(predictive_path_summary.get("model_signal_summary")),
            "predictive_path_heuristic_summary": _clean_text(predictive_path_summary.get("heuristic_logic_summary")),
            "predictive_representation_summary": _clean_text(
                ((predictive_path_summary.get("representation_summary") or {}) if isinstance(predictive_path_summary.get("representation_summary"), dict) else {}).get("representation_limitations_summary")
            ),
            "predictive_evaluation_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("evaluation_summary")
            ),
            "predictive_separation_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("candidate_separation_summary")
            ),
            "predictive_stability_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("ranking_stability_summary")
            ),
            "predictive_closeness_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("closeness_band_summary")
            ),
            "predictive_top_k_quality_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("top_k_quality_summary")
            ),
            "predictive_calibration_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("calibration_awareness_summary")
            ),
            "predictive_calibration_band_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("calibration_band_summary")
            ),
            "predictive_variation_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("session_variation_summary")
            ),
            "predictive_cross_session_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("cross_session_comparison_summary")
            ),
            "predictive_comparison_cohort_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("comparison_cohort_summary")
            ),
            "predictive_cohort_diagnostic_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("cohort_diagnostic_summary")
            ),
            "predictive_evaluation_subset_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("evaluation_subset_summary")
            ),
            "predictive_representation_evaluation_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("representation_evaluation_summary")
            ),
            "predictive_representation_condition_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("representation_condition_summary")
            ),
            "predictive_cross_run_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("cross_run_comparison_summary")
            ),
            "predictive_engine_strength_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("engine_strength_summary")
            ),
            "predictive_engine_weakness_summary": _clean_text(
                ((predictive_path_summary.get("evaluation_contract") or {}) if isinstance(predictive_path_summary.get("evaluation_contract"), dict) else {}).get("engine_weakness_summary")
            ),
            "predictive_failure_mode_summary": _clean_text(
                ((predictive_path_summary.get("failure_mode_summary") or {}) if isinstance(predictive_path_summary.get("failure_mode_summary"), dict) else {}).get("summary_text")
            ),
            "scientific_decision_carryover_guardrail_summary": _clean_text(
                scientific_decision_summary.get("carryover_guardrail_summary")
            ),
            "scientific_decision_next_step_label": _clean_text(
                scientific_decision_summary.get("next_step_label"),
                default="Not recorded",
            ),
            "scientific_decision_next_step_summary": _clean_text(
                scientific_decision_summary.get("next_step_summary")
            ),
            "scientific_decision_result_state_label": _clean_text(
                scientific_decision_summary.get("result_state_label"),
                default="Not recorded",
            ),
            "scientific_decision_result_state_summary": _clean_text(
                scientific_decision_summary.get("result_state_summary")
            ),
            "session_support_role_label": session_support_role_label,
            "session_support_role_summary": session_support_role_summary,
            "belief_state_accepted_updates": int(belief_state.get("accepted_update_count") or 0),
            "belief_state_proposed_updates": int(belief_state.get("proposed_update_count") or 0),
            "belief_state_superseded_updates": int(belief_state.get("superseded_update_count") or 0),
            "belief_state_observed_label_support_count": int(belief_state.get("observed_label_support_count") or 0),
            "belief_state_numeric_rule_based_support_count": int(belief_state.get("numeric_rule_based_support_count") or 0),
            "belief_state_unresolved_basis_count": int(belief_state.get("unresolved_basis_count") or 0),
            "belief_state_weak_basis_count": int(belief_state.get("weak_basis_count") or 0),
            "belief_update_observed_label_support_count": int(belief_updates.get("observed_label_support_count") or 0),
            "belief_update_numeric_rule_based_support_count": int(belief_updates.get("numeric_rule_based_support_count") or 0),
            "belief_update_unresolved_basis_count": int(belief_updates.get("unresolved_basis_count") or 0),
            "belief_update_weak_basis_count": int(belief_updates.get("weak_basis_count") or 0),
            "claims_with_active_support_count": int(claims_summary.get("claims_with_active_support_count") or 0),
            "claims_with_historical_support_only_count": int(claims_summary.get("claims_with_historical_support_only_count") or 0),
            "claims_with_no_governed_support_count": int(claims_summary.get("claims_with_no_governed_support_count") or 0),
            "claims_continuity_aligned_count": int(claims_summary.get("continuity_aligned_claim_count") or 0),
            "claims_new_context_count": int(claims_summary.get("new_claim_context_count") or 0),
            "claims_weak_prior_alignment_count": int(claims_summary.get("weak_prior_alignment_count") or 0),
            "claims_no_prior_context_count": int(claims_summary.get("no_prior_claim_context_count") or 0),
            "claims_active_governed_continuity_count": int(
                claims_summary.get("claims_with_active_governed_continuity_count") or 0
            ),
            "claims_tentative_active_continuity_count": int(
                claims_summary.get("claims_with_tentative_active_continuity_count") or 0
            ),
            "claims_historical_continuity_only_count": int(
                claims_summary.get("claims_with_historical_continuity_only_count") or 0
            ),
            "claims_sparse_prior_context_count": int(claims_summary.get("claims_with_sparse_prior_context_count") or 0),
            "claims_no_useful_prior_context_count": int(
                claims_summary.get("claims_with_no_useful_prior_context_count") or 0
            ),
            "claims_chronology_summary": _clean_text(claims_summary.get("chronology_summary_text")),
            "claims_broader_reuse_label": _clean_text(
                claims_summary.get("broader_reuse_label"),
                default="Not recorded",
            ),
            "claims_broader_reuse_summary": _clean_text(
                claims_summary.get("broader_reuse_summary_text")
            ),
            "claims_broader_continuity_label": _clean_text(
                claims_summary.get("broader_continuity_label"),
                default="Not recorded",
            ),
            "claims_broader_continuity_summary": _clean_text(
                claims_summary.get("broader_continuity_summary_text")
            ),
            "claims_future_reuse_candidacy_label": _clean_text(
                claims_summary.get("future_reuse_candidacy_label"),
                default="Not recorded",
            ),
            "claims_future_reuse_candidacy_summary": _clean_text(
                claims_summary.get("future_reuse_candidacy_summary_text")
            ),
            "claims_continuity_cluster_posture_label": _clean_text(
                claims_summary.get("continuity_cluster_posture_label"),
                default="Not recorded",
            ),
            "claims_continuity_cluster_posture_summary": _clean_text(
                claims_summary.get("continuity_cluster_posture_summary_text")
            ),
            "claims_promotion_candidate_posture_label": _clean_text(
                claims_summary.get("promotion_candidate_posture_label"),
                default="Not recorded",
            ),
            "claims_promotion_candidate_posture_summary": _clean_text(
                claims_summary.get("promotion_candidate_posture_summary_text")
            ),
            "claims_promotion_stability_label": _clean_text(
                claims_summary.get("promotion_stability_label"),
                default="Not recorded",
            ),
            "claims_promotion_stability_summary": _clean_text(
                claims_summary.get("promotion_stability_summary_text")
            ),
            "claims_promotion_gate_status_label": _clean_text(
                claims_summary.get("promotion_gate_status_label"),
                default="Not recorded",
            ),
            "claims_promotion_gate_status_summary": _clean_text(
                claims_summary.get("promotion_gate_status_summary_text")
            ),
            "claims_promotion_block_reason_label": _clean_text(
                claims_summary.get("promotion_block_reason_label"),
                default="Not recorded",
            ),
            "claims_promotion_block_reason_summary": _clean_text(
                claims_summary.get("promotion_block_reason_summary_text")
            ),
            "claims_source_class_label": _clean_text(
                claims_summary.get("source_class_label"),
                default="Not recorded",
            ),
            "claims_source_class_summary": _clean_text(
                claims_summary.get("source_class_summary_text")
            ),
            "claims_trust_tier_label": _clean_text(
                claims_summary.get("trust_tier_label"),
                default="Not recorded",
            ),
            "claims_trust_tier_summary": _clean_text(
                claims_summary.get("trust_tier_summary_text")
            ),
            "claims_provenance_confidence_label": _clean_text(
                claims_summary.get("provenance_confidence_label"),
                default="Not recorded",
            ),
            "claims_provenance_confidence_summary": _clean_text(
                claims_summary.get("provenance_confidence_summary_text")
            ),
            "claims_governed_review_status_label": _clean_text(
                claims_summary.get("governed_review_status_label"),
                default="Not recorded",
            ),
            "claims_governed_review_status_summary": _clean_text(
                claims_summary.get("governed_review_status_summary_text")
            ),
            "claims_governed_review_reason_label": _clean_text(
                claims_summary.get("governed_review_reason_label"),
                default="Not recorded",
            ),
            "claims_governed_review_reason_summary": _clean_text(
                claims_summary.get("governed_review_reason_summary_text")
            ),
            "claims_governed_review_record_count": int(
                claims_summary.get("governed_review_record_count") or 0
            ),
            "claims_governed_review_history_summary": _clean_text(
                claims_summary.get("governed_review_history_summary_text")
            ),
            "claims_promotion_audit_summary": _clean_text(
                claims_summary.get("promotion_audit_summary_text")
            ),
            "claims_support_basis_summary": _clean_text(claims_summary.get("claim_support_basis_summary_text")),
            "claims_actionability_summary": _clean_text(claims_summary.get("claim_actionability_summary_text")),
            "claims_actionability_basis_summary": _clean_text(
                claims_summary.get("claim_actionability_basis_summary_text")
            ),
            "claims_observed_label_grounded_count": int(
                claims_summary.get("claims_mostly_observed_label_grounded_count") or 0
            ),
            "claims_numeric_rule_based_support_count": int(
                claims_summary.get("claims_with_numeric_rule_based_support_count") or 0
            ),
            "claims_weak_basis_support_count": int(
                claims_summary.get("claims_with_weak_basis_support_count") or 0
            ),
            "claims_mixed_support_basis_count": int(
                claims_summary.get("claims_with_mixed_support_basis_count") or 0
            ),
            "claims_decision_useful_active_support_count": int(
                claims_summary.get("claims_with_decision_useful_active_support_count") or 0
            ),
            "claims_limited_active_support_quality_count": int(
                claims_summary.get("claims_with_limited_active_support_quality_count") or 0
            ),
            "claims_context_limited_active_support_count": int(
                claims_summary.get("claims_with_context_limited_active_support_count") or 0
            ),
            "claims_weak_or_unresolved_active_support_count": int(
                claims_summary.get("claims_with_weak_or_unresolved_active_support_count") or 0
            ),
            "claims_posture_governing_support_count": int(
                claims_summary.get("claims_with_posture_governing_support_count") or 0
            ),
            "claims_tentative_current_support_count": int(
                claims_summary.get("claims_with_tentative_current_support_count") or 0
            ),
            "claims_accepted_limited_support_count": int(
                claims_summary.get("claims_with_accepted_limited_support_count") or 0
            ),
            "claims_historical_non_governing_support_count": int(
                claims_summary.get("claims_with_historical_non_governing_support_count") or 0
            ),
            "claims_contested_current_support_count": int(
                claims_summary.get("claims_with_contested_current_support_count") or 0
            ),
            "claims_degraded_current_posture_count": int(
                claims_summary.get("claims_with_degraded_current_posture_count") or 0
            ),
            "claims_historical_stronger_than_current_count": int(
                claims_summary.get("claims_with_historical_stronger_than_current_count") or 0
            ),
            "claims_contradiction_limited_reuse_count": int(
                claims_summary.get("claims_with_contradiction_limited_reuse_count") or 0
            ),
            "claims_weakly_reusable_support_count": int(
                claims_summary.get("claims_with_weakly_reusable_support_count") or 0
            ),
            "claims_action_ready_follow_up_count": int(
                claims_summary.get("claims_action_ready_follow_up_count") or 0
            ),
            "claims_need_stronger_evidence_count": int(
                claims_summary.get("claims_promising_but_need_stronger_evidence_count") or 0
            ),
            "claims_need_clarifying_experiment_count": int(
                claims_summary.get("claims_need_clarifying_experiment_count") or 0
            ),
            "claims_do_not_prioritize_yet_count": int(
                claims_summary.get("claims_do_not_prioritize_yet_count") or 0
            ),
            "claims_insufficient_governed_basis_count": int(
                claims_summary.get("claims_with_insufficient_governed_basis_count") or 0
            ),
            "claims_action_ready_from_active_support_count": int(
                claims_summary.get("claims_action_ready_from_active_support_count") or 0
            ),
            "claims_active_but_limited_actionability_count": int(
                claims_summary.get("claims_with_active_but_limited_actionability_count") or 0
            ),
            "claims_historically_interesting_count": int(
                claims_summary.get("claims_historically_interesting_count") or 0
            ),
            "claims_mixed_current_historical_actionability_count": int(
                claims_summary.get("claims_with_mixed_current_historical_actionability_count") or 0
            ),
            "claims_no_active_governed_support_actionability_count": int(
                claims_summary.get("claims_with_no_active_governed_support_actionability_count") or 0
            ),
            "claims_read_across_summary": _claims_read_across_summary(item),
            "recommendation_reuse_active": _as_bool(controlled_reuse.get("recommendation_reuse_active")),
            "ranking_context_reuse_active": _as_bool(controlled_reuse.get("ranking_context_reuse_active")),
            "interpretation_support_active": _as_bool(controlled_reuse.get("interpretation_support_active")),
            "future_activation_summary": _join_compact(
                _clean_list(evidence_loop.get("future_activation_candidates")),
                default="None recorded",
            ),
            "comparison_ready_label": "Comparison-ready" if _as_bool(anchors.get("comparison_ready")) else "Partial basis",
            "bridge_state_summary": _clean_text(bridge_state_notes[0] if bridge_state_notes else ""),
            "results_ready": bool(item.get("results_ready")),
            "discovery_url": item.get("discovery_url") or "",
            "dashboard_url": item.get("dashboard_url") or "",
        }

    focus_row = _row_for_item(focus_session, None, is_focus=True)
    comparison_rows: list[dict[str, Any]] = []
    counts = {
        "directly_comparable": 0,
        "partially_comparable": 0,
        "not_comparable": 0,
    }

    for item in items:
        if item is focus_session:
            continue
        comparison = compare_session_basis(
            focus_session=focus_session,
            candidate_session=item,
        )
        counts[comparison["status"]] += 1
        comparison_rows.append(_row_for_item(item, comparison, is_focus=False))

    comparison_rows.sort(
        key=lambda row: (
            _comparison_rank((row.get("comparison") or {}).get("status") or ""),
            0 if row.get("results_ready") else 1,
            row.get("source_name") or "",
        )
    )

    return {
        "focus_session_id": focus_session.get("session_id") or "",
        "focus_basis_label": _comparison_basis_label(focus_session),
        "focus_basis_source_label": _basis_source_label(focus_session),
        "focus_activation_boundary_summary": _activation_boundary_summary(focus_session),
        "rows": [focus_row, *comparison_rows],
        "counts": counts,
    }


__all__ = [
    "build_candidate_preview",
    "build_session_comparison_matrix",
    "build_session_comparison_overview",
    "compare_session_basis",
]
