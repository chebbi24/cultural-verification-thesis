import json

import pytest

from scripts.run_final_baselines import (
    DIRECT_PROMPT,
    baseline_protocol_hash,
    direct_decision,
    evaluate_one,
    load_baseline_completed,
)


@pytest.fixture
def row():
    return {
        "corpus": "plt120",
        "item_id": "PLT001",
        "prompt": "Sample cultural invitation?",
        "response": "A sample culturally respectful invitation.",
        "prompt_sha256": "prompt-verified",
        "response_sha256": "response-verified",
    }


class FakeJudge:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        next_answer = next(self.answers)
        if isinstance(next_answer, Exception):
            raise next_answer
        return json.dumps(next_answer)


class FakeReward:
    def __init__(self, score):
        self.value = score
        self.calls = []

    def score(self, prompt, response):
        self.calls.append((prompt, response))
        return self.value


def test_direct_judge_uses_only_frozen_prompt_response_and_rubric(row):
    judge = FakeJudge([{"label": "culturally_appropriate", "rationale": "Respects regional context."}])
    decision = direct_decision(judge, row, ["D01"])
    assert decision["judge_label"] == "culturally_appropriate"
    assert len(judge.calls) == 1
    call = judge.calls[0]
    assert call["stage"] == "direct_single_response_judge_v1"
    assert call["system"] == DIRECT_PROMPT
    assert call["payload"] == {"prompt": row["prompt"], "response": row["response"], "rubric": ["D01"]}
    assert "evidence" not in json.dumps(call["payload"])
    assert "insufficient_evidence" in str(call["schema"])


def test_direct_judge_retries_invalid_label_without_fabricating_a_verdict(row):
    judge = FakeJudge(
        [
            {"label": "probably_ok", "rationale": "Invalid outcome"},
            {"label": "not_assessable", "rationale": "Pure refusal"},
        ]
    )
    assert direct_decision(judge, row, ["D01"])["judge_label"] == "not_assessable"
    assert len(judge.calls) == 2
    invalid = FakeJudge([{"label": "maybe", "rationale": "No"}, {"label": "maybe", "rationale": "No"}])
    record = evaluate_one(row, "direct-judge", invalid, "freeze", "hash", rubric=["D01"])
    assert record["status"] == "failed"
    assert "judge_label" not in record


def test_single_reward_model_score_is_raw_and_never_a_label(row):
    model = FakeReward(-2.5)
    record = evaluate_one(row, "reward-model", model, "freeze", "hash")
    assert record["status"] == "completed"
    assert record["rm_raw_score"] == -2.5
    assert "judge_label" not in record
    assert model.calls == [(row["prompt"], row["response"])]


def test_invalid_reward_score_fails_individually(row):
    record = evaluate_one(row, "reward-model", FakeReward(float("nan")), "freeze", "hash")
    assert record["status"] == "failed"
    assert "rm_raw_score" not in record
    assert record["errors"] == ["baseline:ValueError"]


def test_direct_judge_error_is_isolated_for_resume(row):
    judge = FakeJudge([RuntimeError("Provider unavailable")])
    record = evaluate_one(row, "direct-judge", judge, "freeze", "hash", rubric=["D01"])
    assert record["status"] == "failed"
    assert record["errors"] == ["baseline:RuntimeError"]


def test_baseline_resume_requires_matching_freeze_protocol_and_hashes(tmp_path, row):
    output = tmp_path / "baseline.jsonl"
    record = evaluate_one(row, "reward-model", FakeReward(1.25), "freeze-abc", "protocol-abc")
    output.write_text(json.dumps(record) + "\n")
    rows = [row]
    assert load_baseline_completed(output, "reward-model", "freeze-abc", "protocol-abc", rows) == {"PLT001"}
    assert load_baseline_completed(output, "reward-model", "freeze-other", "protocol-abc", rows) == set()
    assert load_baseline_completed(output, "reward-model", "freeze-abc", "protocol-other", rows) == set()
    assert load_baseline_completed(
        output, "reward-model", "freeze-abc", "protocol-abc", [{**row, "response_sha256": "changed"}]
    ) == set()
    output.write_text(output.read_text() + json.dumps({**record, "status": "failed"}) + "\n")
    assert load_baseline_completed(output, "reward-model", "freeze-abc", "protocol-abc", rows) == set()


def test_independent_baseline_protocol_hashes_are_distinct():
    rm_a = baseline_protocol_hash("reward-model", "Skywork/Model", "revision-a")
    rm_b = baseline_protocol_hash("reward-model", "Skywork/Model", "revision-b")
    direct = baseline_protocol_hash("direct-judge", "vllm/qwen3.6:35b-a3b-fp8")
    assert rm_a != rm_b != direct
