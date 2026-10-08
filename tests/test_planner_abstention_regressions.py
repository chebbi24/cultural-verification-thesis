"""Regressions found in PLT001-PLT003 final LIVE smoke inspection.

These tests use no model API, retrieval, or human labels.
"""
import pytest

from cultverify.llm import SemanticSession, StageError
from cultverify.planner import plan_prompt
from cultverify.schemas import (
    ContextFrame, CulturalApplicability, DimensionApplicability,
    DimensionPlan, DimensionScore,
)
from cultverify.scoring import cultural_appropriateness, vericult_score


def _score(dimension_id, value):
    return DimensionScore(
        dimension_id=dimension_id,
        score=value,
        rationale="Regression fixture",
        response_quotes=() if value == "abstain" else ("response",),
        target_ids=(),
        memo_ids=(),
    )


def test_unresolved_dimension_does_not_create_partial_quality_label():
    scores = (_score("D01", 2), _score("D08", "abstain"))
    assert cultural_appropriateness(scores) == "insufficient_evidence"
    assert vericult_score(scores) is None


def test_partial_requires_observed_partial_score_and_complete_coverage():
    assert cultural_appropriateness((_score("D01", 2), _score("D08", 1))) == "partially_culturally_appropriate"
    assert cultural_appropriateness((_score("D01", 2), _score("D08", 2))) == "culturally_appropriate"
    assert cultural_appropriateness((_score("D01", 0), _score("D08", "abstain"))) == "culturally_inappropriate"


class PlannedSession:
    def __init__(self, plans):
        self.plans = iter(plans)
        self.attempts = 0

    def call(self, stage, payload, output_type, validator=None):
        if stage == "context_planner_v1":
            return ContextFrame()
        if stage == "cultural_applicability_v1":
            return CulturalApplicability(applicable=True, reason="Material cultural context")
        assert stage == "dimension_planner_v1"
        self.attempts += 1
        value = next(self.plans)
        if validator:
            validator(value)
        return value


def test_applicable_prompt_rejects_empty_dimensions():
    empty = DimensionPlan(dimensions=(), reasoning="D02 primary and D03 secondary")
    session = PlannedSession([empty])
    with pytest.raises(ValueError, match="applicable=true"):
        plan_prompt(session, "Cultural question", [])
    assert session.attempts == 1


def test_applicable_prompt_keeps_valid_dimensions():
    valid = DimensionPlan(
        dimensions=(DimensionApplicability(dimension_id="D02", role="primary", reason="Relevant pragmatics"),),
        reasoning="Cultural pragmatics affect judgment",
    )
    session = PlannedSession([valid])
    _, plan = plan_prompt(session, "Cultural question", [])
    assert plan.dimensions[0].dimension_id == "D02"


class ScriptedLLM:
    def __init__(self, config, sequence):
        self.config = config
        self.sequence = iter(sequence)
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        return next(self.sequence)


def test_semantic_session_retries_contradictory_plan():
    from cultverify.config import Config
    config = Config(verifier_model_id="test", retry_count=1)
    empty = '{"dimensions":[],"reasoning":"D02 primary"}'
    valid = '{"dimensions":[{"dimension_id":"D02","role":"primary","reason":"Cultural pragmatics"}],"reasoning":"D02"}'
    llm = ScriptedLLM(config, [empty, valid])
    session = SemanticSession(llm, config)

    def require_nonempty(plan):
        if not plan.dimensions:
            raise ValueError("applicable=true requires dimensions")

    result = session.call("dimension_planner_v1", {}, DimensionPlan, require_nonempty)
    assert len(result.dimensions) == 1
    assert llm.calls == 2
    assert session.calls[0].error == "ValueError"


def test_semantic_session_fails_closed_after_invalid_retry():
    from cultverify.config import Config
    config = Config(verifier_model_id="test", retry_count=1)
    llm = ScriptedLLM(config, ['{"dimensions":[],"reasoning":"D02"}'] * 2)
    session = SemanticSession(llm, config)
    with pytest.raises(StageError, match="invalid output after bounded retry"):
        session.call(
            "dimension_planner_v1", {}, DimensionPlan,
            lambda plan: (_ for _ in ()).throw(ValueError("empty dimensions")) if not plan.dimensions else None,
        )


def test_timeout_retries_then_succeeds_without_semantic_repair():
    import requests
    from cultverify.config import Config
    config = Config(verifier_model_id="test", retry_count=1, transport_retry_count=1)
    llm = ScriptedLLM(config, [
        requests.Timeout("simulated provider timeout"),
        '{"dimensions":[{"dimension_id":"D02","role":"primary","reason":"Relevant"}],"reasoning":"Material"}',
    ])
    original_complete = llm.complete

    def complete(**kwargs):
        outcome = next(llm.sequence)
        llm.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    llm.complete = complete
    session = SemanticSession(llm, config)
    result = session.call("dimension_planner_v1", {}, DimensionPlan)
    assert result.dimensions[0].dimension_id == "D02"
    assert llm.calls == 2
    assert session.calls[0].error == "Timeout"


def test_exhausted_transport_timeouts_remain_technical_failures():
    import requests
    from cultverify.config import Config
    config = Config(verifier_model_id="test", transport_retry_count=1)
    llm = ScriptedLLM(config, [requests.Timeout("simulated")] * 2)

    def complete(**kwargs):
        llm.calls += 1
        raise next(llm.sequence)

    llm.complete = complete
    session = SemanticSession(llm, config)
    with pytest.raises(StageError, match="dimension_planner_v1: transport Timeout"):
        session.call("dimension_planner_v1", {}, DimensionPlan)
    assert len(session.calls) == 2
    assert all(call.error == "Timeout" for call in session.calls)
