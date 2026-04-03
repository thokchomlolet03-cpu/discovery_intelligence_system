from __future__ import annotations

from typing import Any

from system.contracts import (
    ComparisonAnchors,
    DatasetType,
    DecisionIntent,
    ModelingMode,
    RunContract,
    TargetKind,
    validate_comparison_anchors,
    validate_run_contract,
)
from system.services.target_definition_service import (
    default_contract_versions,
    infer_target_definition,
    normalize_decision_intent,
    normalize_modeling_mode,
)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _humanize_token(value: Any, default: str = "Not recorded") -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return default
    return cleaned.replace("_", " ").strip().title()


def _normalized_mapping(mapping: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(mapping, dict):
        return {}
    payload: dict[str, str] = {}
    for key, value in mapping.items():
        cleaned_key = _clean_text(key).lower()
        cleaned_value = _clean_text(value)
        if cleaned_key and cleaned_value:
            payload[cleaned_key] = cleaned_value
    return payload


def _target_definition_from_sources(
    *,
    target_definition: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
    validation_summary: dict[str, Any] | None,
    label_builder: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = target_definition if isinstance(target_definition, dict) else {}
    if existing:
        return existing
    return infer_target_definition(
        mapping=mapping,
        validation_summary=validation_summary or {},
        label_builder=label_builder,
        existing=existing,
    )


def _feature_signature(bundle: dict[str, Any] | None) -> str:
    if not isinstance(bundle, dict) or not bundle:
        return "not_recorded"
    descriptor_features = bundle.get("descriptor_features")
    fingerprint_bits = bundle.get("fingerprint_bits")
    if isinstance(descriptor_features, list) and descriptor_features:
        if fingerprint_bits:
            return f"rdkit_descriptors_plus_morgan_fp_{int(fingerprint_bits)}"
        return "rdkit_descriptors"
    return "not_recorded"


def _training_scope(bundle: dict[str, Any] | None, modeling_mode: str) -> str:
    if isinstance(bundle, dict):
        explicit = _clean_text(bundle.get("training_scope")).lower()
        if explicit:
            return explicit
    normalized_mode = normalize_modeling_mode(modeling_mode, default=ModelingMode.ranking_only.value)
    if normalized_mode == ModelingMode.ranking_only.value:
        return "ranking_without_target_model"
    return "not_recorded"


def _selected_model(bundle: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(bundle, dict):
        return {"name": "", "family": "", "calibration_method": ""}
    selected = bundle.get("selected_model") if isinstance(bundle.get("selected_model"), dict) else {}
    return {
        "name": _clean_text(selected.get("name")),
        "family": _clean_text(bundle.get("model_family"), default="random_forest"),
        "calibration_method": _clean_text(selected.get("calibration_method")),
    }


def _label_source(validation_summary: dict[str, Any] | None, target_definition: dict[str, Any]) -> str:
    validation_summary = validation_summary or {}
    explicit = _clean_text(validation_summary.get("label_source")).lower()
    target_kind = _clean_text(target_definition.get("target_kind"), default=TargetKind.classification.value).lower()
    derived_rule = target_definition.get("derived_label_rule") if isinstance(target_definition.get("derived_label_rule"), dict) else None
    if explicit and explicit not in {"missing", "not_recorded"}:
        return explicit
    if derived_rule:
        return "derived"
    if target_kind == TargetKind.regression.value:
        return "continuous_measurement"
    if _clean_text(target_definition.get("label_column")):
        return "explicit"
    return "not_recorded"


def build_run_contract(
    *,
    session_id: str,
    source_name: str,
    input_type: str,
    requested_intent: str,
    decision_intent: str,
    modeling_mode: str,
    scoring_mode: str,
    target_definition: dict[str, Any] | None,
    scientific_contract: dict[str, Any] | None = None,
    contract_versions: dict[str, Any] | None = None,
    validation_summary: dict[str, Any] | None = None,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scientific_contract = scientific_contract or {}
    target_definition = _target_definition_from_sources(
        target_definition=target_definition,
        mapping=None,
        validation_summary=validation_summary,
    )
    normalized_versions = default_contract_versions(contract_versions if isinstance(contract_versions, dict) else {})
    selected_model = _selected_model(bundle)
    normalized_mode = normalize_modeling_mode(modeling_mode, default=ModelingMode.ranking_only.value)
    payload = {
        "session_id": session_id,
        "source_name": source_name,
        "input_type": input_type,
        "requested_intent": _clean_text(requested_intent),
        "decision_intent": normalize_decision_intent(decision_intent),
        "modeling_mode": normalized_mode,
        "scoring_mode": _clean_text(scoring_mode, default="balanced"),
        "target_definition": target_definition,
        "target_model_available": bool(scientific_contract.get("target_model_available")),
        "candidate_generation_requested": _clean_text(requested_intent) == "generate_candidates",
        "candidate_generation_eligible": bool(scientific_contract.get("candidate_generation_eligible")),
        "used_candidate_generation": bool(scientific_contract.get("used_candidate_generation")),
        "fallback_reason": _clean_text(scientific_contract.get("fallback_reason")),
        "selected_model_name": selected_model["name"],
        "selected_model_family": selected_model["family"],
        "calibration_method": selected_model["calibration_method"],
        "training_scope": _training_scope(bundle, normalized_mode),
        "label_source": _label_source(validation_summary, target_definition),
        "feature_signature": _feature_signature(bundle),
        "reference_basis": {
            "novelty_reference": "reference_dataset_similarity",
            "applicability_reference": "reference_dataset_similarity",
        },
        "contract_versions": normalized_versions,
    }
    return validate_run_contract(payload)


def build_comparison_anchors(
    *,
    session_id: str,
    source_name: str,
    input_type: str,
    column_mapping: dict[str, Any] | None,
    target_definition: dict[str, Any] | None,
    decision_intent: str | None,
    modeling_mode: str | None,
    scoring_mode: str | None,
    contract_versions: dict[str, Any] | None = None,
    validation_summary: dict[str, Any] | None = None,
    run_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_definition = _target_definition_from_sources(
        target_definition=target_definition,
        mapping=column_mapping,
        validation_summary=validation_summary,
    )
    normalized_versions = default_contract_versions(contract_versions if isinstance(contract_versions, dict) else {})
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    normalized_intent = normalize_decision_intent(decision_intent)
    normalized_mode = normalize_modeling_mode(modeling_mode, default="")
    training_scope = _clean_text(run_contract.get("training_scope"))
    selected_model_name = _clean_text(run_contract.get("selected_model_name"))
    if not normalized_mode:
        normalized_mode = normalize_modeling_mode(run_contract.get("modeling_mode"), default="")

    target_name = _clean_text(target_definition.get("target_name"))
    payload = {
        "session_id": session_id,
        "source_name": source_name,
        "input_type": input_type,
        "target_name": target_name,
        "target_kind": target_definition.get("target_kind") or TargetKind.classification.value,
        "optimization_direction": target_definition.get("optimization_direction") or "classify",
        "measurement_column": target_definition.get("measurement_column") or "",
        "label_column": target_definition.get("label_column") or "",
        "measurement_unit": target_definition.get("measurement_unit") or "",
        "dataset_type": target_definition.get("dataset_type") or DatasetType.structure_only.value,
        "mapping_confidence": target_definition.get("mapping_confidence") or "low",
        "column_mapping": _normalized_mapping(column_mapping),
        "label_source": _clean_text(run_contract.get("label_source")) or _label_source(validation_summary, target_definition),
        "decision_intent": normalized_intent or None,
        "modeling_mode": normalized_mode or None,
        "scoring_mode": _clean_text(scoring_mode) or _clean_text(run_contract.get("scoring_mode")),
        "selected_model_name": selected_model_name,
        "training_scope": training_scope,
        "target_contract_version": _clean_text(normalized_versions.get("target_contract_version")),
        "model_contract_version": _clean_text(normalized_versions.get("model_contract_version")),
        "scoring_policy_version": _clean_text(
            normalized_versions.get("scoring_policy_version") or normalized_versions.get("decision_policy_version")
        ),
        "explanation_contract_version": _clean_text(normalized_versions.get("explanation_contract_version")),
        "run_contract_version": _clean_text(normalized_versions.get("run_contract_version")),
        "fallback_reason": _clean_text(run_contract.get("fallback_reason")),
        "comparison_ready": bool(target_name and normalized_intent and normalized_mode),
    }
    return validate_comparison_anchors(payload)


def infer_comparison_anchors(
    *,
    session_record: dict[str, Any] | None = None,
    upload_metadata: dict[str, Any] | None = None,
    analysis_report: dict[str, Any] | None = None,
    decision_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_record = session_record or {}
    upload_metadata = upload_metadata or {}
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}
    summary_metadata = session_record.get("summary_metadata") if isinstance(session_record.get("summary_metadata"), dict) else {}
    scientific_truth = summary_metadata.get("scientific_session_truth") if isinstance(summary_metadata.get("scientific_session_truth"), dict) else {}

    existing = summary_metadata.get("comparison_anchors") if isinstance(summary_metadata.get("comparison_anchors"), dict) else {}
    if existing:
        return validate_comparison_anchors(existing)
    if scientific_truth and isinstance(scientific_truth.get("comparison_anchors"), dict):
        return validate_comparison_anchors(scientific_truth.get("comparison_anchors"))
    payload_existing = (
        decision_payload.get("comparison_anchors")
        if isinstance(decision_payload.get("comparison_anchors"), dict)
        else analysis_report.get("comparison_anchors")
        if isinstance(analysis_report.get("comparison_anchors"), dict)
        else {}
    )
    if payload_existing:
        return validate_comparison_anchors(payload_existing)

    run_contract = (
        scientific_truth.get("run_contract")
        if isinstance(scientific_truth.get("run_contract"), dict)
        else summary_metadata.get("run_contract")
        if isinstance(summary_metadata.get("run_contract"), dict)
        else decision_payload.get("run_contract")
        if isinstance(decision_payload.get("run_contract"), dict)
        else {}
    )
    if not isinstance(run_contract, dict):
        run_contract = {}

    target_definition = (
        scientific_truth.get("target_definition")
        if isinstance(scientific_truth.get("target_definition"), dict)
        else analysis_report.get("target_definition")
        if isinstance(analysis_report.get("target_definition"), dict)
        else decision_payload.get("target_definition")
        if isinstance(decision_payload.get("target_definition"), dict)
        else upload_metadata.get("target_definition")
        if isinstance(upload_metadata.get("target_definition"), dict)
        else {}
    )
    contract_versions = (
        scientific_truth.get("contract_versions")
        if isinstance(scientific_truth.get("contract_versions"), dict)
        else analysis_report.get("contract_versions")
        if isinstance(analysis_report.get("contract_versions"), dict)
        else decision_payload.get("contract_versions")
        if isinstance(decision_payload.get("contract_versions"), dict)
        else upload_metadata.get("contract_versions")
        if isinstance(upload_metadata.get("contract_versions"), dict)
        else summary_metadata.get("contract_versions")
        if isinstance(summary_metadata.get("contract_versions"), dict)
        else {}
    )
    validation_summary = upload_metadata.get("validation_summary") if isinstance(upload_metadata.get("validation_summary"), dict) else {}
    column_mapping = (
        upload_metadata.get("selected_mapping")
        or upload_metadata.get("semantic_roles")
        or upload_metadata.get("inferred_mapping")
        or {}
    )
    return build_comparison_anchors(
        session_id=_clean_text(session_record.get("session_id") or upload_metadata.get("session_id") or decision_payload.get("session_id")),
        source_name=_clean_text(session_record.get("source_name") or upload_metadata.get("filename")),
        input_type=_clean_text(session_record.get("input_type") or upload_metadata.get("input_type")),
        column_mapping=column_mapping,
        target_definition=target_definition,
        decision_intent=(
            scientific_truth.get("decision_intent")
            or analysis_report.get("decision_intent")
            or decision_payload.get("decision_intent")
            or upload_metadata.get("decision_intent")
            or summary_metadata.get("decision_intent")
        ),
        modeling_mode=(
            scientific_truth.get("modeling_mode")
            or analysis_report.get("modeling_mode")
            or decision_payload.get("modeling_mode")
            or summary_metadata.get("modeling_mode")
            or run_contract.get("modeling_mode")
        ),
        scoring_mode=(
            analysis_report.get("mode_used")
            or decision_payload.get("mode_used")
            or summary_metadata.get("scoring_mode")
            or run_contract.get("scoring_mode")
        ),
        contract_versions=contract_versions,
        validation_summary=validation_summary,
        run_contract=run_contract,
    )


def comparison_anchor_summary(anchors: dict[str, Any] | None) -> str:
    if not isinstance(anchors, dict) or not anchors:
        return ""
    target_name = _clean_text(anchors.get("target_name"), default="target not recorded")
    modeling_mode = _clean_text(anchors.get("modeling_mode"), default="mode not recorded").replace("_", " ")
    decision_intent = _clean_text(anchors.get("decision_intent"), default="intent not recorded").replace("_", " ")
    scoring_version = _clean_text(anchors.get("scoring_policy_version"), default="policy version not recorded")
    return f"{target_name} · {modeling_mode} · {decision_intent} · {scoring_version}"


def build_run_provenance(
    *,
    run_contract: dict[str, Any] | None,
    comparison_anchors: dict[str, Any] | None,
) -> dict[str, Any]:
    run_contract = run_contract if isinstance(run_contract, dict) else {}
    comparison_anchors = comparison_anchors if isinstance(comparison_anchors, dict) else {}
    if not run_contract and not comparison_anchors:
        return {}

    comparison_basis_label = comparison_anchor_summary(comparison_anchors)
    comparison_ready = bool(comparison_anchors.get("comparison_ready"))
    fallback_reason = _clean_text(
        comparison_anchors.get("fallback_reason") or run_contract.get("fallback_reason")
    )
    selected_model_name = _clean_text(
        run_contract.get("selected_model_name") or comparison_anchors.get("selected_model_name"),
        default="Model not recorded",
    )
    selected_model_family = _humanize_token(run_contract.get("selected_model_family"), default="")
    calibration_method = _clean_text(run_contract.get("calibration_method"))
    training_scope = _clean_text(
        run_contract.get("training_scope") or comparison_anchors.get("training_scope")
    )
    scoring_mode = _clean_text(
        run_contract.get("scoring_mode") or comparison_anchors.get("scoring_mode"),
        default="not recorded",
    )
    policy_version = _clean_text(comparison_anchors.get("scoring_policy_version"), default="policy version not recorded")
    explanation_version = _clean_text(
        comparison_anchors.get("explanation_contract_version"),
        default="explanation contract not recorded",
    )
    reference_basis = run_contract.get("reference_basis") if isinstance(run_contract.get("reference_basis"), dict) else {}
    novelty_reference = _clean_text(reference_basis.get("novelty_reference"), default="not recorded")
    applicability_reference = _clean_text(reference_basis.get("applicability_reference"), default="not recorded")

    if training_scope == "session_trained":
        model_summary = (
            f"This run used a session-trained {selected_model_family.lower() + ' ' if selected_model_family else ''}"
            f"model ({selected_model_name})."
        )
    elif training_scope == "baseline_bundle":
        model_summary = f"This run used the saved legacy baseline model bundle ({selected_model_name}) instead of training on the current session."
    elif training_scope == "ranking_without_target_model":
        model_summary = "This run did not use a target-trained model, so shortlist ordering depends more on policy-level ranking than on model discrimination."
    else:
        model_summary = f"This run recorded model provenance as {selected_model_name}."

    if calibration_method:
        model_summary = f"{model_summary.rstrip('.')} Calibration method: {calibration_method}."

    if comparison_ready:
        comparison_summary = (
            "This session is comparison-ready against runs that share the same target definition, modeling mode, "
            "and scoring-policy version."
        )
    elif fallback_reason:
        comparison_summary = (
            "Comparison metadata is only partially trustworthy because the recorded run contract required a fallback "
            f"({fallback_reason.replace('_', ' ')})."
        )
    else:
        comparison_summary = (
            "Comparison metadata is partial because older sessions did not record the full scientific contract needed "
            "for clean run-to-run comparison."
        )

    training_scope_summary = {
        "session_trained": "The model was fit from the current session data before ranking.",
        "baseline_bundle": "The model came from a pre-existing legacy saved bundle, so the session reused older model state instead of fitting a session-specific target model.",
        "ranking_without_target_model": "No target-trained model was available, so the run behaved mostly as a ranking/policy workflow.",
    }.get(training_scope, "Training scope was not fully recorded for this run.")

    reference_summary = (
        f"Novelty reference: {novelty_reference.replace('_', ' ')}. "
        f"Applicability reference: {applicability_reference.replace('_', ' ')}."
    )
    policy_summary = (
        f"Scoring mode {scoring_mode.replace('_', ' ')} used policy version {policy_version}. "
        f"Explanation contract: {explanation_version}."
    )

    cautions: list[str] = []
    if fallback_reason:
        cautions.append(f"Fallback recorded: {fallback_reason.replace('_', ' ')}.")
    if training_scope == "baseline_bundle":
        cautions.append("Comparisons against session-trained runs should account for the reused legacy baseline model.")
    if training_scope == "ranking_without_target_model":
        cautions.append("Treat recommendation ordering as policy-heavy because target-model provenance is weak.")

    bridge_state_active = bool(
        fallback_reason or training_scope in {"baseline_bundle", "ranking_without_target_model"}
    )
    if training_scope == "baseline_bundle":
        bridge_state_summary = (
            "Bridge-state fallback is active because this run reused the saved legacy baseline bundle instead of "
            "training a session-specific target model."
        )
    elif training_scope == "ranking_without_target_model":
        bridge_state_summary = (
            "Bridge-state fallback is active because no target-trained model was available, so ordering depends more "
            "on policy-level ranking than on model discrimination."
        )
    elif fallback_reason:
        bridge_state_summary = (
            "Bridge-state fallback metadata was recorded for this session, so comparison and interpretation should be "
            f"read with the recorded fallback in mind ({fallback_reason.replace('_', ' ')})."
        )
    else:
        bridge_state_summary = ""

    return {
        "comparison_ready": comparison_ready,
        "comparison_basis_label": comparison_basis_label,
        "comparison_summary": comparison_summary,
        "selected_model_name": selected_model_name,
        "selected_model_family": selected_model_family,
        "calibration_method": calibration_method,
        "model_summary": model_summary,
        "training_scope": training_scope,
        "training_scope_label": _humanize_token(training_scope),
        "training_scope_summary": training_scope_summary,
        "scoring_mode_label": _humanize_token(scoring_mode),
        "policy_version": policy_version,
        "explanation_version": explanation_version,
        "policy_summary": policy_summary,
        "reference_summary": reference_summary,
        "fallback_reason": fallback_reason,
        "cautions": cautions,
        "bridge_state_active": bridge_state_active,
        "bridge_state_summary": bridge_state_summary,
    }


__all__ = [
    "build_comparison_anchors",
    "build_run_contract",
    "build_run_provenance",
    "comparison_anchor_summary",
    "infer_comparison_anchors",
]
