import os
import tempfile
import unittest
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.services.belief_state_service import get_belief_state_for_target
from system.services.belief_update_service import (
    accept_belief_update,
    create_belief_update,
    list_session_belief_updates,
    reject_belief_update,
    supersede_belief_update,
)
from system.services.claim_service import create_session_claims
from system.services.experiment_request_service import create_session_experiment_requests, list_session_experiment_requests
from system.services.experiment_result_service import ingest_experiment_result
from system.services.scientific_session_truth_service import build_scientific_session_truth


class BeliefUpdateServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'belief_updates.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def _seed_claim_request_result(
        self,
        session_id: str,
        *,
        observed_value=None,
        observed_label: str = "",
        result_quality: str = "confirmatory",
        assay_context: str = "",
        measurement_unit: str = "log units",
        target_definition_overrides: dict | None = None,
    ):
        target_definition = {
            "target_name": "pIC50",
            "target_kind": "regression",
            "optimization_direction": "maximize",
            "measurement_column": "pic50",
            "measurement_unit": "log units",
            "dataset_type": "measurement_dataset",
            "mapping_confidence": "medium",
        }
        if isinstance(target_definition_overrides, dict):
            target_definition.update(target_definition_overrides)
        decision_payload = {
            "top_experiments": [
                {
                    "rank": 1,
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "trust_label": "Mixed trust",
                    "rationale_primary_driver": "High ranking compatibility supports near-term testing.",
                    "domain_status": "in_domain",
                }
            ]
        }
        scientific_truth = {
            "session_id": session_id,
            "target_definition": target_definition,
            "evidence_loop": {
                "active_modeling_evidence": ["Observed experimental values"],
                "active_ranking_evidence": ["Model predictions"],
            },
        }
        claims = create_session_claims(
            session_id=session_id,
            workspace_id="workspace_1",
            decision_payload=decision_payload,
            scientific_truth=scientific_truth,
            created_by_user_id="user_1",
        )
        create_session_experiment_requests(
            session_id=session_id,
            workspace_id="workspace_1",
            claims=claims,
            decision_payload=decision_payload,
            requested_by_user_id="user_1",
        )
        request = list_session_experiment_requests(session_id, workspace_id="workspace_1")[0]
        result = ingest_experiment_result(
            session_id=session_id,
            workspace_id="workspace_1",
            source_experiment_request_id=request["experiment_request_id"],
            observed_value=observed_value,
            observed_label=observed_label,
            measurement_unit=measurement_unit,
            assay_context=assay_context,
            result_quality=result_quality,
            ingested_by="Owner",
            ingested_by_user_id="user_1",
        )
        return claims[0], request, result

    def test_create_belief_update_strengthens_support_for_positive_observed_label(self):
        claim, _, result = self._seed_claim_request_result("session_belief_1", observed_label="positive")

        created = create_belief_update(
            session_id="session_belief_1",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        stored = list_session_belief_updates("session_belief_1", workspace_id="workspace_1")
        self.assertEqual(len(stored), 1)
        self.assertEqual(created["belief_update_id"], stored[0]["belief_update_id"])
        self.assertEqual(stored[0]["previous_support_level"], "moderate")
        self.assertEqual(stored[0]["updated_support_level"], "strong")
        self.assertEqual(stored[0]["update_direction"], "strengthened")
        self.assertEqual(stored[0]["governance_status"], "proposed")
        self.assertEqual(stored[0]["support_input_quality_label"], "Stronger interpretation basis")
        self.assertEqual(stored[0]["result_interpretation_basis"], "Observed label")
        self.assertEqual(stored[0]["support_quality_label"], "Decision-useful active support")
        self.assertEqual(stored[0]["support_decision_usefulness_label"], "Can justify bounded follow-up")
        self.assertEqual(stored[0]["governed_support_posture_label"], "Current support remains tentative")
        self.assertEqual(stored[0]["contradiction_role_label"], "Adds tentative current support")

    def test_numeric_result_with_derived_label_rule_can_strengthen_support(self):
        claim, _, result = self._seed_claim_request_result(
            "session_belief_2",
            observed_value=6.8,
            target_definition_overrides={
                "derived_label_rule": {
                    "source_column": "pic50",
                    "operator": ">=",
                    "threshold": 6.0,
                    "positive_label": 1,
                    "negative_label": 0,
                    "rule_reason": "Binary labels were derived from the numeric measurement column using the configured threshold rule.",
                }
            },
        )
        create_belief_update(
            session_id="session_belief_2",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        truth = build_scientific_session_truth(
            session_id="session_belief_2",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_belief_2",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "summary_metadata": {"last_job_status": "succeeded"},
            },
            analysis_report={
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "measurement_unit": "log units",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "ranking_policy": {"primary_score": "confidence", "primary_score_label": "Ranking compatibility"},
                "run_contract": {"training_scope": "session_trained"},
                "comparison_anchors": {"comparison_ready": True},
            },
            decision_payload={"summary": {"candidate_count": 1}, "top_experiments": []},
            review_queue={"summary": {"counts": {}}},
        )

        self.assertEqual(truth["belief_update_summary"]["update_count"], 1)
        self.assertIn("belief update", truth["belief_update_summary"]["summary_text"].lower())
        self.assertEqual(truth["belief_update_summary"]["chronology_mix_label"], "Current support only")
        self.assertIn("active governed support change", truth["belief_update_summary"]["chronology_summary_text"].lower())
        self.assertEqual(truth["belief_update_summary"]["numeric_interpreted_count"], 1)
        self.assertEqual(truth["belief_update_summary"]["numeric_unresolved_count"], 0)
        self.assertEqual(truth["belief_update_refs"][0]["update_direction"], "strengthened")
        self.assertEqual(truth["belief_update_refs"][0]["updated_support_level"], "strong")
        self.assertEqual(truth["belief_update_refs"][0]["result_interpretation_basis"], "Numeric outcome under current target rule")
        self.assertEqual(truth["belief_update_refs"][0]["numeric_result_basis_label"], "Clean target rule available")
        self.assertEqual(truth["belief_update_refs"][0]["target_rule_alignment_label"], "Target rule aligned")
        self.assertEqual(truth["belief_update_refs"][0]["numeric_result_resolution_label"], "Interpreted through current target rule")
        self.assertIn("current target rule", truth["belief_update_refs"][0]["numeric_result_interpretation_label"].lower())
        self.assertEqual(truth["belief_update_refs"][0]["support_quality_label"], "Active but limited support")
        self.assertEqual(truth["belief_update_summary"]["active_but_limited_support_count"], 1)

    def test_numeric_result_without_clean_target_rule_remains_unresolved(self):
        claim, _, result = self._seed_claim_request_result(
            "session_belief_2c",
            observed_value=6.8,
        )
        created = create_belief_update(
            session_id="session_belief_2c",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        self.assertEqual(created["update_direction"], "unresolved")
        self.assertEqual(created["numeric_result_basis_label"], "No clean target rule")
        self.assertEqual(created["numeric_result_resolution_label"], "Unresolved under current numeric basis")
        self.assertEqual(created["target_rule_alignment_label"], "No target rule alignment")
        self.assertIn("does not include a clean derived target rule", created["numeric_result_basis_summary"].lower())

    def test_numeric_result_with_unit_mismatch_stays_unresolved_under_current_basis(self):
        claim, _, result = self._seed_claim_request_result(
            "session_belief_2d",
            observed_value=6.8,
            measurement_unit="nM",
            target_definition_overrides={
                "derived_label_rule": {
                    "source_column": "pic50",
                    "operator": ">=",
                    "threshold": 6.0,
                    "positive_label": 1,
                    "negative_label": 0,
                    "rule_reason": "Binary labels were derived from the numeric measurement column using the configured threshold rule.",
                }
            },
        )
        created = create_belief_update(
            session_id="session_belief_2d",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        self.assertEqual(created["update_direction"], "unresolved")
        self.assertEqual(created["numeric_result_basis_label"], "Weak numeric basis")
        self.assertEqual(created["numeric_result_resolution_label"], "Unresolved under current numeric basis")
        self.assertIn("expects log units", created["numeric_result_basis_summary"].lower())

    def test_low_quality_result_keeps_support_unresolved_even_with_positive_label(self):
        claim, _, result = self._seed_claim_request_result(
            "session_belief_2b",
            observed_label="positive",
            result_quality="provisional",
            target_definition_overrides={"assay_context": "pic50_confirmatory_assay"},
        )
        created = create_belief_update(
            session_id="session_belief_2b",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        self.assertEqual(created["update_direction"], "unresolved")
        self.assertEqual(created["updated_support_level"], "moderate")
        self.assertEqual(created["support_input_quality_label"], "Weak interpretation basis")
        self.assertEqual(created["assay_context_alignment_label"], "Sparse assay context")

    def test_accepting_belief_update_refreshes_belief_state_toward_accepted_support(self):
        claim, _, result = self._seed_claim_request_result("session_belief_3", observed_label="positive")
        created = create_belief_update(
            session_id="session_belief_3",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        updated = accept_belief_update(
            belief_update_id=created["belief_update_id"],
            workspace_id="workspace_1",
            session_id="session_belief_3",
            reviewed_by="Owner",
            reviewed_by_user_id="user_1",
            governance_note="Scientist accepted this bounded support change.",
        )

        self.assertEqual(updated["governance_status"], "accepted")
        self.assertEqual(updated["reviewed_by"], "Owner")
        self.assertIn("accepted_at", updated["metadata"])
        self.assertEqual(updated["metadata"]["accepted_by"], "Owner")
        self.assertEqual(updated["governed_support_posture_label"], "Accepted and posture-governing")
        self.assertEqual(updated["contradiction_role_label"], "Reinforces current posture")
        belief_state = get_belief_state_for_target(
            workspace_id="workspace_1",
            target_definition_snapshot=claim["target_definition_snapshot"],
        )
        self.assertEqual(belief_state["metadata"]["accepted_update_count"], 1)
        self.assertEqual(belief_state["metadata"]["proposed_update_count"], 0)
        self.assertEqual(belief_state["governance_mix_label"], "Mostly accepted")

    def test_rejecting_belief_update_excludes_it_from_active_belief_picture(self):
        claim, _, result = self._seed_claim_request_result("session_belief_4", observed_label="negative")
        created = create_belief_update(
            session_id="session_belief_4",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        updated = reject_belief_update(
            belief_update_id=created["belief_update_id"],
            workspace_id="workspace_1",
            session_id="session_belief_4",
            reviewed_by="Owner",
            reviewed_by_user_id="user_1",
            governance_note="Scientist rejected this support interpretation.",
        )

        self.assertEqual(updated["governance_status"], "rejected")
        self.assertEqual(updated["metadata"]["rejected_by"], "Owner")
        belief_state = get_belief_state_for_target(
            workspace_id="workspace_1",
            target_definition_snapshot=claim["target_definition_snapshot"],
        )
        self.assertIsNone(belief_state)

    def test_superseding_belief_update_preserves_history_but_removes_active_support(self):
        claim, _, result = self._seed_claim_request_result("session_belief_5", observed_label="positive")
        created = create_belief_update(
            session_id="session_belief_5",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )
        accept_belief_update(
            belief_update_id=created["belief_update_id"],
            workspace_id="workspace_1",
            session_id="session_belief_5",
            reviewed_by="Owner",
            reviewed_by_user_id="user_1",
            governance_note="Scientist accepted this bounded support change.",
        )

        updated = supersede_belief_update(
            belief_update_id=created["belief_update_id"],
            workspace_id="workspace_1",
            session_id="session_belief_5",
            reviewed_by="Owner",
            reviewed_by_user_id="user_1",
            supersede_reason="Newer governed support change replaced this one.",
        )

        self.assertEqual(updated["governance_status"], "superseded")
        self.assertEqual(updated["metadata"]["superseded_by"], "Owner")
        self.assertIn("superseded_at", updated["metadata"])
        self.assertEqual(updated["metadata"]["supersede_reason"], "Newer governed support change replaced this one.")
        self.assertEqual(updated["governed_support_posture_label"], "Historical only, not posture-governing")
        self.assertEqual(updated["contradiction_role_label"], "Historical context only")

        stored = list_session_belief_updates("session_belief_5", workspace_id="workspace_1")[0]
        self.assertEqual(stored["chronology_label"], "Historical superseded support change")
        self.assertFalse(stored["active_for_belief_state"])

        belief_state = get_belief_state_for_target(
            workspace_id="workspace_1",
            target_definition_snapshot=claim["target_definition_snapshot"],
        )
        self.assertIsNone(belief_state)


if __name__ == "__main__":
    unittest.main()
