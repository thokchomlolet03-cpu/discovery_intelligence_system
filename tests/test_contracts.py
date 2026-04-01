import unittest

from system.contracts import (
    validate_comparison_anchors,
    ContractValidationError,
    validate_decision_artifact,
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
