from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from reasoning.rules import HIGH_H_ACCEPTORS_THRESHOLD, HYDROPHILIC_LOGP_THRESHOLD, LOW_MW_THRESHOLD
from system.contracts import validate_decision_artifact, validate_prediction_result, validate_selection_result
from system.services.data_service import canonicalize_smiles
from system.services.runtime_config import resolve_system_config


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def risk_level(row, config=None):
    cfg = resolve_system_config(config)
    uncertainty = _safe_float(row.get("uncertainty", 0.0))
    confidence = _safe_float(row.get("confidence", 0.0))

    if uncertainty > cfg.decision.high_risk_uncertainty:
        return "high"
    if confidence > cfg.decision.low_risk_confidence:
        return "low"
    return "medium"


def decision_explanations(row, target_definition=None):
    target_definition = target_definition or {}
    target_name = str(target_definition.get("target_name") or "").strip().lower()
    biodegradability_mode = "biodegrad" in target_name
    explanations = []
    if float(row.get("rdkit_logp", row.get("logp", 0.0))) < HYDROPHILIC_LOGP_THRESHOLD:
        explanations.append(
            "low logP -> likely biodegradable"
            if biodegradability_mode
            else "low logP is one of the chemistry features influencing this model judgment"
        )
    if float(row.get("mw", 0.0)) < LOW_MW_THRESHOLD:
        explanations.append(
            "low molecular weight -> degradability favorable"
            if biodegradability_mode
            else "low molecular weight is one of the chemistry features influencing this model judgment"
        )
    if float(row.get("h_acceptors", 0.0)) >= HIGH_H_ACCEPTORS_THRESHOLD:
        explanations.append(
            "high H-bond acceptors -> biodegradable tendency"
            if biodegradability_mode
            else "high H-bond acceptors are one of the chemistry features influencing this model judgment"
        )
    if not explanations:
        explanations.append(
            "no strong rule-based biodegradability signal detected"
            if biodegradability_mode
            else "no strong rule-based chemistry signal was recorded for this candidate"
        )
    return explanations


def _candidate_id(row, rank: int) -> str:
    return str(row.get("candidate_id") or row.get("molecule_id") or row.get("polymer") or f"candidate_{rank}").strip()


def _canonical_smiles(row) -> str:
    smiles = str(row.get("smiles") or "").strip()
    return canonicalize_smiles(smiles) or smiles


def _model_metadata(row) -> dict[str, object]:
    version = str(row.get("model_version") or "unknown").strip() or "unknown"
    calibration_method = ""
    if ":" in version:
        _, calibration_method = version.split(":", 1)
    family = "random_forest" if version.lower().startswith("rf") else "unknown"
    return {
        "version": version,
        "family": family,
        "calibration_method": calibration_method,
    }


def _provenance(row) -> dict[str, object]:
    source_smiles = str(row.get("source_smiles") or "").strip()
    source_name = str(row.get("source") or "").strip()
    molecule_id = str(row.get("molecule_id") or row.get("polymer") or "").strip()
    text = str(row.get("provenance") or "").strip()
    if not text:
        text = "Provenance was not recorded for this candidate."
    source_type = "generated" if source_smiles else ("uploaded" if source_name or molecule_id else "")
    return {
        "text": text,
        "source_name": source_name,
        "source_type": source_type,
        "parent_molecule": source_smiles or molecule_id,
        "model_version": str(row.get("model_version") or "").strip(),
    }


def _feasibility(row) -> dict[str, object]:
    feasible = row.get("is_feasible")
    return {
        "is_feasible": bool(feasible) if feasible is not None else None,
        "reason": str(row.get("feasibility_reason") or "").strip(),
    }


def _review_summary(row) -> dict[str, object] | None:
    reviewed_at = row.get("reviewed_at")
    review_note = str(row.get("review_note") or "").strip()
    reviewer = str(row.get("reviewer") or "unassigned").strip() or "unassigned"
    if not review_note and not reviewed_at:
        return None
    return {
        "status": row.get("status") or "suggested",
        "note": review_note,
        "reviewer": reviewer,
        "actor": reviewer,
        "reviewed_at": reviewed_at,
    }


def _prediction_row_payload(row, rank: int) -> dict[str, object]:
    return {
        "candidate_id": _candidate_id(row, rank),
        "smiles": str(row.get("smiles") or "").strip(),
        "canonical_smiles": _canonical_smiles(row),
        "confidence": _safe_float(row.get("confidence"), None),
        "uncertainty": _safe_float(row.get("uncertainty"), None),
        "novelty": _safe_float(row.get("novelty", 0.0) or 0.0),
        "predicted_value": row.get("predicted_value"),
        "prediction_dispersion": row.get("prediction_dispersion"),
        "feasibility": _feasibility(row),
        "prediction_metadata": {
            "model_version": str(row.get("model_version") or "").strip(),
            "priority_score": _safe_float(row.get("priority_score", row.get("experiment_value", 0.0)) or 0.0),
        },
    }


def _selection_row_payload(row, rank: int) -> dict[str, object]:
    return {
        "candidate_id": _candidate_id(row, rank),
        "smiles": str(row.get("smiles") or "").strip(),
        "canonical_smiles": _canonical_smiles(row),
        "acquisition_score": float(row.get("final_score", row.get("score", row.get("priority_score", row.get("experiment_value", 0.0)))) or 0.0),
        "experiment_value": float(row.get("experiment_value", 0.0) or 0.0),
        "bucket": row.get("bucket") or row.get("selection_bucket") or "learn",
        "rank": int(rank),
        "selection_reason": str(row.get("selection_reason") or "").strip(),
        "portfolio_metadata": {
            "accepted_for_feedback": bool(row.get("accepted_for_feedback", True)),
            "priority_score": float(row.get("priority_score", row.get("experiment_value", 0.0)) or 0.0),
        },
    }


def build_decision_package(df, iteration, config=None, session_id: str | None = None):
    cfg = resolve_system_config(config)
    sort_columns = ["priority_score", "experiment_value", "uncertainty", "novelty"] if "priority_score" in df.columns else ["experiment_value", "uncertainty", "novelty"]
    ranked = df.sort_values(sort_columns, ascending=[False] * len(sort_columns)).head(cfg.decision.top_k)

    top_experiments = []
    risk_counts = Counter()
    generated_at = datetime.now(timezone.utc).isoformat()
    prediction_rows = []
    selection_rows = []
    effective_session_id = session_id or "public"
    target_definition = dict(df.attrs.get("target_definition") or {})
    for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
        risk = risk_level(row, config=cfg)
        risk_counts[risk] += 1
        prediction_rows.append(_prediction_row_payload(row, rank))
        selection_rows.append(_selection_row_payload(row, rank))
        top_experiments.append(
            {
                "session_id": effective_session_id,
                "rank": int(rank),
                "candidate_id": _candidate_id(row, rank),
                "smiles": str(row.get("smiles") or "").strip(),
                "canonical_smiles": _canonical_smiles(row),
                "confidence": _safe_float(row.get("confidence"), None),
                "uncertainty": _safe_float(row.get("uncertainty"), None),
                "novelty": _safe_float(row.get("novelty", 0.0) or 0.0),
                "acquisition_score": _safe_float(
                    row.get("final_score", row.get("score", row.get("priority_score", row.get("experiment_value", 0.0))))
                    or 0.0
                ),
                "experiment_value": _safe_float(row.get("experiment_value", 0.0) or 0.0),
                "bucket": row.get("bucket") or row.get("selection_bucket") or "learn",
                "risk": risk,
                "status": row.get("status") or "suggested",
                "explanation": row.get("explanation") or row.get("short_explanation") or decision_explanations(row, target_definition=target_definition),
                "provenance": _provenance(row),
                "feasibility": _feasibility(row),
                "created_at": row.get("created_at") or row.get("timestamp") or generated_at,
                "model_metadata": _model_metadata(row),
                "priority_score": row.get("priority_score"),
                "max_similarity": row.get("max_similarity"),
                "observed_value": row.get("observed_value", row.get("value")),
                "assay": row.get("assay") or "",
                "target": row.get("target") or "",
                "score_breakdown": row.get("score_breakdown") or [],
                "rationale": row.get("rationale"),
                "target_definition": row.get("target_definition") or target_definition,
                "data_facts": row.get("data_facts") or {},
                "model_judgment": row.get("model_judgment") or {},
                "applicability_domain": row.get("applicability_domain") or {},
                "novelty_signal": row.get("novelty_signal") or {},
                "decision_policy": row.get("decision_policy") or {},
                "final_recommendation": row.get("final_recommendation") or {},
                "normalized_explanation": row.get("normalized_explanation") or {},
                "domain_status": row.get("domain_status") or "",
                "domain_label": row.get("domain_label") or "",
                "domain_summary": row.get("domain_summary") or "",
                "review_summary": _review_summary(row),
                "selection_reason": str(
                    row.get("selection_reason")
                    or ((row.get("rationale") or {}).get("summary") if isinstance(row.get("rationale"), dict) else "")
                    or ""
                ).strip(),
                "review_note": str(row.get("review_note") or "").strip(),
                "reviewer": str(row.get("reviewer") or "unassigned").strip() or "unassigned",
                "reviewed_at": row.get("reviewed_at"),
                "review_history": row.get("review_history") or [],
            }
        )

    validate_prediction_result(
        {
            "session_id": effective_session_id,
            "candidate_count": len(prediction_rows),
            "candidates": prediction_rows,
        }
    )
    validate_selection_result(
        {
            "session_id": effective_session_id,
            "candidate_count": len(selection_rows),
            "bucket_counts": {
                str(key): int(value)
                for key, value in Counter(item["bucket"] for item in selection_rows).items()
            },
            "candidates": selection_rows,
        }
    )

    return validate_decision_artifact(
        {
        "session_id": effective_session_id,
        "iteration": int(iteration),
        "generated_at": generated_at,
        "summary": {
            "top_k": int(cfg.decision.top_k),
            "candidate_count": int(len(df)),
            "risk_counts": dict(risk_counts),
            "top_experiment_value": float(top_experiments[0]["experiment_value"]) if top_experiments else 0.0,
        },
        "top_experiments": top_experiments,
        "target_definition": target_definition,
        }
    )
