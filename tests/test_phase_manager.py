import unittest

from system.phase_manager import build_phase_manager_context


class PhaseManagerTest(unittest.TestCase):
    def test_phase_manager_exposes_recommended_and_next_up_phases(self):
        context = build_phase_manager_context()

        self.assertEqual(context["counts"]["total"], 6)
        self.assertEqual(context["recommended_phase"]["phase_id"], "trust_contract_explanations")
        self.assertEqual(context["recommended_phase"]["status"], "active")
        self.assertEqual(context["next_up_phase"]["phase_id"], "neutral_scientific_core")
        self.assertEqual(context["next_up_phase"]["status"], "blocked")

    def test_phase_manager_tracks_completed_baseline_and_dependencies(self):
        context = build_phase_manager_context()
        phases = {item["phase_id"]: item for item in context["phases"]}

        self.assertEqual(phases["workflow_surface_coherence"]["status"], "completed")
        self.assertEqual(phases["trust_contract_explanations"]["status"], "active")
        self.assertEqual(phases["neutral_scientific_core"]["dependency_details"][0]["phase_id"], "trust_contract_explanations")
        self.assertFalse(phases["neutral_scientific_core"]["dependency_details"][0]["satisfied"])
