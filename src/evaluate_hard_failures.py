"""Evaluate hard-failure eligibility labels against human annotations.

The annotation file must contain: set_id, candidate_label, human_ineligible
(0/1).  Optional ``human_hard_failure_codes`` stores pipe-separated HF codes.
The verifier details JSON is produced by evaluate_best_of4.py.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _truth(value: str) -> bool:
    value = value.strip().lower()
    if value in {"1", "true", "yes"}:
        return True
    if value in {"0", "false", "no"}:
        return False
    raise ValueError("human_ineligible must be one of 1/0, true/false, or yes/no")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("verifier_details_json", type=Path)
    parser.add_argument("annotations_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()

    details = json.loads(args.verifier_details_json.read_text(encoding="utf-8"))
    predictions: dict[tuple[str, str], bool] = {}
    for item in details:
        set_id = str(item.get("set_id", ""))
        for label, candidate in item.get("candidates", {}).items():
            predictions[(set_id, str(label).lower())] = not bool(
                candidate.get("eligible", not candidate.get("hard_fail", False))
            )

    with args.annotations_csv.open(encoding="utf-8-sig", newline="") as handle:
        annotations = list(csv.DictReader(handle))
    required = {"set_id", "candidate_label", "human_ineligible"}
    if not annotations or not required.issubset(annotations[0]):
        raise ValueError(f"annotations CSV must contain columns: {sorted(required)}")

    tp = fp = tn = fn = 0
    missing: list[str] = []
    for row in annotations:
        key = (row["set_id"].strip(), row["candidate_label"].strip().lower())
        if key not in predictions:
            missing.append(f"{key[0]}:{key[1]}")
            continue
        predicted, actual = predictions[key], _truth(row["human_ineligible"])
        if predicted and actual:
            tp += 1
        elif predicted:
            fp += 1
        elif actual:
            fn += 1
        else:
            tn += 1

    evaluated = tp + fp + tn + fn
    metric = lambda numerator, denominator: None if not denominator else numerator / denominator
    result = {
        "n_annotated": len(annotations),
        "n_evaluated": evaluated,
        "missing_verifier_predictions": missing,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "hard_failure_precision": metric(tp, tp + fp),
        "hard_failure_recall": metric(tp, tp + fn),
        "hard_failure_false_positive_rate": metric(fp, fp + tn),
        "human_ineligible_rate": metric(tp + fn, evaluated),
        "verifier_ineligible_rate": metric(tp + fp, evaluated),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved {args.output_json}")


if __name__ == "__main__":
    main()
