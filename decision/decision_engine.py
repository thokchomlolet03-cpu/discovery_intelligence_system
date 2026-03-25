from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from pipeline_utils import resolve_system_config
from reasoning.rules import HIGH_H_ACCEPTORS_THRESHOLD, HYDROPHILIC_LOGP_THRESHOLD, LOW_MW_THRESHOLD


def risk_level(row, config=None):
    cfg = resolve_system_config(config)
    uncertainty = float(row.get("uncertainty", 0.0))
    confidence = float(row.get("confidence", 0.0))

    if uncertainty > cfg.decision.high_risk_uncertainty:
        return "high"
    if confidence > cfg.decision.low_risk_confidence:
        return "low"
    return "medium"


def decision_explanations(row):
    explanations = []
    if float(row.get("rdkit_logp", row.get("logp", 0.0))) < HYDROPHILIC_LOGP_THRESHOLD:
        explanations.append("low logP -> likely biodegradable")
    if float(row.get("mw", 0.0)) < LOW_MW_THRESHOLD:
        explanations.append("low molecular weight -> degradability favorable")
    if float(row.get("h_acceptors", 0.0)) >= HIGH_H_ACCEPTORS_THRESHOLD:
        explanations.append("high H-bond acceptors -> biodegradable tendency")
    if not explanations:
        explanations.append("no strong rule-based biodegradability signal detected")
    return explanations


def build_decision_package(df, iteration, config=None):
    cfg = resolve_system_config(config)
    sort_columns = ["priority_score", "experiment_value", "uncertainty", "novelty"] if "priority_score" in df.columns else ["experiment_value", "uncertainty", "novelty"]
    ranked = df.sort_values(sort_columns, ascending=[False] * len(sort_columns)).head(cfg.decision.top_k)

    top_experiments = []
    risk_counts = Counter()
    generated_at = datetime.now(timezone.utc).isoformat()
    for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
        risk = risk_level(row, config=cfg)
        risk_counts[risk] += 1
        top_experiments.append(
            {
                "rank": int(rank),
                "candidate_id": row.get("candidate_id"),
                "molecule_id": row.get("molecule_id"),
                "polymer": row.get("polymer"),
                "smiles": row["smiles"],
                "confidence": float(row.get("confidence", 0.0)),
                "uncertainty": float(row.get("uncertainty", 0.0)),
                "novelty": float(row.get("novelty", 0.0)),
                "experiment_value": float(row.get("experiment_value", 0.0)),
                "priority_score": float(row.get("priority_score", row.get("experiment_value", 0.0))),
                "bucket": row.get("bucket", row.get("selection_bucket")),
                "risk": risk,
                "selection_bucket": row.get("selection_bucket"),
                "accepted_for_feedback": bool(row.get("accepted_for_feedback", False)),
                "explanation": row.get("short_explanation", decision_explanations(row)),
                "provenance": row.get("provenance", ""),
                "status": row.get("status", "suggested"),
                "iteration": int(iteration),
                "timestamp": row.get("timestamp", generated_at),
                "model_version": row.get("model_version"),
            }
        )

    return {
        "iteration": int(iteration),
        "generated_at": generated_at,
        "summary": {
            "top_k": int(cfg.decision.top_k),
            "candidate_count": int(len(df)),
            "risk_counts": dict(risk_counts),
            "top_experiment_value": float(top_experiments[0]["experiment_value"]) if top_experiments else 0.0,
        },
        "top_experiments": top_experiments,
    }
