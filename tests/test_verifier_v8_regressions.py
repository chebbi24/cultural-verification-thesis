from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from verifier import (  # noqa: E402
    CulturalVerifier,
    DimensionApplicability,
    TargetCheck,
    VerificationTarget,
)


class ScriptedClient:
    model = "scripted-v8-test"

    def __init__(self, outputs: list[Any]):
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []

    def json_call(self, *args: Any, **kwargs: Any):
        self.calls.append({"args": args, **kwargs})
        if not self.outputs:
            raise AssertionError("unexpected model call")
        value = self.outputs.pop(0)
        return value if isinstance(value, tuple) else (value, [])


class V8RegressionTests(unittest.TestCase):
    def test_planner_does_not_request_or_execute_model_written_queries(self) -> None:
        response = (
            "Schnitzel or Sauerbraten (please let us know if you have any dietary restrictions)"
        )
        client = ScriptedClient(
            [
                {
                    "targets": [
                        {
                            "target_kind": "explicit_external_claim",
                            "evidence_type": "dietary_or_religious",
                            "response_span": response,
                            "why_it_matters": "The menu must suit the named guests.",
                            "importance": 3,
                            "dimension_ids": ["D01", "D06"],
                        }
                    ]
                }
            ]
        )
        verifier = CulturalVerifier(client)
        plan = [
            DimensionApplicability("D01", "primary", "Food is central.", []),
            DimensionApplicability("D06", "secondary", "Religion is relevant.", []),
        ]
        targets = verifier.plan_targets(
            "A Frankfurt dinner includes vegetarians and Muslims.",
            response,
            "Germany",
            plan,
        )

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].target_kind, "recommendation_suitability")
        self.assertIn("muslim", " ".join(targets[0].queries).lower())
        self.assertIn("vegetarian", " ".join(targets[0].queries).lower())
        self.assertFalse(any(query.lower().startswith("what ") for query in targets[0].queries))
        schema = client.calls[0]["response_schema"]
        target_properties = schema["properties"]["targets"]["items"]["properties"]
        self.assertNotIn("queries", target_properties)

    def test_supported_recommendation_is_downgraded_when_cited_source_has_counterevidence(self) -> None:
        target = VerificationTarget(
            target_kind="recommendation_suitability",
            proposition="Suitability of the exact recommendation in context: German beer and schnapps",
            evidence_type="dietary_or_religious",
            response_span="German beer and schnapps",
            why_it_matters="The drinks must fit the named guests.",
            importance=3,
            queries=["Germany beer Muslims", "Germany beer Muslims accommodation"],
            dimension_ids=["D06"],
        )
        check = TargetCheck(
            proposition=target.proposition,
            evidence_type=target.evidence_type,
            verdict="supported",
            confidence=0.95,
            reason="Nominal support.",
            cited_source_urls=["https://example.org/source"],
            sources=[
                {
                    "url": "https://example.org/source",
                    "title": "Guidance on Islam and alcohol",
                    "content": "Alcohol is prohibited in Islam and the association was criticized as unwise.",
                }
            ],
        )

        calibrated = CulturalVerifier._recommendation_guard(
            "Dinner with Muslim colleagues.", target, check
        )
        self.assertEqual(calibrated.verdict, "mixed")
        self.assertLessEqual(calibrated.confidence, 0.7)

    def test_prompt_specific_accommodation_gap_caps_perfect_score(self) -> None:
        client = ScriptedClient(
            [
                {
                    "dimension_scores": {
                        "D01": {
                            "score": 2,
                            "confidence": 0.95,
                            "reason": "The response is fully appropriate.",
                            "response_spans": ["We will serve Schnitzel and German beer."],
                            "evidence_target_ids": [],
                        }
                    }
                }
            ]
        )
        verifier = CulturalVerifier(client)
        plan = [
            DimensionApplicability(
                "D01",
                "primary",
                "Food is central.",
                ["Concrete accommodation is required for explicit dietary needs."],
            )
        ]
        records, normalized, _ = verifier.score_dimensions(
            "Dinner with vegetarians and Muslims.",
            "We will serve Schnitzel and German beer.",
            "Germany",
            plan,
            [],
            [],
        )

        self.assertEqual(records["D01"]["score"], 1)
        self.assertEqual(normalized["D01"], 0.5)
        self.assertEqual(records["D01"]["confidence"], 0.85)

    def test_reason_cleanup_removes_repetition_and_internal_leakage(self) -> None:
        client = ScriptedClient(
            [
                {
                    "dimension_scores": {
                        "D01": {
                            "score": 1,
                            "confidence": 0.99,
                            "reason": (
                                "The response is incomplete. The response is incomplete. "
                                "assistant_response_to_score: hidden internal field. "
                                "A concrete alternative is missing."
                            ),
                            "response_spans": ["A short response."],
                            "evidence_target_ids": [],
                        }
                    }
                }
            ]
        )
        verifier = CulturalVerifier(client)
        plan = [DimensionApplicability("D01", "primary", "Food.", [])]
        records, _, _ = verifier.score_dimensions(
            "A meal prompt.", "A short response.", "Germany", plan, [], []
        )
        reason = records["D01"]["reason"]
        self.assertEqual(reason.count("The response is incomplete."), 1)
        self.assertNotIn("assistant_response_to_score", reason)
        self.assertLessEqual(len(reason), 700)


if __name__ == "__main__":
    unittest.main()
