from __future__ import annotations

from typing import Any

from system.contracts import (
    DatasetType,
    validate_decision_policy_trace,
    validate_model_judgment,
    validate_normalized_explanation,
    validate_novelty_signal,
    validate_scientific_recommendation,
)


def build_novelty_signal(row) -> dict[str, Any]:
    novelty = row.get("novelty")
    max_similarity = row.get("max_similarity")
    batch_similarity = row.get("batch_similarity")
    summary = "Structural novelty could not be estimated."
    try:
        novelty_value = float(novelty)
    except (TypeError, ValueError):
        novelty_value = None
    if novelty_value is not None:
        if novelty_value >= 0.65:
            summary = "This candidate is structurally novel relative to the reference chemistry set."
        elif novelty_value <= 0.25:
            summary = "This candidate stays relatively close to known chemistry."
        else:
            summary = "This candidate adds some structural novelty without leaving known chemistry entirely."
    return validate_novelty_signal(
        {
            "novelty_score": novelty_value,
            "reference_similarity": max_similarity,
            "batch_similarity": batch_similarity,
            "summary": summary,
        }
    )


def build_model_judgment(row, *, target_definition: dict[str, Any] | None) -> dict[str, Any]:
    target_definition = target_definition or {}
    target_kind = str(target_definition.get("target_kind") or "classification")

    predicted_label = None
    if target_kind == "classification":
        try:
            predicted_label = int(float(row.get("predicted_label", row.get("confidence", 0.0))) >= 0.5)
        except (TypeError, ValueError):
            predicted_label = None

    if target_kind == "regression":
        model_summary = "The model produced a continuous target prediction and a dispersion-based uncertainty estimate."
    else:
        model_summary = "The model produced a positive-class probability estimate and a probability-based uncertainty score."

    return validate_model_judgment(
        {
            "target_kind": target_kind,
            "predicted_label": predicted_label,
            "positive_class_name": str(target_definition.get("target_name") or "positive class"),
            "confidence": row.get("confidence"),
            "uncertainty": row.get("uncertainty"),
            "uncertainty_kind": row.get("uncertainty_kind")
            or ("ensemble_prediction_std" if target_kind == "regression" else "probability_distance_from_boundary"),
            "predicted_value": row.get("predicted_value"),
            "prediction_dispersion": row.get("prediction_dispersion"),
            "model_summary": model_summary,
        }
    )


def build_decision_policy(row) -> dict[str, Any]:
    bucket = row.get("bucket") or row.get("selection_bucket")
    priority_score = row.get("priority_score")
    experiment_value = row.get("experiment_value")
    acquisition_score = row.get("final_score", row.get("acquisition_score"))
    if bucket == "learn":
        summary = "The decision policy is prioritizing this candidate because it is informative for reducing model uncertainty."
    elif bucket == "explore":
        summary = "The decision policy is prioritizing this candidate because it broadens chemistry coverage."
    elif bucket == "exploit":
        summary = "The decision policy is prioritizing this candidate for near-term testing based on current score stability."
    else:
        summary = "The decision policy is using the current weighted shortlist score to order this candidate."
    return validate_decision_policy_trace(
        {
            "bucket": bucket,
            "priority_score": priority_score,
            "acquisition_score": acquisition_score,
            "experiment_value": experiment_value,
            "selection_reason": row.get("selection_reason") or "",
            "policy_summary": summary,
        }
    )


def build_scientific_recommendation(row, *, rationale: dict[str, Any] | None = None) -> dict[str, Any]:
    rationale = rationale or {}
    cautions = list(rationale.get("cautions") or [])
    return validate_scientific_recommendation(
        {
            "recommended_action": rationale.get("recommended_action") or row.get("selection_reason") or "Review before testing.",
            "summary": rationale.get("summary") or "Recommendation details unavailable.",
            "follow_up_experiment": rationale.get("recommended_action") or "Review and confirm experimentally.",
            "trust_cautions": cautions,
        }
    )


def build_normalized_explanation(
    row,
    *,
    rationale: dict[str, Any] | None,
    target_definition: dict[str, Any] | None,
    model_judgment: dict[str, Any],
    decision_policy: dict[str, Any],
) -> dict[str, Any]:
    rationale = rationale or {}
    target_name = str((target_definition or {}).get("target_name") or "the session target")
    target_kind = str((target_definition or {}).get("target_kind") or "classification")

    if target_kind == "regression":
        prediction_text = (
            f"The model predicts a continuous value of {float(row.get('predicted_value')):.3f} for {target_name}."
            if row.get("predicted_value") is not None
            else f"The model did not produce a usable continuous prediction for {target_name}."
        )
    else:
        if row.get("confidence") is None:
            prediction_text = f"The model did not produce a usable classification confidence for {target_name}."
        else:
            prediction_text = (
                f"The model estimates a positive-class probability of {float(row.get('confidence')):.3f} for {target_name}."
            )

    uncertainty_text = (
        f"Uncertainty is {float(row.get('uncertainty')):.3f}."
        if row.get("uncertainty") is not None
        else "Uncertainty was not available for this candidate."
    )
    novelty_text = str((model_judgment.get("novelty_signal") or {}).get("summary") or "Novelty support was not available.")

    return validate_normalized_explanation(
        {
            "why_this_candidate": rationale.get("summary") or "This candidate is included because it remains competitive under the current decision policy.",
            "why_now": rationale.get("why_now") or str(decision_policy.get("policy_summary") or ""),
            "supporting_evidence": rationale.get("evidence_lines") or [],
            "model_judgment_summary": prediction_text,
            "uncertainty_summary": uncertainty_text,
            "novelty_summary": novelty_text,
            "decision_policy_reason": str(decision_policy.get("policy_summary") or ""),
            "recommended_followup": rationale.get("recommended_action") or "Review and confirm experimentally.",
            "trust_cautions": rationale.get("cautions") or [],
        }
    )


def scientific_data_facts(row, *, target_definition: dict[str, Any] | None, source_name: str) -> dict[str, Any]:
    target_definition = target_definition or {}
    return {
        "observed_value": row.get("observed_value", row.get("value")),
        "measurement_column": target_definition.get("measurement_column") or "",
        "label_column": target_definition.get("label_column") or "",
        "dataset_type": target_definition.get("dataset_type") or DatasetType.structure_only.value,
        "assay": row.get("assay") or "",
        "target": row.get("target") or target_definition.get("target_name") or "",
        "source_name": source_name,
    }


__all__ = [
    "build_decision_policy",
    "build_model_judgment",
    "build_normalized_explanation",
    "build_novelty_signal",
    "build_scientific_recommendation",
    "scientific_data_facts",
]
