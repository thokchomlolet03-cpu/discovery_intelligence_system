# interpret_fingerprints.py

from rdkit import Chem
from rdkit.Chem import AllChem

# ---------------------------
# IMPORTANT FINGERPRINT BITS
# (from your SHAP output)
# ---------------------------
important_bits = [1, 64, 106, 251, 210]

# ---------------------------
# TEST MOLECULES
# ---------------------------
smiles_list = [
    ("PLA", "CC(=O)OCC(=O)O"),
    ("PCL", "CCCCCC(=O)O"),
    ("PET", "CCOC(=O)c1ccc(cc1)C(=O)O"),
    ("PE", "CC"),
]

print("🧠 Interpreting fingerprint bits across molecules...\n")

# ---------------------------
# LOOP THROUGH MOLECULES
# ---------------------------
for name, smiles in smiles_list:
    print(f"\n==============================")
    print(f"🔬 Molecule: {name}")
    print(f"SMILES: {smiles}")
    print(f"==============================")

    mol = Chem.MolFromSmiles(smiles)

    if mol is None:
        print("❌ Invalid SMILES\n")
        continue

    bitInfo = {}

    # Generate fingerprint
    fp = AllChem.GetMorganFingerprintAsBitVect(
        mol,
        radius=3,
        nBits=2048,
        bitInfo=bitInfo
    )

    # ---------------------------
    # INTERPRET EACH IMPORTANT BIT
    # ---------------------------
    for bit in important_bits:
        if bit not in bitInfo:
            continue

        print(f"\n🔹 fp_{bit}:")

        for atom_id, radius in bitInfo[bit]:
            if radius == 0:
                continue # skip trivial single-atom features
            try:
                env = Chem.FindAtomEnvironmentOfRadiusN(mol, radius, atom_id)

                # Handle empty environment
                if len(env) == 0:
                    atom = mol.GetAtomWithIdx(atom_id)
                    print(f"  → Atom: {atom.GetSymbol()} (radius {radius})")
                    continue

                submol = Chem.PathToSubmol(mol, env)

                if submol is None:
                    print("  → Substructure: [invalid fragment]")
                    continue

                smiles_sub = Chem.MolToSmiles(submol)

                if smiles_sub.strip() == "":
                    print("  → Substructure: [empty fragment]")
                else:
                    print(f"  → Substructure: {smiles_sub}")

            except Exception as e:
                print(f"  → Error extracting fragment: {e}")

print("\n✅ Interpretation complete.")