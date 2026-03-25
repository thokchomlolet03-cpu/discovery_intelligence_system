from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean
from typing import Any

from system.review_manager import STATUS_ORDER, normalize_status


BUCKET_ORDER = {"exploit": 0, "learn": 1, "explore": 2}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: Any) -> float:
    return max(0.0, min(1.0, _safe_float(value)))


def _to_iso(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        target = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return target.isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    text = str(value).strip()
    if not text:
        return ""
    try:
        target = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return target.astimezone(timezone.utc).isoformat() if target.tzinfo else target.replace(tzinfo=timezone.utc).isoformat()


def humanize_timestamp(value: Any) -> str:
    iso_value = _to_iso(value)
    if not iso_value:
        return "Not available"
    try:
        target = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return target.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def derive_risk(confidence: Any, uncertainty: Any, risk: Any = None) -> str:
    cleaned = str(risk or "").strip().lower()
    if cleaned in RISK_ORDER:
        return cleaned

    uncertainty_value = _clamp_score(uncertainty)
    confidence_value = _clamp_score(confidence)
    if uncertainty_value > 0.7:
        return "high"
    if confidence_value > 0.8 and uncertainty_value < 0.2:
        return "low"
    return "medium"


def derive_bucket(bucket: Any, confidence: Any, uncertainty: Any, novelty: Any) -> str:
    cleaned = str(bucket or "").strip().lower()
    if cleaned in BUCKET_ORDER:
        return cleaned
    uncertainty_value = _clamp_score(uncertainty)
    novelty_value = _clamp_score(novelty)
    confidence_value = _clamp_score(confidence)
    if uncertainty_value >= 0.65:
        return "learn"
    if novelty_value >= 0.65:
        return "explore"
    if confidence_value >= 0.75:
        return "exploit"
    return "learn"


def _clean_explanation_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [segment.strip() for segment in value.split("\n") if segment.strip()]
    return []


def fallback_explanation(bucket: str, confidence: float, uncertainty: float, novelty: float, risk: str) -> list[str]:
    lines: list[str] = []

    if bucket == "learn" or uncertainty >= 0.65:
        lines.append("High uncertainty makes this a strong learning candidate for reducing model blind spots.")
    elif bucket == "explore" or novelty >= 0.65:
        lines.append("High novelty makes this a useful exploration candidate for expanding chemical coverage.")
    elif bucket == "exploit" or confidence >= 0.75:
        lines.append("High confidence makes this a practical exploit candidate for near-term review.")
    else:
        lines.append("Balanced scores make this a reasonable candidate for expert review.")

    if novelty >= 0.55:
        lines.append("Novel relative to known chemistry and useful for widening the search space.")
    if 0.35 <= confidence <= 0.75:
        lines.append("Moderate confidence suggests informative experimental value without overclaiming certainty.")
    if risk == "high":
        lines.append("Requires careful review because model uncertainty remains elevated.")
    elif risk == "low":
        lines.append("Low inferred risk suggests the model is relatively consistent on this candidate.")

    return lines


def normalize_explanations(
    explanation: Any,
    bucket: str,
    confidence: float,
    uncertainty: float,
    novelty: float,
    risk: str,
) -> list[str]:
    cleaned = _clean_explanation_lines(explanation)
    return cleaned or fallback_explanation(bucket, confidence, uncertainty, novelty, risk)


def normalize_review_history(history: Any) -> list[dict[str, Any]]:
    if not isinstance(history, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        reviewed_at = _to_iso(item.get("reviewed_at") or item.get("timestamp"))
        normalized.append(
            {
                "action": str(item.get("action") or "later"),
                "status": normalize_status(item.get("status"), action=item.get("action")),
                "note": str(item.get("note") or "").strip(),
                "reviewer": str(item.get("reviewer") or "unassigned"),
                "reviewed_at": reviewed_at,
                "reviewed_at_label": humanize_timestamp(reviewed_at),
            }
        )
    return sorted(normalized, key=lambda item: item["reviewed_at"])


def infer_source_type(candidate: dict[str, Any], provenance_text: str) -> str:
    source_smiles = str(candidate.get("source_smiles") or "").strip()
    source = str(candidate.get("source") or "").strip()
    text = provenance_text.lower()
    if source_smiles or "generated" in text:
        return "generated"
    if source or "uploaded" in text:
        return "uploaded"
    if candidate.get("molecule_id"):
        return "derived"
    return "not available"


def compact_provenance(source_type: str, iteration: int, model_version: str, parent: str) -> str:
    parts = [source_type.title() if source_type != "not available" else "Not available", f"Iteration {iteration}"]
    if parent:
        parts.append(f"From {parent}")
    if model_version:
        parts.append(f"Model {model_version}")
    return " / ".join(parts)


def suggested_next_action(bucket: str, risk: str, confidence: float, uncertainty: float) -> str:
    if bucket == "learn" or uncertainty >= 0.7:
        return "Best used as a learning candidate because the model remains uncertain."
    if bucket == "exploit" or (confidence >= 0.8 and uncertainty <= 0.2):
        return "Good exploit candidate because confidence is high and uncertainty is controlled."
    if risk == "high":
        return "Requires careful review before testing because the current risk signal is elevated."
    return "Useful review candidate for the next testing round after chemist inspection."


def resolve_model_version(
    evaluation_summary: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    system_version: str,
) -> str:
    if isinstance(evaluation_summary, dict):
        selected = evaluation_summary.get("selected_model")
        if isinstance(selected, dict):
            name = str(selected.get("name") or "").strip()
            method = str(selected.get("calibration_method") or "").strip()
            if name and method:
                return f"{name}:{method}"
            if name:
                return name

    for candidate in candidates:
        label = str(candidate.get("model_version") or "").strip()
        if label:
            return label
    return f"system-{system_version}"


def resolve_dataset_version(session_id: str | None, decision_output: dict[str, Any]) -> str:
    if session_id:
        return f"session_{session_id}"
    explicit = str(decision_output.get("dataset_version") or "").strip()
    if explicit:
        return explicit
    source_path = str(decision_output.get("source_path") or "").strip()
    if source_path:
        return source_path.replace("/", "_")
    return "public_snapshot"


def normalize_candidate(
    candidate: dict[str, Any],
    *,
    position: int,
    iteration: int,
    model_version: str,
    dataset_version: str,
) -> dict[str, Any]:
    confidence = _clamp_score(candidate.get("confidence"))
    uncertainty = _clamp_score(candidate.get("uncertainty"))
    novelty = _clamp_score(candidate.get("novelty"))
    experiment_value = _clamp_score(candidate.get("experiment_value"))
    bucket = derive_bucket(candidate.get("bucket") or candidate.get("selection_bucket"), confidence, uncertainty, novelty)
    risk = derive_risk(confidence, uncertainty, candidate.get("risk") or candidate.get("risk_level"))
    raw_status = str(candidate.get("status") or "").strip().lower().replace("_", " ")
    status = raw_status if raw_status in STATUS_ORDER else "suggested"
    explanations = normalize_explanations(candidate.get("explanation") or candidate.get("short_explanation"), bucket, confidence, uncertainty, novelty, risk)
    provenance_text = str(candidate.get("provenance") or "Not available")
    source_type = infer_source_type(candidate, provenance_text)
    parent_molecule = str(candidate.get("source_smiles") or candidate.get("source") or candidate.get("molecule_id") or "").strip()
    candidate_id = str(
        candidate.get("candidate_id")
        or candidate.get("molecule_id")
        or candidate.get("polymer")
        or f"candidate_{position}"
    )
    review_history = normalize_review_history(candidate.get("review_history"))
    reviewed_at = _to_iso(candidate.get("reviewed_at") or candidate.get("timestamp"))

    return {
        "rank": int(candidate.get("rank") or position),
        "candidate_id": candidate_id,
        "smiles": str(candidate.get("smiles") or "Not available"),
        "confidence": confidence,
        "uncertainty": uncertainty,
        "novelty": novelty,
        "experiment_value": experiment_value,
        "bucket": bucket,
        "risk": risk,
        "status": status,
        "explanation_lines": explanations,
        "explanation_short": explanations[0] if explanations else "Recommendation details unavailable.",
        "provenance": provenance_text,
        "provenance_compact": compact_provenance(source_type, iteration, model_version, parent_molecule),
        "source_type": source_type,
        "parent_molecule": parent_molecule or "Not available",
        "iteration": int(candidate.get("iteration") or iteration or 0),
        "model_version": str(candidate.get("model_version") or model_version),
        "dataset_version": str(candidate.get("dataset_version") or dataset_version),
        "status_label": status.title(),
        "review_note": str(candidate.get("review_note") or "").strip(),
        "reviewer": str(candidate.get("reviewer") or "unassigned"),
        "reviewed_at": reviewed_at,
        "reviewed_at_label": humanize_timestamp(reviewed_at),
        "review_history": review_history,
        "review_history_count": len(review_history),
        "suggested_next_action": suggested_next_action(bucket, risk, confidence, uncertainty),
        "search_text": " ".join(
            part for part in (candidate_id, str(candidate.get("smiles") or ""), bucket, risk, provenance_text) if part
        ).lower(),
        "risk_rank": RISK_ORDER.get(risk, 1),
        "bucket_rank": BUCKET_ORDER.get(bucket, 1),
        "latest_sort_key": reviewed_at or _to_iso(candidate.get("timestamp")) or f"{position:04d}",
    }


def summary_from_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    confidences = [candidate["confidence"] for candidate in candidates]
    uncertainties = [candidate["uncertainty"] for candidate in candidates]
    experiment_values = [candidate["experiment_value"] for candidate in candidates]

    return {
        "candidates_displayed": len(candidates),
        "top_experiment_value": max(experiment_values, default=0.0),
        "average_confidence": fmean(confidences) if confidences else 0.0,
        "average_uncertainty": fmean(uncertainties) if uncertainties else 0.0,
    }


def review_summary_from_candidates(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_ORDER}
    for candidate in candidates:
        status = normalize_status(candidate.get("status"))
        counts[status] += 1
    return counts


def build_discovery_workbench(
    *,
    decision_output: dict[str, Any],
    analysis_report: dict[str, Any] | None,
    review_queue: dict[str, Any] | None,
    session_id: str | None,
    evaluation_summary: dict[str, Any] | None,
    system_version: str,
) -> dict[str, Any]:
    raw_candidates = decision_output.get("top_experiments", [])
    candidates_input = raw_candidates if isinstance(raw_candidates, list) else []
    model_version = resolve_model_version(evaluation_summary, candidates_input, system_version)
    dataset_version = resolve_dataset_version(session_id, decision_output)
    iteration = int(decision_output.get("iteration") or 0)

    candidates = [
        normalize_candidate(
            dict(candidate),
            position=index + 1,
            iteration=iteration,
            model_version=model_version,
            dataset_version=dataset_version,
        )
        for index, candidate in enumerate(candidates_input)
        if isinstance(candidate, dict)
    ]

    summary = summary_from_candidates(candidates)
    queue_summary = (review_queue or {}).get("summary", {}) if isinstance(review_queue, dict) else {}
    counts = queue_summary.get("counts") if isinstance(queue_summary, dict) else None
    if not isinstance(counts, dict):
        counts = review_summary_from_candidates(candidates)

    artifact_state = str(decision_output.get("artifact_state") or "ok")
    has_candidates = bool(candidates)
    if artifact_state == "error":
        state = {
            "kind": "error",
            "message": "Current decision artifact could not be loaded. Please rerun the pipeline or check output integrity.",
        }
    elif not has_candidates:
        state = {
            "kind": "empty",
            "message": "No discovery results available yet. Run analysis or upload a dataset to generate recommendations.",
        }
    else:
        state = {"kind": "ready", "message": ""}

    last_updated = decision_output.get("source_updated_at") or max(
        [candidate.get("reviewed_at") for candidate in candidates if candidate.get("reviewed_at")],
        default="",
    )

    return {
        "state": state,
        "session_id": session_id,
        "source_path": decision_output.get("source_path") or "decision_output.json",
        "summary": {
            "iteration": iteration,
            **summary,
            "model_version": model_version,
            "dataset_version": dataset_version,
        },
        "review_summary": {
            "suggested": int(counts.get("suggested", 0)),
            "under_review": int(counts.get("under review", 0)),
            "approved": int(counts.get("approved", 0)),
            "rejected": int(counts.get("rejected", 0)),
            "tested": int(counts.get("tested", 0)),
            "ingested": int(counts.get("ingested", 0)),
        },
        "warnings": list((analysis_report or {}).get("warnings", [])) if isinstance(analysis_report, dict) else [],
        "recommendation_summary": str((analysis_report or {}).get("top_level_recommendation_summary") or "").strip(),
        "last_updated_label": humanize_timestamp(last_updated),
        "last_updated": _to_iso(last_updated),
        "system_version": system_version,
        "candidates": candidates,
        "interpretation": [
            {"label": "Confidence", "text": "Model belief strength for the current candidate."},
            {"label": "Uncertainty", "text": "How unsure the model is about this recommendation."},
            {"label": "Novelty", "text": "How different the candidate is from known reference chemistry."},
            {"label": "Experiment Value", "text": "Combined prioritization score for what to test next."},
            {"label": "Bucket", "text": "Exploit uses known good patterns, explore expands chemistry, learn reduces uncertainty."},
        ],
    }
