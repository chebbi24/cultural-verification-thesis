import json
from pathlib import Path

import pytest

from scripts.preflight_final_experiment import find_ollama_model, tags_url
from scripts.run_final_experiment import (
    EXPECTED_PROMPT_IDS,
    load_completed,
    read_rows,
    sha256_file,
    verify_evidence_manifest,
    winner_label,
)

ROOT = Path(__file__).resolve().parents[1]


def test_final_runner_accepts_only_canonical_plts():
    rows = read_rows(ROOT / "data" / "evaluation" / "best_of4_v1.csv")
    assert tuple(row["prompt_id"] for row in rows) == EXPECTED_PROMPT_IDS
    assert len(rows) == 30


def test_final_runner_winner_labels_cover_selective_outcomes():
    assert [winner_label(i) for i in range(4)] == list("ABCD")
    for outcome in ("no_clear_winner", "no_acceptable_candidate", "insufficient_evidence"):
        assert winner_label(outcome) == outcome
    with pytest.raises(ValueError):
        winner_label(4)


def test_final_runner_resume_only_skips_completed_matching_mode(tmp_path):
    output = tmp_path / "results.jsonl"
    records = [
        {"mode": "LIVE", "status": "completed", "prompt_id": "PLT001"},
        {"mode": "LIVE", "status": "failed", "prompt_id": "PLT002"},
        {"mode": "REPLAY", "status": "completed", "prompt_id": "PLT003"},
    ]
    output.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    assert load_completed(output, "LIVE") == {"PLT001"}
    assert load_completed(output, "REPLAY") == {"PLT003"}


def test_replay_evidence_manifest_detects_mutation(tmp_path):
    evidence = tmp_path / "snapshot.json"
    evidence.write_text('{"frozen": true}\n', encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"evidence_files": [{"path": str(evidence), "sha256": sha256_file(evidence)}]}),
        encoding="utf-8",
    )
    verify_evidence_manifest(manifest)
    evidence.write_text('{"frozen": false}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="Frozen evidence changed"):
        verify_evidence_manifest(manifest)


def test_preflight_resolves_ollama_registry_and_frozen_model():
    assert tags_url("http://localhost:11434/api/chat") == "http://localhost:11434/api/tags"
    model = find_ollama_model(
        [{"name": "qwen3:4b", "digest": "abc"}, {"name": "other:latest", "digest": "def"}],
        "qwen3:4b",
    )
    assert model["digest"] == "abc"
    with pytest.raises(RuntimeError, match="not installed"):
        find_ollama_model([], "qwen3:4b")
