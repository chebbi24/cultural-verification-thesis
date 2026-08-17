"""Convert long-format pilot candidates into the wide Best-of-4 format.

Inputs
------
data/pilot/candidates.csv
    One row per candidate with columns including set_id, legacy_prompt_id,
    candidate_position, prompt_text, response_text.

data/pilot/provisional_annotations.csv (optional)
    Provisional preferred candidate labels. These are development labels only
    and must not be presented as human ground truth.

Output
------
data/pilot/best_of4.csv
    set_id,prompt_id,prompt,response_a,response_b,response_c,response_d,
    human_chosen,label_source
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


POSITION_TO_LABEL = {1: "a", 2: "b", 3: "c", 4: "d"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_annotations(path: Path | None) -> dict[str, tuple[str, str]]:
    if path is None or not path.exists():
        return {}

    annotations: dict[str, tuple[str, str]] = {}
    for row in read_csv(path):
        set_id = (row.get("set_id") or "").strip()
        preferred = (row.get("preferred_candidate_id") or "").strip()
        source = (row.get("label_source") or "").strip()
        if not set_id or not preferred:
            continue

        # Expected form: PLT001-C1 -> candidate position 1 -> label a.
        try:
            position = int(preferred.rsplit("-C", 1)[1])
        except (IndexError, ValueError):
            raise ValueError(
                f"Could not parse preferred_candidate_id={preferred!r} for {set_id}"
            )
        if position not in POSITION_TO_LABEL:
            raise ValueError(f"Candidate position must be 1..4, got {position} for {set_id}")
        annotations[set_id] = (POSITION_TO_LABEL[position], source)

    return annotations


def build_rows(
    candidate_rows: list[dict[str, str]],
    annotations: dict[str, tuple[str, str]],
) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        set_id = (row.get("set_id") or "").strip()
        if not set_id:
            raise ValueError("Found candidate row without set_id")
        grouped[set_id].append(row)

    output: list[dict[str, str]] = []

    for set_id in sorted(grouped):
        rows = grouped[set_id]
        by_position: dict[int, dict[str, str]] = {}

        for row in rows:
            try:
                position = int((row.get("candidate_position") or "").strip())
            except ValueError as exc:
                raise ValueError(f"Invalid candidate_position in {set_id}") from exc
            if position in by_position:
                raise ValueError(f"Duplicate candidate position {position} in {set_id}")
            by_position[position] = row

        missing = sorted(set(POSITION_TO_LABEL) - set(by_position))
        if missing:
            raise ValueError(f"{set_id} is missing candidate positions: {missing}")

        prompts = {(row.get("prompt_text") or "").strip() for row in rows}
        if len(prompts) != 1:
            raise ValueError(f"Candidates in {set_id} do not share exactly one prompt")
        prompt = prompts.pop()

        prompt_ids = {
            (row.get("legacy_prompt_id") or "").strip()
            for row in rows
            if (row.get("legacy_prompt_id") or "").strip()
        }
        if len(prompt_ids) > 1:
            raise ValueError(f"Candidates in {set_id} have conflicting legacy_prompt_id values")
        prompt_id = next(iter(prompt_ids), "")

        human_chosen, label_source = annotations.get(set_id, ("", ""))

        output.append(
            {
                "set_id": set_id,
                "prompt_id": prompt_id,
                "prompt": prompt,
                "response_a": (by_position[1].get("response_text") or "").strip(),
                "response_b": (by_position[2].get("response_text") or "").strip(),
                "response_c": (by_position[3].get("response_text") or "").strip(),
                "response_d": (by_position[4].get("response_text") or "").strip(),
                "human_chosen": human_chosen,
                "label_source": label_source,
            }
        )

    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/pilot/candidates.csv"),
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("data/pilot/provisional_annotations.csv"),
        help="Optional provisional annotation file; ignored if it does not exist.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/pilot/best_of4.csv"),
    )
    args = parser.parse_args()

    candidate_rows = read_csv(args.candidates)
    annotations = load_annotations(args.annotations)
    output_rows = build_rows(candidate_rows, annotations)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "set_id",
        "prompt_id",
        "prompt",
        "response_a",
        "response_b",
        "response_c",
        "response_d",
        "human_chosen",
        "label_source",
    ]
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    labelled = sum(bool(row["human_chosen"]) for row in output_rows)
    print(f"Saved {len(output_rows)} Best-of-4 sets to {args.output}")
    print(f"Rows with provisional preferred-candidate labels: {labelled}")
    if labelled:
        print("NOTE: these labels are provisional/synthetic and are not human ground truth.")


if __name__ == "__main__":
    main()
