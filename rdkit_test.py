# rdkit_test.py

from rdkit import Chem
from rdkit.Chem import Descriptors

smiles = "CC(=O)O"

mol = Chem.MolFromSmiles(smiles)

if mol is None:
    print("❌ Invalid SMILES")
else:
    print("✅ Molecule created successfully")

    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)

    print("\n=== DESCRIPTORS ===")
    print("Molecular Weight:", mw)
    print("LogP:", logp)
