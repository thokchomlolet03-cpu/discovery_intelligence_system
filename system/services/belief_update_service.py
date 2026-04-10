from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    BeliefUpdateDirection,
    BeliefUpdateGovernanceStatus,
    ClaimStatus,
    EvidenceSupportLevel,
    ExperimentResultQuality,
    OptimizationDirection,
    TargetKind,
    validate_belief_update_record,
    validate_belief_update_reference,
    validate_belief_update_summary,
    validate_scientific_session_truth,
)
from system.db.repositories import BeliefUpdateRepository, ClaimRepository, ExperimentResultRepository
from system.services.belief_state_service import refresh_belief_state
from system.services.claim_service import sync_claim_governed_review_snapshot
from system.services.support_quality_service import (
    GOVERNED_SUPPORT_POSTURE_ACCEPTED_LIMITED,
    GOVERNED_SUPPORT_POSTURE_GOVERNING,
    GOVERNED_SUPPORT_POSTURE_HISTORICAL,
    GOVERNED_SUPPORT_POSTURE_TENTATIVE,
    REVIEW_REASON_APPROVED,
    REVIEW_REASON_CONTRADICTION,
    REVIEW_REASON_DOWNGRADED,
    REVIEW_REASON_QUARANTINED,
    REVIEW_REASON_STRONGER_TRUST_NEEDED,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_BLOCKED,
    REVIEW_STATUS_CANDIDATE,
    REVIEW_STATUS_DOWNGRADED,
    SUPPORT_QUALITY_ACTIVE_LIMITED,
    SUPPORT_QUALITY_CONTEXT_LIMITED,
    SUPPORT_QUALITY_DECISION_USEFUL,
    SUPPORT_QUALITY_WEAK,
    assess_support_coherence,
    classify_belief_update_contradiction_role,
    classify_belief_update_support_quality,
    classify_governed_support_posture,
    rollup_governed_support_postures,
    rollup_quality_labels,
)


belief_update_repository = BeliefUpdateRepository()
claim_repository = ClaimRepository()
experiment_result_repository = ExperimentResultRepository()

_SUPPORT_ORDER = (
    EvidenceSupportLevel.contextual.value,
    EvidenceSupportLevel.limited.value,
    EvidenceSupportLevel.moderate.value,
    EvidenceSupportLevel.strong.value,
)
_POSITIVE_LABELS = {"1", "true", "positive", "yes", "active", "pass", "hit", "confirmed"}
_NEGATIVE_LABELS = {"0", "false", "negative", "no", "inactive", "fail", "miss", "not_confirmed"}
_ALIGNED_ASSAY_LABEL = "Aligned assay context"
_NEUTRAL_ASSAY_LABEL = "No specific assay context expected"
_SPARSE_ASSAY_LABEL = "Sparse assay context"
_WEAK_ASSAY_LABEL = "Weak assay alignment"
_STRONG_INPUT_LABEL = "Stronger interpretation basis"
_CAUTIOUS_INPUT_LABEL = "Cautious interpretation basis"
_WEAK_INPUT_LABEL = "Weak interpretation basis"
_CLEAN_NUMERIC_BASIS_LABEL = "Clean target rule available"
_WEAK_NUMERIC_BASIS_LABEL = "Weak numeric basis"
_NO_NUMERIC_BASIS_LABEL = "No clean target rule"
_NUMERIC_RESOLVED_LABEL = "Interpreted through current target rule"
_NUMERIC_TENTATIVE_LABEL = "Tentative numeric interpretation"
_NUMERIC_UNRESOLVED_LABEL = "Unresolved under current numeric basis"
_TARGET_RULE_ALIGNED_LABEL = "Target rule aligned"
_TARGET_RULE_CAUTIOUS_LABEL = "Target rule directionally cautious"
_TARGET_RULE_MISSING_LABEL = "No target rule alignment"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _active_for_belief_state(governance_status: Any) -> bool:
    return _clean_text(governance_status).lower() in {
        BeliefUpdateGovernanceStatus.accepted.value,
        BeliefUpdateGovernanceStatus.proposed.value,
    }


def _candidate_label(claim_payload: dict[str, Any], experiment_result_payload: dict[str, Any]) -> str:
    result_reference = (
        experiment_result_payload.get("candidate_reference")
        if isinstance(experiment_result_payload.get("candidate_reference"), dict)
        else {}
    )
    claim_reference = claim_payload.get("candidate_reference") if isinstance(claim_payload.get("candidate_reference"), dict) else {}
    return _clean_text(
        result_reference.get("candidate_label")
        or claim_reference.get("candidate_label")
        or experiment_result_payload.get("candidate_id")
        or claim_payload.get("candidate_id")
    )


def _normalize_support_level(value: Any) -> str:
    token = _clean_text(value, default=EvidenceSupportLevel.limited.value).lower()
    if token in _SUPPORT_ORDER:
        return token
    return EvidenceSupportLevel.limited.value


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "nan"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized_unit(value: Any) -> str:
    return _clean_text(value).lower().replace("μ", "u").replace("µ", "u").replace(" ", "")


def _clean_target_definition(claim_payload: dict[str, Any], experiment_result_payload: dict[str, Any]) -> dict[str, Any]:
    claim_target = claim_payload.get("target_definition_snapshot")
    if isinstance(claim_target, dict) and claim_target:
        return claim_target
    result_target = experiment_result_payload.get("target_definition_snapshot")
    return result_target if isinstance(result_target, dict) else {}


def _normalized_label_token(value: Any) -> str:
    return _clean_text(value).lower().replace(" ", "_")


def _measurement_unit_alignment(
    experiment_result_payload: dict[str, Any],
    target_definition: dict[str, Any],
) -> tuple[str, int]:
    target_unit = _clean_text(target_definition.get("measurement_unit"))
    observed_unit = _clean_text(experiment_result_payload.get("measurement_unit"))
    normalized_target_unit = _normalized_unit(target_unit)
    normalized_observed_unit = _normalized_unit(observed_unit)
    if not normalized_target_unit:
        return "", 1
    if not normalized_observed_unit:
        return (
            f"The current target definition expects measurements in {target_unit}, but this observed numeric result does not record a matching measurement unit.",
            0,
        )
    if (
        normalized_target_unit == normalized_observed_unit
        or normalized_target_unit in normalized_observed_unit
        or normalized_observed_unit in normalized_target_unit
    ):
        return (
            f"The recorded measurement unit ({observed_unit}) aligns with the current target definition.",
            1,
        )
    return (
        f"The observed numeric result is recorded in {observed_unit}, while the current target definition expects {target_unit}, so numeric interpretation remains unresolved under the current target context.",
        0,
    )


def _target_rule_alignment(target_definition: dict[str, Any], operator: str) -> tuple[str, str, int]:
    target_name = _clean_text(target_definition.get("target_name"), default="current target")
    target_kind = _clean_text(target_definition.get("target_kind"), default=TargetKind.classification.value).lower()
    optimization_direction = _clean_text(
        target_definition.get("optimization_direction"),
        default=OptimizationDirection.classify.value if target_kind == TargetKind.classification.value else OptimizationDirection.hit_range.value,
    ).lower()
    if target_kind != TargetKind.regression.value:
        return (
            _TARGET_RULE_CAUTIOUS_LABEL,
            f"The current target rule is available for {target_name}, but this target is not a simple maximize/minimize regression objective, so numeric interpretation remains cautious.",
            1,
        )
    if optimization_direction == OptimizationDirection.maximize.value:
        if operator in {">", ">="}:
            return (
                _TARGET_RULE_ALIGNED_LABEL,
                f"The current target rule is directionally aligned with the maximize objective for {target_name}.",
                2,
            )
        return (
            _TARGET_RULE_CAUTIOUS_LABEL,
            f"The current target rule does not align cleanly with the maximize objective for {target_name}, so numeric interpretation remains cautious.",
            1,
        )
    if optimization_direction == OptimizationDirection.minimize.value:
        if operator in {"<", "<="}:
            return (
                _TARGET_RULE_ALIGNED_LABEL,
                f"The current target rule is directionally aligned with the minimize objective for {target_name}.",
                2,
            )
        return (
            _TARGET_RULE_CAUTIOUS_LABEL,
            f"The current target rule does not align cleanly with the minimize objective for {target_name}, so numeric interpretation remains cautious.",
            1,
        )
    return (
        _TARGET_RULE_CAUTIOUS_LABEL,
        f"The current target rule is recorded for {target_name}, but this target uses a bounded direction ({optimization_direction or 'current'}), so numeric interpretation remains cautious.",
        1,
    )


def _numeric_result_context(
    target_definition: dict[str, Any],
    experiment_result_payload: dict[str, Any],
) -> dict[str, Any]:
    observed_value = _safe_float(experiment_result_payload.get("observed_value"))
    empty_payload = {
        "has_numeric_result": False,
        "direction": BeliefUpdateDirection.unresolved.value,
        "result_interpretation_basis": "",
        "numeric_result_basis_label": "",
        "numeric_result_basis_summary": "",
        "numeric_result_resolution_label": "",
        "numeric_result_interpretation_label": "",
        "target_rule_alignment_label": "",
        "basis_strength": 2,
        "rule_outcome_summary": "",
    }
    if observed_value is None:
        return empty_payload

    rule = target_definition.get("derived_label_rule") if isinstance(target_definition.get("derived_label_rule"), dict) else {}
    operator = _clean_text(rule.get("operator"), default=">=")
    threshold = _safe_float(rule.get("threshold"))
    if threshold is None:
        return {
            **empty_payload,
            "has_numeric_result": True,
            "result_interpretation_basis": "Numeric outcome without clean target rule",
            "numeric_result_basis_label": _NO_NUMERIC_BASIS_LABEL,
            "numeric_result_basis_summary": "A numeric outcome is recorded, but the current target definition does not include a clean derived target rule for bounded interpretation.",
            "numeric_result_resolution_label": _NUMERIC_UNRESOLVED_LABEL,
            "target_rule_alignment_label": _TARGET_RULE_MISSING_LABEL,
            "basis_strength": 0,
        }
    comparison: bool | None = None
    if operator == ">":
        comparison = observed_value > threshold
    elif operator == ">=":
        comparison = observed_value >= threshold
    elif operator == "<":
        comparison = observed_value < threshold
    elif operator == "<=":
        comparison = observed_value <= threshold
    elif operator == "==":
        comparison = observed_value == threshold
    else:
        return {
            **empty_payload,
            "has_numeric_result": True,
            "result_interpretation_basis": "Numeric outcome without clean target rule",
            "numeric_result_basis_label": _NO_NUMERIC_BASIS_LABEL,
            "numeric_result_basis_summary": "A numeric outcome is recorded, but the current target rule uses an unsupported operator, so bounded interpretation remains unresolved.",
            "numeric_result_resolution_label": _NUMERIC_UNRESOLVED_LABEL,
            "target_rule_alignment_label": _TARGET_RULE_MISSING_LABEL,
            "basis_strength": 0,
        }

    target_name = _clean_text(target_definition.get("target_name"), default="current target")
    optimization_direction = _clean_text(target_definition.get("optimization_direction"), default="current")
    unit_alignment_summary, unit_alignment_score = _measurement_unit_alignment(experiment_result_payload, target_definition)
    target_rule_alignment_label, target_rule_alignment_summary, target_rule_alignment_score = _target_rule_alignment(
        target_definition,
        operator,
    )
    base_summary = (
        f"Numeric result can be compared against the current target rule ({operator} {threshold:g}) for {optimization_direction or 'current'} {target_name}."
    )
    if comparison:
        direction = BeliefUpdateDirection.strengthened.value
        rule_outcome_summary = f"Recorded numeric result {observed_value:g} met the current target rule ({operator} {threshold:g})."
    else:
        direction = BeliefUpdateDirection.weakened.value
        rule_outcome_summary = f"Recorded numeric result {observed_value:g} did not meet the current target rule ({operator} {threshold:g})."

    if unit_alignment_score <= 0:
        return {
            **empty_payload,
            "has_numeric_result": True,
            "result_interpretation_basis": "Numeric outcome with weak target rule context",
            "numeric_result_basis_label": _WEAK_NUMERIC_BASIS_LABEL,
            "numeric_result_basis_summary": (
                f"A current target rule ({operator} {threshold:g}) is recorded for {optimization_direction or 'current'} {target_name}, "
                f"but {unit_alignment_summary.lower()}"
            ),
            "numeric_result_resolution_label": _NUMERIC_UNRESOLVED_LABEL,
            "target_rule_alignment_label": target_rule_alignment_label,
            "basis_strength": 0,
            "rule_outcome_summary": rule_outcome_summary,
        }

    basis_strength = 2 if target_rule_alignment_score >= 2 else 1
    basis_label = _CLEAN_NUMERIC_BASIS_LABEL if basis_strength >= 2 else _WEAK_NUMERIC_BASIS_LABEL
    basis_parts = [base_summary]
    if target_rule_alignment_summary:
        basis_parts.append(target_rule_alignment_summary)
    if unit_alignment_summary:
        basis_parts.append(unit_alignment_summary)
    return {
        **empty_payload,
        "has_numeric_result": True,
        "direction": direction,
        "result_interpretation_basis": "Numeric outcome under current target rule",
        "numeric_result_basis_label": basis_label,
        "numeric_result_basis_summary": " ".join(part for part in basis_parts if part).strip(),
        "numeric_result_resolution_label": _NUMERIC_RESOLVED_LABEL if basis_strength >= 2 else _NUMERIC_TENTATIVE_LABEL,
        "target_rule_alignment_label": target_rule_alignment_label,
        "basis_strength": basis_strength,
        "rule_outcome_summary": rule_outcome_summary,
    }


def _assay_context_alignment(
    experiment_result_payload: dict[str, Any],
    target_definition: dict[str, Any],
) -> tuple[str, str, int]:
    assay_context = _clean_text(experiment_result_payload.get("assay_context")).lower()
    target_assay = _clean_text(target_definition.get("assay_context")).lower()
    measurement_column = _clean_text(target_definition.get("measurement_column")).lower()
    target_name = _clean_text(target_definition.get("target_name")).lower()
    if not target_assay:
        if assay_context:
            if measurement_column and measurement_column in assay_context:
                return (
                    _ALIGNED_ASSAY_LABEL,
                    "Recorded assay context mentions the current measurement column, so assay alignment is directionally compatible.",
                    2,
                )
            if target_name and target_name in assay_context:
                return (
                    _ALIGNED_ASSAY_LABEL,
                    "Recorded assay context mentions the current target, so assay alignment is directionally compatible.",
                    2,
                )
            return (
                _NEUTRAL_ASSAY_LABEL,
                "Assay context is recorded, but no stricter target-assay expectation is defined for this claim.",
                1,
            )
        return (
            _NEUTRAL_ASSAY_LABEL,
            "No stricter target-assay expectation is defined for this claim, so support interpretation falls back to result quality and target direction.",
            1,
        )
    if not assay_context:
        return (
            _SPARSE_ASSAY_LABEL,
            "The target definition expects assay context, but none was recorded with this observed result, so support interpretation stays cautious.",
            0,
        )
    if assay_context == target_assay or target_assay in assay_context or assay_context in target_assay:
        return (
            _ALIGNED_ASSAY_LABEL,
            "Recorded assay context matches the target-scoped assay context closely enough for a stronger bounded interpretation.",
            2,
        )
    if measurement_column and measurement_column in assay_context:
        return (
            _NEUTRAL_ASSAY_LABEL,
            "Recorded assay context is only partially aligned through the current measurement column, so support interpretation remains cautious.",
            1,
        )
    return (
        _WEAK_ASSAY_LABEL,
        "Recorded assay context does not clearly align with the target-scoped assay context, so support interpretation remains cautious.",
        0,
    )


def _support_input_quality(
    *,
    result_quality: str,
    assay_alignment_score: int,
    interpretation_basis: str,
    basis_strength: int = 2,
) -> tuple[str, str]:
    quality_token = _clean_text(result_quality, default=ExperimentResultQuality.provisional.value).lower()
    if basis_strength <= 0:
        return (
            _WEAK_INPUT_LABEL,
            f"The current {interpretation_basis.lower()} path does not have a strong enough target-scoped basis for a bounded support-change interpretation.",
        )
    if quality_token == ExperimentResultQuality.confirmatory.value and assay_alignment_score >= 1 and basis_strength >= 2:
        return (
            _STRONG_INPUT_LABEL,
            f"Result quality and context support a stronger bounded interpretation under the current {interpretation_basis.lower()} path.",
        )
    if quality_token in {ExperimentResultQuality.confirmatory.value, ExperimentResultQuality.screening.value} and assay_alignment_score >= 1:
        return (
            _CAUTIOUS_INPUT_LABEL,
            f"Result quality and context support a cautious bounded interpretation under the current {interpretation_basis.lower()} path.",
        )
    return (
        _WEAK_INPUT_LABEL,
        f"Result quality or assay context is too weak for a strong bounded interpretation under the current {interpretation_basis.lower()} path.",
    )


def _target_direction_signal(
    claim_payload: dict[str, Any],
    experiment_result_payload: dict[str, Any],
) -> dict[str, Any]:
    target_definition = _clean_target_definition(claim_payload, experiment_result_payload)
    target_kind = _clean_text(target_definition.get("target_kind"), default=TargetKind.classification.value).lower()
    optimization_direction = _clean_text(
        target_definition.get("optimization_direction"),
        default=OptimizationDirection.classify.value if target_kind == TargetKind.classification.value else OptimizationDirection.hit_range.value,
    ).lower()
    observed_label = _normalized_label_token(experiment_result_payload.get("observed_label"))
    observed_value = _safe_float(experiment_result_payload.get("observed_value"))
    if observed_label:
        if observed_label in _POSITIVE_LABELS:
            return {
                "direction": BeliefUpdateDirection.strengthened.value,
                "result_interpretation_basis": "Observed label",
                "numeric_result_basis_label": "",
                "numeric_result_basis_summary": "",
                "numeric_result_resolution_label": "",
                "numeric_result_interpretation_label": "",
                "target_rule_alignment_label": "",
                "basis_strength": 2,
                "has_numeric_result": False,
            }
        if observed_label in _NEGATIVE_LABELS:
            return {
                "direction": BeliefUpdateDirection.weakened.value,
                "result_interpretation_basis": "Observed label",
                "numeric_result_basis_label": "",
                "numeric_result_basis_summary": "",
                "numeric_result_resolution_label": "",
                "numeric_result_interpretation_label": "",
                "target_rule_alignment_label": "",
                "basis_strength": 2,
                "has_numeric_result": False,
            }
        return {
            "direction": BeliefUpdateDirection.unresolved.value,
            "result_interpretation_basis": "Observed label",
            "numeric_result_basis_label": "",
            "numeric_result_basis_summary": "",
            "numeric_result_resolution_label": "",
            "numeric_result_interpretation_label": "",
            "target_rule_alignment_label": "",
            "basis_strength": 2,
            "has_numeric_result": False,
        }

    if observed_value is not None:
        numeric_context = _numeric_result_context(target_definition, experiment_result_payload)
        if numeric_context.get("has_numeric_result"):
            return numeric_context
        return {
            "direction": BeliefUpdateDirection.unresolved.value,
            "result_interpretation_basis": "Numeric outcome without clean target rule",
            "numeric_result_basis_label": _NO_NUMERIC_BASIS_LABEL,
            "numeric_result_basis_summary": (
                f"Numeric outcome is recorded for a {optimization_direction or 'current'} {target_kind or 'target'} objective, "
                "but no bounded target rule is available to convert it into a support-change direction."
            ),
            "numeric_result_resolution_label": _NUMERIC_UNRESOLVED_LABEL,
            "numeric_result_interpretation_label": "",
            "target_rule_alignment_label": _TARGET_RULE_MISSING_LABEL,
            "basis_strength": 0,
            "has_numeric_result": True,
        }
    return {
        "direction": BeliefUpdateDirection.unresolved.value,
        "result_interpretation_basis": "Observed result without interpretable signal",
        "numeric_result_basis_label": "",
        "numeric_result_basis_summary": "",
        "numeric_result_resolution_label": "",
        "numeric_result_interpretation_label": "",
        "target_rule_alignment_label": "",
        "basis_strength": 0,
        "has_numeric_result": False,
    }


def _numeric_resolution_fields(
    *,
    numeric_context: dict[str, Any],
    update_direction: str,
    support_input_quality_label: str,
    support_input_quality_summary: str,
    assay_context_alignment_label: str,
) -> tuple[str, str]:
    if not numeric_context.get("has_numeric_result"):
        return "", ""
    basis_summary = _clean_text(numeric_context.get("numeric_result_basis_summary"))
    rule_outcome_summary = _clean_text(numeric_context.get("rule_outcome_summary"))
    raw_direction = _clean_text(numeric_context.get("direction"), default=BeliefUpdateDirection.unresolved.value).lower()
    if raw_direction == BeliefUpdateDirection.unresolved.value:
        return (
            _NUMERIC_UNRESOLVED_LABEL,
            basis_summary or "Numeric result remains unresolved under the current numeric basis.",
        )
    if update_direction == raw_direction:
        if support_input_quality_label == _STRONG_INPUT_LABEL and int(numeric_context.get("basis_strength") or 0) >= 2:
            return (
                _NUMERIC_RESOLVED_LABEL,
                f"{rule_outcome_summary} Numeric result was interpreted through the current target rule under a stronger bounded basis.",
            )
        return (
            _NUMERIC_TENTATIVE_LABEL,
            f"{rule_outcome_summary} {support_input_quality_summary} {assay_context_alignment_label} keeps the numeric interpretation cautious.",
        )
    return (
        _NUMERIC_UNRESOLVED_LABEL,
        f"{rule_outcome_summary} {support_input_quality_summary} {assay_context_alignment_label} keeps support unresolved under the current numeric basis.",
    )


def _step_support_level(level: str, direction: str) -> str:
    current = _normalize_support_level(level)
    index = _SUPPORT_ORDER.index(current)
    if direction == BeliefUpdateDirection.strengthened.value:
        return _SUPPORT_ORDER[min(index + 1, len(_SUPPORT_ORDER) - 1)]
    if direction == BeliefUpdateDirection.weakened.value:
        return _SUPPORT_ORDER[max(index - 1, 0)]
    return current


def _latest_support_level(workspace_id: str, claim_payload: dict[str, Any]) -> str:
    claim_id = _clean_text(claim_payload.get("claim_id"))
    if not claim_id:
        return EvidenceSupportLevel.limited.value
    prior_updates = belief_update_repository.list_belief_updates(
        workspace_id=workspace_id,
        claim_id=claim_id,
    )
    for update in prior_updates:
        if not isinstance(update, dict):
            continue
        governance = _clean_text(update.get("governance_status")).lower()
        if governance in {
            BeliefUpdateGovernanceStatus.rejected.value,
            BeliefUpdateGovernanceStatus.superseded.value,
        }:
            continue
        return _normalize_support_level(update.get("updated_support_level"))
    return _normalize_support_level(claim_payload.get("support_level"))


def _reason_text(
    *,
    direction: str,
    claim_payload: dict[str, Any],
    experiment_result_payload: dict[str, Any],
    support_input_quality_label: str,
    support_input_quality_summary: str,
    assay_context_alignment_label: str,
    result_interpretation_basis: str,
    numeric_result_interpretation_label: str,
    numeric_result_basis_summary: str,
    numeric_result_resolution_label: str,
) -> str:
    label = _candidate_label(claim_payload, experiment_result_payload) or "This candidate"
    observed_label = _clean_text(experiment_result_payload.get("observed_label"))
    observed_value = experiment_result_payload.get("observed_value")
    target_definition = _clean_target_definition(claim_payload, experiment_result_payload)
    target_name = _clean_text(target_definition.get("target_name"), default="current target")
    if direction == BeliefUpdateDirection.strengthened.value:
        return (
            f"{label} now has an observed outcome that directionally supports the current {target_name} framing under the {result_interpretation_basis.lower()} path. "
            f"{support_input_quality_summary} {assay_context_alignment_label} keeps this a bounded support change only; it does not prove the claim, establish causality, or change the model."
        )
    if direction == BeliefUpdateDirection.weakened.value:
        return (
            f"{label} now has an observed outcome that directionally weakens the current {target_name} framing under the {result_interpretation_basis.lower()} path. "
            f"{support_input_quality_summary} This remains a bounded support change and does not disprove the broader objective or imply causality."
        )
    if numeric_result_interpretation_label:
        return (
            f"{label} now has a recorded numeric outcome. {numeric_result_interpretation_label} "
            f"{numeric_result_basis_summary} {numeric_result_resolution_label or 'Support remains unresolved under the current evidence basis.'}"
        )
    if observed_value is not None and observed_label:
        return (
            f"{label} now has both a numeric outcome and observed label, but {support_input_quality_label.lower()} keeps this support change unresolved under the current evidence basis."
        )
    return (
        f"{label} now has a recorded observed label '{observed_label or 'not recorded'}', but {support_input_quality_label.lower()} keeps the support change unresolved under the current evidence basis."
    )


def build_belief_update_record(
    *,
    session_id: str,
    workspace_id: str,
    claim_id: str = "",
    experiment_result_id: str = "",
    created_by: str = "scientist",
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    experiment_result_payload = (
        experiment_result_repository.get_experiment_result(experiment_result_id, workspace_id=workspace_id)
        if _clean_text(experiment_result_id)
        else {}
    )
    effective_claim_id = _clean_text(claim_id or experiment_result_payload.get("source_claim_id"))
    if not effective_claim_id:
        raise ValueError("BeliefUpdate requires a linked claim or an observed result already linked to a claim.")
    claim_payload = claim_repository.get_claim(effective_claim_id, workspace_id=workspace_id)
    if experiment_result_payload and _clean_text(experiment_result_payload.get("source_claim_id")):
        linked_claim_id = _clean_text(experiment_result_payload.get("source_claim_id"))
        if linked_claim_id and linked_claim_id != _clean_text(claim_payload.get("claim_id")):
            raise ValueError("BeliefUpdate claim/result linkage mismatch.")

    previous_support_level = _latest_support_level(workspace_id, claim_payload)
    target_definition = _clean_target_definition(claim_payload, experiment_result_payload)
    interpretation_context = _target_direction_signal(
        claim_payload,
        experiment_result_payload,
    )
    raw_direction = _clean_text(interpretation_context.get("direction"), default=BeliefUpdateDirection.unresolved.value)
    result_interpretation_basis = _clean_text(interpretation_context.get("result_interpretation_basis"))
    numeric_result_basis_label = _clean_text(interpretation_context.get("numeric_result_basis_label"))
    numeric_result_basis_summary = _clean_text(interpretation_context.get("numeric_result_basis_summary"))
    target_rule_alignment_label = _clean_text(interpretation_context.get("target_rule_alignment_label"))
    assay_context_alignment_label, assay_context_alignment_summary, assay_alignment_score = _assay_context_alignment(
        experiment_result_payload,
        target_definition,
    )
    support_input_quality_label, support_input_quality_summary = _support_input_quality(
        result_quality=_clean_text(experiment_result_payload.get("result_quality")),
        assay_alignment_score=assay_alignment_score,
        interpretation_basis=result_interpretation_basis,
        basis_strength=int(interpretation_context.get("basis_strength") or 0),
    )
    if raw_direction != BeliefUpdateDirection.unresolved.value and support_input_quality_label == _WEAK_INPUT_LABEL:
        update_direction = BeliefUpdateDirection.unresolved.value
    else:
        update_direction = raw_direction
    numeric_result_resolution_label, numeric_result_interpretation_label = _numeric_resolution_fields(
        numeric_context=interpretation_context,
        update_direction=update_direction,
        support_input_quality_label=support_input_quality_label,
        support_input_quality_summary=support_input_quality_summary,
        assay_context_alignment_label=assay_context_alignment_label,
    )
    support_quality = classify_belief_update_support_quality(
        {
            "update_direction": update_direction,
            "support_input_quality_label": support_input_quality_label,
            "assay_context_alignment_label": assay_context_alignment_label,
            "result_interpretation_basis": result_interpretation_basis,
            "numeric_result_resolution_label": numeric_result_resolution_label,
            "target_rule_alignment_label": target_rule_alignment_label,
            "metadata": {
                "linked_result_quality": _clean_text(experiment_result_payload.get("result_quality")),
                "source_class_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("source_class_label")),
                "source_class_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("source_class_summary")),
                "provenance_confidence_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("provenance_confidence_label")),
                "provenance_confidence_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("provenance_confidence_summary")),
                "trust_tier_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("trust_tier_label")),
                "trust_tier_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("trust_tier_summary")),
                "governed_review_status_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("governed_review_status_label"), default=REVIEW_STATUS_CANDIDATE),
                "governed_review_status_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("governed_review_status_summary")),
                "governed_review_reason_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("governed_review_reason_label"), default=REVIEW_REASON_STRONGER_TRUST_NEEDED),
                "governed_review_reason_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("governed_review_reason_summary")),
            },
        }
    )
    governed_posture = classify_governed_support_posture(
        {
            "governance_status": BeliefUpdateGovernanceStatus.proposed.value,
            "support_quality_label": support_quality["support_quality_label"],
            "metadata": {
                "support_quality_label": support_quality["support_quality_label"],
            },
        }
    )
    contradiction_role = classify_belief_update_contradiction_role(
        {
            "governance_status": BeliefUpdateGovernanceStatus.proposed.value,
            "update_direction": update_direction,
            "support_quality_label": support_quality["support_quality_label"],
            "governed_support_posture_label": governed_posture["governed_support_posture_label"],
            "metadata": {
                "support_quality_label": support_quality["support_quality_label"],
                "governed_support_posture_label": governed_posture["governed_support_posture_label"],
            },
        }
    )
    updated_support_level = _step_support_level(previous_support_level, update_direction)
    candidate_id = _clean_text(
        experiment_result_payload.get("candidate_id")
        or claim_payload.get("candidate_id")
    )
    candidate_label = _candidate_label(claim_payload, experiment_result_payload)
    created_at = _utc_now()

    return validate_belief_update_record(
        {
            "belief_update_id": "",
            "workspace_id": workspace_id,
            "session_id": session_id,
            "claim_id": effective_claim_id,
            "experiment_result_id": _clean_text(experiment_result_payload.get("experiment_result_id")),
            "candidate_id": candidate_id,
            "candidate_label": candidate_label,
            "previous_support_level": previous_support_level,
            "updated_support_level": updated_support_level,
            "update_direction": update_direction,
            "update_reason": _reason_text(
                direction=update_direction,
                claim_payload=claim_payload,
                experiment_result_payload=experiment_result_payload,
                support_input_quality_label=support_input_quality_label,
                support_input_quality_summary=support_input_quality_summary,
                assay_context_alignment_label=assay_context_alignment_label,
                result_interpretation_basis=result_interpretation_basis,
                numeric_result_interpretation_label=numeric_result_interpretation_label,
                numeric_result_basis_summary=numeric_result_basis_summary,
                numeric_result_resolution_label=numeric_result_resolution_label,
            ),
            "support_input_quality_label": support_input_quality_label,
            "support_input_quality_summary": support_input_quality_summary,
            "assay_context_alignment_label": assay_context_alignment_label,
            "result_interpretation_basis": result_interpretation_basis,
            "numeric_result_basis_label": numeric_result_basis_label,
            "numeric_result_basis_summary": numeric_result_basis_summary,
            "numeric_result_resolution_label": numeric_result_resolution_label,
            "numeric_result_interpretation_label": numeric_result_interpretation_label,
            "target_rule_alignment_label": target_rule_alignment_label,
            "support_quality_label": support_quality["support_quality_label"],
            "support_quality_summary": support_quality["support_quality_summary"],
            "support_decision_usefulness_label": support_quality["support_decision_usefulness_label"],
            "governed_support_posture_label": governed_posture["governed_support_posture_label"],
            "governed_support_posture_summary": governed_posture["governed_support_posture_summary"],
            "contradiction_role_label": contradiction_role["contradiction_role_label"],
            "contradiction_role_summary": contradiction_role["contradiction_role_summary"],
            "governance_status": BeliefUpdateGovernanceStatus.proposed.value,
            "created_at": created_at,
            "created_by": _clean_text(created_by, default="scientist"),
            "created_by_user_id": _clean_text(created_by_user_id),
            "reviewed_at": None,
            "reviewed_by": "",
            "metadata": {
                "claim_status": _clean_text(claim_payload.get("status"), default=ClaimStatus.proposed.value),
                "linked_result_quality": _clean_text(experiment_result_payload.get("result_quality")),
                "linked_result_source": _clean_text(experiment_result_payload.get("result_source")),
                "source_class_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("source_class_label")),
                "source_class_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("source_class_summary")),
                "provenance_confidence_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("provenance_confidence_label")),
                "provenance_confidence_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("provenance_confidence_summary")),
                "trust_tier_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("trust_tier_label")),
                "trust_tier_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("trust_tier_summary")),
                "governed_review_status_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("governed_review_status_label"), default=REVIEW_STATUS_CANDIDATE),
                "governed_review_status_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("governed_review_status_summary")),
                "governed_review_reason_label": _clean_text((experiment_result_payload.get("metadata") or {}).get("governed_review_reason_label"), default=REVIEW_REASON_STRONGER_TRUST_NEEDED),
                "governed_review_reason_summary": _clean_text((experiment_result_payload.get("metadata") or {}).get("governed_review_reason_summary")),
                "support_input_quality_label": support_input_quality_label,
                "support_input_quality_summary": support_input_quality_summary,
                "assay_context_alignment_label": assay_context_alignment_label,
                "assay_context_alignment_summary": assay_context_alignment_summary,
                "result_interpretation_basis": result_interpretation_basis,
                "numeric_result_basis_label": numeric_result_basis_label,
                "numeric_result_basis_summary": numeric_result_basis_summary,
                "numeric_result_resolution_label": numeric_result_resolution_label,
                "numeric_result_interpretation_label": numeric_result_interpretation_label,
                "target_rule_alignment_label": target_rule_alignment_label,
                "support_quality_label": support_quality["support_quality_label"],
                "support_quality_summary": support_quality["support_quality_summary"],
                "support_decision_usefulness_label": support_quality["support_decision_usefulness_label"],
                "governed_support_posture_label": governed_posture["governed_support_posture_label"],
                "governed_support_posture_summary": governed_posture["governed_support_posture_summary"],
                "contradiction_role_label": contradiction_role["contradiction_role_label"],
                "contradiction_role_summary": contradiction_role["contradiction_role_summary"],
            },
        }
    )


def create_belief_update(
    *,
    session_id: str,
    workspace_id: str,
    claim_id: str = "",
    experiment_result_id: str = "",
    created_by: str = "scientist",
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    payload = build_belief_update_record(
        session_id=session_id,
        workspace_id=workspace_id,
        claim_id=claim_id,
        experiment_result_id=experiment_result_id,
        created_by=created_by,
        created_by_user_id=created_by_user_id,
    )
    created = belief_update_repository.upsert_belief_update(payload)
    refresh_belief_state(
        workspace_id=workspace_id,
        claim_id=_clean_text(created.get("claim_id")),
    )
    sync_claim_governed_review_snapshot(
        claim_id=_clean_text(created.get("claim_id")),
        workspace_id=workspace_id,
        recorded_by=created_by,
        actor_user_id=created_by_user_id,
    )
    return created


def _govern_belief_update(
    *,
    belief_update_id: str,
    workspace_id: str,
    session_id: str = "",
    governance_status: str,
    reviewed_by: str = "scientist",
    reviewed_by_user_id: str | None = None,
    governance_note: str = "",
) -> dict[str, Any]:
    current = belief_update_repository.get_belief_update(belief_update_id, workspace_id=workspace_id)
    if _clean_text(session_id) and _clean_text(current.get("session_id")) != _clean_text(session_id):
        raise ValueError("BeliefUpdate governance must be applied within the matching session context.")
    if _clean_text(current.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value:
        raise ValueError("Superseded belief updates cannot be re-governed in this slice.")
    reviewed_at = _utc_now()
    metadata = dict(current.get("metadata") or {})
    if governance_status == BeliefUpdateGovernanceStatus.accepted.value:
        metadata["accepted_at"] = reviewed_at.isoformat()
        metadata["accepted_by"] = _clean_text(reviewed_by, default="scientist")
        metadata["governed_review_status_label"] = REVIEW_STATUS_APPROVED
        metadata["governed_review_reason_label"] = REVIEW_REASON_APPROVED
    elif governance_status == BeliefUpdateGovernanceStatus.rejected.value:
        metadata["rejected_at"] = reviewed_at.isoformat()
        metadata["rejected_by"] = _clean_text(reviewed_by, default="scientist")
        metadata["governed_review_status_label"] = REVIEW_STATUS_BLOCKED
        metadata["governed_review_reason_label"] = REVIEW_REASON_CONTRADICTION
    elif governance_status == BeliefUpdateGovernanceStatus.superseded.value:
        metadata["superseded_at"] = reviewed_at.isoformat()
        metadata["superseded_by"] = _clean_text(reviewed_by, default="scientist")
        metadata["governed_review_status_label"] = REVIEW_STATUS_DOWNGRADED
        metadata["governed_review_reason_label"] = REVIEW_REASON_DOWNGRADED
    if reviewed_by_user_id:
        metadata["reviewed_by_user_id"] = _clean_text(reviewed_by_user_id)
    if governance_note:
        note_key = "supersede_reason" if governance_status == BeliefUpdateGovernanceStatus.superseded.value else "governance_note"
        metadata[note_key] = _clean_text(governance_note)
    governed_posture = classify_governed_support_posture(
        {
            **current,
            "governance_status": governance_status,
            "metadata": metadata,
        }
    )
    contradiction_role = classify_belief_update_contradiction_role(
        {
            **current,
            "governance_status": governance_status,
            "governed_support_posture_label": governed_posture["governed_support_posture_label"],
            "metadata": {
                **metadata,
                "governed_support_posture_label": governed_posture["governed_support_posture_label"],
            },
        }
    )
    metadata["governed_support_posture_label"] = governed_posture["governed_support_posture_label"]
    metadata["governed_support_posture_summary"] = governed_posture["governed_support_posture_summary"]
    metadata["contradiction_role_label"] = contradiction_role["contradiction_role_label"]
    metadata["contradiction_role_summary"] = contradiction_role["contradiction_role_summary"]
    if not _clean_text(metadata.get("governed_review_status_summary")):
        if metadata.get("governed_review_status_label") == REVIEW_STATUS_APPROVED:
            metadata["governed_review_status_summary"] = "This support change was reviewed and approved for bounded broader governed consideration."
            metadata["governed_review_reason_summary"] = "Accepted governed support now strengthens the broader review basis while still remaining bounded."
        elif metadata.get("governed_review_status_label") == REVIEW_STATUS_BLOCKED:
            metadata["governed_review_status_summary"] = "This support change was reviewed and blocked from stronger broader influence."
            metadata["governed_review_reason_summary"] = "Contradiction or rejection keeps this support useful as context, not as broader trust."
        elif metadata.get("governed_review_status_label") == REVIEW_STATUS_DOWNGRADED:
            metadata["governed_review_status_summary"] = "This support change was downgraded after newer evidence displaced a cleaner broader-trust posture."
            metadata["governed_review_reason_summary"] = "Superseded support remains historical context, not a current broader-trust basis."

    updated = belief_update_repository.update_belief_update_governance(
        belief_update_id=belief_update_id,
        workspace_id=workspace_id,
        governance_status=governance_status,
        reviewed_at=reviewed_at,
        reviewed_by=_clean_text(reviewed_by, default="scientist"),
        metadata_updates=metadata,
    )
    refresh_belief_state(
        workspace_id=workspace_id,
        claim_id=_clean_text(updated.get("claim_id")),
    )
    sync_claim_governed_review_snapshot(
        claim_id=_clean_text(updated.get("claim_id")),
        workspace_id=workspace_id,
        recorded_by=_clean_text(reviewed_by, default="scientist"),
        actor_user_id=reviewed_by_user_id,
    )
    updated = dict(updated)
    updated["governed_support_posture_label"] = governed_posture["governed_support_posture_label"]
    updated["governed_support_posture_summary"] = governed_posture["governed_support_posture_summary"]
    updated["contradiction_role_label"] = contradiction_role["contradiction_role_label"]
    updated["contradiction_role_summary"] = contradiction_role["contradiction_role_summary"]
    return updated


def accept_belief_update(
    *,
    belief_update_id: str,
    workspace_id: str,
    session_id: str = "",
    reviewed_by: str = "scientist",
    reviewed_by_user_id: str | None = None,
    governance_note: str = "",
) -> dict[str, Any]:
    return _govern_belief_update(
        belief_update_id=belief_update_id,
        workspace_id=workspace_id,
        session_id=session_id,
        governance_status=BeliefUpdateGovernanceStatus.accepted.value,
        reviewed_by=reviewed_by,
        reviewed_by_user_id=reviewed_by_user_id,
        governance_note=governance_note,
    )


def reject_belief_update(
    *,
    belief_update_id: str,
    workspace_id: str,
    session_id: str = "",
    reviewed_by: str = "scientist",
    reviewed_by_user_id: str | None = None,
    governance_note: str = "",
) -> dict[str, Any]:
    return _govern_belief_update(
        belief_update_id=belief_update_id,
        workspace_id=workspace_id,
        session_id=session_id,
        governance_status=BeliefUpdateGovernanceStatus.rejected.value,
        reviewed_by=reviewed_by,
        reviewed_by_user_id=reviewed_by_user_id,
        governance_note=governance_note,
    )


def supersede_belief_update(
    *,
    belief_update_id: str,
    workspace_id: str,
    session_id: str = "",
    reviewed_by: str = "scientist",
    reviewed_by_user_id: str | None = None,
    supersede_reason: str = "",
) -> dict[str, Any]:
    return _govern_belief_update(
        belief_update_id=belief_update_id,
        workspace_id=workspace_id,
        session_id=session_id,
        governance_status=BeliefUpdateGovernanceStatus.superseded.value,
        reviewed_by=reviewed_by,
        reviewed_by_user_id=reviewed_by_user_id,
        governance_note=supersede_reason,
    )


def list_session_belief_updates(session_id: str, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
    return belief_update_repository.list_belief_updates(session_id=session_id, workspace_id=workspace_id)


def belief_update_refs_from_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        contradiction_role = classify_belief_update_contradiction_role(record)
        refs.append(
            validate_belief_update_reference(
                {
                    "belief_update_id": record.get("belief_update_id"),
                    "claim_id": record.get("claim_id"),
                    "experiment_result_id": record.get("experiment_result_id"),
                    "candidate_id": record.get("candidate_id"),
                    "candidate_label": record.get("candidate_label"),
                    "previous_support_level": record.get("previous_support_level"),
                    "updated_support_level": record.get("updated_support_level"),
                    "update_direction": record.get("update_direction"),
                    "support_input_quality_label": (record.get("support_input_quality_label") or (record.get("metadata") or {}).get("support_input_quality_label")),
                    "support_input_quality_summary": (record.get("support_input_quality_summary") or (record.get("metadata") or {}).get("support_input_quality_summary")),
                    "assay_context_alignment_label": (record.get("assay_context_alignment_label") or (record.get("metadata") or {}).get("assay_context_alignment_label")),
                    "result_interpretation_basis": (record.get("result_interpretation_basis") or (record.get("metadata") or {}).get("result_interpretation_basis")),
                    "numeric_result_basis_label": (record.get("numeric_result_basis_label") or (record.get("metadata") or {}).get("numeric_result_basis_label")),
                    "numeric_result_basis_summary": (record.get("numeric_result_basis_summary") or (record.get("metadata") or {}).get("numeric_result_basis_summary")),
                    "numeric_result_resolution_label": (record.get("numeric_result_resolution_label") or (record.get("metadata") or {}).get("numeric_result_resolution_label")),
                    "numeric_result_interpretation_label": (record.get("numeric_result_interpretation_label") or (record.get("metadata") or {}).get("numeric_result_interpretation_label")),
                    "target_rule_alignment_label": (record.get("target_rule_alignment_label") or (record.get("metadata") or {}).get("target_rule_alignment_label")),
                    "support_quality_label": (record.get("support_quality_label") or (record.get("metadata") or {}).get("support_quality_label")),
                    "support_quality_summary": (record.get("support_quality_summary") or (record.get("metadata") or {}).get("support_quality_summary")),
                    "support_decision_usefulness_label": (record.get("support_decision_usefulness_label") or (record.get("metadata") or {}).get("support_decision_usefulness_label")),
                    "governed_support_posture_label": (
                        record.get("governed_support_posture_label")
                        or (record.get("metadata") or {}).get("governed_support_posture_label")
                        or classify_governed_support_posture(record).get("governed_support_posture_label")
                    ),
                    "governed_support_posture_summary": (
                        record.get("governed_support_posture_summary")
                        or (record.get("metadata") or {}).get("governed_support_posture_summary")
                        or classify_governed_support_posture(record).get("governed_support_posture_summary")
                    ),
                    "contradiction_role_label": (
                        record.get("contradiction_role_label")
                        or (record.get("metadata") or {}).get("contradiction_role_label")
                        or contradiction_role.get("contradiction_role_label")
                    ),
                    "contradiction_role_summary": (
                        record.get("contradiction_role_summary")
                        or (record.get("metadata") or {}).get("contradiction_role_summary")
                        or contradiction_role.get("contradiction_role_summary")
                    ),
                    "governance_status": record.get("governance_status"),
                    "chronology_label": record.get("chronology_label"),
                    "active_for_belief_state": record.get("active_for_belief_state"),
                    "created_at": record.get("created_at"),
                }
            )
        )
    return refs


def _support_basis_mix_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    observed_label_support_count = 0
    numeric_rule_based_support_count = 0
    unresolved_basis_count = 0
    weak_basis_count = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        interpretation_basis = _clean_text(record.get("result_interpretation_basis") or metadata.get("result_interpretation_basis"))
        support_input_quality_label = _clean_text(
            record.get("support_input_quality_label") or metadata.get("support_input_quality_label")
        )
        numeric_result_resolution_label = _clean_text(
            record.get("numeric_result_resolution_label") or metadata.get("numeric_result_resolution_label")
        )
        update_direction = _clean_text(record.get("update_direction"))
        if interpretation_basis == "Observed label":
            observed_label_support_count += 1
        elif interpretation_basis == "Numeric outcome under current target rule":
            numeric_rule_based_support_count += 1
        if support_input_quality_label == _WEAK_INPUT_LABEL:
            weak_basis_count += 1
        if (
            update_direction == BeliefUpdateDirection.unresolved.value
            or numeric_result_resolution_label == _NUMERIC_UNRESOLVED_LABEL
        ):
            unresolved_basis_count += 1

    total = len(records)
    if total <= 0:
        return {
            "support_basis_mix_label": "No support basis recorded",
            "support_basis_mix_summary": "No support-basis composition is recorded yet for this session.",
            "observed_label_support_count": 0,
            "numeric_rule_based_support_count": 0,
            "unresolved_basis_count": 0,
            "weak_basis_count": 0,
        }
    if (
        observed_label_support_count > 0
        and observed_label_support_count >= max(numeric_rule_based_support_count, unresolved_basis_count)
        and observed_label_support_count >= weak_basis_count
        and numeric_rule_based_support_count == 0
    ):
        label = "Grounded mostly in observed labels"
        summary = (
            f"Session support changes are grounded mostly in observed labels ({observed_label_support_count}), "
            f"with {numeric_rule_based_support_count} bounded numeric interpretation record{'s' if numeric_rule_based_support_count != 1 else ''} "
            f"and {unresolved_basis_count} unresolved support basis record{'s' if unresolved_basis_count != 1 else ''}."
        )
    elif (
        numeric_rule_based_support_count > 0
        and numeric_rule_based_support_count >= max(observed_label_support_count, unresolved_basis_count)
        and numeric_rule_based_support_count >= weak_basis_count
        and observed_label_support_count == 0
    ):
        label = "Includes bounded numeric interpretation"
        summary = (
            f"Session support changes rely mainly on bounded numeric interpretation under current target rules ({numeric_rule_based_support_count}), "
            f"with {observed_label_support_count} observed-label record{'s' if observed_label_support_count != 1 else ''} "
            f"and {unresolved_basis_count} unresolved support basis record{'s' if unresolved_basis_count != 1 else ''}."
        )
    elif unresolved_basis_count > 0 and unresolved_basis_count >= max(observed_label_support_count, numeric_rule_based_support_count):
        label = "Mostly unresolved or weak-basis"
        summary = (
            f"Session support changes remain largely tentative: {unresolved_basis_count} record{'s' if unresolved_basis_count != 1 else ''} "
            f"stay unresolved under the current basis and {weak_basis_count} carry weak interpretation basis labels."
        )
    else:
        label = "Mixed support basis"
        summary = (
            f"Session support changes use a mixed basis: {observed_label_support_count} observed-label, "
            f"{numeric_rule_based_support_count} numeric-rule-based, {unresolved_basis_count} unresolved, "
            f"and {weak_basis_count} weak-basis record{'s' if weak_basis_count != 1 else ''}."
        )
    return {
        "support_basis_mix_label": label,
        "support_basis_mix_summary": summary,
        "observed_label_support_count": observed_label_support_count,
        "numeric_rule_based_support_count": numeric_rule_based_support_count,
        "unresolved_basis_count": unresolved_basis_count,
        "weak_basis_count": weak_basis_count,
    }


def belief_update_summary_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    active = sum(1 for record in records if _active_for_belief_state(record.get("governance_status")))
    proposed = sum(
        1 for record in records if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.proposed.value
    )
    accepted = sum(
        1 for record in records if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.accepted.value
    )
    rejected = sum(
        1 for record in records if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.rejected.value
    )
    superseded = sum(
        1 for record in records if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
    )
    historical = rejected + superseded
    strengthened = sum(
        1 for record in records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.strengthened.value
    )
    weakened = sum(
        1 for record in records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.weakened.value
    )
    unresolved = sum(
        1 for record in records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.unresolved.value
    )
    numeric_interpreted = 0
    numeric_unresolved = 0
    for record in records:
        resolution_label = _clean_text(
            record.get("numeric_result_resolution_label") or (record.get("metadata") or {}).get("numeric_result_resolution_label")
        )
        if not resolution_label:
            continue
        if resolution_label == _NUMERIC_UNRESOLVED_LABEL:
            numeric_unresolved += 1
        else:
            numeric_interpreted += 1
    chronology_mix_label = "No governed support yet"
    chronology_summary_text = "No governed support-change records are recorded yet."
    if active > 0 and historical <= 0:
        chronology_mix_label = "Current support only"
        chronology_summary_text = (
            f"This session currently contributes {active} active governed support change"
            f"{'' if active == 1 else 's'} and no historical support records."
        )
    elif active > 0 and historical > 0:
        chronology_mix_label = "Current and historical support"
        chronology_summary_text = (
            f"This session contributes {active} active governed support change"
            f"{'' if active == 1 else 's'} alongside {historical} historical support record"
            f"{'' if historical == 1 else 's'}."
        )
    elif active <= 0 and superseded > 0 and rejected <= 0:
        chronology_mix_label = "Historical support only"
        chronology_summary_text = (
            f"This session currently contributes only {superseded} superseded historical support record"
            f"{'' if superseded == 1 else 's'}."
        )
    elif active <= 0 and rejected > 0 and superseded <= 0:
        chronology_mix_label = "Rejected support only"
        chronology_summary_text = (
            f"This session currently contributes only {rejected} rejected support change"
            f"{'' if rejected == 1 else 's'}."
        )
    elif active <= 0 and historical > 0:
        chronology_mix_label = "Historical or rejected support only"
        chronology_summary_text = (
            f"This session currently contributes no active governed support; {historical} historical support record"
            f"{'' if historical == 1 else 's'} remain visible."
        )
    if total:
        summary_text = (
            f"{total} belief update{'s' if total != 1 else ''} {'has' if total == 1 else 'have'} been recorded for this session. "
            f"{active} currently active, {superseded} superseded, and {rejected} rejected support change{'s' if total != 1 else ''} are currently recorded. "
            "These updates use observed labels, numeric outcomes under current target rules where available, result quality, and assay context where available. They do not prove claims, imply causality, or change the model."
        )
    else:
        summary_text = "No belief updates have been recorded."
    numeric_interpretation_summary_text = ""
    if numeric_interpreted or numeric_unresolved:
        numeric_interpretation_summary_text = (
            f"{numeric_interpreted} numeric result{'s' if numeric_interpreted != 1 else ''} {'was' if numeric_interpreted == 1 else 'were'} interpreted through the current target rule, "
            f"while {numeric_unresolved} numeric result{'s' if numeric_unresolved != 1 else ''} remained unresolved under the current numeric basis."
        )
    support_basis_mix = _support_basis_mix_from_records(records)
    active_records = [
        record
        for record in records
        if _active_for_belief_state(record.get("governance_status"))
    ]
    active_strengthened = sum(
        1 for record in active_records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.strengthened.value
    )
    active_weakened = sum(
        1 for record in active_records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.weakened.value
    )
    active_unresolved = sum(
        1 for record in active_records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.unresolved.value
    )
    posture_counts = rollup_governed_support_postures(
        [
            (record.get("governed_support_posture_label") or (record.get("metadata") or {}).get("governed_support_posture_label"))
            or classify_governed_support_posture(record).get("governed_support_posture_label")
            for record in records
        ]
    )
    historical_decision_useful_count = sum(
        1
        for record in records
        if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
        and (
            _clean_text(record.get("support_quality_label") or (record.get("metadata") or {}).get("support_quality_label"))
            or classify_belief_update_support_quality(record).get("support_quality_label")
        )
        == SUPPORT_QUALITY_DECISION_USEFUL
    )
    support_quality_counts = rollup_quality_labels(
        [
            (record.get("support_quality_label") or (record.get("metadata") or {}).get("support_quality_label"))
            or classify_belief_update_support_quality(record).get("support_quality_label")
            for record in active_records
        ]
    )
    if active <= 0:
        support_quality_label = "No active support quality yet"
        support_quality_summary = "No active governed support update is recorded yet for support-quality interpretation."
    elif support_quality_counts["decision_useful_count"] > 0 and support_quality_counts["weak_count"] <= 0 and support_quality_counts["context_limited_count"] <= 0:
        support_quality_label = "Current active support includes decision-useful grounding"
        support_quality_summary = (
            f"{support_quality_counts['decision_useful_count']} active support update"
            f"{'' if support_quality_counts['decision_useful_count'] == 1 else 's'} currently look more decision-useful for bounded follow-up."
        )
    elif support_quality_counts["weak_count"] >= max(
        support_quality_counts["decision_useful_count"],
        support_quality_counts["limited_count"],
        support_quality_counts["context_limited_count"],
    ) and support_quality_counts["weak_count"] > 0:
        support_quality_label = "Current active support remains weak or unresolved"
        support_quality_summary = (
            f"{support_quality_counts['weak_count']} active support update"
            f"{'' if support_quality_counts['weak_count'] == 1 else 's'} remain weak or unresolved under the current basis."
        )
    elif support_quality_counts["context_limited_count"] >= max(
        support_quality_counts["decision_useful_count"],
        support_quality_counts["limited_count"],
        support_quality_counts["weak_count"],
    ) and support_quality_counts["context_limited_count"] > 0:
        support_quality_label = "Current active support is context-limited"
        support_quality_summary = (
            f"{support_quality_counts['context_limited_count']} active support update"
            f"{'' if support_quality_counts['context_limited_count'] == 1 else 's'} still depend on assay or target-context clarification."
        )
    else:
        support_quality_label = "Current active support remains limited"
        support_quality_summary = (
            f"{support_quality_counts['limited_count']} active support update"
            f"{'' if support_quality_counts['limited_count'] == 1 else 's'} remain present but still limited for stronger follow-up."
        )
    if active <= 0:
        governed_support_posture_label = "No current posture-governing support"
        governed_support_posture_summary = (
            "No active governed support currently governs present posture for this session."
        )
    elif posture_counts["governing_count"] > 0:
        governed_support_posture_label = "Current support governs present posture"
        governed_support_posture_summary = (
            f"{posture_counts['governing_count']} accepted support update"
            f"{'' if posture_counts['governing_count'] == 1 else 's'} currently govern present posture for bounded follow-up."
        )
        if posture_counts["tentative_count"] > 0 or posture_counts["accepted_limited_count"] > 0:
            governed_support_posture_summary += (
                f" {posture_counts['tentative_count']} active update"
                f"{'' if posture_counts['tentative_count'] == 1 else 's'} still remain tentative and "
                f"{posture_counts['accepted_limited_count']} accepted update"
                f"{'' if posture_counts['accepted_limited_count'] == 1 else 's'} count only weakly."
            )
    elif posture_counts["accepted_limited_count"] > 0:
        governed_support_posture_label = "Accepted support remains limited-weight"
        governed_support_posture_summary = (
            f"{posture_counts['accepted_limited_count']} accepted support update"
            f"{'' if posture_counts['accepted_limited_count'] == 1 else 's'} remain too limited or context-limited to govern present posture strongly."
        )
    elif posture_counts["tentative_count"] > 0:
        governed_support_posture_label = "Current support remains tentative"
        governed_support_posture_summary = (
            f"{posture_counts['tentative_count']} active support update"
            f"{'' if posture_counts['tentative_count'] == 1 else 's'} remain proposed, so current posture should stay cautious."
        )
    else:
        governed_support_posture_label = "Historical support only"
        governed_support_posture_summary = (
            "Only historical or otherwise non-posture-governing support remains visible for this session."
        )
    if historical_decision_useful_count > 0 and posture_counts["governing_count"] <= 0:
        governed_support_posture_summary += (
            f" {historical_decision_useful_count} superseded support record"
            f"{'' if historical_decision_useful_count == 1 else 's'} previously looked more decision-useful, but now remain historical context only."
        )
    coherence = assess_support_coherence(
        active_count=active,
        accepted_count=accepted,
        strengthened_count=active_strengthened,
        weakened_count=active_weakened,
        unresolved_count=active_unresolved,
        support_quality_counts=support_quality_counts,
        posture_counts=posture_counts,
        historical_decision_useful_count=historical_decision_useful_count,
        superseded_count=superseded,
    )
    return validate_belief_update_summary(
        {
            "update_count": total,
            "active_count": active,
            "historical_count": historical,
            "proposed_count": proposed,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "superseded_count": superseded,
            "strengthened_count": strengthened,
            "weakened_count": weakened,
            "unresolved_count": unresolved,
            "numeric_interpreted_count": numeric_interpreted,
            "numeric_unresolved_count": numeric_unresolved,
            "observed_label_support_count": support_basis_mix["observed_label_support_count"],
            "numeric_rule_based_support_count": support_basis_mix["numeric_rule_based_support_count"],
            "unresolved_basis_count": support_basis_mix["unresolved_basis_count"],
            "weak_basis_count": support_basis_mix["weak_basis_count"],
            "support_basis_mix_label": support_basis_mix["support_basis_mix_label"],
            "support_basis_mix_summary": support_basis_mix["support_basis_mix_summary"],
            "support_quality_label": support_quality_label,
            "support_quality_summary": support_quality_summary,
            "decision_useful_active_support_count": support_quality_counts["decision_useful_count"],
            "active_but_limited_support_count": support_quality_counts["limited_count"],
            "context_limited_active_support_count": support_quality_counts["context_limited_count"],
            "weak_or_unresolved_active_support_count": support_quality_counts["weak_count"],
            "governed_support_posture_label": governed_support_posture_label,
            "governed_support_posture_summary": governed_support_posture_summary,
            "posture_governing_support_count": posture_counts["governing_count"],
            "tentative_active_support_count": posture_counts["tentative_count"],
            "accepted_limited_weight_support_count": posture_counts["accepted_limited_count"],
            "historical_non_governing_support_count": posture_counts["historical_count"],
            "support_coherence_label": coherence["support_coherence_label"],
            "support_coherence_summary": coherence["support_coherence_summary"],
            "support_reuse_label": coherence["support_reuse_label"],
            "support_reuse_summary": coherence["support_reuse_summary"],
            "contradiction_pressure_count": coherence["contradiction_pressure_count"],
            "weakly_reusable_support_count": coherence["weakly_reusable_support_count"],
            "current_support_contested_flag": coherence["current_support_contested_flag"],
            "current_posture_degraded_flag": coherence["current_posture_degraded_flag"],
            "historical_support_stronger_than_current_flag": coherence["historical_support_stronger_than_current_flag"],
            "numeric_interpretation_summary_text": numeric_interpretation_summary_text,
            "chronology_mix_label": chronology_mix_label,
            "chronology_summary_text": chronology_summary_text,
            "summary_text": summary_text,
            "top_updates": belief_update_refs_from_records(records[:3]),
        }
    )


def support_role_from_belief_update_summary(summary: dict[str, Any] | None) -> tuple[str, str]:
    summary = summary if isinstance(summary, dict) else {}
    active = int(summary.get("active_count") or 0)
    superseded = int(summary.get("superseded_count") or 0)
    rejected = int(summary.get("rejected_count") or 0)
    historical = int(summary.get("historical_count") or 0)
    if active > 0:
        posture_governing = int(summary.get("posture_governing_support_count") or 0)
        accepted_limited = int(summary.get("accepted_limited_weight_support_count") or 0)
        tentative_active = int(summary.get("tentative_active_support_count") or 0)
        decision_useful_active = int(summary.get("decision_useful_active_support_count") or 0)
        context_limited_active = int(summary.get("context_limited_active_support_count") or 0)
        weak_active = int(summary.get("weak_or_unresolved_active_support_count") or 0)
        limited_active = int(summary.get("active_but_limited_support_count") or 0)
        contradiction_pressure = int(summary.get("contradiction_pressure_count") or 0)
        contested = bool(summary.get("current_support_contested_flag"))
        degraded = bool(summary.get("current_posture_degraded_flag"))
        historical_stronger = bool(summary.get("historical_support_stronger_than_current_flag"))
        if contested and degraded:
            return (
                "Contributed contested and degraded current support",
                "This session contributes active support, but mixed or weakening updates now apply contradiction pressure and reduce how strongly that support should shape present posture.",
            )
        if degraded or historical_stronger:
            return (
                "Contributed degraded current support",
                "This session contributes active support, but weakening evidence or stronger superseded history means present posture should be treated as degraded rather than cleanly strong.",
            )
        if contested or contradiction_pressure > 0:
            return (
                "Contributed contested current support",
                "This session contributes active support, but mixed or unresolved updates keep the current picture contested and more clarification-heavy.",
            )
        if posture_governing > 0:
            return (
                "Contributed posture-governing current support",
                "This session contributes accepted support that is strong enough to help govern present posture for bounded follow-up, while still remaining bounded rather than final truth.",
            )
        if accepted_limited > 0:
            return (
                "Contributed accepted but limited current support",
                "This session contributes accepted support, but its limited or context-limited basis means it should count only weakly in present posture.",
            )
        if tentative_active > 0:
            return (
                "Contributed tentative current support",
                "This session contributes active support, but that support remains proposed and should stay tentative in present posture.",
            )
        if decision_useful_active > 0 and weak_active <= 0 and context_limited_active <= 0:
            return (
                "Contributed decision-useful current support",
                "This session contributes active governed support that is currently more decision-useful for bounded follow-up, while still remaining bounded rather than final truth.",
            )
        if weak_active > 0 and weak_active >= max(decision_useful_active, context_limited_active, limited_active):
            return (
                "Contributed weak current support",
                "This session contributes active governed support, but most of that current support remains weak or unresolved under the available basis.",
            )
        if context_limited_active > 0 and context_limited_active >= max(decision_useful_active, limited_active, weak_active):
            return (
                "Contributed context-limited current support",
                "This session contributes active governed support, but assay or target-context limitations keep it from being strongly decision-useful yet.",
            )
        if historical > 0:
            return (
                "Contributed current support",
                "This session currently contributes governed support to the active target-scoped picture and also carries historical support records for context.",
            )
        return (
            "Contributed current support",
            "This session currently contributes governed support to the active target-scoped picture.",
        )
    if superseded > 0 and rejected <= 0:
        return (
            "Contributed historical support",
            "This session currently contributes only superseded historical support records, not active governed support.",
        )
    if rejected > 0 and superseded <= 0:
        return (
            "Rejected support only",
            "This session currently contributes only rejected support-change records, so it does not shape the active support picture.",
        )
    if historical > 0:
        return (
            "Historical support only",
            "This session contributes historical support records only and does not currently shape the active support picture.",
        )
    return (
        "No governed support yet",
        "This session does not currently contribute a governed support-change record.",
    )


def attach_belief_updates_to_scientific_session_truth(
    scientific_truth: dict[str, Any],
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(scientific_truth, dict):
        return scientific_truth
    updated = dict(scientific_truth)
    updated["belief_update_refs"] = belief_update_refs_from_records(updates)
    updated["belief_update_summary"] = belief_update_summary_from_records(updates)
    return validate_scientific_session_truth(updated)


__all__ = [
    "accept_belief_update",
    "attach_belief_updates_to_scientific_session_truth",
    "belief_update_refs_from_records",
    "belief_update_summary_from_records",
    "build_belief_update_record",
    "create_belief_update",
    "list_session_belief_updates",
    "reject_belief_update",
    "support_role_from_belief_update_summary",
    "supersede_belief_update",
]
