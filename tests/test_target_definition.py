import unittest

from system.services.target_definition_service import infer_target_definition, normalize_decision_intent


class TargetDefinitionServiceTest(unittest.TestCase):
    def test_infers_legacy_biodegradability_target(self):
        target = infer_target_definition(
            mapping={"smiles": "smiles", "biodegradable": "biodegradable"},
            validation_summary={
                "rows_with_labels": 8,
                "rows_without_labels": 0,
                "rows_with_values": 0,
                "rows_without_values": 8,
                "semantic_mode": "labeled_tabular_dataset",
                "label_source": "column",
            },
            label_builder={"enabled": False},
        )

        self.assertEqual(target["target_name"], "biodegradability")
        self.assertEqual(target["target_kind"], "classification")
        self.assertEqual(target["dataset_type"], "labeled_dataset")
        self.assertEqual(target["mapping_confidence"], "high")

    def test_infers_measurement_regression_target(self):
        target = infer_target_definition(
            mapping={"smiles": "smiles", "value": "pic50", "assay": "assay_name"},
            validation_summary={
                "rows_with_labels": 0,
                "rows_without_labels": 10,
                "rows_with_values": 10,
                "rows_without_values": 0,
                "semantic_mode": "measurement_dataset",
                "value_column": "pic50",
            },
            label_builder={"enabled": False},
        )

        self.assertEqual(target["target_kind"], "regression")
        self.assertEqual(target["dataset_type"], "measurement_dataset")
        self.assertEqual(target["optimization_direction"], "maximize")
        self.assertEqual(target["measurement_unit"], "log10 molar potency scale")

    def test_structure_only_target_no_longer_defaults_to_biodegradability(self):
        target = infer_target_definition(
            mapping={"smiles": "smiles"},
            validation_summary={
                "rows_with_labels": 0,
                "rows_without_labels": 10,
                "rows_with_values": 0,
                "rows_without_values": 10,
                "semantic_mode": "structure_only_screening",
            },
            label_builder={"enabled": False},
        )

        self.assertEqual(target["target_name"], "")
        self.assertEqual(target["target_kind"], "classification")
        self.assertEqual(target["dataset_type"], "structure_only")
        self.assertEqual(target["mapping_confidence"], "low")

    def test_generic_label_column_does_not_become_silent_target_name(self):
        target = infer_target_definition(
            mapping={"smiles": "smiles", "label": "label"},
            validation_summary={
                "rows_with_labels": 6,
                "rows_without_labels": 0,
                "rows_with_values": 0,
                "rows_without_values": 6,
                "semantic_mode": "labeled_tabular_dataset",
                "label_source": "column",
            },
            label_builder={"enabled": False},
        )

        self.assertEqual(target["target_name"], "")
        self.assertEqual(target["target_kind"], "classification")
        self.assertIn("positive class defined for this session", target["scientific_meaning"])

    def test_infers_derived_label_rule_when_thresholding_measurements(self):
        target = infer_target_definition(
            mapping={"smiles": "smiles", "value": "pic50"},
            validation_summary={
                "rows_with_labels": 6,
                "rows_without_labels": 2,
                "rows_with_values": 8,
                "rows_without_values": 0,
                "semantic_mode": "measurement_dataset",
                "value_column": "pic50",
            },
            label_builder={"enabled": True, "value_column": "pic50", "operator": ">=", "threshold": 6.0},
        )

        self.assertEqual(target["target_kind"], "classification")
        self.assertEqual(target["dataset_type"], "labeled_dataset")
        self.assertEqual(target["derived_label_rule"]["source_column"], "pic50")

    def test_normalize_decision_intent_maps_legacy_names(self):
        self.assertEqual(normalize_decision_intent("rank_uploaded_molecules"), "prioritize_experiments")
        self.assertEqual(normalize_decision_intent("predict_labels"), "estimate_labels")


if __name__ == "__main__":
    unittest.main()
