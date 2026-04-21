from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from system.db import ScientificStateRepository
from system.db.repositories import ReviewRepository
from system.services.claim_service import build_claim_evidence_links, materialize_session_claims
from system.services.contradiction_service import build_session_contradictions
from system.services.data_service import canonicalize_smiles
from system.services.run_metadata_service import build_run_provenance


scientific_state_repository = ScientificStateRepository()
review_repository = ReviewRepository()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _target_payload(
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
    target_definition: dict[str, Any],
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "workspace_id": workspace_id,
        "created_by_user_id": created_by_user_id or "",
        "target_name": str(target_definition.get("target_name") or "").strip(),
        "target_kind": str(target_definition.get("target_kind") or "classification").strip(),
        "optimization_direction": str(target_definition.get("optimization_direction") or "classify").strip(),
        "measurement_column": str(target_definition.get("measurement_column") or "").strip(),
        "label_column": str(target_definition.get("label_column") or "").strip(),
        "measurement_unit": str(target_definition.get("measurement_unit") or "").strip(),
        "scientific_meaning": str(target_definition.get("scientific_meaning") or "").strip(),
        "assay_context": str(target_definition.get("assay_context") or "").strip(),
        "dataset_type": str(target_definition.get("dataset_type") or "").strip(),
        "mapping_confidence": str(target_definition.get("mapping_confidence") or "").strip(),
        "derived_label_rule": target_definition.get("derived_label_rule"),
        "success_definition": str(target_definition.get("success_definition") or "").strip(),
        "target_notes": str(target_definition.get("target_notes") or "").strip(),
        "source_payload": dict(target_definition),
    }


def build_evidence_records(
    prepared: pd.DataFrame,
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
    target_definition: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    target_name = str(target_definition.get("target_name") or "").strip()
    measurement_column = str(target_definition.get("measurement_column") or "").strip()
    label_column = str(target_definition.get("label_column") or "").strip()
    for row_index, row in enumerate(prepared.to_dict("records")):
        canonical_smiles = canonicalize_smiles(row.get("smiles")) or str(row.get("smiles") or "").strip()
        common = {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "created_by_user_id": created_by_user_id or "",
            "entity_id": str(row.get("entity_id") or row.get("molecule_id") or "").strip(),
            "candidate_id": str(row.get("molecule_id") or row.get("entity_id") or canonical_smiles).strip(),
            "smiles": str(row.get("smiles") or "").strip(),
            "canonical_smiles": canonical_smiles,
            "assay": str(row.get("assay") or "").strip(),
            "target_name": target_name,
            "source_row_index": row_index,
            "provenance": {
                "source": "upload_normalization",
                "session_id": session_id,
            },
            "payload": dict(row),
        }
        records.append(
            {
                **common,
                "evidence_type": "structure_input",
                "source_column": "smiles",
            }
        )
        observed_value = _safe_float(row.get("target_value", row.get("value")))
        if observed_value is not None:
            records.append(
                {
                    **common,
                    "evidence_type": "observed_measurement",
                    "observed_value": observed_value,
                    "source_column": measurement_column or "value",
                }
            )
        observed_label = _safe_int(row.get("target_label", row.get("biodegradable")))
        if observed_label in {0, 1}:
            records.append(
                {
                    **common,
                    "evidence_type": "observed_label",
                    "observed_label": observed_label,
                    "source_column": label_column or "target_label",
                }
            )
    return records


def build_model_output_records(
    scored_candidates: list[dict[str, Any]],
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
    bundle: dict[str, Any] | None,
    target_definition: dict[str, Any],
    scientific_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    bundle = bundle or {}
    selected_model = bundle.get("selected_model") if isinstance(bundle.get("selected_model"), dict) else {}
    model_name = str(selected_model.get("name") or "").strip()
    calibration_method = str(selected_model.get("calibration_method") or "").strip()
    model_kind = str(bundle.get("model_kind") or target_definition.get("target_kind") or "").strip()
    training_scope = str(bundle.get("training_scope") or "").strip()
    model_source = str(bundle.get("model_source") or "").strip()
    model_source_role = str(bundle.get("model_source_role") or "").strip()
    baseline_fallback = training_scope == "baseline_bundle" or scientific_contract.get("fallback_reason") == "legacy_baseline_bundle_reused"
    bridge_state_summary = (
        "Legacy baseline bundle reused for this session."
        if baseline_fallback
        else str(scientific_contract.get("fallback_reason") or "").replace("_", " ").strip()
    )
    records: list[dict[str, Any]] = []
    for row in scored_candidates:
        provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {"text": str(row.get("provenance") or "").strip()}
        records.append(
            {
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "candidate_id": str(row.get("candidate_id") or row.get("molecule_id") or row.get("smiles") or "").strip(),
                "smiles": str(row.get("smiles") or "").strip(),
                "canonical_smiles": str(row.get("canonical_smiles") or row.get("smiles") or "").strip(),
                "target_name": str(target_definition.get("target_name") or row.get("target") or "").strip(),
                "model_name": model_name,
                "model_family": str(bundle.get("model_family") or "random_forest").strip(),
                "model_kind": model_kind,
                "calibration_method": calibration_method,
                "training_scope": training_scope,
                "model_source": model_source,
                "model_source_role": model_source_role,
                "baseline_fallback_used": bool(baseline_fallback),
                "bridge_state_summary": bridge_state_summary,
                "confidence": _safe_float(row.get("confidence")),
                "uncertainty": _safe_float(row.get("uncertainty")),
                "predicted_value": _safe_float(row.get("predicted_value")),
                "prediction_dispersion": _safe_float(row.get("prediction_dispersion")),
                "novelty": _safe_float(row.get("novelty")),
                "applicability": row.get("applicability_domain") if isinstance(row.get("applicability_domain"), dict) else {},
                "provenance": provenance,
                "diagnostics": {
                    "max_similarity": _safe_float(row.get("max_similarity")),
                    "fallback_reason": scientific_contract.get("fallback_reason") or "",
                },
                "payload": dict(row),
            }
        )
    return records


def build_recommendation_records(
    candidates: list[dict[str, Any]],
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(candidates, start=1):
        rationale = row.get("rationale") if isinstance(row.get("rationale"), dict) else {}
        records.append(
            {
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "candidate_id": str(row.get("candidate_id") or row.get("molecule_id") or row.get("smiles") or "").strip(),
                "smiles": str(row.get("smiles") or "").strip(),
                "canonical_smiles": str(row.get("canonical_smiles") or row.get("smiles") or "").strip(),
                "rank": int(row.get("rank") or index),
                "decision_intent": str(result.get("decision_intent") or "").strip(),
                "modeling_mode": str(result.get("modeling_mode") or "").strip(),
                "scoring_mode": str(result.get("scoring_mode") or "").strip(),
                "bucket": str(row.get("bucket") or row.get("selection_bucket") or "").strip(),
                "risk": str(row.get("risk") or row.get("risk_level") or "").strip(),
                "status": str(row.get("status") or "suggested").strip(),
                "priority_score": _safe_float(row.get("priority_score")),
                "experiment_value": _safe_float(row.get("experiment_value")),
                "acquisition_score": _safe_float(row.get("acquisition_score", row.get("final_score"))),
                "rationale_summary": str(rationale.get("summary") or row.get("selection_reason") or "").strip(),
                "rationale": rationale,
                "policy_trace": row.get("decision_policy") if isinstance(row.get("decision_policy"), dict) else {},
                "recommendation": row.get("final_recommendation") if isinstance(row.get("final_recommendation"), dict) else {},
                "normalized_explanation": row.get("normalized_explanation") if isinstance(row.get("normalized_explanation"), dict) else {},
                "governance": {
                    "review_summary": row.get("review_summary") if isinstance(row.get("review_summary"), dict) else {},
                    "review_note": str(row.get("review_note") or "").strip(),
                    "reviewer": str(row.get("reviewer") or "").strip(),
                    "reviewed_at": row.get("reviewed_at"),
                },
                "payload": dict(row),
            }
        )
    return records


def build_carryover_records(
    candidates: list[dict[str, Any]],
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
) -> list[dict[str, Any]]:
    reviews = review_repository.list_reviews(workspace_id=workspace_id)
    by_smiles: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        if str(review.get("session_id") or "").strip() == session_id:
            continue
        canonical_smiles = canonicalize_smiles(review.get("smiles")) or str(review.get("smiles") or "").strip()
        if canonical_smiles:
            by_smiles.setdefault(canonical_smiles, []).append(review)

    records: list[dict[str, Any]] = []
    for candidate in candidates:
        canonical_smiles = canonicalize_smiles(candidate.get("canonical_smiles") or candidate.get("smiles")) or str(candidate.get("canonical_smiles") or candidate.get("smiles") or "").strip()
        if not canonical_smiles:
            continue
        for review in by_smiles.get(canonical_smiles, []):
            records.append(
                {
                    "workspace_id": workspace_id,
                    "session_id": session_id,
                    "created_by_user_id": created_by_user_id or "",
                    "source_session_id": str(review.get("session_id") or "").strip(),
                    "source_candidate_id": str(review.get("candidate_id") or "").strip(),
                    "target_candidate_id": str(candidate.get("candidate_id") or candidate.get("smiles") or "").strip(),
                    "smiles": str(candidate.get("smiles") or "").strip(),
                    "canonical_smiles": canonical_smiles,
                    "carryover_kind": "review_memory",
                    "match_basis": "canonical_smiles",
                    "review_event_id": _safe_int(review.get("id")),
                    "source_status": str(review.get("status") or "").strip(),
                    "source_action": str(review.get("action") or "").strip(),
                    "source_note": str(review.get("note") or "").strip(),
                    "source_reviewer": str(review.get("reviewer") or "").strip(),
                    "source_reviewed_at": review.get("reviewed_at"),
                    "payload": {
                        "source_review": review,
                        "target_candidate": {
                            "candidate_id": candidate.get("candidate_id"),
                            "rank": candidate.get("rank"),
                        },
                    },
                }
            )
    return records


def _ranking_policy_from_result(result: dict[str, Any], target_definition: dict[str, Any]) -> dict[str, Any]:
    analysis_report = result.get("analysis_report") if isinstance(result.get("analysis_report"), dict) else {}
    ranking_policy = analysis_report.get("ranking_policy") if isinstance(analysis_report.get("ranking_policy"), dict) else {}
    if ranking_policy:
        return dict(ranking_policy)
    target_kind = str(target_definition.get("target_kind") or "classification").strip().lower()
    return {
        "primary_score": "priority_score",
        "primary_score_label": "Ranking compatibility" if target_kind == "regression" else "Priority score",
        "sort_order": ["priority_score", "experiment_value", "novelty"],
        "weights": {"confidence": 0.30, "uncertainty": 0.20, "novelty": 0.15, "experiment_value": 0.35},
        "formula_label": "priority_score",
        "formula_summary": (
            "Candidate ordering emphasizes ranking compatibility first, then experiment value and novelty."
            if target_kind == "regression"
            else "Candidate ordering emphasizes composite priority first, then experiment value and novelty."
        ),
        "formula_text": (
            "priority_score combines ranking compatibility, prediction dispersion, novelty, and experiment value."
            if target_kind == "regression"
            else "priority_score combines confidence, uncertainty, novelty, and experiment value."
        ),
    }


def _ranking_diagnostics_from_result(
    result: dict[str, Any],
    model_outputs: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    analysis_report = result.get("analysis_report") if isinstance(result.get("analysis_report"), dict) else {}
    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report.get("ranking_diagnostics"), dict) else {}
    if ranking_diagnostics:
        return (dict(ranking_diagnostics), "analysis_report")

    outputs_by_candidate = {
        str(item.get("candidate_id") or "").strip(): item
        for item in model_outputs
        if str(item.get("candidate_id") or "").strip()
    }
    uncertainties: list[float] = []
    out_of_domain = 0
    high_caution = 0
    for item in recommendations:
        output = outputs_by_candidate.get(str(item.get("candidate_id") or "").strip()) or {}
        uncertainty = _safe_float(output.get("uncertainty"))
        if uncertainty is not None:
            uncertainties.append(uncertainty)
        applicability = output.get("applicability") if isinstance(output.get("applicability"), dict) else {}
        if str(applicability.get("status") or "").strip().lower() == "out_of_domain":
            out_of_domain += 1
        if str(item.get("risk") or "").strip().lower() == "high":
            high_caution += 1
    count = len(recommendations)
    return (
        {
            "candidate_count": count,
            "average_uncertainty": round(sum(uncertainties) / len(uncertainties), 4) if uncertainties else None,
            "out_of_domain_rate": round(out_of_domain / count, 4) if count else None,
            "high_caution_count": high_caution,
        },
        "scientific_state",
    )


def build_run_metadata_record(
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
    result: dict[str, Any],
    target_definition: dict[str, Any],
    model_outputs: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    run_contract = dict(result.get("run_contract") or {})
    comparison_anchors = dict(result.get("comparison_anchors") or {})
    ranking_policy = _ranking_policy_from_result(result, target_definition)
    ranking_diagnostics, diagnostics_source = _ranking_diagnostics_from_result(result, model_outputs, recommendations)
    run_provenance = build_run_provenance(
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
    )
    trust_summary = {
        "comparison_summary": str(run_provenance.get("comparison_summary") or "").strip(),
        "model_summary": str(run_provenance.get("model_summary") or "").strip(),
        "policy_summary": str(run_provenance.get("policy_summary") or "").strip(),
        "bridge_state_summary": str(run_provenance.get("bridge_state_summary") or "").strip(),
        "cautions": list(run_provenance.get("cautions") or [])[:4],
        "baseline_fallback_visible": bool(run_provenance.get("bridge_state_active")),
    }
    return {
        "session_id": session_id,
        "workspace_id": workspace_id,
        "created_by_user_id": created_by_user_id or "",
        "source_name": str(result.get("source_name") or "").strip(),
        "input_type": str(result.get("input_type") or "").strip(),
        "decision_intent": str(result.get("decision_intent") or "").strip(),
        "modeling_mode": str(result.get("modeling_mode") or "").strip(),
        "scoring_mode": str(result.get("scoring_mode") or "").strip(),
        "run_contract": run_contract,
        "comparison_anchors": comparison_anchors,
        "ranking_policy": ranking_policy,
        "ranking_diagnostics": ranking_diagnostics,
        "trust_summary": trust_summary,
        "provenance_markers": {
            "run_contract_source": "pipeline_result",
            "comparison_anchors_source": "pipeline_result",
            "ranking_policy_source": "analysis_report" if isinstance((result.get("analysis_report") or {}).get("ranking_policy"), dict) else "scientific_state",
            "ranking_diagnostics_source": diagnostics_source,
            "trust_summary_source": "run_provenance",
        },
        "source_payload": {
            "contract_versions": dict(result.get("contract_versions") or {}),
            "scientific_contract": dict(result.get("scientific_contract") or {}),
            "target_definition": target_definition,
        },
    }


def build_candidate_state_records(
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
    target_definition: dict[str, Any],
    evidence_records: list[dict[str, Any]],
    model_outputs: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    carryover_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_by_key: dict[str, dict[str, Any]] = {}
    for item in evidence_records:
        candidate_id = str(item.get("candidate_id") or "").strip()
        canonical_smiles = str(item.get("canonical_smiles") or item.get("smiles") or "").strip()
        key = candidate_id or canonical_smiles
        if not key:
            continue
        summary = evidence_by_key.setdefault(
            key,
            {
                "has_structure_input": False,
                "has_observed_measurement": False,
                "has_observed_label": False,
                "observed_value_count": 0,
                "observed_label_count": 0,
                "assays": set(),
            },
        )
        evidence_type = str(item.get("evidence_type") or "").strip()
        if evidence_type == "structure_input":
            summary["has_structure_input"] = True
        elif evidence_type == "observed_measurement":
            summary["has_observed_measurement"] = True
            summary["observed_value_count"] += 1
        elif evidence_type == "observed_label":
            summary["has_observed_label"] = True
            summary["observed_label_count"] += 1
        assay = str(item.get("assay") or "").strip()
        if assay:
            summary["assays"].add(assay)

    model_by_key: dict[str, dict[str, Any]] = {}
    for item in model_outputs:
        candidate_id = str(item.get("candidate_id") or "").strip()
        canonical_smiles = str(item.get("canonical_smiles") or item.get("smiles") or "").strip()
        if candidate_id:
            model_by_key[f"id::{candidate_id}"] = item
        if canonical_smiles:
            model_by_key[f"smiles::{canonical_smiles}"] = item

    carryover_by_smiles: dict[str, list[dict[str, Any]]] = {}
    for item in carryover_records:
        canonical_smiles = str(item.get("canonical_smiles") or item.get("smiles") or "").strip()
        if canonical_smiles:
            carryover_by_smiles.setdefault(canonical_smiles, []).append(item)

    records: list[dict[str, Any]] = []
    target_name = str(target_definition.get("target_name") or "").strip()
    target_kind = str(target_definition.get("target_kind") or "").strip()
    for item in recommendations:
        candidate_id = str(item.get("candidate_id") or "").strip()
        smiles = str(item.get("smiles") or "").strip()
        canonical_smiles = str(item.get("canonical_smiles") or smiles).strip()
        output = model_by_key.get(f"id::{candidate_id}") or model_by_key.get(f"smiles::{canonical_smiles}") or {}
        governance = item.get("governance") if isinstance(item.get("governance"), dict) else {}
        review_summary = governance.get("review_summary") if isinstance(governance.get("review_summary"), dict) else {}
        rationale = item.get("rationale") if isinstance(item.get("rationale"), dict) else {}
        recommendation_payload = item.get("recommendation") if isinstance(item.get("recommendation"), dict) else {}
        normalized_explanation = item.get("normalized_explanation") if isinstance(item.get("normalized_explanation"), dict) else {}
        evidence_key = candidate_id or canonical_smiles
        evidence_summary = evidence_by_key.get(
            evidence_key,
            {
                "has_structure_input": False,
                "has_observed_measurement": False,
                "has_observed_label": False,
                "observed_value_count": 0,
                "observed_label_count": 0,
                "assays": set(),
            },
        )
        carryover_matches = carryover_by_smiles.get(canonical_smiles, [])
        predictive_summary = {
            "confidence": output.get("confidence"),
            "uncertainty": output.get("uncertainty"),
            "predicted_value": output.get("predicted_value"),
            "prediction_dispersion": output.get("prediction_dispersion"),
            "novelty": output.get("novelty"),
            "applicability": output.get("applicability") if isinstance(output.get("applicability"), dict) else {},
            "model_name": str(output.get("model_name") or "").strip(),
            "training_scope": str(output.get("training_scope") or "").strip(),
            "baseline_fallback_used": bool(output.get("baseline_fallback_used")),
            "bridge_state_summary": str(output.get("bridge_state_summary") or "").strip(),
        }
        recommendation_summary = {
            "rank": int(item.get("rank") or 0),
            "bucket": str(item.get("bucket") or "").strip(),
            "risk": str(item.get("risk") or "").strip(),
            "status": str(item.get("status") or "").strip(),
            "priority_score": item.get("priority_score"),
            "experiment_value": item.get("experiment_value"),
            "rationale_summary": str(item.get("rationale_summary") or rationale.get("summary") or "").strip(),
            "rationale": rationale,
            "decision_policy": item.get("policy_trace") if isinstance(item.get("policy_trace"), dict) else {},
            "final_recommendation": recommendation_payload,
            "normalized_explanation": normalized_explanation,
        }
        governance_summary = {
            "status": str(item.get("status") or "").strip(),
            "review_summary": review_summary,
            "review_note": str(governance.get("review_note") or "").strip(),
            "reviewer": str(governance.get("reviewer") or review_summary.get("reviewer") or "").strip(),
            "reviewed_at": review_summary.get("reviewed_at") or governance.get("reviewed_at"),
        }
        carryover_summary = {
            "record_count": len(carryover_matches),
            "continuity_source": "canonical_carryover" if carryover_matches else "not_recorded",
            "source_session_ids": sorted({str(match.get("source_session_id") or "").strip() for match in carryover_matches if str(match.get("source_session_id") or "").strip()}),
            "latest_source_reviewed_at": max((match.get("source_reviewed_at") for match in carryover_matches if match.get("source_reviewed_at")), default=None),
        }
        trust_summary = {
            "trust_label": str(rationale.get("trust_label") or "").strip(),
            "trust_summary": str(rationale.get("trust_summary") or "").strip(),
            "cautions": list(rationale.get("cautions") or [])[:4] if isinstance(rationale.get("cautions"), list) else [],
        }
        records.append(
            {
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "candidate_id": candidate_id or canonical_smiles,
                "smiles": smiles,
                "canonical_smiles": canonical_smiles,
                "rank": int(item.get("rank") or 0),
                "identity_context": {
                    "target_name": target_name,
                    "target_kind": target_kind,
                    "measurement_column": str(target_definition.get("measurement_column") or "").strip(),
                },
                "evidence_summary": {
                    "has_structure_input": bool(evidence_summary["has_structure_input"]),
                    "has_observed_measurement": bool(evidence_summary["has_observed_measurement"]),
                    "has_observed_label": bool(evidence_summary["has_observed_label"]),
                    "observed_value_count": int(evidence_summary["observed_value_count"]),
                    "observed_label_count": int(evidence_summary["observed_label_count"]),
                    "assays": sorted(evidence_summary["assays"]),
                },
                "predictive_summary": predictive_summary,
                "recommendation_summary": recommendation_summary,
                "governance_summary": governance_summary,
                "carryover_summary": carryover_summary,
                "trust_summary": trust_summary,
                "provenance_markers": {
                    "predictive_source": "model_output_records",
                    "recommendation_source": "recommendation_records",
                    "governance_source": "review_events_via_recommendation_sync",
                    "carryover_source": "carryover_records",
                },
                "source_payload": {
                    "recommendation_record": item,
                    "model_output_record": output,
                },
            }
        )
    return records


def persist_run_scientific_state(
    *,
    prepared: pd.DataFrame,
    result: dict[str, Any],
    scored: pd.DataFrame | None,
    bundle: dict[str, Any] | None,
    workspace_id: str,
    created_by_user_id: str | None,
) -> dict[str, Any]:
    session_id = str(result.get("session_id") or result.get("run_id") or "").strip()
    target_definition = dict(result.get("target_definition") or {})
    scientific_contract = dict(result.get("scientific_contract") or {})
    scored_candidates = scored.to_dict("records") if isinstance(scored, pd.DataFrame) else list(result.get("top_candidates") or [])
    top_candidates = list(result.get("top_candidates") or [])
    diagnostics: dict[str, Any] = {
        "canonical_state_written": False,
        "legacy_artifacts_present": bool(result.get("artifacts")),
        "legacy_fallback_used": False,
        "scientific_state_source": "canonical_sql",
        "written_at": _utc_now().isoformat(),
    }
    if not session_id:
        diagnostics["error"] = "missing_session_id"
        return diagnostics

    scientific_state_repository.upsert_target_definition(
        _target_payload(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            target_definition=target_definition,
        )
    )
    evidence_records = scientific_state_repository.replace_evidence_records(
        session_id=session_id,
        workspace_id=workspace_id,
        payloads=build_evidence_records(
            prepared,
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            target_definition=target_definition,
        ),
    )
    model_outputs = scientific_state_repository.replace_model_outputs(
        session_id=session_id,
        workspace_id=workspace_id,
        payloads=build_model_output_records(
            scored_candidates,
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            bundle=bundle,
            target_definition=target_definition,
            scientific_contract=scientific_contract,
        ),
    )
    recommendations = scientific_state_repository.replace_recommendations(
        session_id=session_id,
        workspace_id=workspace_id,
        payloads=build_recommendation_records(
            top_candidates,
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            result=result,
        ),
    )
    carryover = scientific_state_repository.replace_carryover_records(
        session_id=session_id,
        workspace_id=workspace_id,
        payloads=build_carryover_records(
            top_candidates,
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
        ),
    )
    candidate_states = scientific_state_repository.replace_candidate_states(
        session_id=session_id,
        workspace_id=workspace_id,
        payloads=build_candidate_state_records(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            target_definition=target_definition,
            evidence_records=evidence_records,
            model_outputs=model_outputs,
            recommendations=recommendations,
            carryover_records=carryover,
        ),
    )
    run_metadata = scientific_state_repository.upsert_run_metadata(
        build_run_metadata_record(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            result=result,
            target_definition=target_definition,
            model_outputs=model_outputs,
            recommendations=recommendations,
        )
    )
    claims = scientific_state_repository.replace_claims(
        session_id=session_id,
        workspace_id=workspace_id,
        payloads=materialize_session_claims(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            run_metadata=run_metadata,
            candidate_states=candidate_states,
        ),
    )
    claim_evidence_links = scientific_state_repository.replace_claim_evidence_links(
        session_id=session_id,
        workspace_id=workspace_id,
        payloads=build_claim_evidence_links(
            claims=claims,
            evidence_records=evidence_records,
            model_outputs=model_outputs,
            recommendations=recommendations,
        ),
    )
    contradictions = scientific_state_repository.replace_contradictions(
        session_id=session_id,
        workspace_id=workspace_id,
        payloads=build_session_contradictions(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            claims=claims,
            claim_evidence_links=claim_evidence_links,
            experiment_results=[],
            belief_updates=[],
        ),
    )
    diagnostics.update(
        {
            "canonical_state_written": True,
            "target_definition_written": bool(target_definition),
            "evidence_record_count": len(evidence_records),
            "model_output_count": len(model_outputs),
            "recommendation_count": len(recommendations),
            "carryover_count": len(carryover),
            "candidate_state_count": len(candidate_states),
            "canonical_run_metadata_written": bool(run_metadata),
            "claim_count": len(claims),
            "claim_evidence_link_count": len(claim_evidence_links),
            "contradiction_count": len(contradictions),
            "baseline_model_fallback": any(item.get("baseline_fallback_used") for item in model_outputs),
            "baseline_model_fallback_summary": next((item.get("bridge_state_summary") for item in model_outputs if item.get("baseline_fallback_used")), ""),
        }
    )
    return diagnostics


def sync_review_into_scientific_state(review: dict[str, Any]) -> None:
    session_id = str(review.get("session_id") or "").strip()
    workspace_id = str(review.get("workspace_id") or "").strip()
    if not session_id or not workspace_id:
        return
    recommendations = scientific_state_repository.list_recommendations(session_id=session_id, workspace_id=workspace_id)
    if not recommendations:
        return
    updated: list[dict[str, Any]] = []
    matched = False
    canonical_review_smiles = canonicalize_smiles(review.get("smiles")) or str(review.get("smiles") or "").strip()
    for item in recommendations:
        same_candidate = str(item.get("candidate_id") or "").strip() == str(review.get("candidate_id") or "").strip()
        same_smiles = canonical_review_smiles and canonical_review_smiles == str(item.get("canonical_smiles") or item.get("smiles") or "").strip()
        if same_candidate or same_smiles:
            governance = dict(item.get("governance") or {})
            governance.update(
                {
                    "review_summary": {
                        "status": review.get("status"),
                        "action": review.get("action"),
                        "note": review.get("note"),
                        "reviewer": review.get("reviewer"),
                        "reviewed_at": review.get("reviewed_at"),
                    },
                    "latest_review_event": review,
                }
            )
            item["status"] = str(review.get("status") or item.get("status") or "under review").strip()
            item["governance"] = governance
            matched = True
        updated.append(item)
    if matched:
        scientific_state_repository.replace_recommendations(session_id=session_id, workspace_id=workspace_id, payloads=updated)
        evidence = scientific_state_repository.list_evidence_records(session_id=session_id, workspace_id=workspace_id)
        model_outputs = scientific_state_repository.list_model_outputs(session_id=session_id, workspace_id=workspace_id)
        carryover = scientific_state_repository.list_carryover_records(session_id=session_id, workspace_id=workspace_id)
        try:
            target_definition = scientific_state_repository.get_target_definition(session_id=session_id, workspace_id=workspace_id)
        except FileNotFoundError:
            target_definition = {}
        scientific_state_repository.replace_candidate_states(
            session_id=session_id,
            workspace_id=workspace_id,
            payloads=build_candidate_state_records(
                session_id=session_id,
                workspace_id=workspace_id,
                created_by_user_id=str(review.get("actor_user_id") or "").strip() or None,
                target_definition=target_definition,
                evidence_records=evidence,
                model_outputs=model_outputs,
                recommendations=updated,
                carryover_records=carryover,
            ),
        )
        try:
            run_metadata = scientific_state_repository.get_run_metadata(session_id=session_id, workspace_id=workspace_id)
        except FileNotFoundError:
            run_metadata = {}
        scientific_state_repository.replace_claims(
            session_id=session_id,
            workspace_id=workspace_id,
            payloads=materialize_session_claims(
                session_id=session_id,
                workspace_id=workspace_id,
                created_by_user_id=str(review.get("actor_user_id") or "").strip() or None,
                run_metadata=run_metadata,
                candidate_states=scientific_state_repository.list_candidate_states(session_id=session_id, workspace_id=workspace_id),
            ),
        )
        claims = scientific_state_repository.list_claims(session_id=session_id, workspace_id=workspace_id)
        claim_evidence_links = scientific_state_repository.replace_claim_evidence_links(
            session_id=session_id,
            workspace_id=workspace_id,
            payloads=build_claim_evidence_links(
                claims=claims,
                evidence_records=evidence,
                model_outputs=model_outputs,
                recommendations=updated,
            ),
        )
        experiment_results = scientific_state_repository.list_experiment_results(claim_id=None)
        experiment_results = [
            item
            for item in experiment_results
            if str(item.get("session_id") or "").strip() == session_id
            and str(item.get("workspace_id") or "").strip() == workspace_id
        ]
        belief_updates = scientific_state_repository.list_belief_updates(claim_id=None)
        belief_updates = [
            item
            for item in belief_updates
            if str(item.get("session_id") or "").strip() == session_id
            and str(item.get("workspace_id") or "").strip() == workspace_id
        ]
        scientific_state_repository.replace_contradictions(
            session_id=session_id,
            workspace_id=workspace_id,
            payloads=build_session_contradictions(
                session_id=session_id,
                workspace_id=workspace_id,
                created_by_user_id=str(review.get("actor_user_id") or "").strip() or None,
                claims=claims,
                claim_evidence_links=claim_evidence_links,
                experiment_results=experiment_results,
                belief_updates=belief_updates,
            ),
        )


def load_canonical_session_scientific_state(session_id: str, *, workspace_id: str | None = None) -> dict[str, Any]:
    target_definition = scientific_state_repository.get_target_definition(session_id=session_id, workspace_id=workspace_id)
    evidence = scientific_state_repository.list_evidence_records(session_id=session_id, workspace_id=workspace_id)
    model_outputs = scientific_state_repository.list_model_outputs(session_id=session_id, workspace_id=workspace_id)
    recommendations = scientific_state_repository.list_recommendations(session_id=session_id, workspace_id=workspace_id)
    carryover = scientific_state_repository.list_carryover_records(session_id=session_id, workspace_id=workspace_id)
    candidate_states = scientific_state_repository.list_candidate_states(session_id=session_id, workspace_id=workspace_id)
    claims = scientific_state_repository.list_claims(session_id=session_id, workspace_id=workspace_id)
    claim_evidence_links = scientific_state_repository.list_claim_evidence_links(session_id=session_id, workspace_id=workspace_id)
    contradictions = scientific_state_repository.list_contradictions(session_id=session_id, workspace_id=workspace_id)
    try:
        run_metadata = scientific_state_repository.get_run_metadata(session_id=session_id, workspace_id=workspace_id)
    except FileNotFoundError:
        run_metadata = {}
    return {
        "session_id": session_id,
        "target_definition": target_definition,
        "evidence_records": evidence,
        "model_outputs": model_outputs,
        "recommendations": recommendations,
        "carryover_records": carryover,
        "candidate_states": candidate_states,
        "claims": claims,
        "claim_evidence_links": claim_evidence_links,
        "contradictions": contradictions,
        "run_metadata": run_metadata,
        "diagnostics": {
            "scientific_state_source": "canonical_sql",
            "loaded_at": _utc_now().isoformat(),
            "recommendation_count": len(recommendations),
            "candidate_state_count": len(candidate_states),
            "claim_count": len(claims),
            "claim_evidence_link_count": len(claim_evidence_links),
            "contradiction_count": len(contradictions),
            "run_metadata_present": bool(run_metadata),
        },
    }


def synthesize_decision_payload_from_scientific_state(session_id: str, *, workspace_id: str | None = None) -> dict[str, Any]:
    state = load_canonical_session_scientific_state(session_id, workspace_id=workspace_id)
    recommendations = state["recommendations"]
    model_outputs = {
        str(item.get("candidate_id") or ""): item
        for item in state["model_outputs"]
    }
    top_experiments: list[dict[str, Any]] = []
    risk_counts: dict[str, int] = {}
    for item in recommendations:
        output = model_outputs.get(str(item.get("candidate_id") or ""), {})
        row_payload = dict(item.get("payload") or {})
        top_experiments.append(
            {
                **row_payload,
                "session_id": session_id,
                "rank": item.get("rank"),
                "candidate_id": item.get("candidate_id"),
                "smiles": item.get("smiles"),
                "canonical_smiles": item.get("canonical_smiles"),
                "confidence": output.get("confidence"),
                "uncertainty": output.get("uncertainty"),
                "novelty": output.get("novelty"),
                "predicted_value": output.get("predicted_value"),
                "prediction_dispersion": output.get("prediction_dispersion"),
                "bucket": item.get("bucket"),
                "risk": item.get("risk"),
                "status": item.get("status"),
                "priority_score": item.get("priority_score"),
                "experiment_value": item.get("experiment_value"),
                "acquisition_score": item.get("acquisition_score"),
                "rationale": item.get("rationale"),
                "decision_policy": item.get("policy_trace"),
                "final_recommendation": item.get("recommendation"),
                "normalized_explanation": item.get("normalized_explanation"),
                "target_definition": state["target_definition"],
                "applicability_domain": output.get("applicability") or {},
                "provenance": output.get("provenance") or {},
                "review_summary": (item.get("governance") or {}).get("review_summary") or {},
            }
        )
        risk = str(item.get("risk") or "medium")
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
    return {
        "session_id": session_id,
        "iteration": 1,
        "generated_at": _utc_now().isoformat(),
        "summary": {
            "top_k": len(top_experiments),
            "candidate_count": len(recommendations),
            "risk_counts": risk_counts,
            "top_experiment_value": float(top_experiments[0].get("experiment_value") or 0.0) if top_experiments else 0.0,
        },
        "top_experiments": top_experiments,
        "target_definition": state["target_definition"],
        "run_contract": dict((state.get("run_metadata") or {}).get("run_contract") or {}),
        "comparison_anchors": dict((state.get("run_metadata") or {}).get("comparison_anchors") or {}),
        "artifact_state": "ok",
        "load_error": "",
        "source_path": "scientific_state://recommendation_records",
        "source_updated_at": _utc_now().isoformat(),
        "scientific_state_diagnostics": state.get("diagnostics") or {},
    }


def synthesize_analysis_report_from_scientific_state(session_id: str, *, workspace_id: str | None = None) -> dict[str, Any]:
    state = load_canonical_session_scientific_state(session_id, workspace_id=workspace_id)
    evidence = state["evidence_records"]
    target_definition = state["target_definition"]
    run_metadata = dict(state.get("run_metadata") or {})
    rows_with_values = sum(1 for item in evidence if item.get("evidence_type") == "observed_measurement")
    rows_with_labels = sum(1 for item in evidence if item.get("evidence_type") == "observed_label")
    rows_total = sum(1 for item in evidence if item.get("evidence_type") == "structure_input")
    baseline_fallback = any(item.get("baseline_fallback_used") for item in state["model_outputs"])
    warnings = []
    if baseline_fallback:
        warnings.append("This run reused the legacy baseline classification bundle; treat the ranking as bridge-state guidance.")
    return {
        "session_id": session_id,
        "target_definition": target_definition,
        "measurement_summary": {
            "rows_with_values": rows_with_values,
            "rows_without_values": max(rows_total - rows_with_values, 0),
            "rows_with_labels": rows_with_labels,
            "rows_without_labels": max(rows_total - rows_with_labels, 0),
            "value_column": target_definition.get("measurement_column") or "",
            "label_source": "explicit" if rows_with_labels > 0 else "",
            "semantic_mode": target_definition.get("dataset_type") or "",
        },
        "warnings": warnings,
        "top_candidates_returned": len(state["recommendations"]),
        "comparison_anchors": dict(run_metadata.get("comparison_anchors") or {}),
        "run_contract": dict(run_metadata.get("run_contract") or {}),
        "ranking_policy": dict(run_metadata.get("ranking_policy") or {}),
        "ranking_diagnostics": dict(run_metadata.get("ranking_diagnostics") or {}),
        "artifact_state": "ok",
        "load_error": "",
        "source_path": "scientific_state://analysis_projection",
        "source_updated_at": _utc_now().isoformat(),
        "scientific_state_diagnostics": state.get("diagnostics") or {},
    }
