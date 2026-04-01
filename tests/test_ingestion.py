import tempfile
import unittest
from pathlib import Path

from rdkit import Chem

from system.services.ingestion import infer_semantic_roles, normalize_input_type, parse_sdf_bytes, parse_smiles_text
from system.services.target_definition_service import enrich_upload_inspection_payload


class IngestionParserTest(unittest.TestCase):
    def test_parse_smiles_text_creates_structure_screening_frame(self):
        payload = b"CCO ethanol\nCCN ethylamine\n"

        dataframe = parse_smiles_text(payload, "molecules.txt")

        self.assertEqual(list(dataframe.columns), ["smiles", "entity_id"])
        self.assertEqual(dataframe.iloc[0]["smiles"], "CCO")
        self.assertEqual(dataframe.iloc[0]["entity_id"], "ethanol")

    def test_infer_semantic_roles_detects_measurement_column(self):
        import pandas as pd

        frame = pd.DataFrame(
            {
                "SMILES": ["CCO", "CCN"],
                "pIC50": [6.1, 5.2],
                "assay_name": ["screen_a", "screen_a"],
            }
        )

        mapping = infer_semantic_roles(list(frame.columns), dataframe=frame)

        self.assertEqual(mapping["smiles"], "smiles")
        self.assertEqual(mapping["value"], "pic50")
        self.assertEqual(mapping["assay"], "assay_name")

    def test_parse_sdf_bytes_extracts_smiles_and_properties(self):
        molecule = Chem.MolFromSmiles("CCO")
        molecule.SetProp("_Name", "mol_1")
        molecule.SetProp("pIC50", "6.4")
        molecule.SetProp("assay", "screen_a")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "molecules.sdf"
            writer = Chem.SDWriter(str(path))
            writer.write(molecule)
            writer.close()

            dataframe = parse_sdf_bytes(path.read_bytes(), "molecules.sdf")

        self.assertEqual(dataframe.iloc[0]["entity_id"], "mol_1")
        self.assertEqual(dataframe.iloc[0]["pIC50"], "6.4")
        self.assertEqual(dataframe.iloc[0]["assay"], "screen_a")
        self.assertTrue(dataframe.iloc[0]["smiles"])

    def test_normalize_input_type_maps_legacy_aliases(self):
        self.assertEqual(normalize_input_type("experimental_results"), "measurement_dataset")
        self.assertEqual(normalize_input_type("molecules_to_screen_only"), "structure_only_screening")
        self.assertEqual(normalize_input_type("labeled_tabular_dataset"), "labeled_tabular_dataset")

    def test_upload_inspection_payload_is_enriched_with_target_definition(self):
        payload = enrich_upload_inspection_payload(
            {
                "session_id": "session_1",
                "created_at": "2026-04-01T12:00:00+00:00",
                "filename": "molecules.csv",
                "input_type": "measurement_dataset",
                "file_type": "csv",
                "semantic_mode": "measurement_dataset",
                "columns": ["smiles", "pic50"],
                "preview_rows": [{"smiles": "CCO", "pic50": "6.1"}],
                "inferred_mapping": {"smiles": "smiles", "value": "pic50"},
                "semantic_roles": {"smiles": "smiles", "value": "pic50"},
                "selected_mapping": {"smiles": "smiles", "value": "pic50"},
                "measurement_columns": ["pic50"],
                "label_builder_suggestion": {"enabled": False},
                "label_builder_config": {"enabled": False},
                "validation_summary": {
                    "total_rows": 1,
                    "valid_smiles_count": 1,
                    "invalid_smiles_count": 0,
                    "duplicate_count": 0,
                    "rows_with_labels": 0,
                    "rows_without_labels": 1,
                    "rows_with_values": 1,
                    "rows_without_values": 0,
                    "value_column": "pic50",
                    "semantic_mode": "measurement_dataset",
                    "label_source": "",
                    "file_type": "csv",
                    "positive_label_count": 0,
                    "negative_label_count": 0,
                    "unlabeled_label_count": 1,
                    "label_counts": {"positive": 0, "negative": 0, "unlabeled": 1},
                    "missing_fields": [],
                    "warnings": [],
                    "can_run_analysis": True,
                },
                "free_tier_assessment": {},
            }
        )

        self.assertEqual(payload["target_definition"]["target_kind"], "regression")
        self.assertEqual(payload["target_definition"]["measurement_column"], "pic50")
        self.assertEqual(payload["contract_versions"]["target_contract_version"], "target_definition.v1")


if __name__ == "__main__":
    unittest.main()
