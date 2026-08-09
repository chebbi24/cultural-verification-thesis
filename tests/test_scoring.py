import importlib.util
import unittest
from pathlib import Path

from cultural_verifier.scoring import (
    ScoringConfig,
    aggregate_evidence,
    hybrid_probabilities,
    verifier_score,
)

ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_SPEC = importlib.util.spec_from_file_location(
    "calibrate_scoring", ROOT / "scripts/calibrate_scoring.py"
)
calibrate_scoring = importlib.util.module_from_spec(CALIBRATION_SPEC)
assert CALIBRATION_SPEC.loader is not None
CALIBRATION_SPEC.loader.exec_module(calibrate_scoring)


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = ScoringConfig.from_json(ROOT / "config/scoring.json")

    def test_insufficient_evidence_is_abstention(self) -> None:
        evidence = aggregate_evidence(["not_enough_evidence"] * 5)
        self.assertIsNone(evidence.evidence_score)
        self.assertEqual(evidence.coverage, 0.0)
        score, aligned, weight = verifier_score(
            rubric_score=1.0,
            evidence=evidence,
            hard_fail=False,
            config=self.config,
        )
        self.assertEqual(score, 1.0)
        self.assertTrue(aligned)
        self.assertEqual(weight, 0.0)

    def test_coverage_scales_evidence_weight(self) -> None:
        evidence = aggregate_evidence(["supported", "not_enough_evidence"])
        score, _, weight = verifier_score(
            rubric_score=0.5,
            evidence=evidence,
            hard_fail=False,
            config=self.config,
        )
        self.assertAlmostEqual(weight, self.config.max_evidence_weight * 0.5)
        self.assertAlmostEqual(score, 0.625)

    def test_contradiction_penalty(self) -> None:
        evidence = aggregate_evidence(["contradicted", "supported"])
        score, _, _ = verifier_score(
            rubric_score=1.0,
            evidence=evidence,
            hard_fail=False,
            config=self.config,
        )
        self.assertLess(score, 0.75)

    def test_hard_fail_veto(self) -> None:
        evidence = aggregate_evidence(["supported"])
        score, aligned, _ = verifier_score(
            rubric_score=1.0,
            evidence=evidence,
            hard_fail=True,
            config=self.config,
        )
        self.assertEqual(score, 0.0)
        self.assertFalse(aligned)

    def test_hybrid_is_normalized_and_vetoes(self) -> None:
        probabilities = hybrid_probabilities(
            rm_probabilities=[0.7, 0.2, 0.1],
            verifier_scores=[0.9, 0.8, 0.7],
            hard_fails=[True, False, False],
            config=self.config,
        )
        self.assertEqual(probabilities[0], 0.0)
        self.assertAlmostEqual(sum(probabilities), 1.0)

    def test_calibration_rejects_synthetic_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "human_adjudicated"):
            calibrate_scoring.require_final_human_development_labels(
                [
                    {
                        "set_id": "PLT001",
                        "human_choice_candidate_id": "PLT001-C1",
                        "split": "development",
                        "label_source": "synthetic_model_provisional",
                        "review_status": "final",
                    }
                ]
            )
