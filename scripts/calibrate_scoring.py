#!/usr/bin/env python3
"""Select verifier-fusion parameters using final human development labels only."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cultural_verifier.io import read_csv, write_json
from cultural_verifier.scoring import (
    EvidenceAggregate,
    ScoringConfig,
    hybrid_probabilities,
    verifier_score,
)


def comma_floats(value: str) -> list[float]:
    values = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("provide at least one comma-separated number")
    return values


def require_final_human_development_labels(rows: list[dict[str, str]]) -> dict[str, str]:
    """Return set-to-winner labels after enforcing the anti-leakage contract."""
    required = {"set_id", "human_choice_candidate_id", "split", "label_source", "review_status"}
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise ValueError(f"Labels are missing columns: {', '.join(sorted(missing))}")

    labels: dict[str, str] = {}
    forbidden_provenance = ("synthetic", "model", "provisional", "pseudo")
    for row in rows:
        if row["split"] != "development":
            raise ValueError(
                f"Calibration accepts development labels only; {row['set_id']} is {row['split']!r}"
            )
        provenance = row["label_source"].strip().lower()
        if provenance != "human_adjudicated" or any(
            token in provenance for token in forbidden_provenance
        ):
            raise ValueError(
                "Calibration requires label_source=human_adjudicated; "
                f"{row['set_id']} has {row['label_source']!r}"
            )
        if row["review_status"].strip().lower() != "final":
            raise ValueError(f"{row['set_id']} is not a final reviewed label")
        if row["set_id"] in labels:
            raise ValueError(f"Duplicate label for {row['set_id']}")
        labels[row["set_id"]] = row["human_choice_candidate_id"]
    return labels


def candidate_groups(
    rows: list[dict[str, str]], labels: dict[str, str]
) -> dict[str, list[dict[str, str]]]:
    required = {
        "set_id",
        "candidate_id",
        "rm_probability",
        "rubric_score",
        "evidence_score",
        "evidence_coverage",
        "contradiction_fraction",
        "hard_fail",
    }
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise ValueError(f"Candidate scores are missing columns: {', '.join(sorted(missing))}")

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["set_id"] in labels:
            groups[row["set_id"]].append(row)
    if set(groups) != set(labels):
        missing_sets = sorted(set(labels).difference(groups))
        raise ValueError(f"No candidate scores for labeled sets: {', '.join(missing_sets)}")
    for set_id, candidates in groups.items():
        candidate_ids = {row["candidate_id"] for row in candidates}
        if labels[set_id] not in candidate_ids:
            raise ValueError(f"Human choice {labels[set_id]} is absent from set {set_id}")
        if len(candidate_ids) != len(candidates):
            raise ValueError(f"Duplicate candidate IDs in set {set_id}")
    return groups


def evaluate(
    groups: dict[str, list[dict[str, str]]],
    labels: dict[str, str],
    config: ScoringConfig,
) -> tuple[float, float]:
    verifier_matches = 0
    hybrid_matches = 0
    for set_id, candidates in groups.items():
        verifier_scores: list[float] = []
        hard_fails: list[bool] = []
        rm_probabilities: list[float] = []
        for row in candidates:
            evidence_score = None if row["evidence_score"] == "" else float(row["evidence_score"])
            coverage = float(row["evidence_coverage"])
            hard_fail = row["hard_fail"].strip().lower() == "true"
            evidence = EvidenceAggregate(
                evidence_score=evidence_score,
                coverage=coverage,
                contradiction_fraction=float(row["contradiction_fraction"]),
                determinate_count=0,
                total_count=0,
            )
            score, _, _ = verifier_score(
                rubric_score=float(row["rubric_score"]),
                evidence=evidence,
                hard_fail=hard_fail,
                config=config,
            )
            verifier_scores.append(score)
            hard_fails.append(hard_fail)
            rm_probabilities.append(float(row["rm_probability"]))

        hybrid = hybrid_probabilities(
            rm_probabilities=rm_probabilities,
            verifier_scores=verifier_scores,
            hard_fails=hard_fails,
            config=config,
        )
        verifier_winner = max(
            zip(candidates, verifier_scores, strict=True),
            key=lambda pair: (pair[1], pair[0]["candidate_id"]),
        )[0]["candidate_id"]
        hybrid_winner = max(
            zip(candidates, hybrid, strict=True),
            key=lambda pair: (pair[1], pair[0]["candidate_id"]),
        )[0]["candidate_id"]
        verifier_matches += verifier_winner == labels[set_id]
        hybrid_matches += hybrid_winner == labels[set_id]
    denominator = len(labels)
    return verifier_matches / denominator, hybrid_matches / denominator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_scores", type=Path)
    parser.add_argument("human_labels", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base-config", type=Path, default=REPO_ROOT / "config/scoring.json")
    parser.add_argument("--evidence-weights", type=comma_floats, default=[0.0, 0.25, 0.5, 0.75])
    parser.add_argument(
        "--contradiction-penalties", type=comma_floats, default=[0.0, 0.1, 0.25, 0.5]
    )
    parser.add_argument("--rm-weights", type=comma_floats, default=[0.0, 0.25, 0.5, 0.75, 1.0])
    parser.add_argument("--temperatures", type=comma_floats, default=[0.1, 0.2, 0.5, 1.0])
    args = parser.parse_args()

    labels = require_final_human_development_labels(read_csv(args.human_labels))
    groups = candidate_groups(read_csv(args.candidate_scores), labels)
    base = ScoringConfig.from_json(args.base_config)

    trials = []
    for evidence_weight, penalty, rm_weight, temperature in itertools.product(
        args.evidence_weights,
        args.contradiction_penalties,
        args.rm_weights,
        args.temperatures,
    ):
        if not 0.0 <= evidence_weight <= 1.0:
            raise ValueError("evidence weights must be in [0, 1]")
        if penalty < 0.0:
            raise ValueError("contradiction penalties cannot be negative")
        if not 0.0 <= rm_weight <= 1.0:
            raise ValueError("RM weights must be in [0, 1]")
        if temperature <= 0.0:
            raise ValueError("temperatures must be positive")
        trial_config = replace(
            base,
            max_evidence_weight=evidence_weight,
            contradiction_penalty=penalty,
            hybrid_rm_weight=rm_weight,
            verifier_softmax_temperature=temperature,
        )
        verifier_accuracy, hybrid_accuracy = evaluate(groups, labels, trial_config)
        trials.append(
            {
                "max_evidence_weight": evidence_weight,
                "contradiction_penalty": penalty,
                "hybrid_rm_weight": rm_weight,
                "verifier_softmax_temperature": temperature,
                "verifier_accuracy": verifier_accuracy,
                "hybrid_accuracy": hybrid_accuracy,
            }
        )

    defaults = (
        base.max_evidence_weight,
        base.contradiction_penalty,
        base.hybrid_rm_weight,
        base.verifier_softmax_temperature,
    )
    best = max(
        trials,
        key=lambda row: (
            row["hybrid_accuracy"],
            row["verifier_accuracy"],
            -sum(
                abs(value - default)
                for value, default in zip(
                    (
                        row["max_evidence_weight"],
                        row["contradiction_penalty"],
                        row["hybrid_rm_weight"],
                        row["verifier_softmax_temperature"],
                    ),
                    defaults,
                    strict=True,
                )
            ),
        ),
    )
    write_json(
        args.output,
        {
            "calibrated_at": datetime.now(UTC).isoformat(),
            "label_contract": {
                "split": "development",
                "label_source": "human_adjudicated",
                "review_status": "final",
            },
            "labeled_set_count": len(labels),
            "selection_objective": (
                "hybrid_accuracy, then verifier_accuracy, then closest to base config"
            ),
            "frozen_not_calibrated_here": {
                "alignment_threshold": base.alignment_threshold,
                "hard_fail_veto": base.hard_fail_veto,
            },
            "selected_parameters": best,
            "trial_count": len(trials),
            "all_trials": sorted(
                trials,
                key=lambda row: (row["hybrid_accuracy"], row["verifier_accuracy"]),
                reverse=True,
            ),
        },
    )
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    main()
