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
from system.services.run_metadata_service import build_comparison_anchors, build_run_contract
from system.services.target_definition_service import (
    default_contract_versions,
    infer_modeling_mode,
    normalize_decision_intent,
)
from system.services.scientific_state_service import persist_run_scientific_state
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
    target_definition: dict[str, Any],
    decision_intent: str,
    modeling_mode: str,
    scientific_contract: dict[str, Any],
    run_contract: dict[str, Any],
    comparison_anchors: dict[str, Any],
    contract_versions: dict[str, str],
) -> None:
    result["run_id"] = session_id
    result["session_id"] = session_id
    result["product_tier"] = product_tier
    result["source_name"] = source_name
    result["input_type"] = input_type
    result["intent"] = intent
    result["decision_intent"] = decision_intent
    result["modeling_mode"] = modeling_mode
    result["scoring_mode"] = scoring_mode
    result["warnings"] = warnings
    result["target_definition"] = target_definition
    result["scientific_contract"] = scientific_contract
    result["run_contract"] = run_contract
    result["comparison_anchors"] = comparison_anchors
    result["contract_versions"] = contract_versions
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
        validation_context=options.get("validation_context"),
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
    target_definition = dict(summary.get("target_definition") or prepared.attrs.get("target_definition") or {})
    contract_versions = default_contract_versions()

    input_type = normalize_input_type(options.get("input_type"), default="structure_only_screening")
    intent = str(options.get("intent") or "rank_uploaded_molecules")
    decision_intent = normalize_decision_intent(intent)
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
    target_kind = str(target_definition.get("target_kind") or "classification")
    if target_kind == "regression":
        measured = pd.to_numeric(prepared.get("target_value"), errors="coerce")
        measured = measured[measured.notna()]
        target_model_available = int(len(measured)) >= 6 and int(measured.nunique()) >= 3
    else:
        class_count = int(labeled["target_label"].nunique()) if not labeled.empty and "target_label" in labeled.columns else int(labeled["biodegradable"].nunique()) if not labeled.empty else 0
        min_class_count = int(labeled["target_label"].value_counts().min()) if not labeled.empty and "target_label" in labeled.columns else int(labeled["biodegradable"].value_counts().min()) if not labeled.empty else 0
        target_model_available = class_count >= 2 and min_class_count >= 2

    _emit_progress(
        progress_callback,
        stage="preparing_dataset",
        message="Selecting the scoring workflow for this upload.",
        percent=34,
    )

    used_candidate_generation = intent == "generate_candidates" and target_kind == "classification" and target_model_available
    if used_candidate_generation:
        result, generated, processed, scored, bundle = build_discovery_result(
            prepared,
            summary,
            config,
            seed,
            session_id,
            source_name,
            intent,
            scoring_mode,
            target_definition=target_definition,
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
            allow_session_training=target_model_available,
            target_definition=target_definition,
            progress_callback=progress_callback,
        )
        generated = None
        processed = None
    modeling_mode = infer_modeling_mode(
        target_definition=target_definition,
        decision_intent=decision_intent,
        used_candidate_generation=used_candidate_generation,
        target_model_available=target_model_available,
    )
    scientific_contract = {
        "target_definition": target_definition,
        "decision_intent": decision_intent,
        "modeling_mode": modeling_mode,
        "target_model_available": bool(target_model_available),
        "candidate_generation_eligible": bool(intent == "generate_candidates" and target_kind == "classification" and target_model_available),
        "used_candidate_generation": bool(used_candidate_generation),
        "fallback_reason": "",
    }

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
    if intent == "generate_candidates" and target_kind != "classification":
        warnings.append("Candidate generation currently supports classification-style targets only, so this run used the ranking workflow instead.")
        scientific_contract["fallback_reason"] = "candidate_generation_requires_classification_target"
    elif intent == "generate_candidates" and not target_model_available:
        warnings.append("The upload did not contain enough labeled examples per class for session-trained candidate generation, so the run fell back to ranking uploaded molecules.")
        scientific_contract["fallback_reason"] = "insufficient_training_data_for_candidate_generation"
    elif isinstance(bundle, dict) and str(bundle.get("training_scope") or "").strip().lower() == "baseline_bundle":
        warnings.append(
            "This run reused the legacy baseline classification bundle instead of training on the current session, so treat the ranking as bridge-state guidance rather than target-neutral evidence."
        )
        scientific_contract["fallback_reason"] = "legacy_baseline_bundle_reused"

    if bundle is not None:
        bundle["contract_versions"] = contract_versions
        bundle["target_definition"] = target_definition

    run_contract = build_run_contract(
        session_id=session_id,
        source_name=source_name,
        input_type=input_type,
        requested_intent=intent,
        decision_intent=decision_intent,
        modeling_mode=modeling_mode,
        scoring_mode=scoring_mode,
        target_definition=target_definition,
        scientific_contract=scientific_contract,
        contract_versions=contract_versions,
        validation_summary=summary,
        bundle=bundle,
    )
    comparison_anchors = build_comparison_anchors(
        session_id=session_id,
        source_name=source_name,
        input_type=input_type,
        column_mapping=column_mapping,
        target_definition=target_definition,
        decision_intent=decision_intent,
        modeling_mode=modeling_mode,
        scoring_mode=scoring_mode,
        contract_versions=contract_versions,
        validation_summary=summary,
        run_contract=run_contract,
    )

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
        decision_intent=decision_intent,
        modeling_mode=modeling_mode,
        scoring_mode=scoring_mode,
        consent_learning=consent_learning,
        warnings=warnings,
        product_tier=product_tier,
        target_definition=target_definition,
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
        contract_versions=contract_versions,
    )
    analysis_report = build_analysis_report(
        validation=summary,
        scoring_mode=scoring_mode,
        intent=intent,
        decision_intent=decision_intent,
        modeling_mode=modeling_mode,
        consent_learning=consent_learning,
        top_candidates=result.get("top_candidates", []),
        warnings=warnings,
        product_tier=product_tier,
        scored_frame=scored,
        target_definition=target_definition,
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
        contract_versions=contract_versions,
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
        target_definition=target_definition,
        decision_intent=decision_intent,
        modeling_mode=modeling_mode,
        scientific_contract=scientific_contract,
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
        contract_versions=contract_versions,
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
        result["decision_output"]["decision_intent"] = decision_intent
        result["decision_output"]["modeling_mode"] = modeling_mode
        result["decision_output"]["mode_used"] = scoring_mode
        result["decision_output"]["product_tier"] = product_tier
        result["decision_output"]["warnings"] = warnings
        result["decision_output"]["target_definition"] = target_definition
        result["decision_output"]["scientific_contract"] = scientific_contract
        result["decision_output"]["run_contract"] = run_contract
        result["decision_output"]["comparison_anchors"] = comparison_anchors
        result["decision_output"]["contract_versions"] = contract_versions
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
    workspace_id = str(options.get("workspace_id") or "") or "legacy_workspace"
    result["scientific_state_diagnostics"] = persist_run_scientific_state(
        prepared=prepared,
        result=result,
        scored=scored,
        bundle=bundle,
        workspace_id=workspace_id,
        created_by_user_id=str(options.get("created_by_user_id") or "") or None,
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
