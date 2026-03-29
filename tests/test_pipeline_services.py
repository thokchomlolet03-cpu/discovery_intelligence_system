import unittest
from unittest.mock import patch

import pandas as pd

from system.contracts import validate_decision_artifact
from system.run_pipeline import run_pipeline
from system.services.data_service import prepare_analysis_dataframe
from system.services.decision_service import decorate_candidates


def canonical_decision_output(session_id: str) -> dict:
    return validate_decision_artifact(
        {
            "session_id": session_id,
            "iteration": 1,
            "generated_at": "2026-03-25T12:00:00+00:00",
            "summary": {
                "top_k": 1,
                "candidate_count": 1,
                "risk_counts": {"low": 1},
                "top_experiment_value": 0.72,
            },
            "top_experiments": [
                {
                    "session_id": session_id,
                    "rank": 1,
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "confidence": 0.91,
                    "uncertainty": 0.10,
                    "novelty": 0.58,
                    "acquisition_score": 0.77,
                    "experiment_value": 0.72,
                    "bucket": "exploit",
                    "risk": "low",
                    "status": "suggested",
                    "explanation": ["High confidence makes this a practical exploit candidate for review."],
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
    )


class PipelineServicesTest(unittest.TestCase):
    def test_prepare_analysis_dataframe_normalizes_and_deduplicates(self):
        frame = pd.DataFrame(
            [
                {"smiles": "CCO", "biodegradable": 1, "molecule_id": "mol_1", "source": "upload", "notes": "first"},
                {"smiles": "OCC", "biodegradable": 0, "molecule_id": "mol_2", "source": "upload", "notes": "duplicate"},
                {"smiles": "not_smiles", "biodegradable": 1, "molecule_id": "mol_3", "source": "upload", "notes": "invalid"},
            ]
        )

        prepared, summary = prepare_analysis_dataframe(
            frame,
            {
                "smiles": "smiles",
                "biodegradable": "biodegradable",
                "molecule_id": "molecule_id",
                "source": "source",
                "notes": "notes",
            },
        )

        self.assertEqual(prepared["smiles"].tolist(), ["CCO"])
        self.assertEqual(int(summary["duplicate_count"]), 1)
        self.assertEqual(int(summary["analyzed_rows"]), 1)
        self.assertEqual(int(summary["invalid_smiles_count"]), 1)

    def test_decorate_candidates_assigns_ids_buckets_and_review_defaults(self):
        frame = pd.DataFrame(
            [
                {
                    "polymer": "poly_1",
                    "smiles": "CCO",
                    "confidence": 0.91,
                    "uncertainty": 0.10,
                    "novelty": 0.30,
                    "experiment_value": 0.72,
                    "final_score": 0.77,
                }
            ]
        )

        decorated = decorate_candidates(
            frame,
            mode="prediction",
            source_name="upload.csv",
            bundle={"selected_model": {"name": "rf_isotonic", "calibration_method": "isotonic"}},
            intent="rank_uploaded_molecules",
            scoring_mode="balanced",
        )

        candidate = decorated.iloc[0].to_dict()
        self.assertEqual(candidate["candidate_id"], "poly_1")
        self.assertEqual(candidate["bucket"], "exploit")
        self.assertEqual(candidate["status"], "suggested")
        self.assertIn("upload.csv", candidate["provenance"])
        self.assertTrue(candidate["short_explanation"])
        self.assertIn(candidate["risk"], {"low", "medium", "high"})

    @patch("system.run_pipeline.build_discovery_result")
    @patch("system.run_pipeline.persist_review_queue")
    @patch("system.run_pipeline.build_prediction_result")
    def test_run_pipeline_coordinates_services_and_validates_decisions(
        self,
        build_prediction_result_mock,
        persist_review_queue_mock,
        build_discovery_result_mock,
    ):
        session_id = "session_test"
        scored = pd.DataFrame([{"smiles": "CCO", "confidence": 0.91, "uncertainty": 0.10, "novelty": 0.58}])
        build_prediction_result_mock.return_value = (
            {
                "mode": "prediction",
                "message": "Ranked uploaded molecules for review using the current scoring workflow.",
                "summary": {"scored_candidates": 1},
                "top_candidates": [],
                "decision_output": canonical_decision_output(session_id),
            },
            scored,
            None,
        )
        persist_review_queue_mock.return_value = {
            "session_id": session_id,
            "generated_at": "2026-03-25T12:05:00+00:00",
            "summary": {"pending_review": 1, "approved": 0, "rejected": 0, "tested": 0, "ingested": 0, "counts": {}},
            "groups": {},
        }

        result = run_pipeline(
            pd.DataFrame([{"smiles": "CCO", "biodegradable": -1, "molecule_id": "mol_1", "source": "upload", "notes": ""}]),
            persist_artifacts=False,
            update_discovery_snapshot=False,
            seed=42,
            source_name="upload.csv",
            analysis_options={
                "session_id": session_id,
                "input_type": "molecules_to_screen_only",
                "intent": "rank_uploaded_molecules",
                "scoring_mode": "balanced",
                "consent_learning": False,
                "column_mapping": {
                    "smiles": "smiles",
                    "biodegradable": "biodegradable",
                    "molecule_id": "molecule_id",
                    "source": "source",
                    "notes": "notes",
                },
            },
        )

        build_discovery_result_mock.assert_not_called()
        build_prediction_result_mock.assert_called_once()
        self.assertEqual(result["session_id"], session_id)
        self.assertEqual(result["decision_output"]["session_id"], session_id)
        self.assertEqual(result["decision_output"]["input_type"], "molecules_to_screen_only")
        self.assertEqual(result["decision_output"]["intent"], "rank_uploaded_molecules")
        self.assertEqual(result["top_candidates"][0]["candidate_id"], "cand_1")
        self.assertEqual(result["review_queue"]["session_id"], session_id)
        self.assertEqual(result["artifacts"], {})
        self.assertEqual(result["discovery_url"], f"/discovery?session_id={session_id}")
        self.assertEqual(result["dashboard_url"], f"/dashboard?session_id={session_id}")


if __name__ == "__main__":
    unittest.main()
