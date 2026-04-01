from __future__ import annotations

from typing import Any

import pandas as pd


SCORE_LABELS = {
    "confidence": "Confidence",
    "uncertainty": "Uncertainty",
    "novelty": "Novelty",
    "experiment_value": "Experiment value",
    "priority_score": "Priority score",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: Any) -> float:
    return max(0.0, min(1.0, _safe_float(value)))


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _with_session_context(df: pd.DataFrame) -> pd.DataFrame:
    contextual = df.copy()
    session_size = int(len(contextual))
    contextual["session_candidate_count"] = session_size

    if session_size == 0:
        return contextual

    percentile_columns = (
        "confidence",
        "uncertainty",
        "novelty",
        "experiment_value",
        "priority_score",
        "max_similarity",
    )
    for column in percentile_columns:
        target_column = f"{column}_percentile"
        if column not in contextual.columns:
            contextual[target_column] = 0.0
            continue
        values = pd.to_numeric(contextual[column], errors="coerce")
        if values.notna().any():
            contextual[target_column] = values.rank(method="average", pct=True).fillna(0.0)
        else:
            contextual[target_column] = 0.0

    if "priority_score" in contextual.columns:
        priority_values = pd.to_numeric(contextual["priority_score"], errors="coerce").fillna(0.0)
        contextual["priority_rank"] = priority_values.rank(method="first", ascending=False).astype(int)
    else:
        contextual["priority_rank"] = pd.Series(range(1, session_size + 1), index=contextual.index)
    return contextual


def _within_run_readout(percentile: float, *, direction: str = "higher") -> str:
    bounded = max(0.0, min(1.0, percentile))
    if direction == "lower":
        return f"lower than {int(round((1.0 - bounded) * 100))}% of scored candidates in this run"
    return f"higher than {int(round(bounded * 100))}% of scored candidates in this run"


def _score_position_line(label: str, percentile: Any, *, direction: str = "higher") -> str:
    return f"{label} is {_within_run_readout(_safe_float(percentile), direction=direction)}."


def _session_context_lines(
    row,
    *,
    bucket: str,
    confidence: float,
    uncertainty: float,
    novelty: float,
) -> list[str]:
    session_size = int(_safe_float(row.get("session_candidate_count"), default=0.0) or 0)
    if session_size <= 1:
        return ["This is currently the only scored candidate in the session, so the recommendation is based on absolute signals rather than run-relative ranking."]

    priority_rank = max(int(_safe_float(row.get("priority_rank"), default=1.0) or 1), 1)
    priority_total = max(session_size, 1)
    lines = [
        f"Priority score ranks #{priority_rank} out of {priority_total} scored candidates in this run.",
        _score_position_line("Priority score", row.get("priority_score_percentile")),
    ]

    if bucket == "learn" or uncertainty >= 0.65:
        lines.append(_score_position_line("Uncertainty", row.get("uncertainty_percentile")))
    else:
        lines.append(_score_position_line("Uncertainty", row.get("uncertainty_percentile"), direction="lower"))

    confidence_line = _score_position_line("Confidence", row.get("confidence_percentile"))
    novelty_line = _score_position_line("Novelty", row.get("novelty_percentile"))
    experiment_line = _score_position_line("Experiment value", row.get("experiment_value_percentile"))

    if confidence >= 0.7:
        lines.append(confidence_line)
    elif novelty >= 0.6:
        lines.append(novelty_line)
    else:
        lines.append(experiment_line)

    return lines[:3]


def _score_breakdown(row) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in ("confidence", "uncertainty", "novelty", "experiment_value"):
        raw_value = _clamp_score(row.get(key))
        weight = max(_safe_float(row.get(f"priority_weight_{key}")), 0.0)
        contribution = max(_safe_float(row.get(f"priority_component_{key}")), 0.0)
        items.append(
            {
                "key": key,
                "label": SCORE_LABELS[key],
                "raw_value": raw_value,
                "weight": weight,
                "weight_percent": round(weight * 100.0, 1),
                "contribution": contribution,
            }
        )
    return items


def _domain_context(max_similarity: Any) -> dict[str, Any]:
    try:
        similarity = float(max_similarity)
    except (TypeError, ValueError):
        return {
            "status": "unknown",
            "label": "Domain coverage unavailable",
            "summary": "Reference-similarity diagnostics were not saved for this candidate.",
        }

    if similarity < 0.25:
        return {
            "status": "out_of_domain",
            "label": "Outside strong chemistry range",
            "summary": "Reference similarity is low, so the model signal is less transferable and should be challenged carefully.",
        }
    if similarity < 0.45:
        return {
            "status": "near_boundary",
            "label": "Near the edge of domain coverage",
            "summary": "Similarity is moderate, so the ranking is still useful but should not be treated as a near-certain read.",
        }
    return {
        "status": "in_domain",
        "label": "Within stronger chemistry range",
        "summary": "Reference similarity is strong enough to support more confident near-term review.",
    }


def _recommended_action(bucket: str, confidence: float, uncertainty: float, novelty: float, domain_status: str) -> str:
    if bucket == "learn" or uncertainty >= 0.65:
        return "Use this as a learning candidate to reduce uncertainty before overcommitting bench time."
    if bucket == "explore" or novelty >= 0.65:
        return "Use this as an exploration candidate to widen chemistry coverage before committing to a lead series."
    if bucket == "exploit" and confidence >= 0.75 and domain_status != "out_of_domain":
        return "Use this as a near-term testing candidate because the signal is relatively stable."
    if domain_status == "out_of_domain":
        return "Review this with extra caution before testing because domain coverage is weak."
    return "Keep this in expert review before moving it into the next testing round."


def _trust_label(
    *,
    confidence: float,
    uncertainty: float,
    novelty: float,
    domain_status: str,
    measurement_value: float | None,
) -> tuple[str, str]:
    if domain_status == "out_of_domain" or uncertainty >= 0.75:
        return (
            "High caution",
            "The recommendation is still useful, but uncertainty or weak domain coverage means it should not be treated as a stable prediction.",
        )
    if confidence >= 0.8 and uncertainty <= 0.25 and domain_status == "in_domain":
        return (
            "Stronger trust",
            "The model signal is relatively stable and sits within stronger chemistry coverage, so this is suitable for near-term review.",
        )
    if novelty >= 0.65 or domain_status == "edge_of_domain":
        return (
            "Exploratory trust",
            "The ranking is useful for exploration, but novelty and edge-of-domain behavior mean the result should be validated deliberately.",
        )
    if measurement_value is not None:
        return (
            "Measured cross-check available",
            "An uploaded observed value is available, so the shortlist can be challenged directly against measured evidence.",
        )
    return (
        "Mixed trust",
        "The shortlist is useful for prioritization, but the recommendation still needs scientist review before it becomes a testing commitment.",
    )


def _dominant_component(breakdown: list[dict[str, Any]]) -> dict[str, Any]:
    if not breakdown:
        return {"key": "experiment_value", "label": "Experiment value", "contribution": 0.0}
    return max(breakdown, key=lambda item: float(item.get("contribution", 0.0)))


def candidate_rationale(row) -> dict[str, Any]:
    bucket = _clean_text(row.get("selection_bucket") or row.get("bucket")).lower()
    confidence = _clamp_score(row.get("confidence"))
    uncertainty = _clamp_score(row.get("uncertainty"))
    novelty = _clamp_score(row.get("novelty"))
    target_definition = row.get("target_definition") if isinstance(row.get("target_definition"), dict) else {}
    target_name = _clean_text(target_definition.get("target_name") or row.get("target"))
    target_kind = _clean_text(target_definition.get("target_kind") or "classification")
    measurement_value = row.get("value")
    try:
        measurement_value = float(measurement_value)
    except (TypeError, ValueError):
        measurement_value = None
    assay = _clean_text(row.get("assay"))
    target = _clean_text(row.get("target"))

    breakdown = _score_breakdown(row)
    dominant = _dominant_component(breakdown)
    domain = _domain_context(row.get("max_similarity"))
    session_context = _session_context_lines(
        row,
        bucket=bucket,
        confidence=confidence,
        uncertainty=uncertainty,
        novelty=novelty,
    )
    recommended_action = _recommended_action(bucket, confidence, uncertainty, novelty, str(domain["status"]))
    trust_label, trust_summary = _trust_label(
        confidence=confidence,
        uncertainty=uncertainty,
        novelty=novelty,
        domain_status=str(domain["status"]),
        measurement_value=measurement_value,
    )

    driver_label = str(dominant.get("label") or "Experiment value")
    priority_rank = max(int(_safe_float(row.get("priority_rank"), default=1.0) or 1), 1)
    session_size = max(int(_safe_float(row.get("session_candidate_count"), default=1.0) or 1), 1)
    if dominant.get("key") == "uncertainty":
        summary = f"This candidate is being prioritized mainly for learning value because uncertainty is carrying a large share of the score, and it ranks #{priority_rank} out of {session_size} by priority score in this run."
    elif dominant.get("key") == "novelty":
        summary = f"This candidate is being prioritized mainly because novelty is expanding chemistry coverage beyond the current reference set, and it ranks #{priority_rank} out of {session_size} by priority score in this run."
    elif target_kind == "regression" and row.get("predicted_value") is not None:
        summary = (
            f"This candidate is being prioritized for {target_name or 'the session target'} because the model predicts "
            f"{float(row.get('predicted_value')):.3f} and it ranks #{priority_rank} out of {session_size} by priority score in this run."
        )
    elif dominant.get("key") == "confidence":
        summary = f"This candidate is being prioritized mainly because confidence is carrying the current shortlist position, and it ranks #{priority_rank} out of {session_size} by priority score in this run."
    else:
        summary = f"This candidate is being prioritized mainly because experiment value is carrying the current shortlist position, and it ranks #{priority_rank} out of {session_size} by priority score in this run."

    driver_percentile = row.get(f"{str(dominant.get('key') or 'experiment_value')}_percentile")
    if dominant.get("key") == "uncertainty":
        why_now = f"{driver_label} is the largest contributor to the current priority score, and uncertainty is {_within_run_readout(_safe_float(driver_percentile))}."
    else:
        why_now = f"{driver_label} is the largest contributor to the current priority score, and it is {_within_run_readout(_safe_float(driver_percentile))}."

    strengths: list[str] = []
    cautions: list[str] = []

    if target_kind == "regression" and row.get("predicted_value") is not None:
        strengths.append(
            f"Predicted {target_name or 'target'} value is {float(row.get('predicted_value')):.3f}."
        )
    elif confidence >= 0.8:
        strengths.append(f"Confidence is relatively strong at {confidence:.3f}.")
    elif confidence <= 0.35:
        cautions.append(f"Confidence is low at {confidence:.3f}, so treat the recommendation as exploratory.")

    if uncertainty >= 0.65:
        cautions.append(f"Uncertainty remains high at {uncertainty:.3f}, so this is more useful for learning than confirmation.")
    elif uncertainty <= 0.25:
        strengths.append(f"Uncertainty is relatively controlled at {uncertainty:.3f}.")

    if novelty >= 0.65:
        strengths.append(f"Novelty is high at {novelty:.3f}, which expands chemistry coverage.")
    elif novelty <= 0.25:
        strengths.append(f"Novelty is low at {novelty:.3f}, which keeps the candidate closer to known chemistry.")

    strengths.append(str(domain["summary"]))
    strengths.extend(line for line in session_context if line not in strengths)

    if measurement_value is not None:
        if assay:
            strengths.append(f"Uploaded observed value {measurement_value:.3f} is available for {assay} cross-checking.")
        else:
            strengths.append(f"Uploaded observed value {measurement_value:.3f} is available for direct cross-checking.")
    else:
        cautions.append("No uploaded observed value is available for direct cross-checking in this session.")

    if assay or target:
        context_bits = [part for part in (assay, target) if part]
        strengths.append(f"Scientific context from the upload: {', '.join(context_bits)}.")

    if str(domain["status"]) == "out_of_domain":
        cautions.append("This molecule sits outside stronger chemistry coverage, so transferability is weaker.")
    elif str(domain["status"]) == "near_boundary":
        cautions.append("This molecule sits near the edge of stronger chemistry coverage.")

    evidence_lines = [summary, why_now] + session_context[:2]
    for line in strengths:
        if line not in evidence_lines:
            evidence_lines.append(line)
    if cautions:
        evidence_lines.append(cautions[0])

    return {
        "summary": summary,
        "why_now": why_now,
        "trust_label": trust_label,
        "trust_summary": trust_summary,
        "recommended_action": recommended_action,
        "primary_driver": str(dominant.get("key") or "experiment_value"),
        "session_context": session_context[:3],
        "strengths": strengths[:4],
        "cautions": cautions[:4],
        "evidence_lines": evidence_lines[:5],
    }


def candidate_explanation_lines(row) -> list[str]:
    rationale = candidate_rationale(row)
    lines = [str(item).strip() for item in rationale.get("evidence_lines", []) if str(item).strip()]
    if not lines:
        return ["Recommendation details unavailable."]
    return lines


def candidate_short_explanation(row) -> str:
    rationale = candidate_rationale(row)
    summary = _clean_text(rationale.get("summary"))
    return summary or "Recommendation details unavailable."


def add_candidate_explanations(df: pd.DataFrame, target_definition: dict[str, Any] | None = None) -> pd.DataFrame:
    explained = _with_session_context(df.copy())
    if target_definition:
        explained["target_definition"] = [target_definition for _ in range(len(explained))]
    explained["score_breakdown"] = explained.apply(_score_breakdown, axis=1)
    explained["rationale"] = explained.apply(candidate_rationale, axis=1)
    explained["explanation"] = explained["rationale"].apply(
        lambda rationale: rationale.get("evidence_lines") or [rationale.get("summary") or "Recommendation details unavailable."]
    )
    explained["short_explanation"] = explained["rationale"].apply(
        lambda rationale: _clean_text(rationale.get("summary")) or "Recommendation details unavailable."
    )
    explained["trust_label"] = explained["rationale"].apply(lambda rationale: _clean_text(rationale.get("trust_label")))
    if "max_similarity" in explained.columns:
        explained["domain_status"] = explained["max_similarity"].apply(lambda value: _domain_context(value)["status"])
        explained["domain_label"] = explained["max_similarity"].apply(lambda value: _domain_context(value)["label"])
        explained["domain_summary"] = explained["max_similarity"].apply(lambda value: _domain_context(value)["summary"])
    else:
        explained["domain_status"] = "unknown"
        explained["domain_label"] = "Domain coverage unavailable"
        explained["domain_summary"] = "Reference-similarity diagnostics were not saved for this candidate."
    return explained
