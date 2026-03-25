import random
import unittest

import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors

from pipeline_utils import (
    DESCRIPTOR_COLUMNS,
    ThresholdConfig,
    align_features,
    build_fingerprint_columns,
    is_confidence_collapse,
    mutate_smiles,
    process_candidate_dataframe,
    pseudo_label_candidates,
    select_acquisition_portfolio,
    select_feedback_batch,
)
from system_config import default_system_config


class PipelineUtilsTest(unittest.TestCase):
    def test_align_features_preserves_2048_layout(self):
        features = DESCRIPTOR_COLUMNS + build_fingerprint_columns(2048)
        frame = pd.DataFrame(
            [
                {
                    "mw": 100.0,
                    "rdkit_logp": 1.2,
                    "h_donors": 0,
                    "h_acceptors": 1,
                    "fp_0": 1,
                    "fp_5": 1,
                    "fp_9999": 1,
                }
            ]
        )

        aligned = align_features(frame, features)

        self.assertEqual(aligned.shape, (1, len(features)))
        self.assertEqual(aligned.iloc[0]["fp_0"], 1.0)
        self.assertEqual(aligned.iloc[0]["fp_5"], 1.0)
        self.assertEqual(aligned.iloc[0]["fp_2047"], 0.0)

    def test_confidence_collapse_detection(self):
        collapsed, summary = is_confidence_collapse([0.50, 0.51, 0.52], ThresholdConfig())
        self.assertTrue(collapsed)
        self.assertLess(summary["std"], ThresholdConfig().min_confidence_std)

    def test_process_candidate_dataframe_tracks_existing_and_batch_similarity(self):
        config = default_system_config()
        reference = pd.DataFrame([{"smiles": "CCO", "biodegradable": 1}])
        candidates = pd.DataFrame(
            [
                {"polymer": "cand_a", "smiles": "CCO", "biodegradable": -1},
                {"polymer": "cand_b", "smiles": "CCCN", "biodegradable": -1},
                {"polymer": "cand_c", "smiles": "CCCN", "biodegradable": -1},
            ]
        )

        scored, processed = process_candidate_dataframe(candidates, reference, config=config)

        statuses = dict(zip(scored["polymer"], scored["candidate_status"]))
        reasons = dict(zip(scored["polymer"], scored["rejection_reason"]))
        self.assertEqual(statuses["cand_a"], "rejected_existing_similarity")
        self.assertEqual(reasons["cand_a"], "too_similar_to_existing")
        self.assertIn(statuses["cand_b"], {"accepted", "rejected_batch_similarity"})
        self.assertIn(statuses["cand_c"], {"accepted", "rejected_batch_similarity"})
        self.assertEqual(len(processed), 1)
        self.assertIn("batch_max_similarity", scored.columns)

    def test_portfolio_selection_assigns_bucket_quotas(self):
        config = default_system_config()
        rows = []
        for idx in range(10):
            rows.append(
                {
                    "polymer": f"cand_{idx}",
                    "confidence": 0.1 + (idx * 0.08),
                    "uncertainty": 1.0 - (abs((0.1 + (idx * 0.08)) - 0.5) * 2.0),
                    "novelty": 0.2 + (idx * 0.05),
                    "final_score": 0.3 + (idx * 0.04),
                    "passes_diversity_filter": True,
                }
            )
        frame = pd.DataFrame(rows)

        selected = select_acquisition_portfolio(frame, total_candidates=10, config=config)
        counts = selected[selected["accepted_for_feedback"]]["selection_bucket"].value_counts().to_dict()

        self.assertEqual(int(selected["accepted_for_feedback"].sum()), 10)
        self.assertEqual(counts.get("exploit", 0), 4)
        self.assertEqual(counts.get("learn", 0), 3)
        self.assertEqual(counts.get("explore", 0), 3)

    def test_pseudo_label_candidates_only_labels_selected_rows(self):
        frame = pd.DataFrame(
            [
                {"polymer": "a", "confidence": 0.91, "accepted_for_feedback": True},
                {"polymer": "b", "confidence": 0.51, "accepted_for_feedback": True},
                {"polymer": "c", "confidence": 0.05, "accepted_for_feedback": False},
            ]
        )

        labeled = pseudo_label_candidates(frame)
        labels = dict(zip(labeled["polymer"], labeled["pseudo_label"]))

        self.assertEqual(labels["a"], 1)
        self.assertEqual(labels["b"], -1)
        self.assertEqual(labels["c"], -1)
        self.assertTrue(bool(labeled.loc[labeled["polymer"] == "b", "review_candidate"].iloc[0]))
        self.assertFalse(bool(labeled.loc[labeled["polymer"] == "c", "review_candidate"].iloc[0]))

    def test_select_feedback_batch_stays_balanced(self):
        frame = pd.DataFrame(
            [
                {"polymer": "p1", "pseudo_label": 1, "confidence": 0.95, "novelty": 0.4, "selected_for_feedback": True},
                {"polymer": "p2", "pseudo_label": 1, "confidence": 0.85, "novelty": 0.5, "selected_for_feedback": True},
                {"polymer": "n1", "pseudo_label": 0, "confidence": 0.05, "novelty": 0.6, "selected_for_feedback": True},
            ]
        )

        selected = select_feedback_batch(frame, per_class=2)
        counts = selected["pseudo_label"].value_counts().to_dict()

        self.assertEqual(counts.get(1, 0), 1)
        self.assertEqual(counts.get(0, 0), 1)

    def test_mutate_smiles_produces_valid_candidate_within_mw_bounds(self):
        config = default_system_config()
        rng = random.Random(42)
        generated = []
        for _ in range(20):
            candidate, _ = mutate_smiles("CCOCC", rng, config=config)
            if candidate:
                generated.append(candidate)

        self.assertTrue(generated)
        for smiles in generated:
            mol = Chem.MolFromSmiles(smiles)
            self.assertIsNotNone(mol)
            mw = Descriptors.MolWt(mol)
            self.assertGreaterEqual(mw, config.generator.min_mw)
            self.assertLessEqual(mw, config.generator.max_mw)


if __name__ == "__main__":
    unittest.main()
