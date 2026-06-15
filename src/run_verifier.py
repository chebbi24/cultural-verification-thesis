"""
Run the concrete cultural verifier on an existing model-output CSV.

"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from verifier import MINIMAL_OUTPUT_FIELDS, verify_case


def detect_delimiter(path: Path) -> str:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    first_line = sample.splitlines()[0] if sample.splitlines() else ""

    if first_line.count(";") > first_line.count(","):
        return ";"

    return ","


def read_rows(path: Path) -> list[dict[str, str]]:
    delimiter = detect_delimiter(path)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv")
    parser.add_argument("output_csv")
    parser.add_argument("--target-culture", default="Germany")
    parser.add_argument("--judge-model", default="llama3.2:3b")
    parser.add_argument("--limit", type=int, default=0, help="Use 0 for all rows.")

    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    rows = read_rows(input_path)

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(rows)

    for index, row in enumerate(rows, start=1):
        case_id = row.get("prompt_id") or row.get("case_id") or f"row_{index}"
        print(f"[{index}/{total}] verifying {case_id}", flush=True)

        result = verify_case(
            row,
            target_culture=args.target_culture,
            judge_model=args.judge_model,
        )

        results.append(result)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MINIMAL_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print(f"Saved results to {output_path}")


if __name__ == "__main__":
    main()