"""Evaluate the standalone verifier on Best-of-4 candidate sets.

Expected columns: set_id (optional), prompt_id (optional), prompt,
response_a, response_b, response_c, response_d, human_chosen (optional).

The human label is used only after all candidates have been independently
scored. It is never sent to the verifier.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from verifier import CulturalVerifier, OpenRouterClient


def read_rows(path: Path) -> list[dict[str, str]]:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    first = sample.splitlines()[0] if sample.splitlines() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--target-context", default="Germany")
    parser.add_argument("--model", default=None, help="OpenRouter model slug; otherwise OPENROUTER_MODEL/default is used.")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = read_rows(args.input_csv)
    if args.limit > 0:
        rows = rows[: args.limit]

    verifier = CulturalVerifier(OpenRouterClient(model=args.model))
    summary: list[dict[str, object]] = []
    details: list[dict[str, object]] = []

    for index, row in enumerate(rows, 1):
        prompt = row["prompt"]
        case_id = row.get("set_id") or row.get("prompt_id") or f"row_{index}"
        print(f"[{index}/{len(rows)}] {case_id}", flush=True)

        candidate_results = {}
        for label in "abcd":
            response = row[f"response_{label}"]
            print(f"  candidate {label.upper()}", flush=True)
            candidate_results[label] = verifier.verify(prompt, response, args.target_context)

        winner = max(
            "abcd",
            key=lambda label: (candidate_results[label].final_score, -"abcd".index(label)),
        )
        human = (row.get("human_chosen") or "").strip().lower()
        summary.append({
            "set_id": row.get("set_id", case_id),
            "prompt_id": row.get("prompt_id", ""),
            "human_chosen": human,
            "verifier_winner": winner,
            "verifier_correct": int(bool(human) and winner == human),
            "score_a": candidate_results["a"].final_score,
            "score_b": candidate_results["b"].final_score,
            "score_c": candidate_results["c"].final_score,
            "score_d": candidate_results["d"].final_score,
        })
        details.append({
            "set_id": row.get("set_id", case_id),
            "prompt_id": row.get("prompt_id", ""),
            "prompt": prompt,
            "target_context": args.target_context,
            "verifier_winner": winner,
            "candidates": {
                label: {
                    "response": row[f"response_{label}"],
                    **candidate_results[label].__dict__,
                }
                for label in "abcd"
            },
        })

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "set_id", "prompt_id", "human_chosen", "verifier_winner", "verifier_correct",
        "score_a", "score_b", "score_c", "score_d",
    ]
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)

    details_path = args.output_csv.with_suffix(".details.json")
    details_path.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")

    labelled = [row for row in summary if row["human_chosen"]]
    if labelled:
        accuracy = sum(int(row["verifier_correct"]) for row in labelled) / len(labelled)
        print(json.dumps({"n_labelled": len(labelled), "best_of_4_accuracy": accuracy}, indent=2))
    print(f"Saved {args.output_csv}")
    print(f"Saved {details_path}")


if __name__ == "__main__":
    main()
