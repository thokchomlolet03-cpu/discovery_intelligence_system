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


BUCKET_VALUES = tuple(item.value for item in Bucket)
RISK_LEVEL_VALUES = tuple(item.value for item in RiskLevel)
REVIEW_STATUS_VALUES = tuple(item.value for item in ReviewStatus)
WORKSPACE_ROLE_VALUES = tuple(item.value for item in WorkspaceRole)
WORKSPACE_PLAN_TIER_VALUES = tuple(item.value for item in WorkspacePlanTier)
WORKSPACE_PLAN_STATUS_VALUES = tuple(item.value for item in WorkspacePlanStatus)
WORKSPACE_USAGE_EVENT_TYPE_VALUES = tuple(item.value for item in WorkspaceUsageEventType)


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
    free_tier_assessment: dict[str, Any] = Field(default_factory=dict)

    @validator("filename", "input_type", "session_id", "file_type", "semantic_mode", pre=True)
    def _strip_required_text(cls, value: Any) -> str:
        return _clean_text(value)


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
    calibration_method: str
    training_sample_size: int = Field(ge=0)
    class_balance: LabelCounts = Field(default_factory=LabelCounts)
    evaluation_metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    diagnostic_flags: list[str] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(default_factory=dict)
    selected_model: dict[str, Any] = Field(default_factory=dict)
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
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    feasibility: FeasibilityInfo = Field(default_factory=FeasibilityInfo)
    prediction_metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("candidate_id", "smiles", "canonical_smiles", pre=True)
    def _strip_prediction_text(cls, value: Any) -> str:
        return _clean_text(value)


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


class DecisionArtifactRow(ContractBaseModel):
    session_id: str
    rank: int = Field(ge=1)
    candidate_id: str
    smiles: str
    canonical_smiles: str
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
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
    review_summary: CandidateReviewSummary | None = None
    selection_reason: str = ""
    review_note: str = ""
    reviewer: str = "unassigned"
    reviewed_at: datetime | None = None
    review_history: list[ReviewEventRecord] = Field(default_factory=list)

    @validator("session_id", "candidate_id", "smiles", "canonical_smiles", "selection_reason", "review_note", pre=True, always=True)
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
    artifact_state: ArtifactState | None = None
    source_path: str | None = None
    source_updated_at: datetime | None = None
    load_error: str | None = None

    @validator("session_id", "input_type", "intent", "mode_used", "product_tier", "source_name", pre=True, always=True)
    def _clean_artifact_text(cls, value: Any) -> str:
        return _clean_text(value)

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
        "confidence": float(row.get("confidence", 0.0) or 0.0),
        "uncertainty": float(row.get("uncertainty", 0.0) or 0.0),
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
        "artifact_state": artifact_state or payload.get("artifact_state"),
        "source_path": source_path or payload.get("source_path"),
        "source_updated_at": source_updated_at or payload.get("source_updated_at"),
        "load_error": payload.get("load_error"),
    }
    return validate_decision_artifact(normalized_payload)
