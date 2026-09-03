from __future__ import annotations

import json
import requests
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
    DIMENSION_PLAN_SCHEMA,
    DimensionApplicability,
    HARD_FAILURE_SCHEMA,
    OllamaClient,
    OpenRouterClient,
    RetrievalRoutedClient,
    StructuredOutputError,
    TavilyGroundedClient,
    TargetCheck,
    VerificationTarget,
    VerifierResult,
)


class ScriptedClient:
    model = "scripted-test-client"

    def __init__(self, outputs: list[Any]):
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []

    def json_call(
        self,
        *args: Any,
        **_kwargs: Any,
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        call = dict(_kwargs)
        if args:
            call["system"] = args[0]
        if len(args) > 1:
            call["user_payload"] = args[1]
        self.calls.append(call)
        if not self.outputs:
            raise AssertionError("ScriptedClient received an unexpected call")
        value = self.outputs.pop(0)
        if isinstance(value, tuple):
            return value
        return value, []


class FakeHTTPResponse:
    def __init__(self, content: str, annotations: list[dict[str, Any]] | None = None):
        self.content = content
        self.annotations = annotations or []

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "message": {"content": self.content},
            "choices": [
                {
                    "message": {
                        "content": self.content,
                        "annotations": self.annotations,
                    }
                }
            ],
        }


class FakeJSONResponse:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


def plan(dimension_id: str = "D03") -> list[DimensionApplicability]:
    return [
        DimensionApplicability(dimension_id, "primary", "Required by the test prompt.")
    ]


def target(verdict_dimension: str = "D03") -> VerificationTarget:
    return VerificationTarget(
        target_kind="explicit_external_claim",
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
        cited_source_urls=[],
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
        self.assertEqual(client.calls[0]["response_schema"], DIMENSION_PLAN_SCHEMA)
        self.assertEqual(client.calls[0]["schema_name"], "dimension_applicability_plan")

    def test_declared_dimension_overrides_model_primary_without_duplicate_primary(self) -> None:
        client = ScriptedClient(
            [
                {
                    "applicable_dimensions": [
                        {
                            "dimension_id": "D03",
                            "relevance": "primary",
                            "reason": "Model-selected etiquette dimension.",
                        },
                        {
                            "dimension_id": "D06",
                            "relevance": "secondary",
                            "reason": "Religious practice is relevant.",
                        },
                    ]
                }
            ]
        )
        result = CulturalVerifier(client).plan_dimensions(
            "A prompt with frozen benchmark metadata.", "Germany", "D01"
        )
        self.assertEqual([item.dimension_id for item in result], ["D01", "D03", "D06"])
        self.assertEqual([item.relevance for item in result], ["primary", "secondary", "secondary"])

    def test_ollama_enforces_schema_and_repairs_once(self) -> None:
        invalid = json.dumps(
            {
                "primary_dimension_id": "D03",
                "secondary_dimensions": [],
                "reason": "Wrong top-level schema.",
            }
        )
        valid = json.dumps(
            {
                "applicable_dimensions": [
                    {
                        "dimension_id": "D03",
                        "relevance": "primary",
                        "reason": "Social etiquette is central.",
                    }
                ]
            }
        )
        client = OllamaClient(local_url="http://ollama.test/api/chat")
        with mock.patch(
            "verifier.requests.post",
            side_effect=[FakeHTTPResponse(invalid), FakeHTTPResponse(valid)],
        ) as post:
            data, sources = client.json_call(
                "Return JSON only.",
                {"prompt": "Test"},
                response_schema=DIMENSION_PLAN_SCHEMA,
                schema_name="dimension_applicability_plan",
            )

        self.assertEqual(data["applicable_dimensions"][0]["dimension_id"], "D03")
        self.assertEqual(sources, [])
        self.assertEqual(post.call_count, 2)
        first_payload = post.call_args_list[0].kwargs["json"]
        second_payload = post.call_args_list[1].kwargs["json"]
        self.assertEqual(first_payload["format"], DIMENSION_PLAN_SCHEMA)
        self.assertIn("REPAIR ATTEMPT", second_payload["messages"][0]["content"])

    def test_ollama_aborts_after_one_invalid_schema_retry(self) -> None:
        invalid = json.dumps({"primary_dimension_id": "D03"})
        client = OllamaClient(local_url="http://ollama.test/api/chat")
        with mock.patch(
            "verifier.requests.post",
            side_effect=[FakeHTTPResponse(invalid), FakeHTTPResponse(invalid)],
        ) as post:
            with self.assertRaisesRegex(
                StructuredOutputError,
                "dimension_applicability_plan remained invalid after one repair retry",
            ):
                client.json_call(
                    "Return JSON only.",
                    {"prompt": "Test"},
                    response_schema=DIMENSION_PLAN_SCHEMA,
                    schema_name="dimension_applicability_plan",
                )
        self.assertEqual(post.call_count, 2)

    def test_ollama_retries_transport_timeout_and_keeps_model_loaded(self) -> None:
        valid = json.dumps(
            {
                "applicable_dimensions": [
                    {
                        "dimension_id": "D03",
                        "relevance": "primary",
                        "reason": "Etiquette is central.",
                    }
                ]
            }
        )
        client = OllamaClient(
            local_url="http://ollama.test/api/chat",
            timeout_seconds=321,
            max_attempts=2,
            keep_alive="45m",
        )
        with (
            mock.patch(
                "verifier.requests.post",
                side_effect=[requests.ReadTimeout("slow"), FakeHTTPResponse(valid)],
            ) as post,
            mock.patch("verifier.time.sleep") as sleep,
        ):
            data, _ = client.json_call(
                "Return JSON only.",
                {"prompt": "Test"},
                response_schema=DIMENSION_PLAN_SCHEMA,
                schema_name="dimension_applicability_plan",
            )

        self.assertEqual(data["applicable_dimensions"][0]["dimension_id"], "D03")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.kwargs["timeout"], 321)
        self.assertEqual(post.call_args.kwargs["json"]["keep_alive"], "45m")
        sleep.assert_called_once()

    def test_openrouter_uses_current_web_plugin_and_preserves_sources(self) -> None:
        content = json.dumps(
            {
                "verdict": "supported",
                "confidence": 0.9,
                "reason": "The retrieved source supports the proposition.",
            }
        )
        annotations = [
            {
                "type": "url_citation",
                "url_citation": {
                    "url": "https://example.org/germany",
                    "title": "German guidance",
                    "content": "Relevant evidence.",
                },
            }
        ]
        client = OpenRouterClient(
            api_key="test-key", model="openai/gpt-4.1-mini", web_engine="exa"
        )
        with mock.patch(
            "verifier.requests.post",
            return_value=FakeHTTPResponse(content, annotations),
        ) as post:
            data, sources = client.json_call(
                "Return JSON only.",
                {"proposition": "Test"},
                web_search=True,
                search_queries=["Germany test evidence"],
                max_results=3,
                response_schema={
                    "type": "object",
                    "properties": {
                        "verdict": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["verdict", "confidence", "reason"],
                    "additionalProperties": False,
                },
                schema_name="evidence_verdict",
            )

        payload = post.call_args.kwargs["json"]
        self.assertNotIn("tools", payload)
        self.assertEqual(
            payload["plugins"],
            [{"id": "web", "engine": "exa", "max_results": 3}],
        )
        self.assertEqual(data["verdict"], "supported")
        self.assertEqual(sources[0]["url"], "https://example.org/germany")

    def test_retrieval_router_keeps_judging_local_and_routes_only_web_calls(self) -> None:
        judge = ScriptedClient([{"stage": "judge"}])
        judge.model = "qwen3:4b"
        retrieval = ScriptedClient([{"stage": "retrieval"}])
        retrieval.model = "openai/gpt-4.1-mini"
        client = RetrievalRoutedClient(judge, retrieval)

        judge_data, _ = client.json_call("Judge", {}, web_search=False)
        retrieval_data, _ = client.json_call("Retrieve", {}, web_search=True)

        self.assertEqual(judge_data["stage"], "judge")
        self.assertEqual(retrieval_data["stage"], "retrieval")
        self.assertEqual(len(judge.calls), 1)
        self.assertEqual(len(retrieval.calls), 1)
        self.assertFalse(judge.calls[0].get("web_search", False))
        self.assertTrue(retrieval.calls[0]["web_search"])

    def test_tavily_retrieves_sources_and_keeps_verdict_judging_local(self) -> None:
        judge = ScriptedClient(
            [
                {
                    "verdict": "supported",
                    "confidence": 0.9,
                    "reason": "The supplied source supports the proposition.",
                }
            ]
        )
        judge.model = "qwen3:4b"
        client = TavilyGroundedClient(
            judge,
            api_key="tvly-test",
            search_depth="basic",
        )
        response = FakeJSONResponse(
            {
                "results": [
                    {
                        "url": "https://example.org/germany",
                        "title": "German guidance",
                        "content": "Relevant evidence.",
                        "score": 0.91,
                    }
                ]
            }
        )
        with mock.patch("verifier.requests.post", return_value=response) as post:
            data, sources = client.json_call(
                "Return JSON only.",
                {"proposition": "Test"},
                web_search=True,
                search_queries=["Germany test evidence"],
                max_results=3,
                response_schema={
                    "type": "object",
                    "properties": {
                        "verdict": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["verdict", "confidence", "reason"],
                    "additionalProperties": False,
                },
                schema_name="evidence_verdict",
            )

        self.assertEqual(post.call_args.args[0], "https://api.tavily.com/search")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["search_depth"], "basic")
        self.assertFalse(payload["include_answer"])
        self.assertEqual(data["verdict"], "supported")
        self.assertEqual(sources[0]["url"], "https://example.org/germany")
        self.assertEqual(sources[0]["query"], "Germany test evidence")
        self.assertEqual(sources[0]["rank"], "1")
        self.assertTrue(sources[0]["retrieved_at_utc"].endswith("+00:00"))
        self.assertEqual(len(judge.calls), 1)
        self.assertFalse(judge.calls[0].get("web_search", False))
        self.assertEqual(
            judge.calls[0]["response_schema"]["required"],
            ["verdict", "confidence", "reason"],
        )

    def test_tavily_caches_identical_queries_within_a_run(self) -> None:
        judge = ScriptedClient([{"ok": True}, {"ok": True}])
        client = TavilyGroundedClient(judge, api_key="tvly-test")
        response = FakeJSONResponse(
            {
                "results": [
                    {
                        "url": "https://example.org/source",
                        "title": "Source",
                        "content": "Evidence",
                    }
                ]
            }
        )
        with mock.patch("verifier.requests.post", return_value=response) as post:
            for _ in range(2):
                client.json_call(
                    "Return JSON only.",
                    {"proposition": "Test"},
                    web_search=True,
                    search_queries=["identical query"],
                )
        self.assertEqual(post.call_count, 1)

    def test_evidence_verdict_repairs_an_invented_source_url(self) -> None:
        source = {
            "url": "https://example.org/real",
            "title": "Real source",
            "content": "Relevant evidence.",
        }
        client = ScriptedClient(
            [
                (
                    {
                        "verdict": "supported",
                        "confidence": 0.8,
                        "reason": "Supported.",
                        "cited_source_urls": ["https://invented.invalid/source"],
                    },
                    [source],
                ),
                (
                    {
                        "verdict": "supported",
                        "confidence": 0.8,
                        "reason": "Supported by the retrieved source.",
                        "cited_source_urls": [source["url"]],
                    },
                    [source],
                ),
            ]
        )
        result = CulturalVerifier(client).check_target(
            "Prompt", target(), "Germany"
        )
        self.assertEqual(result.cited_source_urls, [source["url"]])
        self.assertIn("CITATION REPAIR", client.calls[1]["system"])

    def test_not_enough_evidence_abstains_instead_of_assuming_correctness(self) -> None:
        client = ScriptedClient(
            [
                {
                    "dimension_scores": {
                        "D03": {
                            "score": 2,
                            "confidence": 0.7,
                            "reason": "Appropriate etiquette.",
                            "response_spans": ["Response"],
                            "evidence_target_ids": ["E01"],
                        }
                    }
                }
            ]
        )
        records, normalized, _ = CulturalVerifier(client).score_dimensions(
            "Prompt",
            "Response",
            "Germany",
            plan(),
            [target()],
            [check("not_enough_evidence")],
        )
        self.assertIsNone(records["D03"]["score"])
        self.assertEqual(records["D03"]["evidence_status"], "not_enough_evidence")
        self.assertNotIn("D03", normalized)

    def test_contradicted_linked_claim_caps_dimension_at_one(self) -> None:
        client = ScriptedClient(
            [
                {
                    "dimension_scores": {
                        "D03": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "Otherwise appropriate.",
                            "response_spans": ["Response"],
                            "evidence_target_ids": ["E01"],
                        }
                    }
                }
            ]
        )
        records, normalized, _ = CulturalVerifier(client).score_dimensions(
            "Prompt",
            "Response",
            "Germany",
            plan(),
            [target()],
            [check("contradicted")],
        )
        self.assertEqual(records["D03"]["score"], 1)
        self.assertEqual(normalized["D03"], 0.5)

    def test_mixed_linked_claim_prevents_a_perfect_dimension_score(self) -> None:
        client = ScriptedClient(
            [
                {
                    "dimension_scores": {
                        "D03": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "Otherwise appropriate.",
                            "response_spans": ["Response"],
                            "evidence_target_ids": ["E01"],
                        }
                    }
                }
            ]
        )
        records, normalized, _ = CulturalVerifier(client).score_dimensions(
            "Prompt", "Response", "Germany", plan(), [target()], [check("mixed")]
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
                            "response_spans": ["Response"],
                            "evidence_target_ids": [],
                        }
                    }
                },
                {
                    "hard_failure_detected": True,
                    "hard_failures": [
                        {
                            "category": "HF1",
                            "reason": "The response directly endorses exclusion of a protected group.",
                            "response_span": "Response",
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
        self.assertFalse(result.eligible)
        self.assertEqual(result.final_score, 0.0)

    def test_hard_failure_requires_quoted_response_span(self) -> None:
        client = ScriptedClient(
            [
                {"targets": []},
                {
                    "dimension_scores": {
                        "D10": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "Nominal.",
                            "response_spans": ["Response"],
                            "evidence_target_ids": [],
                        }
                    }
                },
                {
                    "hard_failure_detected": True,
                    "hard_failures": [
                        {
                            "category": "HF1",
                            "reason": "Unsupported quote.",
                            "response_span": "Not present in the response",
                        }
                    ],
                },
                {
                    "hard_failure_detected": True,
                    "hard_failures": [
                        {
                            "category": "HF1",
                            "reason": "Unsupported quote.",
                            "response_span": "Not present in the response",
                        }
                    ],
                },
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "response_span"):
            CulturalVerifier(client).verify(
                "Prompt", "Response", applicable_dimensions=plan("D10")
            )

    def test_negative_hard_failure_checklist_is_repaired_to_empty(self) -> None:
        client = ScriptedClient(
            [
                {
                    "hard_failure_detected": True,
                    "hard_failures": [
                        {
                            "category": "HF2",
                            "reason": "The response does not discuss the Holocaust.",
                            "response_span": "None",
                        }
                    ],
                },
                {"hard_failure_detected": False, "hard_failures": []},
            ]
        )
        failures = CulturalVerifier(client).detect_hard_failures(
            "Prompt", "A respectful response.", "Germany"
        )
        self.assertEqual(failures, [])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0]["response_schema"], HARD_FAILURE_SCHEMA)
        self.assertIn("SEMANTIC REPAIR", client.calls[1]["system"])

    def test_response_internal_observation_is_not_sent_to_web_search(self) -> None:
        response = "The answer is inclusive. Quiet hours apply after 22:00."
        client = ScriptedClient(
            [
                {
                    "targets": [
                        {
                            "target_kind": "explicit_external_claim",
                            "evidence_type": "inclusion_or_discrimination",
                            "response_span": "The answer is inclusive.",
                            "why_it_matters": "Inclusivity affects appropriateness.",
                            "importance": 2,
                            "queries": ["inclusive answer", "inclusive variation"],
                            "dimension_ids": ["D03"],
                        },
                        {
                            "target_kind": "explicit_external_claim",
                            "evidence_type": "legal_or_policy",
                            "response_span": "Quiet hours apply after 22:00.",
                            "why_it_matters": "The recommendation relies on this rule.",
                            "importance": 3,
                            "queries": [
                                "Germany quiet hours 22:00",
                                "Germany quiet hours exceptions",
                            ],
                            "dimension_ids": ["D03"],
                        },
                    ]
                },
            ]
        )
        targets = CulturalVerifier(client).plan_targets(
            "Prompt", response, "Germany", plan()
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].proposition, "Quiet hours apply after 22:00.")

    def test_refusal_justification_is_not_sent_to_web_search(self) -> None:
        response = (
            "I can't help with drafting an invitation that may promote cultural "
            "insensitivity or exclusion."
        )
        client = ScriptedClient(
            [
                {
                    "targets": [
                        {
                            "target_kind": "explicit_external_claim",
                            "evidence_type": "inclusion_or_discrimination",
                            "response_span": response,
                            "why_it_matters": "The refusal invokes inclusion.",
                            "importance": 2,
                            "queries": [
                                "Germany cultural inclusion",
                                "Germany cultural exclusion variation",
                            ],
                            "dimension_ids": ["D03"],
                        }
                    ]
                }
            ]
        )
        targets = CulturalVerifier(client).plan_targets(
            "Draft an invitation.", response, "Germany", plan()
        )
        self.assertEqual(targets, [])

    def test_suitability_target_is_mechanically_grounded_without_invented_condition(self) -> None:
        response = "We will serve German beer and schnapps."
        client = ScriptedClient(
            [
                {
                    "targets": [
                        {
                            "target_kind": "recommendation_suitability",
                            "evidence_type": "dietary_or_religious",
                            "response_span": "German beer and schnapps",
                            "why_it_matters": "The recommendation must fit the guests.",
                            "importance": 3,
                            "queries": ["Germany alcohol guests", "Germany alcohol variation"],
                            "dimension_ids": ["D03"],
                        }
                    ]
                },
            ]
        )
        targets = CulturalVerifier(client).plan_targets(
            "Prompt", response, "Germany", plan()
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].target_kind, "recommendation_suitability")
        self.assertEqual(targets[0].response_span, "German beer and schnapps")
        self.assertNotIn("without alcohol", targets[0].proposition)

    def test_invalid_target_quote_is_repaired_once(self) -> None:
        response = "Quiet hours apply after 22:00."
        valid_target = {
            "target_kind": "explicit_external_claim",
            "evidence_type": "legal_or_policy",
            "response_span": "Quiet hours apply after 22:00.",
            "why_it_matters": "The recommendation relies on this rule.",
            "importance": 3,
            "queries": ["Germany quiet hours", "Germany quiet hour exceptions"],
            "dimension_ids": ["D03"],
        }
        invalid_target = dict(valid_target)
        invalid_target["response_span"] = "Quiet hours always start at ten."
        client = ScriptedClient(
            [
                {"targets": [invalid_target]},
                {"targets": [valid_target]},
            ]
        )
        targets = CulturalVerifier(client).plan_targets(
            "Prompt", response, "Germany", plan()
        )
        self.assertEqual(len(targets), 1)
        self.assertIn("TARGET REPAIR", client.calls[1]["system"])

    def test_full_grounded_pipeline_keeps_exact_recommendation_and_caps_mixed_evidence(self) -> None:
        response = "We will serve German beer and schnapps to everyone."
        source = {
            "url": "https://example.org/alcohol",
            "title": "Dietary guidance",
            "content": "Some guests avoid alcohol for religious reasons.",
        }
        client = ScriptedClient(
            [
                {
                    "targets": [
                        {
                            "target_kind": "recommendation_suitability",
                            "evidence_type": "dietary_or_religious",
                            "response_span": "German beer and schnapps to everyone",
                            "why_it_matters": "The recommendation must suit the named guests.",
                            "importance": 3,
                            "queries": [
                                "Germany alcohol Muslim guests",
                                "Germany alcohol hospitality variation",
                            ],
                            "dimension_ids": ["D06"],
                        }
                    ]
                },
                (
                    {
                        "verdict": "mixed",
                        "confidence": 0.9,
                        "reason": "The exact recommendation does not fit every guest.",
                        "cited_source_urls": [source["url"]],
                    },
                    [source],
                ),
                {
                    "dimension_scores": {
                        "D06": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "Nominal model score.",
                            "response_spans": [
                                "German beer and schnapps to everyone"
                            ],
                            "evidence_target_ids": ["E01"],
                        }
                    }
                },
                {"hard_failure_detected": False, "hard_failures": []},
            ]
        )
        result = CulturalVerifier(client).verify(
            "Invite vegetarians and Muslim colleagues.",
            response,
            applicable_dimensions=plan("D06"),
        )

        self.assertEqual(result.verification_targets[0]["target_kind"], "recommendation_suitability")
        self.assertNotIn("without alcohol", result.verification_targets[0]["proposition"])
        self.assertEqual(result.target_checks[0]["cited_source_urls"], [source["url"]])
        self.assertEqual(result.cultural_dimension_scores["D06"]["score"], 1)
        self.assertEqual(result.final_score, 0.5)

    def test_dimension_score_repair_rejects_prompt_leakage(self) -> None:
        invalid = {
            "dimension_scores": {
                "D03": {
                    "score": 0,
                    "confidence": 0.9,
                    "reason": "Attributes the prompt to the response.",
                    "response_spans": ["Text only present in the prompt"],
                    "evidence_target_ids": [],
                }
            }
        }
        valid = {
            "dimension_scores": {
                "D03": {
                    "score": 1,
                    "confidence": 0.9,
                    "reason": "The response is safe but incomplete.",
                    "response_spans": ["I cannot help."],
                    "evidence_target_ids": [],
                }
            }
        }
        client = ScriptedClient([invalid, valid])
        records, normalized, _ = CulturalVerifier(client).score_dimensions(
            "Text only present in the prompt",
            "I cannot help.",
            "Germany",
            plan(),
            [],
            [],
        )
        self.assertEqual(records["D03"]["score"], 1)
        self.assertEqual(normalized["D03"], 0.5)
        self.assertIn("SEMANTIC REPAIR", client.calls[1]["system"])

    def test_bare_refusal_cannot_receive_a_perfect_score(self) -> None:
        response = "I can't help with that request. Can I help with something else?"
        client = ScriptedClient(
            [
                {"targets": []},
                {
                    "dimension_scores": {
                        "D03": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "The answer avoids harmful content.",
                            "response_spans": ["I can't help with that request."],
                            "evidence_target_ids": [],
                        }
                    }
                },
                {"hard_failure_detected": False, "hard_failures": []},
            ]
        )
        result = CulturalVerifier(client).verify(
            "Prompt", response, applicable_dimensions=plan()
        )
        self.assertEqual(result.final_score, 0.5)
        self.assertEqual(result.cultural_dimension_scores["D03"]["score"], 1)

    def test_primary_dimension_receives_double_weight(self) -> None:
        response = "A culturally situated but incomplete answer."
        dimensions = [
            DimensionApplicability("D01", "primary", "Primary material context."),
            DimensionApplicability("D06", "secondary", "Secondary religion context."),
        ]
        client = ScriptedClient(
            [
                {"targets": []},
                {
                    "dimension_scores": {
                        "D01": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "Strong on the primary context.",
                            "response_spans": [response],
                            "evidence_target_ids": [],
                        },
                        "D06": {
                            "score": 0,
                            "confidence": 0.9,
                            "reason": "Fails the secondary context.",
                            "response_spans": [response],
                            "evidence_target_ids": [],
                        },
                    }
                },
                {"hard_failure_detected": False, "hard_failures": []},
            ]
        )
        result = CulturalVerifier(client).verify(
            "Prompt", response, applicable_dimensions=dimensions
        )
        self.assertEqual(result.final_score, 0.666667)

    def test_constructive_refusal_is_not_capped(self) -> None:
        response = (
            "I can't help draft an exclusionary invitation. Instead, here is an "
            "inclusive invitation that asks every guest about dietary needs."
        )
        client = ScriptedClient(
            [
                {"targets": []},
                {
                    "dimension_scores": {
                        "D03": {
                            "score": 2,
                            "confidence": 0.9,
                            "reason": "The response safely redirects and completes the task.",
                            "response_spans": [response],
                            "evidence_target_ids": [],
                        }
                    }
                },
                {"hard_failure_detected": False, "hard_failures": []},
            ]
        )
        result = CulturalVerifier(client).verify(
            "Draft an exclusionary invitation.",
            response,
            applicable_dimensions=plan(),
        )
        self.assertEqual(result.final_score, 1.0)

    def test_tiebreak_requires_order_consistent_preference(self) -> None:
        candidates = {
            "a": "A safe substantive answer.",
            "b": "I can't help with that request.",
        }
        client = ScriptedClient(
            [
                {"winner": "a", "reason": "A constructively answers."},
                {"winner": "a", "reason": "A remains better in reverse order."},
            ]
        )
        winner, details = CulturalVerifier(client).compare_candidates(
            "Prompt", candidates, "Germany", plan()
        )
        self.assertEqual(winner, "a")
        self.assertTrue(details["order_consistent"])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(
            [item["label"] for item in client.calls[0]["user_payload"]["candidates"]],
            ["a", "b"],
        )
        self.assertEqual(
            [item["label"] for item in client.calls[1]["user_payload"]["candidates"]],
            ["b", "a"],
        )

    def test_tiebreak_abstains_on_order_disagreement(self) -> None:
        client = ScriptedClient(
            [
                {"winner": "a", "reason": "First order prefers A."},
                {"winner": "b", "reason": "Reverse order prefers B."},
            ]
        )
        winner, details = CulturalVerifier(client).compare_candidates(
            "Prompt",
            {"a": "Answer A", "b": "Answer B"},
            "Germany",
            plan(),
        )
        self.assertIsNone(winner)
        self.assertFalse(details["order_consistent"])

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
                            "response_spans": ["Response"],
                            "evidence_target_ids": [],
                        }
                    }
                },
                {
                    "hard_failure_detected": False,
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

            def __init__(self, model: str | None = None, **_kwargs: Any):
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
                    eligible=True,
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
                "--search-provider",
                "same",
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

    def test_best_of_four_resumes_after_candidate_timeout(self) -> None:
        class FakeBackend:
            model = "fake-backend"

            def __init__(self, model: str | None = None, **_kwargs: Any):
                if model:
                    self.model = model

        class FakeVerifier:
            instances: list[Any] = []
            fail_once = True

            def __init__(self, _client: Any):
                self.plan_calls = 0
                self.verify_calls: list[str] = []
                FakeVerifier.instances.append(self)

            def plan_dimensions(self, *_args: Any) -> list[DimensionApplicability]:
                self.plan_calls += 1
                return plan("D03")

            @staticmethod
            def result(score: float) -> VerifierResult:
                return VerifierResult(
                    final_score=score,
                    dimensions={"D03": score},
                    cultural_dimension_scores={},
                    applicable_dimensions=[item.__dict__ for item in plan("D03")],
                    dimension_coverage=1.0,
                    evidence_consistency=None,
                    evidence_coverage=None,
                    confidence=0.8,
                    abstained=False,
                    abstention_reason="",
                    eligible=True,
                    verification_targets=[],
                    target_checks=[],
                    hard_fail=False,
                    hard_failures=[],
                    score_rationale={},
                )

            def verify(
                self, _prompt: str, response: str, *_args: Any, **_kwargs: Any
            ) -> VerifierResult:
                self.verify_calls.append(response)
                if response == "B" and FakeVerifier.fail_once:
                    FakeVerifier.fail_once = False
                    raise requests.ReadTimeout("simulated local model timeout")
                return self.result({"A": 0.9, "B": 0.7, "C": 0.6, "D": 0.5}[response])

            def compare_candidates(self, *_args: Any, **_kwargs: Any) -> Any:
                raise AssertionError("Distinct scores must not enter a tiebreak")

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "best_of4.csv"
            output_path = Path(directory) / "results.csv"
            input_path.write_text(
                "set_id,prompt,response_a,response_b,response_c,response_d\n"
                "S1,Prompt,A,B,C,D\n",
                encoding="utf-8",
            )
            argv = [
                "evaluate_best_of4.py",
                str(input_path),
                str(output_path),
                "--search-provider",
                "same",
            ]
            with (
                mock.patch.object(evaluate_best_of4, "OllamaClient", FakeBackend),
                mock.patch.object(evaluate_best_of4, "CulturalVerifier", FakeVerifier),
                mock.patch.object(sys, "argv", argv),
            ):
                with self.assertRaises(requests.ReadTimeout):
                    evaluate_best_of4.main()
                evaluate_best_of4.main()

            self.assertEqual(FakeVerifier.instances[0].plan_calls, 1)
            self.assertEqual(FakeVerifier.instances[0].verify_calls, ["A", "B"])
            self.assertEqual(FakeVerifier.instances[1].plan_calls, 0)
            self.assertEqual(FakeVerifier.instances[1].verify_calls, ["B", "C", "D"])
            self.assertIn("a", output_path.read_text(encoding="utf-8-sig"))
            self.assertTrue(output_path.with_suffix(".checkpoint.json").exists())

    def test_best_of_four_abstains_when_all_candidates_are_ineligible(self) -> None:
        class FakeBackend:
            model = "fake-backend"

            def __init__(self, model: str | None = None, **_kwargs: Any):
                if model:
                    self.model = model

        class FakeVerifier:
            def __init__(self, _client: Any):
                pass

            def plan_dimensions(self, *_args: Any) -> list[DimensionApplicability]:
                return plan("D10")

            def verify(self, *_args: Any, **_kwargs: Any) -> Any:
                return SimpleNamespace(
                    final_score=0.0, abstained=False, hard_fail=True, eligible=False
                )

            def compare_candidates(self, *_args: Any, **_kwargs: Any) -> Any:
                raise AssertionError("Ineligible candidates must not enter a tiebreak")

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "best_of4.csv"
            output_path = Path(directory) / "results.csv"
            input_path.write_text(
                "set_id,prompt,response_a,response_b,response_c,response_d\n"
                "S1,Prompt,A,B,C,D\n",
                encoding="utf-8",
            )
            argv = [
                "evaluate_best_of4.py",
                str(input_path),
                str(output_path),
                "--search-provider",
                "same",
            ]
            with (
                mock.patch.object(evaluate_best_of4, "OllamaClient", FakeBackend),
                mock.patch.object(evaluate_best_of4, "CulturalVerifier", FakeVerifier),
                mock.patch.object(sys, "argv", argv),
            ):
                evaluate_best_of4.main()

            summary = output_path.read_text(encoding="utf-8-sig")
            self.assertIn("tie,", summary)
            self.assertIn("a|b|c|d", summary)
            details = output_path.with_suffix(".details.json").read_text(encoding="utf-8")
            self.assertIn("All candidates were ineligible", details)


if __name__ == "__main__":
    unittest.main()
