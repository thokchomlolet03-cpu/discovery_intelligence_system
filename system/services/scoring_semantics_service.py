from __future__ import annotations

from typing import Any

import pandas as pd

from system.contracts import validate_candidate_score_semantics


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(0.0, min(1.0, numeric))


def _target_kind(
    *,
    target_definition: dict[str, Any] | None,
    modeling_mode: str | None,
) -> str:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    return str(target_definition.get("target_kind") or modeling_mode or "classification").strip().lower() or "classification"


def _raw_signal_label(*, target_kind: str) -> str:
    return "Ranking compatibility" if target_kind == "regression" else "Predictive signal"


def _raw_signal_from_candidate(candidate: dict[str, Any], *, target_kind: str) -> float:
    explicit = _safe_float(candidate.get("raw_predictive_signal"))
    if explicit is not None:
        return _clamp_score(explicit)

    confidence = _clamp_score(candidate.get("confidence"))
    signal_support = _safe_float(candidate.get("signal_support"))
    if signal_support is None:
        signal_support = 1.0 - _clamp_score(candidate.get("uncertainty"))
    if target_kind == "regression":
        return _clamp_score((0.8 * confidence) + (0.2 * signal_support))
    return _clamp_score((0.72 * confidence) + (0.28 * signal_support))


def _representation_support_from_similarity(max_similarity: Any, support_density: Any) -> tuple[float, str, list[str]]:
    similarity = _safe_float(max_similarity)
    density = _safe_float(support_density)
    if similarity is None and density is None:
        return (
            0.97,
            "Representation support is slightly reduced because chemistry coverage diagnostics were not fully recorded for this candidate.",
            ["representation_coverage_missing"],
        )

    similarity = 0.0 if similarity is None else similarity
    density = similarity if density is None else density
    weakest_support = min(similarity, density)
    if weakest_support < 0.2:
        return (
            0.80,
            "Representation support is strongly reduced because both local similarity support and neighborhood density are weak.",
            ["representation_out_of_domain"],
        )
    if weakest_support < 0.35 or similarity < 0.25:
        return (
            0.88,
            "Representation support is reduced because the candidate sits near thin chemistry coverage even if some local support exists.",
            ["representation_edge_of_domain"],
        )
    if weakest_support < 0.5:
        return (
            0.94,
            "Representation support is mildly reduced because chemistry support is present but still thinner than the strongest covered regions.",
            ["representation_boundary_support"],
        )
    return (
        1.0,
        "Representation support does not reduce the current score because the candidate remains within stronger chemistry coverage.",
        [],
    )


def _signal_weight_from_bundle(bundle: dict[str, Any] | None, *, target_kind: str) -> float:
    bundle = bundle if isinstance(bundle, dict) else {}
    training_scope = _clean_text(bundle.get("training_scope")).lower()
    metrics = bundle.get("metrics") if isinstance(bundle.get("metrics"), dict) else {}
    holdout = metrics.get("holdout") if isinstance(metrics.get("holdout"), dict) else {}

    if training_scope == "baseline_bundle":
        base_weight = 0.44
    else:
        base_weight = 0.60 if target_kind == "regression" else 0.64

    if target_kind == "regression":
        spearman = _safe_float(holdout.get("spearman_rank_correlation"))
        if spearman is not None:
            if spearman >= 0.45:
                base_weight += 0.08
            elif spearman < 0.2:
                base_weight -= 0.08
    else:
        balanced_accuracy = _safe_float(holdout.get("balanced_accuracy"))
        brier = _safe_float(holdout.get("brier_score"))
        if balanced_accuracy is not None:
            if balanced_accuracy >= 0.68:
                base_weight += 0.08
            elif balanced_accuracy < 0.58:
                base_weight -= 0.08
        if brier is not None and brier > 0.24:
            base_weight -= 0.04

    return max(0.35, min(0.78, base_weight))


def _bounded_closeness_from_gap(neighbor_gap: Any) -> float:
    gap = _safe_float(neighbor_gap)
    if gap is None:
        return 0.55
    if gap >= 0.08:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (gap / 0.08)))


def _series_mean(series: pd.Series | None) -> float | None:
    if series is None:
        return None
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.mean())


def _series_share(mask: pd.Series | None) -> float:
    if mask is None:
        return 0.0
    numeric = pd.Series(mask).fillna(False)
    if numeric.empty:
        return 0.0
    return float(numeric.astype(bool).mean())


def _cohort_diagnostic_label(
    *,
    mean_representation_support: float | None,
    mean_neighbor_gap: float | None,
    too_close_rate: float,
    mean_raw_signal_weight: float | None,
) -> str:
    if mean_representation_support is not None and mean_representation_support < 0.88:
        return "representation-limited"
    if too_close_rate >= 0.4 or (mean_neighbor_gap is not None and mean_neighbor_gap < 0.02):
        return "weakly separated"
    if mean_raw_signal_weight is not None and mean_raw_signal_weight < 0.55:
        return "policy-shaped"
    return "more reusable"


def _build_cohort_record(
    *,
    key: str,
    label: str,
    subset: pd.DataFrame,
    total_count: int,
) -> dict[str, Any] | None:
    if subset is None or subset.empty:
        return None

    count = int(len(subset))
    final_score = pd.to_numeric(subset.get("priority_score", 0.0), errors="coerce").fillna(0.0)
    raw_signal = pd.to_numeric(subset.get("raw_predictive_signal", 0.0), errors="coerce").fillna(0.0)
    representation_support = pd.to_numeric(subset.get("representation_support_factor", 1.0), errors="coerce").fillna(1.0)
    raw_signal_weight = pd.to_numeric(subset.get("raw_signal_weight", 0.5), errors="coerce").fillna(0.5)
    neighbor_gap = pd.to_numeric(subset.get("neighbor_gap", None), errors="coerce")
    bounded_uncertainty = pd.to_numeric(subset.get("bounded_uncertainty_score", subset.get("uncertainty", 0.0)), errors="coerce").fillna(0.0)
    fragility = pd.to_numeric(subset.get("fragility_score", subset.get("bounded_uncertainty_score", subset.get("uncertainty", 0.0))), errors="coerce").fillna(0.0)
    heuristic_delta = pd.to_numeric(subset.get("heuristic_adjustment_delta", 0.0), errors="coerce").fillna(0.0)

    mean_neighbor_gap = _series_mean(neighbor_gap)
    too_close_rate = float((neighbor_gap.dropna() < 0.015).mean()) if neighbor_gap.notna().any() else 0.0
    weak_band_rate = float((neighbor_gap.dropna() < 0.035).mean()) if neighbor_gap.notna().any() else 0.0
    mean_representation_support = _series_mean(representation_support)
    mean_raw_signal_weight = _series_mean(raw_signal_weight)
    diagnostic_label = _cohort_diagnostic_label(
        mean_representation_support=mean_representation_support,
        mean_neighbor_gap=mean_neighbor_gap,
        too_close_rate=too_close_rate,
        mean_raw_signal_weight=mean_raw_signal_weight,
    )

    summary = (
        f"{label} covers {count}/{max(total_count, 1)} candidates ({(count / max(total_count, 1)) * 100:.1f}%). "
        f"Mean raw signal is {float(raw_signal.mean()):.3f}, mean final priority is {float(final_score.mean()):.3f}, "
        f"and mean bounded uncertainty is {float(bounded_uncertainty.mean()):.3f}. "
    )
    if diagnostic_label == "representation-limited":
        summary += "This subset is representation-limited, so read ranking quality cautiously."
    elif diagnostic_label == "weakly separated":
        summary += "This subset remains weakly separated, so nearby candidates are difficult to rank confidently."
    elif diagnostic_label == "policy-shaped":
        summary += "This subset is still more policy-shaped than signal-led."
    else:
        summary += "This subset is a better reusable comparison anchor than the weakest shortlist bands."

    return {
        "key": key,
        "label": label,
        "count": count,
        "share": count / max(total_count, 1),
        "comparison_ready": count >= 3,
        "diagnostic_label": diagnostic_label,
        "mean_raw_signal": float(raw_signal.mean()),
        "mean_final_priority": float(final_score.mean()),
        "mean_uncertainty": float(bounded_uncertainty.mean()),
        "mean_fragility": float(fragility.mean()),
        "mean_representation_support": mean_representation_support,
        "mean_raw_signal_weight": mean_raw_signal_weight,
        "mean_heuristic_shift": float(heuristic_delta.abs().mean()),
        "mean_neighbor_gap": mean_neighbor_gap,
        "too_close_rate": too_close_rate,
        "weak_band_rate": weak_band_rate,
        "summary": summary,
    }


def _build_comparison_cohorts(scored: pd.DataFrame) -> list[dict[str, Any]]:
    if scored is None or scored.empty:
        return []

    total_count = int(len(scored))
    ordered = scored.sort_values("priority_score", ascending=False)
    top_count = max(1, min(5, total_count))
    representation_support = pd.to_numeric(scored.get("representation_support_factor", 1.0), errors="coerce").fillna(1.0)
    raw_signal_weight = pd.to_numeric(scored.get("raw_signal_weight", 0.5), errors="coerce").fillna(0.5)
    heuristic_delta = pd.to_numeric(scored.get("heuristic_adjustment_delta", 0.0), errors="coerce").fillna(0.0)
    neighbor_gap = pd.to_numeric(scored.get("neighbor_gap", None), errors="coerce")

    cohort_specs = [
        ("top_shortlist", "Top shortlist", ordered.head(top_count)),
        ("representation_supported", "Representation-supported cohort", scored[representation_support >= 0.94]),
        ("representation_limited", "Representation-limited cohort", scored[representation_support < 0.90]),
        ("signal_led", "Signal-led cohort", scored[(raw_signal_weight >= 0.60) & (heuristic_delta.abs() < 0.12)]),
        ("heuristic_heavy", "Heuristic-heavy cohort", scored[(raw_signal_weight < 0.55) | (heuristic_delta.abs() >= 0.15)]),
        ("fragile_band", "Fragile shortlist band", scored[(neighbor_gap < 0.035) | (representation_support < 0.88)]),
    ]
    cohorts: list[dict[str, Any]] = []
    for key, label, subset in cohort_specs:
        record = _build_cohort_record(key=key, label=label, subset=subset, total_count=total_count)
        if record:
            cohorts.append(record)
    return cohorts


def _representation_evaluation_summary(comparison_cohorts: list[dict[str, Any]]) -> str:
    supported = next((item for item in comparison_cohorts if item.get("key") == "representation_supported"), None)
    limited = next((item for item in comparison_cohorts if item.get("key") == "representation_limited"), None)
    if not supported or not limited:
        return (
            "Representation-aware evaluation evidence is still limited because the current run does not contain enough reusable supported-versus-limited cohorts."
        )

    supported_gap = _safe_float(supported.get("mean_neighbor_gap"))
    limited_gap = _safe_float(limited.get("mean_neighbor_gap"))
    supported_uncertainty = _safe_float(supported.get("mean_uncertainty"), default=0.0) or 0.0
    limited_uncertainty = _safe_float(limited.get("mean_uncertainty"), default=0.0) or 0.0
    if supported_gap is not None and limited_gap is not None and supported_gap > limited_gap and limited_uncertainty > supported_uncertainty:
        return (
            f"Representation-aware evaluation suggests stronger chemistry coverage improves ranking quality in this run: supported cohorts show mean neighbor-gap {supported_gap:.3f} versus {limited_gap:.3f} for representation-limited cohorts, with lower bounded uncertainty."
        )
    if limited_uncertainty > supported_uncertainty + 0.08:
        return (
            "Representation-aware evaluation still indicates thinner chemistry coverage increases bounded uncertainty even when the shortlist remains usable."
        )
    return (
        "Representation-aware evaluation is mixed: supported and representation-limited cohorts do not yet separate cleanly enough to claim stronger ranking reliability from coverage alone."
    )


def _cohort_diagnostic_summary(comparison_cohorts: list[dict[str, Any]]) -> str:
    if not comparison_cohorts:
        return "No reusable evaluation subsets are available yet."
    fragile = next((item for item in comparison_cohorts if item.get("key") == "fragile_band"), None)
    signal_led = next((item for item in comparison_cohorts if item.get("key") == "signal_led"), None)
    heuristic_heavy = next((item for item in comparison_cohorts if item.get("key") == "heuristic_heavy"), None)
    summary_bits: list[str] = []
    if signal_led and signal_led.get("comparison_ready"):
        summary_bits.append("A reusable signal-led cohort is now available for later version comparison.")
    if heuristic_heavy and heuristic_heavy.get("count"):
        summary_bits.append("A heuristic-heavy cohort remains visible, which helps isolate where policy still carries too much ordering work.")
    if fragile and (_safe_float(fragile.get("too_close_rate"), default=0.0) or 0.0) >= 0.3:
        summary_bits.append("The fragile shortlist band remains a meaningful reusable caution subset.")
    return " ".join(summary_bits) or "Reusable evaluation subsets now exist, but none dominate this run strongly enough to summarize beyond the saved cohort records."


def _cohort_lookup(comparison_cohorts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("key")): item
        for item in comparison_cohorts
        if isinstance(item, dict) and _clean_text(item.get("key"))
    }


def _top_k_quality_summary(scored: pd.DataFrame) -> str:
    if scored is None or scored.empty:
        return "Top-k quality is not available because no scored candidates were recorded."

    ordered = scored.sort_values("priority_score", ascending=False).head(min(5, len(scored)))
    if ordered.empty:
        return "Top-k quality is not available because the shortlisted candidates are empty."

    mean_raw_signal = _series_mean(pd.to_numeric(ordered.get("raw_predictive_signal", 0.0), errors="coerce"))
    mean_uncertainty = _series_mean(
        pd.to_numeric(ordered.get("bounded_uncertainty_score", ordered.get("uncertainty", 0.0)), errors="coerce")
    )
    mean_fragility = _series_mean(
        pd.to_numeric(ordered.get("fragility_score", ordered.get("bounded_uncertainty_score", 0.0)), errors="coerce")
    )
    mean_gap = _series_mean(pd.to_numeric(ordered.get("neighbor_gap", None), errors="coerce"))
    mean_support = _series_mean(pd.to_numeric(ordered.get("representation_support_factor", 1.0), errors="coerce"))
    mean_signal_weight = _series_mean(pd.to_numeric(ordered.get("raw_signal_weight", 0.5), errors="coerce"))
    too_close_rate = _series_share(pd.to_numeric(ordered.get("neighbor_gap", None), errors="coerce") < 0.015)

    if (
        mean_gap is not None
        and mean_gap >= 0.035
        and (mean_uncertainty or 0.0) <= 0.42
        and (mean_support or 0.0) >= 0.93
        and too_close_rate < 0.2
    ):
        return (
            f"Top-k quality is stronger in this run: the lead band has mean raw signal {mean_raw_signal or 0.0:.3f}, "
            f"mean neighbor-gap {mean_gap:.3f}, mean bounded uncertainty {mean_uncertainty or 0.0:.3f}, and representation support {mean_support or 0.0:.3f}."
        )
    if too_close_rate >= 0.4 or (mean_gap is not None and mean_gap < 0.02):
        return (
            f"Top-k quality remains fragile: the lead band has mean raw signal {mean_raw_signal or 0.0:.3f}, "
            f"but mean neighbor-gap is only {mean_gap or 0.0:.3f} and {too_close_rate * 100:.1f}% of the top candidates are too close to separate strongly."
        )
    return (
        f"Top-k quality is usable but still bounded: the lead band shows mean raw signal {mean_raw_signal or 0.0:.3f}, "
        f"mean bounded uncertainty {mean_uncertainty or 0.0:.3f}, mean fragility {mean_fragility or 0.0:.3f}, "
        f"representation support {mean_support or 0.0:.3f}, and raw-signal weight {mean_signal_weight or 0.0:.3f}."
    )


def _evaluation_subset_summary(comparison_cohorts: list[dict[str, Any]]) -> str:
    if not comparison_cohorts:
        return "Reusable evaluation subsets are not available yet."

    ready = [item for item in comparison_cohorts if item.get("comparison_ready")]
    if not ready:
        return (
            "Reusable evaluation subsets were detected, but none reached enough size to act as stable comparison anchors yet."
        )

    stronger = [item.get("label") for item in ready if item.get("diagnostic_label") == "more reusable"]
    weaker = [
        item.get("label")
        for item in ready
        if item.get("diagnostic_label") in {"representation-limited", "weakly separated", "policy-shaped"}
    ]
    summary = (
        f"{len(ready)} reusable evaluation subset(s) are now recorded: "
        + ", ".join(str(item.get("label")) for item in ready[:4])
        + "."
    )
    if stronger:
        summary += f" Stronger anchors currently include {', '.join(str(label) for label in stronger[:2])}."
    if weaker:
        summary += f" Weaker anchors currently include {', '.join(str(label) for label in weaker[:2])}."
    return summary


def _representation_condition_diagnostics(comparison_cohorts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for key in ("representation_supported", "representation_limited", "fragile_band"):
        cohort = next((item for item in comparison_cohorts if item.get("key") == key), None)
        if not cohort:
            continue
        diagnostics.append(
            {
                "key": str(cohort.get("key")),
                "label": str(cohort.get("label")),
                "comparison_ready": bool(cohort.get("comparison_ready")),
                "mean_neighbor_gap": _safe_float(cohort.get("mean_neighbor_gap")),
                "mean_uncertainty": _safe_float(cohort.get("mean_uncertainty")),
                "mean_representation_support": _safe_float(cohort.get("mean_representation_support")),
                "diagnostic_label": _clean_text(cohort.get("diagnostic_label")),
                "summary": _clean_text(cohort.get("summary")),
            }
        )
    return diagnostics


def _representation_condition_summary(comparison_cohorts: list[dict[str, Any]]) -> str:
    cohorts = _cohort_lookup(comparison_cohorts)
    supported = cohorts.get("representation_supported")
    limited = cohorts.get("representation_limited")
    if not supported or not limited:
        return (
            "Representation-conditioned evaluation is still limited because the run does not yet contain both stronger-covered and thinner-covered reusable subsets."
        )

    supported_gap = _safe_float(supported.get("mean_neighbor_gap"))
    limited_gap = _safe_float(limited.get("mean_neighbor_gap"))
    supported_uncertainty = _safe_float(supported.get("mean_uncertainty"))
    limited_uncertainty = _safe_float(limited.get("mean_uncertainty"))

    if (
        supported_gap is not None
        and limited_gap is not None
        and supported_uncertainty is not None
        and limited_uncertainty is not None
        and supported_gap > limited_gap
        and limited_uncertainty > supported_uncertainty
    ):
        return (
            f"Representation-conditioned evaluation suggests stronger-covered chemistry regions are more reliable in this run: supported subsets show mean neighbor-gap {supported_gap:.3f} versus {limited_gap:.3f}, while representation-limited subsets carry higher bounded uncertainty ({limited_uncertainty:.3f} vs {supported_uncertainty:.3f})."
        )
    return (
        "Representation-conditioned evaluation is mixed: thinner-coverage subsets remain weaker, but the supported-versus-limited split is not yet strong enough to treat as a robust pattern."
    )


def _cross_session_evaluation_contract(
    *,
    comparison_cohorts: list[dict[str, Any]],
    comparison_anchors: dict[str, Any] | None,
    run_contract: dict[str, Any] | None,
    target_definition: dict[str, Any] | None,
    target_kind: str,
    feature_signature: str,
    training_scope: str,
) -> dict[str, Any]:
    comparison_anchors = comparison_anchors if isinstance(comparison_anchors, dict) else {}
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    target_definition = target_definition if isinstance(target_definition, dict) else {}

    target_name = _clean_text(comparison_anchors.get("target_name") or target_definition.get("target_name"), default="not recorded")
    decision_intent = _clean_text(comparison_anchors.get("decision_intent") or run_contract.get("decision_intent"), default="not recorded")
    modeling_mode = _clean_text(comparison_anchors.get("modeling_mode") or run_contract.get("modeling_mode"), default=target_kind)
    scoring_mode = _clean_text(comparison_anchors.get("scoring_mode") or run_contract.get("scoring_mode"), default="not recorded")
    reusable_subset_keys = [str(item.get("key")) for item in comparison_cohorts if item.get("comparison_ready")]
    comparable_dimensions = ["target contract", "training scope", "feature contract", "reusable subsets"]
    weak_dimensions: list[str] = []
    if target_name == "not recorded":
        weak_dimensions.append("target name not recorded")
    if training_scope in {"baseline_bundle", "ranking_without_target_model", "not_recorded"}:
        weak_dimensions.append("training scope remains bridge-state")
    if feature_signature == "feature contract not recorded":
        weak_dimensions.append("feature contract is incomplete")
    if not reusable_subset_keys:
        weak_dimensions.append("no comparison-ready subsets were saved")

    session_family_key = "|".join(
        [
            target_name,
            target_kind,
            decision_intent,
            modeling_mode,
            scoring_mode,
            training_scope,
            feature_signature,
        ]
    )
    summary = (
        f"Cross-session evaluation is anchored by {target_name}, {target_kind} ranking, {decision_intent.replace('_', ' ')}, {modeling_mode.replace('_', ' ')}, {scoring_mode.replace('_', ' ')}, and {training_scope.replace('_', ' ')}. "
        f"Reusable subsets: {', '.join(reusable_subset_keys) if reusable_subset_keys else 'none yet'}."
    )
    if weak_dimensions:
        summary += f" Cross-session comparability remains bounded because {', '.join(weak_dimensions)}."
    else:
        summary += " Cross-session comparability is stronger when later sessions preserve these same anchors."
    return {
        "schema_version": "cross_session_evaluation_contract.v1",
        "comparison_ready": not weak_dimensions,
        "session_family_key": session_family_key,
        "target_name": target_name,
        "target_kind": target_kind,
        "decision_intent": decision_intent,
        "modeling_mode": modeling_mode,
        "scoring_mode": scoring_mode,
        "training_scope": training_scope,
        "feature_signature": feature_signature,
        "reusable_subset_keys": reusable_subset_keys,
        "comparable_dimensions": comparable_dimensions,
        "weak_dimensions": weak_dimensions,
        "summary": summary,
    }


def _version_comparison_contract(
    *,
    comparison_cohorts: list[dict[str, Any]],
    bundle: dict[str, Any],
    target_kind: str,
    feature_signature: str,
    training_scope: str,
) -> dict[str, Any]:
    selected = bundle.get("selected_model") if isinstance(bundle.get("selected_model"), dict) else {}
    benchmark = bundle.get("benchmark") if isinstance(bundle.get("benchmark"), list) else []
    selected_name = _clean_text(selected.get("name"), default="not recorded")
    runner_up_name = _clean_text((benchmark[1] or {}).get("name")) if len(benchmark) >= 2 and isinstance(benchmark[1], dict) else ""
    reusable_subset_keys = [str(item.get("key")) for item in comparison_cohorts if item.get("comparison_ready")]
    comparison_questions = [
        "did raw signal improve on reusable subsets",
        "did heuristic dominance reduce",
        "did representation-limited cohorts weaken less",
        "did shortlist fragility improve",
    ]
    summary = (
        f"Version-to-version comparison is now anchored by {target_kind} ranking, {training_scope.replace('_', ' ')}, {feature_signature.replace('_', ' ')}, and reusable subsets {', '.join(reusable_subset_keys) if reusable_subset_keys else 'none yet'}."
    )
    if selected_name != "not recorded":
        summary += f" Current selected model is {selected_name.replace('_', ' ')}."
    if runner_up_name:
        summary += f" Current runner-up is {runner_up_name.replace('_', ' ')}."
    if not reusable_subset_keys:
        summary += " Version comparison still remains partly ad hoc because no subset reached comparison-ready size."
    return {
        "schema_version": "version_comparison_contract.v1",
        "comparison_ready": bool(reusable_subset_keys),
        "target_kind": target_kind,
        "training_scope": training_scope,
        "feature_signature": feature_signature,
        "selected_model_name": selected_name,
        "runner_up_name": runner_up_name,
        "reusable_subset_keys": reusable_subset_keys,
        "comparison_questions": comparison_questions,
        "summary": summary,
    }


def _cross_run_comparison_contract(
    *,
    comparison_cohorts: list[dict[str, Any]],
    target_kind: str,
    bundle: dict[str, Any],
    feature_signature: str,
    run_contract: dict[str, Any] | None = None,
    comparison_anchors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    comparison_anchors = comparison_anchors if isinstance(comparison_anchors, dict) else {}
    model_family = _clean_text(bundle.get("model_family"), default="not recorded")
    training_scope = _clean_text(bundle.get("training_scope"), default="not recorded")
    selected_model_name = _clean_text(
        ((bundle.get("selected_model") or {}) if isinstance(bundle.get("selected_model"), dict) else {}).get("name")
        or run_contract.get("selected_model_name"),
        default="not recorded",
    )
    target_name = _clean_text(comparison_anchors.get("target_name"), default="not recorded")
    scoring_mode = _clean_text(comparison_anchors.get("scoring_mode") or run_contract.get("scoring_mode"), default="not recorded")
    reusable_subset_keys = [str(item.get("key")) for item in comparison_cohorts if item.get("comparison_ready")]
    comparability_cautions: list[str] = []
    if training_scope in {"baseline_bundle", "ranking_without_target_model"}:
        comparability_cautions.append("training scope still includes bridge-state fallback behavior")
    if feature_signature == "feature contract not recorded":
        comparability_cautions.append("feature contract is incomplete")
    if not reusable_subset_keys:
        comparability_cautions.append("no reusable subset reached comparison-ready size")
    summary = (
        f"Cross-run comparison is anchored by {target_name if target_name != 'not recorded' else target_kind} ranking, {training_scope.replace('_', ' ')}, {model_family.replace('_', ' ')}, {selected_model_name.replace('_', ' ')}, {scoring_mode.replace('_', ' ')}, and {feature_signature.replace('_', ' ')}. "
        f"Reusable subset keys: {', '.join(reusable_subset_keys) if reusable_subset_keys else 'none yet'}."
    )
    if comparability_cautions:
        summary += f" Comparability remains bounded because {', '.join(comparability_cautions)}."
    else:
        summary += " Comparability is stronger when future runs preserve these same anchors."
    return {
        "schema_version": "cross_run_comparison_contract.v1",
        "comparison_ready": bool(reusable_subset_keys),
        "target_kind": target_kind,
        "target_name": target_name,
        "training_scope": training_scope,
        "model_family": model_family,
        "selected_model_name": selected_model_name,
        "scoring_mode": scoring_mode,
        "feature_signature": feature_signature,
        "reusable_subset_keys": reusable_subset_keys,
        "comparability_cautions": comparability_cautions,
        "summary": summary,
    }


def _engine_strength_and_weakness_summaries(
    *,
    comparison_cohorts: list[dict[str, Any]],
    top_gap: float,
    raw_final_rank_correlation: float | None,
    too_close_rate: float,
    heuristic_shift_mean: float,
) -> tuple[str, str]:
    signal_led = next((item for item in comparison_cohorts if item.get("key") == "signal_led"), None)
    representation_supported = next((item for item in comparison_cohorts if item.get("key") == "representation_supported"), None)
    representation_limited = next((item for item in comparison_cohorts if item.get("key") == "representation_limited"), None)
    heuristic_heavy = next((item for item in comparison_cohorts if item.get("key") == "heuristic_heavy"), None)

    strength_bits: list[str] = []
    if signal_led and signal_led.get("comparison_ready"):
        strength_bits.append("signal-led cohorts are now reusable across runs")
    if representation_supported and (_safe_float(representation_supported.get("mean_neighbor_gap")) or 0.0) >= 0.035:
        strength_bits.append("better-covered chemistry regions show more usable separation")
    if raw_final_rank_correlation is not None and raw_final_rank_correlation >= 0.8:
        strength_bits.append("raw signal and final ordering remain reasonably aligned")
    if top_gap >= 0.04:
        strength_bits.append("the top shortlist band is not completely flat")
    strength_summary = (
        "Engine strengths are becoming more reusable: " + "; ".join(strength_bits[:3]) + "."
        if strength_bits
        else "No strong reusable engine-strength pattern dominates yet."
    )

    weakness_bits: list[str] = []
    if representation_limited and representation_limited.get("comparison_ready"):
        weakness_bits.append("representation-limited cohorts still degrade ranking quality")
    if heuristic_heavy and heuristic_heavy.get("comparison_ready"):
        weakness_bits.append("heuristic-heavy subsets still carry meaningful ordering burden")
    if too_close_rate >= 0.3:
        weakness_bits.append("too-close shortlist pressure remains high")
    if heuristic_shift_mean >= 0.12:
        weakness_bits.append("policy shifts still move candidates materially away from raw signal")
    weakness_summary = (
        "Engine weaknesses remain visible: " + "; ".join(weakness_bits[:3]) + "."
        if weakness_bits
        else "No single reusable engine weakness dominates this run, though bounded caution still applies."
    )
    return strength_summary, weakness_summary


def _signal_status_label(
    *,
    raw_signal: float,
    bounded_uncertainty_score: float,
    fragility_score: float,
    representation_support_factor: float,
    neighbor_gap: float | None,
) -> str:
    if neighbor_gap is not None and neighbor_gap < 0.015:
        return "Too close to separate strongly"
    if representation_support_factor < 0.88 and raw_signal >= 0.5:
        return "Thinly supported signal"
    if fragility_score >= 0.66 or bounded_uncertainty_score >= 0.62:
        return "Fragile signal"
    if raw_signal >= 0.68 and bounded_uncertainty_score <= 0.38 and representation_support_factor >= 0.94:
        return "Stronger signal"
    return "Bounded signal"


def _uncertainty_semantics(
    *,
    candidate: dict[str, Any],
    raw_signal: float,
    heuristic_adjustment_delta: float,
    representation_support_factor: float,
    neighbor_gap: float | None,
) -> dict[str, Any]:
    uncertainty = _clamp_score(candidate.get("uncertainty"))
    closeness_pressure = _bounded_closeness_from_gap(neighbor_gap)
    heuristic_reliance = min(1.0, abs(heuristic_adjustment_delta) / 0.25)
    representation_thinness = 1.0 - max(0.0, min(1.0, representation_support_factor))

    bounded_uncertainty_score = _clamp_score(
        (0.36 * uncertainty)
        + (0.26 * representation_thinness)
        + (0.22 * closeness_pressure)
        + (0.16 * heuristic_reliance)
    )
    fragility_score = _clamp_score(
        (0.42 * closeness_pressure)
        + (0.24 * heuristic_reliance)
        + (0.20 * representation_thinness)
        + (0.14 * uncertainty)
    )

    if neighbor_gap is None:
        separation_summary = (
            "Neighbor-gap separation is not fully recorded for this candidate, so closeness-to-neighbors should be read cautiously."
        )
    elif neighbor_gap < 0.015:
        separation_summary = (
            f"This candidate is too close to nearby shortlist entries to separate strongly; the nearest priority gap is only {neighbor_gap:.3f}."
        )
    elif neighbor_gap < 0.035:
        separation_summary = (
            f"This candidate sits in a weakly separated shortlist band; the nearest priority gap is {neighbor_gap:.3f}."
        )
    elif neighbor_gap < 0.08:
        separation_summary = (
            f"This candidate is boundedly separated from its neighbors; the nearest priority gap is {neighbor_gap:.3f}."
        )
    else:
        separation_summary = (
            f"This candidate is more clearly separated from nearby shortlist entries; the nearest priority gap is {neighbor_gap:.3f}."
        )

    uncertainty_summary = (
        f"Bounded uncertainty is {bounded_uncertainty_score:.3f}. It reflects signal-relative uncertainty, representation thinness, shortlist closeness, and heuristic reliance rather than calibrated truth."
    )
    caution_bits: list[str] = []
    if raw_signal < 0.5:
        caution_bits.append("Raw signal remains modest.")
    if representation_support_factor < 0.9:
        caution_bits.append("Representation support is thin enough to limit confidence.")
    if neighbor_gap is not None and neighbor_gap < 0.035:
        caution_bits.append("Nearby candidates are hard to separate honestly.")
    if abs(heuristic_adjustment_delta) >= 0.15:
        caution_bits.append("Heuristic policy is still doing meaningful ordering work.")
    if uncertainty >= 0.6:
        caution_bits.append("Session-level uncertainty remains elevated.")
    caution_summary = " ".join(caution_bits) if caution_bits else "No single caution dominates, but this remains a bounded prioritization signal."

    signal_status = _signal_status_label(
        raw_signal=raw_signal,
        bounded_uncertainty_score=bounded_uncertainty_score,
        fragility_score=fragility_score,
        representation_support_factor=representation_support_factor,
        neighbor_gap=neighbor_gap,
    )
    return {
        "bounded_uncertainty_score": bounded_uncertainty_score,
        "fragility_score": fragility_score,
        "neighbor_gap": neighbor_gap,
        "signal_status_label": signal_status,
        "uncertainty_summary": uncertainty_summary,
        "separation_summary": separation_summary,
        "caution_summary": caution_summary,
    }


def build_candidate_score_semantics(
    candidate: dict[str, Any],
    *,
    ranking_policy: dict[str, Any] | None = None,
    target_definition: dict[str, Any] | None = None,
    modeling_mode: str | None = None,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = candidate if isinstance(candidate, dict) else {}
    target_kind = _target_kind(target_definition=target_definition or candidate.get("target_definition"), modeling_mode=modeling_mode)
    raw_signal = _raw_signal_from_candidate(candidate, target_kind=target_kind)
    heuristic_policy_score = _clamp_score(candidate.get("heuristic_policy_score", candidate.get("priority_score")))

    representation_support_factor = _safe_float(candidate.get("representation_support_factor"))
    if representation_support_factor is None:
        representation_support_factor, representation_summary, failure_modes = _representation_support_from_similarity(
            candidate.get("max_similarity"),
            candidate.get("support_density"),
        )
    else:
        representation_support_factor = max(0.0, min(1.0, representation_support_factor))
        representation_summary = _clean_text(candidate.get("representation_summary")) or (
            "Representation support is already encoded in the saved candidate semantics."
        )
        failure_modes = list(candidate.get("scoring_failure_modes") or []) if isinstance(candidate.get("scoring_failure_modes"), list) else []

    raw_signal_weight = _safe_float(candidate.get("raw_signal_weight"))
    if raw_signal_weight is None:
        raw_signal_weight = _signal_weight_from_bundle(bundle or candidate.get("bundle"), target_kind=target_kind)
        if representation_support_factor < 0.9:
            raw_signal_weight -= 0.06
        if _clamp_score(candidate.get("uncertainty")) >= 0.7:
            raw_signal_weight -= 0.05
    raw_signal_weight = max(0.35, min(0.8, raw_signal_weight))
    heuristic_weight = _safe_float(candidate.get("heuristic_weight"))
    if heuristic_weight is None:
        heuristic_weight = 1.0 - raw_signal_weight
    heuristic_weight = max(0.2, min(0.65, heuristic_weight))

    blended_priority_score = _safe_float(candidate.get("blended_priority_score"))
    if blended_priority_score is None:
        blended_priority_score = _clamp_score((raw_signal * raw_signal_weight) + (heuristic_policy_score * heuristic_weight))

    representation_adjustment = _safe_float(candidate.get("representation_adjustment"))
    if representation_adjustment is None:
        representation_adjustment = blended_priority_score * (representation_support_factor - 1.0)
    final_priority_score = _clamp_score(candidate.get("priority_score", blended_priority_score + representation_adjustment))

    heuristic_adjustment_delta = _safe_float(candidate.get("heuristic_adjustment_delta"))
    if heuristic_adjustment_delta is None:
        heuristic_adjustment_delta = heuristic_policy_score - raw_signal

    uncertainty_bits = _uncertainty_semantics(
        candidate=candidate,
        raw_signal=raw_signal,
        heuristic_adjustment_delta=heuristic_adjustment_delta,
        representation_support_factor=representation_support_factor,
        neighbor_gap=_safe_float(candidate.get("neighbor_gap")),
    )

    heuristic_summary = (
        "Heuristic shortlist policy still matters, but the final bounded priority now leans more on the raw predictive signal than before."
        if abs(heuristic_adjustment_delta) >= 0.15
        else "Heuristic shortlist policy is acting as a bounded adjustment layer rather than carrying most of the final priority."
    )
    governance_effect_summary = _clean_text(candidate.get("governance_effect_summary")) or (
        "Governance is applied after candidate scoring. This score summary describes bounded prioritization before broader trust or carryover gates."
    )

    local_failure_modes = list(failure_modes)
    if abs(heuristic_adjustment_delta) >= 0.2:
        local_failure_modes.append("heuristic_policy_heavy")
    if final_priority_score <= 0.35 and raw_signal >= 0.55:
        local_failure_modes.append("policy_or_representation_downweights_raw_signal")
    if heuristic_policy_score <= 0.35 and raw_signal <= 0.42:
        local_failure_modes.append("weak_candidate_separation_signal")
    if raw_signal_weight < 0.5:
        local_failure_modes.append("raw_signal_still_not_strong_enough")
    if uncertainty_bits["neighbor_gap"] is not None and uncertainty_bits["neighbor_gap"] < 0.015:
        local_failure_modes.append("too_close_to_separate")
    elif uncertainty_bits["neighbor_gap"] is not None and uncertainty_bits["neighbor_gap"] < 0.035:
        local_failure_modes.append("weakly_separated_shortlist_band")
    if uncertainty_bits["fragility_score"] >= 0.66:
        local_failure_modes.append("fragile_ordering")
    if uncertainty_bits["bounded_uncertainty_score"] >= 0.62:
        local_failure_modes.append("bounded_uncertainty_elevated")

    summary = (
        f"Raw predictive signal is {_raw_signal_label(target_kind=target_kind).lower()} {raw_signal:.3f}. "
        f"Heuristic policy score is {heuristic_policy_score:.3f}. "
        f"The blended priority uses {raw_signal_weight:.2f} raw-signal weight and {heuristic_weight:.2f} heuristic weight, "
        f"then representation support adjusts the final priority to {final_priority_score:.3f}. "
        f"{uncertainty_bits['uncertainty_summary']}"
    )

    return validate_candidate_score_semantics(
        {
            "raw_predictive_signal": raw_signal,
            "raw_predictive_signal_label": _raw_signal_label(target_kind=target_kind),
            "heuristic_policy_score": heuristic_policy_score,
            "heuristic_adjustment_delta": heuristic_adjustment_delta,
            "raw_signal_weight": raw_signal_weight,
            "heuristic_weight": heuristic_weight,
            "blended_priority_score": blended_priority_score,
            "representation_support_factor": representation_support_factor,
            "representation_adjustment": representation_adjustment,
            "final_priority_score": final_priority_score,
            "bounded_uncertainty_score": uncertainty_bits["bounded_uncertainty_score"],
            "fragility_score": uncertainty_bits["fragility_score"],
            "neighbor_gap": uncertainty_bits["neighbor_gap"],
            "signal_status_label": uncertainty_bits["signal_status_label"],
            "governance_effect_summary": governance_effect_summary,
            "heuristic_summary": heuristic_summary,
            "representation_summary": representation_summary,
            "uncertainty_summary": uncertainty_bits["uncertainty_summary"],
            "separation_summary": uncertainty_bits["separation_summary"],
            "caution_summary": uncertainty_bits["caution_summary"],
            "summary": summary,
            "failure_modes": local_failure_modes,
        }
    )


def attach_candidate_score_semantics(
    frame: pd.DataFrame,
    *,
    ranking_policy: dict[str, Any] | None = None,
    target_definition: dict[str, Any] | None = None,
    modeling_mode: str | None = None,
    bundle: dict[str, Any] | None = None,
) -> pd.DataFrame:
    scored = frame.copy()
    target_kind = _target_kind(target_definition=target_definition, modeling_mode=modeling_mode)

    if "raw_predictive_signal" not in scored.columns:
        scored["raw_predictive_signal"] = scored.apply(
            lambda row: _raw_signal_from_candidate(row.to_dict(), target_kind=target_kind),
            axis=1,
        )
    else:
        scored["raw_predictive_signal"] = pd.to_numeric(scored["raw_predictive_signal"], errors="coerce").fillna(0.0)

    if "heuristic_policy_score" not in scored.columns:
        scored["heuristic_policy_score"] = pd.to_numeric(
            scored.get("priority_score", scored.get("final_score", 0.0)),
            errors="coerce",
        ).fillna(0.0)
    else:
        scored["heuristic_policy_score"] = pd.to_numeric(scored["heuristic_policy_score"], errors="coerce").fillna(0.0)

    def _support_factor_for_row(row: pd.Series) -> float:
        explicit = _safe_float(row.get("representation_support_factor"))
        if explicit is not None:
            return max(0.0, min(1.0, explicit))
        factor, _, _ = _representation_support_from_similarity(row.get("max_similarity"), row.get("support_density"))
        return factor

    base_signal_weight = _signal_weight_from_bundle(bundle, target_kind=target_kind)
    scored["representation_support_factor"] = scored.apply(_support_factor_for_row, axis=1)
    scored["raw_signal_weight"] = (
        base_signal_weight
        - ((1.0 - scored["representation_support_factor"]) * 0.35)
        - (pd.to_numeric(scored.get("uncertainty", 0.0), errors="coerce").fillna(0.0) * 0.08)
    ).clip(lower=0.35, upper=0.8)
    scored["heuristic_weight"] = (1.0 - scored["raw_signal_weight"]).clip(lower=0.2, upper=0.65)
    scored["blended_priority_score"] = (
        (scored["raw_predictive_signal"] * scored["raw_signal_weight"])
        + (scored["heuristic_policy_score"] * scored["heuristic_weight"])
    ).clip(lower=0.0, upper=1.0)
    scored["representation_adjustment"] = (
        scored["blended_priority_score"] * (scored["representation_support_factor"] - 1.0)
    )
    scored["heuristic_adjustment_delta"] = scored["heuristic_policy_score"] - scored["raw_predictive_signal"]
    scored["priority_score"] = (
        scored["blended_priority_score"] + scored["representation_adjustment"]
    ).clip(lower=0.0, upper=1.0)
    ordered_index = scored["priority_score"].sort_values(ascending=False).index.tolist()
    neighbor_gaps: dict[Any, float | None] = {}
    ordered_scores = scored.loc[ordered_index, "priority_score"].tolist()
    for position, index in enumerate(ordered_index):
        local_gaps: list[float] = []
        if position > 0:
            local_gaps.append(abs(float(ordered_scores[position]) - float(ordered_scores[position - 1])))
        if position + 1 < len(ordered_scores):
            local_gaps.append(abs(float(ordered_scores[position]) - float(ordered_scores[position + 1])))
        neighbor_gaps[index] = min(local_gaps) if local_gaps else None
    scored["neighbor_gap"] = scored.index.to_series().map(neighbor_gaps)

    scored["score_semantics"] = scored.apply(
        lambda row: build_candidate_score_semantics(
            row.to_dict(),
            ranking_policy=ranking_policy,
            target_definition=target_definition,
            modeling_mode=modeling_mode,
            bundle=bundle,
        ),
        axis=1,
    )
    scored["score_decomposition_summary"] = scored["score_semantics"].apply(
        lambda item: _clean_text(item.get("summary")) if isinstance(item, dict) else ""
    )
    scored["scoring_failure_mode_summary"] = scored["score_semantics"].apply(
        lambda item: "; ".join(item.get("failure_modes", [])[:3]) if isinstance(item, dict) else ""
    )
    scored["bounded_uncertainty_score"] = scored["score_semantics"].apply(
        lambda item: _safe_float(item.get("bounded_uncertainty_score")) if isinstance(item, dict) else None
    )
    scored["fragility_score"] = scored["score_semantics"].apply(
        lambda item: _safe_float(item.get("fragility_score")) if isinstance(item, dict) else None
    )
    scored["signal_status_label"] = scored["score_semantics"].apply(
        lambda item: _clean_text(item.get("signal_status_label")) if isinstance(item, dict) else ""
    )
    scored["raw_predictive_signal_label"] = _raw_signal_label(target_kind=target_kind)
    return scored


def build_offline_ranking_evaluation(
    frame: pd.DataFrame | None,
    *,
    ranking_policy: dict[str, Any] | None = None,
    target_definition: dict[str, Any] | None = None,
    modeling_mode: str | None = None,
    bundle: dict[str, Any] | None = None,
    run_contract: dict[str, Any] | None = None,
    comparison_anchors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = bundle if isinstance(bundle, dict) else {}
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    comparison_anchors = comparison_anchors if isinstance(comparison_anchors, dict) else {}
    if frame is None or frame.empty:
        return {
            "schema_version": "offline_ranking_evaluation.v3",
            "evaluation_ready": False,
            "evaluation_summary": "Offline ranking evaluation could not run because no scored candidates were available.",
            "candidate_separation_summary": "No candidate separation diagnostics are available yet.",
            "ranking_stability_summary": "No ranking stability diagnostics are available yet.",
            "heuristic_influence_summary": "No heuristic-influence diagnostics are available yet.",
            "sensitivity_summary": "No sensitivity diagnostics are available yet.",
            "closeness_band_summary": "No closeness-band diagnostics are available yet.",
            "top_k_quality_summary": "No top-k quality summary is available yet.",
            "calibration_awareness_summary": "No calibration-aware summary is available yet.",
            "calibration_band_summary": "No calibration-band summary is available yet.",
            "comparison_cohort_summary": "No stable comparison cohort is recorded yet.",
            "cohort_diagnostic_summary": "No reusable evaluation subsets are recorded yet.",
            "evaluation_subset_summary": "No reusable evaluation subset summary is available yet.",
            "session_variation_summary": "No session-variation summary is available yet.",
            "cross_session_comparison_summary": "No cross-session comparison summary is available yet.",
            "version_comparison_summary": "No model-family or version comparison is available yet.",
            "representation_support_summary": "No representation-support summary is available yet.",
            "representation_evaluation_summary": "No representation-aware evaluation summary is available yet.",
            "representation_condition_summary": "No representation-conditioned evaluation summary is available yet.",
            "cross_run_comparison_summary": "No cross-run comparison contract is available yet.",
            "engine_strength_summary": "No reusable engine-strength summary is available yet.",
            "engine_weakness_summary": "No reusable engine-weakness summary is available yet.",
            "comparison_cohorts": [],
            "evaluation_subsets": [],
            "representation_condition_diagnostics": [],
            "calibration_band_diagnostics": [],
            "cross_run_comparison_contract": {},
            "cross_session_evaluation_contract": {},
            "version_comparison_contract": {},
            "score_span": None,
            "top_gap": None,
            "raw_signal_span": None,
            "raw_final_rank_correlation": None,
            "heuristic_shift_mean": None,
            "representation_penalty_rate": None,
            "too_close_rate": None,
            "weak_band_rate": None,
            "diagnostics": [],
        }

    scored = frame.copy()
    target_kind = _target_kind(target_definition=target_definition, modeling_mode=modeling_mode)
    raw_signal = pd.to_numeric(scored.get("raw_predictive_signal", scored.get("confidence", 0.0)), errors="coerce").fillna(0.0)
    final_score = pd.to_numeric(scored.get("priority_score", scored.get("final_score", 0.0)), errors="coerce").fillna(0.0)
    heuristic_policy = pd.to_numeric(
        scored.get("heuristic_policy_score", scored.get("priority_score", 0.0)),
        errors="coerce",
    ).fillna(0.0)
    representation_support = pd.to_numeric(
        scored.get("representation_support_factor", 1.0),
        errors="coerce",
    ).fillna(1.0)
    uncertainty = pd.to_numeric(scored.get("uncertainty", 0.0), errors="coerce").fillna(0.0)
    bounded_uncertainty = pd.to_numeric(
        scored.get("bounded_uncertainty_score", scored.get("uncertainty", 0.0)),
        errors="coerce",
    ).fillna(0.0)
    fragility = pd.to_numeric(
        scored.get("fragility_score", scored.get("bounded_uncertainty_score", scored.get("uncertainty", 0.0))),
        errors="coerce",
    ).fillna(0.0)
    raw_signal_weight = pd.to_numeric(scored.get("raw_signal_weight", 0.5), errors="coerce").fillna(0.5)
    neighbor_gap = pd.to_numeric(scored.get("neighbor_gap", None), errors="coerce")

    ordered = final_score.sort_values(ascending=False).reset_index(drop=True)
    raw_ordered = raw_signal.sort_values(ascending=False).reset_index(drop=True)
    score_span = float(ordered.max() - ordered.min()) if not ordered.empty else 0.0
    raw_signal_span = float(raw_ordered.max() - raw_ordered.min()) if not raw_ordered.empty else 0.0
    top_gap = float(ordered.iloc[0] - ordered.iloc[1]) if len(ordered) >= 2 else 0.0
    top_window = ordered.head(min(5, len(ordered)))
    mean_adjacent_gap = float((top_window.diff(-1).abs().dropna()).mean()) if len(top_window) >= 2 else 0.0
    heuristic_shift_mean = float((heuristic_policy - raw_signal).abs().mean()) if len(scored) else 0.0
    penalized_rate = float((representation_support < 0.999).mean()) if len(scored) else 0.0
    too_close_rate = float((neighbor_gap.dropna() < 0.015).mean()) if neighbor_gap.notna().any() else 0.0
    weak_band_rate = float((neighbor_gap.dropna() < 0.035).mean()) if neighbor_gap.notna().any() else 0.0
    raw_final_rank_correlation = None
    if len(scored) >= 3:
        raw_final_rank_correlation = float(raw_signal.rank().corr(final_score.rank()))

    diagnostics: list[str] = []
    if score_span < 0.10 or mean_adjacent_gap < 0.02:
        candidate_separation_summary = (
            f"Candidate separation is weak: final priority scores span only {score_span:.3f}, so small changes could reshuffle the shortlist."
        )
        diagnostics.append("weak_candidate_separation")
    elif score_span < 0.20 or mean_adjacent_gap < 0.035:
        candidate_separation_summary = (
            f"Candidate separation is usable but still bounded: score span is {score_span:.3f}, so shortlist distinctions should be read cautiously."
        )
    else:
        candidate_separation_summary = (
            f"Candidate separation improved for this run: final priority spans {score_span:.3f}, which is stronger than a flat shortlist."
        )

    if top_gap < 0.02 or mean_adjacent_gap < 0.02:
        ranking_stability_summary = (
            f"Top-of-shortlist stability is fragile: the top gap is {top_gap:.3f}, so nearby candidates may swap positions under small score changes."
        )
        diagnostics.append("ranking_top_is_fragile")
    elif top_gap < 0.05:
        ranking_stability_summary = (
            f"Top-of-shortlist stability is bounded: the top gap is {top_gap:.3f}, so ordering is usable but not strongly separated."
        )
    else:
        ranking_stability_summary = (
            f"Top-of-shortlist stability is reasonably bounded for this run: the top gap is {top_gap:.3f}."
        )

    if too_close_rate >= 0.3:
        closeness_band_summary = (
            "A material share of the shortlist is too close to separate strongly, so rank order inside the leading band should be read cautiously."
        )
        diagnostics.append("many_candidates_too_close")
    elif weak_band_rate >= 0.3:
        closeness_band_summary = (
            "The shortlist contains a noticeable weak-separation band where nearby candidates are difficult to distinguish confidently."
        )
    elif neighbor_gap.notna().any():
        closeness_band_summary = (
            "Most leading candidates sit outside the weakest closeness bands, so shortlist separation is more usable than a flat ranking."
        )
    else:
        closeness_band_summary = (
            "Closeness-band diagnostics are limited because neighbor-gap information was not fully recorded."
        )

    if heuristic_shift_mean >= 0.12 or raw_signal_weight.mean() < 0.55 or (raw_final_rank_correlation is not None and raw_final_rank_correlation < 0.7):
        heuristic_influence_summary = (
            "Heuristic shortlist policy is still doing substantial ranking work relative to the raw predictive signal, even though the final priority now gives signal more weight than before."
        )
        diagnostics.append("heuristic_policy_heavy")
    else:
        heuristic_influence_summary = (
            "Final ordering is more closely tracking the raw predictive signal than before, with heuristic policy acting as a bounded secondary layer."
        )

    if penalized_rate >= 0.4 or float(bounded_uncertainty.mean()) >= 0.6:
        sensitivity_summary = (
            "Ranking sensitivity remains elevated because many candidates sit near thin representation support or high uncertainty."
        )
        diagnostics.append("high_representation_or_uncertainty_sensitivity")
    elif penalized_rate > 0:
        sensitivity_summary = (
            "Some candidates are still being downweighted by thin representation support, but the penalty is now explicit and bounded."
        )
    else:
        sensitivity_summary = (
            "Representation support is not currently downweighting much of the shortlist, so the main sensitivity remains in signal quality and policy separation."
        )

    selected = bundle.get("selected_model") if isinstance(bundle.get("selected_model"), dict) else {}
    model_family = _clean_text(bundle.get("model_family"), default="not recorded")
    calibration_method = _clean_text(selected.get("calibration_method"))
    metrics = bundle.get("metrics") if isinstance(bundle.get("metrics"), dict) else {}
    holdout = metrics.get("holdout") if isinstance(metrics.get("holdout"), dict) else {}
    brier = _safe_float(holdout.get("brier_score"))
    log_loss = _safe_float(holdout.get("log_loss"))
    raw_signal_quantiles = raw_signal.quantile([0.33, 0.67]) if len(scored) >= 6 else None
    band_summary = ""
    calibration_band_diagnostics: list[dict[str, Any]] = []
    if isinstance(raw_signal_quantiles, pd.Series) and len(raw_signal_quantiles) == 2:
        lower_cut = float(raw_signal_quantiles.iloc[0])
        upper_cut = float(raw_signal_quantiles.iloc[1])
        high_band = scored[raw_signal >= upper_cut]
        low_band = scored[raw_signal <= lower_cut]
        high_uncertainty = _series_mean(pd.to_numeric(high_band.get("bounded_uncertainty_score", high_band.get("uncertainty", 0.0)), errors="coerce"))
        low_uncertainty = _series_mean(pd.to_numeric(low_band.get("bounded_uncertainty_score", low_band.get("uncertainty", 0.0)), errors="coerce"))
        high_support = _series_mean(pd.to_numeric(high_band.get("representation_support_factor", 1.0), errors="coerce"))
        low_support = _series_mean(pd.to_numeric(low_band.get("representation_support_factor", 1.0), errors="coerce"))
        high_gap = _series_mean(pd.to_numeric(high_band.get("neighbor_gap", None), errors="coerce"))
        low_gap = _series_mean(pd.to_numeric(low_band.get("neighbor_gap", None), errors="coerce"))
        calibration_band_diagnostics = [
            {
                "band": "higher_raw_signal",
                "count": int(len(high_band)),
                "mean_uncertainty": high_uncertainty,
                "mean_representation_support": high_support,
                "mean_neighbor_gap": high_gap,
            },
            {
                "band": "lower_raw_signal",
                "count": int(len(low_band)),
                "mean_uncertainty": low_uncertainty,
                "mean_representation_support": low_support,
                "mean_neighbor_gap": low_gap,
            },
        ]
        if (
            high_uncertainty is not None
            and low_uncertainty is not None
            and high_support is not None
            and low_support is not None
            and high_uncertainty + 0.08 < low_uncertainty
            and high_support > low_support + 0.04
        ):
            band_summary = (
                " Higher raw-signal bands also show better internal reliability signals in this run, with lower bounded uncertainty and stronger representation support."
            )
        else:
            band_summary = (
                " Higher raw-signal bands do not yet map cleanly to stronger internal shortlist reliability, so score strength should stay bounded and relative."
            )
        if high_gap is not None and low_gap is not None and high_gap > low_gap + 0.01:
            band_summary += " The stronger band is also more separated from nearby candidates."

    if target_kind == "classification":
        if calibration_method and (brier is not None or log_loss is not None):
            bits: list[str] = [f"Saved confidence uses {calibration_method} calibration."]
            if brier is not None:
                bits.append(f"Brier score is {brier:.3f}.")
            if log_loss is not None:
                bits.append(f"Log loss is {log_loss:.3f}.")
            bits.append("This still supports only signal-relative confidence, not calibrated truth certainty.")
            if band_summary:
                bits.append(band_summary.strip())
            calibration_awareness_summary = " ".join(bits)
        else:
            calibration_awareness_summary = (
                "Confidence should still be read as signal-relative rather than calibrated certainty because saved calibration evidence is limited."
            )
            if band_summary:
                calibration_awareness_summary = f"{calibration_awareness_summary}{band_summary}"
    else:
        calibration_awareness_summary = (
            "Regression ranking compatibility is not a calibrated probability. It is a bounded ordering signal and should be read together with dispersion and representation support."
        )
        if band_summary:
            calibration_awareness_summary = f"{calibration_awareness_summary}{band_summary}"
    calibration_band_summary = band_summary.strip() if band_summary else (
        "Calibration-band evidence is still limited, so score strength should remain bounded and relative."
    )

    benchmark = bundle.get("benchmark") if isinstance(bundle.get("benchmark"), list) else []
    if len(benchmark) >= 2:
        leader = benchmark[0]
        runner_up = benchmark[1]
        version_comparison_summary = (
            f"Offline model comparison selected {leader.get('name', 'the current model')} ahead of {runner_up.get('name', 'the next candidate')} for this run, giving a bounded model-family comparison baseline for later versions."
        )
    elif benchmark:
        version_comparison_summary = (
            f"Offline model comparison currently records a selected configuration ({benchmark[0].get('name', 'current model')}), but runner-up comparison coverage is still thin."
        )
    else:
        version_comparison_summary = "No model-family comparison was saved for this run, so version comparison remains limited."

    feature_signature = _clean_text(
        (
            f"rdkit_descriptors_{len(bundle.get('descriptor_features', []))}_plus_morgan_fp_{int(bundle.get('fingerprint_bits'))}"
            if isinstance(bundle.get("descriptor_features"), list) and bundle.get("descriptor_features") and bundle.get("fingerprint_bits")
            else ""
        ),
        default="feature contract not recorded",
    )
    training_scope = _clean_text(bundle.get("training_scope"), default="not recorded")
    comparison_cohort_summary = (
        f"Comparison cohort for this run is bounded by {target_kind} ranking, {training_scope.replace('_', ' ')}, {model_family.replace('_', ' ')}, and {feature_signature.replace('_', ' ')}."
    )
    comparison_cohorts = _build_comparison_cohorts(scored)
    evaluation_subsets = [item for item in comparison_cohorts if item.get("comparison_ready")]
    cohort_diagnostic_summary = _cohort_diagnostic_summary(comparison_cohorts)
    evaluation_subset_summary = _evaluation_subset_summary(comparison_cohorts)
    representation_evaluation_summary = _representation_evaluation_summary(comparison_cohorts)
    representation_condition_diagnostics = _representation_condition_diagnostics(comparison_cohorts)
    representation_condition_summary = _representation_condition_summary(comparison_cohorts)
    cross_run_comparison_contract = _cross_run_comparison_contract(
        comparison_cohorts=comparison_cohorts,
        target_kind=target_kind,
        bundle=bundle,
        feature_signature=feature_signature,
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
    )
    cross_session_evaluation_contract = _cross_session_evaluation_contract(
        comparison_cohorts=comparison_cohorts,
        comparison_anchors=comparison_anchors,
        run_contract=run_contract,
        target_definition=target_definition,
        target_kind=target_kind,
        feature_signature=feature_signature,
        training_scope=training_scope,
    )
    version_comparison_contract = _version_comparison_contract(
        comparison_cohorts=comparison_cohorts,
        bundle=bundle,
        target_kind=target_kind,
        feature_signature=feature_signature,
        training_scope=training_scope,
    )
    cross_run_comparison_summary = _clean_text(cross_run_comparison_contract.get("summary"))
    cross_session_comparison_summary = _clean_text(cross_session_evaluation_contract.get("summary"))
    top_k_quality_summary = _top_k_quality_summary(scored)

    if too_close_rate >= 0.3 or weak_band_rate >= 0.5 or float(fragility.mean()) >= 0.55:
        session_variation_summary = (
            "This run should be compared across similar sessions carefully because weak separation suggests session-specific variation could reorder part of the shortlist."
        )
    elif raw_final_rank_correlation is not None and raw_final_rank_correlation >= 0.8 and top_gap >= 0.04:
        session_variation_summary = (
            "This run is a better candidate for cross-session comparison because raw signal and final ordering remain reasonably aligned and the top band is not extremely flat."
        )
    else:
        session_variation_summary = (
            "Cross-session comparison is possible, but ranking reliability across session variation remains only partly established."
        )

    if penalized_rate >= 0.35:
        representation_support_summary = (
            "Representation support remains a material constraint on this shortlist because a sizable share of candidates sit near thin chemistry coverage."
        )
    elif penalized_rate > 0:
        representation_support_summary = (
            "Representation support still limits part of the shortlist, but most candidates remain within stronger chemistry coverage."
        )
    else:
        representation_support_summary = (
            "Representation support is not a major limiting factor for most of the current shortlist."
        )
    if "stronger chemistry coverage improves ranking quality" in representation_evaluation_summary.lower():
        diagnostics.append("representation_limits_correlate_with_weaker_ranking")

    signal_label = _raw_signal_label(target_kind=target_kind).lower()
    engine_strength_summary, engine_weakness_summary = _engine_strength_and_weakness_summaries(
        comparison_cohorts=comparison_cohorts,
        top_gap=top_gap,
        raw_final_rank_correlation=raw_final_rank_correlation,
        too_close_rate=too_close_rate,
        heuristic_shift_mean=heuristic_shift_mean,
    )
    evaluation_summary = (
        f"Offline ranking evaluation now records candidate-level separation, stability, heuristic-dominance, and representation-support diagnostics for {len(scored)} scored candidates. "
        f"Raw predictive signal uses {signal_label}, while final ordering uses the bounded blended priority score. "
        f"Reusable comparison cohorts now make later cross-run evaluation less session-local."
    )

    return {
        "schema_version": "offline_ranking_evaluation.v3",
        "evaluation_ready": True,
        "evaluation_summary": evaluation_summary,
        "candidate_separation_summary": candidate_separation_summary,
        "ranking_stability_summary": ranking_stability_summary,
        "closeness_band_summary": closeness_band_summary,
        "top_k_quality_summary": top_k_quality_summary,
        "heuristic_influence_summary": heuristic_influence_summary,
        "sensitivity_summary": sensitivity_summary,
        "calibration_awareness_summary": calibration_awareness_summary,
        "calibration_band_summary": calibration_band_summary,
        "comparison_cohort_summary": comparison_cohort_summary,
        "cohort_diagnostic_summary": cohort_diagnostic_summary,
        "evaluation_subset_summary": evaluation_subset_summary,
        "session_variation_summary": session_variation_summary,
        "cross_session_comparison_summary": cross_session_comparison_summary,
        "version_comparison_summary": version_comparison_summary,
        "representation_support_summary": representation_support_summary,
        "representation_evaluation_summary": representation_evaluation_summary,
        "representation_condition_summary": representation_condition_summary,
        "cross_run_comparison_summary": cross_run_comparison_summary,
        "engine_strength_summary": engine_strength_summary,
        "engine_weakness_summary": engine_weakness_summary,
        "comparison_cohorts": comparison_cohorts,
        "evaluation_subsets": evaluation_subsets,
        "representation_condition_diagnostics": representation_condition_diagnostics,
        "calibration_band_diagnostics": calibration_band_diagnostics,
        "cross_run_comparison_contract": cross_run_comparison_contract,
        "cross_session_evaluation_contract": cross_session_evaluation_contract,
        "version_comparison_contract": version_comparison_contract,
        "score_span": score_span,
        "top_gap": top_gap,
        "raw_signal_span": raw_signal_span,
        "raw_final_rank_correlation": raw_final_rank_correlation,
        "heuristic_shift_mean": heuristic_shift_mean,
        "representation_penalty_rate": penalized_rate,
        "too_close_rate": too_close_rate,
        "weak_band_rate": weak_band_rate,
        "diagnostics": diagnostics,
    }


__all__ = [
    "attach_candidate_score_semantics",
    "build_candidate_score_semantics",
    "build_offline_ranking_evaluation",
]
