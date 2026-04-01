from __future__ import annotations

from typing import Any

from system.contracts import (
    DatasetType,
    DecisionIntent,
    MappingConfidence,
    ModelingMode,
    OptimizationDirection,
    TargetDefinition,
    TargetKind,
    validate_label_builder_config,
    validate_target_definition,
    validate_upload_inspection_result,
)


LEGACY_INTENT_MAP = {
    "rank_uploaded_molecules": DecisionIntent.prioritize_experiments.value,
    "predict_labels": DecisionIntent.estimate_labels.value,
    "generate_candidates": DecisionIntent.generate_candidates.value,
    "explore_uncertain": DecisionIntent.reduce_uncertainty.value,
}

DEFAULT_CONTRACT_VERSIONS = {
    "target_contract_version": "target_definition.v1",
    "model_contract_version": "model_contract.v1",
    "scientific_output_version": "scientific_output.v1",
    "explanation_contract_version": "normalized_explanation.v1",
    "decision_policy_version": "decision_policy.v1",
    "scoring_policy_version": "scoring_policy.v1",
    "run_contract_version": "run_contract.v1",
    "comparison_anchor_version": "comparison_anchors.v1",
}

BIODEGRADABILITY_HINTS = {"biodegradable", "biodegradability", "degradable", "degradation"}
MAXIMIZE_HINTS = {"pic50", "pec50", "pchembl", "solubility", "conductivity", "yield", "potency"}
MINIMIZE_HINTS = {"ic50", "ec50", "toxicity", "toxic", "clearance", "risk", "error"}


def normalize_decision_intent(intent: str | None) -> str:
    cleaned = str(intent or "").strip().lower()
    if not cleaned:
        return DecisionIntent.prioritize_experiments.value
    if cleaned in LEGACY_INTENT_MAP:
        return LEGACY_INTENT_MAP[cleaned]
    if cleaned in {item.value for item in DecisionIntent}:
        return cleaned
    return DecisionIntent.prioritize_experiments.value


def normalize_modeling_mode(value: str | None, *, default: str = ModelingMode.binary_classification.value) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in {item.value for item in ModelingMode}:
        return cleaned
    return default


def default_contract_versions(overrides: dict[str, Any] | None = None) -> dict[str, str]:
    payload = dict(DEFAULT_CONTRACT_VERSIONS)
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            text = str(value or "").strip()
            if text:
                payload[str(key)] = text
    return payload


def _non_empty_text(value: Any) -> str:
    text = str(value or "").strip()
    return text


def _normalize_mapping(mapping: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(mapping, dict):
        return {}
    return {str(key).strip().lower(): _non_empty_text(value).lower() for key, value in mapping.items() if _non_empty_text(value)}


def _measurement_unit_for_column(column_name: str) -> str:
    cleaned = column_name.lower().strip()
    if cleaned.endswith("_nm") or cleaned.endswith(" nm"):
        return "nM"
    if cleaned.endswith("_um") or cleaned.endswith(" um"):
        return "uM"
    if cleaned.startswith("pic50") or cleaned.startswith("pec50") or cleaned.startswith("pchembl"):
        return "log10 molar potency scale"
    return ""


def _optimization_direction(target_name: str, *, target_kind: str) -> str:
    if target_kind == TargetKind.classification.value:
        return OptimizationDirection.classify.value

    cleaned = target_name.lower().replace(" ", "_")
    if any(token in cleaned for token in MAXIMIZE_HINTS):
        return OptimizationDirection.maximize.value
    if any(token in cleaned for token in MINIMIZE_HINTS):
        return OptimizationDirection.minimize.value
    return OptimizationDirection.hit_range.value


def _scientific_meaning(target_name: str, target_kind: str, optimization_direction: str) -> str:
    if target_kind == TargetKind.classification.value:
        return f"The model estimates whether a molecule belongs to the positive class for {target_name}."
    if optimization_direction == OptimizationDirection.maximize.value:
        return f"Higher predicted values are treated as more favorable for {target_name}."
    if optimization_direction == OptimizationDirection.minimize.value:
        return f"Lower predicted values are treated as more favorable for {target_name}."
    return f"Predicted values for {target_name} are interpreted as a continuous property and should be reviewed in context."


def _success_definition(target_name: str, target_kind: str, optimization_direction: str) -> str:
    if target_kind == TargetKind.classification.value:
        return f"Success means prioritizing molecules likely to belong to the positive class for {target_name}."
    if optimization_direction == OptimizationDirection.maximize.value:
        return f"Success means prioritizing molecules expected to achieve higher {target_name} values."
    if optimization_direction == OptimizationDirection.minimize.value:
        return f"Success means prioritizing molecules expected to achieve lower {target_name} values."
    return f"Success means prioritizing molecules whose predicted {target_name} values look experimentally useful to test."


def _mapping_confidence(label_column: str, measurement_column: str, summary: dict[str, Any]) -> str:
    rows_with_labels = int(summary.get("rows_with_labels", 0) or 0)
    rows_with_values = int(summary.get("rows_with_values", 0) or 0)
    if label_column and rows_with_labels > 0:
        return MappingConfidence.high.value
    if measurement_column and rows_with_values > 0:
        return MappingConfidence.medium.value
    return MappingConfidence.low.value


def _dataset_type(label_column: str, measurement_column: str, label_builder_payload: dict[str, Any], summary: dict[str, Any]) -> str:
    if label_column or int(summary.get("rows_with_labels", 0) or 0) > 0 or bool(label_builder_payload.get("enabled")):
        return DatasetType.labeled_dataset.value
    if measurement_column or int(summary.get("rows_with_values", 0) or 0) > 0:
        return DatasetType.measurement_dataset.value
    return DatasetType.structure_only.value


def _default_target_name(label_column: str, measurement_column: str) -> str:
    if any(token in label_column for token in BIODEGRADABILITY_HINTS):
        return "biodegradability"
    if measurement_column:
        return measurement_column
    if label_column:
        return label_column
    return "biodegradability"


def _derived_label_rule(label_builder: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = validate_label_builder_config(label_builder or {"enabled": False})
    if not payload.get("enabled"):
        return None
    return {
        "source_column": payload.get("value_column") or "",
        "operator": payload.get("operator") or ">=",
        "threshold": payload.get("threshold"),
        "positive_label": int(payload.get("positive_label", 1) or 1),
        "negative_label": int(payload.get("negative_label", 0) or 0),
        "rule_reason": "Binary labels were derived from the numeric measurement column using the configured threshold rule.",
    }


def infer_target_definition(
    *,
    mapping: dict[str, Any] | None,
    validation_summary: dict[str, Any] | None,
    label_builder: dict[str, Any] | None = None,
    existing: dict[str, Any] | None = None,
    target_name_hint: str | None = None,
    scientific_notes: str | None = None,
) -> dict[str, Any]:
    summary = validation_summary or {}
    normalized_mapping = _normalize_mapping(mapping)
    label_column = normalized_mapping.get("label") or normalized_mapping.get("biodegradable") or ""
    measurement_column = normalized_mapping.get("value") or _non_empty_text(summary.get("value_column")).lower()
    label_rule = _derived_label_rule(label_builder)
    dataset_type = _dataset_type(label_column, measurement_column, label_builder or {}, summary)

    existing_payload = dict(existing or {})
    target_name = _non_empty_text(existing_payload.get("target_name") or target_name_hint) or _default_target_name(
        label_column,
        measurement_column,
    )

    target_kind = _non_empty_text(existing_payload.get("target_kind"))
    if target_kind not in {item.value for item in TargetKind}:
        if dataset_type == DatasetType.measurement_dataset.value and not label_column and label_rule is None:
            target_kind = TargetKind.regression.value
        else:
            target_kind = TargetKind.classification.value

    optimization_direction = _non_empty_text(existing_payload.get("optimization_direction"))
    if optimization_direction not in {item.value for item in OptimizationDirection}:
        optimization_direction = _optimization_direction(target_name, target_kind=target_kind)

    target_payload = {
        "target_name": target_name,
        "target_kind": target_kind,
        "optimization_direction": optimization_direction,
        "measurement_column": measurement_column or _non_empty_text(existing_payload.get("measurement_column")),
        "label_column": label_column or _non_empty_text(existing_payload.get("label_column")),
        "measurement_unit": _non_empty_text(existing_payload.get("measurement_unit"))
        or _measurement_unit_for_column(measurement_column or ""),
        "scientific_meaning": _non_empty_text(existing_payload.get("scientific_meaning"))
        or _scientific_meaning(target_name, target_kind, optimization_direction),
        "assay_context": _non_empty_text(existing_payload.get("assay_context")),
        "dataset_type": _non_empty_text(existing_payload.get("dataset_type")) or dataset_type,
        "mapping_confidence": _non_empty_text(existing_payload.get("mapping_confidence"))
        or _mapping_confidence(label_column, measurement_column, summary),
        "derived_label_rule": existing_payload.get("derived_label_rule") or label_rule,
        "success_definition": _non_empty_text(existing_payload.get("success_definition"))
        or _success_definition(target_name, target_kind, optimization_direction),
        "target_notes": _non_empty_text(existing_payload.get("target_notes") or scientific_notes),
    }
    return validate_target_definition(target_payload)


def enrich_upload_inspection_payload(payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload or {})
    enriched["target_definition"] = infer_target_definition(
        mapping=enriched.get("selected_mapping") or enriched.get("semantic_roles") or enriched.get("inferred_mapping"),
        validation_summary=enriched.get("validation_summary") or {},
        label_builder=enriched.get("label_builder_config") or enriched.get("label_builder_suggestion"),
        existing=enriched.get("target_definition") or {},
    )
    if not enriched.get("decision_intent"):
        enriched["decision_intent"] = DecisionIntent.prioritize_experiments.value
    enriched["contract_versions"] = default_contract_versions(enriched.get("contract_versions"))
    return validate_upload_inspection_result(enriched)


def infer_modeling_mode(
    *,
    target_definition: dict[str, Any] | None,
    decision_intent: str,
    used_candidate_generation: bool,
    target_model_available: bool,
) -> str:
    target_kind = str((target_definition or {}).get("target_kind") or TargetKind.classification.value)
    if used_candidate_generation:
        return ModelingMode.mutation_based_candidate_generation.value
    if target_kind == TargetKind.regression.value and target_model_available:
        return ModelingMode.regression.value
    if target_kind == TargetKind.classification.value and target_model_available:
        return ModelingMode.binary_classification.value
    return ModelingMode.ranking_only.value


__all__ = [
    "DEFAULT_CONTRACT_VERSIONS",
    "default_contract_versions",
    "enrich_upload_inspection_payload",
    "infer_modeling_mode",
    "infer_target_definition",
    "normalize_decision_intent",
    "normalize_modeling_mode",
]
