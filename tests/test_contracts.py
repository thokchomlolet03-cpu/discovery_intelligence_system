import unittest

from system.contracts import (
    validate_comparison_anchors,
    validate_belief_state_record,
    validate_belief_update_record,
    ContractValidationError,
    validate_claim_record,
    validate_decision_artifact,
    validate_experiment_result_record,
    validate_experiment_request_record,
    validate_label_builder_config,
    validate_review_event_record,
    validate_run_contract,
    validate_session_identity,
    validate_target_definition,
)


def canonical_decision_artifact() -> dict:
    return {
        "session_id": "session_1",
        "iteration": 1,
        "generated_at": "2026-03-25T12:00:00+00:00",
        "summary": {
            "top_k": 1,
            "candidate_count": 1,
            "risk_counts": {"medium": 1},
            "top_experiment_value": 0.64,
        },
        "top_experiments": [
            {
                "session_id": "session_1",
                "rank": 1,
                "candidate_id": "cand_1",
                "smiles": "CCO",
                "canonical_smiles": "CCO",
                "confidence": 0.74,
                "uncertainty": 0.26,
                "novelty": 0.48,
                "acquisition_score": 0.62,
                "experiment_value": 0.64,
                "priority_score": 0.66,
                "bucket": "exploit",
                "risk": "medium",
                "status": "suggested",
                "explanation": ["Balanced scores make this a reasonable candidate for expert review."],
                "score_breakdown": [
                    {
                        "key": "confidence",
                        "label": "Confidence",
                        "raw_value": 0.74,
                        "weight": 0.30,
                        "weight_percent": 30.0,
                        "contribution": 0.222,
                    }
                ],
                "rationale": {
                    "summary": "This candidate is being prioritized mainly because confidence is carrying the shortlist position.",
                    "why_now": "Confidence is the largest contributor to the current priority score.",
                    "trust_label": "Mixed trust",
                    "trust_summary": "The shortlist is useful for prioritization, but still needs scientist review before becoming a bench commitment.",
                    "recommended_action": "Keep this in expert review before moving it into the next testing round.",
                    "primary_driver": "confidence",
                    "session_context": ["Priority score ranks #1 out of 1 scored candidates in this run."],
                    "strengths": ["Confidence is relatively strong at 0.740."],
                    "cautions": ["No uploaded observed value is available for direct cross-checking in this session."],
                    "evidence_lines": ["This candidate is being prioritized mainly because confidence is carrying the shortlist position."],
                },
                "domain_status": "in_domain",
                "domain_label": "Within stronger chemistry range",
                "domain_summary": "Reference similarity is strong enough to support more confident near-term review.",
                "provenance": {
                    "text": "Scored directly from user-uploaded dataset upload.csv. Model version: rf_isotonic:isotonic.",
                    "source_name": "upload.csv",
                    "source_type": "uploaded",
                    "parent_molecule": "",
                    "model_version": "rf_isotonic:isotonic",
                },
                "feasibility": {"is_feasible": True, "reason": ""},
                "created_at": "2026-03-25T12:00:00+00:00",
                "model_metadata": {
                    "version": "rf_isotonic:isotonic",
                    "family": "random_forest",
                    "calibration_method": "isotonic",
                },
            }
        ],
    }


class ContractValidationTest(unittest.TestCase):
    def test_valid_decision_artifact_passes_schema_validation(self):
        validated = validate_decision_artifact(canonical_decision_artifact())

        self.assertEqual(validated["session_id"], "session_1")
        self.assertEqual(validated["top_experiments"][0]["candidate_id"], "cand_1")
        self.assertEqual(validated["top_experiments"][0]["bucket"], "exploit")
        self.assertEqual(validated["top_experiments"][0]["rationale"]["primary_driver"], "confidence")
        self.assertTrue(validated["top_experiments"][0]["rationale"]["session_context"])

    def test_malformed_decision_artifact_fails_schema_validation(self):
        invalid = canonical_decision_artifact()
        invalid["top_experiments"][0].pop("bucket")

        with self.assertRaises(ContractValidationError):
            validate_decision_artifact(invalid)

    def test_review_record_validates_correctly(self):
        review = validate_review_event_record(
            {
                "session_id": "session_1",
                "candidate_id": "cand_1",
                "smiles": "CCO",
                "action": "approve",
                "previous_status": "suggested",
                "status": "approved",
                "note": "Looks reasonable",
                "timestamp": "2026-03-25T12:00:00+00:00",
                "reviewed_at": "2026-03-25T12:00:00+00:00",
                "actor": "qa",
                "reviewer": "qa",
                "metadata": {"origin": "unit_test"},
            }
        )

        self.assertEqual(review["status"], "approved")
        self.assertEqual(review["previous_status"], "suggested")
        self.assertEqual(review["reviewer"], "qa")

    def test_claim_record_validates_bounded_recommendation_assertion(self):
        claim = validate_claim_record(
            {
                "claim_id": "claim_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)", "smiles": "CCO", "rank": 1},
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "claim_type": "recommendation_assertion",
                "claim_text": "Under the current session evidence, cand_1 (CCO) is a plausible follow-up candidate to test for higher pIC50.",
                "bounded_scope": "This proposed claim is scoped to the current session and is not experimental confirmation or causal proof.",
                "support_level": "moderate",
                "evidence_basis_summary": "Modeling uses Observed experimental values. Ranking uses Model predictions.",
                "source_recommendation_rank": 1,
                "status": "proposed",
                "created_at": "2026-04-02T10:00:00+00:00",
                "updated_at": "2026-04-02T10:00:00+00:00",
                "created_by": "system",
            }
        )

        self.assertEqual(claim["claim_type"], "recommendation_assertion")
        self.assertEqual(claim["status"], "proposed")
        self.assertEqual(claim["support_level"], "moderate")

    def test_experiment_request_record_validates_recommended_experiment(self):
        request = validate_experiment_request_record(
            {
                "experiment_request_id": "expreq_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "claim_id": "claim_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)", "smiles": "CCO", "rank": 1},
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "requested_measurement": "pIC50",
                "requested_direction": "measure for higher values",
                "rationale_summary": "This proposed experiment request is derived from the current claim. It is not scheduled lab work.",
                "priority_tier": "high",
                "status": "proposed",
                "requested_at": "2026-04-02T12:00:00+00:00",
                "requested_by": "system",
            }
        )

        self.assertEqual(request["requested_measurement"], "pIC50")
        self.assertEqual(request["priority_tier"], "high")
        self.assertEqual(request["status"], "proposed")

    def test_experiment_result_record_validates_observed_outcome(self):
        result = validate_experiment_result_record(
            {
                "experiment_result_id": "expres_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "source_experiment_request_id": "expreq_1",
                "source_claim_id": "claim_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)", "smiles": "CCO", "rank": 1},
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "observed_value": 6.4,
                "observed_label": "",
                "measurement_unit": "log units",
                "assay_context": "screen_a repeat 1",
                "result_quality": "screening",
                "result_source": "manual_entry",
                "ingested_at": "2026-04-02T14:00:00+00:00",
                "ingested_by": "system",
                "notes": "Observed outcome recorded.",
            }
        )

        self.assertEqual(result["observed_value"], 6.4)
        self.assertEqual(result["result_quality"], "screening")
        self.assertEqual(result["result_source"], "manual_entry")

    def test_belief_update_record_validates_bounded_support_change(self):
        belief_update = validate_belief_update_record(
            {
                "belief_update_id": "belief_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "claim_id": "claim_1",
                "experiment_result_id": "expres_1",
                "candidate_id": "cand_1",
                "candidate_label": "cand_1 (CCO)",
                "previous_support_level": "moderate",
                "updated_support_level": "strong",
                "update_direction": "strengthened",
                "update_reason": "This proposed belief update strengthens support in a bounded way only.",
                "governance_status": "proposed",
                "created_at": "2026-04-02T15:00:00+00:00",
                "created_by": "scientist",
            }
        )

        self.assertEqual(belief_update["update_direction"], "strengthened")
        self.assertEqual(belief_update["governance_status"], "proposed")
        self.assertEqual(belief_update["updated_support_level"], "strong")

    def test_belief_state_record_validates_current_support_picture(self):
        belief_state = validate_belief_state_record(
            {
                "belief_state_id": "beliefstate_1",
                "workspace_id": "workspace_1",
                "target_key": "pic50|regression|maximize|pic50|measurement_dataset",
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "summary_text": "Current belief state tracks 2 active claims. This is a bounded support summary, not final truth.",
                "active_claim_count": 2,
                "supported_claim_count": 1,
                "weakened_claim_count": 0,
                "unresolved_claim_count": 1,
                "last_updated_at": "2026-04-02T16:00:00+00:00",
                "last_update_source": "latest belief update linked to an observed result",
                "version": 1,
                "support_distribution_summary": "Supported 1, weakened 0, unresolved 1.",
                "governance_scope_summary": "Current picture includes 1 accepted and 1 proposed belief update.",
            }
        )

        self.assertEqual(belief_state["active_claim_count"], 2)
        self.assertEqual(belief_state["supported_claim_count"], 1)
        self.assertEqual(belief_state["version"], 1)

    def test_label_builder_config_validates_threshold_rule(self):
        validated = validate_label_builder_config(
            {
                "enabled": True,
                "value_column": "pic50",
                "operator": ">=",
                "threshold": 6.0,
            }
        )

        self.assertTrue(validated["enabled"])
        self.assertEqual(validated["value_column"], "pic50")
        self.assertEqual(validated["threshold"], 6.0)

    def test_target_definition_validates_regression_contract(self):
        validated = validate_target_definition(
            {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "measurement_unit": "log10 molar potency scale",
                "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
                "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
            }
        )

        self.assertEqual(validated["target_kind"], "regression")
        self.assertEqual(validated["measurement_column"], "pic50")
        self.assertEqual(validated["dataset_type"], "measurement_dataset")

    def test_session_identity_validates_target_aware_contract(self):
        validated = validate_session_identity(
            {
                "session_id": "session_1",
                "source_name": "upload.csv",
                "created_at": "2026-03-25T12:00:00+00:00",
                "workspace_id": "workspace_1",
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                    "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
                },
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "session_status": "results_ready",
                "current_job_status": "succeeded",
                "scientific_purpose": "Estimate continuous values for pIC50 and prioritize molecules that look experimentally useful to test.",
                "trust_summary": "Uploaded measurements are available, so the ranking can be cross-checked against observed evidence rather than treated as model truth.",
                "latest_result_summary": "3 saved candidates are available for review.",
            }
        )

        self.assertEqual(validated["modeling_mode"], "regression")
        self.assertEqual(validated["decision_intent"], "prioritize_experiments")
        self.assertEqual(validated["target_definition"]["target_name"], "pIC50")

    def test_run_contract_validates_comparison_ready_metadata(self):
        validated = validate_run_contract(
            {
                "session_id": "session_1",
                "source_name": "upload.csv",
                "input_type": "measurement_dataset",
                "requested_intent": "rank_uploaded_molecules",
                "decision_intent": "prioritize_experiments",
                "modeling_mode": "regression",
                "scoring_mode": "balanced",
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                    "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
                },
                "target_model_available": True,
                "candidate_generation_requested": False,
                "candidate_generation_eligible": False,
                "used_candidate_generation": False,
                "selected_model_name": "rf_regression",
                "selected_model_family": "random_forest",
                "training_scope": "session_trained",
                "label_source": "continuous_measurement",
                "feature_signature": "rdkit_descriptors_plus_morgan_fp_2048",
                "reference_basis": {
                    "novelty_reference": "reference_dataset_similarity",
                    "applicability_reference": "reference_dataset_similarity",
                },
                "contract_versions": {
                    "target_contract_version": "target_definition.v1",
                    "model_contract_version": "model_contract.v1",
                    "run_contract_version": "run_contract.v1",
                },
            }
        )

        self.assertEqual(validated["modeling_mode"], "regression")
        self.assertEqual(validated["training_scope"], "session_trained")
        self.assertEqual(validated["contract_versions"]["run_contract_version"], "run_contract.v1")

    def test_comparison_anchors_validate_session_basis(self):
        validated = validate_comparison_anchors(
            {
                "session_id": "session_1",
                "source_name": "upload.csv",
                "input_type": "measurement_dataset",
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
                "column_mapping": {"smiles": "smiles", "value": "pic50"},
                "label_source": "continuous_measurement",
                "decision_intent": "prioritize_experiments",
                "modeling_mode": "regression",
                "scoring_mode": "balanced",
                "selected_model_name": "rf_regression",
                "training_scope": "session_trained",
                "target_contract_version": "target_definition.v1",
                "model_contract_version": "model_contract.v1",
                "scoring_policy_version": "scoring_policy.v1",
                "explanation_contract_version": "normalized_explanation.v1",
                "run_contract_version": "run_contract.v1",
                "comparison_ready": True,
            }
        )

        self.assertEqual(validated["target_kind"], "regression")
        self.assertTrue(validated["comparison_ready"])
        self.assertEqual(validated["scoring_policy_version"], "scoring_policy.v1")


if __name__ == "__main__":
    unittest.main()
