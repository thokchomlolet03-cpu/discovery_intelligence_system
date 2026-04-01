from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean
from typing import Any

from system.contracts import ContractValidationError, validate_decision_artifact, validate_review_event_record
from system.review_manager import STATUS_ORDER, normalize_status
from system.services.run_metadata_service import build_run_provenance
from system.services.session_identity_service import build_metric_interpretation
from system.session_report import ranking_policy as build_ranking_policy


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
        try:
            record = validate_review_event_record(item)
        except ValueError:
            continue
        reviewed_at = _to_iso(record.get("reviewed_at") or record.get("timestamp"))
        normalized.append(
            {
                "action": str(record.get("action") or "later"),
                "status": normalize_status(record.get("status"), action=record.get("action")),
                "note": str(record.get("note") or "").strip(),
                "reviewer": str(record.get("reviewer") or "unassigned"),
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


SCORE_LABELS = {
    "confidence": "Confidence",
    "uncertainty": "Uncertainty",
    "novelty": "Novelty",
    "experiment_value": "Experiment value",
    "priority_score": "Priority score",
}


DECISION_COPY = {
    "test_now": {
        "label": "Recommended for immediate testing",
        "description": "Use this queue for near-term bench work when the model signal is strong and risk is controlled.",
    },
    "learning_value": {
        "label": "High learning value",
        "description": "Use this queue to reduce model blind spots or probe uncertain chemistry.",
    },
    "review_before_testing": {
        "label": "Review before testing",
        "description": "Keep these molecules in chemist review before spending bench time.",
    },
    "deprioritize": {
        "label": "Deprioritize for now",
        "description": "These molecules look weaker than the current shortlist and can wait.",
    },
}


def _canonical_score_name(value: Any) -> str:
    cleaned = str(value or "").strip().lower()
    return cleaned if cleaned in SCORE_LABELS else "priority_score"


def _score_label(value: Any) -> str:
    return SCORE_LABELS.get(_canonical_score_name(value), "Priority score")


def _normalized_weights(value: Any) -> dict[str, float]:
    base = {"confidence": 0.30, "uncertainty": 0.20, "novelty": 0.15, "experiment_value": 0.35}
    if not isinstance(value, dict):
        return base

    weights = {
        key: max(_safe_float(value.get(key)), 0.0)
        for key in ("confidence", "uncertainty", "novelty", "experiment_value")
    }
    total = sum(weights.values()) or 1.0
    return {key: value / total for key, value in weights.items()}


def normalize_ranking_policy(analysis_payload: dict[str, Any]) -> dict[str, Any]:
    raw_policy = analysis_payload.get("ranking_policy") if isinstance(analysis_payload, dict) else {}
    ranking_diagnostics = analysis_payload.get("ranking_diagnostics", {}) if isinstance(analysis_payload, dict) else {}

    if isinstance(raw_policy, dict) and raw_policy:
        primary_score = _canonical_score_name(raw_policy.get("primary_score"))
        sort_order = [_canonical_score_name(item) for item in raw_policy.get("sort_order", [])]
        if not sort_order:
            sort_order = [primary_score, "experiment_value", "novelty"]
        cleaned = {
            "primary_score": primary_score,
            "sort_order": sort_order,
            "weights": _normalized_weights(raw_policy.get("weights")),
            "formula_label": str(raw_policy.get("formula_label") or "priority_score"),
            "formula_summary": str(raw_policy.get("formula_summary") or "").strip(),
            "formula_text": str(raw_policy.get("formula_text") or "").strip(),
        }
    else:
        intent = str(analysis_payload.get("intent_selected") or "").strip() if isinstance(analysis_payload, dict) else ""
        scoring_mode = str(analysis_payload.get("mode_used") or "").strip() if isinstance(analysis_payload, dict) else ""
        cleaned = build_ranking_policy(intent or "rank_uploaded_molecules", scoring_mode or "balanced")
        cleaned["primary_score"] = _canonical_score_name(
            ranking_diagnostics.get("score_basis") or cleaned.get("primary_score")
        )

    primary_score = _canonical_score_name(cleaned.get("primary_score"))
    sort_order = []
    for item in cleaned.get("sort_order", []):
        canonical = _canonical_score_name(item)
        if canonical not in sort_order:
            sort_order.append(canonical)
    if primary_score not in sort_order:
        sort_order.insert(0, primary_score)
    for fallback in ("priority_score", "experiment_value", "novelty"):
        if fallback not in sort_order:
            sort_order.append(fallback)

    weights = _normalized_weights(cleaned.get("weights"))
    formula_label = str(cleaned.get("formula_label") or "priority_score").strip() or "priority_score"
    formula_summary = str(cleaned.get("formula_summary") or "").strip()
    if not formula_summary:
        formula_summary = f"Candidate order prioritizes {_score_label(primary_score).lower()} first, then supporting scores."
    formula_text = str(cleaned.get("formula_text") or "").strip()
    if not formula_text:
        formula_text = (
            "priority_score combines confidence, uncertainty, novelty, and experiment value using the current scoring "
            "mode and intent."
        )

    weight_breakdown = [
        {
            "key": key,
            "label": _score_label(key),
            "weight": float(weight),
            "weight_percent": round(float(weight) * 100.0, 1),
        }
        for key, weight in weights.items()
    ]

    return {
        "primary_score": primary_score,
        "primary_score_label": _score_label(primary_score),
        "sort_order": sort_order,
        "weights": weights,
        "weight_breakdown": weight_breakdown,
        "formula_label": formula_label,
        "formula_summary": formula_summary,
        "formula_text": formula_text,
    }


def score_breakdown(candidate: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    weights = policy.get("weights", {}) if isinstance(policy, dict) else {}
    items: list[dict[str, Any]] = []
    for key in ("confidence", "uncertainty", "novelty", "experiment_value"):
        raw_value = _clamp_score(candidate.get(key))
        weight = max(_safe_float(weights.get(key)), 0.0)
        items.append(
            {
                "key": key,
                "label": _score_label(key),
                "raw_value": raw_value,
                "weight": weight,
                "weight_percent": round(weight * 100.0, 1),
                "contribution": raw_value * weight,
            }
        )
    return items


def normalize_score_breakdown_payload(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        key = _canonical_score_name(item.get("key"))
        normalized.append(
            {
                "key": key,
                "label": str(item.get("label") or _score_label(key)).strip() or _score_label(key),
                "raw_value": _clamp_score(item.get("raw_value")),
                "weight": max(_safe_float(item.get("weight")), 0.0),
                "weight_percent": max(_safe_float(item.get("weight_percent")), 0.0),
                "contribution": max(_safe_float(item.get("contribution")), 0.0),
            }
        )
    return normalized


def domain_summary(max_similarity: Any) -> dict[str, Any]:
    try:
        similarity = float(max_similarity)
    except (TypeError, ValueError):
        return {
            "status": "unknown",
            "label": "Domain coverage unavailable",
            "summary": "Reference-similarity diagnostics were not saved for this candidate.",
            "max_similarity": None,
        }

    if similarity < 0.25:
        return {
            "status": "out_of_domain",
            "label": "Outside strong chemistry range",
            "summary": "Reference similarity is low, so treat the model signal as less transferable.",
            "max_similarity": similarity,
        }
    if similarity < 0.45:
        return {
            "status": "edge_of_domain",
            "label": "Near the edge of domain coverage",
            "summary": "Similarity is moderate, so the recommendation is useful but should be reviewed carefully.",
            "max_similarity": similarity,
        }
    return {
        "status": "in_domain",
        "label": "Within stronger chemistry range",
        "summary": "Reference similarity is healthy enough to support more confident near-term review.",
        "max_similarity": similarity,
    }


def classify_decision(
    *,
    bucket: str,
    risk: str,
    confidence: float,
    uncertainty: float,
    novelty: float,
    priority_score: float,
    experiment_value: float,
    domain_status: str,
) -> dict[str, str]:
    if (
        priority_score >= 0.68
        and confidence >= 0.72
        and uncertainty <= 0.35
        and risk != "high"
        and domain_status != "out_of_domain"
    ):
        key = "test_now"
        summary = (
            "Strong near-term testing candidate because the composite priority is high, confidence is solid, "
            "and risk is controlled."
        )
    elif bucket == "learn" or uncertainty >= 0.62:
        key = "learning_value"
        summary = (
            "Good learning candidate because uncertainty remains high enough that testing could reduce model blind spots."
        )
    elif (
        (priority_score <= 0.35 and experiment_value <= 0.35 and confidence <= 0.45)
        or (risk == "high" and confidence <= 0.35 and novelty <= 0.45)
    ):
        key = "deprioritize"
        summary = "Lower near-term priority because the signal is weaker than the current shortlist."
    else:
        key = "review_before_testing"
        if domain_status == "out_of_domain":
            summary = (
                "Worth chemist review before testing because novelty is interesting, but domain coverage is weak."
            )
        elif novelty >= 0.65:
            summary = "Worth chemist review before testing because novelty is high and the tradeoff is less straightforward."
        else:
            summary = "Worth chemist review before testing because the ranking is promising but still needs scrutiny."

    return {
        "category": key,
        "label": DECISION_COPY[key]["label"],
        "description": DECISION_COPY[key]["description"],
        "summary": summary,
    }


def enrich_explanations(
    explanation_lines: list[str],
    *,
    decision_summary: str,
    domain: dict[str, Any],
    observed_value: float | None,
    assay: str,
    target: str,
) -> list[str]:
    lines = [str(item).strip() for item in explanation_lines if str(item).strip()]
    if decision_summary and decision_summary not in lines:
        lines.insert(0, decision_summary)
    domain_line = str(domain.get("summary") or "").strip()
    if domain_line and domain_line not in lines:
        lines.append(domain_line)
    if observed_value is not None:
        value_line = f"Uploaded observed value {observed_value:.3f} is available for direct cross-checking."
        if assay:
            value_line = f"Uploaded observed value {observed_value:.3f} is available for {assay} cross-checking."
        if value_line not in lines:
            lines.append(value_line)
    if assay or target:
        context_bits = [part for part in (assay, target) if part]
        context_line = f"Scientific context from the upload: {', '.join(context_bits)}."
        if context_line not in lines:
            lines.append(context_line)
    return lines[:5]


def normalize_candidate_rationale(
    raw_rationale: Any,
    *,
    explanation_lines: list[str],
    breakdown: list[dict[str, Any]],
    decision_summary: str,
    suggested_action: str,
    domain: dict[str, Any],
    bucket: str,
    risk: str,
    confidence: float,
    uncertainty: float,
    novelty: float,
) -> dict[str, Any]:
    cleaned = raw_rationale if isinstance(raw_rationale, dict) else {}
    dominant = max(breakdown, key=lambda item: float(item.get("contribution", 0.0))) if breakdown else {}
    dominant_key = _canonical_score_name(cleaned.get("primary_driver") or dominant.get("key"))
    dominant_label = _score_label(dominant_key)

    if uncertainty >= 0.7 or str(domain.get("status") or "") == "out_of_domain" or risk == "high":
        default_trust_label = "High caution"
        default_trust_summary = "The recommendation is useful, but uncertainty or weak domain coverage means it should be challenged carefully."
    elif confidence >= 0.8 and uncertainty <= 0.25 and str(domain.get("status") or "") == "in_domain":
        default_trust_label = "Stronger trust"
        default_trust_summary = "Confidence is relatively stable and the chemistry remains within stronger domain coverage."
    elif bucket == "learn" or novelty >= 0.65:
        default_trust_label = "Exploratory trust"
        default_trust_summary = "The shortlist is useful for exploration or learning, but it should not be treated as near-certain."
    else:
        default_trust_label = "Mixed trust"
        default_trust_summary = "The shortlist is useful for prioritization, but still needs scientist review before becoming a bench commitment."

    summary = str(cleaned.get("summary") or decision_summary or (explanation_lines[0] if explanation_lines else "")).strip()
    why_now = str(cleaned.get("why_now") or f"{dominant_label} is the largest contributor to the current priority score.").strip()
    trust_label = str(cleaned.get("trust_label") or default_trust_label).strip()
    trust_summary = str(cleaned.get("trust_summary") or default_trust_summary).strip()
    recommended_action = str(cleaned.get("recommended_action") or suggested_action).strip()

    strengths = cleaned.get("strengths") if isinstance(cleaned.get("strengths"), list) else []
    strengths = [str(item).strip() for item in strengths if str(item).strip()]
    session_context = cleaned.get("session_context") if isinstance(cleaned.get("session_context"), list) else []
    session_context = [str(item).strip() for item in session_context if str(item).strip()]
    cautions = cleaned.get("cautions") if isinstance(cleaned.get("cautions"), list) else []
    cautions = [str(item).strip() for item in cautions if str(item).strip()]
    evidence_lines = cleaned.get("evidence_lines") if isinstance(cleaned.get("evidence_lines"), list) else []
    evidence_lines = [str(item).strip() for item in evidence_lines if str(item).strip()]

    if not evidence_lines:
        evidence_lines = explanation_lines[:4]
    if not strengths:
        strengths = explanation_lines[1:3]
    if not cautions:
        if str(domain.get("status") or "") == "out_of_domain":
            cautions.append("This candidate sits outside stronger chemistry coverage.")
        elif uncertainty >= 0.7:
            cautions.append("Uncertainty remains high, so the recommendation is more useful for learning than confirmation.")
        elif confidence <= 0.35:
            cautions.append("Confidence remains low, so treat this as exploratory guidance.")

    return {
        "summary": summary,
        "why_now": why_now,
        "trust_label": trust_label,
        "trust_summary": trust_summary,
        "recommended_action": recommended_action,
        "primary_driver": dominant_key,
        "session_context": session_context[:3],
        "strengths": strengths[:4],
        "cautions": cautions[:4],
        "evidence_lines": evidence_lines[:5],
    }


def decision_overview(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    groups = []
    next_action_items = []
    for key in ("test_now", "learning_value", "review_before_testing", "deprioritize"):
        matching = [candidate for candidate in candidates if candidate.get("decision_category") == key]
        groups.append(
            {
                "key": key,
                "label": DECISION_COPY[key]["label"],
                "description": DECISION_COPY[key]["description"],
                "count": len(matching),
                "candidates": [
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "rank": candidate.get("rank"),
                        "summary": candidate.get("rationale_summary") or candidate.get("decision_summary") or candidate.get("explanation_short"),
                        "smiles": candidate.get("smiles"),
                        "priority_score": candidate.get("priority_score"),
                        "primary_score_value": candidate.get("primary_score_value"),
                        "suggested_next_action": candidate.get("suggested_next_action"),
                        "domain_label": candidate.get("domain_label"),
                        "trust_label": candidate.get("trust_label"),
                        "observed_value": candidate.get("observed_value"),
                        "assay": candidate.get("assay"),
                        "target": candidate.get("target"),
                    }
                    for candidate in matching[:3]
                ],
            }
        )
        if matching:
            next_action_items.append(f"{DECISION_COPY[key]['label']}: {matching[0].get('candidate_id')}")

    headline = next((group for group in groups if group["count"] > 0), groups[0] if groups else None)
    primary_group = next((group for group in groups if group["count"] > 0), None)
    primary_candidate = primary_group["candidates"][0] if primary_group and primary_group["candidates"] else None
    top_shortlist = [
        {
            "candidate_id": candidate.get("candidate_id"),
            "rank": candidate.get("rank"),
            "decision_label": candidate.get("decision_label"),
            "decision_summary": candidate.get("decision_summary"),
            "rationale_summary": candidate.get("rationale_summary"),
            "suggested_next_action": candidate.get("suggested_next_action"),
            "priority_score": candidate.get("priority_score"),
            "primary_score_label": candidate.get("primary_score_label"),
            "primary_score_value": candidate.get("primary_score_value"),
            "domain_label": candidate.get("domain_label"),
            "trust_label": candidate.get("trust_label"),
            "observed_value": candidate.get("observed_value"),
            "assay": candidate.get("assay"),
            "target": candidate.get("target"),
        }
        for candidate in candidates[:3]
    ]
    return {
        "headline": headline["label"] if headline else "No recommendation set",
        "headline_summary": headline["description"] if headline else "",
        "groups": groups,
        "next_actions": next_action_items[:4],
        "primary_group": primary_group,
        "primary_candidate": primary_candidate,
        "top_shortlist": top_shortlist,
    }


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
        metadata = candidate.get("model_metadata") if isinstance(candidate, dict) else {}
        label = str((metadata or {}).get("version") or candidate.get("model_version") or "").strip()
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
    ranking_policy: dict[str, Any],
) -> dict[str, Any]:
    confidence = _clamp_score(candidate.get("confidence"))
    uncertainty = _clamp_score(candidate.get("uncertainty"))
    novelty = _clamp_score(candidate.get("novelty"))
    experiment_value = _clamp_score(candidate.get("experiment_value"))
    priority_score_raw = candidate.get("priority_score")
    priority_score = _clamp_score(experiment_value if priority_score_raw is None else priority_score_raw)
    bucket = str(candidate["bucket"])
    risk = str(candidate["risk"])
    status = normalize_status(candidate["status"])
    explanations = _clean_explanation_lines(candidate.get("explanation"))
    if not explanations:
        explanations = ["Recommendation details unavailable."]
    provenance = candidate.get("provenance") if isinstance(candidate.get("provenance"), dict) else {}
    provenance_text = str(provenance.get("text") or "Not available")
    source_type = str(provenance.get("source_type") or "").strip() or infer_source_type(candidate, provenance_text)
    parent_molecule = str(provenance.get("parent_molecule") or candidate.get("source_smiles") or candidate.get("source") or candidate.get("molecule_id") or "").strip()
    candidate_id = str(candidate["candidate_id"])
    review_summary = candidate.get("review_summary") if isinstance(candidate.get("review_summary"), dict) else {}
    review_history = normalize_review_history(candidate.get("review_history"))
    reviewed_at = _to_iso(candidate.get("reviewed_at") or review_summary.get("reviewed_at"))
    reviewer = str(candidate.get("reviewer") or review_summary.get("reviewer") or "unassigned")
    review_note = str(candidate.get("review_note") or review_summary.get("note") or "").strip()
    model_metadata = candidate.get("model_metadata") if isinstance(candidate.get("model_metadata"), dict) else {}
    observed_value_raw = candidate.get("observed_value", candidate.get("value"))
    observed_value = None
    try:
        observed_value = float(observed_value_raw)
    except (TypeError, ValueError):
        observed_value = None
    assay = str(candidate.get("assay") or "").strip()
    target = str(candidate.get("target") or "").strip()
    target_definition = candidate.get("target_definition") if isinstance(candidate.get("target_definition"), dict) else {}
    data_facts = candidate.get("data_facts") if isinstance(candidate.get("data_facts"), dict) else {}
    model_judgment = candidate.get("model_judgment") if isinstance(candidate.get("model_judgment"), dict) else {}
    applicability_domain = candidate.get("applicability_domain") if isinstance(candidate.get("applicability_domain"), dict) else {}
    novelty_signal = candidate.get("novelty_signal") if isinstance(candidate.get("novelty_signal"), dict) else {}
    decision_policy = candidate.get("decision_policy") if isinstance(candidate.get("decision_policy"), dict) else {}
    final_recommendation = candidate.get("final_recommendation") if isinstance(candidate.get("final_recommendation"), dict) else {}
    normalized_explanation = candidate.get("normalized_explanation") if isinstance(candidate.get("normalized_explanation"), dict) else {}
    domain = domain_summary(candidate.get("max_similarity"))
    if candidate.get("domain_status") or candidate.get("domain_label") or candidate.get("domain_summary"):
        domain = {
            "status": str(candidate.get("domain_status") or domain.get("status") or "unknown"),
            "label": str(candidate.get("domain_label") or domain.get("label") or "Domain coverage unavailable"),
            "summary": str(candidate.get("domain_summary") or domain.get("summary") or "Reference-similarity diagnostics were not saved for this candidate."),
            "max_similarity": candidate.get("max_similarity", domain.get("max_similarity")),
        }
    decision = classify_decision(
        bucket=bucket,
        risk=risk,
        confidence=confidence,
        uncertainty=uncertainty,
        novelty=novelty,
        priority_score=priority_score,
        experiment_value=experiment_value,
        domain_status=str(domain.get("status") or "unknown"),
    )
    primary_score = _canonical_score_name(ranking_policy.get("primary_score"))
    primary_score_raw = candidate.get(primary_score)
    if primary_score == "priority_score":
        primary_score_value = _clamp_score(priority_score if primary_score_raw is None else primary_score_raw)
    else:
        primary_score_value = _clamp_score(0.0 if primary_score_raw is None else primary_score_raw)
    persisted_breakdown = normalize_score_breakdown_payload(candidate.get("score_breakdown"))
    breakdown = persisted_breakdown or score_breakdown(
        {
            "confidence": confidence,
            "uncertainty": uncertainty,
            "novelty": novelty,
            "experiment_value": experiment_value,
        },
        ranking_policy,
    )
    suggested_action = suggested_next_action(bucket, risk, confidence, uncertainty)
    if decision["category"] == "test_now":
        suggested_action = "Test this candidate in the next round and use it as a near-term lead."
    elif decision["category"] == "deprioritize":
        suggested_action = "Keep this candidate off the immediate testing list unless new evidence changes the tradeoff."
    rationale = normalize_candidate_rationale(
        candidate.get("rationale"),
        explanation_lines=explanations,
        breakdown=breakdown,
        decision_summary=decision["summary"],
        suggested_action=suggested_action,
        domain=domain,
        bucket=bucket,
        risk=risk,
        confidence=confidence,
        uncertainty=uncertainty,
        novelty=novelty,
    )
    explanations = enrich_explanations(
        rationale["evidence_lines"] or explanations,
        decision_summary=rationale["summary"] or decision["summary"],
        domain=domain,
        observed_value=observed_value,
        assay=assay,
        target=target,
    )
    rationale["evidence_lines"] = explanations

    return {
        "rank": int(candidate.get("rank") or position),
        "candidate_id": candidate_id,
        "smiles": str(candidate.get("smiles") or "Not available"),
        "canonical_smiles": str(candidate.get("canonical_smiles") or candidate.get("smiles") or "Not available"),
        "confidence": confidence,
        "uncertainty": uncertainty,
        "novelty": novelty,
        "acquisition_score": _clamp_score(candidate.get("acquisition_score")),
        "experiment_value": experiment_value,
        "priority_score": priority_score,
        "primary_score_name": primary_score,
        "primary_score_label": _score_label(primary_score),
        "primary_score_value": primary_score_value,
        "score_breakdown": breakdown,
        "trust_label": rationale["trust_label"],
        "trust_summary": rationale["trust_summary"],
        "rationale_summary": rationale["summary"],
        "rationale_why_now": rationale["why_now"],
        "rationale_primary_driver": rationale["primary_driver"],
        "rationale_session_context": rationale["session_context"],
        "rationale_strengths": rationale["strengths"],
        "rationale_cautions": rationale["cautions"],
        "rationale_recommended_action": rationale["recommended_action"],
        "rationale_evidence_lines": rationale["evidence_lines"],
        "bucket": bucket,
        "risk": risk,
        "status": status,
        "decision_category": decision["category"],
        "decision_label": decision["label"],
        "decision_description": decision["description"],
        "decision_summary": decision["summary"],
        "explanation_lines": explanations,
        "explanation_short": rationale["summary"] if rationale.get("summary") else (explanations[0] if explanations else "Recommendation details unavailable."),
        "provenance": provenance_text,
        "provenance_compact": compact_provenance(source_type, iteration, model_version, parent_molecule),
        "source_type": source_type,
        "parent_molecule": parent_molecule or "Not available",
        "iteration": int(candidate.get("iteration") or iteration or 0),
        "model_version": str(model_metadata.get("version") or candidate.get("model_version") or model_version),
        "dataset_version": str(candidate.get("dataset_version") or dataset_version),
        "status_label": status.title(),
        "review_note": review_note,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reviewed_at_label": humanize_timestamp(reviewed_at),
        "review_history": review_history,
        "review_history_count": len(review_history),
        "suggested_next_action": suggested_action,
        "observed_value": observed_value,
        "assay": assay,
        "target": target,
        "target_definition": target_definition,
        "data_facts": data_facts,
        "model_judgment": model_judgment,
        "applicability_domain": applicability_domain,
        "novelty_signal": novelty_signal,
        "decision_policy": decision_policy,
        "final_recommendation": final_recommendation,
        "normalized_explanation": normalized_explanation,
        "max_similarity": domain.get("max_similarity"),
        "domain_status": domain.get("status"),
        "domain_label": domain.get("label"),
        "domain_summary": domain.get("summary"),
        "search_text": " ".join(
            part
            for part in (
                candidate_id,
                str(candidate.get("smiles") or ""),
                bucket,
                risk,
                decision["label"],
                assay,
                target,
                provenance_text,
            )
            if part
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
    artifact_state = str(decision_output.get("artifact_state") or "ok")
    analysis_payload = analysis_report if isinstance(analysis_report, dict) else {}
    ranking_policy = normalize_ranking_policy(analysis_payload)
    target_definition = (
        decision_output.get("target_definition") if isinstance(decision_output.get("target_definition"), dict) else {}
    ) or (
        analysis_payload.get("target_definition") if isinstance(analysis_payload.get("target_definition"), dict) else {}
    )
    modeling_mode = str(
        decision_output.get("modeling_mode")
        or analysis_payload.get("modeling_mode")
        or ""
    ).strip()
    interpretation = build_metric_interpretation(
        target_definition=target_definition,
        modeling_mode=modeling_mode,
        ranking_policy=ranking_policy,
    )
    run_contract = (
        decision_output.get("run_contract") if isinstance(decision_output.get("run_contract"), dict) else {}
    ) or (
        analysis_payload.get("run_contract") if isinstance(analysis_payload.get("run_contract"), dict) else {}
    )
    comparison_anchors = (
        decision_output.get("comparison_anchors") if isinstance(decision_output.get("comparison_anchors"), dict) else {}
    ) or (
        analysis_payload.get("comparison_anchors") if isinstance(analysis_payload.get("comparison_anchors"), dict) else {}
    )
    run_provenance = build_run_provenance(
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
    )
    if artifact_state == "error":
        state = {
            "kind": "error",
            "message": str(decision_output.get("load_error") or "Current decision artifact could not be loaded. Please rerun the pipeline or check output integrity."),
        }
        return {
            "state": state,
            "session_id": session_id,
            "source_path": decision_output.get("source_path") or "decision_output.json",
            "summary": {
                "iteration": int(decision_output.get("iteration") or 0),
                "candidates_displayed": 0,
                "top_experiment_value": 0.0,
                "average_confidence": 0.0,
                "average_uncertainty": 0.0,
                "model_version": f"system-{system_version}",
                "dataset_version": resolve_dataset_version(session_id, decision_output),
            },
            "review_summary": {status.replace(" ", "_") if " " in status else status: 0 for status in STATUS_ORDER},
            "warnings": list(analysis_payload.get("warnings", [])),
            "recommendation_summary": str(analysis_payload.get("top_level_recommendation_summary") or "").strip(),
            "last_updated_label": humanize_timestamp(decision_output.get("source_updated_at")),
            "last_updated": _to_iso(decision_output.get("source_updated_at")),
            "system_version": system_version,
            "candidates": [],
            "target_definition": target_definition,
            "measurement_summary": analysis_payload.get("measurement_summary", {}),
            "ranking_diagnostics": analysis_payload.get("ranking_diagnostics", {}),
            "ranking_policy": ranking_policy,
            "decision_overview": decision_overview([]),
            "interpretation": interpretation,
            "run_provenance": run_provenance,
        }

    if artifact_state == "missing":
        candidates_input: list[dict[str, Any]] = []
        validated_output = decision_output
    else:
        try:
            validated_output = validate_decision_artifact(decision_output)
        except ContractValidationError as exc:
            return {
                "state": {"kind": "error", "message": f"Decision artifact contract error: {exc.detail}"},
                "session_id": session_id,
                "source_path": decision_output.get("source_path") or "decision_output.json",
                "summary": {
                    "iteration": int(decision_output.get("iteration") or 0),
                    "candidates_displayed": 0,
                    "top_experiment_value": 0.0,
                    "average_confidence": 0.0,
                    "average_uncertainty": 0.0,
                    "model_version": f"system-{system_version}",
                    "dataset_version": resolve_dataset_version(session_id, decision_output),
                },
                "review_summary": {"suggested": 0, "under_review": 0, "approved": 0, "rejected": 0, "tested": 0, "ingested": 0},
                "warnings": list(analysis_payload.get("warnings", [])),
                "recommendation_summary": str(analysis_payload.get("top_level_recommendation_summary") or "").strip(),
                "last_updated_label": humanize_timestamp(decision_output.get("source_updated_at")),
                "last_updated": _to_iso(decision_output.get("source_updated_at")),
                "system_version": system_version,
                "candidates": [],
                "target_definition": target_definition,
                "measurement_summary": analysis_payload.get("measurement_summary", {}),
                "ranking_diagnostics": analysis_payload.get("ranking_diagnostics", {}),
                "ranking_policy": ranking_policy,
                "decision_overview": decision_overview([]),
                "interpretation": interpretation,
                "run_provenance": run_provenance,
            }
        raw_candidates = validated_output.get("top_experiments", [])
        candidates_input = raw_candidates if isinstance(raw_candidates, list) else []

    model_version = resolve_model_version(evaluation_summary, candidates_input, system_version)
    dataset_version = resolve_dataset_version(session_id, validated_output)
    iteration = int(validated_output.get("iteration") or 0)

    candidates = [
        normalize_candidate(
            dict(candidate),
            position=index + 1,
            iteration=iteration,
            model_version=model_version,
            dataset_version=dataset_version,
            ranking_policy=ranking_policy,
        )
        for index, candidate in enumerate(candidates_input)
        if isinstance(candidate, dict)
    ]

    summary = summary_from_candidates(candidates)
    queue_summary = (review_queue or {}).get("summary", {}) if isinstance(review_queue, dict) else {}
    counts = queue_summary.get("counts") if isinstance(queue_summary, dict) else None
    if not isinstance(counts, dict):
        counts = review_summary_from_candidates(candidates)

    has_candidates = bool(candidates)
    if artifact_state == "missing" and session_id:
        state = {
            "kind": "artifact_missing",
            "message": str(decision_output.get("load_error") or "No saved decision artifact was found for this session yet."),
        }
    elif not has_candidates and not session_id:
        state = {
            "kind": "no_session",
            "message": "No session is selected yet. Open a completed upload session or run a new analysis.",
        }
    elif not has_candidates:
        state = {
            "kind": "empty",
            "message": "No discovery results available yet. Run analysis or upload a dataset to generate recommendations.",
        }
    else:
        state = {"kind": "ready", "message": ""}

    last_updated = validated_output.get("source_updated_at") or max(
        [candidate.get("reviewed_at") for candidate in candidates if candidate.get("reviewed_at")],
        default="",
    )

    return {
        "state": state,
        "session_id": session_id,
        "source_path": validated_output.get("source_path") or "decision_output.json",
        "target_definition": validated_output.get("target_definition") or analysis_payload.get("target_definition") or {},
        "scientific_contract": validated_output.get("scientific_contract") or {},
        "run_contract": validated_output.get("run_contract") or analysis_payload.get("run_contract") or {},
        "comparison_anchors": validated_output.get("comparison_anchors") or analysis_payload.get("comparison_anchors") or {},
        "run_provenance": build_run_provenance(
            run_contract=validated_output.get("run_contract") or analysis_payload.get("run_contract") or {},
            comparison_anchors=validated_output.get("comparison_anchors") or analysis_payload.get("comparison_anchors") or {},
        ),
        "contract_versions": validated_output.get("contract_versions") or analysis_payload.get("contract_versions") or {},
        "modeling_mode": modeling_mode,
        "decision_intent": str(validated_output.get("decision_intent") or analysis_payload.get("decision_intent") or "").strip(),
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
        "warnings": list(analysis_payload.get("warnings", [])),
        "recommendation_summary": str(analysis_payload.get("top_level_recommendation_summary") or "").strip(),
        "last_updated_label": humanize_timestamp(last_updated),
        "last_updated": _to_iso(last_updated),
        "system_version": system_version,
        "candidates": candidates,
        "measurement_summary": analysis_payload.get("measurement_summary", {}),
        "ranking_diagnostics": analysis_payload.get("ranking_diagnostics", {}),
        "ranking_policy": ranking_policy,
        "decision_overview": decision_overview(candidates),
        "interpretation": interpretation,
    }
