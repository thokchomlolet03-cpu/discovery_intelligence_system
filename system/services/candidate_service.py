from __future__ import annotations

import random
from dataclasses import replace

import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem, Descriptors

from system.services.data_service import (
    DEFAULT_FINGERPRINT_BITS,
    canonicalize_smiles,
    clean_labels,
    featurize_dataframe,
    infer_fingerprint_columns,
    molecule_from_smiles,
    reference_smiles_from_dataset,
)
from system.services.runtime_config import resolve_system_config
from system.services.training_service import log_distribution


OUT_OF_DOMAIN_SAMPLE_LIMIT = 512


def mol_weight_in_range(mol, config=None):
    cfg = resolve_system_config(config)
    mw = float(Descriptors.MolWt(mol))
    return cfg.generator.min_mw <= mw <= cfg.generator.max_mw


def molecule_fingerprint(smiles, n_bits=DEFAULT_FINGERPRINT_BITS):
    canonical, mol = molecule_from_smiles(smiles)
    if mol is None:
        return canonical, None
    return canonical, AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=n_bits)


def build_reference_fingerprints(smiles_list, n_bits=DEFAULT_FINGERPRINT_BITS):
    fingerprints = []
    for smiles in smiles_list:
        canonical, fp = molecule_fingerprint(smiles, n_bits=n_bits)
        if canonical is None or fp is None:
            continue
        fingerprints.append((canonical, fp))
    return fingerprints


def tanimoto_similarity(fp_left, fp_right):
    return float(DataStructs.TanimotoSimilarity(fp_left, fp_right))


def max_similarity_to_reference(candidate_fp, reference_fingerprints):
    if candidate_fp is None or not reference_fingerprints:
        return 0.0
    similarities = [tanimoto_similarity(candidate_fp, reference_fp) for _, reference_fp in reference_fingerprints]
    return max(similarities, default=0.0)


def candidate_similarity_table(df, reference_smiles, config=None, enforce_batch_diversity: bool = True):
    cfg = resolve_system_config(config)
    n_bits = len(infer_fingerprint_columns(df))
    reference_fingerprints = build_reference_fingerprints(reference_smiles, n_bits=n_bits)
    prepared_rows = []

    for original_index, row in enumerate(df.to_dict("records")):
        canonical, candidate_fp = molecule_fingerprint(row.get("smiles"), n_bits=n_bits)
        prepared = dict(row)
        prepared["original_index"] = original_index
        prepared["smiles"] = canonical
        prepared["batch_max_similarity"] = 0.0
        prepared["passes_reference_filter"] = False
        prepared["passes_batch_filter"] = False
        prepared["passes_diversity_filter"] = False
        prepared["candidate_status"] = "invalid_smiles"
        prepared["acceptance_reason"] = ""
        prepared["rejection_reason"] = "invalid_smiles"
        prepared["novel_to_dataset"] = 0

        if canonical is None or candidate_fp is None:
            prepared["max_similarity"] = None
            prepared["novelty"] = None
            prepared_rows.append(prepared)
            continue

        max_similarity = max_similarity_to_reference(candidate_fp, reference_fingerprints)
        prepared["max_similarity"] = float(max_similarity)
        prepared["novelty"] = float(max(0.0, 1.0 - max_similarity))
        prepared["novel_to_dataset"] = int(max_similarity < 1.0)
        if not enforce_batch_diversity:
            prepared["passes_reference_filter"] = bool(
                max_similarity <= cfg.generator.reference_similarity_threshold
            )
            prepared["passes_batch_filter"] = True
            prepared["passes_diversity_filter"] = True
            prepared["candidate_status"] = "accepted"
            prepared["acceptance_reason"] = "retained_for_uploaded_screening"
            prepared["rejection_reason"] = ""
            prepared_rows.append(prepared)
            continue
        prepared["_fingerprint"] = candidate_fp
        prepared_rows.append(prepared)

    if not enforce_batch_diversity:
        ordered_rows = sorted(prepared_rows, key=lambda item: item["original_index"])
        for row in ordered_rows:
            row.pop("original_index", None)
        return pd.DataFrame(ordered_rows)

    ranked_rows = sorted(
        prepared_rows,
        key=lambda item: (
            item["novelty"] is not None,
            item["novelty"] if item["novelty"] is not None else -1.0,
            -(item["max_similarity"] if item["max_similarity"] is not None else 1.0),
            -item["original_index"],
        ),
        reverse=True,
    )

    accepted_batch_fps = []
    for prepared in ranked_rows:
        candidate_fp = prepared.get("_fingerprint")
        if candidate_fp is None:
            continue

        if prepared["max_similarity"] > cfg.generator.reference_similarity_threshold:
            prepared["batch_max_similarity"] = (
                max((tanimoto_similarity(candidate_fp, accepted_fp) for accepted_fp in accepted_batch_fps), default=0.0)
                if accepted_batch_fps
                else 0.0
            )
            prepared["candidate_status"] = "rejected_existing_similarity"
            prepared["rejection_reason"] = "too_similar_to_existing"
            continue

        batch_similarity = (
            max((tanimoto_similarity(candidate_fp, accepted_fp) for accepted_fp in accepted_batch_fps), default=0.0)
            if accepted_batch_fps
            else 0.0
        )
        prepared["batch_max_similarity"] = float(batch_similarity)

        if batch_similarity > cfg.generator.batch_similarity_threshold:
            prepared["candidate_status"] = "rejected_batch_similarity"
            prepared["rejection_reason"] = "too_similar_to_batch"
            continue

        prepared["passes_reference_filter"] = True
        prepared["passes_batch_filter"] = True
        prepared["passes_diversity_filter"] = True
        prepared["candidate_status"] = "accepted"
        prepared["acceptance_reason"] = "passed_reference_and_batch_diversity"
        prepared["rejection_reason"] = ""
        accepted_batch_fps.append(candidate_fp)

    ordered_rows = sorted(ranked_rows, key=lambda item: item["original_index"])
    for row in ordered_rows:
        row.pop("_fingerprint", None)
        row.pop("original_index", None)
    return pd.DataFrame(ordered_rows)


def process_candidate_dataframe(raw_candidates, reference_df, config=None):
    cfg = resolve_system_config(config)
    reference_smiles = reference_df["smiles"].dropna().tolist()
    scored = candidate_similarity_table(raw_candidates, reference_smiles=reference_smiles, config=cfg)
    accepted = scored[scored["passes_diversity_filter"]].copy()
    processed = featurize_dataframe(
        accepted,
        fingerprint_columns=infer_fingerprint_columns(reference_df),
    )
    return scored, processed


def attach_atom_fragment(base_mol, fragment_smiles, rng, config=None):
    fragment = Chem.MolFromSmiles(fragment_smiles)
    if fragment is None:
        return None

    combo = Chem.CombineMols(base_mol, fragment)
    rw = Chem.RWMol(combo)
    base_atoms = base_mol.GetNumAtoms()
    fragment_atoms = fragment.GetNumAtoms()
    base_candidates = [atom.GetIdx() for atom in rw.GetAtoms() if atom.GetIdx() < base_atoms]
    fragment_candidates = [
        atom.GetIdx()
        for atom in rw.GetAtoms()
        if base_atoms <= atom.GetIdx() < base_atoms + fragment_atoms
    ]

    rng.shuffle(base_candidates)
    rng.shuffle(fragment_candidates)

    for base_idx in base_candidates:
        base_atom = rw.GetAtomWithIdx(base_idx)
        if base_atom.GetDegree() >= base_atom.GetTotalValence():
            continue
        for fragment_idx in fragment_candidates:
            if rw.GetBondBetweenAtoms(base_idx, fragment_idx) is not None:
                continue
            trial = Chem.RWMol(rw)
            trial.AddBond(base_idx, fragment_idx, Chem.rdchem.BondType.SINGLE)
            mol = trial.GetMol()
            try:
                Chem.SanitizeMol(mol)
            except Exception:
                continue
            if mol_weight_in_range(mol, config=config):
                return canonicalize_smiles(Chem.MolToSmiles(mol))
    return None


def functional_group_substitution(smiles, rng, config=None):
    cfg = resolve_system_config(config)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return attach_atom_fragment(mol, rng.choice(cfg.generator.functional_groups), rng, config=cfg)


def chain_extension(smiles, rng, config=None):
    cfg = resolve_system_config(config)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return attach_atom_fragment(mol, rng.choice(cfg.generator.chain_extensions), rng, config=cfg)


def ring_addition(smiles, rng, config=None):
    cfg = resolve_system_config(config)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return attach_atom_fragment(mol, rng.choice(cfg.generator.ring_fragments), rng, config=cfg)


def mutate_smiles(smiles, rng, config=None):
    cfg = resolve_system_config(config)
    strategies = [
        ("functional_group_substitution", functional_group_substitution),
        ("chain_extension", chain_extension),
        ("ring_addition", ring_addition),
    ]
    rng.shuffle(strategies)
    for name, strategy in strategies:
        candidate = strategy(smiles, rng, config=cfg)
        if candidate is not None:
            return candidate, name
    return None, None


def generate_candidate_pool(
    df,
    n=30,
    seed=42,
    max_attempt_multiplier=50,
    prefer_balanced_sources=True,
    config=None,
):
    cfg = resolve_system_config(config, seed=seed)
    rng = random.Random(seed)
    source = clean_labels(df)
    source_smiles = source["smiles"].dropna().tolist()
    if not source_smiles:
        raise ValueError("No valid source SMILES found for candidate generation.")

    positive = source[source["biodegradable"] == 1]["smiles"].dropna().tolist()
    negative = source[source["biodegradable"] == 0]["smiles"].dropna().tolist()
    prefer_balanced = prefer_balanced_sources if prefer_balanced_sources is not None else cfg.generator.prefer_balanced_sources

    generated = []
    seen = set(source_smiles)
    attempts_total = 0
    attempts_since_success = 0
    max_attempts = max(n * max_attempt_multiplier, n)

    while len(generated) < n and attempts_total < max_attempts:
        if prefer_balanced and positive and negative:
            pool = positive if len(generated) % 2 == 0 else negative
            base = rng.choice(pool)
        else:
            base = rng.choice(source_smiles)

        candidate, strategy = mutate_smiles(base, rng, config=cfg)
        attempts_total += 1
        attempts_since_success += 1

        if candidate is None or candidate in seen:
            continue

        seen.add(candidate)
        generated.append(
            {
                "polymer": f"cand_{len(generated)}",
                "source_smiles": base,
                "smiles": candidate,
                "biodegradable": -1,
                "generation_strategy": strategy,
                "generation_attempts": attempts_since_success,
                "candidate_status": "generated",
                "acceptance_reason": "valid_guided_mutation",
                "rejection_reason": "",
            }
        )
        attempts_since_success = 0

    return pd.DataFrame(generated)


def generate_candidate_dataframe(
    df,
    n=30,
    seed=42,
    max_attempt_multiplier=50,
    prefer_balanced_sources=True,
    similarity_threshold=None,
    config=None,
):
    cfg = resolve_system_config(config, seed=seed)
    reference_threshold = (
        cfg.generator.reference_similarity_threshold
        if similarity_threshold is None
        else similarity_threshold
    )
    cfg = replace(
        cfg,
        generator=replace(cfg.generator, reference_similarity_threshold=reference_threshold),
    )
    raw_candidates = generate_candidate_pool(
        df,
        n=n,
        seed=seed,
        max_attempt_multiplier=max_attempt_multiplier,
        prefer_balanced_sources=prefer_balanced_sources,
        config=cfg,
    )
    scored, processed = process_candidate_dataframe(raw_candidates, df, config=cfg)
    accepted = int(scored["passes_diversity_filter"].sum()) if not scored.empty else 0
    rejected = int(len(scored) - accepted)
    print(
        f"Candidate diversity filter: accepted={accepted} rejected={rejected} "
        f"threshold={cfg.generator.reference_similarity_threshold}/{cfg.generator.batch_similarity_threshold}"
    )
    if not scored.empty and "novelty" in scored.columns:
        log_distribution("Novelty distribution", scored["novelty"].dropna())
    return processed


def out_of_domain_ratio(df: pd.DataFrame, config) -> float | None:
    reference = reference_smiles_from_dataset()
    if not reference or df.empty:
        return None
    sample = df[["smiles"]].dropna().drop_duplicates(subset=["smiles"]).reset_index(drop=True)
    if sample.empty:
        return None
    if len(sample) > OUT_OF_DOMAIN_SAMPLE_LIMIT:
        sample = sample.sample(n=OUT_OF_DOMAIN_SAMPLE_LIMIT, random_state=0).reset_index(drop=True)

    n_bits = len(infer_fingerprint_columns(df))
    reference_fingerprints = build_reference_fingerprints(reference, n_bits=n_bits)
    if not reference_fingerprints:
        return None

    similarities: list[float] = []
    for smiles in sample["smiles"].tolist():
        _, candidate_fp = molecule_fingerprint(smiles, n_bits=n_bits)
        if candidate_fp is None:
            continue
        similarities.append(float(max_similarity_to_reference(candidate_fp, reference_fingerprints)))

    if not similarities:
        return None
    similarities = pd.to_numeric(pd.Series(similarities), errors="coerce").fillna(0.0)
    return float((similarities < 0.25).mean())


__all__ = [
    "attach_atom_fragment",
    "build_reference_fingerprints",
    "candidate_similarity_table",
    "chain_extension",
    "functional_group_substitution",
    "generate_candidate_dataframe",
    "generate_candidate_pool",
    "max_similarity_to_reference",
    "mol_weight_in_range",
    "molecule_fingerprint",
    "mutate_smiles",
    "out_of_domain_ratio",
    "process_candidate_dataframe",
    "ring_addition",
    "tanimoto_similarity",
]
