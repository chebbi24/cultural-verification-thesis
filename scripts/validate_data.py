#!/usr/bin/env python3
"""Validate canonical IDs, foreign keys, balance, lineage, splits, and provenance."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cultural_verifier.ids import (
    ATTACK_RE,
    CANDIDATE_RE,
    DOMAIN_RE,
    LEGACY_PROMPT_RE,
    PILOT_SET_RE,
    PROMPT_RE,
    SUBDIMENSION_RE,
)
from cultural_verifier.io import read_csv


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def unique(rows: list[dict[str, str]], field: str) -> set[str]:
    values = [row[field] for row in rows]
    require(len(values) == len(set(values)), f"Duplicate {field}")
    return set(values)


def main() -> None:
    domains = read_csv(REPO_ROOT / "data/taxonomy/domains.csv")
    subdimensions = read_csv(REPO_ROOT / "data/taxonomy/subdimensions.csv")
    attacks = read_csv(REPO_ROOT / "data/taxonomy/attacks.csv")
    issues = read_csv(REPO_ROOT / "data/taxonomy/issues.csv")
    legacy_crosswalk = read_csv(REPO_ROOT / "data/taxonomy/legacy_v1_crosswalk.csv")
    prompts = read_csv(REPO_ROOT / "data/benchmark/prompts.csv")
    lineage = read_csv(REPO_ROOT / "data/benchmark/lineage.csv")
    splits = read_csv(REPO_ROOT / "data/benchmark/splits.csv")
    claims = read_csv(REPO_ROOT / "data/evidence/reference_claims.csv")
    candidates = read_csv(REPO_ROOT / "data/pilot/candidates.csv")
    annotations = read_csv(REPO_ROOT / "data/pilot/provisional_annotations.csv")

    domain_ids = unique(domains, "domain_id")
    subdimension_ids = unique(subdimensions, "subdimension_id")
    attack_ids = unique(attacks, "attack_id")
    prompt_ids = unique(prompts, "prompt_id")
    issue_ids = unique(issues, "issue_id")
    require(len(legacy_crosswalk) == 19, "Expected 19 legacy taxonomy mappings")
    require(
        unique(legacy_crosswalk, "legacy_taxonomy_id") == {f"T{index}" for index in range(1, 20)},
        "Legacy taxonomy crosswalk coverage mismatch",
    )
    require(
        all(row["canonical_issue_id"] in issue_ids for row in legacy_crosswalk),
        "Legacy taxonomy crosswalk references unknown issue",
    )
    require(
        all(len(row["source_file_sha256"]) == 64 for row in legacy_crosswalk),
        "Legacy taxonomy source hash is missing",
    )
    require(len(domain_ids) == 10, "Expected 10 domains")
    require(len(subdimension_ids) == 30, "Expected 30 subdimensions")
    require(len(attack_ids) == 10, "Expected 10 attacks")
    require(len(prompt_ids) == 300, "Expected 300 prompts")
    require(all(DOMAIN_RE.fullmatch(value) for value in domain_ids), "Invalid domain ID")
    require(all(SUBDIMENSION_RE.fullmatch(value) for value in subdimension_ids), "Invalid subdimension ID")
    require(all(ATTACK_RE.fullmatch(value) for value in attack_ids), "Invalid attack ID")
    require(all(PROMPT_RE.fullmatch(value) for value in prompt_ids), "Invalid prompt ID")

    require(
        all(row["domain_id"] in domain_ids for row in subdimensions),
        "Subdimension references unknown domain",
    )
    require(all(row["domain_id"] in domain_ids for row in prompts), "Prompt references unknown domain")
    require(
        all(row["subdimension_id"] in subdimension_ids for row in prompts),
        "Prompt references unknown subdimension",
    )
    require(all(row["attack_id"] in attack_ids for row in prompts), "Prompt references unknown attack")

    require(Counter(row["domain_id"] for row in prompts) == {value: 30 for value in domain_ids}, "Domain imbalance")
    require(
        Counter(row["subdimension_id"] for row in prompts) == {value: 10 for value in subdimension_ids},
        "Subdimension imbalance",
    )
    require(Counter(row["attack_id"] for row in prompts) == {value: 30 for value in attack_ids}, "Attack imbalance")

    require(unique(lineage, "prompt_id") == prompt_ids, "Lineage coverage mismatch")
    require(all(row["lineage_group_id"] == row["prompt_id"] for row in lineage), "Unexpected lineage grouping")
    require(all(not row["parent_prompt_id"] for row in lineage), "Final RT items must not point to obsolete parents")
    require(all(len(row["source_row_sha256"]) == 64 for row in lineage), "Missing lineage hash")

    require(unique(splits, "prompt_id") == prompt_ids, "Split coverage mismatch")
    split_counts = Counter(row["split"] for row in splits)
    require(split_counts == {"development": 60, "verifier_validation": 60, "test": 180}, "Wrong split sizes")
    split_by_prompt = {row["prompt_id"]: row["split"] for row in splits}
    prompt_by_id = {row["prompt_id"]: row for row in prompts}
    for split, expected in [("development", 6), ("verifier_validation", 6), ("test", 18)]:
        counts = Counter(
            prompt_by_id[prompt_id]["attack_id"]
            for prompt_id, assigned in split_by_prompt.items()
            if assigned == split
        )
        require(counts == {value: expected for value in attack_ids}, f"Attack imbalance in {split}")

    require(unique(claims, "reference_claim_id") == {f"{value}-CL01" for value in prompt_ids}, "Reference-claim coverage mismatch")
    require(all(row["evidence_status"] == "pending_agentic_search" for row in claims), "Unexpected evidence provenance")

    require(len(candidates) == 120, "Expected 120 pilot candidates")
    require(all(PILOT_SET_RE.fullmatch(row["set_id"]) for row in candidates), "Invalid pilot set ID")
    require(all(LEGACY_PROMPT_RE.fullmatch(row["legacy_prompt_id"]) for row in candidates), "Invalid legacy prompt ID")
    require(all(CANDIDATE_RE.fullmatch(row["candidate_id"]) for row in candidates), "Invalid candidate ID")
    by_set: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        by_set[row["set_id"]].append(row)
    require(len(by_set) == 30 and all(len(rows) == 4 for rows in by_set.values()), "Pilot is not 30x4")

    require(len(annotations) == 30, "Expected 30 provisional annotations")
    require(all(row["label_source"] == "synthetic_model_provisional" for row in annotations), "Label provenance is not explicit")
    require(all(row["review_status"] == "requires_human_verification" for row in annotations), "Synthetic labels must require review")
    require(Counter(row["acceptable_set"] for row in annotations) == {"true": 26, "false": 4}, "Unexpected pilot acceptability count")
    require(all(row["preferred_candidate_id"] in {candidate["candidate_id"] for candidate in candidates} for row in annotations if row["preferred_candidate_id"]), "Annotation references unknown candidate")

    search_source = (REPO_ROOT / "src/cultural_verifier/search.py").read_text(encoding="utf-8")
    require("allowed_domains" not in search_source and "site:" not in search_source, "Retrieval contains a forbidden domain allowlist or site filter")

    print("All canonical data checks passed")
    print(f"prompts={len(prompts)} claims={len(claims)} pilot_candidates={len(candidates)}")
    print(f"splits={dict(split_counts)} provisional_acceptable=26 provisional_regenerate=4")


if __name__ == "__main__":
    main()
