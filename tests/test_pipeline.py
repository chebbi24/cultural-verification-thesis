import inspect
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from pydantic import ValidationError
from cultverify import CulturalVerifier
from cultverify.evidence import BlindEvidenceEngine
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
from cultverify.scoring import aggregate, compare_target, rank_results
from cultverify.trace import digest
from cultverify.validation import validate_context, validate_document_citation, validate_trace_links
from conftest import FixtureLLM, FixtureRetriever, PROMPT, RESPONSE


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


def test_target_limit_and_internal_type():
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
    blind_stages = {"query_rewriter_v1", "source_classifier_v1", "evidence_memo_v1", "followup_v1"}
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


def test_followup_reason_is_bounded_and_prompt_is_concise():
    Followup(question=None, reason="Short reason.")
    with pytest.raises(ValidationError):
        Followup(question=None, reason="x" * 401)
    assert "1-2 concise sentences" in PROMPTS["followup_v1"]


def test_scope_and_query_prompts_prefer_general_then_authoritative():
    question_prompt = PROMPTS["verification_question_v1"]
    query_prompt = PROMPTS["query_rewriter_v1"]
    assert "broadest justified" in question_prompt
    assert "named city or region" in question_prompt
    assert "academic or linguistic" in query_prompt
    assert "official or institutional" in query_prompt


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


def test_broken_score_memo_links_retry_then_abstain(setup):
    config, _, retriever, _ = setup
    llm = FixtureLLM(
        config,
        overrides={
            "dimension_scorer_v1": {
                "scores": [
                    {
                        "dimension_id": "D03",
                        "score": 2,
                        "rationale": "x",
                        "response_quotes": [RESPONSE],
                        "target_ids": [],
                        "memo_ids": ["invented"],
                    }
                ]
            }
        },
    )
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "failed" and result.candidate_abstained
    assert sum(c["stage"] == "dimension_scorer_v1" for c in llm.calls) == 2


def test_missing_citations_fail_before_target_comparison(setup):
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
                "statements": [],
                "citations": [],
            }
        },
    )
    result = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "failed" and not result.verdicts
    trace = RunTrace.model_validate_json(Path(result.trace_path).read_text())
    assert trace.partial_evidence_json and "snapshots" in trace.partial_evidence_json
    assert sum(c.stage == "evidence_memo_v1" for c in trace.calls) == 2


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
        ids = [d["document_id"] for d in payload["documents"]]
        return {
            "answer": "The retrieved sources do not resolve the question consistently.",
            "scope": "The documented context",
            "variation": "Relevant sources differ.",
            "agreement": "Conflicting evidence",
            "sufficiency": "conflicting",
            "confidence": "medium",
            "citations": ids,
            "statements": [
                {
                    "text": "The retrieved sources do not resolve the question consistently.",
                    "kind": "context_sensitive_practice",
                    "citations": ids,
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
