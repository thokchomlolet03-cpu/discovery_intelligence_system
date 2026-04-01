import unittest

import pandas as pd

from features.rdkit_features import build_features
from system.services.regression_service import predict_regression_with_model, train_regression_model


class RegressionServiceTest(unittest.TestCase):
    def _training_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"smiles": "CCO", "target_value": 5.1},
                {"smiles": "CCN", "target_value": 5.5},
                {"smiles": "CCC", "target_value": 4.8},
                {"smiles": "CCCl", "target_value": 4.2},
                {"smiles": "CCBr", "target_value": 4.0},
                {"smiles": "CC(=O)O", "target_value": 6.0},
                {"smiles": "c1ccccc1", "target_value": 3.8},
                {"smiles": "c1ccncc1", "target_value": 4.4},
            ]
        )

    def test_train_regression_model_returns_regression_bundle(self):
        bundle = train_regression_model(self._training_frame(), random_state=42)

        self.assertEqual(bundle["model_kind"], "regression")
        self.assertIn("holdout", bundle["metrics"])
        self.assertIn("rmse", bundle["metrics"]["holdout"])
        self.assertIn("target_summary", bundle)

    def test_predict_regression_with_model_populates_regression_fields(self):
        bundle = train_regression_model(self._training_frame(), random_state=42)
        _, clean = build_features(self._training_frame().copy())

        scored = predict_regression_with_model(
            {
                **bundle,
                "target_definition": {"optimization_direction": "maximize"},
            },
            clean,
            optimization_direction="maximize",
        )

        self.assertIn("predicted_value", scored.columns)
        self.assertIn("prediction_dispersion", scored.columns)
        self.assertIn("confidence", scored.columns)
        self.assertIn("uncertainty", scored.columns)
        self.assertTrue(scored["confidence"].between(0.0, 1.0).all())
        self.assertTrue((scored["prediction_dispersion"] >= 0.0).all())


if __name__ == "__main__":
    unittest.main()
