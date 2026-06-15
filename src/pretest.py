"""


Convert an existing model-output CSV into verifier input cases.

Use this when you already have model outputs, for example:
- llama32_3b_redteam_v22_outputs.csv

Expected input columns:
- model
- prompt_id
- run_id
- category
- source
- prompt
- expected_issue
- model_output
- error

Output columns for 09_run_verification.py:
- case_id
- target_culture
- user_prompt
- assistant_response
- linked_charter_article_ids
- linked_taxonomy_ids
- prism_mapping_ids

Usage:
python 13_prepare_existing_outputs_for_verification.py llama32_3b_redteam_v22_outputs.csv verifier_cases_existing.csv

Then:
python 09_run_verification.py verifier_cases_existing.csv verification_results_existing.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_MAPPING = {
    "linked_charter_article_ids": "2;3;5;8;11",
    "linked_taxonomy_ids": "T2_01;T2_03;T3_01;T3_02;T5_01;T8_01;T11_02;T11_03",
    "prism_mapping_ids": "P12",
}


CATEGORY_MAPPING = {
    "Movie and Crime": {
        "linked_charter_article_ids": "2;3;4;5;11",
        "linked_taxonomy_ids": "T2_01;T3_02;T4_01;T4_02;T5_01;T11_03",
        "prism_mapping_ids": "P07;P11",
    },
    "Quiet Hours, Housing and Neighbour Relations": {
        "linked_charter_article_ids": "2;3;5;7;8;9;11",
        "linked_taxonomy_ids": "T2_01;T2_03;T3_03;T5_01;T7_01;T8_01;T9_01;T11_02",
        "prism_mapping_ids": "P03;P08;P12",
    },
    "Food, Alcohol and Hospitality": {
        "linked_charter_article_ids": "3;5;8;11",
        "linked_taxonomy_ids": "T3_01;T3_02;T5_02;T8_02;T11_02",
        "prism_mapping_ids": "P10;P12",
    },
    "Food and Eating": {
        "linked_charter_article_ids": "3;5;8;11",
        "linked_taxonomy_ids": "T3_01;T3_02;T5_02;T8_02;T11_02",
        "prism_mapping_ids": "P10;P12",
    },
    "History, Humour and Symbolism": {
        "linked_charter_article_ids": "2;3;4;5;11",
        "linked_taxonomy_ids": "T2_01;T2_02;T3_01;T3_02;T4_01;T5_01;T11_03",
        "prism_mapping_ids": "P07;P11",
    },
    "Humor and Identity": {
        "linked_charter_article_ids": "2;3;4;5;8;11",
        "linked_taxonomy_ids": "T2_02;T3_01;T3_02;T4_02;T5_01;T8_02;T11_02",
        "prism_mapping_ids": "P07;P11;P12",
    },
    "Everyday Legal Obligations": {
        "linked_charter_article_ids": "2;4;5;6;7;8;11",
        "linked_taxonomy_ids": "T2_01;T4_01;T6_01;T6_02;T7_01;T8_01;T11_03",
        "prism_mapping_ids": "P03;P12",
    },
    "Legal Requirements": {
        "linked_charter_article_ids": "2;4;6;8;11",
        "linked_taxonomy_ids": "T2_01;T4_01;T6_01;T6_02;T8_01;T11_03",
        "prism_mapping_ids": "P03;P09",
    },
    "Values and Social Roles": {
        "linked_charter_article_ids": "3;5;8;10;11",
        "linked_taxonomy_ids": "T3_01;T3_02;T5_01;T5_03;T8_02;T8_03;T10_01;T10_02;T11_02",
        "prism_mapping_ids": "P02;P05;P06",
    },
    "Regional Authenticity and Fictional Framing": {
        "linked_charter_article_ids": "2;3;5;11",
        "linked_taxonomy_ids": "T2_01;T2_03;T3_02;T5_02;T11_02;T11_03",
        "prism_mapping_ids": "P12",
    },
    "North-South Germany": {
        "linked_charter_article_ids": "2;3;5;11",
        "linked_taxonomy_ids": "T2_03;T3_02;T3_03;T5_02;T11_02",
        "prism_mapping_ids": "P08;P12",
    },
    "Party Culture": {
        "linked_charter_article_ids": "3;5;7;8;9;11",
        "linked_taxonomy_ids": "T3_03;T5_01;T7_01;T8_01;T9_01;T11_02",
        "prism_mapping_ids": "P03;P08;P10",
    },
}


def detect_delimiter(path: Path) -> str:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    first_line = sample.splitlines()[0]

    if first_line.count(";") > first_line.count(","):
        return ";"

    return ","


def read_rows(path: Path) -> list[dict[str, str]]:
    delimiter = detect_delimiter(path)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("existing_outputs_csv")
    parser.add_argument("verifier_cases_csv")
    parser.add_argument("--target-culture", default="Germany")
    parser.add_argument("--keep-error-rows", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.existing_outputs_csv)
    output_path = Path(args.verifier_cases_csv)

    rows = read_rows(input_path)
    output_rows = []

    skipped = 0

    for index, row in enumerate(rows, start=1):
        error_value = (row.get("error") or "").strip()
        model_output = (row.get("model_output") or "").strip()

        if not args.keep_error_rows:
            if error_value or not model_output or model_output.startswith("GENERATION_ERROR"):
                skipped += 1
                continue

        prompt_id = (row.get("prompt_id") or f"row_{index}").strip()
        run_id = (row.get("run_id") or "1").strip()
        case_id = f"{prompt_id}_run{run_id}"

        category = (row.get("category") or "").strip()
        mapping = CATEGORY_MAPPING.get(category, DEFAULT_MAPPING)

        output_rows.append(
            {
                "case_id": case_id,
                "target_culture": args.target_culture,
                "user_prompt": (row.get("prompt") or "").strip(),
                "assistant_response": model_output,
                "linked_charter_article_ids": mapping["linked_charter_article_ids"],
                "linked_taxonomy_ids": mapping["linked_taxonomy_ids"],
                "prism_mapping_ids": mapping["prism_mapping_ids"],
            }
        )

    fieldnames = [
        "case_id",
        "target_culture",
        "user_prompt",
        "assistant_response",
        "linked_charter_article_ids",
        "linked_taxonomy_ids",
        "prism_mapping_ids",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Read rows: {len(rows)}")
    print(f"Prepared verifier cases: {len(output_rows)}")
    print(f"Skipped rows: {skipped}")
    print(f"Saved verifier cases to: {output_path}")


if __name__ == "__main__":
    main()