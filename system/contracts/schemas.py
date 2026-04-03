from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, Field, ValidationError, root_validator, validator

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - Pydantic v1
    ConfigDict = None


ModelT = TypeVar("ModelT", bound=BaseModel)


class ContractValidationError(ValueError):
    def __init__(self, contract_name: str, detail: str):
        super().__init__(f"{contract_name} validation failed: {detail}")
        self.contract_name = contract_name
        self.detail = detail


def _validation_error_text(exc: ValidationError) -> str:
    parts: list[str] = []
    for item in exc.errors():
        location = ".".join(str(token) for token in item.get("loc", ())) or "__root__"
        parts.append(f"{location}: {item.get('msg', 'invalid value')}")
    return "; ".join(parts)


def validate_contract_model(model_cls: type[ModelT], payload: Any, contract_name: str | None = None) -> ModelT:
    try:
        if hasattr(model_cls, "model_validate"):
            return model_cls.model_validate(payload)
        return model_cls.parse_obj(payload)
    except ValidationError as exc:
        raise ContractValidationError(contract_name or model_cls.__name__, _validation_error_text(exc)) from exc


def dump_contract_model(instance: BaseModel) -> dict[str, Any]:
    if hasattr(instance, "model_dump_json"):
        return json.loads(instance.model_dump_json(by_alias=True, exclude_none=True))
    return json.loads(instance.json(by_alias=True, exclude_none=True))


def _int_or_default(value: Any, default: int) -> int:
    return int(default if value is None else value)


class ContractBaseModel(BaseModel):
    if ConfigDict is not None:
        model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=True, validate_assignment=True)
    else:  # pragma: no cover - Pydantic v1
        class Config:
            extra = "forbid"
            allow_population_by_field_name = True
            use_enum_values = True
            validate_assignment = True


class ArtifactState(str, Enum):
    ok = "ok"
    missing = "missing"
    error = "error"


class Bucket(str, Enum):
    exploit = "exploit"
    learn = "learn"
    explore = "explore"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ReviewStatus(str, Enum):
    suggested = "suggested"
    under_review = "under review"
    approved = "approved"
    rejected = "rejected"
    tested = "tested"
    ingested = "ingested"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class WorkspaceRole(str, Enum):
    owner = "owner"
    member = "member"


class WorkspacePlanTier(str, Enum):
    free = "free"
    pro = "pro"
    internal = "internal"


class WorkspacePlanStatus(str, Enum):
    active = "active"
    trialing = "trialing"
    past_due = "past_due"
    canceled = "canceled"


class WorkspaceUsageEventType(str, Enum):
    analysis_job_created = "analysis_job_created"
    candidate_generation_requested = "candidate_generation_requested"
    upload_session_created = "upload_session_created"
    upload_rows_uploaded = "upload_rows_uploaded"
    decision_exported = "decision_exported"


class TargetKind(str, Enum):
    classification = "classification"
    regression = "regression"


class OptimizationDirection(str, Enum):
    maximize = "maximize"
    minimize = "minimize"
    classify = "classify"
    hit_range = "hit_range"


class DatasetType(str, Enum):
    structure_only = "structure_only"
    measurement_dataset = "measurement_dataset"
    labeled_dataset = "labeled_dataset"


class MappingConfidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class DecisionIntent(str, Enum):
    prioritize_experiments = "prioritize_experiments"
    estimate_labels = "estimate_labels"
    generate_candidates = "generate_candidates"
    reduce_uncertainty = "reduce_uncertainty"


class ModelingMode(str, Enum):
    binary_classification = "binary_classification"
    regression = "regression"
    mutation_based_candidate_generation = "mutation_based_candidate_generation"
    ranking_only = "ranking_only"


class DomainStatus(str, Enum):
    in_domain = "in_domain"
    near_boundary = "near_boundary"
    out_of_domain = "out_of_domain"
    unknown = "unknown"


class EvidenceType(str, Enum):
    experimental_value = "experimental_value"
    binary_label = "binary_label"
    chemistry_feature = "chemistry_feature"
    derived_label = "derived_label"
    reference_context = "reference_context"
    model_prediction = "model_prediction"
    human_review = "human_review"
    workspace_memory = "workspace_memory"
    learning_queue = "learning_queue"


class EvidenceTruthStatus(str, Enum):
    observed = "observed"
    computed = "computed"
    retrieved = "retrieved"
    derived = "derived"
    predicted = "predicted"
    reviewed = "reviewed"


class EvidenceScope(str, Enum):
    session_input = "session_input"
    session_output = "session_output"
    workspace_history = "workspace_history"
    reference_corpus = "reference_corpus"
    session_summary = "session_summary"


class EvidenceUse(str, Enum):
    active_modeling = "active_modeling"
    active_ranking = "active_ranking"
    interpretation_only = "interpretation_only"
    memory_only = "memory_only"
    stored_not_active = "stored_not_active"


class EvidenceFutureUse(str, Enum):
    none = "none"
    may_inform_future_ranking = "may_inform_future_ranking"
    may_inform_future_learning = "may_inform_future_learning"


class EvidenceSupportLevel(str, Enum):
    strong = "strong"
    moderate = "moderate"
    limited = "limited"
    contextual = "contextual"


class ClaimType(str, Enum):
    recommendation_assertion = "recommendation_assertion"


class ClaimStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"


class ExperimentRequestStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"
    completed = "completed"
    superseded = "superseded"


class PriorityTier(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ExperimentResultQuality(str, Enum):
    provisional = "provisional"
    screening = "screening"
    confirmatory = "confirmatory"


class ExperimentResultSource(str, Enum):
    manual_entry = "manual_entry"
    uploaded_result = "uploaded_result"
    external_record = "external_record"


class BeliefUpdateDirection(str, Enum):
    strengthened = "strengthened"
    weakened = "weakened"
    unresolved = "unresolved"


class BeliefUpdateGovernanceStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"


BUCKET_VALUES = tuple(item.value for item in Bucket)
RISK_LEVEL_VALUES = tuple(item.value for item in RiskLevel)
REVIEW_STATUS_VALUES = tuple(item.value for item in ReviewStatus)
WORKSPACE_ROLE_VALUES = tuple(item.value for item in WorkspaceRole)
WORKSPACE_PLAN_TIER_VALUES = tuple(item.value for item in WorkspacePlanTier)
WORKSPACE_PLAN_STATUS_VALUES = tuple(item.value for item in WorkspacePlanStatus)
WORKSPACE_USAGE_EVENT_TYPE_VALUES = tuple(item.value for item in WorkspaceUsageEventType)
TARGET_KIND_VALUES = tuple(item.value for item in TargetKind)
OPTIMIZATION_DIRECTION_VALUES = tuple(item.value for item in OptimizationDirection)
DATASET_TYPE_VALUES = tuple(item.value for item in DatasetType)
MAPPING_CONFIDENCE_VALUES = tuple(item.value for item in MappingConfidence)
DECISION_INTENT_VALUES = tuple(item.value for item in DecisionIntent)
MODELING_MODE_VALUES = tuple(item.value for item in ModelingMode)
DOMAIN_STATUS_VALUES = tuple(item.value for item in DomainStatus)
EVIDENCE_TYPE_VALUES = tuple(item.value for item in EvidenceType)
EVIDENCE_TRUTH_STATUS_VALUES = tuple(item.value for item in EvidenceTruthStatus)
EVIDENCE_SCOPE_VALUES = tuple(item.value for item in EvidenceScope)
EVIDENCE_USE_VALUES = tuple(item.value for item in EvidenceUse)
EVIDENCE_FUTURE_USE_VALUES = tuple(item.value for item in EvidenceFutureUse)
EVIDENCE_SUPPORT_LEVEL_VALUES = tuple(item.value for item in EvidenceSupportLevel)
CLAIM_TYPE_VALUES = tuple(item.value for item in ClaimType)
CLAIM_STATUS_VALUES = tuple(item.value for item in ClaimStatus)
EXPERIMENT_REQUEST_STATUS_VALUES = tuple(item.value for item in ExperimentRequestStatus)
PRIORITY_TIER_VALUES = tuple(item.value for item in PriorityTier)
EXPERIMENT_RESULT_QUALITY_VALUES = tuple(item.value for item in ExperimentResultQuality)
EXPERIMENT_RESULT_SOURCE_VALUES = tuple(item.value for item in ExperimentResultSource)
BELIEF_UPDATE_DIRECTION_VALUES = tuple(item.value for item in BeliefUpdateDirection)
BELIEF_UPDATE_GOVERNANCE_STATUS_VALUES = tuple(item.value for item in BeliefUpdateGovernanceStatus)


def _clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _normalize_bucket(value: Any) -> str:
    return _clean_text(value).lower()


def _normalize_risk(value: Any) -> str:
    return _clean_text(value).lower()


def _normalize_status(value: Any) -> str:
    return _clean_text(value).lower().replace("_", " ")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _infer_model_family(model_name: str, version: str) -> str:
    cleaned_name = _clean_text(model_name).lower()
    cleaned_version = _clean_text(version).lower()
    if cleaned_name.startswith("rf") or cleaned_version.startswith("rf"):
        return "random_forest"
    return cleaned_name or "unknown"


def _legacy_provenance_text() -> str:
    return "Legacy decision artifact without recorded provenance."


def _legacy_model_metadata(model_version: Any) -> dict[str, Any]:
    version = _clean_text(model_version, default="unknown")
    calibration_method = ""
    if ":" in version:
        _, calibration_method = version.split(":", 1)
    return {
        "version": version,
        "family": _infer_model_family(version, version),
        "calibration_method": calibration_method,
    }


class LabelCounts(ContractBaseModel):
    positive: int = Field(default=0, ge=0)
    negative: int = Field(default=0, ge=0)
    unlabeled: int = Field(default=0, ge=0)
    coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    class_balance_ratio: float | None = Field(default=None, ge=0.0, le=1.0)

    @root_validator(pre=False)
    def _derive_balance(cls, values: dict[str, Any]) -> dict[str, Any]:
        positive = int(values.get("positive", 0))
        negative = int(values.get("negative", 0))
        unlabeled = int(values.get("unlabeled", 0))
        total = positive + negative + unlabeled
        labeled = positive + negative
        values["coverage"] = float(labeled / total) if total else 0.0
        if labeled and positive and negative:
            values["class_balance_ratio"] = float(min(positive, negative) / labeled)
        else:
            values["class_balance_ratio"] = values.get("class_balance_ratio")
        return values


class ValidationStats(ContractBaseModel):
    total_rows: int = Field(ge=0)
    valid_smiles_count: int = Field(ge=0)
    invalid_smiles_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    rows_with_labels: int = Field(ge=0)
    rows_without_labels: int = Field(ge=0)
    rows_with_values: int = Field(default=0, ge=0)
    rows_without_values: int = Field(default=0, ge=0)
    value_column: str = ""
    semantic_mode: str = ""
    label_source: str = ""
    file_type: str = ""
    positive_label_count: int = Field(default=0, ge=0)
    negative_label_count: int = Field(default=0, ge=0)
    unlabeled_label_count: int = Field(default=0, ge=0)
    label_counts: LabelCounts = Field(default_factory=LabelCounts)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    can_run_analysis: bool
    analyzed_rows: int | None = Field(default=None, ge=0)
    canonicalized_rows: int | None = Field(default=None, ge=0)
    duplicate_removed_count: int | None = Field(default=None, ge=0)
    usable_label_count: int | None = Field(default=None, ge=0)
    row_count_before: int | None = Field(default=None, ge=0)
    row_count_after: int | None = Field(default=None, ge=0)

    @root_validator(pre=False)
    def _fill_derived_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        total_rows = _int_or_default(values.get("total_rows", 0), 0)
        rows_with_labels = _int_or_default(values.get("rows_with_labels", 0), 0)
        rows_without_labels = _int_or_default(
            values.get("rows_without_labels", max(total_rows - rows_with_labels, 0)),
            max(total_rows - rows_with_labels, 0),
        )
        rows_with_values = _int_or_default(values.get("rows_with_values", 0), 0)
        rows_without_values = _int_or_default(
            values.get("rows_without_values", max(total_rows - rows_with_values, 0)),
            max(total_rows - rows_with_values, 0),
        )
        values["rows_without_labels"] = rows_without_labels
        values["rows_with_values"] = rows_with_values
        values["rows_without_values"] = rows_without_values
        values["value_column"] = _clean_text(values.get("value_column"))
        values["semantic_mode"] = _clean_text(values.get("semantic_mode"))
        values["label_source"] = _clean_text(values.get("label_source"))
        values["file_type"] = _clean_text(values.get("file_type"))
        values["row_count_before"] = _int_or_default(values.get("row_count_before", total_rows), total_rows)
        values["row_count_after"] = _int_or_default(
            values.get("row_count_after", values.get("analyzed_rows", total_rows)),
            _int_or_default(values.get("analyzed_rows", total_rows), total_rows),
        )
        values["analyzed_rows"] = _int_or_default(values.get("analyzed_rows", values["row_count_after"]), values["row_count_after"])
        values["canonicalized_rows"] = _int_or_default(
            values.get("canonicalized_rows", values.get("valid_smiles_count", 0)),
            _int_or_default(values.get("valid_smiles_count", 0), 0),
        )
        values["duplicate_removed_count"] = _int_or_default(
            values.get("duplicate_removed_count", values.get("duplicate_count", 0)),
            _int_or_default(values.get("duplicate_count", 0), 0),
        )
        values["usable_label_count"] = _int_or_default(values.get("usable_label_count", rows_with_labels), rows_with_labels)
        label_counts = values.get("label_counts")
        if not isinstance(label_counts, LabelCounts):
            label_counts = LabelCounts(
                positive=_int_or_default(values.get("positive_label_count", 0), 0),
                negative=_int_or_default(values.get("negative_label_count", 0), 0),
                unlabeled=_int_or_default(values.get("unlabeled_label_count", rows_without_labels), rows_without_labels),
            )
        values["label_counts"] = label_counts
        return values


class LabelBuilderConfig(ContractBaseModel):
    enabled: bool = False
    value_column: str = ""
    operator: str = ">="
    threshold: float | None = None
    positive_label: int = Field(default=1)
    negative_label: int = Field(default=0)

    @validator("value_column", "operator", pre=True, always=True)
    def _clean_label_builder_text(cls, value: Any, field) -> str:
        default = ">=" if field.name == "operator" else ""
        return _clean_text(value, default=default)

    @root_validator(pre=False)
    def _validate_rule(cls, values: dict[str, Any]) -> dict[str, Any]:
        enabled = bool(values.get("enabled"))
        operator = values.get("operator") or ">="
        if operator not in {">", ">=", "<", "<=", "=", "=="}:
            raise ValueError("operator must be one of >, >=, <, <=, =, ==")
        if enabled and not values.get("value_column"):
            raise ValueError("value_column is required when label builder is enabled")
        if enabled and values.get("threshold") is None:
            raise ValueError("threshold is required when label builder is enabled")
        return values


class DerivedLabelRule(ContractBaseModel):
    source_column: str = ""
    operator: str = ">="
    threshold: float | None = None
    positive_label: int = Field(default=1)
    negative_label: int = Field(default=0)
    rule_reason: str = ""

    @validator("source_column", "operator", "rule_reason", pre=True, always=True)
    def _clean_rule_text(cls, value: Any, field) -> str:
        default = ">=" if field.name == "operator" else ""
        return _clean_text(value, default=default)


class TargetDefinition(ContractBaseModel):
    schema_version: str = "target_definition.v1"
    target_name: str = ""
    target_kind: TargetKind = TargetKind.classification
    optimization_direction: OptimizationDirection = OptimizationDirection.classify
    measurement_column: str = ""
    label_column: str = ""
    measurement_unit: str = ""
    scientific_meaning: str = ""
    assay_context: str = ""
    dataset_type: DatasetType = DatasetType.structure_only
    mapping_confidence: MappingConfidence = MappingConfidence.low
    derived_label_rule: DerivedLabelRule | None = None
    success_definition: str = ""
    target_notes: str = ""

    @validator(
        "target_name",
        "measurement_column",
        "label_column",
        "measurement_unit",
        "scientific_meaning",
        "assay_context",
        "success_definition",
        "target_notes",
        pre=True,
        always=True,
    )
    def _clean_target_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("target_kind", pre=True)
    def _clean_target_kind(cls, value: Any) -> str:
        return _clean_text(value, default=TargetKind.classification.value).lower()

    @validator("optimization_direction", pre=True)
    def _clean_optimization_direction(cls, value: Any) -> str:
        return _clean_text(value, default=OptimizationDirection.classify.value).lower()

    @validator("dataset_type", pre=True)
    def _clean_dataset_type(cls, value: Any) -> str:
        return _clean_text(value, default=DatasetType.structure_only.value).lower()

    @validator("mapping_confidence", pre=True)
    def _clean_mapping_confidence(cls, value: Any) -> str:
        return _clean_text(value, default=MappingConfidence.low.value).lower()


class SessionIdentity(ContractBaseModel):
    schema_version: str = "session_identity.v1"
    session_id: str
    source_name: str = ""
    created_at: datetime | None = None
    created_at_label: str = ""
    workspace_id: str = ""
    target_definition: TargetDefinition | None = None
    modeling_mode: ModelingMode | None = None
    modeling_mode_label: str = ""
    decision_intent: DecisionIntent | None = None
    decision_intent_label: str = ""
    session_status: str = ""
    session_status_tone: str = ""
    current_job_status: JobStatus | None = None
    scientific_purpose: str = ""
    evidence_support_label: str = ""
    evidence_summary: str = ""
    bridge_state_summary: str = ""
    trust_summary: str = ""
    latest_result_summary: str = ""

    @validator(
        "session_id",
        "source_name",
        "created_at_label",
        "workspace_id",
        "modeling_mode_label",
        "decision_intent_label",
        "session_status",
        "session_status_tone",
        "scientific_purpose",
        "evidence_support_label",
        "evidence_summary",
        "bridge_state_summary",
        "trust_summary",
        "latest_result_summary",
        pre=True,
        always=True,
    )
    def _clean_identity_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("created_at", pre=True)
    def _coerce_identity_created_at(cls, value: Any) -> Any:
        return _coerce_datetime(value)

    @validator("decision_intent", pre=True)
    def _clean_identity_decision_intent(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("modeling_mode", pre=True)
    def _clean_identity_modeling_mode(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("current_job_status", pre=True)
    def _clean_identity_job_status(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()


class StatusSemantics(ContractBaseModel):
    schema_version: str = "status_semantics.v1"
    status_code: str = ""
    status_tone: str = ""
    where_failed: str = ""
    usable_upload: bool = False
    usable_validation: bool = False
    viewable_artifacts: bool = False
    trustworthy_recommendations: bool = False
    rerun_possible: bool = False
    can_open_discovery: bool = False
    can_open_dashboard: bool = False
    available_artifacts: list[str] = Field(default_factory=list)
    headline: str = ""
    detail: str = ""
    next_steps: list[str] = Field(default_factory=list)
    last_error: str = ""

    @validator(
        "status_code",
        "status_tone",
        "where_failed",
        "headline",
        "detail",
        "last_error",
        pre=True,
        always=True,
    )
    def _clean_status_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("available_artifacts", "next_steps", pre=True)
    def _clean_status_lists(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _clean_text(item)]


class RunContract(ContractBaseModel):
    schema_version: str = "run_contract.v1"
    session_id: str = ""
    source_name: str = ""
    input_type: str = ""
    requested_intent: str = ""
    decision_intent: DecisionIntent | None = None
    modeling_mode: ModelingMode | None = None
    scoring_mode: str = ""
    target_definition: TargetDefinition | None = None
    target_model_available: bool = False
    candidate_generation_requested: bool = False
    candidate_generation_eligible: bool = False
    used_candidate_generation: bool = False
    fallback_reason: str = ""
    selected_model_name: str = ""
    selected_model_family: str = ""
    calibration_method: str = ""
    training_scope: str = ""
    label_source: str = ""
    feature_signature: str = ""
    reference_basis: dict[str, str] = Field(default_factory=dict)
    contract_versions: dict[str, str] = Field(default_factory=dict)

    @validator(
        "session_id",
        "source_name",
        "input_type",
        "requested_intent",
        "scoring_mode",
        "fallback_reason",
        "selected_model_name",
        "selected_model_family",
        "calibration_method",
        "training_scope",
        "label_source",
        "feature_signature",
        pre=True,
        always=True,
    )
    def _clean_run_contract_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("decision_intent", pre=True)
    def _clean_run_contract_intent(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("modeling_mode", pre=True)
    def _clean_run_contract_mode(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("reference_basis", "contract_versions", pre=True)
    def _clean_run_contract_mapping(cls, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        payload: dict[str, str] = {}
        for key, item in value.items():
            cleaned_key = _clean_text(key)
            cleaned_value = _clean_text(item)
            if cleaned_key and cleaned_value:
                payload[cleaned_key] = cleaned_value
        return payload


class ComparisonAnchors(ContractBaseModel):
    schema_version: str = "comparison_anchors.v1"
    session_id: str = ""
    source_name: str = ""
    input_type: str = ""
    target_name: str = ""
    target_kind: TargetKind = TargetKind.classification
    optimization_direction: OptimizationDirection = OptimizationDirection.classify
    measurement_column: str = ""
    label_column: str = ""
    measurement_unit: str = ""
    dataset_type: DatasetType = DatasetType.structure_only
    mapping_confidence: MappingConfidence = MappingConfidence.low
    column_mapping: dict[str, str] = Field(default_factory=dict)
    label_source: str = ""
    decision_intent: DecisionIntent | None = None
    modeling_mode: ModelingMode | None = None
    scoring_mode: str = ""
    selected_model_name: str = ""
    training_scope: str = ""
    target_contract_version: str = ""
    model_contract_version: str = ""
    scoring_policy_version: str = ""
    explanation_contract_version: str = ""
    run_contract_version: str = ""
    fallback_reason: str = ""
    comparison_ready: bool = False

    @validator(
        "session_id",
        "source_name",
        "input_type",
        "target_name",
        "measurement_column",
        "label_column",
        "measurement_unit",
        "label_source",
        "scoring_mode",
        "selected_model_name",
        "training_scope",
        "target_contract_version",
        "model_contract_version",
        "scoring_policy_version",
        "explanation_contract_version",
        "run_contract_version",
        "fallback_reason",
        pre=True,
        always=True,
    )
    def _clean_comparison_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("target_kind", pre=True)
    def _clean_comparison_target_kind(cls, value: Any) -> str:
        return _clean_text(value, default=TargetKind.classification.value).lower()

    @validator("optimization_direction", pre=True)
    def _clean_comparison_direction(cls, value: Any) -> str:
        return _clean_text(value, default=OptimizationDirection.classify.value).lower()

    @validator("dataset_type", pre=True)
    def _clean_comparison_dataset_type(cls, value: Any) -> str:
        return _clean_text(value, default=DatasetType.structure_only.value).lower()

    @validator("mapping_confidence", pre=True)
    def _clean_comparison_mapping_confidence(cls, value: Any) -> str:
        return _clean_text(value, default=MappingConfidence.low.value).lower()

    @validator("decision_intent", pre=True)
    def _clean_comparison_intent(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("modeling_mode", pre=True)
    def _clean_comparison_mode(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("column_mapping", pre=True)
    def _clean_comparison_mapping(cls, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        payload: dict[str, str] = {}
        for key, item in value.items():
            cleaned_key = _clean_text(key)
            cleaned_value = _clean_text(item)
            if cleaned_key and cleaned_value:
                payload[cleaned_key] = cleaned_value
        return payload


class EvidenceRecord(ContractBaseModel):
    name: str
    evidence_type: EvidenceType
    truth_status: EvidenceTruthStatus
    source: str = ""
    scope: EvidenceScope = EvidenceScope.session_summary
    support_level: EvidenceSupportLevel = EvidenceSupportLevel.contextual
    current_use: EvidenceUse = EvidenceUse.interpretation_only
    future_use: EvidenceFutureUse = EvidenceFutureUse.none
    active_in_live_pipeline: bool = False
    summary: str = ""

    @validator("name", "source", "summary", pre=True, always=True)
    def _clean_evidence_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("evidence_type", "truth_status", "scope", "support_level", "current_use", "future_use", pre=True)
    def _clean_evidence_tokens(cls, value: Any) -> str:
        return _clean_text(value).lower()


class EvidenceLoopSummary(ContractBaseModel):
    schema_version: str = "evidence_loop.v1"
    summary: str = ""
    learning_boundary_note: str = ""
    activation_boundary_summary: str = ""
    active_modeling_evidence: list[str] = Field(default_factory=list)
    active_ranking_evidence: list[str] = Field(default_factory=list)
    interpretation_only_evidence: list[str] = Field(default_factory=list)
    memory_only_evidence: list[str] = Field(default_factory=list)
    stored_not_active_evidence: list[str] = Field(default_factory=list)
    future_activation_candidates: list[str] = Field(default_factory=list)

    @validator("summary", "learning_boundary_note", "activation_boundary_summary", pre=True, always=True)
    def _clean_loop_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator(
        "active_modeling_evidence",
        "active_ranking_evidence",
        "interpretation_only_evidence",
        "memory_only_evidence",
        "stored_not_active_evidence",
        "future_activation_candidates",
        pre=True,
    )
    def _clean_loop_lists(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _clean_text(item)]


class EvidenceActivationRule(ContractBaseModel):
    evidence_type: EvidenceType
    name: str = ""
    model_training_allowed: bool = False
    ranking_context_allowed: bool = False
    interpretation_allowed: bool = False
    comparison_allowed: bool = False
    future_learning_eligible: bool = False
    eligible_for_recommendation_reuse: bool = False
    eligible_for_ranking_context: bool = False
    eligible_for_future_learning: bool = False
    requires_stronger_validation: bool = False
    memory_only: bool = False
    stored_only: bool = False
    permanently_non_active: bool = False
    currently_active: bool = False
    ineligibility_reason: str = ""
    activation_summary: str = ""
    eligibility_summary: str = ""

    @validator("evidence_type", pre=True)
    def _clean_activation_evidence_type(cls, value: Any) -> str:
        return _clean_text(value).lower()

    @validator("name", "ineligibility_reason", "activation_summary", "eligibility_summary", pre=True, always=True)
    def _clean_activation_rule_text(cls, value: Any) -> str:
        return _clean_text(value)


class EvidenceActivationPolicy(ContractBaseModel):
    schema_version: str = "evidence_activation_policy.v2"
    summary: str = ""
    ranking_context_summary: str = ""
    interpretation_summary: str = ""
    learning_eligibility_summary: str = ""
    recommendation_reuse_summary: str = ""
    future_ranking_context_summary: str = ""
    future_learning_eligibility_summary: str = ""
    stored_only_summary: str = ""
    permanently_non_active_summary: str = ""
    rules: list[EvidenceActivationRule] = Field(default_factory=list)

    @validator(
        "summary",
        "ranking_context_summary",
        "interpretation_summary",
        "learning_eligibility_summary",
        "recommendation_reuse_summary",
        "future_ranking_context_summary",
        "future_learning_eligibility_summary",
        "stored_only_summary",
        "permanently_non_active_summary",
        pre=True,
        always=True,
    )
    def _clean_activation_policy_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("rules", pre=True)
    def _clean_activation_policy_rules(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []


class ControlledReuseState(ContractBaseModel):
    schema_version: str = "controlled_reuse.v1"
    recommendation_reuse_active: bool = False
    ranking_context_reuse_active: bool = False
    interpretation_support_active: bool = False
    reused_evidence: list[str] = Field(default_factory=list)
    support_carriers: list[str] = Field(default_factory=list)
    recommendation_reuse_summary: str = ""
    ranking_context_reuse_summary: str = ""
    interpretation_support_summary: str = ""
    inactive_boundary_summary: str = ""

    @validator(
        "recommendation_reuse_summary",
        "ranking_context_reuse_summary",
        "interpretation_support_summary",
        "inactive_boundary_summary",
        pre=True,
        always=True,
    )
    def _clean_controlled_reuse_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("reused_evidence", "support_carriers", pre=True)
    def _clean_controlled_reuse_lists(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _clean_text(item)]


class ClaimRecord(ContractBaseModel):
    schema_version: str = "claim.v1"
    claim_id: str
    workspace_id: str = ""
    session_id: str
    candidate_id: str
    candidate_reference: dict[str, Any] = Field(default_factory=dict)
    target_definition_snapshot: TargetDefinition | None = None
    claim_type: ClaimType = ClaimType.recommendation_assertion
    claim_text: str
    bounded_scope: str
    support_level: EvidenceSupportLevel = EvidenceSupportLevel.limited
    evidence_basis_summary: str = ""
    source_recommendation_rank: int = Field(default=0, ge=0)
    status: ClaimStatus = ClaimStatus.proposed
    created_at: datetime
    updated_at: datetime
    created_by: str = "system"
    created_by_user_id: str = ""
    reviewed_at: datetime | None = None
    reviewed_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator(
        "claim_id",
        "workspace_id",
        "session_id",
        "candidate_id",
        "claim_text",
        "bounded_scope",
        "evidence_basis_summary",
        "created_by",
        "created_by_user_id",
        "reviewed_by",
        pre=True,
        always=True,
    )
    def _clean_claim_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("claim_type", pre=True)
    def _clean_claim_type(cls, value: Any) -> str:
        return _clean_text(value, default=ClaimType.recommendation_assertion.value).lower()

    @validator("support_level", pre=True)
    def _clean_claim_support_level(cls, value: Any) -> str:
        return _clean_text(value, default=EvidenceSupportLevel.limited.value).lower()

    @validator("status", pre=True)
    def _clean_claim_status(cls, value: Any) -> str:
        return _clean_text(value, default=ClaimStatus.proposed.value).lower()

    @validator("created_at", "updated_at", "reviewed_at", pre=True)
    def _coerce_claim_datetime(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _coerce_datetime(value)

    @validator("candidate_reference", "metadata", pre=True)
    def _clean_claim_maps(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class ClaimReference(ContractBaseModel):
    claim_id: str
    candidate_id: str
    candidate_label: str = ""
    claim_type: ClaimType = ClaimType.recommendation_assertion
    claim_text: str
    support_level: EvidenceSupportLevel = EvidenceSupportLevel.limited
    status: ClaimStatus = ClaimStatus.proposed
    source_recommendation_rank: int = Field(default=0, ge=0)
    created_at: datetime | None = None

    @validator("claim_id", "candidate_id", "candidate_label", "claim_text", pre=True, always=True)
    def _clean_claim_ref_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("claim_type", pre=True)
    def _clean_claim_ref_type(cls, value: Any) -> str:
        return _clean_text(value, default=ClaimType.recommendation_assertion.value).lower()

    @validator("support_level", pre=True)
    def _clean_claim_ref_support(cls, value: Any) -> str:
        return _clean_text(value, default=EvidenceSupportLevel.limited.value).lower()

    @validator("status", pre=True)
    def _clean_claim_ref_status(cls, value: Any) -> str:
        return _clean_text(value, default=ClaimStatus.proposed.value).lower()

    @validator("created_at", pre=True)
    def _coerce_claim_ref_datetime(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _coerce_datetime(value)


class ClaimsSummary(ContractBaseModel):
    claim_count: int = Field(default=0, ge=0)
    proposed_count: int = Field(default=0, ge=0)
    accepted_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    superseded_count: int = Field(default=0, ge=0)
    summary_text: str = ""
    top_claims: list[ClaimReference] = Field(default_factory=list)

    @validator("summary_text", pre=True, always=True)
    def _clean_claim_summary_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("top_claims", pre=True)
    def _clean_top_claims(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []


class ExperimentRequestRecord(ContractBaseModel):
    schema_version: str = "experiment_request.v1"
    experiment_request_id: str
    workspace_id: str = ""
    session_id: str
    claim_id: str
    candidate_id: str
    candidate_reference: dict[str, Any] = Field(default_factory=dict)
    target_definition_snapshot: TargetDefinition | None = None
    requested_measurement: str
    requested_direction: str = ""
    rationale_summary: str
    priority_tier: PriorityTier = PriorityTier.medium
    status: ExperimentRequestStatus = ExperimentRequestStatus.proposed
    requested_at: datetime
    requested_by: str = "system"
    requested_by_user_id: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator(
        "experiment_request_id",
        "workspace_id",
        "session_id",
        "claim_id",
        "candidate_id",
        "requested_measurement",
        "requested_direction",
        "rationale_summary",
        "requested_by",
        "requested_by_user_id",
        "notes",
        pre=True,
        always=True,
    )
    def _clean_experiment_request_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("priority_tier", pre=True)
    def _clean_experiment_request_priority(cls, value: Any) -> str:
        return _clean_text(value, default=PriorityTier.medium.value).lower()

    @validator("status", pre=True)
    def _clean_experiment_request_status(cls, value: Any) -> str:
        return _clean_text(value, default=ExperimentRequestStatus.proposed.value).lower()

    @validator("requested_at", pre=True)
    def _coerce_experiment_request_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()

    @validator("candidate_reference", "metadata", pre=True)
    def _clean_experiment_request_maps(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class ExperimentRequestReference(ContractBaseModel):
    experiment_request_id: str
    claim_id: str
    candidate_id: str
    candidate_label: str = ""
    requested_measurement: str = ""
    requested_direction: str = ""
    priority_tier: PriorityTier = PriorityTier.medium
    status: ExperimentRequestStatus = ExperimentRequestStatus.proposed
    requested_at: datetime | None = None

    @validator(
        "experiment_request_id",
        "claim_id",
        "candidate_id",
        "candidate_label",
        "requested_measurement",
        "requested_direction",
        pre=True,
        always=True,
    )
    def _clean_experiment_request_ref_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("priority_tier", pre=True)
    def _clean_experiment_request_ref_priority(cls, value: Any) -> str:
        return _clean_text(value, default=PriorityTier.medium.value).lower()

    @validator("status", pre=True)
    def _clean_experiment_request_ref_status(cls, value: Any) -> str:
        return _clean_text(value, default=ExperimentRequestStatus.proposed.value).lower()

    @validator("requested_at", pre=True)
    def _coerce_experiment_request_ref_datetime(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _coerce_datetime(value)


class ExperimentRequestSummary(ContractBaseModel):
    request_count: int = Field(default=0, ge=0)
    proposed_count: int = Field(default=0, ge=0)
    accepted_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    completed_count: int = Field(default=0, ge=0)
    superseded_count: int = Field(default=0, ge=0)
    summary_text: str = ""
    top_requests: list[ExperimentRequestReference] = Field(default_factory=list)

    @validator("summary_text", pre=True, always=True)
    def _clean_experiment_request_summary_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("top_requests", pre=True)
    def _clean_top_requests(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []


class ExperimentResultRecord(ContractBaseModel):
    schema_version: str = "experiment_result.v1"
    experiment_result_id: str
    workspace_id: str = ""
    session_id: str
    source_experiment_request_id: str = ""
    source_claim_id: str = ""
    candidate_id: str
    candidate_reference: dict[str, Any] = Field(default_factory=dict)
    target_definition_snapshot: TargetDefinition | None = None
    observed_value: float | None = None
    observed_label: str = ""
    measurement_unit: str = ""
    assay_context: str = ""
    result_quality: ExperimentResultQuality = ExperimentResultQuality.provisional
    result_source: ExperimentResultSource = ExperimentResultSource.manual_entry
    ingested_at: datetime
    ingested_by: str = ""
    ingested_by_user_id: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator(
        "experiment_result_id",
        "workspace_id",
        "session_id",
        "source_experiment_request_id",
        "source_claim_id",
        "candidate_id",
        "observed_label",
        "measurement_unit",
        "assay_context",
        "ingested_by",
        "ingested_by_user_id",
        "notes",
        pre=True,
        always=True,
    )
    def _clean_experiment_result_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("result_quality", pre=True)
    def _clean_experiment_result_quality(cls, value: Any) -> str:
        return _clean_text(value, default=ExperimentResultQuality.provisional.value).lower()

    @validator("result_source", pre=True)
    def _clean_experiment_result_source(cls, value: Any) -> str:
        return _clean_text(value, default=ExperimentResultSource.manual_entry.value).lower()

    @validator("observed_value", pre=True)
    def _coerce_experiment_result_value(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @validator("ingested_at", pre=True)
    def _coerce_experiment_result_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()

    @validator("candidate_reference", "metadata", pre=True)
    def _clean_experiment_result_maps(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class ExperimentResultReference(ContractBaseModel):
    experiment_result_id: str
    source_experiment_request_id: str = ""
    source_claim_id: str = ""
    candidate_id: str
    candidate_label: str = ""
    observed_value: float | None = None
    observed_label: str = ""
    measurement_unit: str = ""
    result_quality: ExperimentResultQuality = ExperimentResultQuality.provisional
    result_source: ExperimentResultSource = ExperimentResultSource.manual_entry
    ingested_at: datetime | None = None

    @validator(
        "experiment_result_id",
        "source_experiment_request_id",
        "source_claim_id",
        "candidate_id",
        "candidate_label",
        "observed_label",
        "measurement_unit",
        pre=True,
        always=True,
    )
    def _clean_experiment_result_ref_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("result_quality", pre=True)
    def _clean_experiment_result_ref_quality(cls, value: Any) -> str:
        return _clean_text(value, default=ExperimentResultQuality.provisional.value).lower()

    @validator("result_source", pre=True)
    def _clean_experiment_result_ref_source(cls, value: Any) -> str:
        return _clean_text(value, default=ExperimentResultSource.manual_entry.value).lower()

    @validator("observed_value", pre=True)
    def _coerce_experiment_result_ref_value(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @validator("ingested_at", pre=True)
    def _coerce_experiment_result_ref_datetime(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _coerce_datetime(value)


class ExperimentResultSummary(ContractBaseModel):
    result_count: int = Field(default=0, ge=0)
    recorded_count: int = Field(default=0, ge=0)
    with_numeric_value_count: int = Field(default=0, ge=0)
    with_label_count: int = Field(default=0, ge=0)
    summary_text: str = ""
    top_results: list[ExperimentResultReference] = Field(default_factory=list)

    @validator("summary_text", pre=True, always=True)
    def _clean_experiment_result_summary_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("top_results", pre=True)
    def _clean_top_results(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []


class BeliefUpdateRecord(ContractBaseModel):
    schema_version: str = "belief_update.v1"
    belief_update_id: str
    workspace_id: str = ""
    session_id: str
    claim_id: str
    experiment_result_id: str = ""
    candidate_id: str = ""
    candidate_label: str = ""
    previous_support_level: EvidenceSupportLevel = EvidenceSupportLevel.limited
    updated_support_level: EvidenceSupportLevel = EvidenceSupportLevel.limited
    update_direction: BeliefUpdateDirection = BeliefUpdateDirection.unresolved
    update_reason: str = ""
    governance_status: BeliefUpdateGovernanceStatus = BeliefUpdateGovernanceStatus.proposed
    created_at: datetime
    created_by: str = ""
    created_by_user_id: str = ""
    reviewed_at: datetime | None = None
    reviewed_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator(
        "belief_update_id",
        "workspace_id",
        "session_id",
        "claim_id",
        "experiment_result_id",
        "candidate_id",
        "candidate_label",
        "update_reason",
        "created_by",
        "created_by_user_id",
        "reviewed_by",
        pre=True,
        always=True,
    )
    def _clean_belief_update_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("previous_support_level", "updated_support_level", pre=True)
    def _clean_belief_update_support_levels(cls, value: Any) -> str:
        return _clean_text(value, default=EvidenceSupportLevel.limited.value).lower()

    @validator("update_direction", pre=True)
    def _clean_belief_update_direction(cls, value: Any) -> str:
        return _clean_text(value, default=BeliefUpdateDirection.unresolved.value).lower()

    @validator("governance_status", pre=True)
    def _clean_belief_update_governance(cls, value: Any) -> str:
        return _clean_text(value, default=BeliefUpdateGovernanceStatus.proposed.value).lower()

    @validator("created_at", "reviewed_at", pre=True)
    def _coerce_belief_update_datetime(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _coerce_datetime(value)

    @validator("metadata", pre=True)
    def _clean_belief_update_maps(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class BeliefUpdateReference(ContractBaseModel):
    belief_update_id: str
    claim_id: str
    experiment_result_id: str = ""
    candidate_id: str = ""
    candidate_label: str = ""
    previous_support_level: EvidenceSupportLevel = EvidenceSupportLevel.limited
    updated_support_level: EvidenceSupportLevel = EvidenceSupportLevel.limited
    update_direction: BeliefUpdateDirection = BeliefUpdateDirection.unresolved
    governance_status: BeliefUpdateGovernanceStatus = BeliefUpdateGovernanceStatus.proposed
    created_at: datetime | None = None

    @validator(
        "belief_update_id",
        "claim_id",
        "experiment_result_id",
        "candidate_id",
        "candidate_label",
        pre=True,
        always=True,
    )
    def _clean_belief_update_ref_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("previous_support_level", "updated_support_level", pre=True)
    def _clean_belief_update_ref_support_levels(cls, value: Any) -> str:
        return _clean_text(value, default=EvidenceSupportLevel.limited.value).lower()

    @validator("update_direction", pre=True)
    def _clean_belief_update_ref_direction(cls, value: Any) -> str:
        return _clean_text(value, default=BeliefUpdateDirection.unresolved.value).lower()

    @validator("governance_status", pre=True)
    def _clean_belief_update_ref_governance(cls, value: Any) -> str:
        return _clean_text(value, default=BeliefUpdateGovernanceStatus.proposed.value).lower()

    @validator("created_at", pre=True)
    def _coerce_belief_update_ref_datetime(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _coerce_datetime(value)


class BeliefUpdateSummary(ContractBaseModel):
    update_count: int = Field(default=0, ge=0)
    proposed_count: int = Field(default=0, ge=0)
    accepted_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    superseded_count: int = Field(default=0, ge=0)
    strengthened_count: int = Field(default=0, ge=0)
    weakened_count: int = Field(default=0, ge=0)
    unresolved_count: int = Field(default=0, ge=0)
    summary_text: str = ""
    top_updates: list[BeliefUpdateReference] = Field(default_factory=list)

    @validator("summary_text", pre=True, always=True)
    def _clean_belief_update_summary_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("top_updates", pre=True)
    def _clean_top_belief_updates(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []


class BeliefStateRecord(ContractBaseModel):
    schema_version: str = "belief_state.v1"
    belief_state_id: str
    workspace_id: str = ""
    target_key: str
    target_definition_snapshot: TargetDefinition | None = None
    summary_text: str = ""
    active_claim_count: int = Field(default=0, ge=0)
    supported_claim_count: int = Field(default=0, ge=0)
    weakened_claim_count: int = Field(default=0, ge=0)
    unresolved_claim_count: int = Field(default=0, ge=0)
    last_updated_at: datetime
    last_update_source: str = ""
    version: int = Field(default=1, ge=1)
    latest_belief_update_refs: list[BeliefUpdateReference] = Field(default_factory=list)
    support_distribution_summary: str = ""
    governance_scope_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator(
        "belief_state_id",
        "workspace_id",
        "target_key",
        "summary_text",
        "last_update_source",
        "support_distribution_summary",
        "governance_scope_summary",
        pre=True,
        always=True,
    )
    def _clean_belief_state_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("last_updated_at", pre=True)
    def _coerce_belief_state_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()

    @validator("latest_belief_update_refs", pre=True)
    def _clean_belief_state_refs(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []

    @validator("metadata", pre=True)
    def _clean_belief_state_maps(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class BeliefStateReference(ContractBaseModel):
    belief_state_id: str
    target_key: str
    summary_text: str = ""
    active_claim_count: int = Field(default=0, ge=0)
    supported_claim_count: int = Field(default=0, ge=0)
    weakened_claim_count: int = Field(default=0, ge=0)
    unresolved_claim_count: int = Field(default=0, ge=0)
    last_updated_at: datetime | None = None
    last_update_source: str = ""
    version: int = Field(default=1, ge=1)

    @validator(
        "belief_state_id",
        "target_key",
        "summary_text",
        "last_update_source",
        pre=True,
        always=True,
    )
    def _clean_belief_state_ref_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("last_updated_at", pre=True)
    def _coerce_belief_state_ref_datetime(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _coerce_datetime(value)


class BeliefStateSummary(ContractBaseModel):
    summary_text: str = ""
    support_distribution_summary: str = ""
    governance_scope_summary: str = ""
    active_claim_count: int = Field(default=0, ge=0)
    supported_claim_count: int = Field(default=0, ge=0)
    weakened_claim_count: int = Field(default=0, ge=0)
    unresolved_claim_count: int = Field(default=0, ge=0)
    last_updated_at: datetime | None = None
    last_update_source: str = ""

    @validator(
        "summary_text",
        "support_distribution_summary",
        "governance_scope_summary",
        "last_update_source",
        pre=True,
        always=True,
    )
    def _clean_belief_state_summary_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("last_updated_at", pre=True)
    def _coerce_belief_state_summary_datetime(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _coerce_datetime(value)


class ScientificSessionTruth(ContractBaseModel):
    schema_version: str = "scientific_session_truth.v1"
    session_id: str
    workspace_id: str = ""
    source_name: str = ""
    generated_at: datetime
    session_identity: SessionIdentity | None = None
    target_definition: TargetDefinition | None = None
    decision_intent: DecisionIntent | None = None
    modeling_mode: ModelingMode | None = None
    run_contract: RunContract | None = None
    comparison_anchors: ComparisonAnchors | None = None
    evidence_records: list[EvidenceRecord] = Field(default_factory=list)
    evidence_loop: EvidenceLoopSummary | None = None
    evidence_activation_policy: EvidenceActivationPolicy | None = None
    controlled_reuse: ControlledReuseState | None = None
    claim_refs: list[ClaimReference] = Field(default_factory=list)
    claims_summary: ClaimsSummary | None = None
    experiment_request_refs: list[ExperimentRequestReference] = Field(default_factory=list)
    experiment_request_summary: ExperimentRequestSummary | None = None
    experiment_result_refs: list[ExperimentResultReference] = Field(default_factory=list)
    linked_result_summary: ExperimentResultSummary | None = None
    belief_update_refs: list[BeliefUpdateReference] = Field(default_factory=list)
    belief_update_summary: BeliefUpdateSummary | None = None
    belief_state_ref: BeliefStateReference | None = None
    belief_state_summary: BeliefStateSummary | None = None
    bridge_state_notes: list[str] = Field(default_factory=list)
    core_outputs: dict[str, Any] = Field(default_factory=dict)
    decision_policy_summary: dict[str, Any] = Field(default_factory=dict)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    comparison_ready: bool = False
    contract_versions: dict[str, str] = Field(default_factory=dict)

    @validator("session_id", "workspace_id", "source_name", pre=True, always=True)
    def _clean_scientific_truth_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("generated_at", pre=True)
    def _coerce_scientific_truth_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()

    @validator("decision_intent", "modeling_mode", pre=True)
    def _clean_scientific_truth_tokens(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("bridge_state_notes", pre=True)
    def _clean_bridge_state_notes(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _clean_text(item)]

    @validator("claim_refs", pre=True)
    def _clean_claim_refs(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []

    @validator("experiment_request_refs", pre=True)
    def _clean_experiment_request_refs(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []

    @validator("experiment_result_refs", pre=True)
    def _clean_experiment_result_refs(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []

    @validator("belief_update_refs", pre=True)
    def _clean_belief_update_refs(cls, value: Any) -> list[dict[str, Any]]:
        return value if isinstance(value, list) else []

    @validator("core_outputs", "decision_policy_summary", "review_summary", "contract_versions", pre=True)
    def _clean_scientific_truth_maps(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class ApplicabilityDomainAssessment(ContractBaseModel):
    status: DomainStatus = DomainStatus.unknown
    max_reference_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    support_band: str = ""
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)

    @validator("status", pre=True)
    def _clean_domain_status(cls, value: Any) -> str:
        return _clean_text(value, default=DomainStatus.unknown.value).lower()

    @validator("support_band", "summary", pre=True, always=True)
    def _clean_domain_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("max_reference_similarity", pre=True)
    def _coerce_similarity(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @validator("evidence", pre=True)
    def _coerce_domain_evidence(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _clean_text(item)]


class NoveltySignal(ContractBaseModel):
    novelty_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reference_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    batch_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    summary: str = ""

    @validator("novelty_score", "reference_similarity", "batch_similarity", pre=True)
    def _coerce_novelty_float(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @validator("summary", pre=True, always=True)
    def _clean_novelty_summary(cls, value: Any) -> str:
        return _clean_text(value)


class ModelJudgment(ContractBaseModel):
    target_kind: TargetKind = TargetKind.classification
    predicted_label: int | None = None
    positive_class_name: str = ""
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty_kind: str = ""
    predicted_value: float | None = None
    prediction_dispersion: float | None = Field(default=None, ge=0.0)
    model_summary: str = ""

    @validator("target_kind", pre=True)
    def _clean_model_target_kind(cls, value: Any) -> str:
        return _clean_text(value, default=TargetKind.classification.value).lower()

    @validator("positive_class_name", "uncertainty_kind", "model_summary", pre=True, always=True)
    def _clean_model_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("confidence", "uncertainty", "predicted_value", "prediction_dispersion", pre=True)
    def _coerce_model_float(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class ScientificDataFacts(ContractBaseModel):
    observed_value: float | None = None
    measurement_column: str = ""
    label_column: str = ""
    dataset_type: DatasetType | None = None
    assay: str = ""
    target: str = ""
    source_name: str = ""

    @validator("observed_value", pre=True)
    def _coerce_observed_value(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @validator("measurement_column", "label_column", "assay", "target", "source_name", pre=True, always=True)
    def _clean_data_fact_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("dataset_type", pre=True)
    def _clean_data_dataset_type(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()


class DecisionPolicyTrace(ContractBaseModel):
    bucket: Bucket | None = None
    priority_score: float | None = Field(default=None, ge=0.0, le=1.0)
    acquisition_score: float | None = Field(default=None, ge=0.0, le=1.0)
    experiment_value: float | None = Field(default=None, ge=0.0, le=1.0)
    selection_reason: str = ""
    policy_summary: str = ""

    @validator("bucket", pre=True)
    def _clean_policy_bucket(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _normalize_bucket(value)

    @validator("priority_score", "acquisition_score", "experiment_value", pre=True)
    def _coerce_policy_float(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @validator("selection_reason", "policy_summary", pre=True, always=True)
    def _clean_policy_text(cls, value: Any) -> str:
        return _clean_text(value)


class ScientificRecommendation(ContractBaseModel):
    recommended_action: str = ""
    summary: str = ""
    follow_up_experiment: str = ""
    trust_cautions: list[str] = Field(default_factory=list)

    @validator("recommended_action", "summary", "follow_up_experiment", pre=True, always=True)
    def _clean_recommendation_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("trust_cautions", pre=True)
    def _coerce_recommendation_cautions(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _clean_text(item)]


class NormalizedExplanation(ContractBaseModel):
    why_this_candidate: str = ""
    why_now: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    model_judgment_summary: str = ""
    uncertainty_summary: str = ""
    novelty_summary: str = ""
    decision_policy_reason: str = ""
    recommended_followup: str = ""
    trust_cautions: list[str] = Field(default_factory=list)

    @validator(
        "why_this_candidate",
        "why_now",
        "model_judgment_summary",
        "uncertainty_summary",
        "novelty_summary",
        "decision_policy_reason",
        "recommended_followup",
        pre=True,
        always=True,
    )
    def _clean_normalized_explanation_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("supporting_evidence", "trust_cautions", pre=True)
    def _coerce_explanation_lists(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _clean_text(item)]


class UploadInspectionResult(ContractBaseModel):
    schema_version: str = "upload_inspection.v1"
    session_id: str
    created_at: datetime
    filename: str
    input_type: str
    file_type: str = ""
    semantic_mode: str = ""
    columns: list[str]
    preview_rows: list[dict[str, str]] = Field(default_factory=list)
    inferred_mapping: dict[str, str | None]
    semantic_roles: dict[str, str | None] = Field(default_factory=dict)
    selected_mapping: dict[str, str | None] = Field(default_factory=dict)
    measurement_columns: list[str] = Field(default_factory=list)
    label_builder_suggestion: LabelBuilderConfig = Field(default_factory=LabelBuilderConfig)
    label_builder_config: LabelBuilderConfig = Field(default_factory=LabelBuilderConfig)
    validation_summary: ValidationStats
    target_definition: TargetDefinition | None = None
    decision_intent: DecisionIntent | None = None
    comparison_anchors: ComparisonAnchors | None = None
    contract_versions: dict[str, str] = Field(default_factory=dict)
    free_tier_assessment: dict[str, Any] = Field(default_factory=dict)

    @validator("filename", "input_type", "session_id", "file_type", "semantic_mode", pre=True)
    def _strip_required_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("decision_intent", pre=True)
    def _clean_inspection_decision_intent(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()


class SessionMetadata(ContractBaseModel):
    schema_version: str = "session_metadata.v1"
    session_id: str
    workspace_id: str = ""
    created_by_user_id: str = ""
    created_at: datetime
    updated_at: datetime
    source_name: str = ""
    input_type: str = ""
    latest_job_id: str = ""
    upload_metadata: dict[str, Any] = Field(default_factory=dict)
    summary_metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("session_id", "workspace_id", "created_by_user_id", "source_name", "input_type", "latest_job_id", pre=True, always=True)
    def _clean_session_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("created_at", "updated_at", pre=True)
    def _coerce_session_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()


class UserRecord(ContractBaseModel):
    schema_version: str = "user_record.v1"
    user_id: str
    email: str
    display_name: str = ""
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    @validator("user_id", "display_name", pre=True, always=True)
    def _clean_user_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("email", pre=True)
    def _clean_user_email(cls, value: Any) -> str:
        return _clean_text(value).lower()

    @validator("created_at", "updated_at", pre=True)
    def _coerce_user_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()


class WorkspaceRecord(ContractBaseModel):
    schema_version: str = "workspace_record.v1"
    workspace_id: str
    name: str
    owner_user_id: str = ""
    plan_tier: WorkspacePlanTier = WorkspacePlanTier.free
    plan_status: WorkspacePlanStatus = WorkspacePlanStatus.active
    trial_ends_at: datetime | None = None
    current_period_ends_at: datetime | None = None
    external_billing_provider: str = ""
    external_customer_ref: str = ""
    external_subscription_ref: str = ""
    external_price_ref: str = ""
    provider_subscription_status: str = ""
    billing_synced_at: datetime | None = None
    billing_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @validator(
        "workspace_id",
        "name",
        "owner_user_id",
        "external_billing_provider",
        "external_customer_ref",
        "external_subscription_ref",
        "external_price_ref",
        "provider_subscription_status",
        pre=True,
        always=True,
    )
    def _clean_workspace_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("plan_tier", pre=True)
    def _clean_workspace_plan_tier(cls, value: Any) -> str:
        return _clean_text(value, default=WorkspacePlanTier.free.value).lower()

    @validator("plan_status", pre=True)
    def _clean_workspace_plan_status(cls, value: Any) -> str:
        return _clean_text(value, default=WorkspacePlanStatus.active.value).lower()

    @validator("created_at", "updated_at", pre=True)
    def _coerce_workspace_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()

    @validator("trial_ends_at", "current_period_ends_at", "billing_synced_at", pre=True)
    def _coerce_workspace_optional_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value)


class WorkspaceUsageEventRecord(ContractBaseModel):
    schema_version: str = "workspace_usage_event.v1"
    workspace_id: str
    event_type: WorkspaceUsageEventType
    quantity: int = Field(default=1, ge=0)
    created_at: datetime
    session_id: str = ""
    job_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("workspace_id", "session_id", "job_id", pre=True, always=True)
    def _clean_usage_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("event_type", pre=True)
    def _clean_usage_event_type(cls, value: Any) -> str:
        return _clean_text(value).lower()

    @validator("created_at", pre=True)
    def _coerce_usage_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()


class WorkspaceMembershipRecord(ContractBaseModel):
    schema_version: str = "workspace_membership.v1"
    workspace_id: str
    user_id: str
    role: WorkspaceRole
    created_at: datetime
    updated_at: datetime

    @validator("workspace_id", "user_id", pre=True, always=True)
    def _clean_membership_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("role", pre=True)
    def _clean_membership_role(cls, value: Any) -> str:
        return _clean_text(value).lower()

    @validator("created_at", "updated_at", pre=True)
    def _coerce_membership_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()


class ArtifactPointer(ContractBaseModel):
    schema_version: str = "artifact_pointer.v1"
    session_id: str = ""
    job_id: str = ""
    workspace_id: str = ""
    created_by_user_id: str = ""
    artifact_type: str
    path: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("session_id", "job_id", "workspace_id", "created_by_user_id", "artifact_type", "path", pre=True, always=True)
    def _clean_artifact_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("created_at", "updated_at", pre=True)
    def _coerce_artifact_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()


class NormalizedDatasetSummary(ContractBaseModel):
    schema_version: str = "normalized_dataset_summary.v1"
    session_id: str | None = None
    source_name: str | None = None
    total_rows: int = Field(ge=0)
    analyzed_rows: int = Field(ge=0)
    row_count_before: int = Field(ge=0)
    row_count_after: int = Field(ge=0)
    valid_smiles_count: int = Field(ge=0)
    invalid_smiles_count: int = Field(ge=0)
    canonicalized_rows: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    duplicate_removed_count: int = Field(ge=0)
    rows_with_labels: int = Field(ge=0)
    rows_without_labels: int = Field(ge=0)
    rows_with_values: int = Field(default=0, ge=0)
    rows_without_values: int = Field(default=0, ge=0)
    value_column: str = ""
    semantic_mode: str = ""
    label_source: str = ""
    file_type: str = ""
    usable_label_count: int = Field(ge=0)
    positive_label_count: int = Field(default=0, ge=0)
    negative_label_count: int = Field(default=0, ge=0)
    unlabeled_label_count: int = Field(default=0, ge=0)
    label_counts: LabelCounts = Field(default_factory=LabelCounts)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    can_run_analysis: bool
    target_definition: TargetDefinition | None = None
    contract_versions: dict[str, str] = Field(default_factory=dict)

    @root_validator(pre=False)
    def _sync_counts(cls, values: dict[str, Any]) -> dict[str, Any]:
        total_rows = _int_or_default(values.get("total_rows", 0), 0)
        rows_with_values = _int_or_default(values.get("rows_with_values", 0), 0)
        values["rows_with_values"] = rows_with_values
        values["rows_without_values"] = _int_or_default(
            values.get("rows_without_values", max(total_rows - rows_with_values, 0)),
            max(total_rows - rows_with_values, 0),
        )
        values["value_column"] = _clean_text(values.get("value_column"))
        values["semantic_mode"] = _clean_text(values.get("semantic_mode"))
        values["label_source"] = _clean_text(values.get("label_source"))
        values["file_type"] = _clean_text(values.get("file_type"))
        label_counts = values.get("label_counts")
        if not isinstance(label_counts, LabelCounts):
            label_counts = LabelCounts(
                positive=int(values.get("positive_label_count", 0)),
                negative=int(values.get("negative_label_count", 0)),
                unlabeled=int(values.get("unlabeled_label_count", values.get("rows_without_labels", 0))),
            )
        values["label_counts"] = label_counts
        return values


class BenchmarkModelResult(ContractBaseModel):
    name: str
    calibration_method: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class TrainingResult(ContractBaseModel):
    schema_version: str = "training_result.v1"
    model_family: str
    model_type: str = ""
    calibration_method: str
    training_scope: str = ""
    model_source: str = ""
    training_sample_size: int = Field(ge=0)
    class_balance: LabelCounts = Field(default_factory=LabelCounts)
    evaluation_metrics: dict[str, Any] = Field(default_factory=dict)
    regression_metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    diagnostic_flags: list[str] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(default_factory=dict)
    selected_model: dict[str, Any] = Field(default_factory=dict)
    target_definition: TargetDefinition | None = None
    contract_versions: dict[str, str] = Field(default_factory=dict)
    benchmark: list[BenchmarkModelResult] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)

    @root_validator(pre=False)
    def _sync_selected_model(cls, values: dict[str, Any]) -> dict[str, Any]:
        selected = dict(values.get("selected_model") or {})
        if not values.get("calibration_method"):
            values["calibration_method"] = _clean_text(selected.get("calibration_method"))
        if not values.get("model_family"):
            values["model_family"] = _infer_model_family(selected.get("name"), selected.get("name"))
        if not values.get("model_type"):
            values["model_type"] = _clean_text(values.get("model_type")) or "classification"
        if not values.get("evaluation_metrics"):
            values["evaluation_metrics"] = dict(values.get("metrics") or {})
        return values


class FeasibilityInfo(ContractBaseModel):
    is_feasible: bool | None = None
    reason: str = ""

    @validator("reason", pre=True, always=True)
    def _clean_reason(cls, value: Any) -> str:
        return _clean_text(value)


class ProvenanceInfo(ContractBaseModel):
    text: str
    source_name: str = ""
    source_type: str = ""
    parent_molecule: str = ""
    model_version: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("text", pre=True)
    def _coerce_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("source_name", "source_type", "parent_molecule", "model_version", pre=True, always=True)
    def _clean_provenance_text(cls, value: Any) -> str:
        return _clean_text(value)


class ModelMetadata(ContractBaseModel):
    version: str
    family: str = ""
    calibration_method: str = ""
    training_sample_size: int | None = Field(default=None, ge=0)
    class_balance: LabelCounts | None = None
    artifact_ref: str = ""

    @validator("version", pre=True)
    def _clean_version(cls, value: Any) -> str:
        return _clean_text(value, default="unknown")

    @validator("family", "calibration_method", "artifact_ref", pre=True, always=True)
    def _clean_metadata_text(cls, value: Any) -> str:
        return _clean_text(value)

    @root_validator(pre=False)
    def _default_family(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not values.get("family"):
            values["family"] = _infer_model_family(values.get("version", ""), values.get("version", ""))
        return values


class CandidatePredictionRow(ContractBaseModel):
    candidate_id: str
    smiles: str
    canonical_smiles: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty: float | None = Field(default=None, ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    predicted_value: float | None = None
    prediction_dispersion: float | None = Field(default=None, ge=0.0)
    feasibility: FeasibilityInfo = Field(default_factory=FeasibilityInfo)
    prediction_metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("candidate_id", "smiles", "canonical_smiles", pre=True)
    def _strip_prediction_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("confidence", "uncertainty", "predicted_value", "prediction_dispersion", pre=True)
    def _coerce_prediction_float(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class SelectionResultRow(ContractBaseModel):
    candidate_id: str
    smiles: str
    canonical_smiles: str
    acquisition_score: float = Field(ge=0.0, le=1.0)
    experiment_value: float = Field(ge=0.0, le=1.0)
    bucket: Bucket
    rank: int | None = Field(default=None, ge=1)
    selection_reason: str = ""
    portfolio_metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("candidate_id", "smiles", "canonical_smiles", "selection_reason", pre=True)
    def _strip_selection_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("bucket", pre=True)
    def _clean_bucket(cls, value: Any) -> str:
        return _normalize_bucket(value)


class ReviewEventRecord(ContractBaseModel):
    session_id: str
    workspace_id: str = ""
    candidate_id: str
    smiles: str
    action: str
    previous_status: ReviewStatus | None = None
    status: ReviewStatus
    note: str = ""
    timestamp: datetime
    reviewed_at: datetime
    actor: str = "unassigned"
    reviewer: str = "unassigned"
    actor_user_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("session_id", "workspace_id", "candidate_id", "smiles", "action", "note", "actor_user_id", pre=True, always=True)
    def _clean_review_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("actor", "reviewer", pre=True, always=True)
    def _clean_review_actor_text(cls, value: Any) -> str:
        return _clean_text(value, default="unassigned")

    @validator("status", "previous_status", pre=True)
    def _clean_review_status(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return _normalize_status(value)

    @validator("timestamp", "reviewed_at", pre=True)
    def _coerce_review_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()

    @root_validator(pre=False)
    def _sync_review_actor(cls, values: dict[str, Any]) -> dict[str, Any]:
        reviewer = _clean_text(values.get("reviewer"), default="unassigned")
        actor = _clean_text(values.get("actor"), default=reviewer or "unassigned")
        values["reviewer"] = reviewer or actor
        values["actor"] = actor or reviewer
        if values.get("reviewed_at") is None:
            values["reviewed_at"] = values.get("timestamp")
        if values.get("timestamp") is None:
            values["timestamp"] = values.get("reviewed_at")
        return values


class CandidateReviewSummary(ContractBaseModel):
    status: ReviewStatus
    note: str = ""
    actor: str = "unassigned"
    reviewer: str = "unassigned"
    reviewed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("status", pre=True)
    def _clean_summary_status(cls, value: Any) -> str:
        return _normalize_status(value)

    @validator("note", pre=True, always=True)
    def _clean_summary_note(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("actor", "reviewer", pre=True, always=True)
    def _clean_summary_actor_text(cls, value: Any) -> str:
        return _clean_text(value, default="unassigned")

    @validator("reviewed_at", pre=True)
    def _coerce_summary_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value)

    @root_validator(pre=False)
    def _sync_summary_names(cls, values: dict[str, Any]) -> dict[str, Any]:
        reviewer = _clean_text(values.get("reviewer"), default="unassigned")
        actor = _clean_text(values.get("actor"), default=reviewer or "unassigned")
        values["reviewer"] = reviewer or actor
        values["actor"] = actor or reviewer
        return values


class ScoreBreakdownItem(ContractBaseModel):
    key: str
    label: str
    raw_value: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    weight_percent: float = Field(ge=0.0, le=100.0)
    contribution: float = Field(ge=0.0, le=1.0)

    @validator("key", "label", pre=True, always=True)
    def _clean_breakdown_text(cls, value: Any) -> str:
        return _clean_text(value)


class CandidateRationale(ContractBaseModel):
    summary: str
    why_now: str = ""
    trust_label: str = ""
    trust_summary: str = ""
    recommended_action: str = ""
    primary_driver: str = ""
    session_context: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    evidence_lines: list[str] = Field(default_factory=list)

    @validator(
        "summary",
        "why_now",
        "trust_label",
        "trust_summary",
        "recommended_action",
        "primary_driver",
        pre=True,
        always=True,
    )
    def _clean_rationale_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("session_context", "strengths", "cautions", "evidence_lines", pre=True)
    def _coerce_rationale_lists(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _clean_text(item)]


class DecisionArtifactRow(ContractBaseModel):
    session_id: str
    rank: int = Field(ge=1)
    candidate_id: str
    smiles: str
    canonical_smiles: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty: float | None = Field(default=None, ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    acquisition_score: float = Field(ge=0.0, le=1.0)
    experiment_value: float = Field(ge=0.0, le=1.0)
    bucket: Bucket
    risk: RiskLevel
    status: ReviewStatus
    explanation: list[str] = Field(min_items=1)
    provenance: ProvenanceInfo
    feasibility: FeasibilityInfo = Field(default_factory=FeasibilityInfo)
    created_at: datetime
    model_metadata: ModelMetadata
    priority_score: float | None = Field(default=None, ge=0.0, le=1.0)
    max_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_value: float | None = None
    assay: str = ""
    target: str = ""
    score_breakdown: list[ScoreBreakdownItem] = Field(default_factory=list)
    rationale: CandidateRationale | None = None
    target_definition: TargetDefinition | None = None
    data_facts: ScientificDataFacts | None = None
    model_judgment: ModelJudgment | None = None
    applicability_domain: ApplicabilityDomainAssessment | None = None
    novelty_signal: NoveltySignal | None = None
    decision_policy: DecisionPolicyTrace | None = None
    final_recommendation: ScientificRecommendation | None = None
    normalized_explanation: NormalizedExplanation | None = None
    domain_status: str = ""
    domain_label: str = ""
    domain_summary: str = ""
    review_summary: CandidateReviewSummary | None = None
    selection_reason: str = ""
    review_note: str = ""
    reviewer: str = "unassigned"
    reviewed_at: datetime | None = None
    review_history: list[ReviewEventRecord] = Field(default_factory=list)

    @validator(
        "session_id",
        "candidate_id",
        "smiles",
        "canonical_smiles",
        "selection_reason",
        "review_note",
        "assay",
        "target",
        "domain_status",
        "domain_label",
        "domain_summary",
        pre=True,
        always=True,
    )
    def _clean_row_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("reviewer", pre=True, always=True)
    def _clean_row_reviewer(cls, value: Any) -> str:
        return _clean_text(value, default="unassigned")

    @validator("bucket", pre=True)
    def _clean_row_bucket(cls, value: Any) -> str:
        return _normalize_bucket(value)

    @validator("risk", pre=True)
    def _clean_row_risk(cls, value: Any) -> str:
        return _normalize_risk(value)

    @validator("status", pre=True)
    def _clean_row_status(cls, value: Any) -> str:
        return _normalize_status(value)

    @validator("explanation", pre=True)
    def _coerce_explanation(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            cleaned = [_clean_text(item) for item in value if _clean_text(item)]
            return cleaned
        if isinstance(value, str):
            cleaned = [_clean_text(part) for part in value.split("\n") if _clean_text(part)]
            return cleaned
        return []

    @validator("provenance", pre=True)
    def _coerce_provenance(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            return {"text": _clean_text(value)}
        return {"text": _legacy_provenance_text()}

    @validator("feasibility", pre=True)
    def _coerce_feasibility(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        if isinstance(value, bool):
            return {"is_feasible": bool(value), "reason": ""}
        return {"is_feasible": None, "reason": ""}

    @validator("created_at", pre=True)
    def _coerce_created_at(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()

    @validator("reviewed_at", pre=True)
    def _coerce_reviewed_at(cls, value: Any) -> Any:
        return _coerce_datetime(value)

    @validator("confidence", "uncertainty", "priority_score", "max_similarity", "observed_value", pre=True)
    def _coerce_optional_float(cls, value: Any) -> Any:
        if value in (None, "", "nan"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @validator("model_metadata", pre=True)
    def _coerce_model_metadata(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        return _legacy_model_metadata(value)

    @root_validator(pre=False)
    def _sync_review_summary(cls, values: dict[str, Any]) -> dict[str, Any]:
        review_summary = values.get("review_summary")
        if review_summary is None and (values.get("review_note") or values.get("reviewed_at")):
            values["review_summary"] = CandidateReviewSummary(
                status=values.get("status", ReviewStatus.suggested),
                note=values.get("review_note", ""),
                reviewer=values.get("reviewer", "unassigned"),
                actor=values.get("reviewer", "unassigned"),
                reviewed_at=values.get("reviewed_at"),
            )
        return values


class DecisionArtifactSummary(ContractBaseModel):
    top_k: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    risk_counts: dict[str, int] = Field(default_factory=dict)
    top_experiment_value: float = Field(ge=0.0, le=1.0)

    @validator("risk_counts", pre=True)
    def _normalize_risk_counts(cls, value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        return {_normalize_risk(key): int(count) for key, count in value.items()}


class DecisionArtifact(ContractBaseModel):
    schema_version: str = "decision_artifact.v1"
    session_id: str
    iteration: int = Field(ge=0)
    generated_at: datetime
    summary: DecisionArtifactSummary
    top_experiments: list[DecisionArtifactRow] = Field(default_factory=list)
    input_type: str = ""
    intent: str = ""
    mode_used: str = ""
    product_tier: str = ""
    warnings: list[str] = Field(default_factory=list)
    source_name: str = ""
    target_definition: TargetDefinition | None = None
    decision_intent: DecisionIntent | None = None
    modeling_mode: ModelingMode | None = None
    scientific_contract: dict[str, Any] = Field(default_factory=dict)
    run_contract: RunContract | None = None
    comparison_anchors: ComparisonAnchors | None = None
    contract_versions: dict[str, str] = Field(default_factory=dict)
    artifact_state: ArtifactState | None = None
    source_path: str | None = None
    source_updated_at: datetime | None = None
    load_error: str | None = None

    @validator("session_id", "input_type", "intent", "mode_used", "product_tier", "source_name", pre=True, always=True)
    def _clean_artifact_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("decision_intent", pre=True)
    def _clean_artifact_decision_intent(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("modeling_mode", pre=True)
    def _clean_artifact_modeling_mode(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()

    @validator("generated_at", "source_updated_at", pre=True)
    def _coerce_artifact_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value)

    @validator("artifact_state", pre=True)
    def _clean_artifact_state(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return _clean_text(value).lower()


class PredictionResult(ContractBaseModel):
    schema_version: str = "prediction_result.v1"
    session_id: str | None = None
    candidate_count: int = Field(ge=0)
    candidates: list[CandidatePredictionRow] = Field(default_factory=list)


class SelectionResult(ContractBaseModel):
    schema_version: str = "selection_result.v1"
    session_id: str | None = None
    candidate_count: int = Field(ge=0)
    bucket_counts: dict[str, int] = Field(default_factory=dict)
    candidates: list[SelectionResultRow] = Field(default_factory=list)


class ReviewQueueSummary(ContractBaseModel):
    pending_review: int = Field(ge=0)
    approved: int = Field(ge=0)
    rejected: int = Field(ge=0)
    tested: int = Field(ge=0)
    ingested: int = Field(ge=0)
    counts: dict[str, int] = Field(default_factory=dict)

    @validator("counts", pre=True)
    def _clean_queue_counts(cls, value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        return {_normalize_status(key): int(count) for key, count in value.items()}


class ReviewQueueArtifact(ContractBaseModel):
    schema_version: str = "review_queue.v1"
    session_id: str
    generated_at: datetime
    summary: ReviewQueueSummary
    groups: dict[str, list[DecisionArtifactRow]] = Field(default_factory=dict)

    @validator("session_id", pre=True)
    def _clean_queue_session(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("generated_at", pre=True)
    def _coerce_queue_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()

    @validator("groups", pre=True)
    def _clean_queue_groups(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {_normalize_status(key): items for key, items in value.items()}


class JobState(ContractBaseModel):
    schema_version: str = "job_state.v1"
    job_id: str
    session_id: str
    workspace_id: str = ""
    created_by_user_id: str = ""
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    job_type: str = ""
    progress_stage: str = "queued"
    progress_percent: int = Field(default=0, ge=0, le=100)
    progress_message: str = ""
    error: str = ""
    artifact_refs: dict[str, str] = Field(default_factory=dict)

    @validator(
        "job_id",
        "session_id",
        "workspace_id",
        "created_by_user_id",
        "job_type",
        "progress_stage",
        "progress_message",
        "error",
        pre=True,
        always=True,
    )
    def _clean_job_text(cls, value: Any) -> str:
        return _clean_text(value)

    @validator("status", pre=True)
    def _clean_job_status(cls, value: Any) -> str:
        return _clean_text(value).lower()

    @validator("progress_percent", pre=True)
    def _clean_job_progress_percent(cls, value: Any) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = 0
        return max(0, min(100, numeric))

    @validator("created_at", "updated_at", pre=True)
    def _coerce_job_datetime(cls, value: Any) -> Any:
        return _coerce_datetime(value) or _now_utc()


def validate_upload_inspection_result(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(UploadInspectionResult, payload))


def validate_label_builder_config(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(LabelBuilderConfig, payload))


def validate_target_definition(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(TargetDefinition, payload))


def validate_session_identity(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(SessionIdentity, payload))


def validate_status_semantics(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(StatusSemantics, payload))


def validate_run_contract(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(RunContract, payload))


def validate_comparison_anchors(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ComparisonAnchors, payload))


def validate_evidence_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(EvidenceRecord, payload))


def validate_evidence_activation_policy(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(EvidenceActivationPolicy, payload))


def validate_claim_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ClaimRecord, payload))


def validate_claim_reference(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ClaimReference, payload))


def validate_claims_summary(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ClaimsSummary, payload))


def validate_experiment_request_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ExperimentRequestRecord, payload))


def validate_experiment_request_reference(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ExperimentRequestReference, payload))


def validate_experiment_request_summary(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ExperimentRequestSummary, payload))


def validate_experiment_result_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ExperimentResultRecord, payload))


def validate_experiment_result_reference(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ExperimentResultReference, payload))


def validate_experiment_result_summary(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ExperimentResultSummary, payload))


def validate_belief_update_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(BeliefUpdateRecord, payload))


def validate_belief_update_reference(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(BeliefUpdateReference, payload))


def validate_belief_update_summary(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(BeliefUpdateSummary, payload))


def validate_belief_state_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(BeliefStateRecord, payload))


def validate_belief_state_reference(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(BeliefStateReference, payload))


def validate_belief_state_summary(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(BeliefStateSummary, payload))


def validate_scientific_session_truth(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ScientificSessionTruth, payload))


def validate_normalized_explanation(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(NormalizedExplanation, payload))


def validate_model_judgment(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ModelJudgment, payload))


def validate_applicability_domain(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ApplicabilityDomainAssessment, payload))


def validate_novelty_signal(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(NoveltySignal, payload))


def validate_decision_policy_trace(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(DecisionPolicyTrace, payload))


def validate_scientific_recommendation(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ScientificRecommendation, payload))


def validate_session_metadata(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(SessionMetadata, payload))


def validate_user_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(UserRecord, payload))


def validate_workspace_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(WorkspaceRecord, payload))


def validate_workspace_membership_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(WorkspaceMembershipRecord, payload))


def validate_workspace_usage_event_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(WorkspaceUsageEventRecord, payload))


def validate_artifact_pointer(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ArtifactPointer, payload))


def validate_normalized_dataset_summary(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(NormalizedDatasetSummary, payload))


def validate_training_result(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(TrainingResult, payload))


def validate_prediction_result(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(PredictionResult, payload))


def validate_selection_result(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(SelectionResult, payload))


def validate_decision_artifact(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(DecisionArtifact, payload))


def validate_review_event_record(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ReviewEventRecord, payload))


def validate_review_event_records(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [validate_review_event_record(payload) for payload in payloads]


def validate_review_queue_artifact(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(ReviewQueueArtifact, payload))


def validate_job_state(payload: Any) -> dict[str, Any]:
    return dump_contract_model(validate_contract_model(JobState, payload))


def _canonical_decision_row(
    row: dict[str, Any],
    *,
    session_id: str,
    generated_at: Any,
    index: int,
) -> dict[str, Any]:
    candidate_id = _clean_text(row.get("candidate_id")) or _clean_text(row.get("molecule_id")) or _clean_text(row.get("polymer"))
    candidate_id = candidate_id or f"candidate_{index}"
    provenance = row.get("provenance")
    if isinstance(provenance, str):
        provenance = {"text": provenance or _legacy_provenance_text()}
    elif not isinstance(provenance, dict):
        provenance = {"text": _legacy_provenance_text()}

    review_summary = row.get("review_summary")
    if not review_summary and (row.get("review_note") or row.get("reviewed_at")):
        review_summary = {
            "status": row.get("status") or "suggested",
            "note": row.get("review_note") or "",
            "reviewer": row.get("reviewer") or "unassigned",
            "actor": row.get("reviewer") or "unassigned",
            "reviewed_at": row.get("reviewed_at"),
        }

    return {
        "session_id": session_id,
        "rank": int(row.get("rank") or index),
        "candidate_id": candidate_id,
        "smiles": _clean_text(row.get("smiles")),
        "canonical_smiles": _clean_text(row.get("canonical_smiles")) or _clean_text(row.get("smiles")),
        "confidence": row.get("confidence"),
        "uncertainty": row.get("uncertainty"),
        "novelty": float(row.get("novelty", 0.0) or 0.0),
        "acquisition_score": float(
            row.get("acquisition_score", row.get("final_score", row.get("score", row.get("priority_score", row.get("experiment_value", 0.0)))))
            or 0.0
        ),
        "experiment_value": float(row.get("experiment_value", 0.0) or 0.0),
        "bucket": row.get("bucket") or row.get("selection_bucket"),
        "risk": row.get("risk") or row.get("risk_level"),
        "status": row.get("status") or "suggested",
        "explanation": row.get("explanation") or row.get("short_explanation") or ["Legacy decision artifact without recorded explanation."],
        "provenance": provenance,
        "feasibility": row.get("feasibility") or {
            "is_feasible": row.get("is_feasible"),
            "reason": row.get("feasibility_reason") or "",
        },
        "created_at": row.get("created_at") or row.get("timestamp") or generated_at,
        "model_metadata": row.get("model_metadata") or _legacy_model_metadata(row.get("model_version")),
        "priority_score": row.get("priority_score"),
        "max_similarity": row.get("max_similarity"),
        "observed_value": row.get("observed_value", row.get("value")),
        "assay": row.get("assay") or "",
        "target": row.get("target") or "",
        "score_breakdown": row.get("score_breakdown") or [],
        "rationale": row.get("rationale"),
        "target_definition": row.get("target_definition") or {},
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
        "review_summary": review_summary,
        "selection_reason": row.get("selection_reason") or "",
        "review_note": row.get("review_note") or "",
        "reviewer": row.get("reviewer") or "unassigned",
        "reviewed_at": row.get("reviewed_at"),
        "review_history": row.get("review_history") or [],
    }


def normalize_loaded_decision_artifact(
    payload: Any,
    *,
    session_id: str | None = None,
    generated_at: Any = None,
    source_path: str | None = None,
    source_updated_at: Any = None,
    artifact_state: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("DecisionArtifact", "payload must be a JSON object")

    effective_session_id = _clean_text(payload.get("session_id"), default=session_id or "public")
    effective_generated_at = payload.get("generated_at") or payload.get("created_at") or generated_at or _now_utc()
    top_experiments = payload.get("top_experiments", [])
    normalized_rows: list[dict[str, Any]] = []
    if isinstance(top_experiments, list):
        for index, row in enumerate(top_experiments, start=1):
            if isinstance(row, dict):
                normalized_rows.append(
                    _canonical_decision_row(
                        row,
                        session_id=effective_session_id,
                        generated_at=effective_generated_at,
                        index=index,
                    )
                )

    normalized_payload = {
        "schema_version": payload.get("schema_version") or "decision_artifact.v1",
        "session_id": effective_session_id,
        "iteration": int(payload.get("iteration") or 0),
        "generated_at": effective_generated_at,
        "summary": payload.get("summary")
        or {
            "top_k": len(normalized_rows),
            "candidate_count": len(normalized_rows),
            "risk_counts": {},
            "top_experiment_value": 0.0,
        },
        "top_experiments": normalized_rows,
        "input_type": payload.get("input_type") or "",
        "intent": payload.get("intent") or "",
        "mode_used": payload.get("mode_used") or "",
        "product_tier": payload.get("product_tier") or "",
        "warnings": payload.get("warnings") or [],
        "source_name": payload.get("source_name") or "",
        "target_definition": payload.get("target_definition") or {},
        "decision_intent": payload.get("decision_intent") or payload.get("intent") or "",
        "modeling_mode": payload.get("modeling_mode") or "",
        "scientific_contract": payload.get("scientific_contract") or {},
        "run_contract": payload.get("run_contract") or {},
        "comparison_anchors": payload.get("comparison_anchors") or {},
        "contract_versions": payload.get("contract_versions") or {},
        "artifact_state": artifact_state or payload.get("artifact_state"),
        "source_path": source_path or payload.get("source_path"),
        "source_updated_at": source_updated_at or payload.get("source_updated_at"),
        "load_error": payload.get("load_error"),
    }
    return validate_decision_artifact(normalized_payload)
