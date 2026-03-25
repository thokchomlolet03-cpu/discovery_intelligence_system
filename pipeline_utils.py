import json
import random
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem, Descriptors
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.calibration import calibrate_model
from system_config import SystemConfig, config_to_dict, default_system_config, system_config_from_dict


DESCRIPTOR_COLUMNS = ["mw", "rdkit_logp", "h_donors", "h_acceptors"]
DEFAULT_FINGERPRINT_BITS = 2048
DEFAULT_FINGERPRINT_COLUMNS = [f"fp_{idx}" for idx in range(DEFAULT_FINGERPRINT_BITS)]
FINGERPRINT_BITS = DEFAULT_FINGERPRINT_BITS
FINGERPRINT_COLUMNS = DEFAULT_FINGERPRINT_COLUMNS
MODEL_FEATURES = DESCRIPTOR_COLUMNS + DEFAULT_FINGERPRINT_COLUMNS

DEFAULT_MODEL_PATH = Path("rf_model_v1.joblib")
DEFAULT_DATA_PATH = Path("data.csv")
DEFAULT_CANDIDATE_PATH = Path("candidates.csv")
DEFAULT_GENERATED_CANDIDATE_PATH = Path("generated_candidates.csv")
DEFAULT_PROCESSED_CANDIDATE_PATH = Path("candidates_processed.csv")
DEFAULT_PREDICTED_CANDIDATE_PATH = Path("predicted_candidates.csv")
DEFAULT_LABELED_CANDIDATE_PATH = Path("labeled_candidates.csv")
DEFAULT_RESULTS_PATH = Path("candidates_results.csv")
DEFAULT_REVIEW_QUEUE_PATH = Path("review_queue.csv")
DEFAULT_LOG_PATH = Path("logs.json")
DEFAULT_EVALUATION_PATH = Path("evaluation_summary.json")
DEFAULT_ITERATION_HISTORY_PATH = Path("iteration_history.csv")
DEFAULT_RUN_CONFIG_PATH = Path("run_config.json")
DEFAULT_DECISION_OUTPUT_PATH = Path("decision_output.json")

RDLogger.DisableLog("rdApp.*")


@dataclass(frozen=True)
class ThresholdConfig:
    positive: float = 0.7
    negative: float = 0.3
    min_confidence_std: float = 0.05
    min_confidence_span: float = 0.25


def resolve_system_config(config=None, seed=None):
    if config is None:
        return default_system_config(seed=42 if seed is None else seed)
    if isinstance(config, SystemConfig):
        if seed is None:
            return config
        return replace(
            config,
            model=replace(config.model, random_state=seed),
            loop=replace(config.loop, seed=seed),
        )
    merged = system_config_from_dict(config)
    return resolve_system_config(merged, seed=seed)


def bundle_config(bundle):
    return resolve_system_config(bundle.get("config"))


def canonicalize_smiles(smiles):
    if pd.isna(smiles):
        return None
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def molecule_from_smiles(smiles):
    canonical = canonicalize_smiles(smiles)
    if canonical is None:
        return None, None
    return canonical, Chem.MolFromSmiles(canonical)


def infer_fingerprint_columns(df):
    fp_cols = sorted(
        [col for col in df.columns if str(col).startswith("fp_")],
        key=lambda name: int(str(name).split("_")[1]),
    )
    return fp_cols or list(DEFAULT_FINGERPRINT_COLUMNS)


def feature_columns_from_df(df):
    return list(DESCRIPTOR_COLUMNS) + infer_fingerprint_columns(df)


def compute_descriptors(mol):
    return {
        "mw": float(Descriptors.MolWt(mol)),
        "rdkit_logp": float(Descriptors.MolLogP(mol)),
        "h_donors": int(Descriptors.NumHDonors(mol)),
        "h_acceptors": int(Descriptors.NumHAcceptors(mol)),
    }


def compute_fingerprint(mol, n_bits=DEFAULT_FINGERPRINT_BITS):
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=n_bits)
    arr = np.zeros((n_bits,), dtype=int)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def build_fingerprint_columns(n_bits):
    return [f"fp_{idx}" for idx in range(n_bits)]


def featurize_dataframe(df, smiles_column="smiles", fingerprint_columns=None):
    fp_columns = list(fingerprint_columns or infer_fingerprint_columns(df))
    n_bits = len(fp_columns)
    model_features = list(DESCRIPTOR_COLUMNS) + fp_columns
    cleaned_rows = []

    for row in df.to_dict("records"):
        canonical, mol = molecule_from_smiles(row.get(smiles_column))
        if mol is None:
            continue

        base = dict(row)
        base[smiles_column] = canonical
        base.update(compute_descriptors(mol))

        fp = compute_fingerprint(mol, n_bits=n_bits)
        for idx, bit in enumerate(fp):
            base[fp_columns[idx]] = int(bit)

        cleaned_rows.append(base)

    if not cleaned_rows:
        columns = list(dict.fromkeys(list(df.columns) + model_features))
        return pd.DataFrame(columns=columns)

    featurized = pd.DataFrame(cleaned_rows)
    for col in model_features:
        if col not in featurized.columns:
            featurized[col] = 0
    return featurized


def load_dataset(path=DEFAULT_DATA_PATH, featurize=True):
    df = pd.read_csv(path)
    if "smiles" in df.columns:
        df["smiles"] = df["smiles"].apply(canonicalize_smiles)
        df = df[df["smiles"].notna()].reset_index(drop=True)

    if featurize:
        features = feature_columns_from_df(df)
        missing = [col for col in features if col not in df.columns]
        if missing:
            df = featurize_dataframe(df, fingerprint_columns=features[len(DESCRIPTOR_COLUMNS) :])
        else:
            for col in features:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def clean_labels(df):
    cleaned = df.copy()
    cleaned = cleaned[cleaned["biodegradable"].isin([-1, 0, 1])].reset_index(drop=True)
    return cleaned


def labeled_subset(df):
    return df[df["biodegradable"].isin([0, 1])].copy()


def ensure_training_labels(y):
    if y.nunique() < 2:
        raise ValueError("Training requires both positive and negative labeled samples.")


def calibration_cv_splits(y, desired_splits):
    min_class_count = int(y.value_counts().min())
    return max(2, min(desired_splits, min_class_count))


def build_model(calibration_method="isotonic", config=None, random_state=None, calibration_cv=None):
    cfg = resolve_system_config(config, seed=random_state)
    base_model = RandomForestClassifier(
        n_estimators=cfg.model.n_estimators,
        random_state=cfg.model.random_state if random_state is None else random_state,
        class_weight=cfg.model.class_weight,
        min_samples_leaf=cfg.model.min_samples_leaf,
        n_jobs=-1,
    )
    effective_cv = max(2, cfg.model.calibration_cv if calibration_cv is None else calibration_cv)
    calibrated = calibrate_model(base_model, method=calibration_method, cv=effective_cv)
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", calibrated),
        ]
    )


def summarize_series(values):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"count": 0, "min": None, "max": None, "mean": None, "std": None}
    return {
        "count": int(arr.size),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
    }


def quantile_summary(values, quantiles=(0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {str(q): None for q in quantiles}
    return {str(q): float(np.quantile(arr, q)) for q in quantiles}


def log_distribution(prefix, values):
    summary = summarize_series(values)
    if summary["count"] == 0:
        print(f"{prefix}: count=0")
        return
    print(
        f"{prefix}: count={summary['count']} min={summary['min']:.4f} "
        f"max={summary['max']:.4f} mean={summary['mean']:.4f} std={summary['std']:.4f}"
    )


def clip_probabilities(probabilities, eps):
    arr = np.asarray(probabilities, dtype=float)
    return np.clip(arr, eps, 1.0 - eps)


def per_class_probability_summary(y_true, probabilities):
    y_arr = np.asarray(y_true)
    probs = np.asarray(probabilities, dtype=float)
    return {
        f"true_{label}": {
            "summary": summarize_series(probs[y_arr == label]),
            "quantiles": quantile_summary(probs[y_arr == label]),
        }
        for label in sorted(set(y_arr.tolist()))
    }


def holdout_metrics(y_true, y_pred, raw_probabilities, clipped_probabilities):
    y_true_arr = np.asarray(y_true, dtype=int)
    raw_probs = np.asarray(raw_probabilities, dtype=float)
    probs = np.asarray(clipped_probabilities, dtype=float)
    exact_zero = np.isclose(raw_probs, 0.0)
    exact_one = np.isclose(raw_probs, 1.0)

    return {
        "accuracy": float(accuracy_score(y_true_arr, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true_arr, y_pred)),
        "f1_macro": float(f1_score(y_true_arr, y_pred, average="macro")),
        "brier_score": float(brier_score_loss(y_true_arr, probs)),
        "log_loss": float(log_loss(y_true_arr, np.column_stack([1.0 - probs, probs]), labels=[0, 1])),
        "confusion_matrix": confusion_matrix(y_true_arr, y_pred).tolist(),
        "classification_report": classification_report(y_true_arr, y_pred, output_dict=True),
        "confidence_summary": summarize_series(probs),
        "raw_confidence_summary": summarize_series(raw_probs),
        "confidence_quantiles": quantile_summary(probs),
        "raw_confidence_quantiles": quantile_summary(raw_probs),
        "exact_zero_rate_raw": float(np.mean(exact_zero)),
        "exact_one_rate_raw": float(np.mean(exact_one)),
        "exact_confidence_rate_raw": float(np.mean(exact_zero | exact_one)),
        "per_class_probability_summary": per_class_probability_summary(y_true_arr, probs),
    }


def evaluation_summary(model, X, y, config=None):
    cfg = resolve_system_config(config)
    class_counts = y.value_counts().to_dict()
    min_class_count = min(class_counts.values())
    splits = max(2, min(cfg.model.evaluation_cv_splits, min_class_count))
    cv = StratifiedKFold(n_splits=splits, shuffle=True, random_state=cfg.model.random_state)
    metrics = {}
    for metric in ("accuracy", "balanced_accuracy", "f1_macro"):
        scores = cross_val_score(model, X, y, cv=cv, scoring=metric)
        metrics[metric] = {
            "mean": float(np.mean(scores)),
            "std": float(np.std(scores)),
            "scores": [float(score) for score in scores],
        }
    return metrics


def benchmark_model_candidates(X_train, y_train, X_test, y_test, config=None):
    cfg = resolve_system_config(config)
    benchmark = []
    calibration_cv = calibration_cv_splits(y_train, cfg.model.calibration_cv)

    for method in cfg.model.calibration_methods:
        method_cfg = replace(cfg, model=replace(cfg.model, calibration_cv=calibration_cv))
        candidate_model = build_model(calibration_method=method, config=method_cfg)
        candidate_model.fit(X_train, y_train)

        raw_probs = candidate_model.predict_proba(X_test)[:, 1]
        clipped_probs = clip_probabilities(raw_probs, cfg.model.probability_clip)
        y_pred = candidate_model.predict(X_test)
        metrics = holdout_metrics(y_test, y_pred, raw_probs, clipped_probs)

        benchmark.append(
            {
                "name": f"rf_{method}",
                "calibration_method": method,
                "metrics": metrics,
                "model": candidate_model,
            }
        )

    benchmark.sort(
        key=lambda item: (
            item["metrics"]["brier_score"],
            -item["metrics"]["balanced_accuracy"],
            item["metrics"]["exact_confidence_rate_raw"],
            item["metrics"]["log_loss"],
        )
    )
    return benchmark


def train_model(df, random_state=42, config=None):
    cfg = resolve_system_config(config, seed=random_state)
    labeled = labeled_subset(df)
    features = feature_columns_from_df(labeled if not labeled.empty else df)
    X = labeled.reindex(columns=features).fillna(0).astype(float)
    y = labeled["biodegradable"].astype(int)

    ensure_training_labels(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=cfg.model.test_size,
        random_state=cfg.model.random_state,
        stratify=y,
    )

    benchmark = benchmark_model_candidates(X_train, y_train, X_test, y_test, config=cfg)
    selected = benchmark[0]
    selected_method = selected["calibration_method"]

    full_calibration_cv = calibration_cv_splits(y, cfg.model.calibration_cv)
    cv_metrics = evaluation_summary(
        build_model(calibration_method=selected_method, config=cfg, calibration_cv=full_calibration_cv),
        X,
        y,
        config=cfg,
    )

    final_model = build_model(calibration_method=selected_method, config=cfg, calibration_cv=full_calibration_cv)
    final_model.fit(X, y)
    final_model.feature_order_ = list(X.columns)

    benchmark_summary = [
        {
            "name": candidate["name"],
            "calibration_method": candidate["calibration_method"],
            "metrics": candidate["metrics"],
        }
        for candidate in benchmark
    ]

    bundle = {
        "model": final_model,
        "features": list(X.columns),
        "descriptor_features": list(DESCRIPTOR_COLUMNS),
        "fingerprint_bits": int(len(features) - len(DESCRIPTOR_COLUMNS)),
        "thresholds": asdict(ThresholdConfig(
            positive=cfg.pseudo_label.positive,
            negative=cfg.pseudo_label.negative,
            min_confidence_std=cfg.pseudo_label.min_confidence_std,
            min_confidence_span=cfg.pseudo_label.min_confidence_span,
        )),
        "config": config_to_dict(cfg),
        "selected_model": {
            "name": selected["name"],
            "calibration_method": selected_method,
        },
        "benchmark": benchmark_summary,
        "metrics": {
            "cv": cv_metrics,
            "holdout": selected["metrics"],
        },
    }
    return bundle


def save_model_bundle(bundle, path=DEFAULT_MODEL_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def load_model_bundle(path=DEFAULT_MODEL_PATH):
    return joblib.load(path)


def model_features(bundle):
    model = bundle.get("model")
    if model is not None and hasattr(model, "feature_order_"):
        return list(model.feature_order_)
    return list(bundle.get("features", MODEL_FEATURES))


def align_features(df, features):
    aligned = df.reindex(columns=features).copy()
    missing = [feature for feature in features if feature not in df.columns]
    extra = [col for col in df.columns if str(col).startswith("fp_") and col not in features]
    aligned = aligned.fillna(0).astype(float)
    if missing:
        print(f"Feature alignment: filled {len(missing)} missing columns with 0")
    if extra:
        print(f"Feature alignment: ignored {len(extra)} extra fingerprint columns")
    return aligned


def predict_with_model(bundle, df, config=None):
    cfg = resolve_system_config(config or bundle.get("config"))
    model = bundle["model"]
    features = model_features(bundle)
    scored = df.copy()
    X = align_features(scored, features)
    raw_probs = model.predict_proba(X)[:, 1]
    probs = clip_probabilities(raw_probs, cfg.model.probability_clip)

    scored["confidence"] = probs
    scored["uncertainty"] = 1.0 - (np.abs(probs - 0.5) * 2.0)
    if "novelty" not in scored.columns:
        scored["novelty"] = pd.to_numeric(scored.get("novel_to_dataset", 0), errors="coerce").fillna(0)
    else:
        scored["novelty"] = pd.to_numeric(scored["novelty"], errors="coerce").fillna(0)
    scored["final_score"] = (
        cfg.acquisition.w_conf * scored["confidence"]
        + cfg.acquisition.w_novelty * scored["novelty"]
        + cfg.acquisition.w_uncertainty * scored["uncertainty"]
    )
    return scored


def selection_counts(df):
    if "accepted_for_feedback" not in df.columns:
        return {}
    selected = df[df["accepted_for_feedback"]]
    if selected.empty:
        return {}
    return {str(key): int(value) for key, value in selected["selection_bucket"].value_counts().items()}


def allocate_bucket_counts(total, config=None):
    cfg = resolve_system_config(config)
    fractions = {
        "exploit": cfg.acquisition.exploit_fraction,
        "learn": cfg.acquisition.uncertainty_fraction,
        "explore": cfg.acquisition.novelty_fraction,
    }
    raw_counts = {bucket: total * weight for bucket, weight in fractions.items()}
    base_counts = {bucket: int(np.floor(value)) for bucket, value in raw_counts.items()}
    remainder = total - sum(base_counts.values())
    if remainder > 0:
        ranked = sorted(
            fractions,
            key=lambda bucket: (raw_counts[bucket] - base_counts[bucket], fractions[bucket]),
            reverse=True,
        )
        for bucket in ranked[:remainder]:
            base_counts[bucket] += 1
    return base_counts


def rank_bucket_candidates(df, bucket):
    if bucket == "exploit":
        return df.sort_values(["final_score", "novelty", "uncertainty"], ascending=[False, False, False])
    if bucket == "learn":
        return df.sort_values(["uncertainty", "final_score", "novelty"], ascending=[False, False, False])
    if bucket == "explore":
        return df.sort_values(["novelty", "final_score", "uncertainty"], ascending=[False, False, False])
    return df.sort_values(["final_score", "uncertainty", "novelty"], ascending=[False, False, False])


def select_acquisition_portfolio(df, total_candidates=None, config=None):
    cfg = resolve_system_config(config)
    annotated = df.copy().reset_index(drop=True)
    if annotated.empty:
        annotated["accepted_for_feedback"] = False
        annotated["selection_bucket"] = ""
        annotated["selection_reason"] = ""
        return annotated

    if "passes_diversity_filter" in annotated.columns:
        candidate_pool = annotated[annotated["passes_diversity_filter"]].copy()
    else:
        candidate_pool = annotated.copy()

    total = min(
        len(candidate_pool),
        total_candidates if total_candidates is not None else cfg.loop.candidates_per_round,
    )
    quotas = allocate_bucket_counts(total, config=cfg)

    annotated["accepted_for_feedback"] = False
    annotated["selection_bucket"] = ""
    annotated["selection_reason"] = ""

    selected_indices = set()
    for bucket in ("exploit", "learn", "explore"):
        ranking = rank_bucket_candidates(candidate_pool, bucket)
        picked = 0
        for idx in ranking.index:
            if idx in selected_indices:
                continue
            selected_indices.add(idx)
            annotated.loc[idx, "accepted_for_feedback"] = True
            annotated.loc[idx, "selection_bucket"] = bucket
            annotated.loc[idx, "selection_reason"] = f"{bucket}_quota_rank"
            picked += 1
            if picked >= quotas[bucket]:
                break

    if len(selected_indices) < total:
        fallback = rank_bucket_candidates(candidate_pool.loc[~candidate_pool.index.isin(selected_indices)], "exploit")
        for idx in fallback.index:
            selected_indices.add(idx)
            annotated.loc[idx, "accepted_for_feedback"] = True
            annotated.loc[idx, "selection_bucket"] = "exploit"
            annotated.loc[idx, "selection_reason"] = "quota_backfill_by_final_score"
            if len(selected_indices) >= total:
                break

    return annotated


def confidence_series_for_labeling(df):
    if "accepted_for_feedback" in df.columns:
        selected = df[df["accepted_for_feedback"]]
        if not selected.empty:
            return selected["confidence"]
    return df["confidence"]


def is_confidence_collapse(confidence, threshold_cfg):
    summary = summarize_series(confidence)
    if summary["count"] == 0:
        return False, summary
    span = summary["max"] - summary["min"]
    collapsed = summary["std"] < threshold_cfg.min_confidence_std or span < threshold_cfg.min_confidence_span
    summary["span"] = float(span)
    return collapsed, summary


def pseudo_label_candidates(df, thresholds=None, config=None):
    cfg = resolve_system_config(config)
    threshold_cfg = (
        ThresholdConfig(**thresholds)
        if thresholds is not None
        else ThresholdConfig(
            positive=cfg.pseudo_label.positive,
            negative=cfg.pseudo_label.negative,
            min_confidence_std=cfg.pseudo_label.min_confidence_std,
            min_confidence_span=cfg.pseudo_label.min_confidence_span,
        )
    )

    labeled = df.copy()
    if "accepted_for_feedback" not in labeled.columns:
        labeled["accepted_for_feedback"] = True

    labeled["pseudo_label"] = -1
    labeled["selected_for_feedback"] = False
    labeled["review_candidate"] = False

    collapse_confidence = confidence_series_for_labeling(labeled)
    collapsed, summary = is_confidence_collapse(collapse_confidence, threshold_cfg)
    print(
        "Confidence distribution:",
        json.dumps(
            {
                key: round(value, 4) if isinstance(value, float) else value
                for key, value in summary.items()
            }
        ),
    )

    accepted_mask = labeled["accepted_for_feedback"].fillna(False)
    if collapsed:
        print("Confidence collapse detected; rejecting pseudo-label assignment for this batch")
        labeled.loc[accepted_mask, "review_candidate"] = True
        return labeled

    positive_mask = accepted_mask & (labeled["confidence"] > threshold_cfg.positive)
    negative_mask = accepted_mask & (labeled["confidence"] < threshold_cfg.negative)

    labeled.loc[positive_mask, "pseudo_label"] = 1
    labeled.loc[negative_mask, "pseudo_label"] = 0
    labeled.loc[accepted_mask & (labeled["pseudo_label"] != -1), "selected_for_feedback"] = True
    labeled.loc[accepted_mask & (labeled["pseudo_label"] == -1), "review_candidate"] = True

    accepted = int(labeled["selected_for_feedback"].sum())
    rejected = int((accepted_mask & (labeled["pseudo_label"] == -1)).sum())
    print(f"Pseudo-label acceptance: accepted={accepted} rejected={rejected}")
    return labeled


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


def candidate_similarity_table(df, reference_smiles, config=None):
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
        prepared["_fingerprint"] = candidate_fp
        prepared_rows.append(prepared)

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


def select_feedback_batch(df, per_class=5):
    eligible = df.copy()
    if "selected_for_feedback" in eligible.columns:
        eligible = eligible[eligible["selected_for_feedback"]]

    pos = eligible[eligible["pseudo_label"] == 1].sort_values(
        ["confidence", "novelty"], ascending=[False, False]
    )
    neg = eligible[eligible["pseudo_label"] == 0].sort_values(
        ["confidence", "novelty"], ascending=[True, False]
    )
    n = min(len(pos), len(neg), per_class)

    if n == 0:
        print("Skipping iteration due to imbalance")
        return df.iloc[0:0].copy()

    selected = pd.concat([pos.head(n), neg.head(n)], ignore_index=True)
    print(f"Balanced feedback selection: positive={n} negative={n}")
    return selected


def append_feedback_to_dataset(dataset_df, selected_df):
    if selected_df.empty:
        print("No feedback rows added to dataset")
        return dataset_df.copy()

    pos = selected_df[selected_df["pseudo_label"] == 1]
    neg = selected_df[selected_df["pseudo_label"] == 0]
    n = min(len(pos), len(neg))
    if n == 0:
        print("Skipping dataset update due to unbalanced feedback")
        return dataset_df.copy()

    feedback = pd.concat([pos.head(n), neg.head(n)], ignore_index=True).copy()
    feedback["biodegradable"] = feedback["pseudo_label"]
    feedback = feedback.drop(
        columns=[
            "pseudo_label",
            "selected_for_feedback",
            "review_candidate",
            "accepted_for_feedback",
            "confidence",
            "uncertainty",
            "final_score",
            "passes_reference_filter",
            "passes_batch_filter",
            "passes_diversity_filter",
            "batch_max_similarity",
            "max_similarity",
            "novelty",
            "selection_bucket",
            "selection_reason",
            "candidate_status",
            "acceptance_reason",
            "rejection_reason",
            "generation_strategy",
            "generation_attempts",
            "is_feasible",
            "feasibility_reason",
            "experiment_value",
            "risk_level",
        ],
        errors="ignore",
    )

    combined = pd.concat([dataset_df, feedback], ignore_index=True)
    combined = combined.drop_duplicates(subset=["smiles", "biodegradable"], keep="first")
    featurized = featurize_dataframe(
        combined,
        fingerprint_columns=infer_fingerprint_columns(dataset_df),
    )
    print(f"Dataset update: added={len(feedback)} total={len(featurized)}")
    return featurized


def extract_feature_importances(bundle):
    pipeline = bundle["model"]
    features = model_features(bundle)
    calibrated = pipeline.named_steps["clf"]
    estimators = []

    if hasattr(calibrated, "calibrated_classifiers_"):
        for calibrated_model in calibrated.calibrated_classifiers_:
            estimator = None
            for attr in ("estimator", "base_estimator", "classifier"):
                estimator = getattr(calibrated_model, attr, None)
                if estimator is not None:
                    break
            if estimator is not None and hasattr(estimator, "feature_importances_"):
                estimators.append(estimator.feature_importances_)

    if hasattr(calibrated, "feature_importances_"):
        estimators.append(calibrated.feature_importances_)

    if not estimators:
        raise ValueError("Feature importances are unavailable for the current model bundle.")

    averaged = np.mean(np.vstack(estimators), axis=0)
    return pd.Series(averaged, index=features)


def bundle_evaluation_summary(bundle):
    return {
        "selected_model": bundle.get("selected_model", {}),
        "benchmark": bundle.get("benchmark", []),
        "metrics": bundle.get("metrics", {}),
        "thresholds": bundle.get("thresholds", {}),
        "config": bundle.get("config", {}),
    }


def write_json_log(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def write_dataframe(path, df):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_run_config(path, config):
    write_json_log(path, config_to_dict(resolve_system_config(config)))


def write_evaluation_summary(path, bundle):
    write_json_log(path, bundle_evaluation_summary(bundle))


def flatten_iteration_record(record):
    flat = {
        "iteration": record["iteration"],
        "dataset_size": record["dataset_size"],
        "selected_feedback": record["selected_feedback"],
        "review_queue": record["review_queue"],
        "processed_candidates": record["processed_candidates"],
        "generated_candidates": record["generated_candidates"],
        "portfolio_selected": record["portfolio_selected"],
        "appended_feedback": record["appended_feedback"],
        "dry_run": record["dry_run"],
        "selected_model": record["selected_model"]["name"],
        "calibration_method": record["selected_model"]["calibration_method"],
        "holdout_accuracy": record["holdout"]["accuracy"],
        "holdout_balanced_accuracy": record["holdout"]["balanced_accuracy"],
        "holdout_f1_macro": record["holdout"]["f1_macro"],
        "holdout_brier_score": record["holdout"]["brier_score"],
        "holdout_log_loss": record["holdout"]["log_loss"],
        "holdout_exact_confidence_rate_raw": record["holdout"]["exact_confidence_rate_raw"],
        "feasible_candidates": record.get("feasible_candidates", 0),
        "infeasible_candidates": record.get("infeasible_candidates", 0),
        "decision_high_risk": record.get("decision_risk_counts", {}).get("high", 0),
        "decision_medium_risk": record.get("decision_risk_counts", {}).get("medium", 0),
        "decision_low_risk": record.get("decision_risk_counts", {}).get("low", 0),
        "top_experiment_value": record.get("top_experiment_value", 0.0),
    }
    for label, value in record["label_counts"].items():
        flat[f"label_{label}"] = value
    for bucket, value in record["selection_counts"].items():
        flat[f"selection_{bucket}"] = value
    for reason, value in record["candidate_rejections"].items():
        flat[f"rejected_{reason}"] = value
    for reason, value in record.get("feasibility_rejections", {}).items():
        flat[f"infeasible_{reason}"] = value
    return flat


def write_iteration_history(path, records):
    rows = [flatten_iteration_record(record) for record in records]
    frame = pd.DataFrame(rows)
    write_dataframe(path, frame)
