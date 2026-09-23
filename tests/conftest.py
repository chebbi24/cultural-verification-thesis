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
                        "reason": "Event organiser statement",
                    }
                    for d in payload["documents"]
                ]
            }
        elif stage == "evidence_memo_v1":
            ids = [d["document_id"] for d in payload["documents"]]
            out = {
                "answer": "The organiser publishes arrangements." if ids else "No retrieved evidence.",
                "scope": "The documented event",
                "variation": "Other events may differ.",
                "agreement": "Limited evidence",
                "sufficiency": "sufficient" if ids else "insufficient",
                "confidence": "medium" if ids else "low",
                "statements": [
                    {
                        "text": "The organiser publishes arrangements.",
                        "kind": "context_sensitive_practice",
                        "citations": ids,
                    }
                ]
                if ids
                else [],
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
            out = {
                "scores": [
                    {
                        "dimension_id": d["dimension_id"],
                        "score": 2,
                        "rationale": "Uses the documented event arrangements",
                        "response_quotes": [payload["response"]] if payload["response"] else [],
                        "target_ids": [t["target_id"] for t in payload["targets"]],
                        "memo_ids": [m["memo_id"] for m in payload["memos"]],
                    }
                    for d in payload["dimension_plan"]["dimensions"]
                ]
            }
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
