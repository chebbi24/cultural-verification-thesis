"""Canonical literature-derived cultural-dimension registry.

The same D01-D10 ontology is used for benchmark coverage and verifier scoring.
The CSV is deliberately human-readable so that scoring anchors can be reviewed,
annotated, calibrated, and frozen before the held-out experiment.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

DIMENSION_IDS = tuple(f"D{i:02d}" for i in range(1, 11))
DEFAULT_RUBRIC_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "csv"
    / "cultural_dimension_rubric.csv"
)
DEFAULT_BENCHMARK_DOMAINS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "csv" / "domains.csv"
)


@dataclass(frozen=True)
class CulturalDimension:
    dimension_id: str
    dimension_name: str
    definition: str
    scoring_question: str
    zero_anchor: str
    one_anchor: str
    two_anchor: str
    carb_parent: str
    source_basis: str

    def prompt_record(self) -> dict[str, str]:
        return asdict(self)


def load_dimensions(path: Path | None = None) -> dict[str, CulturalDimension]:
    rubric_path = path or DEFAULT_RUBRIC_PATH
    with rubric_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    found = [row.get("dimension_id", "").strip() for row in rows]
    if tuple(found) != DIMENSION_IDS:
        raise ValueError(
            f"Cultural rubric must contain exactly {DIMENSION_IDS} in order; found {tuple(found)}"
        )

    registry: dict[str, CulturalDimension] = {}
    for row in rows:
        missing = [key for key, value in row.items() if not str(value or "").strip()]
        if missing:
            raise ValueError(
                f"Dimension {row.get('dimension_id', '<unknown>')} has empty fields: {missing}"
            )
        dimension = CulturalDimension(
            **{key: str(value).strip() for key, value in row.items()}
        )
        registry[dimension.dimension_id] = dimension
    return registry


CULTURAL_DIMENSIONS = load_dimensions()


def validate_benchmark_domain_alignment(
    registry: dict[str, CulturalDimension] | None = None,
    domains_path: Path | None = None,
) -> None:
    current = registry or CULTURAL_DIMENSIONS
    path = domains_path or DEFAULT_BENCHMARK_DOMAINS_PATH
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    benchmark = {
        str(row.get("domain_id", "")).strip(): row
        for row in rows
        if str(row.get("domain_id", "")).strip()
    }
    if tuple(benchmark) != DIMENSION_IDS:
        raise ValueError(
            "Benchmark domains and verifier rubric must contain the same ordered D01-D10 ids"
        )
    for dimension_id, dimension in current.items():
        row = benchmark[dimension_id]
        if str(row.get("domain_name", "")).strip() != dimension.dimension_name:
            raise ValueError(f"Domain name drift detected for {dimension_id}")
        if str(row.get("definition", "")).strip() != dimension.definition:
            raise ValueError(f"Domain definition drift detected for {dimension_id}")


validate_benchmark_domain_alignment()


def prompt_dimension_records(
    dimension_ids: list[str] | tuple[str, ...],
) -> list[dict[str, str]]:
    unknown = [
        dimension_id
        for dimension_id in dimension_ids
        if dimension_id not in CULTURAL_DIMENSIONS
    ]
    if unknown:
        raise ValueError(f"Unknown cultural dimension ids: {unknown}")
    return [
        CULTURAL_DIMENSIONS[dimension_id].prompt_record()
        for dimension_id in dimension_ids
    ]
