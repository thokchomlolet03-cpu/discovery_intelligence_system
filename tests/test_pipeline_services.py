import unittest
from unittest.mock import patch

import pandas as pd

from system.contracts import validate_decision_artifact
from system.run_pipeline import run_pipeline
from system.services.candidate_service import (
    OUT_OF_DOMAIN_SAMPLE_LIMIT,
    candidate_similarity_table,
    out_of_domain_ratio,
)
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

    def test_prepare_analysis_dataframe_builds_labels_from_measurements(self):
        frame = pd.DataFrame(
            [
                {"smiles": "CCO", "pic50": 6.2, "compound_id": "mol_1", "assay_name": "screen_a"},
                {"smiles": "CCN", "pic50": 5.4, "compound_id": "mol_2", "assay_name": "screen_a"},
                {"smiles": "CCC", "pic50": None, "compound_id": "mol_3", "assay_name": "screen_a"},
            ]
        )

        prepared, summary = prepare_analysis_dataframe(
            frame,
            {
                "smiles": "smiles",
                "value": "pic50",
                "entity_id": "compound_id",
                "assay": "assay_name",
            },
            label_builder={
                "enabled": True,
                "value_column": "pic50",
                "operator": ">=",
                "threshold": 6.0,
            },
        )

        self.assertEqual(prepared["biodegradable"].tolist(), [1, 0, -1])
        self.assertEqual(prepared["molecule_id"].tolist(), ["mol_1", "mol_2", "mol_3"])
        self.assertEqual(prepared["assay"].tolist(), ["screen_a", "screen_a", "screen_a"])
        self.assertEqual(int(summary["rows_with_values"]), 2)
        self.assertEqual(int(summary["rows_with_labels"]), 2)
        self.assertEqual(summary["label_source"], "derived")
        self.assertEqual(summary["semantic_mode"], "measurement_dataset")

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

    @patch("system.services.candidate_service.max_similarity_to_reference", return_value=0.1)
    @patch("system.services.candidate_service.build_reference_fingerprints", return_value=[("ref", object())])
    @patch(
        "system.services.candidate_service.molecule_fingerprint",
        side_effect=lambda smiles, n_bits=2048: (str(smiles), object()),
    )
    @patch("system.services.candidate_service.reference_smiles_from_dataset", return_value=["CCO"])
    def test_out_of_domain_ratio_samples_large_inputs(
        self,
        reference_smiles_mock,
        molecule_fingerprint_mock,
        build_reference_fingerprints_mock,
        max_similarity_mock,
    ):
        frame = pd.DataFrame({"smiles": [f"candidate_{idx}" for idx in range(OUT_OF_DOMAIN_SAMPLE_LIMIT + 300)]})

        ratio = out_of_domain_ratio(frame, config=None)

        self.assertEqual(ratio, 1.0)
        self.assertEqual(build_reference_fingerprints_mock.call_count, 1)
        self.assertEqual(molecule_fingerprint_mock.call_count, OUT_OF_DOMAIN_SAMPLE_LIMIT)
        self.assertEqual(max_similarity_mock.call_count, OUT_OF_DOMAIN_SAMPLE_LIMIT)
        reference_smiles_mock.assert_called_once()

    @patch("system.services.candidate_service.max_similarity_to_reference", return_value=0.1)
    @patch("system.services.candidate_service.build_reference_fingerprints", return_value=[("ref", object())])
    @patch(
        "system.services.candidate_service.molecule_fingerprint",
        side_effect=lambda smiles, n_bits=2048: (str(smiles), object()),
    )
    @patch(
        "system.services.candidate_service.tanimoto_similarity",
        side_effect=AssertionError("Batch diversity should be skipped for uploaded molecule ranking."),
    )
    def test_candidate_similarity_table_can_skip_batch_diversity(
        self,
        tanimoto_similarity_mock,
        molecule_fingerprint_mock,
        build_reference_fingerprints_mock,
        max_similarity_mock,
    ):
        frame = pd.DataFrame({"smiles": ["candidate_a", "candidate_b", "candidate_c"]})

        scored = candidate_similarity_table(
            frame,
            reference_smiles=["CCO"],
            config=None,
            enforce_batch_diversity=False,
        )

        self.assertEqual(scored["smiles"].tolist(), ["candidate_a", "candidate_b", "candidate_c"])
        self.assertTrue(scored["passes_diversity_filter"].all())
        self.assertTrue(scored["passes_batch_filter"].all())
        self.assertEqual(molecule_fingerprint_mock.call_count, 3)
        self.assertEqual(build_reference_fingerprints_mock.call_count, 1)
        self.assertEqual(max_similarity_mock.call_count, 3)
        tanimoto_similarity_mock.assert_not_called()

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
                "input_type": "structure_only_screening",
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
        self.assertEqual(result["decision_output"]["input_type"], "structure_only_screening")
        self.assertEqual(result["decision_output"]["intent"], "rank_uploaded_molecules")
        self.assertEqual(result["top_candidates"][0]["candidate_id"], "cand_1")
        self.assertEqual(result["review_queue"]["session_id"], session_id)
        self.assertEqual(result["artifacts"], {})
        self.assertEqual(result["discovery_url"], f"/discovery?session_id={session_id}")
        self.assertEqual(result["dashboard_url"], f"/dashboard?session_id={session_id}")

    @patch("system.run_pipeline.build_discovery_result")
    @patch("system.run_pipeline.persist_review_queue")
    @patch("system.run_pipeline.build_prediction_result")
    def test_run_pipeline_preserves_measurement_context_in_reports(
        self,
        build_prediction_result_mock,
        persist_review_queue_mock,
        build_discovery_result_mock,
    ):
        session_id = "session_measurements"
        scored = pd.DataFrame(
            [
                {
                    "smiles": "CCO",
                    "value": 6.2,
                    "confidence": 0.91,
                    "uncertainty": 0.10,
                    "novelty": 0.58,
                    "experiment_value": 0.72,
                    "max_similarity": 0.30,
                    "selection_bucket": "exploit",
                },
                {
                    "smiles": "CCN",
                    "value": 5.4,
                    "confidence": 0.61,
                    "uncertainty": 0.22,
                    "novelty": 0.44,
                    "experiment_value": 0.55,
                    "max_similarity": 0.18,
                    "selection_bucket": "learn",
                },
            ]
        )
        build_prediction_result_mock.return_value = (
            {
                "mode": "prediction",
                "message": "Ranked uploaded molecules for review using the current scoring workflow.",
                "summary": {"scored_candidates": 2},
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
            pd.DataFrame(
                [
                    {"smiles": "CCO", "pic50": 6.2, "compound_id": "mol_1", "assay_name": "screen_a"},
                    {"smiles": "CCN", "pic50": 5.4, "compound_id": "mol_2", "assay_name": "screen_a"},
                    {"smiles": "CCC", "pic50": None, "compound_id": "mol_3", "assay_name": "screen_a"},
                ]
            ),
            persist_artifacts=False,
            update_discovery_snapshot=False,
            seed=42,
            source_name="measurements.csv",
            analysis_options={
                "session_id": session_id,
                "input_type": "measurement_dataset",
                "intent": "rank_uploaded_molecules",
                "scoring_mode": "balanced",
                "consent_learning": False,
                "column_mapping": {
                    "smiles": "smiles",
                    "value": "pic50",
                    "entity_id": "compound_id",
                    "assay": "assay_name",
                },
                "validation_context": {"file_type": "csv", "semantic_mode": "measurement_dataset"},
            },
        )

        build_discovery_result_mock.assert_not_called()
        build_prediction_result_mock.assert_called_once()
        measurement_summary = result["upload_session_summary"]["measurement_summary"]
        self.assertEqual(measurement_summary["semantic_mode"], "measurement_dataset")
        self.assertEqual(measurement_summary["value_column"], "pic50")
        self.assertEqual(int(measurement_summary["rows_with_values"]), 2)
        self.assertEqual(result["analysis_report"]["measurement_summary"]["file_type"], "csv")
        self.assertEqual(result["analysis_report"]["ranking_diagnostics"]["score_basis"], "priority_score")
        self.assertEqual(int(result["analysis_report"]["ranking_diagnostics"]["measurement_rows_evaluated"]), 2)
        self.assertEqual(result["analysis_report"]["ranking_policy"]["primary_score"], "priority_score")
        self.assertIn("weights", result["analysis_report"]["ranking_policy"])

    @patch("system.run_pipeline.build_discovery_result")
    @patch("system.run_pipeline.persist_review_queue")
    @patch("system.run_pipeline.build_prediction_result")
    def test_run_pipeline_emits_stage_progress_updates(
        self,
        build_prediction_result_mock,
        persist_review_queue_mock,
        build_discovery_result_mock,
    ):
        session_id = "session_progress"
        progress_events: list[tuple[str, str, int]] = []
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

        run_pipeline(
            pd.DataFrame([{"smiles": "CCO", "biodegradable": -1, "molecule_id": "mol_1", "source": "upload", "notes": ""}]),
            persist_artifacts=False,
            update_discovery_snapshot=False,
            seed=42,
            source_name="upload.csv",
            analysis_options={
                "session_id": session_id,
                "input_type": "structure_only_screening",
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
            progress_callback=lambda stage, message, percent: progress_events.append((stage, message, percent)),
        )

        self.assertGreaterEqual(len(progress_events), 5)
        self.assertEqual(progress_events[0][0], "preparing_dataset")
        self.assertEqual(progress_events[0][2], 12)
        self.assertTrue(any(stage == "building_reports" for stage, _, _ in progress_events))
        self.assertTrue(any(stage == "queueing_feedback" for stage, _, _ in progress_events))
        self.assertEqual(progress_events[-1][0], "finalizing_artifacts")
        self.assertEqual(progress_events[-1][2], 98)


if __name__ == "__main__":
    unittest.main()
