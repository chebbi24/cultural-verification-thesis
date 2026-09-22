import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "cultverify"

FORBIDDEN_LEGACY_IDENTIFIERS = (
    "_CONVERSATIONAL_MARKERS",
    "_VAGUE_HOSTING_MARKERS",
    "_MATERIAL_ACTION_MARKERS",
    "_STRONG_FACTUAL_ASSERTION_MARKERS",
    "_CONTEXT_HINTS",
    "_EVIDENCE_QUERY_TERMS",
    "_COUNTEREVIDENCE_MARKERS",
    "constraint_evidence_terms",
    "material_accommodation_gaps",
    "verifier_v7",
    "verifier_v8",
)


def test_active_verifier_contains_no_legacy_cultural_heuristic_identifiers():
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(PACKAGE.rglob("*.py")))
    for identifier in FORBIDDEN_LEGACY_IDENTIFIERS:
        assert identifier not in source


def test_active_verifier_does_not_load_human_gold_or_evaluation_artifacts():
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in sorted(PACKAGE.rglob("*.py")))
    assert "human_gold" not in source
    assert "data/evaluation" not in source
    assert "majority_winner" not in source
    assert "winner_votes" not in source


def test_smoke_cases_are_unlabelled_and_outside_gold_set():
    cases = json.loads((ROOT / "data" / "dev" / "verifier_smoke_cases.json").read_text(encoding="utf-8"))
    assert len(cases) == 10
    assert len({case["case_id"] for case in cases}) == 10
    for case in cases:
        assert set(case) == {"case_id", "prompt", "response"}
        assert case["case_id"].startswith("SMK") and not case["case_id"].startswith("PLT")
        assert case["prompt"].strip() and case["response"].strip()
