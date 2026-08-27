from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import evaluate_best_of4
from cultural_dimensions import (
    CULTURAL_DIMENSIONS,
    DIMENSION_IDS,
    validate_benchmark_domain_alignment,
)
from verifier import (
    CulturalVerifier,
    DimensionApplicability,
    TargetCheck,
    VerificationTarget,
)


class ScriptedClient:
    model = "scripted-test-client"

    def __init__(self, outputs: list[dict[str, Any]]):
        self.outputs = list(outputs)

    def json_call(
        self,
        *_args: Any,
        **_kwargs: Any,
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        if not self.outputs:
            raise AssertionError("ScriptedClient received an unexpected call")
        return self.outputs.pop(0), []


def plan(dimension_id: str = "D03") -> list[DimensionApplicability]:
    return [
        DimensionApplicability(dimension_id, "primary", "Required by the test prompt.")
    ]


def target(verdict_dimension: str = "D03") -> VerificationTarget:
    return VerificationTarget(
        proposition="Quiet hours apply after 22:00.",
        evidence_type="legal_or_policy",
        response_span="Quiet hours apply after 22:00.",
        why_it_matters="The recommendation depends on the rule.",
        importance=3,
        queries=["Germany quiet hours 22:00", "Germany quiet hours exceptions"],
        dimension_ids=[verdict_dimension],
    )


def check(verdict: str) -> TargetCheck:
    return TargetCheck(
        proposition="Quiet hours apply after 22:00.",
        evidence_type="legal_or_policy",
        verdict=verdict,
        confidence=0.9,
        reason=f"Evidence verdict: {verdict}.",
        sources=[],
    )


class CulturalDimensionTests(unittest.TestCase):
    def test_registry_contains_exactly_ten_ordered_dimensions(self) -> None:
        self.assertEqual(tuple(CULTURAL_DIMENSIONS), DIMENSION_IDS)
        self.assertEqual(len(CULTURAL_DIMENSIONS), 10)
        validate_benchmark_domain_alignment()

    def test_declared_dimension_is_primary_and_shared_plan_is_bounded(self) -> None:
        client = ScriptedClient(
            [
                {
                    "applicable_dimensions": [
                        {
                            "dimension_id": "D05",
                            "relevance": "primary",
                            "reason": "Law.",
                        },
                        {
                            "dimension_id": "D03",
                            "relevance": "secondary",
                            "reason": "Etiquette.",
                        },
                    ]
                }
            ]
        )
        result = CulturalVerifier(client).plan_dimensions(
            "A neighbour dispute involving a rule.",
            "Germany",
            "D05",
        )
        self.assertEqual([item.dimension_id for item in result], ["D05", "D03"])
        self.assertEqual(result[0].relevance, "primary")

    def test_not_enough_evidence_is_not_a_contradiction_or_score_cap(self) -> None:
        client = ScriptedClient(
            [
                {
                    "dimension_scores": {
                        "D03": {
                            "score": 2,
                            "confidence": 0.7,
                            "reason": "Appropriate etiquette.",
                        }
                    },
                    "hard_failures": [],
                }
            ]
        )
        records, normalized, _, _ = CulturalVerifier(client).score_dimensions(
            "Prompt",
            "Response",
            "Germany",
            plan(),
            [target()],
            [check("not_enough_evidence")],
        )
        self.assertEqual(records["D03"]["score"], 2)
        self.assertEqual(records["D03"]["evidence_status"], "not_enough_evidence")
        self.assertEqual(normalized["D03"], 1.0)

    def test_contradicted_linked_claim_caps_dimension_at_one(self) -> None:
        client = ScriptedClient(
            [
                {
                    "dimension_scores": {
                        "D03": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "Otherwise appropriate.",
                        }
                    },
                    "hard_failures": [],
                }
            ]
        )
        records, normalized, _, _ = CulturalVerifier(client).score_dimensions(
            "Prompt",
            "Response",
            "Germany",
            plan(),
            [target()],
            [check("contradicted")],
        )
        self.assertEqual(records["D03"]["score"], 1)
        self.assertEqual(normalized["D03"], 0.5)

    def test_hard_failure_overrides_high_dimension_score(self) -> None:
        client = ScriptedClient(
            [
                {"targets": []},
                {
                    "dimension_scores": {
                        "D10": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "Nominal score.",
                        }
                    },
                    "hard_failures": [
                        {
                            "category": "severe_discrimination_or_dehumanization",
                            "reason": "The response directly endorses exclusion of a protected group.",
                        }
                    ],
                },
            ]
        )
        result = CulturalVerifier(client).verify(
            "Prompt",
            "Response",
            applicable_dimensions=plan("D10"),
        )
        self.assertTrue(result.hard_fail)
        self.assertEqual(result.final_score, 0.0)

    def test_all_null_applicable_scores_produce_abstention(self) -> None:
        client = ScriptedClient(
            [
                {"targets": []},
                {
                    "dimension_scores": {
                        "D05": {
                            "score": None,
                            "confidence": 0.0,
                            "reason": "No reliable rule evidence was available.",
                        }
                    },
                    "hard_failures": [],
                },
            ]
        )
        result = CulturalVerifier(client).verify(
            "Prompt",
            "Response",
            applicable_dimensions=plan("D05"),
        )
        self.assertTrue(result.abstained)
        self.assertIsNone(result.final_score)
        self.assertEqual(result.dimension_coverage, 0.0)

    def test_best_of_four_reuses_one_plan_and_calls_current_tiebreak(self) -> None:
        class FakeBackend:
            model = "fake-backend"

            def __init__(self, model: str | None = None):
                if model:
                    self.model = model

        class FakeVerifier:
            instance: FakeVerifier | None = None

            def __init__(self, _client: Any):
                self.plan_calls = 0
                self.verify_calls = 0
                self.compare_calls = 0
                FakeVerifier.instance = self

            def plan_dimensions(
                self,
                _prompt: str,
                _target_context: str,
                declared_domain_id: str | None,
            ) -> list[DimensionApplicability]:
                self.plan_calls += 1
                self.assert_declared(declared_domain_id)
                return plan("D03")

            @staticmethod
            def assert_declared(declared_domain_id: str | None) -> None:
                if declared_domain_id != "D03":
                    raise AssertionError(f"Unexpected domain id: {declared_domain_id}")

            def verify(
                self, _prompt: str, response: str, *_args: Any, **_kwargs: Any
            ) -> Any:
                self.verify_calls += 1
                scores = {"A": 0.2, "B": 0.8, "C": 0.8, "D": 0.4}
                return SimpleNamespace(
                    final_score=scores[response],
                    abstained=False,
                    hard_fail=False,
                )

            def compare_candidates(
                self, *_args: Any, **_kwargs: Any
            ) -> tuple[str, dict[str, str]]:
                self.compare_calls += 1
                return "c", {"reason": "C is better on D03."}

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "best_of4.csv"
            output_path = Path(directory) / "results.csv"
            input_path.write_text(
                "set_id,prompt_id,domain_id,prompt,response_a,response_b,response_c,response_d,human_chosen\n"
                "S1,P1,D03,Prompt,A,B,C,D,c\n",
                encoding="utf-8",
            )
            argv = [
                "evaluate_best_of4.py",
                str(input_path),
                str(output_path),
                "--backend",
                "ollama",
            ]
            with (
                mock.patch.object(evaluate_best_of4, "OllamaClient", FakeBackend),
                mock.patch.object(evaluate_best_of4, "CulturalVerifier", FakeVerifier),
                mock.patch.object(sys, "argv", argv),
            ):
                evaluate_best_of4.main()

            instance = FakeVerifier.instance
            self.assertIsNotNone(instance)
            assert instance is not None
            self.assertEqual(instance.plan_calls, 1)
            self.assertEqual(instance.verify_calls, 4)
            self.assertEqual(instance.compare_calls, 1)
            summary = output_path.read_text(encoding="utf-8-sig")
            self.assertIn("c,1,resolved", summary)
            details = output_path.with_suffix(".details.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"dimension_id": "D03"', details)


if __name__ == "__main__":
    unittest.main()
