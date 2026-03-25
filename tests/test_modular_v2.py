import tempfile
import unittest
from pathlib import Path

import pandas as pd

from experiment.suggest import suggest_experiments
from features.rdkit_features import build_features
from models.uncertainty import compute_uncertainty
from selection.scorer import score_candidates
from selection.selector import select_candidates
from utils.io import load_knowledge, save_knowledge_entries


class ModularV2Test(unittest.TestCase):
    def test_compute_uncertainty_matches_v2_definition(self):
        probs = pd.Series([0.0, 0.25, 0.5, 0.75, 1.0])
        uncertainty = compute_uncertainty(probs)

        self.assertEqual(list(uncertainty.round(4)), [0.0, 0.5, 1.0, 0.5, 0.0])

    def test_build_features_respects_feature_contract(self):
        frame = pd.DataFrame([{"polymer": "p1", "smiles": "CCO", "biodegradable": 1}])
        contract = ["mw", "rdkit_logp", "h_donors", "h_acceptors", "fp_0", "fp_1"]

        X, clean = build_features(frame, feature_contract=contract)

        self.assertEqual(list(X.columns), contract)
        self.assertEqual(X.shape, (1, len(contract)))
        self.assertFalse(clean.columns.duplicated().any())

    def test_score_candidates_applies_weighted_multi_objective_score(self):
        frame = pd.DataFrame(
            [
                {"polymer": "cand", "confidence": 0.8, "novelty": 0.5, "uncertainty": 0.2},
            ]
        )

        scored = score_candidates(frame)

        self.assertAlmostEqual(float(scored.loc[0, "score"]), 0.59, places=6)
        self.assertAlmostEqual(float(scored.loc[0, "final_score"]), 0.59, places=6)

    def test_select_candidates_returns_portfolio_mix(self):
        rows = []
        for idx in range(12):
            confidence = 0.1 + (idx * 0.07)
            rows.append(
                {
                    "polymer": f"cand_{idx}",
                    "confidence": confidence,
                    "uncertainty": float(compute_uncertainty(pd.Series([confidence]))[0]),
                    "novelty": 0.2 + (idx * 0.04),
                    "passes_diversity_filter": True,
                }
            )
        frame = pd.DataFrame(rows)

        selected = select_candidates(frame, 6)
        accepted = selected[selected["accepted_for_feedback"]]

        self.assertEqual(len(accepted), 6)
        self.assertTrue(set(accepted["selection_bucket"]).issubset({"exploit", "learn", "explore"}))

    def test_suggest_and_knowledge_io_work_with_structured_outputs(self):
        frame = pd.DataFrame(
            [
                {"smiles": "CCO", "confidence": 0.5, "novelty": 0.9},
                {"smiles": "CCN", "confidence": 0.8, "novelty": 0.2},
            ]
        )
        suggested = suggest_experiments(frame, top_k=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_path = Path(tmpdir) / "data" / "knowledge.json"
            save_knowledge_entries(
                [
                    {
                        "smiles": suggested.iloc[0]["smiles"],
                        "prediction": 1,
                        "confidence": 0.5,
                        "explanation": "test entry",
                        "iteration": 1,
                    }
                ],
                path=knowledge_path,
            )
            knowledge = load_knowledge(knowledge_path)

        self.assertEqual(len(suggested), 1)
        self.assertEqual(len(knowledge), 1)
        self.assertEqual(knowledge[0]["smiles"], "CCO")


if __name__ == "__main__":
    unittest.main()
