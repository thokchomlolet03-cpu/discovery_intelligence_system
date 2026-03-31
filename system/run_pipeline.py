from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

from core.config import default_system_config
from core.constants import DECISION_OUTPUT_PATH
from system.contracts import validate_decision_artifact, validate_normalized_dataset_summary
from system.review_manager import persist_review_queue
from system.services.analysis_service import build_discovery_result, build_prediction_result
from system.services.artifact_service import (
    DEFAULT_DECISION_OUTPUT_PATH,
    persist_pipeline_artifacts,
    queue_feedback_rows,
    write_decision_artifact,
    write_json_log,
)
from system.services.candidate_service import out_of_domain_ratio
from system.services.data_service import labeled_subset, prepare_analysis_dataframe
from system.session_report import (
    apply_scoring_mode,
    build_analysis_report,
    build_upload_session_summary,
    build_warnings,
)
from system.upload_parser import infer_column_mapping
from system.services.ingestion import normalize_input_type


DEFAULT_ANALYSIS_OPTIONS = {
    "session_id": None,
    "input_type": "structure_only_screening",
    "intent": "rank_uploaded_molecules",
    "scoring_mode": "balanced",
    "consent_learning": False,
    "column_mapping": None,
    "label_builder": {"enabled": False},
}


ProgressCallback = Callable[[str, str, int], None]


def _emit_progress(
    progress_callback: ProgressCallback | None,
    *,
    stage: str,
    message: str,
    percent: int,
) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, message, percent)


def _resolve_session_id(options: dict[str, Any], prepared: pd.DataFrame) -> str:
    session_id = options.get("session_id") or options.get("run_id") or options.get("session") or prepared.attrs.get("session_id")
    if not session_id:
        session_id = options.get("session_id") or options.get("run_id") or options.get("session") or options.get("source_session")
    if not session_id:
        session_id = options.get("source_name_override") or prepared.attrs.get("generated_session_id")
    if not session_id:
        from system.upload_parser import session_id_now

        session_id = session_id_now()
    return str(session_id)


def _validated_normalized_summary(summary: dict[str, Any], session_id: str, source_name: str) -> dict[str, Any]:
    return validate_normalized_dataset_summary(
        {
            **summary,
            "session_id": session_id,
            "source_name": source_name,
            "row_count_before": int(summary.get("row_count_before", summary.get("total_rows", 0))),
            "row_count_after": int(summary.get("row_count_after", summary.get("analyzed_rows", summary.get("total_rows", 0)))),
            "canonicalized_rows": int(summary.get("canonicalized_rows", summary.get("valid_smiles_count", 0))),
            "duplicate_removed_count": int(summary.get("duplicate_removed_count", summary.get("duplicate_count", 0))),
            "usable_label_count": int(summary.get("usable_label_count", summary.get("rows_with_labels", 0))),
        }
    )


def _apply_result_metadata(
    result: dict[str, Any],
    *,
    session_id: str,
    source_name: str,
    input_type: str,
    intent: str,
    scoring_mode: str,
    product_tier: str,
    warnings: list[str],
    session_summary: dict[str, Any],
    analysis_report: dict[str, Any],
) -> None:
    result["run_id"] = session_id
    result["session_id"] = session_id
    result["product_tier"] = product_tier
    result["source_name"] = source_name
    result["input_type"] = input_type
    result["intent"] = intent
    result["scoring_mode"] = scoring_mode
    result["warnings"] = warnings
    result["upload_session_summary"] = session_summary
    result["analysis_report"] = analysis_report
    result["discovery_url"] = f"/discovery?session_id={session_id}"
    result["dashboard_url"] = f"/dashboard?session_id={session_id}"


def run_pipeline(
    df: pd.DataFrame,
    persist_artifacts: bool = False,
    update_discovery_snapshot: bool = False,
    seed: int = 42,
    source_name: str | None = None,
    analysis_options: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    options = {**DEFAULT_ANALYSIS_OPTIONS, **(analysis_options or {})}
    source_name = source_name or "uploaded_dataset.csv"
    column_mapping = options.get("column_mapping") or infer_column_mapping(list(df.columns))
    _emit_progress(
        progress_callback,
        stage="preparing_dataset",
        message="Normalizing mapped columns and validating uploaded molecules.",
        percent=12,
    )
    prepared, summary = prepare_analysis_dataframe(
        df,
        column_mapping,
        label_builder=options.get("label_builder"),
    )

    _emit_progress(
        progress_callback,
        stage="preparing_dataset",
        message="Applying scoring mode and analysis configuration.",
        percent=24,
    )
    scoring_mode, config = apply_scoring_mode(default_system_config(seed=seed), options.get("scoring_mode"))
    session_id = _resolve_session_id(options, prepared)
    summary = _validated_normalized_summary(summary, session_id, source_name)

    input_type = normalize_input_type(options.get("input_type"), default="structure_only_screening")
    intent = str(options.get("intent") or "rank_uploaded_molecules")
    consent_learning = bool(options.get("consent_learning"))
    product_tier = str(options.get("product_tier") or "standard")

    _emit_progress(
        progress_callback,
        stage="preparing_dataset",
        message="Estimating domain overlap against the reference dataset.",
        percent=30,
    )
    domain_gap = out_of_domain_ratio(prepared, config=config)
    labeled = labeled_subset(prepared)
    class_count = int(labeled["biodegradable"].nunique()) if not labeled.empty else 0
    min_class_count = int(labeled["biodegradable"].value_counts().min()) if not labeled.empty else 0
    session_training_available = class_count >= 2 and min_class_count >= 2

    _emit_progress(
        progress_callback,
        stage="preparing_dataset",
        message="Selecting the scoring workflow for this upload.",
        percent=34,
    )

    if intent == "generate_candidates" and session_training_available:
        result, generated, processed, scored, bundle = build_discovery_result(
            prepared,
            summary,
            config,
            seed,
            session_id,
            source_name,
            intent,
            scoring_mode,
            progress_callback=progress_callback,
        )
    else:
        result, scored, bundle = build_prediction_result(
            prepared,
            summary,
            config,
            seed,
            session_id,
            source_name,
            intent,
            scoring_mode,
            allow_session_training=session_training_available,
            progress_callback=progress_callback,
        )
        generated = None
        processed = None

    mean_uncertainty = None
    if not scored.empty and "uncertainty" in scored.columns:
        mean_uncertainty = float(pd.to_numeric(scored["uncertainty"], errors="coerce").fillna(0.0).head(10).mean())

    warnings = build_warnings(
        summary,
        scoring_mode=scoring_mode,
        intent=intent,
        out_of_domain_ratio=domain_gap,
        mean_uncertainty=mean_uncertainty,
    )
    if intent == "generate_candidates" and not session_training_available:
        warnings.append("The upload did not contain enough labeled examples per class for session-trained candidate generation, so the run fell back to ranking uploaded molecules.")

    _emit_progress(
        progress_callback,
        stage="building_reports",
        message="Compiling session summary, warnings, and recommendation report.",
        percent=80,
    )
    session_summary = build_upload_session_summary(
        session_id=session_id,
        source_name=source_name,
        input_type=input_type,
        column_mapping=column_mapping,
        validation=summary,
        intent=intent,
        scoring_mode=scoring_mode,
        consent_learning=consent_learning,
        warnings=warnings,
        product_tier=product_tier,
    )
    analysis_report = build_analysis_report(
        validation=summary,
        scoring_mode=scoring_mode,
        intent=intent,
        consent_learning=consent_learning,
        top_candidates=result.get("top_candidates", []),
        warnings=warnings,
        product_tier=product_tier,
        scored_frame=scored,
    )
    _apply_result_metadata(
        result,
        session_id=session_id,
        source_name=source_name,
        input_type=input_type,
        intent=intent,
        scoring_mode=scoring_mode,
        product_tier=product_tier,
        warnings=warnings,
        session_summary=session_summary,
        analysis_report=analysis_report,
    )

    _emit_progress(
        progress_callback,
        stage="queueing_feedback",
        message="Evaluating whether labeled rows can enter the feedback queue.",
        percent=88,
    )
    result["feedback_store"] = queue_feedback_rows(prepared, consent_learning=consent_learning)

    if result.get("decision_output"):
        result["decision_output"]["input_type"] = input_type
        result["decision_output"]["intent"] = intent
        result["decision_output"]["mode_used"] = scoring_mode
        result["decision_output"]["product_tier"] = product_tier
        result["decision_output"]["warnings"] = warnings
        result["decision_output"] = validate_decision_artifact(result["decision_output"])
        result["top_candidates"] = result["decision_output"].get("top_experiments", [])

    _emit_progress(
        progress_callback,
        stage="persisting_artifacts",
        message="Saving review queue artifacts for this analysis session.",
        percent=92,
    )
    result["review_queue"] = persist_review_queue(
        result.get("top_candidates", []),
        session_id=session_id,
        workspace_id=str(options.get("workspace_id") or "") or None,
        created_by_user_id=str(options.get("created_by_user_id") or "") or None,
    )
    _emit_progress(
        progress_callback,
        stage="persisting_artifacts",
        message="Writing analysis artifacts for the completed run.",
        percent=96,
    )
    result["artifacts"] = (
        persist_pipeline_artifacts(
            session_id,
            prepared,
            result,
            generated=generated,
            processed=processed,
            scored=scored,
            bundle=bundle,
            expose_latest=consent_learning,
        )
        if persist_artifacts
        else {}
    )

    if persist_artifacts:
        write_json_log(Path(result["artifacts"]["result_json"]), result)
        if result["artifacts"].get("latest_result_json"):
            write_json_log(Path(result["artifacts"]["latest_result_json"]), result)

    if update_discovery_snapshot and result.get("decision_output") and consent_learning:
        write_decision_artifact(DEFAULT_DECISION_OUTPUT_PATH, result["decision_output"])
        write_decision_artifact(DECISION_OUTPUT_PATH, result["decision_output"])

    _emit_progress(
        progress_callback,
        stage="finalizing_artifacts",
        message="Preparing the final result payload for the upload session.",
        percent=98,
    )
    return result
