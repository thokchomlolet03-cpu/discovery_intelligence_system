from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from system.services.run_metadata_service import build_comparison_anchors, build_run_contract, build_run_provenance, infer_comparison_anchors
from system.services.belief_read_service import build_session_belief_read_model
from system.services.claim_read_service import build_session_claim_detail_items
from system.services.experiment_read_service import build_session_experiment_lifecycle_read_model
from system.services.epistemic_ui_service import (
    build_focused_claim_inspection,
    build_focused_experiment_inspection,
    build_epistemic_entry_points,
    build_session_epistemic_detail_reveal,
    build_session_epistemic_summary,
)
from system.services.scientific_state_service import load_canonical_session_scientific_state
from system.services.session_identity_service import build_metric_interpretation, build_session_identity, build_trust_context
from system.services.status_semantics_service import build_status_semantics
from system.services.workspace_feedback_service import build_session_workspace_memory
from system.session_artifacts import load_analysis_report_payload, load_decision_artifact_payload


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


def _to_iso(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        target = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return target.isoformat()
    text = str(value).strip()
    return text


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _evidence_summary(evidence_records: list[dict[str, Any]], target_definition: dict[str, Any]) -> dict[str, Any]:
    rows_total = sum(1 for item in evidence_records if item.get("evidence_type") == "structure_input")
    rows_with_values = sum(1 for item in evidence_records if item.get("evidence_type") == "observed_measurement")
    rows_with_labels = sum(1 for item in evidence_records if item.get("evidence_type") == "observed_label")
    return {
        "rows_total": rows_total,
        "rows_with_values": rows_with_values,
        "rows_without_values": max(rows_total - rows_with_values, 0),
        "rows_with_labels": rows_with_labels,
        "rows_without_labels": max(rows_total - rows_with_labels, 0),
        "value_column": _clean_text(target_definition.get("measurement_column")),
        "label_source": "explicit" if rows_with_labels > 0 else "",
        "semantic_mode": _clean_text(target_definition.get("dataset_type")),
        "evidence_types_present": sorted(
            {
                _clean_text(item.get("evidence_type"))
                for item in evidence_records
                if _clean_text(item.get("evidence_type"))
            }
        ),
    }


def _candidate_preview(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for item in recommendations[:5]:
        rationale = item.get("rationale") if isinstance(item.get("rationale"), dict) else {}
        canonical_smiles = _clean_text(item.get("canonical_smiles") or item.get("smiles"))
        preview.append(
            {
                "key": f"smiles::{canonical_smiles}" if canonical_smiles else f"id::{_clean_text(item.get('candidate_id'))}",
                "rank_position": int(item.get("rank") or 0),
                "candidate_id": _clean_text(item.get("candidate_id")),
                "label": (
                    f"{_clean_text(item.get('candidate_id'))} ({canonical_smiles})"
                    if _clean_text(item.get("candidate_id")) and canonical_smiles and _clean_text(item.get("candidate_id")) != canonical_smiles
                    else _clean_text(item.get("candidate_id")) or canonical_smiles or "candidate"
                ),
                "smiles": _clean_text(item.get("smiles")),
                "canonical_smiles": canonical_smiles,
                "bucket": _clean_text(item.get("bucket"), default="unassigned").lower(),
                "trust_label": _clean_text(rationale.get("trust_label"), default="not_recorded").lower(),
                "priority_score": _safe_float(item.get("priority_score")),
                "experiment_value": _safe_float(item.get("experiment_value")),
            }
        )
    return preview


def _governance_summary(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(_clean_text(item.get("status"), default="suggested") for item in recommendations)
    latest_reviewed_at = ""
    latest_review: dict[str, Any] | None = None
    for item in recommendations:
        review_summary = (item.get("governance") or {}).get("review_summary") if isinstance(item.get("governance"), dict) else {}
        reviewed_at = _to_iso((review_summary or {}).get("reviewed_at"))
        if reviewed_at and reviewed_at > latest_reviewed_at:
            latest_reviewed_at = reviewed_at
            latest_review = review_summary
    return {
        "counts": dict(counts),
        "pending_review": int(counts.get("suggested", 0) + counts.get("under review", 0)),
        "approved": int(counts.get("approved", 0)),
        "rejected": int(counts.get("rejected", 0)),
        "tested": int(counts.get("tested", 0)),
        "ingested": int(counts.get("ingested", 0)),
        "latest_review_summary": latest_review or {},
        "latest_reviewed_at": latest_reviewed_at,
    }


def _carryover_summary(carryover_records: list[dict[str, Any]]) -> dict[str, Any]:
    source_sessions = sorted({_clean_text(item.get("source_session_id")) for item in carryover_records if _clean_text(item.get("source_session_id"))})
    latest = max((_to_iso(item.get("source_reviewed_at")) for item in carryover_records if _to_iso(item.get("source_reviewed_at"))), default="")
    continuity_source = "canonical_carryover" if carryover_records else "not_recorded"
    return {
        "record_count": len(carryover_records),
        "source_session_count": len(source_sessions),
        "source_session_ids": source_sessions,
        "latest_source_reviewed_at": latest,
        "continuity_source": continuity_source,
        "matches": carryover_records[:6],
    }


def _outcome_profile(recommendations: list[dict[str, Any]], model_outputs: list[dict[str, Any]], analysis_report: dict[str, Any]) -> dict[str, Any]:
    bucket_counts = {"exploit": 0, "learn": 0, "explore": 0, "unassigned": 0}
    trust_counts = {
        "stronger_trust": 0,
        "mixed_trust": 0,
        "exploratory_trust": 0,
        "high_caution": 0,
        "unlabeled": 0,
    }
    outputs_by_candidate = {str(item.get("candidate_id") or ""): item for item in model_outputs}
    for item in recommendations:
        bucket = _clean_text(item.get("bucket"), default="unassigned").lower()
        if bucket not in bucket_counts:
            bucket = "unassigned"
        bucket_counts[bucket] += 1
        rationale = item.get("rationale") if isinstance(item.get("rationale"), dict) else {}
        trust_label = _clean_text(rationale.get("trust_label")).lower()
        if trust_label == "stronger trust":
            trust_counts["stronger_trust"] += 1
        elif trust_label == "mixed trust":
            trust_counts["mixed_trust"] += 1
        elif trust_label == "exploratory trust":
            trust_counts["exploratory_trust"] += 1
        elif trust_label == "high caution":
            trust_counts["high_caution"] += 1
        else:
            trust_counts["unlabeled"] += 1
    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = ranking_diagnostics if isinstance(ranking_diagnostics, dict) else {}
    return {
        "bucket_counts": bucket_counts,
        "leading_bucket": max(bucket_counts.items(), key=lambda item: item[1], default=("unassigned", 0))[0],
        "bucket_summary": f"Exploit {bucket_counts['exploit']} / Learn {bucket_counts['learn']} / Explore {bucket_counts['explore']}",
        "trust_counts": trust_counts,
        "dominant_trust": max(trust_counts.items(), key=lambda item: item[1], default=("unlabeled", 0))[0],
        "trust_summary": (
            f"Stronger trust {trust_counts['stronger_trust']} / Mixed {trust_counts['mixed_trust']} / "
            f"Exploratory {trust_counts['exploratory_trust']} / High caution {trust_counts['high_caution']}"
        ),
        "out_of_domain_rate": _safe_float(ranking_diagnostics.get("out_of_domain_rate")),
        "spearman_rank_correlation": _safe_float(ranking_diagnostics.get("spearman_rank_correlation")),
        "top_k_measurement_lift": _safe_float(ranking_diagnostics.get("top_k_measurement_lift")),
        "candidate_output_count": len(outputs_by_candidate),
    }


def _predictive_summary(model_outputs: list[dict[str, Any]], analysis_report: dict[str, Any]) -> dict[str, Any]:
    confidences = [_safe_float(item.get("confidence")) for item in model_outputs]
    confidences = [value for value in confidences if value is not None]
    uncertainties = [_safe_float(item.get("uncertainty")) for item in model_outputs]
    uncertainties = [value for value in uncertainties if value is not None]
    novelty_values = [_safe_float(item.get("novelty")) for item in model_outputs]
    novelty_values = [value for value in novelty_values if value is not None]
    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = ranking_diagnostics if isinstance(ranking_diagnostics, dict) else {}
    baseline_fallback_used = any(bool(item.get("baseline_fallback_used")) for item in model_outputs)
    return {
        "candidate_count": len(model_outputs),
        "average_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "average_uncertainty": round(sum(uncertainties) / len(uncertainties), 4) if uncertainties else None,
        "average_novelty": round(sum(novelty_values) / len(novelty_values), 4) if novelty_values else None,
        "out_of_domain_rate": _safe_float(ranking_diagnostics.get("out_of_domain_rate")),
        "spearman_rank_correlation": _safe_float(ranking_diagnostics.get("spearman_rank_correlation")),
        "top_k_measurement_lift": _safe_float(ranking_diagnostics.get("top_k_measurement_lift")),
        "baseline_fallback_used": baseline_fallback_used,
    }


def _candidate_overlay_rows(
    recommendations: list[dict[str, Any]],
    model_outputs: list[dict[str, Any]],
    carryover_records: list[dict[str, Any]],
    target_definition: dict[str, Any],
    candidate_states: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if isinstance(candidate_states, list) and candidate_states:
        rows: list[dict[str, Any]] = []
        for item in candidate_states:
            predictive = _as_dict(item.get("predictive_summary"))
            recommendation = _as_dict(item.get("recommendation_summary"))
            governance = _as_dict(item.get("governance_summary"))
            rows.append(
                {
                    "candidate_id": _clean_text(item.get("candidate_id")),
                    "smiles": _clean_text(item.get("smiles")),
                    "canonical_smiles": _clean_text(item.get("canonical_smiles")),
                    "rank": _safe_int(item.get("rank")),
                    "priority_score": _safe_float(recommendation.get("priority_score")),
                    "experiment_value": _safe_float(recommendation.get("experiment_value")),
                    "bucket": _clean_text(recommendation.get("bucket"), default="unassigned"),
                    "risk": _clean_text(recommendation.get("risk"), default="medium"),
                    "status": _clean_text(governance.get("status") or recommendation.get("status"), default="suggested"),
                    "confidence": _safe_float(predictive.get("confidence")),
                    "uncertainty": _safe_float(predictive.get("uncertainty")),
                    "novelty": _safe_float(predictive.get("novelty")),
                    "predicted_value": _safe_float(predictive.get("predicted_value")),
                    "prediction_dispersion": _safe_float(predictive.get("prediction_dispersion")),
                    "provenance": {"text": _clean_text((item.get("source_payload") or {}).get("model_output_record", {}).get("provenance", {}).get("text"))},
                    "applicability_domain": _as_dict(predictive.get("applicability")),
                    "rationale": _as_dict(recommendation.get("rationale")),
                    "decision_policy": _as_dict(recommendation.get("decision_policy")),
                    "final_recommendation": _as_dict(recommendation.get("final_recommendation")),
                    "normalized_explanation": _as_dict(recommendation.get("normalized_explanation")),
                    "review_summary": _as_dict(governance.get("review_summary")),
                    "review_note": _clean_text(governance.get("review_note")),
                    "reviewer": _clean_text(governance.get("reviewer")),
                    "reviewed_at": _to_iso(governance.get("reviewed_at")),
                    "target_definition": target_definition,
                    "carryover_summary": _as_dict(item.get("carryover_summary")),
                    "candidate_state_provenance": "canonical_persisted_candidate_state",
                    "candidate_field_provenance": _as_dict(item.get("provenance_markers")),
                    "candidate_trust_summary": _as_dict(item.get("trust_summary")),
                }
            )
        return rows

    outputs_by_key: dict[str, dict[str, Any]] = {}
    for item in model_outputs:
        candidate_id = _clean_text(item.get("candidate_id"))
        canonical_smiles = _clean_text(item.get("canonical_smiles") or item.get("smiles"))
        if candidate_id:
            outputs_by_key[f"id::{candidate_id}"] = item
        if canonical_smiles:
            outputs_by_key[f"smiles::{canonical_smiles}"] = item

    carryover_by_smiles: dict[str, list[dict[str, Any]]] = {}
    for item in carryover_records:
        canonical_smiles = _clean_text(item.get("canonical_smiles") or item.get("smiles"))
        if canonical_smiles:
            carryover_by_smiles.setdefault(canonical_smiles, []).append(item)

    rows: list[dict[str, Any]] = []
    for item in recommendations:
        candidate_id = _clean_text(item.get("candidate_id"))
        canonical_smiles = _clean_text(item.get("canonical_smiles") or item.get("smiles"))
        output = outputs_by_key.get(f"id::{candidate_id}") or outputs_by_key.get(f"smiles::{canonical_smiles}") or {}
        governance = _as_dict(item.get("governance"))
        review_summary = _as_dict(governance.get("review_summary"))
        carryover_matches = carryover_by_smiles.get(canonical_smiles, [])
        rationale = _as_dict(item.get("rationale"))
        rows.append(
            {
                "candidate_id": candidate_id,
                "smiles": _clean_text(item.get("smiles")),
                "canonical_smiles": canonical_smiles,
                "rank": _safe_int(item.get("rank")),
                "priority_score": _safe_float(item.get("priority_score")),
                "experiment_value": _safe_float(item.get("experiment_value")),
                "bucket": _clean_text(item.get("bucket"), default="unassigned"),
                "risk": _clean_text(item.get("risk"), default="medium"),
                "status": _clean_text(item.get("status"), default="suggested"),
                "confidence": _safe_float(output.get("confidence")),
                "uncertainty": _safe_float(output.get("uncertainty")),
                "novelty": _safe_float(output.get("novelty")),
                "predicted_value": _safe_float(output.get("predicted_value")),
                "prediction_dispersion": _safe_float(output.get("prediction_dispersion")),
                "provenance": _as_dict(output.get("provenance")),
                "applicability_domain": _as_dict(output.get("applicability")),
                "rationale": rationale,
                "decision_policy": _as_dict(item.get("policy_trace")),
                "final_recommendation": _as_dict(item.get("recommendation")),
                "normalized_explanation": _as_dict(item.get("normalized_explanation")),
                "review_summary": review_summary,
                "review_note": _clean_text(governance.get("review_note")),
                "reviewer": _clean_text(governance.get("reviewer")),
                "reviewed_at": _to_iso(governance.get("reviewed_at")),
                "target_definition": target_definition,
                "carryover_summary": {
                    "record_count": len(carryover_matches),
                    "latest_source_reviewed_at": max((_to_iso(match.get("source_reviewed_at")) for match in carryover_matches), default=""),
                    "source_session_ids": sorted({_clean_text(match.get("source_session_id")) for match in carryover_matches if _clean_text(match.get("source_session_id"))}),
                },
                "candidate_state_provenance": "projection_overlay",
            }
        )
    return rows


def _ranking_policy_summary(
    recommendations: list[dict[str, Any]],
    target_definition: dict[str, Any],
    analysis_report: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    raw_policy = _as_dict(analysis_report.get("ranking_policy"))
    if raw_policy:
        return (
            {
                **raw_policy,
                "policy_source": "legacy_analysis_report",
                "primary_score_label": _clean_text(raw_policy.get("primary_score_label"), default="Priority score"),
            },
            "legacy_analysis_report",
        )

    target_kind = _clean_text(target_definition.get("target_kind"), default="classification").lower()
    measurement_mode = target_kind == "regression"
    sort_order = ["priority_score", "experiment_value", "novelty"]
    primary_score_label = "Ranking compatibility" if measurement_mode else "Priority score"
    summary = (
        "Candidate ordering emphasizes ranking compatibility first, then experiment value and novelty."
        if measurement_mode
        else "Candidate ordering emphasizes composite priority first, then experiment value and novelty."
    )
    return (
        {
            "primary_score": "priority_score",
            "primary_score_label": primary_score_label,
            "sort_order": sort_order,
            "weights": {"confidence": 0.30, "uncertainty": 0.20, "novelty": 0.15, "experiment_value": 0.35},
            "formula_label": "priority_score",
            "formula_summary": summary,
            "formula_text": summary,
            "policy_source": "projection_synthesized",
        },
        "projection_synthesized",
    )


def _ranking_diagnostic_summary(
    recommendations: list[dict[str, Any]],
    model_outputs: list[dict[str, Any]],
    analysis_report: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    legacy = _as_dict(analysis_report.get("ranking_diagnostics"))
    if legacy:
        return ({**legacy, "diagnostic_source": "legacy_analysis_report"}, "legacy_analysis_report")

    outputs_by_candidate = {
        _clean_text(item.get("candidate_id")): item
        for item in model_outputs
        if _clean_text(item.get("candidate_id"))
    }
    uncertainties = []
    out_of_domain = 0
    for item in recommendations:
        output = outputs_by_candidate.get(_clean_text(item.get("candidate_id"))) or {}
        uncertainty = _safe_float(output.get("uncertainty"))
        if uncertainty is not None:
            uncertainties.append(uncertainty)
        applicability = _as_dict(output.get("applicability"))
        status = _clean_text(applicability.get("status") or item.get("domain_status")).lower()
        if status == "out_of_domain":
            out_of_domain += 1
    recommendation_count = max(len(recommendations), 1)
    return (
        {
            "candidate_count": len(recommendations),
            "average_uncertainty": round(sum(uncertainties) / len(uncertainties), 4) if uncertainties else None,
            "out_of_domain_rate": round(out_of_domain / recommendation_count, 4) if recommendations else None,
            "high_caution_count": sum(1 for item in recommendations if _clean_text(item.get("risk")).lower() == "high"),
            "diagnostic_source": "projection_synthesized",
        },
        "projection_synthesized",
    )


def _resolve_run_contract(
    *,
    session_record: dict[str, Any],
    upload_metadata: dict[str, Any],
    analysis_report: dict[str, Any],
    decision_payload: dict[str, Any],
    target_definition: dict[str, Any],
    model_outputs: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    summary_metadata = _as_dict(session_record.get("summary_metadata"))
    summary_contract = _as_dict(summary_metadata.get("run_contract"))
    if summary_contract:
        return (summary_contract, "session_summary_metadata")

    payload_contract = _as_dict(analysis_report.get("run_contract")) or _as_dict(decision_payload.get("run_contract"))
    if payload_contract:
        return (payload_contract, "legacy_artifact")

    first_output = model_outputs[0] if model_outputs else {}
    scientific_contract = {
        "target_model_available": bool(model_outputs),
        "fallback_reason": _clean_text((first_output.get("diagnostics") or {}).get("fallback_reason")),
    }
    bundle = {
        "training_scope": _clean_text(first_output.get("training_scope")),
        "model_family": _clean_text(first_output.get("model_family"), default="random_forest"),
        "selected_model": {
            "name": _clean_text(first_output.get("model_name")),
            "calibration_method": _clean_text(first_output.get("calibration_method")),
        },
    }
    return (
        build_run_contract(
            session_id=_clean_text(session_record.get("session_id") or upload_metadata.get("session_id")),
            source_name=_clean_text(session_record.get("source_name") or upload_metadata.get("filename")),
            input_type=_clean_text(session_record.get("input_type") or upload_metadata.get("input_type")),
            requested_intent=_clean_text(upload_metadata.get("requested_intent") or upload_metadata.get("decision_intent")),
            decision_intent=_clean_text(decision_payload.get("decision_intent") or upload_metadata.get("decision_intent"), default="prioritize_experiments"),
            modeling_mode=_clean_text(decision_payload.get("modeling_mode") or target_definition.get("target_kind"), default="ranking_only"),
            scoring_mode=_clean_text(decision_payload.get("scoring_mode") or decision_payload.get("mode_used"), default="balanced"),
            target_definition=target_definition,
            scientific_contract=scientific_contract,
            contract_versions=_as_dict(upload_metadata.get("contract_versions")),
            validation_summary=_as_dict(upload_metadata.get("validation_summary")),
            bundle=bundle,
        ),
        "projection_synthesized",
    )


def _resolve_comparison_anchors(
    *,
    session_record: dict[str, Any],
    upload_metadata: dict[str, Any],
    analysis_report: dict[str, Any],
    decision_payload: dict[str, Any],
    run_contract: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    summary_metadata = _as_dict(session_record.get("summary_metadata"))
    summary_anchors = _as_dict(summary_metadata.get("comparison_anchors"))
    if summary_anchors:
        return (summary_anchors, "session_summary_metadata")

    payload_anchors = _as_dict(analysis_report.get("comparison_anchors")) or _as_dict(decision_payload.get("comparison_anchors"))
    if payload_anchors:
        return (payload_anchors, "legacy_artifact")

    return (
        build_comparison_anchors(
            session_id=_clean_text(session_record.get("session_id") or upload_metadata.get("session_id")),
            source_name=_clean_text(session_record.get("source_name") or upload_metadata.get("filename")),
            input_type=_clean_text(session_record.get("input_type") or upload_metadata.get("input_type")),
            column_mapping=_as_dict(upload_metadata.get("selected_mapping") or upload_metadata.get("semantic_roles") or upload_metadata.get("inferred_mapping")),
            target_definition=_as_dict(run_contract.get("target_definition")),
            decision_intent=_clean_text(run_contract.get("decision_intent")),
            modeling_mode=_clean_text(run_contract.get("modeling_mode")),
            scoring_mode=_clean_text(run_contract.get("scoring_mode")),
            contract_versions=_as_dict(upload_metadata.get("contract_versions")),
            validation_summary=_as_dict(upload_metadata.get("validation_summary")),
            run_contract=run_contract,
        ),
        "projection_synthesized",
    )


def _run_interpretation_summary(
    run_provenance: dict[str, Any],
    ranking_diagnostics: dict[str, Any],
    governance_summary: dict[str, Any],
) -> dict[str, Any]:
    cautions: list[str] = list(run_provenance.get("cautions") or [])
    out_of_domain_rate = _safe_float(ranking_diagnostics.get("out_of_domain_rate"))
    if out_of_domain_rate is not None and out_of_domain_rate >= 0.5:
        cautions.append(f"A large share of shortlisted candidates sits outside stronger chemistry coverage ({out_of_domain_rate * 100:.1f}% out of domain).")
    pending_review = _safe_int(governance_summary.get("pending_review"))
    if pending_review > 0:
        cautions.append(f"{pending_review} candidates remain pending review.")
    return {
        "comparison_summary": _clean_text(run_provenance.get("comparison_summary")),
        "model_summary": _clean_text(run_provenance.get("model_summary")),
        "policy_summary": _clean_text(run_provenance.get("policy_summary")),
        "bridge_state_summary": _clean_text(run_provenance.get("bridge_state_summary")),
        "cautions": cautions[:4],
    }


def _recommendation_summary(
    recommendations: list[dict[str, Any]],
    outcome_profile: dict[str, Any],
    target_definition: dict[str, Any],
) -> str:
    if not recommendations:
        return ""
    lead = recommendations[0] if isinstance(recommendations[0], dict) else {}
    candidate_id = _clean_text(lead.get("candidate_id") or lead.get("canonical_smiles") or lead.get("smiles"), default="the lead candidate")
    bucket = _clean_text(lead.get("bucket"), default="review").lower()
    target_name = _clean_text(target_definition.get("target_name"), default="the current target")
    if bucket == "exploit":
        return f"Start with {candidate_id} as the strongest near-term testing candidate for {target_name}."
    if bucket == "learn":
        return f"Lead with {candidate_id} to reduce uncertainty around {target_name} before treating the shortlist as settled."
    if bucket == "explore":
        return f"Use {candidate_id} as an exploratory candidate to widen chemical coverage around {target_name}."
    leading_bucket = _clean_text(outcome_profile.get("leading_bucket"), default="review")
    return f"Review {candidate_id} first while treating the broader shortlist as {leading_bucket.replace('_', ' ')} guidance."


def _diagnostic_warnings(
    diagnostics: dict[str, Any],
    run_provenance: dict[str, Any],
    carryover_summary: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if diagnostics.get("legacy_fallback_used"):
        warnings.append("Legacy artifact fallback was required to build this session projection.")
    legacy_merge_fields = diagnostics.get("legacy_merge_fields") if isinstance(diagnostics.get("legacy_merge_fields"), list) else []
    if legacy_merge_fields:
        warnings.append(f"Legacy merge fields remain active: {', '.join(legacy_merge_fields)}.")
    if bool(run_provenance.get("bridge_state_active")):
        warnings.append(str(run_provenance.get("bridge_state_summary") or "Baseline-model fallback remains visible in run provenance.").strip())
    if _clean_text(carryover_summary.get("continuity_source")) != "canonical_carryover":
        warnings.append("No explicit canonical carryover records were available for this session.")
    return warnings[:4]


def build_scientific_session_projection(
    *,
    session_record: dict[str, Any] | None,
    workspace_id: str | None = None,
    upload_metadata: dict[str, Any] | None = None,
    current_job: dict[str, Any] | None = None,
    include_workspace_memory: bool = True,
    review_events: list[dict[str, Any]] | None = None,
    session_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    session_record = session_record or {}
    upload_metadata = upload_metadata or (session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {})
    session_id = _clean_text(session_record.get("session_id") or upload_metadata.get("session_id"))
    effective_workspace_id = _clean_text(workspace_id or session_record.get("workspace_id"))

    if not session_id:
        return {
            "session_id": "",
            "diagnostics": {"projection_source": "missing_session", "canonical_projection_used": False},
        }

    diagnostics = {
        "projection_source": "canonical_sql",
        "canonical_projection_used": False,
        "legacy_fallback_used": False,
        "legacy_merge_fields": [],
        "missing_canonical_fields": [],
        "baseline_model_fallback_visible": False,
        "field_provenance": {},
    }

    try:
        state = load_canonical_session_scientific_state(session_id, workspace_id=effective_workspace_id or None)
        diagnostics["canonical_projection_used"] = True
    except FileNotFoundError:
        state = {
            "session_id": session_id,
            "target_definition": {},
            "evidence_records": [],
            "model_outputs": [],
            "recommendations": [],
            "carryover_records": [],
            "diagnostics": {"scientific_state_source": "missing"},
        }
        diagnostics["projection_source"] = "legacy_fallback"
        diagnostics["legacy_fallback_used"] = True

    decision_payload = load_decision_artifact_payload(
        session_id=session_id,
        workspace_id=effective_workspace_id or None,
        allow_global_fallback=not bool(effective_workspace_id),
    )
    analysis_report = load_analysis_report_payload(
        session_id=session_id,
        workspace_id=effective_workspace_id or None,
        allow_global_fallback=not bool(effective_workspace_id),
    )

    target_definition = dict(state.get("target_definition") or {})
    if not target_definition:
        diagnostics["legacy_fallback_used"] = True
        diagnostics["legacy_merge_fields"].append("target_definition")
        target_definition = (
            analysis_report.get("target_definition") if isinstance(analysis_report.get("target_definition"), dict) else {}
        ) or (
            decision_payload.get("target_definition") if isinstance(decision_payload.get("target_definition"), dict) else {}
        ) or (
            upload_metadata.get("target_definition") if isinstance(upload_metadata.get("target_definition"), dict) else {}
        )

    evidence_records = list(state.get("evidence_records") or [])
    model_outputs = list(state.get("model_outputs") or [])
    recommendations = list(state.get("recommendations") or [])
    carryover_records = list(state.get("carryover_records") or [])
    candidate_states = list(state.get("candidate_states") or [])
    claims = list(state.get("claims") or [])
    run_metadata = dict(state.get("run_metadata") or {})

    if not recommendations:
        diagnostics["legacy_fallback_used"] = True
        diagnostics["legacy_merge_fields"].append("recommendations")
        recommendations = list(decision_payload.get("top_experiments") or [])
    if not model_outputs:
        diagnostics["missing_canonical_fields"].append("model_outputs")
    if not evidence_records:
        diagnostics["missing_canonical_fields"].append("evidence_records")

    measurement_summary = _evidence_summary(evidence_records, target_definition)
    if measurement_summary["rows_total"] <= 0:
        diagnostics["legacy_merge_fields"].append("measurement_summary")
        report_measurement = analysis_report.get("measurement_summary") if isinstance(analysis_report.get("measurement_summary"), dict) else {}
        measurement_summary = {
            **measurement_summary,
            **report_measurement,
        }

    persisted_run_contract = _as_dict(run_metadata.get("run_contract"))
    if persisted_run_contract:
        run_contract, run_contract_source = persisted_run_contract, "canonical_persisted_run_metadata"
    else:
        run_contract, run_contract_source = _resolve_run_contract(
            session_record=session_record,
            upload_metadata=upload_metadata,
            analysis_report=analysis_report,
            decision_payload=decision_payload,
            target_definition=target_definition,
            model_outputs=model_outputs,
        )
    persisted_comparison_anchors = _as_dict(run_metadata.get("comparison_anchors"))
    if persisted_comparison_anchors:
        comparison_anchors, comparison_anchors_source = persisted_comparison_anchors, "canonical_persisted_run_metadata"
    else:
        comparison_anchors, comparison_anchors_source = _resolve_comparison_anchors(
            session_record=session_record,
            upload_metadata=upload_metadata,
            analysis_report=analysis_report,
            decision_payload=decision_payload,
            run_contract=run_contract,
        )
    persisted_ranking_policy = _as_dict(run_metadata.get("ranking_policy"))
    if persisted_ranking_policy:
        ranking_policy, ranking_policy_source = persisted_ranking_policy, "canonical_persisted_run_metadata"
    else:
        ranking_policy, ranking_policy_source = _ranking_policy_summary(
            recommendations,
            target_definition,
            analysis_report,
        )
    persisted_ranking_diagnostics = _as_dict(run_metadata.get("ranking_diagnostics"))
    if persisted_ranking_diagnostics:
        ranking_diagnostics, ranking_diagnostics_source = persisted_ranking_diagnostics, "canonical_persisted_run_metadata"
    else:
        ranking_diagnostics, ranking_diagnostics_source = _ranking_diagnostic_summary(
            recommendations,
            model_outputs,
            analysis_report,
        )
    diagnostics["field_provenance"].update(
        {
            "run_contract": run_contract_source,
            "comparison_anchors": comparison_anchors_source,
            "ranking_policy": ranking_policy_source,
            "ranking_diagnostics": ranking_diagnostics_source,
        }
    )
    for field_name, field_source in diagnostics["field_provenance"].items():
        if field_source == "legacy_artifact" or field_source == "legacy_analysis_report":
            diagnostics["legacy_merge_fields"].append(field_name)
        elif field_source == "projection_synthesized":
            continue
        elif field_source == "session_summary_metadata":
            continue

    top_level_recommendation_summary = _clean_text(analysis_report.get("top_level_recommendation_summary"))
    if top_level_recommendation_summary:
        diagnostics["legacy_merge_fields"].append("top_level_recommendation_summary")

    run_provenance = build_run_provenance(
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
    )
    trust_context = build_trust_context(
        target_definition=target_definition,
        modeling_mode=_clean_text(
            analysis_report.get("modeling_mode") or decision_payload.get("modeling_mode") or run_contract.get("modeling_mode")
        ),
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        validation_summary=upload_metadata.get("validation_summary") if isinstance(upload_metadata.get("validation_summary"), dict) else {},
        ranking_policy=ranking_policy,
        run_provenance=run_provenance,
    )
    metric_interpretation = build_metric_interpretation(
        target_definition=target_definition,
        modeling_mode=_clean_text(
            analysis_report.get("modeling_mode") or decision_payload.get("modeling_mode") or run_contract.get("modeling_mode")
        ),
        ranking_policy=ranking_policy,
    )
    governance_summary = _governance_summary(recommendations)
    carryover_summary = _carryover_summary(carryover_records)
    outcome_profile = _outcome_profile(recommendations, model_outputs, {"ranking_diagnostics": ranking_diagnostics})
    predictive_summary = _predictive_summary(model_outputs, analysis_report)
    candidate_preview = _candidate_preview(recommendations)
    recommendation_summary = _recommendation_summary(recommendations, outcome_profile, target_definition)
    candidate_projection_rows = _candidate_overlay_rows(
        recommendations,
        model_outputs,
        carryover_records,
        target_definition,
        candidate_states,
    )

    workspace_memory = {}
    if include_workspace_memory:
        workspace_memory = build_session_workspace_memory(
            recommendations,
            session_id=session_id,
            workspace_id=effective_workspace_id or None,
            review_events=review_events,
            session_labels=session_labels,
        )

    status_semantics = build_status_semantics(
        session_record=session_record,
        upload_metadata=upload_metadata,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        current_job=current_job,
    )
    session_identity = build_session_identity(
        session_record=session_record,
        upload_metadata=upload_metadata,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        current_job=current_job,
    )

    trust_summary = _as_dict(run_metadata.get("trust_summary"))
    if trust_summary:
        diagnostics["field_provenance"]["trust_summary"] = "canonical_persisted_run_metadata"
    else:
        diagnostics["field_provenance"]["trust_summary"] = "projection_synthesized"
    diagnostics["baseline_model_fallback_visible"] = bool(
        _safe_int(trust_summary.get("baseline_fallback_visible"), default=0)
        or run_provenance.get("bridge_state_active")
        or any(bool(item.get("baseline_fallback_used")) for item in model_outputs)
    )
    diagnostics["diagnostic_warnings"] = _diagnostic_warnings(
        diagnostics,
        run_provenance,
        carryover_summary,
    )
    belief_read_model = build_session_belief_read_model(
        session_id=session_id,
        workspace_id=effective_workspace_id or None,
    )
    experiment_lifecycle_model = build_session_experiment_lifecycle_read_model(
        session_id=session_id,
        workspace_id=effective_workspace_id or None,
    )
    claim_detail_items = (
        build_session_claim_detail_items(
            session_id=session_id,
            workspace_id=effective_workspace_id or None,
        )
        if claims
        else []
    )
    claim_detail_summary = {
        "claim_detail_count": len(claim_detail_items),
        "candidate_linked_count": sum(
            1 for item in claim_detail_items if _clean_text(((item.get("claim") or {}).get("claim_scope"))) == "candidate"
        ),
        "run_linked_count": sum(
            1 for item in claim_detail_items if _clean_text(((item.get("claim") or {}).get("claim_scope"))) == "run"
        ),
        "claims_with_experiment_requests": sum(
            1 for item in claim_detail_items if bool(((item.get("experiment_detail") or {}).get("has_requests")))
        ),
        "claims_with_experiment_results": sum(
            1 for item in claim_detail_items if bool(((item.get("experiment_detail") or {}).get("has_results")))
        ),
        "claims_with_belief_updates": sum(
            1 for item in claim_detail_items if bool(((item.get("belief_update_summary") or {}).get("has_updates")))
        ),
        "claims_with_belief_state": sum(
            1 for item in claim_detail_items if bool(((item.get("current_belief_state") or {}).get("available")))
        ),
        "has_claim_detail_surface": bool(claim_detail_items),
        "absence_reason": "" if claim_detail_items else "no_claim_detail_available",
        "provenance": "canonical_epistemic_objects" if claim_detail_items else "absent",
    }
    diagnostics["claim_detail_surface_used"] = bool(claim_detail_items)
    diagnostics["claim_detail_source"] = "canonical_epistemic_objects" if claim_detail_items else "absent"
    diagnostics["claim_detail_absent_reason"] = "" if claim_detail_items else "no_claims_materialized"
    diagnostics["experiment_lifecycle_source"] = experiment_lifecycle_model.get("session_summary", {}).get("provenance", "absent")
    diagnostics["experiment_lifecycle_present"] = bool(experiment_lifecycle_model.get("session_summary", {}).get("has_experiments"))
    diagnostics["experiment_lifecycle_absent_reason"] = experiment_lifecycle_model.get("session_summary", {}).get("absence_reason", "")
    session_epistemic_summary = build_session_epistemic_summary(
        belief_layer_summary=dict((belief_read_model.get("session_summary") if isinstance(belief_read_model, dict) else {}) or {}),
        experiment_lifecycle_summary=dict((experiment_lifecycle_model.get("session_summary") if isinstance(experiment_lifecycle_model, dict) else {}) or {}),
        claim_detail_summary=claim_detail_summary,
    )
    epistemic_entry_points = build_epistemic_entry_points(
        claim_detail_summary=claim_detail_summary,
        experiment_lifecycle_summary=dict((experiment_lifecycle_model.get("session_summary") if isinstance(experiment_lifecycle_model, dict) else {}) or {}),
    )
    session_epistemic_detail_reveal = build_session_epistemic_detail_reveal(
        session_epistemic_summary=session_epistemic_summary,
        epistemic_entry_points=epistemic_entry_points,
        claim_detail_items=claim_detail_items,
        experiment_lifecycle_model=experiment_lifecycle_model,
    )
    focused_claim_inspection = build_focused_claim_inspection(
        claim_detail_items=claim_detail_items,
    )
    focused_experiment_inspection = build_focused_experiment_inspection(
        experiment_lifecycle_model=experiment_lifecycle_model,
    )
    diagnostics["session_epistemic_summary_available"] = bool(session_epistemic_summary.get("available"))
    diagnostics["session_epistemic_summary_status"] = session_epistemic_summary.get("status")
    diagnostics["session_epistemic_detail_affordance_available"] = bool(session_epistemic_detail_reveal.get("available"))
    diagnostics["focused_claim_inspection_available"] = bool(focused_claim_inspection.get("available"))
    diagnostics["focused_experiment_inspection_available"] = bool(focused_experiment_inspection.get("available"))
    diagnostics["focused_claim_choice_count"] = _safe_int(focused_claim_inspection.get("choice_count"))
    diagnostics["focused_experiment_choice_count"] = _safe_int(focused_experiment_inspection.get("choice_count"))
    diagnostics["focused_claim_multiple_available"] = bool(focused_claim_inspection.get("multiple_available"))
    diagnostics["focused_experiment_multiple_available"] = bool(focused_experiment_inspection.get("multiple_available"))
    diagnostics["focused_claim_default_first_fallback_used"] = bool(focused_claim_inspection.get("default_first_fallback_used"))
    diagnostics["focused_experiment_default_first_fallback_used"] = bool(
        focused_experiment_inspection.get("default_first_fallback_used")
    )
    diagnostics["focused_claim_selected_available"] = bool(focused_claim_inspection.get("selected_available"))
    diagnostics["focused_experiment_selected_available"] = bool(focused_experiment_inspection.get("selected_available"))
    diagnostics["candidate_epistemic_context_available"] = any(
        bool(item.get("claim_count")) or bool(item.get("has_experiment_request")) or bool(item.get("has_experiment_result"))
        for item in (belief_read_model.get("candidate_items") if isinstance(belief_read_model, dict) else [])
        if isinstance(item, dict)
    )
    diagnostics["epistemic_entry_points_available"] = bool(epistemic_entry_points.get("claim_detail_available") or epistemic_entry_points.get("experiment_lifecycle_available"))

    # Transitional note: ranking policy, run contract, comparison anchors, and some diagnostics
    # still come from artifact-era report/contracts because no canonical read object exists for them yet.
    return {
        "session_id": session_id,
        "workspace_id": effective_workspace_id,
        "source_name": _clean_text(session_record.get("source_name") or upload_metadata.get("filename"), default="Untitled upload"),
        "target_definition": target_definition,
        "evidence_records": evidence_records,
        "model_outputs": model_outputs,
        "recommendations": recommendations,
        "carryover_records": carryover_records,
        "measurement_summary": measurement_summary,
        "predictive_summary": predictive_summary,
        "ranking_diagnostics": ranking_diagnostics,
        "governance_summary": governance_summary,
        "carryover_summary": carryover_summary,
        "candidate_preview": candidate_preview,
        "candidate_projection_rows": candidate_projection_rows,
        "candidate_states": candidate_states,
        "claims": claims,
        "belief_layer_summary": dict((belief_read_model.get("session_summary") if isinstance(belief_read_model, dict) else {}) or {}),
        "belief_read_model": belief_read_model,
        "experiment_lifecycle_summary": dict((experiment_lifecycle_model.get("session_summary") if isinstance(experiment_lifecycle_model, dict) else {}) or {}),
        "experiment_lifecycle_model": experiment_lifecycle_model,
        "claim_detail_summary": claim_detail_summary,
        "claim_detail_items": claim_detail_items,
        "session_epistemic_summary": session_epistemic_summary,
        "epistemic_entry_points": epistemic_entry_points,
        "session_epistemic_detail_reveal": session_epistemic_detail_reveal,
        "focused_claim_inspection": focused_claim_inspection,
        "focused_experiment_inspection": focused_experiment_inspection,
        "outcome_profile": outcome_profile,
        "recommendation_summary": recommendation_summary,
        "run_interpretation_summary": _run_interpretation_summary(
            run_provenance,
            ranking_diagnostics,
            governance_summary,
        ),
        "decision_payload": decision_payload,
        "analysis_report": analysis_report,
        "run_contract": run_contract,
        "comparison_anchors": comparison_anchors,
        "ranking_policy": ranking_policy,
        "run_provenance": run_provenance,
        "run_metadata": run_metadata,
        "trust_summary": trust_summary,
        "trust_context": trust_context,
        "metric_interpretation": metric_interpretation,
        "status_semantics": status_semantics,
        "session_identity": session_identity,
        "workspace_memory": workspace_memory,
        "top_level_recommendation_summary": top_level_recommendation_summary,
        "diagnostics": diagnostics,
    }
