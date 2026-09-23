import inspect
import json
from pathlib import Path
from unittest.mock import patch
import pytest
import requests
from pydantic import ValidationError
from cultverify import CulturalVerifier
from cultverify.evidence import BlindEvidenceEngine, LLM_DOCUMENT_TEXT_LIMIT
from cultverify.schemas import (
    ContextFact,
    ContextFrame,
    DimensionApplicability,
    DimensionPlan,
    DimensionScore,
    Followup,
    InitialQuestions,
    MaterialTarget,
    RunTrace,
    TargetBatch,
)
from cultverify.prompts import PROMPTS
from cultverify.scoring import aggregate, rank_results
from cultverify.trace import digest
from cultverify.validation import (
    matching_support_documents,
    validate_context,
    validate_document_citation,
    validate_trace_links,
)
from conftest import FixtureLLM, FixtureRetriever, PROMPT, RESPONSE, document as make_document


def test_context_quote_validation():
    context = ContextFrame(location=ContextFact(value="local community", prompt_span="local community"))
    validate_context(context, PROMPT)
    with pytest.raises(ValueError):
        validate_context(context, "Other prompt")


def test_hallucinated_context_retries_then_unknown(setup):
    config, _, retriever, _ = setup
    llm = FixtureLLM(
        config, overrides={"context_planner_v1": {"location": {"value": "Invented", "prompt_span": "not present"}}}
    )
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.context == ContextFrame()
    assert len([c for c in llm.calls if c["stage"] == "context_planner_v1"]) == 2
    assert result.status == "completed"


@pytest.mark.parametrize("dimension", ["D00", "D11", "T1"])
def test_only_fixed_dimensions(dimension):
    with pytest.raises(ValidationError):
        DimensionApplicability(dimension_id=dimension, role="primary", reason="x")


def test_duplicate_dimensions_rejected():
    dim = DimensionApplicability(dimension_id="D03", role="primary", reason="x")
    with pytest.raises(ValidationError):
        DimensionPlan(dimensions=(dim, dim), reasoning="x")


def test_invalid_target_quote_abstains(setup):
    config, _, retriever, _ = setup
    target = {
        "response_quote": "hallucinated",
        "proposition": "x",
        "epistemic_type": "external_fact",
        "dimension_ids": ["D03"],
        "materiality": "x",
        "retrieval_appropriate": True,
    }
    llm = FixtureLLM(config, overrides={"target_extractor_v1": {"targets": [target]}})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "failed" and result.candidate_abstained
    assert not retriever.calls
    assert Path(result.trace_path).exists()


def test_target_limit_and_epistemic_retrieval_routing():
    target = dict(
        response_quote="x",
        proposition="x",
        epistemic_type="external_fact",
        dimension_ids=("D03",),
        materiality="x",
        retrieval_appropriate=True,
    )
    with pytest.raises(ValidationError):
        TargetBatch(targets=(target,) * 4)
    with pytest.raises(ValidationError):
        MaterialTarget(**{**target, "epistemic_type": "response_internal_quality"}, target_id="t")
    with pytest.raises(ValidationError):
        MaterialTarget(**{**target, "retrieval_appropriate": False}, target_id="t")
    with pytest.raises(ValidationError):
        MaterialTarget(
            **{**target, "epistemic_type": "descriptive_cultural_norm", "retrieval_appropriate": False},
            target_id="t",
        )
    with pytest.raises(ValidationError):
        MaterialTarget(
            **{**target, "epistemic_type": "context_dependent_recommendation", "retrieval_appropriate": False},
            target_id="t",
        )


def test_configured_target_limit(setup):
    config, _, retriever, _ = setup
    config = config.model_copy(update={"max_material_targets": 1})
    target = dict(
        response_quote=RESPONSE,
        proposition="x",
        epistemic_type="external_fact",
        dimension_ids=["D03"],
        materiality="x",
        retrieval_appropriate=True,
    )
    llm = FixtureLLM(config, overrides={"target_extractor_v1": {"targets": [target, target]}})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "failed"


def test_exactly_two_initial_questions():
    with pytest.raises(ValidationError):
        InitialQuestions(questions=({"kind": "baseline", "text": "x"},))
    with pytest.raises(ValidationError):
        InitialQuestions(questions=({"kind": "variation", "text": "x"}, {"kind": "baseline", "text": "y"}))


def test_blind_boundary_and_query_inputs(setup):
    _, llm, _, verifier = setup
    sentinel = "UNIQUE_CANDIDATE_CONTENT_67243"
    result = verifier.verify(PROMPT, sentinel)
    assert result.status == "completed"
    blind_stages = {
        "query_rewriter_v1",
        "source_classifier_v1",
        "evidence_memo_v1",
        "evidence_relevance_v1",
        "followup_v1",
    }
    forbidden = {"response", "candidate_response", "target", "candidate_label", "human_chosen", "expected_issue"}
    for call in llm.calls:
        if call["stage"] in blind_stages:
            assert sentinel not in json.dumps(call)
            assert not forbidden.intersection(call["payload"])
        if call["stage"] == "query_rewriter_v1":
            assert set(call["payload"]) == {"question", "context"}
    assert list(inspect.signature(BlindEvidenceEngine.evaluate).parameters) == ["self", "questions", "context"]
    with pytest.raises(ValidationError):
        ContextFrame(candidate_response=sentinel)
    order = [c["stage"] for c in llm.calls]
    assert order.index("evidence_memo_v1") < order.index("target_comparator_v1")


def test_source_classifier_does_not_receive_placeholder_type(setup):
    _, llm, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    calls = [c for c in llm.calls if c["stage"] == "source_classifier_v1"]
    assert calls
    for call in calls:
        for document in call["payload"]["documents"]:
            assert set(document) == {"document_id", "url", "title", "text"}
            assert "source_type" not in document


def test_llm_evidence_payload_truncates_text_but_keeps_full_snapshot(setup):
    config, _, _, _ = setup

    class LongRetriever(FixtureRetriever):
        def search(self, query, *, top_k, timeout):
            self.calls.append(query)
            doc = super().search(query, top_k=top_k, timeout=timeout)[0]
            text = "x" * (LLM_DOCUMENT_TEXT_LIMIT + 500)
            return (doc.model_copy(update={"text": text, "content_hash": digest(text)}),)

    retriever = LongRetriever()
    llm = FixtureLLM(config)
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert len(result.evidence[0].documents[0].text) == LLM_DOCUMENT_TEXT_LIMIT + 500

    for call in llm.calls:
        if call["stage"] in {"source_classifier_v1", "evidence_memo_v1"}:
            assert all(len(d["text"]) <= LLM_DOCUMENT_TEXT_LIMIT for d in call["payload"]["documents"])
        if call["stage"] == "evidence_memo_v1":
            assert all("source_ref" not in d and "document_id" not in d for d in call["payload"]["documents"])


def test_classifier_failure_falls_back_to_unknown(setup):
    config, _, retriever, _ = setup
    llm = FixtureLLM(config, overrides={"source_classifier_v1": {"sources": []}})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert result.evidence[0].source_classifications
    assert all(s.source_type == "unknown" for s in result.evidence[0].source_classifications)


def test_unsupported_legal_label_is_downgraded(setup):
    config, _, retriever, _ = setup

    def legal_memo(payload):
        supports = [{"quote": d["text"][:300]} for d in payload["documents"]]
        return {
            "answer": "Documented cultural guidance.",
            "scope": "x",
            "variation": "x",
            "agreement": "x",
            "sufficiency": "sufficient",
            "confidence": "medium",
            "statements": [
                {
                    "text": "Documented cultural guidance.",
                    "kind": "legal_institutional_rule",
                    "supports": supports,
                }
            ],
        }

    llm = FixtureLLM(config, overrides={"evidence_memo_v1": legal_memo})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert all(statement.kind == "context_sensitive_practice" for statement in result.evidence[0].memos[-1].statements)


def test_inferred_strong_provenance_is_downgraded(setup):
    config, _, retriever, _ = setup

    def inferred_academic(payload):
        return {
            "sources": [
                {
                    "document_id": d["document_id"],
                    "source_type": "academic_peer_reviewed",
                    "provenance_basis": "inferred",
                    "reason": "The page looks academic, but peer review is not explicitly established.",
                }
                for d in payload["documents"]
            ]
        }

    llm = FixtureLLM(config, overrides={"source_classifier_v1": inferred_academic})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert all(s.source_type == "unknown" for s in result.evidence[0].source_classifications)


def test_contradictory_strong_source_reason_is_downgraded(setup):
    config, _, retriever, _ = setup

    def contradictory_official(payload):
        return {
            "sources": [
                {
                    "document_id": d["document_id"],
                    "source_type": "official_legal",
                    "provenance_basis": "explicit",
                    "reason": "This source is not an official government document.",
                }
                for d in payload["documents"]
            ]
        }

    llm = FixtureLLM(config, overrides={"source_classifier_v1": contradictory_official})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert all(s.source_type == "unknown" for s in result.evidence[0].source_classifications)
    assert all(s.provenance_basis == "unclear" for s in result.evidence[0].source_classifications)


def test_self_contradictory_institutional_label_is_downgraded(setup):
    config, _, retriever, _ = setup

    def contradictory_institutional(payload):
        return {
            "sources": [
                {
                    "document_id": d["document_id"],
                    "source_type": "institutional_professional",
                    "provenance_basis": "explicit",
                    "reason": (
                        "This is a commercial tutoring platform, not a recognized institution or professional body. "
                        "The source type should be commercial_lifestyle."
                    ),
                }
                for d in payload["documents"]
            ]
        }

    llm = FixtureLLM(config, overrides={"source_classifier_v1": contradictory_institutional})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert all(s.source_type == "unknown" for s in result.evidence[0].source_classifications)
    assert all(s.provenance_basis == "unclear" for s in result.evidence[0].source_classifications)


def test_support_matching_normalizes_whitespace_case_and_typographic_quotes():
    doc = make_document(text="Du is used:\n\n By equal peers, family, friends and lovers. It is someone’s choice.")
    matches = matching_support_documents(
        "DU IS USED: BY EQUAL PEERS, FAMILY, FRIENDS AND LOVERS. IT IS SOMEONE'S CHOICE.",
        (doc,),
    )
    assert matches == (doc,)


def test_ungrounded_support_is_dropped_and_memo_downgraded(setup):
    config, _, retriever, _ = setup

    def bad_support(payload):
        return {
            "answer": "Unsupported",
            "scope": "x",
            "variation": "x",
            "agreement": "x",
            "sufficiency": "sufficient",
            "confidence": "high",
            "statements": [
                {
                    "text": "Unsupported",
                    "kind": "context_sensitive_practice",
                    "supports": [{"quote": "not present in the retrieved document"}],
                }
            ],
        }

    llm = FixtureLLM(config, overrides={"evidence_memo_v1": bad_support})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert result.evidence[0].memos[-1].sufficiency == "insufficient"
    assert result.evidence[0].memos[-1].confidence == "low"
    assert result.evidence[0].memos[-1].statements == ()
    assert result.verdicts[0].verdict == "insufficient"


def test_partial_grounding_loss_preserves_sufficient_evidence_with_lower_confidence(setup):
    config, _, retriever, _ = setup

    def partial_memo(payload):
        valid_quote = payload["documents"][0]["text"][:300]
        return {
            "answer": "One grounded statement survives.",
            "scope": "x",
            "variation": "x",
            "agreement": "x",
            "sufficiency": "sufficient",
            "confidence": "high",
            "statements": [
                {
                    "text": "The organiser publishes arrangements.",
                    "kind": "context_sensitive_practice",
                    "supports": [{"quote": valid_quote}],
                },
                {
                    "text": "Unsupported extra claim.",
                    "kind": "context_sensitive_practice",
                    "supports": [{"quote": "not present in any supplied document"}],
                },
            ],
        }

    llm = FixtureLLM(config, overrides={"evidence_memo_v1": partial_memo})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    memo = result.evidence[0].memos[-1]
    assert result.status == "completed"
    assert memo.sufficiency == "sufficient"
    assert memo.confidence == "medium"
    assert len(memo.statements) == 1
    assert result.evidence_coverage == 1
    assert result.verdicts[0].verdict == "supported"


def test_grounded_but_unsupported_synthesis_is_filtered(setup):
    config, _, retriever, _ = setup

    def overclaim_memo(payload):
        return {
            "answer": "Overclaim",
            "scope": "x",
            "variation": "x",
            "agreement": "x",
            "sufficiency": "sufficient",
            "confidence": "high",
            "statements": [
                {
                    "text": "The organiser requires every visitor to do something universal.",
                    "kind": "universal_claim",
                    "supports": [{"quote": payload["documents"][0]["text"][:300]}],
                }
            ],
        }

    def support_gate(payload):
        return {
            "judgments": [
                {
                    "statement_index": statement["statement_index"],
                    "supported_by_quotes": False,
                    "relevant": True,
                    "reason": "The claim materially exceeds the quoted evidence.",
                }
                for statement in payload["statements"]
            ]
        }

    llm = FixtureLLM(
        config,
        overrides={"evidence_memo_v1": overclaim_memo, "evidence_relevance_v1": support_gate},
    )
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    memo = result.evidence[0].memos[-1]
    assert result.status == "completed"
    assert memo.statements == ()
    assert memo.sufficiency == "insufficient"
    assert memo.confidence == "low"
    assert result.verdicts[0].verdict == "insufficient"


def test_irrelevant_grounded_statement_is_filtered_before_freeze(setup):
    config, _, retriever, _ = setup

    def irrelevant_memo(payload):
        return {
            "answer": "Contains retrieval noise.",
            "scope": "x",
            "variation": "x",
            "agreement": "x",
            "sufficiency": "sufficient",
            "confidence": "high",
            "statements": [
                {
                    "text": "The organiser publishes arrangements.",
                    "kind": "context_sensitive_practice",
                    "supports": [{"quote": payload["documents"][0]["text"][:300]}],
                }
            ],
        }

    def irrelevant_gate(payload):
        return {
            "judgments": [
                {
                    "statement_index": statement["statement_index"],
                    "supported_by_quotes": True,
                    "relevant": False,
                    "reason": "The statement is grounded but does not answer either verification question.",
                }
                for statement in payload["statements"]
            ]
        }

    llm = FixtureLLM(
        config,
        overrides={
            "evidence_memo_v1": irrelevant_memo,
            "evidence_relevance_v1": irrelevant_gate,
        },
    )
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    memo = result.evidence[0].memos[-1]
    assert result.status == "completed"
    assert memo.statements == ()
    assert memo.sufficiency == "insufficient"
    assert memo.confidence == "low"
    assert result.verdicts[0].verdict == "insufficient"
    assert not any(call["stage"] == "target_comparator_v1" for call in llm.calls)


def test_downstream_decisions_receive_only_exact_or_structured_inputs(setup):
    _, llm, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    assert result.status == "completed"

    target_call = next(call for call in llm.calls if call["stage"] == "target_extractor_v1")
    assert "reasoning" not in target_call["payload"]["dimension_plan"]
    assert all(
        set(dimension) == {"dimension_id", "role"}
        for dimension in target_call["payload"]["dimension_plan"]["dimensions"]
    )

    question_call = next(call for call in llm.calls if call["stage"] == "verification_question_v1")
    assert set(question_call["payload"]["target"]) == {"response_quote", "epistemic_type", "dimension_ids"}
    assert not {"target_id", "proposition", "materiality"}.intersection(question_call["payload"]["target"])

    comparator_call = next(call for call in llm.calls if call["stage"] == "target_comparator_v1")
    assert set(comparator_call["payload"]["target"]) == {"target_id", "response_quote"}
    assert set(comparator_call["payload"]["memo"]) == {"memo_id", "sufficiency", "evidence_groups"}
    assert not {
        "answer",
        "scope",
        "variation",
        "agreement",
        "confidence",
        "citations",
        "statements",
    }.intersection(comparator_call["payload"]["memo"])
    assert all(set(group) == {"supports"} for group in comparator_call["payload"]["memo"]["evidence_groups"])

    scorer_call = next(call for call in llm.calls if call["stage"] == "dimension_scorer_v1")
    assert all(
        set(dimension) == {"dimension_id"} for dimension in scorer_call["payload"]["dimension_plan"]["dimensions"]
    )
    assert all(
        set(target) == {"target_id", "response_quote", "dimension_ids", "epistemic_type", "retrieval_appropriate"}
        for target in scorer_call["payload"]["targets"]
    )
    assert all(set(verdict) == {"target_id", "memo_id", "verdict"} for verdict in scorer_call["payload"]["verdicts"])
    assert all(set(memo) == {"memo_id", "sufficiency", "evidence_groups"} for memo in scorer_call["payload"]["memos"])


def test_directional_verdict_forces_numeric_score_retry(setup):
    config, _, retriever, _ = setup
    attempts = {"n": 0}

    def scorer(payload):
        attempts["n"] += 1
        value = "abstain" if attempts["n"] == 1 else 1
        return {
            "scores": [
                {
                    "dimension_id": d["dimension_id"],
                    "score": value,
                    "rationale": "Assessable but incomplete evidence.",
                    "response_quotes": [payload["response"]],
                    "target_ids": [t["target_id"] for t in payload["targets"]],
                }
                for d in payload["dimension_plan"]["dimensions"]
            ]
        }

    llm = FixtureLLM(config, overrides={"dimension_scorer_v1": scorer})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert attempts["n"] == 2
    assert all(score.score == 1 for score in result.dimension_scores)


def test_numeric_score_requires_assessable_target_link(setup):
    config, _, retriever, _ = setup
    attempts = {"n": 0}

    def scorer(payload):
        attempts["n"] += 1
        target_ids = [] if attempts["n"] == 1 else [payload["targets"][0]["target_id"]]
        return {
            "scores": [
                {
                    "dimension_id": d["dimension_id"],
                    "score": 2,
                    "rationale": "Assessable evidence.",
                    "response_quotes": [payload["response"]],
                    "target_ids": target_ids,
                }
                for d in payload["dimension_plan"]["dimensions"]
            ]
        }

    llm = FixtureLLM(config, overrides={"dimension_scorer_v1": scorer})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert attempts["n"] == 2
    assert all(score.target_ids for score in result.dimension_scores)


def test_all_external_insufficient_requires_dimension_abstention(setup):
    config, _, _, _ = setup
    retriever = FixtureRetriever(empty=True)
    attempts = {"n": 0}

    def scorer(payload):
        attempts["n"] += 1
        value = 2 if attempts["n"] == 1 else "abstain"
        return {
            "scores": [
                {
                    "dimension_id": d["dimension_id"],
                    "score": value,
                    "rationale": "Evidence unavailable.",
                    "response_quotes": [payload["response"]] if value != "abstain" else [],
                    "target_ids": [
                        t["target_id"] for t in payload["targets"] if d["dimension_id"] in t["dimension_ids"]
                    ],
                }
                for d in payload["dimension_plan"]["dimensions"]
            ]
        }

    llm = FixtureLLM(config, overrides={"dimension_scorer_v1": scorer})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert attempts["n"] == 2
    assert all(score.score == "abstain" for score in result.dimension_scores)
    assert result.overall_score is None
    assert result.candidate_abstained


def test_invalid_followup_output_keeps_current_memo(setup):
    config, _, _, _ = setup
    retriever = FixtureRetriever(empty=True)
    llm = FixtureLLM(
        config, overrides={"followup_v1": {"question": {"kind": "baseline", "text": "bad"}, "reason": "x"}}
    )
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert len(result.evidence[0].memos) == 1
    assert result.evidence[0].memos[-1].sufficiency == "insufficient"
    assert "Follow-up planning unavailable" in result.evidence[0].followup_reason
    assert result.verdicts[0].verdict == "insufficient"


def test_followup_memo_timeout_keeps_round_one_frozen_memo(setup):
    config, _, retriever, _ = setup
    memo_calls = {"n": 0}

    def memo_then_timeout(payload):
        memo_calls["n"] += 1
        if memo_calls["n"] > 1:
            raise requests.ReadTimeout("fixture timeout")
        supports = [{"quote": d["text"][:300]} for d in payload["documents"]]
        return {
            "answer": "Some grounded evidence exists, but it is not sufficient.",
            "scope": "The documented event",
            "variation": "More specific evidence would help.",
            "agreement": "Limited evidence",
            "sufficiency": "insufficient",
            "confidence": "low",
            "statements": [
                {
                    "text": "The organiser publishes arrangements.",
                    "kind": "context_sensitive_practice",
                    "supports": supports,
                }
            ],
        }

    llm = FixtureLLM(config, overrides={"evidence_memo_v1": memo_then_timeout})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)

    assert result.status == "completed"
    assert len(result.evidence) == 1
    bundle = result.evidence[0]
    assert len(bundle.memos) == 1
    assert bundle.memos[-1].sufficiency == "insufficient"
    assert len(bundle.questions) == 2
    assert len(bundle.queries) == 2
    assert len(bundle.snapshots) == 2
    assert "Follow-up evidence refinement unavailable" in bundle.followup_reason
    assert result.verdicts[0].verdict == "insufficient"
    assert result.candidate_abstained

    trace = RunTrace.model_validate_json(Path(result.trace_path).read_text())
    timeout_calls = [
        call
        for call in trace.calls
        if call.stage == "evidence_memo_v1" and call.error and "ReadTimeout" in call.error
    ]
    assert timeout_calls


def test_followup_receives_only_grounded_statement_level_memo(setup):
    config, _, _, _ = setup
    retriever = FixtureRetriever(empty=True)
    llm = FixtureLLM(config)
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    followup_call = next(call for call in llm.calls if call["stage"] == "followup_v1")
    assert set(followup_call["payload"]["memo"]) == {"sufficiency", "evidence_groups"}
    assert not {
        "answer",
        "scope",
        "variation",
        "agreement",
        "confidence",
        "citations",
        "memo_id",
        "statements",
    }.intersection(followup_call["payload"]["memo"])
    assert all(set(group) == {"supports"} for group in followup_call["payload"]["memo"]["evidence_groups"])


def test_duplicate_followup_is_skipped(setup):
    config, _, _, _ = setup
    retriever = FixtureRetriever(empty=True)

    def duplicate(payload):
        return {
            "question": {
                "kind": "followup",
                "text": payload["questions"][0]["text"],
            },
            "reason": "No distinct searchable gap beyond the existing baseline question.",
        }

    llm = FixtureLLM(config, overrides={"followup_v1": duplicate})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert len(result.evidence[0].questions) == 2
    assert len(retriever.calls) == 2
    assert len(result.evidence[0].memos) == 1


def test_followup_reason_is_bounded_and_prompt_is_concise():
    Followup(question=None, reason="Short reason.")
    with pytest.raises(ValidationError):
        Followup(question=None, reason="x" * 401)
    assert "1-2 concise sentences" in PROMPTS["followup_v1"]
    assert "must not repeat or paraphrase" in PROMPTS["followup_v1"]


def test_scope_and_query_prompts_prefer_general_then_authoritative():
    question_prompt = PROMPTS["verification_question_v1"]
    query_prompt = PROMPTS["query_rewriter_v1"]
    assert "broadest justified" in question_prompt
    assert "named city or region" in question_prompt
    assert "academic or linguistic" in query_prompt
    assert "official or institutional" in query_prompt
    assert "provenance_basis" in PROMPTS["source_classifier_v1"]
    assert "REQUIRE provenance_basis=explicit" in PROMPTS["source_classifier_v1"]
    assert "VERBATIM span" in PROMPTS["evidence_memo_v1"]
    assert "Do not return source references" in PROMPTS["evidence_memo_v1"]
    assert "ONLY for an actual binding law" in PROMPTS["evidence_memo_v1"]
    assert "supported_by_quotes" in PROMPTS["evidence_relevance_v1"]
    assert "materially" in PROMPTS["evidence_relevance_v1"]
    assert "supplied frozen" in PROMPTS["target_comparator_v1"]
    assert "support quotes" in PROMPTS["target_comparator_v1"]
    assert "genuinely unscorable only" in PROMPTS["dimension_scorer_v1"]
    assert "relevant retrievable target is insufficient" in PROMPTS["dimension_scorer_v1"]
    assert "Do not return memo IDs" in PROMPTS["dimension_scorer_v1"]


def test_max_two_rounds_one_followup(setup):
    config, _, _, _ = setup
    retriever = FixtureRetriever(empty=True)
    llm = FixtureLLM(config)
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert len(retriever.calls) == 3
    bundle = result.evidence[0]
    assert [q.round for q in bundle.queries] == [1, 1, 2]
    assert len(bundle.memos) == 2 and bundle.memos[-1].sufficiency == "insufficient"
    assert sum(c["stage"] == "followup_v1" for c in llm.calls) == 1
    assert result.evidence_coverage == 0
    assert result.verdicts[0].verdict == "insufficient"
    assert not any(c["stage"] == "target_comparator_v1" for c in llm.calls)


def test_memo_quotes_map_to_exact_document_ids(setup):
    _, llm, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    memo_call = next(c for c in llm.calls if c["stage"] == "evidence_memo_v1")
    assert all("document_id" not in d for d in memo_call["payload"]["documents"])

    memo = result.evidence[0].memos[-1]
    documents = {document.document_id: document for document in result.evidence[0].documents}
    assert set(memo.citations) <= set(documents)
    for statement in memo.statements:
        for support in statement.supports:
            assert support.document_id in documents
            assert support.quote in documents[support.document_id].text


def test_memo_citations_are_derived_from_statement_union(setup):
    _, _, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    memo = result.evidence[0].memos[-1]
    expected = tuple(dict.fromkeys(c for statement in memo.statements for c in statement.citations))
    assert memo.citations == expected


def test_memo_draft_rejects_more_than_five_statements():
    from cultverify.schemas import MemoDraft

    statement = {
        "text": "x",
        "kind": "context_sensitive_practice",
        "supports": [{"quote": "x"}],
    }
    with pytest.raises(ValidationError):
        MemoDraft(
            answer="x",
            scope="x",
            variation="x",
            agreement="x",
            sufficiency="sufficient",
            confidence="medium",
            statements=[statement] * 6,
        )


def test_citations_require_retrieved_document(setup):
    _, _, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    memo = result.evidence[0].memos[-1]
    with pytest.raises(ValueError):
        validate_document_citation(memo, ())
    bad = memo.model_copy(update={"citations": ("missing",)})
    with pytest.raises(ValueError):
        validate_document_citation(bad, result.evidence[0].documents)


def test_memo_deeply_immutable(setup):
    _, _, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    memo = result.evidence[0].memos[-1]
    before = digest(memo)
    with pytest.raises(ValidationError):
        memo.answer = "replacement"
    with pytest.raises(ValidationError):
        memo.statements[0].text = "replacement"
    assert digest(memo) == before
    trace = RunTrace.model_validate_json(Path(result.trace_path).read_text())
    assert trace.events[1].startswith("memo_frozen:")
    assert trace.events[2].startswith("target_compared:")


def score(value, dimension="D03"):
    return DimensionScore(
        dimension_id=dimension, score=value, rationale="fixture", response_quotes=(), target_ids=(), memo_ids=()
    )


def test_equal_aggregation_and_abstention():
    assert aggregate((score(2), score(1, "D01"), score("abstain", "D02"))) == 0.75
    assert aggregate((score("abstain"),)) is None
    assert aggregate(()) is None
    with pytest.raises(ValidationError):
        score(True)
    with pytest.raises(ValidationError):
        score(1.5)


def test_rank_shared_planning_and_exact_tie(setup):
    _, llm, _, verifier = setup
    result = verifier.rank(PROMPT, [RESPONSE, RESPONSE + " B", RESPONSE + " C", RESPONSE + " D"])
    assert all(c.status == "completed" for c in result.candidates)
    assert result.winner == "no_clear_winner" and result.tied_indices == (0, 1, 2, 3)
    assert sum(c["stage"] == "context_planner_v1" for c in llm.calls) == 1
    assert sum(c["stage"] == "dimension_planner_v1" for c in llm.calls) == 1
    assert all(c.context is result.candidates[0].context for c in result.candidates)
    assert all(c.dimension_plan is result.candidates[0].dimension_plan for c in result.candidates)


def test_ranking_with_failed_candidate_returns_no_clear_winner(setup):
    _, _, _, verifier = setup
    candidate = verifier.verify(PROMPT, RESPONSE)
    failed = candidate.model_copy(update={"status": "failed", "errors": ("fixture",)})
    ranking = rank_results([candidate, candidate, failed, candidate])
    assert ranking.winner == "no_clear_winner"
    assert ranking.tied_indices == ()
    assert ranking.coverage_comparable is False


def test_ranking_all_abstain_and_unique_winner(setup):
    _, _, _, verifier = setup
    candidate = verifier.verify(PROMPT, RESPONSE)
    abstained = candidate.model_copy(update={"dimension_scores": (score("abstain"),), "overall_score": None})
    assert rank_results([abstained] * 4).winner == "no_clear_winner"
    low = candidate.model_copy(update={"dimension_scores": (score(1),), "overall_score": 0.5})
    assert rank_results([low, candidate, low, low]).winner == 1
    assert rank_results([low, candidate, abstained, low]).coverage_comparable is False


def test_replay_no_live_calls_and_no_query_rewrite(setup):
    config, _, retriever, verifier = setup
    live = verifier.verify(PROMPT, RESPONSE)
    assert live.status == "completed"
    replay_config = config.model_copy(update={"mode": "REPLAY"})
    llm = FixtureLLM(replay_config, overrides={"query_rewriter_v1": AssertionError("Must reuse frozen queries")})
    with patch.object(retriever, "search", side_effect=AssertionError("No live retrieval")):
        replay = CulturalVerifier(llm=llm, retriever=retriever, config=replay_config).verify(PROMPT, RESPONSE)
    assert replay.status == "completed" and replay.overall_score == live.overall_score
    assert replay.evidence[0].snapshots == live.evidence[0].snapshots
    assert not any(c["stage"] == "query_rewriter_v1" for c in llm.calls)
    assert replay.evidence[0].memos == live.evidence[0].memos


def test_result_summary_invariants_are_trace_validated(setup):
    _, _, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    trace = RunTrace.model_validate_json(Path(result.trace_path).read_text())

    with pytest.raises(ValueError, match="Overall score mismatch"):
        validate_trace_links(trace.model_copy(update={"result": result.model_copy(update={"overall_score": 0.123})}))
    with pytest.raises(ValueError, match="Evidence coverage summary mismatch"):
        validate_trace_links(
            trace.model_copy(update={"result": result.model_copy(update={"evidence_coverage": 0.123})})
        )
    with pytest.raises(ValueError, match="Abstained dimension summary mismatch"):
        validate_trace_links(
            trace.model_copy(update={"result": result.model_copy(update={"abstained_dimensions": ("D01",)})})
        )


def test_trace_links_and_corruption(setup):
    _, _, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    trace = RunTrace.model_validate_json(Path(result.trace_path).read_text())
    validate_trace_links(trace)
    link = trace.target_evidence_links[0].model_copy(update={"memo_id": "missing"})
    with pytest.raises(ValueError):
        validate_trace_links(trace.model_copy(update={"target_evidence_links": (link,)}))


def test_second_invalid_scoring_returns_failure(setup):
    config, _, retriever, _ = setup
    llm = FixtureLLM(config, overrides={"dimension_scorer_v1": {"scores": []}})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.candidate_abstained and result.status == "failed"
    assert sum(c["stage"] == "dimension_scorer_v1" for c in llm.calls) == 2
    assert result.evidence and result.errors


def test_no_dimensions_no_search(setup):
    config, _, retriever, _ = setup
    llm = FixtureLLM(config, overrides={"dimension_planner_v1": {"dimensions": [], "reasoning": "None applicable"}})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed" and result.candidate_abstained and result.applicable_count == 0
    assert not retriever.calls


def test_internal_targets_no_external_search(setup):
    config, _, retriever, _ = setup
    target = dict(
        response_quote=RESPONSE,
        proposition="x",
        epistemic_type="response_internal_quality",
        dimension_ids=["D03"],
        materiality="x",
        retrieval_appropriate=False,
    )
    llm = FixtureLLM(config, overrides={"target_extractor_v1": {"targets": [target]}})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed" and not retriever.calls
    assert result.evidence_coverage is None and not result.verdicts


def test_unknown_metadata_rejected_at_public_api(setup):
    _, _, _, verifier = setup
    with pytest.raises(TypeError):
        verifier.verify(PROMPT, RESPONSE, human_chosen="a")


def test_no_python_score_override_on_contradiction(setup):
    config, _, retriever, _ = setup

    def contradicted(payload):
        return {
            "target_id": payload["target"]["target_id"],
            "memo_id": payload["memo"]["memo_id"],
            "verdict": "contradicted",
            "reasoning": "Contradicted fixture",
        }

    llm = FixtureLLM(config, overrides={"target_comparator_v1": contradicted})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    # Deliberately inconsistent semantics: structural code must not invent a score cap.
    assert result.status == "completed" and result.overall_score == 1


def test_score_memo_links_are_derived_from_target_ids(setup):
    config, _, retriever, _ = setup

    def scorer(payload):
        target_id = payload["targets"][0]["target_id"]
        return {
            "scores": [
                {
                    "dimension_id": "D03",
                    "score": 2,
                    "rationale": "x",
                    "response_quotes": [RESPONSE],
                    "target_ids": [target_id],
                }
            ]
        }

    llm = FixtureLLM(config, overrides={"dimension_scorer_v1": scorer})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    score_result = result.dimension_scores[0]
    verdict_by_target = {verdict.target_id: verdict for verdict in result.verdicts}
    assert score_result.memo_ids == tuple(verdict_by_target[target_id].memo_id for target_id in score_result.target_ids)
    scorer_call = next(call for call in llm.calls if call["stage"] == "dimension_scorer_v1")
    assert "memo_ids" not in scorer_call["schema"]


def test_ungrounded_support_cannot_reach_target_comparison(setup):
    config, _, retriever, _ = setup
    llm = FixtureLLM(
        config,
        overrides={
            "evidence_memo_v1": {
                "answer": "Unsupported fact",
                "scope": "x",
                "variation": "x",
                "agreement": "x",
                "sufficiency": "sufficient",
                "confidence": "high",
                "statements": [
                    {
                        "text": "Unsupported fact",
                        "kind": "context_sensitive_practice",
                        "supports": [{"quote": "not present in any supplied document"}],
                    }
                ],
            }
        },
    )
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert result.verdicts[0].verdict == "insufficient"
    assert not any(c["stage"] == "target_comparator_v1" for c in llm.calls)


def test_citation_trace_score_reference_validation(setup):
    _, _, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    trace = RunTrace.model_validate_json(Path(result.trace_path).read_text())
    bad_score = result.dimension_scores[0].model_copy(update={"memo_ids": ("missing",)})
    with pytest.raises(ValueError):
        validate_trace_links(
            trace.model_copy(update={"result": result.model_copy(update={"dimension_scores": (bad_score,)})})
        )


def test_conflicting_final_memo_counts_as_evidence_coverage(setup):
    config, _, retriever, _ = setup

    def conflicting(payload):
        supports = [{"quote": d["text"][:300]} for d in payload["documents"]]
        return {
            "answer": "The retrieved sources do not resolve the question consistently.",
            "scope": "The documented context",
            "variation": "Relevant sources differ.",
            "agreement": "Conflicting evidence",
            "sufficiency": "conflicting",
            "confidence": "medium",
            "statements": [
                {
                    "text": "The retrieved sources do not resolve the question consistently.",
                    "kind": "context_sensitive_practice",
                    "supports": supports,
                }
            ],
        }

    llm = FixtureLLM(config, overrides={"evidence_memo_v1": conflicting})
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert result.evidence[0].memos[-1].sufficiency == "conflicting"
    assert result.evidence_coverage == 1


def test_insufficient_memo_cannot_produce_directional_verdict(setup):
    config, _, _, _ = setup
    retriever = FixtureRetriever(empty=True)
    llm = FixtureLLM(
        config,
        overrides={"target_comparator_v1": AssertionError("Comparator must not run on insufficient evidence")},
    )
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "completed"
    assert result.verdicts[0].verdict == "insufficient"
    assert result.evidence[0].memos[-1].sufficiency == "insufficient"
