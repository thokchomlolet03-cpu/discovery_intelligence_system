from __future__ import annotations

import io

import pandas as pd
from rdkit import Chem


def parse_sdf_bytes(file_bytes: bytes, filename: str = "") -> pd.DataFrame:
    supplier = Chem.ForwardSDMolSupplier(io.BytesIO(file_bytes), sanitize=True, removeHs=False)
    rows: list[dict[str, str]] = []
    for index, molecule in enumerate(supplier):
        if molecule is None:
            continue
        row = {
            "smiles": Chem.MolToSmiles(molecule, canonical=True),
            "entity_id": molecule.GetProp("_Name").strip() if molecule.HasProp("_Name") else f"molecule_{index + 1}",
        }
        for prop_name in molecule.GetPropNames():
            row[prop_name] = molecule.GetProp(prop_name)
        rows.append(row)

    if not rows:
        raise ValueError("The uploaded SDF file did not contain any readable molecules.")
    return pd.DataFrame(rows)
