import unittest

from system.contracts import (
    ContractValidationError,
    validate_decision_artifact,
    validate_review_event_record,
)


def canonical_decision_artifact() -> dict:
    return {
        "session_id": "session_1",
        "iteration": 1,
        "generated_at": "2026-03-25T12:00:00+00:00",
        "summary": {
            "top_k": 1,
            "candidate_count": 1,
            "risk_counts": {"medium": 1},
            "top_experiment_value": 0.64,
        },
        "top_experiments": [
            {
                "session_id": "session_1",
                "rank": 1,
                "candidate_id": "cand_1",
                "smiles": "CCO",
                "canonical_smiles": "CCO",
                "confidence": 0.74,
                "uncertainty": 0.26,
                "novelty": 0.48,
                "acquisition_score": 0.62,
                "experiment_value": 0.64,
                "bucket": "exploit",
                "risk": "medium",
                "status": "suggested",
                "explanation": ["Balanced scores make this a reasonable candidate for expert review."],
                "provenance": {
                    "text": "Scored directly from user-uploaded dataset upload.csv. Model version: rf_isotonic:isotonic.",
                    "source_name": "upload.csv",
                    "source_type": "uploaded",
                    "parent_molecule": "",
                    "model_version": "rf_isotonic:isotonic",
                },
                "feasibility": {"is_feasible": True, "reason": ""},
                "created_at": "2026-03-25T12:00:00+00:00",
                "model_metadata": {
                    "version": "rf_isotonic:isotonic",
                    "family": "random_forest",
                    "calibration_method": "isotonic",
                },
            }
        ],
    }


class ContractValidationTest(unittest.TestCase):
    def test_valid_decision_artifact_passes_schema_validation(self):
        validated = validate_decision_artifact(canonical_decision_artifact())

        self.assertEqual(validated["session_id"], "session_1")
        self.assertEqual(validated["top_experiments"][0]["candidate_id"], "cand_1")
        self.assertEqual(validated["top_experiments"][0]["bucket"], "exploit")

    def test_malformed_decision_artifact_fails_schema_validation(self):
        invalid = canonical_decision_artifact()
        invalid["top_experiments"][0].pop("bucket")

        with self.assertRaises(ContractValidationError):
            validate_decision_artifact(invalid)

    def test_review_record_validates_correctly(self):
        review = validate_review_event_record(
            {
                "session_id": "session_1",
                "candidate_id": "cand_1",
                "smiles": "CCO",
                "action": "approve",
                "previous_status": "suggested",
                "status": "approved",
                "note": "Looks reasonable",
                "timestamp": "2026-03-25T12:00:00+00:00",
                "reviewed_at": "2026-03-25T12:00:00+00:00",
                "actor": "qa",
                "reviewer": "qa",
                "metadata": {"origin": "unit_test"},
            }
        )

        self.assertEqual(review["status"], "approved")
        self.assertEqual(review["previous_status"], "suggested")
        self.assertEqual(review["reviewer"], "qa")


if __name__ == "__main__":
    unittest.main()
