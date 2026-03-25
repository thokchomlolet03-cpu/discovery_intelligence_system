import numpy as np
from rdkit import DataStructs
from rdkit.Chem import AllChem

from core.constants import FINGERPRINT_BITS, FINGERPRINT_COLUMNS


def build_fingerprint_columns(n_bits=FINGERPRINT_BITS):
    return [f"fp_{idx}" for idx in range(n_bits)]


def infer_fingerprint_columns(df):
    fp_cols = sorted(
        [col for col in df.columns if str(col).startswith("fp_")],
        key=lambda name: int(str(name).split("_")[1]),
    )
    return fp_cols or list(FINGERPRINT_COLUMNS)


def compute_morgan_fingerprint(mol, n_bits=FINGERPRINT_BITS):
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=n_bits)
    arr = np.zeros((n_bits,), dtype=int)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr

