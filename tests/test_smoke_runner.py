import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_smoke_cases import load_cases, run_cases


class FakeVerifier:
    def __init__(self):
        self.calls = []

    def verify(self, *, prompt, response):
        self.calls.append((prompt, response))
        return SimpleNamespace(
            status="completed",
            overall_score=0.5,
            candidate_abstained=False,
            evidence_coverage=1.0,
            applicable_count=1,
            scored_count=1,
            targets=(object(),),
            targets_truncated=False,
            trace_path="/tmp/trace.json",
            errors=(),
        )


def test_smoke_cases_are_unlabeled_and_non_gold():
    cases = load_cases(Path("data/dev/verifier_smoke_cases.json"))
    assert len(cases) == 10
    assert [case["case_id"] for case in cases] == [f"SMK{i:03d}" for i in range(1, 11)]
    for case in cases:
        assert set(case) == {"case_id", "prompt", "response"}
        assert "PLT" not in case["prompt"]
        assert "PLT" not in case["response"]


def test_smoke_runner_writes_summary_without_labels(tmp_path):
    cases = load_cases(Path("data/dev/verifier_smoke_cases.json"))[:2]
    verifier = FakeVerifier()
    rows = run_cases(cases, verifier, tmp_path)
    assert len(rows) == 2
    assert len(verifier.calls) == 2

    result_path = tmp_path / "smoke_results.csv"
    manifest_path = tmp_path / "smoke_manifest.json"
    assert result_path.exists() and manifest_path.exists()

    with result_path.open(encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert [row["case_id"] for row in written] == ["SMK001", "SMK002"]
    forbidden_columns = {"label", "winner", "expected_score", "human_score", "gold_label"}
    assert not forbidden_columns.intersection(written[0])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "smoke-results-v1"
    assert manifest["n_cases"] == 2
    assert manifest["n_failed"] == 0


@pytest.mark.parametrize(
    "bad_case",
    [
        {"case_id": "PLT001", "prompt": "x", "response": "y"},
        {"case_id": "SMK999", "prompt": "PLT001", "response": "y"},
        {"case_id": "SMK999", "prompt": "x", "response": "y", "expected_score": 1.0},
        {"case_id": "SMK999", "prompt": "x", "response": "y", "winner": "A"},
    ],
)
def test_smoke_case_validation_rejects_gold_or_expected_outputs(tmp_path, bad_case):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([bad_case]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(path)
