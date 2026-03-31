import tempfile
import unittest
from pathlib import Path

from rdkit import Chem

from system.services.ingestion import infer_semantic_roles, normalize_input_type, parse_sdf_bytes, parse_smiles_text


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


if __name__ == "__main__":
    unittest.main()
