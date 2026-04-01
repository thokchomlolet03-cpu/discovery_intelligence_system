import unittest

from system.services.scientific_output_service import build_model_judgment, build_normalized_explanation, build_scientific_recommendation


class ScientificOutputServiceTest(unittest.TestCase):
    def test_normalized_explanation_uses_explicit_novelty_signal_summary(self):
        explanation = build_normalized_explanation(
            {"confidence": 0.7, "uncertainty": 0.2, "predicted_value": None},
            rationale={"summary": "Candidate remains competitive.", "cautions": []},
            target_definition={"target_name": "pIC50", "target_kind": "classification"},
            model_judgment={"confidence": 0.7},
            decision_policy={"policy_summary": "Current shortlist policy favors this candidate."},
            novelty_signal={"summary": "This candidate adds some structural novelty."},
        )

        self.assertEqual(explanation["novelty_summary"], "This candidate adds some structural novelty.")

    def test_regression_outputs_explain_ranking_compatibility_and_measurement_follow_up(self):
        target_definition = {"target_name": "pIC50", "target_kind": "regression"}
        row = {"confidence": 0.83, "uncertainty": 0.14, "predicted_value": 6.55}

        model_judgment = build_model_judgment(row, target_definition=target_definition)
        explanation = build_normalized_explanation(
            row,
            rationale={"summary": "Candidate remains competitive.", "cautions": []},
            target_definition=target_definition,
            model_judgment=model_judgment,
            decision_policy={"policy_summary": "Current shortlist policy favors this candidate."},
            novelty_signal={"summary": "This candidate adds some structural novelty."},
        )
        recommendation = build_scientific_recommendation(
            {**row, "target_definition": target_definition},
            rationale={"summary": "Candidate remains competitive.", "cautions": []},
        )

        self.assertIn("ranking compatibility", model_judgment["model_summary"].lower())
        self.assertIn("ranking compatibility", explanation["model_judgment_summary"].lower())
        self.assertIn("prediction dispersion", explanation["uncertainty_summary"].lower())
        self.assertIn("validate", explanation["recommended_followup"].lower())
        self.assertIn("predicted value", recommendation["follow_up_experiment"].lower())


if __name__ == "__main__":
    unittest.main()
