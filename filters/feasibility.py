from __future__ import annotations

import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors

from system.services.runtime_config import resolve_system_config


def feasibility_reason(smiles, config=None) -> str:
    cfg = resolve_system_config(config)
    mol = Chem.MolFromSmiles(str(smiles)) if pd.notna(smiles) else None
    if mol is None:
        return "invalid_smiles"

    try:
        mw = float(Descriptors.MolWt(mol))
        if mw > cfg.feasibility.max_mw:
            return "molecular_weight_too_high"
        if mol.GetNumAtoms() > cfg.feasibility.max_atoms:
            return "atom_count_too_high"
        if mol.GetRingInfo().NumRings() > cfg.feasibility.max_rings:
            return "ring_count_too_high"
    except Exception:
        return "feasibility_check_failed"

    return ""


def is_feasible(smiles, config=None) -> bool:
    return feasibility_reason(smiles, config=config) == ""


def annotate_feasibility(df, smiles_column="smiles", config=None) -> pd.DataFrame:
    annotated = df.copy()
    reasons = annotated[smiles_column].apply(lambda smiles: feasibility_reason(smiles, config=config))
    annotated["feasibility_reason"] = reasons
    annotated["is_feasible"] = reasons.eq("")
    return annotated
