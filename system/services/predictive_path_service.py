from __future__ import annotations

from typing import Any

from system.contracts import (
    validate_predictive_evaluation_contract,
    validate_predictive_failure_mode_summary,
    validate_predictive_path_summary,
    validate_predictive_representation_summary,
    validate_predictive_task_contract,
)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _weight_driver_summary(ranking_policy: dict[str, Any], *, target_kind: str) -> str:
    weight_breakdown = ranking_policy.get("weight_breakdown") if isinstance(ranking_policy.get("weight_breakdown"), list) else []
    ordered = [
        item
        for item in weight_breakdown
        if isinstance(item, dict) and _safe_float(item.get("weight"), 0.0) and _clean_text(item.get("label"))
    ]
    ordered.sort(key=lambda item: float(item.get("weight") or 0.0), reverse=True)
    if ordered:
        top = ordered[:3]
        parts = [
            f"{_clean_text(item.get('label'))} ({float(item.get('weight_percent') or 0.0):.1f}%)"
            for item in top
        ]
        return (
            "Current prioritization is driven by "
            + ", ".join(parts)
            + ". This is still a bounded ranking contract rather than a mature predictive proof surface."
        )
    primary = _clean_text(ranking_policy.get("primary_score_label") or ranking_policy.get("primary_score"))
    if primary:
        return (
            f"Current prioritization is anchored on {primary.lower()} first, then supporting shortlist scores. "
            "The ordering contract is explicit, but still bridge-state."
        )
    return (
        "Current prioritization logic is available, but the saved ranking-weight breakdown is incomplete, so readiness inspection should treat the policy surface as partial."
    )


def _target_kind(
    target_definition: dict[str, Any],
    modeling_mode: str | None,
    *,
    default: str = "classification",
) -> str:
    return _clean_text(target_definition.get("target_kind") or modeling_mode, default=default).lower()


def _target_name(target_definition: dict[str, Any]) -> str:
    return _clean_text(target_definition.get("target_name"), default="the current target")


def _training_scope(run_contract: dict[str, Any], evaluation_summary: dict[str, Any]) -> str:
    return _clean_text(
        run_contract.get("training_scope") or evaluation_summary.get("training_scope"),
        default="not_recorded",
    ).lower()


def _selected_model_name(run_contract: dict[str, Any], evaluation_summary: dict[str, Any]) -> str:
    selected = evaluation_summary.get("selected_model") if isinstance(evaluation_summary.get("selected_model"), dict) else {}
    return _clean_text(
        run_contract.get("selected_model_name") or selected.get("name"),
        default="not recorded",
    )


def build_predictive_task_contract(
    *,
    target_definition: dict[str, Any] | None = None,
    ranking_policy: dict[str, Any] | None = None,
    run_contract: dict[str, Any] | None = None,
    scientific_truth: dict[str, Any] | None = None,
    modeling_mode: str | None = None,
) -> dict[str, Any]:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    ranking_policy = ranking_policy if isinstance(ranking_policy, dict) else {}
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    scientific_truth = scientific_truth if isinstance(scientific_truth, dict) else {}

    target_kind = _target_kind(target_definition, modeling_mode)
    target_name = _target_name(target_definition)
    decision_intent = _clean_text(run_contract.get("decision_intent"), default="prioritize_experiments")
    primary_score_label = _clean_text(ranking_policy.get("primary_score_label") or ranking_policy.get("primary_score"), default="Priority score")
    scientific_decision_summary = (
        scientific_truth.get("scientific_decision_summary")
        if isinstance(scientific_truth.get("scientific_decision_summary"), dict)
        else {}
    )
    governance_summary = _clean_text(scientific_decision_summary.get("carryover_guardrail_summary"))
    training_scope = _clean_text(run_contract.get("training_scope"), default="not_recorded")

    if target_kind == "regression":
        task_label = "Bounded measurement-oriented candidate prioritization"
        prioritization_target = (
            f"Prioritize molecules worth testing next for {target_name} under a continuous-target ranking workflow."
        )
        predictive_score_summary = (
            "Raw predictive signal uses predicted value, normalized ranking compatibility, and prediction dispersion as bounded ordering inputs rather than as outcome truth."
        )
    else:
        task_label = "Bounded candidate prioritization for what to test next"
        prioritization_target = (
            f"Prioritize molecules worth testing next for {target_name} under uncertainty rather than predict universal truth."
        )
        predictive_score_summary = (
            "Raw predictive signal uses model-produced class probability, uncertainty, novelty, and experiment value for shortlist ordering."
        )

    if decision_intent == "predict_labels":
        task_summary = (
            "The current predictive task is still bounded prioritization for follow-up review, even when the interface is showing a label-style shortlist."
        )
    else:
        task_summary = (
            "The current predictive task is local candidate prioritization for what to test next, not universal truth prediction."
        )

    final_ordering_summary = (
        f"Final user-facing ordering starts from {primary_score_label.lower()} and then remains subject to heuristic shortlist policy, trust posture, and broader carryover boundaries."
    )
    governance_interaction_summary = governance_summary or (
        "Trust, review, and carryover posture can still constrain how far a strong-ranked candidate should travel."
    )

    if training_scope == "baseline_bundle":
        limitation = (
            "This predictive task still reuses a legacy baseline bundle in some sessions, so output should be read as bridge-state guidance."
        )
    elif training_scope == "ranking_without_target_model":
        limitation = (
            "This predictive task may run without a target-specific model, so shortlist ordering can lean heavily on bridge-state policy."
        )
    else:
        limitation = (
            "This predictive task is explicit enough to inspect, but current shortlist behavior still mixes model signal with bounded heuristic policy."
        )

    return validate_predictive_task_contract(
        {
            "task_label": task_label,
            "task_summary": task_summary,
            "prioritization_target": prioritization_target,
            "predictive_score_label": primary_score_label,
            "predictive_score_summary": predictive_score_summary,
            "final_ordering_summary": final_ordering_summary,
            "governance_interaction_summary": governance_interaction_summary,
            "bridge_state_limitations_summary": limitation,
        }
    )


def build_predictive_representation_summary(
    *,
    target_definition: dict[str, Any] | None = None,
    run_contract: dict[str, Any] | None = None,
    analysis_report: dict[str, Any] | None = None,
    modeling_mode: str | None = None,
) -> dict[str, Any]:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    analysis_report = analysis_report if isinstance(analysis_report, dict) else {}

    feature_signature = _clean_text(run_contract.get("feature_signature"), default="not_recorded")
    training_scope = _clean_text(run_contract.get("training_scope"), default="not_recorded")
    selected_model_family = _clean_text(run_contract.get("selected_model_family"), default="not_recorded")
    target_kind = _target_kind(target_definition, modeling_mode)
    target_name = _target_name(target_definition)
    measurement_summary = analysis_report.get("measurement_summary") if isinstance(analysis_report.get("measurement_summary"), dict) else {}
    rows_with_values = _safe_int(measurement_summary.get("rows_with_values"))
    rows_with_labels = _safe_int(measurement_summary.get("rows_with_labels"))
    label_source = _clean_text(run_contract.get("label_source") or measurement_summary.get("label_source"), default="not_recorded")

    parts: list[str] = []
    if feature_signature and feature_signature != "not_recorded":
        parts.append(f"Feature contract currently uses {feature_signature.replace('_', ' ')}.")
    if selected_model_family and selected_model_family != "not_recorded":
        parts.append(f"Current model family is {selected_model_family.replace('_', ' ')}.")
    if rows_with_values > 0:
        parts.append(f"{rows_with_values} uploaded row(s) contribute observed measurement values.")
    if rows_with_labels > 0:
        parts.append(f"{rows_with_labels} row(s) contribute explicit or derived labels.")
    if label_source and label_source != "not_recorded":
        parts.append(f"Label source is recorded as {label_source.replace('_', ' ')}.")
    parts.append(
        f"The current representation is anchored on the {target_name} target contract, chemistry features, shortlist novelty context, and bounded session metadata."
    )

    limitation_bits = [
        "The current representation does not explicitly encode richer assay mechanism, protocol nuance, causal structure, or stronger cross-session scientific state."
    ]
    if training_scope == "baseline_bundle":
        limitation_bits.append(
            "Legacy baseline reuse means the representation can still reflect older bundle assumptions rather than only the current session."
        )
    if target_kind == "regression":
        limitation_bits.append(
            "Continuous-target ranking still compresses predicted value into ordering compatibility, which loses some representation detail."
        )
    missing_structure_summary = (
        "Missing structure still includes deeper assay context, mechanism-level representation, richer provenance-aware scientific state, and explicit independence structure between evidence sources."
    )

    return validate_predictive_representation_summary(
        {
            "feature_signature": feature_signature,
            "represented_inputs_summary": " ".join(bit for bit in parts if bit),
            "representation_limitations_summary": " ".join(bit for bit in limitation_bits if bit),
            "missing_structure_summary": missing_structure_summary,
        }
    )


def build_predictive_evaluation_contract(
    *,
    target_definition: dict[str, Any] | None = None,
    analysis_report: dict[str, Any] | None = None,
    evaluation_summary: dict[str, Any] | None = None,
    run_contract: dict[str, Any] | None = None,
    modeling_mode: str | None = None,
) -> dict[str, Any]:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    analysis_report = analysis_report if isinstance(analysis_report, dict) else {}
    evaluation_summary = evaluation_summary if isinstance(evaluation_summary, dict) else {}
    run_contract = run_contract if isinstance(run_contract, dict) else {}

    target_kind = _target_kind(target_definition, modeling_mode)
    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report.get("ranking_diagnostics"), dict) else {}
    offline_ranking_evaluation = (
        analysis_report.get("offline_ranking_evaluation")
        if isinstance(analysis_report.get("offline_ranking_evaluation"), dict)
        else {}
    )
    metrics = evaluation_summary.get("metrics") if isinstance(evaluation_summary.get("metrics"), dict) else {}
    holdout = metrics.get("holdout") if isinstance(metrics.get("holdout"), dict) else {}
    benchmark = evaluation_summary.get("benchmark") if isinstance(evaluation_summary.get("benchmark"), list) else []
    training_scope = _training_scope(run_contract, evaluation_summary)
    model_name = _selected_model_name(run_contract, evaluation_summary)

    tracked_metrics: list[str] = []
    benchmark_summary = "No saved benchmark sweep is available yet."
    ranking_metric_bits: list[str] = []
    evaluation_summary_text = "Evaluation coverage is still partial."

    if target_kind == "regression":
        for key in ("rmse", "mae", "r2"):
            if _safe_float(holdout.get(key)) is not None:
                tracked_metrics.append(f"holdout_{key}")
        spearman = _safe_float(holdout.get("spearman_rank_correlation"))
        if spearman is not None:
            tracked_metrics.append("holdout_spearman_rank_correlation")
        if tracked_metrics:
            evaluation_summary_text = (
                f"Saved regression evaluation currently centers on {', '.join(item.replace('_', ' ') for item in tracked_metrics)} for {model_name}."
            )
    else:
        for key in ("accuracy", "balanced_accuracy", "f1_macro", "brier_score", "log_loss"):
            if _safe_float(holdout.get(key)) is not None:
                tracked_metrics.append(f"holdout_{key}")
        if tracked_metrics:
            evaluation_summary_text = (
                f"Saved classification evaluation currently centers on {', '.join(item.replace('_', ' ') for item in tracked_metrics[:4])} for {model_name}."
            )

    if benchmark:
        benchmark_summary = f"{len(benchmark)} benchmark candidate configuration(s) were saved for model selection."

    spearman = _safe_float(ranking_diagnostics.get("spearman_rank_correlation"))
    if spearman is not None:
        ranking_metric_bits.append(f"Saved shortlist rank alignment is Spearman {spearman:.3f}.")
    predicted_corr = _safe_float(ranking_diagnostics.get("predicted_value_rank_correlation"))
    if predicted_corr is not None:
        ranking_metric_bits.append(f"Predicted-value rank alignment is {predicted_corr:.3f}.")
    top_k_lift = _safe_float(ranking_diagnostics.get("top_k_measurement_lift"))
    if top_k_lift is not None:
        ranking_metric_bits.append(f"Top-k measurement lift is {top_k_lift:.3f}.")
    if not ranking_metric_bits:
        ranking_metric_bits.append(
            "Saved ranking diagnostics are still limited, so future evaluation work should expand beyond current shortlist-level readouts."
        )

    candidate_separation_summary = _clean_text(offline_ranking_evaluation.get("candidate_separation_summary"))
    ranking_stability_summary = _clean_text(offline_ranking_evaluation.get("ranking_stability_summary"))
    closeness_band_summary = _clean_text(offline_ranking_evaluation.get("closeness_band_summary"))
    top_k_quality_summary = _clean_text(offline_ranking_evaluation.get("top_k_quality_summary"))
    heuristic_influence_summary = _clean_text(offline_ranking_evaluation.get("heuristic_influence_summary"))
    sensitivity_summary = _clean_text(offline_ranking_evaluation.get("sensitivity_summary"))
    calibration_awareness_summary = _clean_text(offline_ranking_evaluation.get("calibration_awareness_summary"))
    calibration_band_summary = _clean_text(offline_ranking_evaluation.get("calibration_band_summary"))
    comparison_cohort_summary = _clean_text(offline_ranking_evaluation.get("comparison_cohort_summary"))
    cohort_diagnostic_summary = _clean_text(offline_ranking_evaluation.get("cohort_diagnostic_summary"))
    evaluation_subset_summary = _clean_text(offline_ranking_evaluation.get("evaluation_subset_summary"))
    session_variation_summary = _clean_text(offline_ranking_evaluation.get("session_variation_summary"))
    cross_session_comparison_summary = _clean_text(offline_ranking_evaluation.get("cross_session_comparison_summary"))
    version_comparison_summary = _clean_text(offline_ranking_evaluation.get("version_comparison_summary"))
    representation_support_summary = _clean_text(offline_ranking_evaluation.get("representation_support_summary"))
    representation_evaluation_summary = _clean_text(offline_ranking_evaluation.get("representation_evaluation_summary"))
    representation_condition_summary = _clean_text(offline_ranking_evaluation.get("representation_condition_summary"))
    cross_run_comparison_summary = _clean_text(offline_ranking_evaluation.get("cross_run_comparison_summary"))
    engine_strength_summary = _clean_text(offline_ranking_evaluation.get("engine_strength_summary"))
    engine_weakness_summary = _clean_text(offline_ranking_evaluation.get("engine_weakness_summary"))
    if not closeness_band_summary:
        closeness_band_summary = "Closeness-band diagnostics are not fully recorded for this run yet."
    if not top_k_quality_summary:
        top_k_quality_summary = "Top-k quality remains only partly characterized for this run."
    if not calibration_awareness_summary:
        calibration_method = _clean_text(
            ((evaluation_summary.get("selected_model") or {}) if isinstance(evaluation_summary.get("selected_model"), dict) else {}).get("calibration_method")
        )
        if target_kind == "classification":
            if calibration_method:
                calibration_awareness_summary = (
                    f"Saved confidence uses {calibration_method} calibration, but it should still be read as signal-relative rather than as calibrated certainty."
                )
            else:
                calibration_awareness_summary = (
                    "Confidence should still be read as signal-relative rather than as calibrated certainty because saved calibration evidence is limited."
                )
        else:
            calibration_awareness_summary = (
                "Regression ranking compatibility is not a calibrated probability. It remains a bounded ordering signal."
            )
    if not calibration_band_summary:
        calibration_band_summary = (
            "Calibration-band evidence is still limited, so score strength should remain bounded and relative."
        )
    if not comparison_cohort_summary:
        comparison_cohort_summary = (
            f"Comparison cohort is currently bounded by {target_kind} ranking, {training_scope.replace('_', ' ')}, and {_clean_text(run_contract.get('feature_signature'), default='feature contract not recorded').replace('_', ' ')}."
        )
    if not session_variation_summary:
        session_variation_summary = (
            "Cross-session comparison is possible, but ranking reliability across session variation remains only partly established."
        )
    if not cohort_diagnostic_summary:
        cohort_diagnostic_summary = (
            "Reusable evaluation subsets are still limited, so later comparison work remains partly session-local."
        )
    if not evaluation_subset_summary:
        evaluation_subset_summary = (
            "Reusable evaluation subsets are still thin, so the current run remains only partly reusable for later comparison."
        )
    if not representation_evaluation_summary:
        representation_evaluation_summary = (
            "Representation-aware evaluation evidence is still limited, so coverage weakness is more visible than reusable."
        )
    if not representation_condition_summary:
        representation_condition_summary = (
            "Representation-conditioned evaluation remains bounded, so it is still difficult to say which coverage regimes are reliably stronger."
        )
    if not cross_session_comparison_summary:
        cross_session_comparison_summary = (
            "Cross-session comparison remains bounded by saved cohort anchors, target contract, and feature signature."
        )
    if not cross_run_comparison_summary:
        cross_run_comparison_summary = (
            "Cross-run comparison remains bounded by saved target, training-scope, and feature-contract anchors."
        )
    if not engine_strength_summary:
        engine_strength_summary = (
            "No strong reusable engine-strength pattern dominates yet."
        )
    if not engine_weakness_summary:
        engine_weakness_summary = (
            "No single reusable engine weakness dominates this run, though bounded caution still applies."
        )

    return validate_predictive_evaluation_contract(
        {
            "evaluation_ready": bool(
                tracked_metrics
                or ranking_metric_bits
                or training_scope == "baseline_bundle"
                or bool(offline_ranking_evaluation.get("evaluation_ready"))
            ),
            "evaluation_summary": evaluation_summary_text,
            "benchmark_summary": benchmark_summary,
            "ranking_metric_summary": " ".join(ranking_metric_bits),
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
            "tracked_metrics": tracked_metrics,
            "offline_ranking_evaluation": offline_ranking_evaluation,
        }
    )


def build_predictive_failure_mode_summary(
    *,
    target_definition: dict[str, Any] | None = None,
    analysis_report: dict[str, Any] | None = None,
    scientific_truth: dict[str, Any] | None = None,
    run_contract: dict[str, Any] | None = None,
    evaluation_contract: dict[str, Any] | None = None,
    modeling_mode: str | None = None,
) -> dict[str, Any]:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    analysis_report = analysis_report if isinstance(analysis_report, dict) else {}
    scientific_truth = scientific_truth if isinstance(scientific_truth, dict) else {}
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    evaluation_contract = evaluation_contract if isinstance(evaluation_contract, dict) else {}

    target_kind = _target_kind(target_definition, modeling_mode)
    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report.get("ranking_diagnostics"), dict) else {}
    offline_ranking_evaluation = (
        analysis_report.get("offline_ranking_evaluation")
        if isinstance(analysis_report.get("offline_ranking_evaluation"), dict)
        else {}
    )
    scientific_decision_summary = (
        scientific_truth.get("scientific_decision_summary")
        if isinstance(scientific_truth.get("scientific_decision_summary"), dict)
        else {}
    )
    measurement_summary = analysis_report.get("measurement_summary") if isinstance(analysis_report.get("measurement_summary"), dict) else {}
    training_scope = _clean_text(run_contract.get("training_scope"), default="not_recorded")

    failure_modes: list[str] = []
    if training_scope == "baseline_bundle":
        failure_modes.append("legacy baseline reuse can blur current-session signal")
    elif training_scope == "ranking_without_target_model":
        failure_modes.append("no target-specific model is available, so bridge-state policy carries more of the ranking burden")

    rows_with_values = _safe_int(measurement_summary.get("rows_with_values"))
    rows_with_labels = _safe_int(measurement_summary.get("rows_with_labels"))
    if target_kind == "regression" and rows_with_values < 12:
        failure_modes.append("continuous-target representation is still thin because measured rows are limited")
    if target_kind != "regression" and rows_with_labels < 12:
        failure_modes.append("classification representation is still thin because labeled rows are limited")

    failure_modes.append("heuristic shortlist policy still shapes ordering alongside model signal")

    spearman = _safe_float(ranking_diagnostics.get("spearman_rank_correlation"))
    if spearman is None:
        failure_modes.append("saved ranking-alignment evidence is still incomplete")
    elif spearman < 0.2:
        failure_modes.append("ranking alignment is weak enough that shortlist discrimination should be read cautiously")
    if _clean_text(offline_ranking_evaluation.get("candidate_separation_summary")) and "weak" in _clean_text(
        offline_ranking_evaluation.get("candidate_separation_summary")
    ).lower():
        failure_modes.append("candidate separation is still weak enough that the shortlist can flatten under small changes")
    if _clean_text(offline_ranking_evaluation.get("ranking_stability_summary")) and "fragile" in _clean_text(
        offline_ranking_evaluation.get("ranking_stability_summary")
    ).lower():
        failure_modes.append("top-of-shortlist ordering is still fragile under small score shifts")
    if _clean_text(offline_ranking_evaluation.get("closeness_band_summary")) and (
        "too close" in _clean_text(offline_ranking_evaluation.get("closeness_band_summary")).lower()
        or "weak-separation" in _clean_text(offline_ranking_evaluation.get("closeness_band_summary")).lower()
    ):
        failure_modes.append("part of the shortlist is too close to separate strongly")
    if _clean_text(offline_ranking_evaluation.get("top_k_quality_summary")) and "too flat" in _clean_text(
        offline_ranking_evaluation.get("top_k_quality_summary")
    ).lower():
        failure_modes.append("top-k shortlist quality remains too flat to support strong prioritization")
    if _clean_text(offline_ranking_evaluation.get("heuristic_influence_summary")) and "substantial" in _clean_text(
        offline_ranking_evaluation.get("heuristic_influence_summary")
    ).lower():
        failure_modes.append("heuristic policy still does substantial ordering work relative to raw predictive signal")
    if _clean_text(offline_ranking_evaluation.get("calibration_awareness_summary")) and "not calibrated" in _clean_text(
        offline_ranking_evaluation.get("calibration_awareness_summary")
    ).lower():
        failure_modes.append("confidence still should not be read as calibrated certainty")
    if _clean_text(offline_ranking_evaluation.get("calibration_band_summary")) and "do not yet map cleanly" in _clean_text(
        offline_ranking_evaluation.get("calibration_band_summary")
    ).lower():
        failure_modes.append("stronger score bands do not yet translate cleanly into stronger internal reliability")
    if _clean_text(offline_ranking_evaluation.get("evaluation_subset_summary")) and "thin" in _clean_text(
        offline_ranking_evaluation.get("evaluation_subset_summary")
    ).lower():
        failure_modes.append("reusable evaluation subsets remain thin for later comparison")
    if _clean_text(offline_ranking_evaluation.get("cross_session_comparison_summary")) and "bounded" in _clean_text(
        offline_ranking_evaluation.get("cross_session_comparison_summary")
    ).lower():
        failure_modes.append("cross-session comparison remains bounded by weak or partial anchors")
    if _clean_text(offline_ranking_evaluation.get("representation_evaluation_summary")) and "improves ranking quality" in _clean_text(
        offline_ranking_evaluation.get("representation_evaluation_summary")
    ).lower():
        failure_modes.append("representation-limited cohorts still weaken separation and uncertainty")
    if _clean_text(offline_ranking_evaluation.get("representation_condition_summary")) and "weaker ranking behavior" in _clean_text(
        offline_ranking_evaluation.get("representation_condition_summary")
    ).lower():
        failure_modes.append("representation-limited conditions remain a systematic ranking weakness")
    if _clean_text(offline_ranking_evaluation.get("engine_weakness_summary")):
        weakness_summary = _clean_text(offline_ranking_evaluation.get("engine_weakness_summary")).lower()
        if "heuristic-heavy" in weakness_summary:
            failure_modes.append("heuristic-heavy subsets remain a reusable weakness")
        if "representation-limited" in weakness_summary:
            failure_modes.append("representation-limited subsets remain a reusable weakness")

    top_k_lift = _safe_float(ranking_diagnostics.get("top_k_measurement_lift"))
    if top_k_lift is not None and top_k_lift <= 0:
        failure_modes.append("top-k shortlist lift is weak or negative")

    carryover_guardrail = _clean_text(scientific_decision_summary.get("carryover_guardrail_summary"))
    if carryover_guardrail:
        failure_modes.append("governance and carryover gates can still mask strong raw ranking signal")

    if not (evaluation_contract.get("tracked_metrics") if isinstance(evaluation_contract.get("tracked_metrics"), list) else []):
        failure_modes.append("saved evaluation coverage is still too narrow for stronger model iteration")

    dominant = failure_modes[0] if failure_modes else "bridge-state predictive weaknesses remain bounded but visible"
    summary_text = (
        "Current predictive failure modes remain inspectable: "
        + "; ".join(failure_modes[:4])
        + "."
        if failure_modes
        else "Current predictive failure modes are not yet strongly differentiated."
    )
    return validate_predictive_failure_mode_summary(
        {
            "summary_text": summary_text,
            "dominant_failure_mode": dominant,
            "failure_modes": failure_modes,
        }
    )


def build_predictive_path_summary(
    *,
    analysis_report: dict[str, Any] | None = None,
    decision_payload: dict[str, Any] | None = None,
    scientific_truth: dict[str, Any] | None = None,
    ranking_policy: dict[str, Any] | None = None,
    target_definition: dict[str, Any] | None = None,
    modeling_mode: str | None = None,
    run_contract: dict[str, Any] | None = None,
    evaluation_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analysis_report = analysis_report if isinstance(analysis_report, dict) else {}
    decision_payload = decision_payload if isinstance(decision_payload, dict) else {}
    scientific_truth = scientific_truth if isinstance(scientific_truth, dict) else {}
    ranking_policy = ranking_policy if isinstance(ranking_policy, dict) else {}
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    evaluation_summary = evaluation_summary if isinstance(evaluation_summary, dict) else {}

    target_kind = _target_kind(target_definition, modeling_mode)
    target_name = _target_name(target_definition)
    belief_state_summary = scientific_truth.get("belief_state_summary") if isinstance(scientific_truth.get("belief_state_summary"), dict) else {}
    scientific_decision_summary = scientific_truth.get("scientific_decision_summary") if isinstance(scientific_truth.get("scientific_decision_summary"), dict) else {}
    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report.get("ranking_diagnostics"), dict) else {}

    task_contract = run_contract.get("predictive_task_contract") if isinstance(run_contract.get("predictive_task_contract"), dict) else {}
    if not task_contract:
        task_contract = build_predictive_task_contract(
            target_definition=target_definition,
            ranking_policy=ranking_policy,
            run_contract=run_contract,
            scientific_truth=scientific_truth,
            modeling_mode=modeling_mode,
        )

    representation_summary = run_contract.get("predictive_representation_summary") if isinstance(run_contract.get("predictive_representation_summary"), dict) else {}
    if not representation_summary:
        representation_summary = build_predictive_representation_summary(
            target_definition=target_definition,
            run_contract=run_contract,
            analysis_report=analysis_report,
            modeling_mode=modeling_mode,
        )

    evaluation_contract = build_predictive_evaluation_contract(
        target_definition=target_definition,
        analysis_report=analysis_report,
        evaluation_summary=evaluation_summary,
        run_contract=run_contract,
        modeling_mode=modeling_mode,
    )

    failure_mode_summary = build_predictive_failure_mode_summary(
        target_definition=target_definition,
        analysis_report=analysis_report,
        scientific_truth=scientific_truth,
        run_contract=run_contract,
        evaluation_contract=evaluation_contract,
        modeling_mode=modeling_mode,
    )

    model_logic_summary = _clean_text(ranking_policy.get("formula_text"))
    if not model_logic_summary:
        if target_kind == "regression":
            model_logic_summary = (
                f"The current path uses model-produced ranking compatibility and prediction dispersion to order candidates for {target_name}; it does not yet expose a mature representation-first predictive core."
            )
        else:
            model_logic_summary = (
                f"The current path uses model-produced confidence, uncertainty, novelty, and experiment-value signals to order candidates for {target_name}, but still inside a bounded shortlist policy."
            )

    heuristic_bits: list[str] = []
    if _clean_text(ranking_policy.get("formula_summary")):
        heuristic_bits.append(_clean_text(ranking_policy.get("formula_summary")))
    if ranking_diagnostics.get("score_basis"):
        heuristic_bits.append(f"Saved score basis: {_clean_text(ranking_diagnostics.get('score_basis')).replace('_', ' ')}.")
    heuristic_bits.append(
        "Selection buckets, bounded score thresholds, and current policy intent still shape the shortlist alongside model scores."
    )
    heuristic_logic_summary = " ".join(bit for bit in heuristic_bits if bit)

    governance_influence_summary = " ".join(
        bit
        for bit in [
            _clean_text(scientific_decision_summary.get("decision_status_summary")),
            _clean_text(scientific_decision_summary.get("carryover_guardrail_summary")),
            _clean_text(scientific_decision_summary.get("session_family_review_status_summary")),
            _clean_text(task_contract.get("governance_interaction_summary")),
        ]
        if bit
    )
    if not governance_influence_summary:
        governance_influence_summary = (
            "Trust, review posture, and broader carryover boundaries still influence how far the shortlist should travel, even when ranking output is available."
        )

    representation_input_summary = _clean_text(representation_summary.get("represented_inputs_summary"))
    if not representation_input_summary:
        representation_input_summary = (
            "Representation inputs are still mainly session upload structure, target contract, shortlist scores, and bridge-state governance summaries."
        )

    weakness_bits: list[str] = []
    weakness_bits.append(_clean_text(representation_summary.get("representation_limitations_summary")))
    if _clean_text(belief_state_summary.get("support_coherence_summary")):
        weakness_bits.append(_clean_text(belief_state_summary.get("support_coherence_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("ranking_metric_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("candidate_separation_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("ranking_stability_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("closeness_band_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("heuristic_influence_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("sensitivity_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("calibration_awareness_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("session_variation_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("evaluation_subset_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("cross_session_comparison_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("representation_support_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("representation_evaluation_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("representation_condition_summary")))
    weakness_bits.append(_clean_text(evaluation_contract.get("engine_weakness_summary")))
    weakness_bits.append(_clean_text(failure_mode_summary.get("summary_text")))
    weakness_summary = " ".join(bit for bit in weakness_bits if bit)

    final_ordering_summary = _clean_text(task_contract.get("final_ordering_summary"))
    if not final_ordering_summary:
        final_ordering_summary = (
            "Final user-facing ordering still mixes raw predictive signal, heuristic shortlist policy, and governance boundaries."
        )

    tracked_metrics = evaluation_contract.get("tracked_metrics") if isinstance(evaluation_contract.get("tracked_metrics"), list) else []
    model_signal_summary = (
        _clean_text(task_contract.get("predictive_score_summary"))
        or model_logic_summary
    )
    offline_ranking_evaluation = (
        analysis_report.get("offline_ranking_evaluation")
        if isinstance(analysis_report.get("offline_ranking_evaluation"), dict)
        else {}
    )
    if _clean_text(offline_ranking_evaluation.get("heuristic_influence_summary")):
        heuristic_logic_summary = (
            f"{heuristic_logic_summary} {_clean_text(offline_ranking_evaluation.get('heuristic_influence_summary'))}"
        ).strip()
    if _clean_text(offline_ranking_evaluation.get("candidate_separation_summary")):
        final_ordering_summary = (
            f"{final_ordering_summary} {_clean_text(offline_ranking_evaluation.get('candidate_separation_summary'))}"
        ).strip()
    if _clean_text(offline_ranking_evaluation.get("engine_strength_summary")):
        model_signal_summary = (
            f"{model_signal_summary} {_clean_text(offline_ranking_evaluation.get('engine_strength_summary'))}"
        ).strip()
    if _clean_text(offline_ranking_evaluation.get("engine_weakness_summary")):
        weakness_summary = (
            f"{weakness_summary} {_clean_text(offline_ranking_evaluation.get('engine_weakness_summary'))}"
        ).strip()
    summary_text = (
        "Current predictive task is now explicit: bounded candidate prioritization for what to test next, with raw model signal, heuristic shortlist policy, and governance gates kept inspectable as separate layers."
    )
    if not tracked_metrics and _training_scope(run_contract, evaluation_summary) == "ranking_without_target_model":
        summary_text = (
            "Current predictive task is explicit, but the path still leans heavily on heuristic prioritization because no target-specific model is available for this session."
        )

    readiness_note = (
        "The predictive path is now explicit enough to inspect candidate prioritization, representation limits, model-vs-policy separation, reusable comparison cohorts, and evaluation gaps. The next phase should strengthen deeper representation/evaluation evidence rather than add more shell semantics."
    )

    next_phase_entry_criteria = [
        "Predictive task and score semantics are explicit enough to compare future ranking changes honestly.",
        "Model signal, heuristic shortlist policy, and governance gates are separated enough to debug which layer is driving a weakness.",
        "Evaluation and failure-mode surfaces are concrete enough to measure predictive improvements rather than only describe architecture.",
    ]

    return validate_predictive_path_summary(
        {
            "summary_text": summary_text,
            "ranking_driver_summary": _weight_driver_summary(ranking_policy, target_kind=target_kind),
            "model_logic_summary": model_logic_summary,
            "model_signal_summary": model_signal_summary,
            "heuristic_logic_summary": heuristic_logic_summary,
            "governance_influence_summary": governance_influence_summary,
            "final_ordering_summary": final_ordering_summary,
            "representation_input_summary": representation_input_summary,
            "weakness_summary": weakness_summary,
            "readiness_note": readiness_note,
            "next_phase_entry_criteria": next_phase_entry_criteria,
            "task_contract": task_contract,
            "representation_summary": representation_summary,
            "evaluation_contract": evaluation_contract,
            "failure_mode_summary": failure_mode_summary,
        }
    )


__all__ = [
    "build_predictive_evaluation_contract",
    "build_predictive_failure_mode_summary",
    "build_predictive_path_summary",
    "build_predictive_representation_summary",
    "build_predictive_task_contract",
]
