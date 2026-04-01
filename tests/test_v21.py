import unittest

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from decision.decision_engine import build_decision_package, risk_level
from experiment.value_function import compute_experiment_value
from filters.feasibility import annotate_feasibility, feasibility_reason, is_feasible
from models.calibration import calibrate_model


class V21Test(unittest.TestCase):
    def test_calibration_helper_returns_predict_proba_model(self):
        X = pd.DataFrame({"x1": [0, 1, 0, 1, 0, 1, 0, 1], "x2": [0, 0, 1, 1, 0, 0, 1, 1]})
        y = pd.Series([0, 0, 0, 1, 0, 1, 1, 1])

        calibrated = calibrate_model(RandomForestClassifier(n_estimators=10, random_state=42), method="sigmoid", cv=2)
        calibrated.fit(X, y)

        probs = calibrated.predict_proba(X)
        self.assertEqual(probs.shape, (8, 2))

    def test_feasibility_annotations_are_stable(self):
        frame = pd.DataFrame(
            [
                {"smiles": "CCO"},
                {"smiles": "not-a-smiles"},
                {"smiles": "C" * 100},
                {"smiles": ".".join(["c1ccccc1"] * 6)},
            ]
        )

        annotated = annotate_feasibility(frame)

        self.assertTrue(bool(annotated.loc[0, "is_feasible"]))
        self.assertEqual(annotated.loc[1, "feasibility_reason"], "invalid_smiles")
        self.assertEqual(annotated.loc[2, "feasibility_reason"], "molecular_weight_too_high")
        self.assertEqual(annotated.loc[3, "feasibility_reason"], "ring_count_too_high")
        self.assertTrue(is_feasible("CCO"))
        self.assertEqual(feasibility_reason("not-a-smiles"), "invalid_smiles")

    def test_experiment_value_matches_configured_formula(self):
        row = {"uncertainty": 0.8, "novelty": 0.4, "confidence": 0.25}

        value = compute_experiment_value(row)

        self.assertAlmostEqual(value, 0.67, places=6)

    def test_decision_engine_ranks_and_assigns_risk(self):
        frame = pd.DataFrame(
            [
                {
                    "polymer": "cand_a",
                    "smiles": "CCO",
                    "confidence": 0.4,
                    "uncertainty": 0.8,
                    "novelty": 0.7,
                    "experiment_value": 0.9,
                    "selection_bucket": "learn",
                    "accepted_for_feedback": True,
                    "rdkit_logp": -0.2,
                    "mw": 120.0,
                    "h_acceptors": 5,
                },
                {
                    "polymer": "cand_b",
                    "smiles": "CCN",
                    "confidence": 0.9,
                    "uncertainty": 0.2,
                    "novelty": 0.2,
                    "experiment_value": 0.3,
                    "selection_bucket": "exploit",
                    "accepted_for_feedback": False,
                    "rdkit_logp": 1.2,
                    "mw": 300.0,
                    "h_acceptors": 1,
                },
            ]
        )

        decision = build_decision_package(frame, iteration=3)

        self.assertEqual(decision["iteration"], 3)
        self.assertEqual(decision["top_experiments"][0]["smiles"], "CCO")
        self.assertEqual(decision["top_experiments"][0]["risk"], "high")
        self.assertIn("low logP is one of the chemistry features influencing this model judgment", decision["top_experiments"][0]["explanation"])
        self.assertEqual(risk_level(frame.iloc[1]), "low")

    def test_decision_engine_keeps_target_specific_biodegradability_rules_when_target_matches(self):
        frame = pd.DataFrame(
            [
                {
                    "polymer": "cand_a",
                    "smiles": "CCO",
                    "confidence": 0.4,
                    "uncertainty": 0.8,
                    "novelty": 0.7,
                    "experiment_value": 0.9,
                    "selection_bucket": "learn",
                    "accepted_for_feedback": True,
                    "rdkit_logp": -0.2,
                    "mw": 120.0,
                    "h_acceptors": 5,
                }
            ]
        )
        frame.attrs["target_definition"] = {"target_name": "biodegradability"}

        decision = build_decision_package(frame, iteration=1)

        self.assertIn("low logP -> likely biodegradable", decision["top_experiments"][0]["explanation"])


if __name__ == "__main__":
    unittest.main()
