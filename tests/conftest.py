import json
import pytest
from cultverify import Config, CulturalVerifier
from cultverify.schemas import RetrievedDocument
from cultverify.trace import digest, stable_id

PROMPT = "Explain visiting arrangements for a local community event."
RESPONSE = "Check the organiser’s published visiting arrangements."


class FixtureLLM:
    """Scripted contract fixture, not a model of cultural correctness."""

    def __init__(self, config, *, overrides=None):
        self.config = config
        self.calls = []
        self.overrides = overrides or {}

    def complete(self, *, stage, system, payload, schema):
        self.calls.append({"stage": stage, "system": system, "payload": payload, "schema": schema})
        if stage in self.overrides:
            value = self.overrides[stage]
            value = value(payload) if callable(value) else value
            if isinstance(value, Exception):
                raise value
            return value if isinstance(value, str) else json.dumps(value)
        if stage == "context_planner_v1":
            out = {"user_goal": {"value": payload["prompt"], "prompt_span": payload["prompt"]}}
        elif stage == "dimension_planner_v1":
            out = {
                "dimensions": [{"dimension_id": "D03", "role": "primary", "reason": "Event etiquette"}],
                "reasoning": "A situated social interaction",
            }
        elif stage == "target_extractor_v1":
            out = {
                "targets": [
                    {
                        "response_quote": payload["response"],
                        "proposition": "Consult the event arrangements",
                        "epistemic_type": "context_dependent_recommendation",
                        "dimension_ids": ["D03"],
                        "materiality": "Determines how the visitor proceeds",
                        "retrieval_appropriate": True,
                    }
                ]
            }
        elif stage == "verification_question_v1":
            out = {
                "questions": [
                    {"kind": "baseline", "text": "What visiting arrangements are documented for the event?"},
                    {"kind": "variation", "text": "How do visiting arrangements vary between events?"},
                ]
            }
        elif stage == "query_rewriter_v1":
            out = {"text": payload["question"]["text"]}
        elif stage == "source_classifier_v1":
            out = {
                "sources": [
                    {
                        "document_id": d["document_id"],
                        "source_type": "institutional_professional",
                        "provenance_basis": "explicit",
                        "reason": "Event organiser statement",
                    }
                    for d in payload["documents"]
                ]
            }
        elif stage == "evidence_memo_v1":
            supports = [{"quote": d["text"][:300]} for d in payload["documents"]]
            out = {
                "answer": "The organiser publishes arrangements." if supports else "No retrieved evidence.",
                "scope": "The documented event",
                "variation": "Other events may differ.",
                "agreement": "Limited evidence",
                "sufficiency": "sufficient" if supports else "insufficient",
                "confidence": "medium" if supports else "low",
                "statements": [
                    {
                        "text": "The organiser publishes arrangements.",
                        "kind": "context_sensitive_practice",
                        "supports": supports,
                    }
                ]
                if supports
                else [],
            }
        elif stage == "evidence_relevance_v1":
            out = {
                "judgments": [
                    {
                        "statement_index": statement["statement_index"],
                        "supported_by_quotes": True,
                        "relevant": True,
                        "reason": "The statement is supported by its quotes and answers the verification questions.",
                    }
                    for statement in payload["statements"]
                ]
            }
        elif stage == "followup_v1":
            out = {
                "question": {"kind": "followup", "text": "Where are the event’s official arrangements published?"},
                "reason": "Locate missing official evidence",
            }
        elif stage == "target_comparator_v1":
            out = {
                "target_id": payload["target"]["target_id"],
                "memo_id": payload["memo"]["memo_id"],
                "verdict": "supported",
                "reasoning": "The source establishes that arrangements are published",
            }
        elif stage == "dimension_scorer_v1":
            verdicts = {v["target_id"]: v for v in payload["verdicts"]}
            scores = []
            for d in payload["dimension_plan"]["dimensions"]:
                relevant_targets = [t for t in payload["targets"] if d["dimension_id"] in t["dimension_ids"]]
                external = [t for t in relevant_targets if t["retrieval_appropriate"]]
                direct = [t for t in relevant_targets if not t["retrieval_appropriate"]]
                directional = any(
                    verdicts.get(t["target_id"], {}).get("verdict") in {"supported", "mixed", "contradicted"}
                    for t in external
                )
                all_external_insufficient = bool(external) and all(
                    verdicts.get(t["target_id"], {}).get("verdict") == "insufficient" for t in external
                )
                abstain = all_external_insufficient and not direct and not directional
                scores.append(
                    {
                        "dimension_id": d["dimension_id"],
                        "score": "abstain" if abstain else 2,
                        "rationale": (
                            "Insufficient external evidence."
                            if abstain
                            else "Uses the documented event arrangements"
                        ),
                        "response_quotes": [] if abstain or not payload["response"] else [payload["response"]],
                        "target_ids": [t["target_id"] for t in relevant_targets],
                    }
                )
            out = {"scores": scores}
        else:
            raise AssertionError(stage)
        return json.dumps(out)


class FixtureRetriever:
    provider = "fixture"

    def __init__(self, empty=False):
        self.calls = []
        self.empty = empty

    def search(self, query, *, top_k, timeout):
        self.calls.append(query)
        return () if self.empty else (document(query=query),)


def document(url="https://example.org/event", text="The organiser publishes visiting arrangements.", query="query"):
    return RetrievedDocument(
        document_id=stable_id("doc", [url, text]),
        query=query,
        url=url,
        title="Event guidance",
        text=text,
        rank=1,
        retrieved_at="2026-09-16T00:00:00+00:00",
        content_hash=digest(text),
    )


@pytest.fixture
def setup(tmp_path):
    config = Config(
        verifier_model_provider="custom",
        verifier_model_id="deterministic-fixture-v1",
        cache_directory=tmp_path / "evidence",
        trace_directory=tmp_path / "traces",
    )
    llm, retriever = FixtureLLM(config), FixtureRetriever()
    return config, llm, retriever, CulturalVerifier(llm=llm, retriever=retriever, config=config)
