import unittest

from system.services.run_metadata_service import (
    build_comparison_anchors,
    build_run_provenance,
    build_run_contract,
    infer_comparison_anchors,
)


class RunMetadataServiceTest(unittest.TestCase):
    def test_build_run_contract_captures_model_provenance(self):
        run_contract = build_run_contract(
            session_id="session_1",
            source_name="measurements.csv",
            input_type="measurement_dataset",
            requested_intent="rank_uploaded_molecules",
            decision_intent="prioritize_experiments",
            modeling_mode="regression",
            scoring_mode="balanced",
            target_definition={
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
                "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
            },
            scientific_contract={
                "target_model_available": True,
                "candidate_generation_eligible": False,
                "used_candidate_generation": False,
                "fallback_reason": "",
            },
            contract_versions={
                "target_contract_version": "target_definition.v1",
                "model_contract_version": "model_contract.v1",
                "run_contract_version": "run_contract.v1",
            },
            validation_summary={"label_source": "", "rows_with_values": 12},
            bundle={
                "selected_model": {"name": "rf_regression", "calibration_method": ""},
                "model_family": "random_forest",
                "training_scope": "session_trained",
                "descriptor_features": ["mw", "rdkit_logp"],
                "fingerprint_bits": 2048,
            },
        )

        self.assertEqual(run_contract["selected_model_name"], "rf_regression")
        self.assertEqual(run_contract["training_scope"], "session_trained")
        self.assertEqual(run_contract["feature_signature"], "rdkit_descriptors_plus_morgan_fp_2048")
        self.assertEqual(run_contract["label_source"], "continuous_measurement")

    def test_infer_comparison_anchors_backfills_from_legacy_session_records(self):
        anchors = infer_comparison_anchors(
            session_record={
                "session_id": "session_legacy",
                "source_name": "upload.csv",
                "input_type": "measurement_dataset",
                "summary_metadata": {
                    "decision_intent": "prioritize_experiments",
                    "modeling_mode": "binary_classification",
                    "contract_versions": {
                        "target_contract_version": "target_definition.v1",
                        "model_contract_version": "model_contract.v1",
                        "scoring_policy_version": "scoring_policy.v1",
                        "explanation_contract_version": "normalized_explanation.v1",
                        "run_contract_version": "run_contract.v1",
                    },
                },
            },
            upload_metadata={
                "session_id": "session_legacy",
                "filename": "upload.csv",
                "input_type": "measurement_dataset",
                "selected_mapping": {"smiles": "smiles", "value": "pic50"},
                "validation_summary": {
                    "value_column": "pic50",
                    "rows_with_values": 8,
                    "rows_with_labels": 0,
                    "label_source": "",
                },
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
            },
            analysis_report={"mode_used": "balanced"},
        )

        self.assertEqual(anchors["target_name"], "pIC50")
        self.assertEqual(anchors["scoring_mode"], "balanced")
        self.assertEqual(anchors["decision_intent"], "prioritize_experiments")
        self.assertEqual(anchors["target_contract_version"], "target_definition.v1")

    def test_build_comparison_anchors_marks_ready_only_when_mode_and_intent_exist(self):
        ready = build_comparison_anchors(
            session_id="session_ready",
            source_name="upload.csv",
            input_type="measurement_dataset",
            column_mapping={"smiles": "smiles", "value": "pic50"},
            target_definition={
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
                "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
            },
            decision_intent="prioritize_experiments",
            modeling_mode="regression",
            scoring_mode="balanced",
            contract_versions={"run_contract_version": "run_contract.v1"},
            validation_summary={"label_source": ""},
            run_contract={"training_scope": "session_trained"},
        )

        self.assertTrue(ready["comparison_ready"])
        self.assertEqual(ready["training_scope"], "session_trained")

    def test_build_run_provenance_exposes_comparison_and_model_context(self):
        provenance = build_run_provenance(
            run_contract={
                "selected_model_name": "rf_regression",
                "selected_model_family": "random_forest",
                "training_scope": "baseline_bundle",
                "scoring_mode": "balanced",
                "calibration_method": "",
                "reference_basis": {
                    "novelty_reference": "reference_dataset_similarity",
                    "applicability_reference": "reference_dataset_similarity",
                },
            },
            comparison_anchors={
                "target_name": "pIC50",
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "scoring_policy_version": "scoring_policy.v1",
                "explanation_contract_version": "normalized_explanation.v1",
                "comparison_ready": True,
            },
        )

        self.assertTrue(provenance["comparison_ready"])
        self.assertIn("pIC50", provenance["comparison_basis_label"])
        self.assertIn("baseline model bundle", provenance["model_summary"])
        self.assertEqual(provenance["policy_version"], "scoring_policy.v1")


if __name__ == "__main__":
    unittest.main()
