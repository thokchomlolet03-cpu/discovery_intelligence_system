from __future__ import annotations

from typing import Any

from system.contracts import (
    ControlledReuseState,
    EvidenceActivationPolicy,
    EvidenceFutureUse,
    EvidenceScope,
    EvidenceSupportLevel,
    EvidenceTruthStatus,
    EvidenceType,
    EvidenceUse,
    ModelingMode,
    ReviewStatus,
    TargetKind,
    validate_evidence_activation_policy,
    validate_evidence_record,
    validate_scientific_session_truth,
)
from system.db.repositories import ArtifactRepository, SessionRepository
from system.services.artifact_service import uploaded_session_dir, write_json_log
from system.services.claim_service import claim_refs_from_records, claims_summary_from_records, list_session_claims
from system.services.experiment_request_service import (
    experiment_request_refs_from_records,
    experiment_request_summary_from_records,
    list_session_experiment_requests,
)
from system.services.experiment_result_service import (
    experiment_result_refs_from_records,
    experiment_result_summary_from_records,
    list_session_experiment_results,
)
from system.services.belief_update_service import (
    belief_update_refs_from_records,
    belief_update_summary_from_records,
    list_session_belief_updates,
)
from system.services.belief_state_service import (
    belief_state_reference_from_record,
    belief_state_summary_from_record,
    get_belief_state_for_target,
)
from system.services.run_metadata_service import build_run_provenance
from system.services.session_identity_service import build_session_identity


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _support_level(count: int, *, strong_threshold: int = 12, moderate_threshold: int = 4) -> str:
    if count >= strong_threshold:
        return EvidenceSupportLevel.strong.value
    if count >= moderate_threshold:
        return EvidenceSupportLevel.moderate.value
    if count > 0:
        return EvidenceSupportLevel.limited.value
    return EvidenceSupportLevel.contextual.value


def _label_source(target_definition: dict[str, Any], run_contract: dict[str, Any], measurement_summary: dict[str, Any]) -> str:
    return _clean_text(
        run_contract.get("label_source")
        or measurement_summary.get("label_source")
        or target_definition.get("label_source")
    ).lower()


def _candidate_count(decision_payload: dict[str, Any]) -> int:
    summary = decision_payload.get("summary") if isinstance(decision_payload, dict) else {}
    if isinstance(summary, dict):
        count = _safe_int(summary.get("candidate_count"), default=-1)
        if count >= 0:
            return count
    rows = decision_payload.get("top_experiments") if isinstance(decision_payload, dict) else []
    return len(rows) if isinstance(rows, list) else 0


def _human_review_count(review_summary: dict[str, Any]) -> int:
    counts = review_summary.get("counts") if isinstance(review_summary.get("counts"), dict) else {}
    return sum(
        _safe_int(counts.get(status), 0)
        for status in (
            ReviewStatus.under_review.value,
            ReviewStatus.approved.value,
            ReviewStatus.rejected.value,
            ReviewStatus.tested.value,
            ReviewStatus.ingested.value,
        )
    )


def _join_names(names: list[str]) -> str:
    cleaned = [_clean_text(name) for name in names if _clean_text(name)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _join_sentence(names: list[str], default: str = "Not recorded") -> str:
    cleaned = [_clean_text(name) for name in names if _clean_text(name)]
    if not cleaned:
        return default
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def build_evidence_records(
    *,
    target_definition: dict[str, Any],
    modeling_mode: str,
    run_contract: dict[str, Any],
    analysis_report: dict[str, Any],
    decision_payload: dict[str, Any],
    review_summary: dict[str, Any],
    workspace_memory: dict[str, Any] | None = None,
    feedback_store: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    target_kind = _clean_text(target_definition.get("target_kind"), default=TargetKind.classification.value).lower()
    target_name = _clean_text(target_definition.get("target_name"), default="the session target")
    measurement_summary = analysis_report.get("measurement_summary") if isinstance(analysis_report.get("measurement_summary"), dict) else {}
    rows_with_values = _safe_int(measurement_summary.get("rows_with_values"), 0)
    rows_with_labels = _safe_int(measurement_summary.get("rows_with_labels"), 0)
    label_source = _label_source(target_definition, run_contract, measurement_summary)
    feature_signature = _clean_text(run_contract.get("feature_signature"))
    reference_basis = run_contract.get("reference_basis") if isinstance(run_contract.get("reference_basis"), dict) else {}
    candidate_count = _candidate_count(decision_payload)

    if rows_with_values > 0:
        records.append(
            validate_evidence_record(
                {
                    "name": "Observed experimental values",
                    "evidence_type": EvidenceType.experimental_value.value,
                    "truth_status": EvidenceTruthStatus.observed.value,
                    "source": "uploaded_dataset",
                    "scope": EvidenceScope.session_input.value,
                    "support_level": _support_level(rows_with_values),
                    "current_use": EvidenceUse.active_modeling.value,
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": (
                        f"{rows_with_values} uploaded rows include observed numeric values. "
                        f"These values are active modeling evidence for {target_name}, not model output."
                    ),
                }
            )
        )

    if rows_with_labels > 0 and target_kind == TargetKind.classification.value:
        derived = label_source == "derived"
        records.append(
            validate_evidence_record(
                {
                    "name": "Derived class labels" if derived else "Observed binary labels",
                    "evidence_type": EvidenceType.derived_label.value if derived else EvidenceType.binary_label.value,
                    "truth_status": EvidenceTruthStatus.derived.value if derived else EvidenceTruthStatus.observed.value,
                    "source": "label_builder" if derived else "uploaded_dataset",
                    "scope": EvidenceScope.session_input.value,
                    "support_level": _support_level(rows_with_labels),
                    "current_use": EvidenceUse.active_modeling.value,
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": (
                        f"{rows_with_labels} rows carry {'derived' if derived else 'observed'} class evidence. "
                        f"{'Derived labels are a transformation of measured data, not raw observation.' if derived else 'These labels directly support the current classification path.'}"
                    ),
                }
            )
        )

    if feature_signature and feature_signature != "not_recorded":
        records.append(
            validate_evidence_record(
                {
                    "name": "Computed chemistry features",
                    "evidence_type": EvidenceType.chemistry_feature.value,
                    "truth_status": EvidenceTruthStatus.computed.value,
                    "source": feature_signature,
                    "scope": EvidenceScope.session_input.value,
                    "support_level": EvidenceSupportLevel.contextual.value,
                    "current_use": (
                        EvidenceUse.active_modeling.value
                        if modeling_mode != ModelingMode.ranking_only.value
                        else EvidenceUse.active_ranking.value
                    ),
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": "RDKit descriptors and Morgan fingerprints are computed inputs to the current model or ranking workflow.",
                }
            )
        )

    if reference_basis:
        novelty_reference = _clean_text(reference_basis.get("novelty_reference"), default="reference_dataset_similarity")
        applicability_reference = _clean_text(reference_basis.get("applicability_reference"), default="reference_dataset_similarity")
        records.append(
            validate_evidence_record(
                {
                    "name": "Retrieved reference chemistry context",
                    "evidence_type": EvidenceType.reference_context.value,
                    "truth_status": EvidenceTruthStatus.retrieved.value,
                    "source": f"novelty={novelty_reference}; applicability={applicability_reference}",
                    "scope": EvidenceScope.reference_corpus.value,
                    "support_level": EvidenceSupportLevel.contextual.value,
                    "current_use": EvidenceUse.active_ranking.value,
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": "Reference-dataset similarity currently drives novelty and applicability support; it is retrieved context, not observed experimental truth.",
                }
            )
        )

    if modeling_mode != ModelingMode.ranking_only.value and candidate_count > 0:
        prediction_name = "Predicted continuous values" if target_kind == TargetKind.regression.value else "Predicted class judgments"
        records.append(
            validate_evidence_record(
                {
                    "name": prediction_name,
                    "evidence_type": EvidenceType.model_prediction.value,
                    "truth_status": EvidenceTruthStatus.predicted.value,
                    "source": _clean_text(run_contract.get("selected_model_name"), default="session_model"),
                    "scope": EvidenceScope.session_output.value,
                    "support_level": EvidenceSupportLevel.contextual.value,
                    "current_use": EvidenceUse.active_ranking.value,
                    "future_use": EvidenceFutureUse.none.value,
                    "active_in_live_pipeline": True,
                    "summary": (
                        "Model predictions are used to rank candidates, but they remain predictions rather than observed truth."
                    ),
                }
            )
        )

    human_review_count = _human_review_count(review_summary)
    if human_review_count > 0:
        records.append(
            validate_evidence_record(
                {
                    "name": "Human review outcomes",
                    "evidence_type": EvidenceType.human_review.value,
                    "truth_status": EvidenceTruthStatus.reviewed.value,
                    "source": "review_events",
                    "scope": EvidenceScope.session_summary.value,
                    "support_level": _support_level(human_review_count, strong_threshold=6, moderate_threshold=2),
                    "current_use": EvidenceUse.interpretation_only.value,
                    "future_use": EvidenceFutureUse.may_inform_future_learning.value,
                    "active_in_live_pipeline": False,
                    "summary": (
                        f"{human_review_count} human review outcome{'s' if human_review_count != 1 else ''} are stored for interpretation and continuity. "
                        "They do not automatically retrain the live model today."
                    ),
                }
            )
        )

    workspace_memory = workspace_memory if isinstance(workspace_memory, dict) else {}
    matched_memory = _safe_int(workspace_memory.get("matched_candidate_count"), 0)
    if matched_memory > 0:
        records.append(
            validate_evidence_record(
                {
                    "name": "Workspace feedback memory",
                    "evidence_type": EvidenceType.workspace_memory.value,
                    "truth_status": EvidenceTruthStatus.retrieved.value,
                    "source": "workspace_review_history",
                    "scope": EvidenceScope.workspace_history.value,
                    "support_level": _support_level(matched_memory, strong_threshold=5, moderate_threshold=2),
                    "current_use": EvidenceUse.memory_only.value,
                    "future_use": EvidenceFutureUse.may_inform_future_learning.value,
                    "active_in_live_pipeline": False,
                    "summary": (
                        f"{matched_memory} current shortlist candidate{'s' if matched_memory != 1 else ''} have prior workspace feedback. "
                        "This memory changes interpretation and continuity, not live model weights."
                    ),
                }
            )
        )

    feedback_store = feedback_store if isinstance(feedback_store, dict) else {}
    queued_rows = _safe_int(feedback_store.get("queued_rows"), 0)
    if bool(feedback_store.get("consent_learning")) and queued_rows > 0:
        records.append(
            validate_evidence_record(
                {
                    "name": "Queued learning evidence",
                    "evidence_type": EvidenceType.learning_queue.value,
                    "truth_status": EvidenceTruthStatus.observed.value if label_source != "derived" else EvidenceTruthStatus.derived.value,
                    "source": "explicit_learning_queue",
                    "scope": EvidenceScope.session_summary.value,
                    "support_level": _support_level(queued_rows, strong_threshold=12, moderate_threshold=4),
                    "current_use": EvidenceUse.stored_not_active.value,
                    "future_use": EvidenceFutureUse.may_inform_future_learning.value,
                    "active_in_live_pipeline": False,
                    "summary": (
                        f"{queued_rows} consented labeled row{'s' if queued_rows != 1 else ''} were stored in the explicit learning queue. "
                        "They are not automatically consumed by the live decision pipeline yet."
                    ),
                }
            )
        )

    return records


def build_evidence_loop_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    modeling = [item["name"] for item in records if item.get("current_use") == EvidenceUse.active_modeling.value]
    ranking = [item["name"] for item in records if item.get("current_use") == EvidenceUse.active_ranking.value]
    interpretation = [item["name"] for item in records if item.get("current_use") == EvidenceUse.interpretation_only.value]
    memory = [item["name"] for item in records if item.get("current_use") == EvidenceUse.memory_only.value]
    stored = [item["name"] for item in records if item.get("current_use") == EvidenceUse.stored_not_active.value]
    future_activation = [
        item["name"]
        for item in records
        if item.get("future_use") in {
            EvidenceFutureUse.may_inform_future_ranking.value,
            EvidenceFutureUse.may_inform_future_learning.value,
        }
    ]

    active_parts: list[str] = []
    if modeling:
        active_parts.append("modeling evidence from " + ", ".join(modeling))
    if ranking:
        active_parts.append("ranking context from " + ", ".join(ranking))
    if not active_parts:
        active_parts.append("policy-level ordering with limited explicit evidence inputs")

    summary = "Current recommendations use " + " and ".join(active_parts) + "."
    if interpretation or memory or stored:
        post_run_bits: list[str] = []
        if interpretation:
            post_run_bits.append("review evidence changes interpretation")
        if memory:
            post_run_bits.append("workspace carryover remains memory-only")
        if stored:
            post_run_bits.append("queued learning evidence is stored but not live")
        summary = f"{summary} " + "; ".join(post_run_bits).capitalize() + "."

    learning_boundary_note = (
        "Observed upload values and labels can drive the active model path. Review outcomes, workspace feedback, and queued learning rows are stored explicitly, but they do not automatically retrain or rerank the live pipeline yet."
    )
    boundary_bits: list[str] = []
    if modeling:
        boundary_bits.append(f"Active modeling uses {_join_names(modeling)}")
    if ranking:
        boundary_bits.append(f"active ranking context uses {_join_names(ranking)}")
    if interpretation:
        boundary_bits.append(f"{_join_names(interpretation)} remain interpretation-only")
    if memory:
        boundary_bits.append(f"{_join_names(memory)} remain memory-only")
    if stored:
        boundary_bits.append(f"{_join_names(stored)} are stored but not active")
    activation_boundary_summary = ". ".join(bit[:1].upper() + bit[1:] if bit else "" for bit in boundary_bits if bit)
    if activation_boundary_summary:
        activation_boundary_summary = activation_boundary_summary.rstrip(".") + "."
    if future_activation:
        future_note = f"Future activation candidates: {_join_names(future_activation)}."
        activation_boundary_summary = (
            f"{activation_boundary_summary} {future_note}".strip()
            if activation_boundary_summary
            else future_note
        )

    return {
        "summary": summary,
        "learning_boundary_note": learning_boundary_note,
        "activation_boundary_summary": activation_boundary_summary,
        "active_modeling_evidence": modeling,
        "active_ranking_evidence": ranking,
        "interpretation_only_evidence": interpretation,
        "memory_only_evidence": memory,
        "stored_not_active_evidence": stored,
        "future_activation_candidates": future_activation,
    }


def build_evidence_activation_policy(records: list[dict[str, Any]]) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    for item in records:
        evidence_type = _clean_text(item.get("evidence_type")).lower()
        current_use = _clean_text(item.get("current_use")).lower()
        future_use = _clean_text(item.get("future_use")).lower()
        name = _clean_text(item.get("name"), default="Evidence")
        support_level = _clean_text(item.get("support_level")).lower()
        truth_status = _clean_text(item.get("truth_status")).lower()

        model_training_allowed = current_use == EvidenceUse.active_modeling.value
        ranking_context_allowed = current_use == EvidenceUse.active_ranking.value
        interpretation_allowed = current_use in {
            EvidenceUse.interpretation_only.value,
            EvidenceUse.memory_only.value,
        } or evidence_type == EvidenceType.model_prediction.value
        comparison_allowed = evidence_type in {
            EvidenceType.experimental_value.value,
            EvidenceType.binary_label.value,
            EvidenceType.derived_label.value,
            EvidenceType.reference_context.value,
            EvidenceType.model_prediction.value,
            EvidenceType.human_review.value,
            EvidenceType.workspace_memory.value,
        }
        eligible_for_future_learning = future_use == EvidenceFutureUse.may_inform_future_learning.value
        memory_only = current_use == EvidenceUse.memory_only.value
        stored_only = current_use == EvidenceUse.stored_not_active.value
        currently_active = current_use in {
            EvidenceUse.active_modeling.value,
            EvidenceUse.active_ranking.value,
            EvidenceUse.interpretation_only.value,
            EvidenceUse.memory_only.value,
        }
        eligible_for_recommendation_reuse = False
        eligible_for_ranking_context = False
        requires_stronger_validation = False
        permanently_non_active = False
        ineligibility_reason = ""

        if evidence_type == EvidenceType.experimental_value.value:
            eligible_for_recommendation_reuse = True
            eligible_for_ranking_context = True
            eligible_for_future_learning = True
            requires_stronger_validation = support_level == EvidenceSupportLevel.limited.value
        elif evidence_type == EvidenceType.binary_label.value:
            eligible_for_recommendation_reuse = True
            eligible_for_ranking_context = True
            eligible_for_future_learning = True
            requires_stronger_validation = support_level == EvidenceSupportLevel.limited.value
        elif evidence_type == EvidenceType.derived_label.value:
            eligible_for_recommendation_reuse = True
            eligible_for_ranking_context = True
            eligible_for_future_learning = True
            requires_stronger_validation = True
            if truth_status == EvidenceTruthStatus.derived.value:
                ineligibility_reason = (
                    "Derived labels can support later activation only after stronger validation against observed outcomes."
                )
        elif evidence_type == EvidenceType.human_review.value:
            eligible_for_recommendation_reuse = True
            eligible_for_ranking_context = True
            eligible_for_future_learning = False
            requires_stronger_validation = True
            ineligibility_reason = (
                "Human review can support conservative reuse and continuity framing, but it is not automated model-learning evidence."
            )
        elif evidence_type == EvidenceType.learning_queue.value:
            eligible_for_future_learning = True
            requires_stronger_validation = truth_status == EvidenceTruthStatus.derived.value or support_level == EvidenceSupportLevel.limited.value
            if requires_stronger_validation:
                ineligibility_reason = (
                    "Queued learning evidence needs stronger validation before any future activation beyond storage."
                )
        elif evidence_type == EvidenceType.workspace_memory.value:
            eligible_for_future_learning = False
            permanently_non_active = True
            ineligibility_reason = (
                "Workspace memory is a continuity layer over prior review history, not standalone scientific learning evidence."
            )
        elif evidence_type == EvidenceType.model_prediction.value:
            eligible_for_future_learning = False
            permanently_non_active = True
            ineligibility_reason = "Predicted outputs are not observed truth and are not eligible as future learning evidence."
        elif evidence_type == EvidenceType.reference_context.value:
            eligible_for_future_learning = False
            permanently_non_active = True
            ineligibility_reason = (
                "Retrieved reference similarity is contextual support, not reusable empirical outcome evidence."
            )
        elif evidence_type == EvidenceType.chemistry_feature.value:
            eligible_for_future_learning = False
            permanently_non_active = True
            ineligibility_reason = (
                "Computed chemistry features are model inputs, not independent outcome evidence for future activation."
            )

        if not ineligibility_reason:
            if not eligible_for_future_learning and not model_training_allowed and not ranking_context_allowed and not interpretation_allowed:
                ineligibility_reason = "This evidence is recorded for traceability, not for stronger future activation."
            elif permanently_non_active:
                ineligibility_reason = "This evidence remains limited to its current contextual role."
        future_learning_eligible = eligible_for_future_learning

        activation_bits: list[str] = []
        if model_training_allowed:
            activation_bits.append("active in the current model path")
        if ranking_context_allowed:
            activation_bits.append("active in ranking context")
        if interpretation_allowed and not memory_only:
            activation_bits.append("active for recommendation interpretation")
        if comparison_allowed:
            activation_bits.append("available for comparison/read-across")
        if future_learning_eligible:
            activation_bits.append("eligible for future learning activation")
        if memory_only:
            activation_bits.append("memory-only")
        if stored_only:
            activation_bits.append("stored but not active")
        if not activation_bits:
            activation_bits.append("recorded without an active role")

        eligibility_bits: list[str] = []
        if eligible_for_recommendation_reuse:
            eligibility_bits.append("eligible for conservative recommendation reuse")
        if eligible_for_ranking_context:
            eligibility_bits.append("eligible for future ranking-context reuse")
        if eligible_for_future_learning:
            eligibility_bits.append("eligible for future learning consideration")
        if requires_stronger_validation:
            eligibility_bits.append("requires stronger validation before stronger activation")
        if permanently_non_active:
            eligibility_bits.append("not eligible for stronger future activation")
        if not eligibility_bits:
            eligibility_bits.append("not currently eligible for stronger future activation")

        rules.append(
            {
                "evidence_type": evidence_type,
                "name": name,
                "model_training_allowed": model_training_allowed,
                "ranking_context_allowed": ranking_context_allowed,
                "interpretation_allowed": interpretation_allowed,
                "comparison_allowed": comparison_allowed,
                "future_learning_eligible": future_learning_eligible,
                "eligible_for_recommendation_reuse": eligible_for_recommendation_reuse,
                "eligible_for_ranking_context": eligible_for_ranking_context,
                "eligible_for_future_learning": eligible_for_future_learning,
                "requires_stronger_validation": requires_stronger_validation,
                "memory_only": memory_only,
                "stored_only": stored_only,
                "permanently_non_active": permanently_non_active,
                "currently_active": currently_active,
                "ineligibility_reason": ineligibility_reason,
                "activation_summary": f"{name} is currently " + ", ".join(activation_bits) + ".",
                "eligibility_summary": f"{name} is " + ", ".join(eligibility_bits) + ".",
            }
        )

    ranking_names = [rule["name"] for rule in rules if rule["ranking_context_allowed"]]
    interpretation_names = [rule["name"] for rule in rules if rule["interpretation_allowed"]]
    learning_names = [rule["name"] for rule in rules if rule["future_learning_eligible"]]
    recommendation_reuse_names = [rule["name"] for rule in rules if rule["eligible_for_recommendation_reuse"]]
    future_ranking_names = [rule["name"] for rule in rules if rule["eligible_for_ranking_context"]]
    future_learning_names = [rule["name"] for rule in rules if rule["eligible_for_future_learning"]]
    permanently_non_active_names = [rule["name"] for rule in rules if rule["permanently_non_active"]]
    validation_required_names = [rule["name"] for rule in rules if rule["requires_stronger_validation"]]
    stored_names = [rule["name"] for rule in rules if rule["stored_only"]]

    summary_parts: list[str] = []
    if ranking_names:
        summary_parts.append(f"Ranking context currently uses {_join_sentence(ranking_names)}")
    if interpretation_names:
        summary_parts.append(f"recommendation interpretation uses {_join_sentence(interpretation_names)}")
    if recommendation_reuse_names:
        summary_parts.append(f"conservative recommendation reuse is currently eligible for {_join_sentence(recommendation_reuse_names)}")
    if future_learning_names:
        summary_parts.append(f"future learning eligibility is limited to {_join_sentence(future_learning_names)}")
    if permanently_non_active_names:
        summary_parts.append(f"{_join_sentence(permanently_non_active_names)} remain non-active beyond their current contextual role")
    if stored_names:
        summary_parts.append(f"{_join_sentence(stored_names)} remain stored but inactive")
    summary = ". ".join(part[:1].upper() + part[1:] if part else "" for part in summary_parts if part)
    if summary:
        summary = summary.rstrip(".") + "."

    return validate_evidence_activation_policy(
        {
            "summary": summary,
            "ranking_context_summary": (
                f"Active ranking context is currently limited to {_join_sentence(ranking_names)}."
                if ranking_names
                else "No explicit ranking-context evidence is recorded."
            ),
            "interpretation_summary": (
                f"Recommendation interpretation currently uses {_join_sentence(interpretation_names)}."
                if interpretation_names
                else "No explicit interpretation-only evidence is recorded."
            ),
            "recommendation_reuse_summary": (
                f"Conservative recommendation reuse is currently eligible for {_join_sentence(recommendation_reuse_names)}."
                if recommendation_reuse_names
                else "No evidence is currently marked as eligible for recommendation reuse."
            ),
            "future_ranking_context_summary": (
                f"Future ranking-context reuse is currently limited to {_join_sentence(future_ranking_names)}."
                if future_ranking_names
                else "No evidence is currently marked as eligible for future ranking-context reuse."
            ),
            "learning_eligibility_summary": (
                f"Only {_join_sentence(learning_names)} are currently eligible for future learning activation."
                if learning_names
                else "No evidence is currently marked as future-learning eligible."
            ),
            "future_learning_eligibility_summary": (
                f"Future learning consideration is currently limited to {_join_sentence(future_learning_names)}."
                if future_learning_names
                else "No evidence is currently marked as eligible for future learning consideration."
            ),
            "stored_only_summary": (
                f"{_join_sentence(stored_names)} are stored but not active in the live pipeline."
                if stored_names
                else "No stored-only evidence is recorded."
            ),
            "permanently_non_active_summary": (
                f"{_join_sentence(permanently_non_active_names)} are not eligible for stronger future activation."
                if permanently_non_active_names
                else "No evidence is currently marked as permanently non-active."
            ),
            "rules": rules,
        }
    )


def build_controlled_reuse_state(
    *,
    evidence_activation_policy: dict[str, Any] | None,
    workspace_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence_activation_policy = evidence_activation_policy if isinstance(evidence_activation_policy, dict) else {}
    workspace_memory = workspace_memory if isinstance(workspace_memory, dict) else {}
    rules = evidence_activation_policy.get("rules") if isinstance(evidence_activation_policy.get("rules"), list) else []
    human_review_rule = next(
        (
            item
            for item in rules
            if _clean_text(item.get("evidence_type")).lower() == EvidenceType.human_review.value
        ),
        {},
    )
    matched_candidate_count = _safe_int(workspace_memory.get("matched_candidate_count"), 0)
    status_counts = workspace_memory.get("status_counts") if isinstance(workspace_memory.get("status_counts"), dict) else {}
    reusable_count = sum(_safe_int(status_counts.get(key), 0) for key in ("approved", "tested", "ingested"))
    stronger_count = sum(_safe_int(status_counts.get(key), 0) for key in ("tested", "ingested"))

    recommendation_reuse_active = bool(human_review_rule.get("eligible_for_recommendation_reuse")) and reusable_count > 0
    ranking_context_reuse_active = bool(human_review_rule.get("eligible_for_ranking_context")) and (
        stronger_count > 0 or reusable_count >= 2
    )
    interpretation_support_active = matched_candidate_count > 0

    reused_evidence = ["Human review outcomes"] if recommendation_reuse_active or ranking_context_reuse_active else []
    support_carriers = ["Workspace feedback memory"] if interpretation_support_active else []

    if recommendation_reuse_active:
        recommendation_reuse_summary = (
            f"Recommendation reuse is active for {matched_candidate_count} shortlist candidate"
            f"{'' if matched_candidate_count == 1 else 's'} because prior human review outcomes met the current reuse rule. "
            "This supports continuity across sessions without retraining the model."
        )
    else:
        recommendation_reuse_summary = (
            "No prior human review outcome is currently active for recommendation reuse in this session."
        )

    if ranking_context_reuse_active:
        ranking_context_reuse_summary = (
            "Ranking-context reuse is active for shortlist framing because prior human review outcomes provide stronger reusable continuity context. "
            "This does not change model outputs or weights."
        )
    else:
        ranking_context_reuse_summary = "No prior evidence is currently active for ranking-context reuse in this session."

    if interpretation_support_active:
        interpretation_support_summary = (
            f"Workspace feedback memory remains active as interpretation support for {matched_candidate_count} matched shortlist candidate"
            f"{'' if matched_candidate_count == 1 else 's'}."
        )
    else:
        interpretation_support_summary = "No matched prior workspace feedback is active for interpretation support in this session."

    inactive_boundary_summary = (
        "Workspace memory remains a continuity carrier only. Reuse-support signals do not retrain the model, replace observed evidence, or silently overwrite scores."
    )

    return ControlledReuseState(
        recommendation_reuse_active=recommendation_reuse_active,
        ranking_context_reuse_active=ranking_context_reuse_active,
        interpretation_support_active=interpretation_support_active,
        reused_evidence=reused_evidence,
        support_carriers=support_carriers,
        recommendation_reuse_summary=recommendation_reuse_summary,
        ranking_context_reuse_summary=ranking_context_reuse_summary,
        interpretation_support_summary=interpretation_support_summary,
        inactive_boundary_summary=inactive_boundary_summary,
    ).dict()


def build_scientific_session_truth(
    *,
    session_id: str,
    workspace_id: str | None = None,
    source_name: str | None = None,
    session_record: dict[str, Any] | None = None,
    upload_metadata: dict[str, Any] | None = None,
    analysis_report: dict[str, Any] | None = None,
    decision_payload: dict[str, Any] | None = None,
    review_queue: dict[str, Any] | None = None,
    workspace_memory: dict[str, Any] | None = None,
    current_job: dict[str, Any] | None = None,
    feedback_store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_record = session_record or {}
    upload_metadata = upload_metadata or {}
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}
    review_queue = review_queue or {}
    summary_metadata = session_record.get("summary_metadata") if isinstance(session_record.get("summary_metadata"), dict) else {}

    target_definition = _first_dict(
        decision_payload.get("target_definition"),
        analysis_report.get("target_definition"),
        upload_metadata.get("target_definition"),
        summary_metadata.get("target_definition"),
    )
    run_contract = _first_dict(
        analysis_report.get("run_contract"),
        decision_payload.get("run_contract"),
        summary_metadata.get("run_contract"),
    )
    comparison_anchors = _first_dict(
        analysis_report.get("comparison_anchors"),
        decision_payload.get("comparison_anchors"),
        summary_metadata.get("comparison_anchors"),
    )
    modeling_mode = _clean_text(
        analysis_report.get("modeling_mode")
        or decision_payload.get("modeling_mode")
        or summary_metadata.get("modeling_mode")
        or run_contract.get("modeling_mode"),
        default=ModelingMode.ranking_only.value,
    ).lower()
    decision_intent = _clean_text(
        analysis_report.get("decision_intent")
        or decision_payload.get("decision_intent")
        or summary_metadata.get("decision_intent"),
    ).lower()
    session_identity = build_session_identity(
        session_record=session_record,
        upload_metadata=upload_metadata,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        current_job=current_job,
    )
    run_provenance = build_run_provenance(
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
    )
    review_summary = review_queue.get("summary") if isinstance(review_queue.get("summary"), dict) else {}
    ranking_policy = analysis_report.get("ranking_policy") if isinstance(analysis_report.get("ranking_policy"), dict) else {}
    measurement_summary = analysis_report.get("measurement_summary") if isinstance(analysis_report.get("measurement_summary"), dict) else {}
    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report.get("ranking_diagnostics"), dict) else {}
    records = build_evidence_records(
        target_definition=target_definition,
        modeling_mode=modeling_mode,
        run_contract=run_contract,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        review_summary=review_summary,
        workspace_memory=workspace_memory,
        feedback_store=feedback_store,
    )
    evidence_loop = build_evidence_loop_summary(records)
    evidence_activation_policy = build_evidence_activation_policy(records)
    controlled_reuse = build_controlled_reuse_state(
        evidence_activation_policy=evidence_activation_policy,
        workspace_memory=workspace_memory,
    )
    effective_workspace_id = _clean_text(workspace_id or session_record.get("workspace_id"))
    claims = list_session_claims(session_id, workspace_id=effective_workspace_id) if effective_workspace_id else []
    experiment_requests = (
        list_session_experiment_requests(session_id, workspace_id=effective_workspace_id)
        if effective_workspace_id
        else []
    )
    experiment_results = (
        list_session_experiment_results(session_id, workspace_id=effective_workspace_id)
        if effective_workspace_id
        else []
    )
    belief_updates = (
        list_session_belief_updates(session_id, workspace_id=effective_workspace_id)
        if effective_workspace_id
        else []
    )
    belief_state = (
        get_belief_state_for_target(
            workspace_id=effective_workspace_id,
            target_definition_snapshot=target_definition,
        )
        if effective_workspace_id and isinstance(target_definition, dict) and target_definition
        else None
    )
    bridge_state_notes = []
    if _clean_text(run_provenance.get("bridge_state_summary")):
        bridge_state_notes.append(_clean_text(run_provenance.get("bridge_state_summary")))
    for warning in analysis_report.get("warnings", []) if isinstance(analysis_report.get("warnings"), list) else []:
        text = _clean_text(warning)
        if text and text not in bridge_state_notes:
            bridge_state_notes.append(text)

    decision_summary = decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}
    payload = {
        "session_id": session_id,
        "workspace_id": _clean_text(workspace_id or session_record.get("workspace_id")),
        "source_name": _clean_text(source_name or session_record.get("source_name") or upload_metadata.get("filename")),
        "generated_at": _clean_text(
            decision_payload.get("source_updated_at")
            or analysis_report.get("source_updated_at")
            or decision_payload.get("generated_at")
        ),
        "session_identity": session_identity,
        "target_definition": target_definition,
        "decision_intent": decision_intent or None,
        "modeling_mode": modeling_mode or None,
        "run_contract": run_contract,
        "comparison_anchors": comparison_anchors,
        "evidence_records": records,
        "evidence_loop": evidence_loop,
        "evidence_activation_policy": evidence_activation_policy,
        "controlled_reuse": controlled_reuse,
        "claim_refs": claim_refs_from_records(claims),
        "claims_summary": claims_summary_from_records(claims),
        "experiment_request_refs": experiment_request_refs_from_records(experiment_requests),
        "experiment_request_summary": experiment_request_summary_from_records(experiment_requests),
        "experiment_result_refs": experiment_result_refs_from_records(experiment_results),
        "linked_result_summary": experiment_result_summary_from_records(experiment_results),
        "belief_update_refs": belief_update_refs_from_records(belief_updates),
        "belief_update_summary": belief_update_summary_from_records(belief_updates),
        "belief_state_ref": belief_state_reference_from_record(belief_state) if isinstance(belief_state, dict) else None,
        "belief_state_summary": belief_state_summary_from_record(belief_state) if isinstance(belief_state, dict) else None,
        "bridge_state_notes": bridge_state_notes,
        "core_outputs": {
            "candidate_count": _candidate_count(decision_payload),
            "top_experiment_value": _safe_float(decision_summary.get("top_experiment_value")),
            "recommendation_summary": _clean_text(analysis_report.get("top_level_recommendation_summary")),
            "warning_count": len(analysis_report.get("warnings") or []) if isinstance(analysis_report.get("warnings"), list) else 0,
            "measurement_summary": measurement_summary,
            "ranking_diagnostics": ranking_diagnostics,
        },
        "decision_policy_summary": {
            "primary_score": _clean_text(ranking_policy.get("primary_score")),
            "primary_score_label": _clean_text(ranking_policy.get("primary_score_label")),
            "formula_label": _clean_text(ranking_policy.get("formula_label")),
            "formula_summary": _clean_text(ranking_policy.get("formula_summary")),
        },
        "review_summary": review_summary,
        "comparison_ready": bool(comparison_anchors.get("comparison_ready")),
        "contract_versions": _first_dict(
            analysis_report.get("contract_versions"),
            decision_payload.get("contract_versions"),
            summary_metadata.get("contract_versions"),
        ),
    }
    return validate_scientific_session_truth(payload)


def persist_scientific_session_truth(
    payload: dict[str, Any],
    *,
    session_id: str,
    workspace_id: str | None = None,
    created_by_user_id: str | None = None,
    register_artifact: bool = False,
) -> str:
    validated = validate_scientific_session_truth(payload)
    target_dir = uploaded_session_dir(session_id, create=True)
    path = target_dir / "scientific_session_truth.json"
    write_json_log(path, validated)
    SessionRepository().upsert_session(
        session_id=session_id,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        summary_metadata={"scientific_session_truth": validated},
    )
    if register_artifact:
        ArtifactRepository().register_artifact(
            artifact_type="scientific_session_truth_json",
            path=path,
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            metadata={
                "comparison_ready": bool(validated.get("comparison_ready")),
                "evidence_records": len(validated.get("evidence_records") or []),
                "claims": int(((validated.get("claims_summary") or {}).get("claim_count")) or 0),
                "experiment_requests": int(
                    (((validated.get("experiment_request_summary") or {}).get("request_count")) or 0)
                ),
                "experiment_results": int(
                    (((validated.get("linked_result_summary") or {}).get("result_count")) or 0)
                ),
                "belief_updates": int(
                    (((validated.get("belief_update_summary") or {}).get("update_count")) or 0)
                ),
                "belief_state_active_claims": int(
                    (((validated.get("belief_state_summary") or {}).get("active_claim_count")) or 0)
                ),
            },
        )
    return str(path)


__all__ = [
    "build_controlled_reuse_state",
    "build_evidence_activation_policy",
    "build_evidence_records",
    "build_evidence_loop_summary",
    "build_scientific_session_truth",
    "persist_scientific_session_truth",
]
