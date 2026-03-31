from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px

from system.contracts import ContractValidationError, normalize_loaded_decision_artifact
from system.db import resolve_artifact_path
from system.review_manager import build_review_queue
from system.session_artifacts import (
    load_analysis_report_payload,
    load_decision_artifact_payload,
    load_evaluation_summary_payload,
)
from utils.artifact_writer import REPO_ROOT, uploaded_session_dir


DATASET_PATHS = ("uploaded_dataset.csv", "data/data.csv", "data.csv")
DATASET_ARTIFACT_TYPES = ("upload_csv", "raw_upload_csv")
CANDIDATE_PATHS = ("scored_candidates.csv", "predicted_candidates.csv", "candidates_results.csv")
CANDIDATE_ARTIFACT_TYPES = ("scored_candidates_csv", "processed_candidates_csv")
REVIEW_QUEUE_PATHS = ("review_queue.json", "data/review_queue.json")
REVIEW_QUEUE_ARTIFACT_TYPES = ("review_queue_json",)
EVOLUTION_PATHS = ("iteration_history.csv",)


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


def build_dashboard_context(session_id: str | None = None, workspace_id: str | None = None) -> dict[str, Any]:
    run_root = _run_root(session_id)
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

    warnings = analysis_report.get("warnings", []) if isinstance(analysis_report, dict) else []
    cards = [
        {"label": "Dataset rows", "value": int(len(dataset)) if not dataset.empty else 0},
        {"label": "Scored candidates", "value": int(len(candidates)) if not candidates.empty else len(decision_rows)},
        {"label": "Top experiment value", "value": f"{float((decision_payload.get('summary') or {}).get('top_experiment_value', 0.0)):.3f}"},
        {"label": "Pending review", "value": int((review_payload.get("summary") or {}).get("pending_review", 0))},
    ]
    measurement_summary = analysis_report.get("measurement_summary", {}) if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = analysis_report.get("ranking_diagnostics", {}) if isinstance(analysis_report, dict) else {}
    if measurement_summary:
        cards.append({"label": "Rows with values", "value": int(measurement_summary.get("rows_with_values", 0) or 0)})
    if ranking_diagnostics.get("out_of_domain_rate") is not None:
        cards.append(
            {
                "label": "OOD rate",
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

    if not dataset.empty and "biodegradable" in dataset.columns:
        class_counts = (
            pd.to_numeric(dataset["biodegradable"], errors="coerce")
            .fillna(-1)
            .astype(int)
            .map({1: "Positive", 0: "Negative", -1: "Unlabeled"})
            .value_counts()
            .rename_axis("class")
            .reset_index(name="count")
        )
        charts.append(
            _chart_section(
                "Class Distribution",
                "Use this to see whether the current dataset is balanced or dominated by one class.",
                px.bar(class_counts, x="class", y="count", color="class"),
                include_js,
            )
        )
        include_js = False

    if not candidates.empty:
        charts.append(
            _chart_section(
                "Confidence Distribution",
                "Higher values indicate stronger model confidence, but not experimental truth.",
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
        "source_path": decision_payload.get("source_path") or "",
        "source_updated_at": decision_payload.get("source_updated_at") or "",
        "cards": cards,
        "warnings": warnings,
        "charts": charts,
        "top_candidates": top_candidates,
        "review_summary": review_payload.get("summary", {}),
        "analysis_report": analysis_report if isinstance(analysis_report, dict) else {},
        "evaluation_summary": evaluation_summary if isinstance(evaluation_summary, dict) else {},
    }
