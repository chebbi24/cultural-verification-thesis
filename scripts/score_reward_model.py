#!/usr/bin/env python3
"""Score long-form candidates with Skywork and add within-set probabilities."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cultural_verifier.io import read_csv, write_csv, write_json
from cultural_verifier.reward import SkyworkRewardModel
from cultural_verifier.scoring import softmax


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="Skywork/Skywork-Reward-V2-Qwen3-0.6B")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-length", type=int, default=4096)
    args = parser.parse_args()

    rows = read_csv(args.input)
    reward = SkyworkRewardModel(args.model, max_length=args.max_length, device=args.device)
    for index, row in enumerate(rows, 1):
        if not row.get("raw_rm_score"):
            row["raw_rm_score"] = reward.score(row["prompt_text"], row["response_text"])
        print(f"[{index}/{len(rows)}] {row['candidate_id']} {float(row['raw_rm_score']):.4f}")

    by_set: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_set[row["set_id"]].append(row)
    for candidates in by_set.values():
        probabilities = softmax(float(row["raw_rm_score"]) for row in candidates)
        for row, probability in zip(candidates, probabilities, strict=True):
            row["rm_probability"] = probability
    fields = list(rows[0])
    for field in ["raw_rm_score", "rm_probability"]:
        if field not in fields:
            fields.append(field)
    write_csv(args.output, rows, fields)
    write_json(
        args.output.with_suffix(".metadata.json"),
        {"reward_model": args.model, "device": args.device, "candidate_count": len(rows)},
    )


if __name__ == "__main__":
    main()
