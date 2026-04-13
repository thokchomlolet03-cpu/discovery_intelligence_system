from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px

from system.contracts import ContractValidationError, normalize_loaded_decision_artifact
from system.db import resolve_artifact_path
from system.db.repositories import SessionRepository
from system.review_manager import build_review_queue
from system.services.run_metadata_service import build_run_provenance
from system.services.predictive_path_service import build_predictive_path_summary
from system.services.scientific_session_truth_service import build_scientific_session_truth
from system.services.scientific_decision_service import build_scientific_decision_summary
from system.services.data_service import canonical_label_column
from system.services.session_identity_service import build_metric_interpretation, build_trust_context, domain_chip_label
from system.services.belief_update_service import support_role_from_belief_update_summary
from system.services.workspace_feedback_service import build_session_workspace_memory
from system.session_artifacts import (
    load_analysis_report_payload,
    load_decision_artifact_payload,
    load_evaluation_summary_payload,
    load_scientific_session_truth_payload,
)
from utils.artifact_writer import REPO_ROOT, uploaded_session_dir


DATASET_PATHS = ("uploaded_dataset.csv", "data/data.csv", "data.csv")
DATASET_ARTIFACT_TYPES = ("upload_csv", "raw_upload_csv")
CANDIDATE_PATHS = ("scored_candidates.csv", "predicted_candidates.csv", "candidates_results.csv")
CANDIDATE_ARTIFACT_TYPES = ("scored_candidates_csv", "processed_candidates_csv")
REVIEW_QUEUE_PATHS = ("review_queue.json", "data/review_queue.json")
REVIEW_QUEUE_ARTIFACT_TYPES = ("review_queue_json",)
EVOLUTION_PATHS = ("iteration_history.csv",)
session_repository = SessionRepository()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _run_root(session_id: str | None) -> Path:
    if session_id:
        return uploaded_session_dir(session_id)
    return REPO_ROOT


def _find_artifact(run_root: Path, candidates: tuple[str, ...], *, include_repo_root: bool = True) -> Path | None:
    roots = [run_root]
    if include_repo_root and run_root.resolve() != REPO_ROOT.resolve():
        roots.append(REPO_ROOT)

    for root in roots:
        for relative in candidates:
            target = root / relative
            if target.exists():
                return target
    return None


def _resolve_run_artifact(
    *,
    session_id: str | None,
    workspace_id: str | None,
    run_root: Path,
    artifact_types: tuple[str, ...],
    fallback_candidates: tuple[str, ...],
) -> Path | None:
    fallback_path = _find_artifact(
        run_root,
        fallback_candidates,
        include_repo_root=workspace_id is None,
    )
    if session_id is None and workspace_id is not None:
        return None
    if session_id is None:
        return fallback_path
    fallback_paths = [fallback_path] if fallback_path is not None else []
    return resolve_artifact_path(
        artifact_types=artifact_types,
        session_id=session_id,
        workspace_id=workspace_id,
        fallback_paths=fallback_paths,
    )


def _load_csv(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text())


def _normalize_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    normalized = df.copy()
    for column in ("confidence", "uncertainty", "novelty", "experiment_value"):
        if column not in normalized.columns:
            normalized[column] = 0.0
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0.0)
    if "selection_bucket" not in normalized.columns:
        normalized["selection_bucket"] = ""
    return normalized


def _decision_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("top_experiments", [])
        return rows if isinstance(rows, list) else []
    return []


def _chart_style(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#d4dee5"},
        margin={"l": 24, "r": 24, "t": 48, "b": 24},
    )
    return fig


def _chart_section(title: str, description: str, fig, include_js: bool) -> dict[str, str]:
    return {
        "title": title,
        "description": description,
        "chart_html": _chart_style(fig).to_html(full_html=False, include_plotlyjs="cdn" if include_js else False),
    }


def _shortlist_preview(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:3], start=1):
        if not isinstance(row, dict):
            continue
        candidate_id = str(row.get("candidate_id") or row.get("molecule_id") or row.get("polymer") or f"cand_{index}")
        assay = str(row.get("assay") or "").strip()
        target = str(row.get("target") or "").strip()
        observed_value = _safe_float(row.get("observed_value", row.get("value")))
        rationale = row.get("rationale") if isinstance(row.get("rationale"), dict) else {}
        score_breakdown = row.get("score_breakdown") if isinstance(row.get("score_breakdown"), list) else []
        score_semantics = row.get("score_semantics") if isinstance(row.get("score_semantics"), dict) else {}
        target_definition = row.get("target_definition") if isinstance(row.get("target_definition"), dict) else {}
        target_kind = str(target_definition.get("target_kind") or "classification").strip().lower()
        primary_driver = ""
        if score_breakdown:
            top_component = max(
                (item for item in score_breakdown if isinstance(item, dict)),
                key=lambda item: float(item.get("contribution") or 0.0),
                default={},
            )
            primary_driver = str(top_component.get("label") or "").strip()
        rationale_summary = str(rationale.get("summary") or "").strip()
        trust_summary = str(rationale.get("trust_summary") or "").strip()
        if target_kind == "regression":
            rationale_summary = rationale_summary.replace("confidence", "ranking compatibility").replace("Confidence", "Ranking compatibility")
            trust_summary = trust_summary.replace("confidence", "ranking compatibility").replace("Confidence", "Ranking compatibility")
            if str(rationale.get("primary_driver") or primary_driver).strip().lower() == "confidence":
                primary_driver = "Ranking compatibility"
        preview.append(
            {
                "rank": int(row.get("rank") or index),
                "candidate_id": candidate_id,
                "smiles": str(row.get("smiles") or ""),
                "bucket": str(row.get("bucket") or row.get("selection_bucket") or "unassigned"),
                "status": str(row.get("status") or "suggested"),
                "confidence": float(_safe_float(row.get("confidence"), 0.0) or 0.0),
                "uncertainty": float(_safe_float(row.get("uncertainty"), 0.0) or 0.0),
                "novelty": float(_safe_float(row.get("novelty"), 0.0) or 0.0),
                "predicted_value": _safe_float(row.get("predicted_value")),
                "prediction_dispersion": _safe_float(row.get("prediction_dispersion")),
                "priority_score": float(_safe_float(row.get("priority_score"), 0.0) or 0.0),
                "raw_predictive_signal": _safe_float(row.get("raw_predictive_signal")),
                "raw_predictive_signal_label": str(score_semantics.get("raw_predictive_signal_label") or row.get("raw_predictive_signal_label") or "").strip(),
                "heuristic_policy_score": _safe_float(row.get("heuristic_policy_score")),
                "raw_signal_weight": _safe_float(row.get("raw_signal_weight")),
                "heuristic_weight": _safe_float(row.get("heuristic_weight")),
                "blended_priority_score": _safe_float(row.get("blended_priority_score")),
                "representation_support_factor": _safe_float(row.get("representation_support_factor")),
                "support_density": _safe_float(row.get("support_density")),
                "bounded_uncertainty_score": _safe_float(score_semantics.get("bounded_uncertainty_score")),
                "fragility_score": _safe_float(score_semantics.get("fragility_score")),
                "neighbor_gap": _safe_float(score_semantics.get("neighbor_gap")),
                "signal_status_label": str(score_semantics.get("signal_status_label") or "").strip(),
                "uncertainty_summary": str(score_semantics.get("uncertainty_summary") or "").strip(),
                "separation_summary": str(score_semantics.get("separation_summary") or "").strip(),
                "caution_summary": str(score_semantics.get("caution_summary") or "").strip(),
                "score_decomposition_summary": str(row.get("score_decomposition_summary") or score_semantics.get("summary") or "").strip(),
                "scoring_failure_mode_summary": str(row.get("scoring_failure_mode_summary") or "").strip(),
                "experiment_value": float(_safe_float(row.get("experiment_value"), 0.0) or 0.0),
                "observed_value": observed_value,
                "context": " / ".join(part for part in (assay, target) if part),
                "trust_label": str(rationale.get("trust_label") or row.get("trust_label") or "").strip(),
                "rationale_summary": rationale_summary,
                "trust_summary": trust_summary,
                "session_context": [
                    str(item).strip()
                    for item in (rationale.get("session_context") or [])
                    if str(item).strip()
                ][:2],
                "caution": (
                    str((rationale.get("cautions") or [""])[0]).strip()
                    if isinstance(rationale.get("cautions"), list)
                    else ""
                ),
                "primary_driver": str(rationale.get("primary_driver") or primary_driver).strip() if target_kind != "regression" else primary_driver,
                "domain_label": str(row.get("domain_label") or domain_chip_label(row.get("domain_status"))).strip(),
                "model_judgment": row.get("model_judgment") if isinstance(row.get("model_judgment"), dict) else {},
                "decision_policy": row.get("decision_policy") if isinstance(row.get("decision_policy"), dict) else {},
                "target_definition": target_definition,
                "target_kind": target_kind,
                "confidence_label": "Ranking compatibility" if target_kind == "regression" else "Confidence",
                "uncertainty_label": "Prediction dispersion" if target_kind == "regression" else "Uncertainty",
            }
        )
    return preview


def _label_chart_metadata(target_definition: dict[str, Any] | None) -> tuple[str, str]:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    target_name = str(target_definition.get("target_name") or "").strip()
    if target_name:
        return (
            "Label Distribution",
            f"Use this to see whether the current dataset is balanced or dominated by one class for {target_name}.",
        )
    return (
        "Label Distribution",
        "Use this to see whether the current dataset is balanced or dominated by one class.",
    )


def _dashboard_insight_summary(
    *,
    analysis_report: dict[str, Any],
    decision_payload: dict[str, Any],
    review_payload: dict[str, Any],
    top_candidates: list[dict[str, Any]],
    target_definition: dict[str, Any],
    modeling_mode: str,
    run_provenance: dict[str, Any],
    scientific_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    measurement_summary = analysis_report.get("measurement_summary", {}) if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = analysis_report.get("ranking_diagnostics", {}) if isinstance(analysis_report, dict) else {}
    recommendation_summary = str(analysis_report.get("top_level_recommendation_summary") or "").strip()
    review_summary = review_payload.get("summary", {}) if isinstance(review_payload, dict) else {}
    ranking_policy = analysis_report.get("ranking_policy", {}) if isinstance(analysis_report, dict) else {}
    trust_context = build_trust_context(
        target_definition=target_definition,
        modeling_mode=modeling_mode,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        ranking_policy=ranking_policy if isinstance(ranking_policy, dict) else {},
        run_provenance=run_provenance,
        scientific_truth=scientific_truth if isinstance(scientific_truth, dict) else {},
    )
    target_kind = str(target_definition.get("target_kind") or "classification").strip().lower()
    target_name = str(target_definition.get("target_name") or "the session target").strip() or "the session target"

    strengths: list[str] = []
    cautions: list[str] = []
    next_steps: list[str] = []

    rows_with_values = int(measurement_summary.get("rows_with_values", 0) or 0)
    if rows_with_values > 0:
        if target_kind == "regression":
            strengths.append(
                f"{rows_with_values} uploaded rows include observed values, so predicted {target_name} values can be cross-checked against measured evidence."
            )
        else:
            strengths.append(f"{rows_with_values} uploaded rows include observed values, so this run can be cross-checked against measured evidence.")
    else:
        cautions.append("No uploaded values are available for direct cross-checking, so treat the shortlist as model-guided ranking rather than evaluated truth.")

    rank_corr = _safe_float(ranking_diagnostics.get("spearman_rank_correlation"))
    if rank_corr is not None:
        if rank_corr >= 0.45:
            if target_kind == "regression":
                strengths.append(
                    f"Priority ordering remains reasonably aligned with uploaded measurement values (Spearman {rank_corr:.3f})."
                )
            else:
                strengths.append(f"Ranking agreement with uploaded values is reasonably positive (Spearman {rank_corr:.3f}).")
        elif rank_corr <= 0.15:
            if target_kind == "regression":
                cautions.append(
                    f"Priority ordering is weakly aligned with uploaded measurement values (Spearman {rank_corr:.3f}), so use the run as guidance rather than strict value truth."
                )
            else:
                cautions.append(f"Ranking agreement with uploaded values is weak (Spearman {rank_corr:.3f}), so review the shortlist with extra caution.")
        else:
            if target_kind == "regression":
                cautions.append(
                    f"Priority ordering has mixed agreement with uploaded measurement values (Spearman {rank_corr:.3f}), so use this run for guidance rather than strict value ordering."
                )
            else:
                cautions.append(f"Ranking agreement with uploaded values is mixed (Spearman {rank_corr:.3f}), so use this run for guidance rather than strict ordering.")

    predicted_corr = _safe_float(ranking_diagnostics.get("predicted_value_rank_correlation"))
    if target_kind == "regression" and predicted_corr is not None:
        if predicted_corr >= 0.45:
            strengths.append(f"Predicted value ordering is reasonably aligned with uploaded measurements (Spearman {predicted_corr:.3f}).")
        elif predicted_corr <= 0.15:
            cautions.append(f"Predicted value ordering is weakly aligned with uploaded measurements (Spearman {predicted_corr:.3f}).")

    out_of_domain_rate = _safe_float(ranking_diagnostics.get("out_of_domain_rate"))
    if out_of_domain_rate is not None:
        if out_of_domain_rate <= 0.25:
            strengths.append(f"Most candidates remain within stronger chemistry coverage ({out_of_domain_rate * 100:.1f}% out of domain).")
        elif out_of_domain_rate >= 0.5:
            cautions.append(f"A large share of candidates sits outside stronger chemistry coverage ({out_of_domain_rate * 100:.1f}% out of domain).")
        else:
            cautions.append(f"Some candidates are near or beyond stronger chemistry coverage ({out_of_domain_rate * 100:.1f}% out of domain).")

    top_k_lift = _safe_float(ranking_diagnostics.get("top_k_measurement_lift"))
    if top_k_lift is not None:
        if top_k_lift > 0:
            strengths.append(f"The top-ranked slice is enriched relative to the session average (lift {top_k_lift:.3f}).")
        elif top_k_lift < 0:
            cautions.append(f"The top-ranked slice is not outperforming the session average (lift {top_k_lift:.3f}).")

    warnings = analysis_report.get("warnings", []) if isinstance(analysis_report, dict) else []
    for warning in warnings[:2]:
        text = str(warning).strip()
        if text and text not in cautions:
            cautions.append(text)

    pending_review = int(review_summary.get("pending_review", 0) or 0)
    if pending_review > 0:
        next_steps.append(f"{pending_review} candidates are still pending review, so align chemist attention before expanding the shortlist.")
    elif top_candidates:
        lead_id = str(top_candidates[0].get("candidate_id") or top_candidates[0].get("molecule_id") or top_candidates[0].get("polymer") or "the leading candidate")
        if target_kind == "regression":
            next_steps.append(
                f"Start by reviewing {lead_id}, then validate its predicted {target_name} value experimentally before widening into the rest of the shortlist."
            )
        else:
            next_steps.append(f"Start by reviewing {lead_id}, then widen into the rest of the shortlist only if the current lead survives expert scrutiny.")

    if recommendation_summary:
        next_steps.insert(0, recommendation_summary)

    if strengths and len(cautions) <= 1:
        headline = "This run is strong enough to guide near-term review."
    elif cautions and not strengths:
        headline = "Treat this run as exploratory guidance rather than a near-term decision."
    else:
        headline = "This run is useful, but the shortlist still needs deliberate scientific review."

    if out_of_domain_rate is not None and out_of_domain_rate >= 0.5:
        trust_label = "High caution"
    elif rank_corr is not None and rank_corr >= 0.45 and (out_of_domain_rate is None or out_of_domain_rate <= 0.25):
        trust_label = "Stronger trust"
    elif rows_with_values > 0:
        trust_label = "Mixed trust"
    else:
        trust_label = "Exploratory trust"

    if trust_context.get("bridge_state_summary") and trust_context["bridge_state_summary"] not in cautions:
        cautions.insert(0, trust_context["bridge_state_summary"])

    return {
        "headline": headline,
        "trust_label": trust_label,
        "evidence_support_label": trust_context.get("evidence_support_label", ""),
        "evidence_basis_label": trust_context.get("evidence_basis_label", ""),
        "evidence_basis_summary": trust_context.get("evidence_basis_summary", ""),
        "model_basis_label": trust_context.get("model_basis_label", ""),
        "model_basis_summary": trust_context.get("model_basis_summary", ""),
        "policy_basis_label": trust_context.get("policy_basis_label", ""),
        "policy_basis_summary": trust_context.get("policy_basis_summary", ""),
        "activation_policy_label": trust_context.get("activation_policy_label", ""),
        "activation_policy_summary": trust_context.get("activation_policy_summary", ""),
        "controlled_reuse_label": trust_context.get("controlled_reuse_label", ""),
        "controlled_reuse_summary": trust_context.get("controlled_reuse_summary", ""),
        "future_eligibility_label": trust_context.get("future_eligibility_label", ""),
        "future_eligibility_summary": trust_context.get("future_eligibility_summary", ""),
        "bridge_state_summary": trust_context.get("bridge_state_summary", ""),
        "strengths": strengths[:3],
        "cautions": cautions[:3],
        "next_steps": next_steps[:3],
    }


def build_dashboard_context(session_id: str | None = None, workspace_id: str | None = None) -> dict[str, Any]:
    run_root = _run_root(session_id)
    session_record: dict[str, Any] = {}
    if session_id:
        try:
            session_record = session_repository.get_session(session_id, workspace_id=workspace_id)
        except FileNotFoundError:
            session_record = {}
    dataset = _load_csv(
        _resolve_run_artifact(
            session_id=session_id,
            workspace_id=workspace_id,
            run_root=run_root,
            artifact_types=DATASET_ARTIFACT_TYPES,
            fallback_candidates=DATASET_PATHS,
        )
    )
    candidates = _normalize_candidates(
        _load_csv(
            _resolve_run_artifact(
                session_id=session_id,
                workspace_id=workspace_id,
                run_root=run_root,
                artifact_types=CANDIDATE_ARTIFACT_TYPES,
                fallback_candidates=CANDIDATE_PATHS,
            )
        )
    )
    decision_payload = load_decision_artifact_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=workspace_id is None,
    )
    if str(decision_payload.get("artifact_state") or "missing") == "ok":
        try:
            decision_payload = normalize_loaded_decision_artifact(
                decision_payload,
                session_id=session_id,
            )
        except ContractValidationError:
            decision_payload = {
                "summary": {"top_experiment_value": 0.0},
                "top_experiments": [],
                "artifact_state": "error",
                "load_error": "Decision artifact failed contract validation.",
            }
    analysis_report = load_analysis_report_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=workspace_id is None,
    )
    evaluation_summary = load_evaluation_summary_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=workspace_id is None,
    )
    review_payload = _load_json(
        _resolve_run_artifact(
            session_id=session_id,
            workspace_id=workspace_id,
            run_root=run_root,
            artifact_types=REVIEW_QUEUE_ARTIFACT_TYPES,
            fallback_candidates=REVIEW_QUEUE_PATHS,
        )
    )
    evolution = _load_csv(
        _find_artifact(run_root, EVOLUTION_PATHS, include_repo_root=workspace_id is None)
        if session_id is not None or workspace_id is None
        else None
    )

    decision_rows = _decision_rows(decision_payload)
    if not isinstance(review_payload, dict):
        review_payload = build_review_queue(decision_rows, session_id=session_id, workspace_id=workspace_id)

    scientific_truth_payload = load_scientific_session_truth_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=workspace_id is None,
    )
    scientific_truth = (
        scientific_truth_payload
        if isinstance(scientific_truth_payload, dict) and str(scientific_truth_payload.get("artifact_state") or "") == "ok"
        else {}
    )
    if not scientific_truth and session_id:
        workspace_memory = build_session_workspace_memory(
            decision_payload.get("top_experiments") if isinstance(decision_payload, dict) else [],
            session_id=session_id,
            workspace_id=workspace_id,
        )
        scientific_truth = build_scientific_session_truth(
            session_id=session_id,
            workspace_id=workspace_id,
            source_name=str(session_record.get("source_name") or ""),
            session_record=session_record,
            upload_metadata=(session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {}),
            analysis_report=analysis_report if isinstance(analysis_report, dict) else {},
            decision_payload=decision_payload if isinstance(decision_payload, dict) else {},
            review_queue=review_payload if isinstance(review_payload, dict) else {},
            workspace_memory=workspace_memory,
        )

    warnings = analysis_report.get("warnings", []) if isinstance(analysis_report, dict) else []
    target_definition = scientific_truth.get("target_definition") if isinstance(scientific_truth.get("target_definition"), dict) else {}
    if not target_definition:
        target_definition = analysis_report.get("target_definition") if isinstance(analysis_report, dict) and isinstance(analysis_report.get("target_definition"), dict) else {}
    if not target_definition and isinstance(decision_payload.get("target_definition"), dict):
        target_definition = decision_payload.get("target_definition") or {}
    modeling_mode = str(
        (scientific_truth.get("modeling_mode") if isinstance(scientific_truth, dict) else "")
        or (analysis_report.get("modeling_mode") if isinstance(analysis_report, dict) else "")
        or decision_payload.get("modeling_mode")
        or ""
    ).strip()
    metric_interpretation = build_metric_interpretation(
        target_definition=target_definition,
        modeling_mode=modeling_mode,
        ranking_policy=analysis_report.get("ranking_policy") if isinstance(analysis_report, dict) else {},
    )
    run_contract = (
        scientific_truth.get("run_contract")
        if isinstance(scientific_truth.get("run_contract"), dict)
        else analysis_report.get("run_contract")
        if isinstance(analysis_report, dict) and isinstance(analysis_report.get("run_contract"), dict)
        else decision_payload.get("run_contract")
        if isinstance(decision_payload.get("run_contract"), dict)
        else {}
    )
    comparison_anchors = (
        scientific_truth.get("comparison_anchors")
        if isinstance(scientific_truth.get("comparison_anchors"), dict)
        else analysis_report.get("comparison_anchors")
        if isinstance(analysis_report, dict) and isinstance(analysis_report.get("comparison_anchors"), dict)
        else decision_payload.get("comparison_anchors")
        if isinstance(decision_payload.get("comparison_anchors"), dict)
        else {}
    )
    run_provenance = build_run_provenance(
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
    )
    cards = [
        {"label": "Dataset rows", "value": int(len(dataset)) if not dataset.empty else 0},
        {"label": "Scored candidates", "value": int(len(candidates)) if not candidates.empty else len(decision_rows)},
        {"label": "Top policy experiment value", "value": f"{float((decision_payload.get('summary') or {}).get('top_experiment_value', 0.0)):.3f}"},
        {"label": "Pending review", "value": int((review_payload.get("summary") or {}).get("pending_review", 0))},
    ]
    measurement_summary = analysis_report.get("measurement_summary", {}) if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = analysis_report.get("ranking_diagnostics", {}) if isinstance(analysis_report, dict) else {}
    if measurement_summary:
        cards.append({"label": "Rows with values", "value": int(measurement_summary.get("rows_with_values", 0) or 0)})
    if scientific_truth and isinstance(scientific_truth.get("evidence_records"), list):
        cards.append({"label": "Evidence records", "value": len(scientific_truth.get("evidence_records") or [])})
    linked_result_summary = scientific_truth.get("linked_result_summary") if isinstance(scientific_truth.get("linked_result_summary"), dict) else {}
    claims_summary = scientific_truth.get("claims_summary") if isinstance(scientific_truth.get("claims_summary"), dict) else {}
    claim_refs = list(scientific_truth.get("claim_refs") or []) if isinstance(scientific_truth.get("claim_refs"), list) else []
    if claims_summary.get("claim_count"):
        cards.append({"label": "Claims", "value": int(claims_summary.get("claim_count") or 0)})
    if claims_summary.get("claims_with_active_support_count"):
        cards.append({"label": "Claims with active support", "value": int(claims_summary.get("claims_with_active_support_count") or 0)})
    if linked_result_summary.get("result_count"):
        cards.append({"label": "Observed results", "value": int(linked_result_summary.get("result_count") or 0)})
    belief_update_summary = scientific_truth.get("belief_update_summary") if isinstance(scientific_truth.get("belief_update_summary"), dict) else {}
    if belief_update_summary.get("update_count"):
        cards.append({"label": "Belief updates", "value": int(belief_update_summary.get("update_count") or 0)})
    belief_state_summary = scientific_truth.get("belief_state_summary") if isinstance(scientific_truth.get("belief_state_summary"), dict) else {}
    scientific_decision_summary = (
        scientific_truth.get("scientific_decision_summary")
        if isinstance(scientific_truth.get("scientific_decision_summary"), dict)
        else {}
    )
    if not scientific_decision_summary and scientific_truth:
        scientific_decision_summary = build_scientific_decision_summary(scientific_truth)
    session_support_role_label, session_support_role_summary = support_role_from_belief_update_summary(belief_update_summary)
    predictive_path_summary = build_predictive_path_summary(
        analysis_report=analysis_report if isinstance(analysis_report, dict) else {},
        decision_payload=decision_payload if isinstance(decision_payload, dict) else {},
        scientific_truth=scientific_truth if isinstance(scientific_truth, dict) else {},
        ranking_policy=analysis_report.get("ranking_policy") if isinstance(analysis_report, dict) else {},
        target_definition=target_definition,
        modeling_mode=modeling_mode,
        run_contract=run_contract,
        evaluation_summary=evaluation_summary if isinstance(evaluation_summary, dict) else {},
    )
    if belief_state_summary.get("active_claim_count"):
        cards.append({"label": "Belief state claims", "value": int(belief_state_summary.get("active_claim_count") or 0)})
    alignment_summary = str(scientific_truth.get("belief_state_alignment_summary") or "").strip()
    alignment_label = str(scientific_truth.get("belief_state_alignment_label") or "").strip()
    if ranking_diagnostics.get("out_of_domain_rate") is not None:
        cards.append(
            {
                "label": "Weak-support rate",
                "value": f"{100 * float(ranking_diagnostics.get('out_of_domain_rate', 0.0)):.1f}%",
            }
        )
    elif ranking_diagnostics.get("spearman_rank_correlation") is not None:
        cards.append(
            {
                "label": "Rank correlation",
                "value": f"{float(ranking_diagnostics.get('spearman_rank_correlation', 0.0)):.3f}",
            }
        )

    charts = []
    include_js = True

    label_column = canonical_label_column(dataset) if not dataset.empty else ""
    if not dataset.empty and label_column in dataset.columns:
        label_title, label_description = _label_chart_metadata(target_definition)
        class_counts = (
            pd.to_numeric(dataset[label_column], errors="coerce")
            .fillna(-1)
            .astype(int)
            .map({1: "Positive", 0: "Negative", -1: "Unlabeled"})
            .value_counts()
            .rename_axis("class")
            .reset_index(name="count")
        )
        charts.append(
            _chart_section(
                label_title,
                label_description,
                px.bar(class_counts, x="class", y="count", color="class"),
                include_js,
            )
        )
        include_js = False

    if not candidates.empty:
        confidence_title = "Confidence Distribution"
        confidence_description = "Higher values indicate stronger model confidence, but not experimental truth."
        if str(target_definition.get("target_kind") or "").strip().lower() == "regression":
            confidence_title = "Ranking Compatibility Distribution"
            confidence_description = "Higher values indicate stronger ranking compatibility with the target direction, not classification confidence."
        charts.append(
            _chart_section(
                confidence_title,
                confidence_description,
                px.histogram(candidates, x="confidence", nbins=20),
                include_js,
            )
        )
        include_js = False
        charts.append(
            _chart_section(
                "Uncertainty Distribution",
                "Higher uncertainty suggests a molecule may be more useful for learning than immediate exploitation.",
                px.histogram(candidates, x="uncertainty", nbins=20),
                include_js,
            )
        )
        charts.append(
            _chart_section(
                "Novelty Distribution",
                "Higher novelty means the molecule is less similar to what the system already knows well.",
                px.histogram(candidates, x="novelty", nbins=20),
                include_js,
            )
        )

        bucket_counts = (
            candidates["selection_bucket"]
            .fillna("unassigned")
            .replace("", "unassigned")
            .value_counts()
            .rename_axis("bucket")
            .reset_index(name="count")
        )
        charts.append(
            _chart_section(
                "Bucket Breakdown",
                "This shows how the system is balancing exploitation, learning, and exploration.",
                px.bar(bucket_counts, x="bucket", y="count", color="bucket"),
                include_js,
            )
        )

    review_counts = (review_payload.get("summary") or {}).get("counts", {})
    if review_counts:
        review_frame = pd.DataFrame(
            [{"status": status, "count": count} for status, count in review_counts.items()]
        )
        charts.append(
            _chart_section(
                "Review Workflow Summary",
                "Track which suggestions are still pending versus approved, rejected, tested, or ingested.",
                px.bar(review_frame, x="status", y="count", color="status"),
                include_js,
            )
        )

    if not evolution.empty and "iteration" in evolution.columns and "dataset_size" in evolution.columns:
        charts.append(
            _chart_section(
                "Dataset Trends",
                "This trend shows how dataset size has changed over iterations when iteration artifacts are available.",
                px.line(evolution.sort_values("iteration"), x="iteration", y="dataset_size", markers=True),
                include_js,
            )
        )

    top_candidates = decision_rows[:10]
    if session_id is None:
        state = {
            "kind": "no_session",
            "message": "No session is selected yet. Open a completed upload session to see its dashboard.",
        }
    elif str(decision_payload.get("artifact_state") or "missing") == "error":
        state = {
            "kind": "error",
            "message": str(decision_payload.get("load_error") or "The dashboard could not read the saved decision artifact for this session."),
        }
    elif str(decision_payload.get("artifact_state") or "missing") == "missing":
        state = {
            "kind": "artifact_missing",
            "message": str(decision_payload.get("load_error") or "No saved decision artifact was found for this session yet."),
        }
    elif top_candidates:
        state = {"kind": "ready", "message": ""}
    else:
        state = {
            "kind": "empty",
            "message": "This session has no ranked candidates yet, even though the run context exists.",
        }
    return {
        "state": state,
        "session_id": session_id,
        "artifact_state": decision_payload.get("artifact_state") or "",
        "source_path": decision_payload.get("source_path") or "",
        "source_updated_at": decision_payload.get("source_updated_at") or "",
        "cards": cards,
        "warnings": warnings,
        "charts": charts,
        "top_candidates": top_candidates,
        "shortlist_preview": _shortlist_preview(top_candidates),
        "insight_summary": _dashboard_insight_summary(
            analysis_report=analysis_report if isinstance(analysis_report, dict) else {},
            decision_payload=decision_payload if isinstance(decision_payload, dict) else {},
            review_payload=review_payload if isinstance(review_payload, dict) else {},
            top_candidates=top_candidates,
            target_definition=target_definition,
            modeling_mode=modeling_mode,
            run_provenance=run_provenance,
            scientific_truth=scientific_truth,
        ),
        "review_summary": review_payload.get("summary", {}),
        "analysis_report": analysis_report if isinstance(analysis_report, dict) else {},
        "evaluation_summary": evaluation_summary if isinstance(evaluation_summary, dict) else {},
        "scientific_session_truth": scientific_truth,
        "claims_summary": claims_summary,
        "claim_refs": claim_refs,
        "experiment_request_summary": scientific_truth.get("experiment_request_summary")
        if isinstance(scientific_truth.get("experiment_request_summary"), dict)
        else {},
        "experiment_request_refs": list(scientific_truth.get("experiment_request_refs") or [])
        if isinstance(scientific_truth.get("experiment_request_refs"), list)
        else [],
        "linked_result_summary": linked_result_summary,
        "experiment_result_refs": list(scientific_truth.get("experiment_result_refs") or [])
        if isinstance(scientific_truth.get("experiment_result_refs"), list)
        else [],
        "belief_update_summary": belief_update_summary,
        "session_support_role_label": session_support_role_label,
        "session_support_role_summary": session_support_role_summary,
        "belief_state_ref": scientific_truth.get("belief_state_ref")
        if isinstance(scientific_truth.get("belief_state_ref"), dict)
        else {},
        "belief_state_summary": belief_state_summary,
        "scientific_decision_summary": scientific_decision_summary,
        "predictive_path_summary": predictive_path_summary,
        "belief_state_alignment_label": alignment_label,
        "belief_state_alignment_summary": alignment_summary,
        "target_definition": target_definition,
        "run_contract": run_contract,
        "comparison_anchors": comparison_anchors,
        "run_provenance": run_provenance,
        "modeling_mode": modeling_mode,
        "decision_intent": str((analysis_report.get("decision_intent") if isinstance(analysis_report, dict) else "") or decision_payload.get("decision_intent") or "").strip(),
        "metric_interpretation": metric_interpretation,
    }
