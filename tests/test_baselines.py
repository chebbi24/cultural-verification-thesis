import pytest
from pydantic import ValidationError

from baseline_direct_judge import DEFAULT_MODEL, JudgeDecision, decision_schema, rubric_text
from baseline_rm import DEFAULT_RM, select_unique_winner


def test_skywork_model_is_frozen():
    assert DEFAULT_RM == "Skywork/Skywork-Reward-V2-Qwen3-4B"


def test_skywork_unique_winner_and_exact_tie():
    assert select_unique_winner({"a": 0.1, "b": 0.7, "c": 0.2, "d": 0.3}) == "b"
    assert select_unique_winner({"a": 0.7, "b": 0.7, "c": 0.2, "d": 0.3}) == "no_clear_winner"


def test_skywork_requires_best_of_four():
    with pytest.raises(ValueError):
        select_unique_winner({"a": 1.0, "b": 0.0})


def test_direct_judge_model_and_schema_are_frozen():
    assert DEFAULT_MODEL == "qwen3:4b"
    assert decision_schema()["properties"]["winner"]["enum"] == ["A", "B", "C", "D", "no_clear_winner"]


def test_direct_judge_uses_exact_d01_d10_rubric():
    rubric = rubric_text()
    for index in range(1, 11):
        assert f"D{index:02}" in rubric


def test_direct_judge_rejects_extra_fields():
    with pytest.raises(ValidationError):
        JudgeDecision(winner="A", reasoning="fixture", extra_field="not allowed")
