import csv
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "evaluation" / "human_annotations_raw.xlsx"
FROZEN = ROOT / "data" / "evaluation"
SCRIPT = ROOT / "scripts" / "build_human_gold.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_human_gold", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_human_gold_rebuild_is_byte_identical(tmp_path):
    builder = _load_builder()
    result = builder.build(RAW, tmp_path)

    for name in (
        "human_gold_candidates.csv",
        "human_gold_prompts.csv",
        "human_gold_summary.json",
        "human_gold_manifest.json",
    ):
        assert (tmp_path / name).read_bytes() == (FROZEN / name).read_bytes()

    assert result["n_annotators"] == 5
    assert result["n_prompts"] == 30
    assert result["n_candidate_responses"] == 120
    assert result["n_candidate_ratings"] == 600
    assert result["n_winner_votes"] == 150
    assert result["winner_fleiss_kappa"] == pytest.approx(0.090494, abs=1e-6)
    assert result["consensus"] == {"ambiguous": 13, "majority": 10, "strong_consensus": 7}


def test_candidate_and_prompt_gold_have_expected_shape():
    with (FROZEN / "human_gold_candidates.csv").open(encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    with (FROZEN / "human_gold_prompts.csv").open(encoding="utf-8", newline="") as handle:
        prompts = list(csv.DictReader(handle))

    assert len(candidates) == 120
    assert len(prompts) == 30
    assert {(row["prompt_id"], row["candidate_id"]) for row in candidates} == {
        (f"PLT{i:03d}", candidate) for i in range(1, 31) for candidate in "ABCD"
    }
    assert {row["prompt_id"] for row in prompts} == {f"PLT{i:03d}" for i in range(1, 31)}
    assert all(0.0 <= float(row["human_score_normalized"]) <= 1.0 for row in candidates)
    assert all(
        int(row["A_votes"]) + int(row["B_votes"]) + int(row["C_votes"]) + int(row["D_votes"]) == 5 for row in prompts
    )


def test_manifest_hashes_match_frozen_files():
    builder = _load_builder()
    manifest = json.loads((FROZEN / "human_gold_manifest.json").read_text(encoding="utf-8"))
    assert manifest["freeze_version"] == "human-gold-v1"
    assert manifest["source_sha256"] == builder.sha256_file(RAW)
    for name, expected_hash in manifest["derived"].items():
        assert builder.sha256_file(FROZEN / name) == expected_hash
