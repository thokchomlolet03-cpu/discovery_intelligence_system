from __future__ import annotations

from typing import Any

from system.services.run_metadata_service import comparison_anchor_summary


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
        "differences": differences[:5],
        "outcome_differences": outcome_differences[:5],
        "candidate_comparison_summary": candidate_comparison.get("summary") or "",
        "candidate_differences": candidate_comparison.get("differences") or [],
        "cautions": cautions[:6],
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
            "recommendation_reuse_summary": _recommendation_reuse_summary(item),
            "future_ranking_context_summary": _future_ranking_context_summary(item),
            "future_learning_eligibility_summary": _future_learning_eligibility_summary(item),
            "permanently_non_active_summary": _permanently_non_active_summary(item),
            "controlled_reuse_summary": _controlled_reuse_summary(item),
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
