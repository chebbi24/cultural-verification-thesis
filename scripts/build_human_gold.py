#!/usr/bin/env python3
"""Build frozen human-reference tables from the exported annotation workbook.

The workbook is treated as immutable input. The script uses only the Python
standard library so that the annotation freeze does not add a spreadsheet
runtime dependency to the verifier package.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
PKG_REL_NS = {"p": "http://schemas.openxmlformats.org/package/2006/relationships"}

RATING_HEADER = re.compile(r"^PLT(\d{3}) — How culturally appropriate is RESPONSE ([ABCD])\?$")
WINNER_HEADER = re.compile(
    r"^PLT(\d{3}) — Considering cultural appropriateness specifically, "
    r"which response is the BEST response to this scenario\?$"
)
RATING_VALUE = re.compile(r"^([123])\s+—\s+")
WINNER_VALUE = re.compile(r"^RESPONSE ([ABCD])$")
PROMPT_IDS = tuple(f"PLT{i:03d}" for i in range(1, 31))
CANDIDATES = tuple("ABCD")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    value = 0
    for ch in letters:
        value = value * 26 + ord(ch.upper()) - 64
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for si in root.findall("m:si", NS):
        values.append("".join(t.text or "" for t in si.iterfind(".//m:t", NS)))
    return values


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    sheet = workbook.find("m:sheets/m:sheet", {**NS, **REL_NS})
    if sheet is None:
        raise ValueError("Workbook contains no worksheet")
    relation_id = sheet.attrib[f"{{{REL_NS['r']}}}id"]
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for rel in relationships.findall("p:Relationship", PKG_REL_NS):
        if rel.attrib.get("Id") == relation_id:
            target = rel.attrib["Target"].lstrip("/")
            if target.startswith("xl/"):
                return target
            return "xl/" + target
    raise ValueError("Could not resolve first worksheet")


def read_xlsx_rows(path: Path) -> list[list[object]]:
    """Read cell values from the first worksheet of a simple .xlsx export."""
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        sheet_path = _first_sheet_path(archive)
        root = ET.fromstring(archive.read(sheet_path))

    materialized: list[dict[int, object]] = []
    max_col = -1
    for row in root.findall(".//m:sheetData/m:row", NS):
        cells: dict[int, object] = {}
        for cell in row.findall("m:c", NS):
            ref = cell.attrib.get("r", "A1")
            col = _column_index(ref)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("m:v", NS)
            if cell_type == "inlineStr":
                value = "".join(t.text or "" for t in cell.iterfind(".//m:t", NS))
            elif value_node is None:
                value = ""
            else:
                raw = value_node.text or ""
                if cell_type == "s":
                    value = shared[int(raw)]
                elif cell_type == "b":
                    value = raw == "1"
                elif cell_type in {"str", "e"}:
                    value = raw
                else:
                    try:
                        value = float(raw) if "." in raw else int(raw)
                    except ValueError:
                        value = raw
            cells[col] = value
            max_col = max(max_col, col)
        materialized.append(cells)

    if not materialized:
        raise ValueError("Workbook has no rows")
    width = max_col + 1
    return [[row.get(i, "") for i in range(width)] for row in materialized]


def _fleiss_kappa(vote_counts: list[list[int]], raters: int) -> float:
    if not vote_counts:
        raise ValueError("No winner votes available")
    n_items = len(vote_counts)
    category_totals = [sum(row[j] for row in vote_counts) for j in range(len(CANDIDATES))]
    p = [count / (n_items * raters) for count in category_totals]
    p_e = sum(value * value for value in p)
    p_bar = sum((sum(v * v for v in row) - raters) / (raters * (raters - 1)) for row in vote_counts) / n_items
    return 1.0 if p_e == 1.0 and p_bar == 1.0 else (p_bar - p_e) / (1.0 - p_e)


def derive_human_gold(headers: list[object], rows: list[list[object]], expected_annotators: int = 5):
    if len(rows) != expected_annotators:
        raise ValueError(f"Expected {expected_annotators} submissions, found {len(rows)}")
    headers = [str(value) for value in headers]
    if len(headers) != 155:
        raise ValueError(f"Expected 155 columns (5 metadata + 30×5 annotations), found {len(headers)}")

    rating_columns: dict[tuple[str, str], int] = {}
    winner_columns: dict[str, int] = {}
    for index, header in enumerate(headers):
        match = RATING_HEADER.fullmatch(header)
        if match:
            rating_columns[(f"PLT{match.group(1)}", match.group(2))] = index
            continue
        match = WINNER_HEADER.fullmatch(header)
        if match:
            winner_columns[f"PLT{match.group(1)}"] = index

    expected_rating_keys = {(pid, candidate) for pid in PROMPT_IDS for candidate in CANDIDATES}
    if set(rating_columns) != expected_rating_keys:
        missing = sorted(expected_rating_keys - set(rating_columns))
        extra = sorted(set(rating_columns) - expected_rating_keys)
        raise ValueError(f"Rating columns mismatch; missing={missing}, extra={extra}")
    if set(winner_columns) != set(PROMPT_IDS):
        raise ValueError("Winner columns must contain exactly PLT001–PLT030")

    confirmation_header = (
        "Confirmation (I have read the annotation instructions and understand how to evaluate the responses.)"
    )
    if confirmation_header not in headers:
        raise ValueError("Missing annotation-instructions confirmation column")
    confirmation_index = headers.index(confirmation_header)
    if not all(row[confirmation_index] is True for row in rows):
        raise ValueError("Every submission must confirm the annotation instructions")

    ratings: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    winner_votes: dict[str, list[str]] = defaultdict(list)
    for row_number, row in enumerate(rows, start=2):
        for key, index in rating_columns.items():
            value = str(row[index])
            match = RATING_VALUE.match(value)
            if not match:
                raise ValueError(f"Invalid rating at row {row_number}, {key}: {value!r}")
            ratings[key[0]][key[1]].append(int(match.group(1)))
        for prompt_id, index in winner_columns.items():
            value = str(row[index])
            match = WINNER_VALUE.fullmatch(value)
            if not match:
                raise ValueError(f"Invalid winner at row {row_number}, {prompt_id}: {value!r}")
            winner_votes[prompt_id].append(match.group(1))

    candidate_rows: list[dict[str, object]] = []
    prompt_rows: list[dict[str, object]] = []
    vote_matrix: list[list[int]] = []
    rating_distribution = Counter()

    for prompt_id in PROMPT_IDS:
        votes = Counter(winner_votes[prompt_id])
        vote_counts = [votes[c] for c in CANDIDATES]
        vote_matrix.append(vote_counts)
        max_votes = max(vote_counts)
        top_set = [c for c in CANDIDATES if votes[c] == max_votes]
        unique_majority = len(top_set) == 1 and max_votes >= 3
        majority_winner = top_set[0] if unique_majority else ""
        if len(top_set) == 1 and max_votes >= 4:
            consensus = "strong_consensus"
        elif unique_majority:
            consensus = "majority"
        else:
            consensus = "ambiguous"

        prompt_rows.append(
            {
                "prompt_id": prompt_id,
                "A_votes": votes["A"],
                "B_votes": votes["B"],
                "C_votes": votes["C"],
                "D_votes": votes["D"],
                "top_set": "|".join(top_set),
                "majority_winner": majority_winner,
                "max_votes": max_votes,
                "consensus_level": consensus,
            }
        )

        for candidate in CANDIDATES:
            values = ratings[prompt_id][candidate]
            if len(values) != expected_annotators:
                raise ValueError(f"Incomplete ratings for {prompt_id}-{candidate}")
            rating_distribution.update(values)
            avg = mean(values)
            candidate_rows.append(
                {
                    "prompt_id": prompt_id,
                    "candidate_id": candidate,
                    "human_mean": f"{avg:.3f}",
                    "human_median": f"{median(values):.1f}",
                    "n_score_1": values.count(1),
                    "n_score_2": values.count(2),
                    "n_score_3": values.count(3),
                    "human_score_normalized": f"{(avg - 1.0) / 2.0:.3f}",
                    "winner_votes": votes[candidate],
                }
            )

    summary = {
        "schema_version": "human-gold-v1",
        "n_annotators": expected_annotators,
        "n_prompts": len(PROMPT_IDS),
        "n_candidates_per_prompt": len(CANDIDATES),
        "n_candidate_responses": len(candidate_rows),
        "n_candidate_ratings": len(candidate_rows) * expected_annotators,
        "n_winner_votes": len(PROMPT_IDS) * expected_annotators,
        "winner_fleiss_kappa": round(_fleiss_kappa(vote_matrix, expected_annotators), 6),
        "consensus": dict(Counter(row["consensus_level"] for row in prompt_rows)),
        "unanimous_prompts": sum(row["max_votes"] == 5 and bool(row["majority_winner"]) for row in prompt_rows),
        "at_least_4_of_5_prompts": sum(row["max_votes"] >= 4 and bool(row["majority_winner"]) for row in prompt_rows),
        "majority_3_of_5_or_more_prompts": sum(bool(row["majority_winner"]) for row in prompt_rows),
        "top_vote_ties": sum("|" in str(row["top_set"]) for row in prompt_rows),
        "rating_distribution": {str(score): rating_distribution[score] for score in (1, 2, 3)},
    }
    return candidate_rows, prompt_rows, summary


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build(input_path: Path, output_dir: Path, expected_annotators: int = 5) -> dict[str, object]:
    sheet_rows = read_xlsx_rows(input_path)
    candidate_rows, prompt_rows, summary = derive_human_gold(sheet_rows[0], sheet_rows[1:], expected_annotators)

    candidate_path = output_dir / "human_gold_candidates.csv"
    prompt_path = output_dir / "human_gold_prompts.csv"
    summary_path = output_dir / "human_gold_summary.json"
    manifest_path = output_dir / "human_gold_manifest.json"

    write_csv(
        candidate_path,
        candidate_rows,
        [
            "prompt_id",
            "candidate_id",
            "human_mean",
            "human_median",
            "n_score_1",
            "n_score_2",
            "n_score_3",
            "human_score_normalized",
            "winner_votes",
        ],
    )
    write_csv(
        prompt_path,
        prompt_rows,
        [
            "prompt_id",
            "A_votes",
            "B_votes",
            "C_votes",
            "D_votes",
            "top_set",
            "majority_winner",
            "max_votes",
            "consensus_level",
        ],
    )
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "freeze_version": "human-gold-v1",
        "source_file": input_path.name,
        "source_sha256": sha256_file(input_path),
        "derived": {
            candidate_path.name: sha256_file(candidate_path),
            prompt_path.name: sha256_file(prompt_path),
            summary_path.name: sha256_file(summary_path),
        },
        "policy": "Raw annotations are immutable. Derived files are regenerated only from the frozen source workbook.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**summary, "manifest": manifest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Raw .xlsx annotation export")
    parser.add_argument("--output-dir", type=Path, default=Path("data/evaluation"))
    parser.add_argument("--expected-annotators", type=int, default=5)
    args = parser.parse_args(argv)
    result = build(args.input, args.output_dir, args.expected_annotators)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
