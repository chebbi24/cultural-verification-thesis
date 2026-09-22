#!/usr/bin/env python3
"""Run development-only smoke cases through the verifier.

Smoke cases are not evaluation data. They contain no labels, winners, expected
scores or PLT IDs. The runner exists to produce traces for manual pre-gold
inspection before Verifier v1.0 is frozen.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from cultverify import Config, CulturalVerifier
from cultverify.llm import HTTPModel
from cultverify.retrieval import TavilyRetriever

FORBIDDEN_CASE_KEYS = {
    "label",
    "labels",
    "winner",
    "expected_winner",
    "expected_score",
    "expected_scores",
    "human_score",
    "human_label",
    "gold",
    "gold_label",
    "verdict",
}
CASE_ID = re.compile(r"^SMK\d{3}$")


def load_cases(path: Path) -> list[dict[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Smoke case file must contain a nonempty JSON array")
    cases: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Smoke case {index} is not an object")
        forbidden = FORBIDDEN_CASE_KEYS & set(item)
        if forbidden:
            case_name = item.get("case_id", index)
            raise ValueError(f"Smoke case {case_name!r} contains labels/expectations: {sorted(forbidden)}")
        allowed = {"case_id", "prompt", "response"}
        extra = set(item) - allowed
        if extra:
            case_name = item.get("case_id", index)
            raise ValueError(f"Smoke case {case_name!r} contains unsupported keys: {sorted(extra)}")
        case_id = item.get("case_id")
        prompt = item.get("prompt")
        response = item.get("response")
        if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
            raise ValueError(f"Smoke case {index} must use an SMK### case_id")
        if case_id in seen:
            raise ValueError(f"Duplicate smoke case_id: {case_id}")
        if not isinstance(prompt, str) or not prompt.strip() or not isinstance(response, str):
            raise ValueError(f"Smoke case {case_id} needs nonempty prompt and string response")
        if case_id.startswith("PLT") or "PLT" in prompt or "PLT" in response:
            raise ValueError(f"Smoke case {case_id} must not reference PLT gold items")
        cases.append({"case_id": case_id, "prompt": prompt, "response": response})
        seen.add(case_id)
    return cases


def build_config(args: argparse.Namespace) -> Config:
    values: dict[str, Any] = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
    env = {
        "verifier_model_id": "CULTVERIFY_MODEL",
        "verifier_model_provider": "CULTVERIFY_PROVIDER",
        "mode": "CULTVERIFY_MODE",
        "ollama_url": "OLLAMA_URL",
    }
    for key, name in env.items():
        if name in os.environ:
            values[key] = os.environ[name]
    for arg, key in [
        ("model", "verifier_model_id"),
        ("provider", "verifier_model_provider"),
        ("mode", "mode"),
        ("cache_directory", "cache_directory"),
        ("trace_directory", "trace_directory"),
    ]:
        value = getattr(args, arg, None)
        if value is not None:
            values[key] = value
    if "cache_directory" not in values:
        values["cache_directory"] = args.output_dir / "evidence"
    if "trace_directory" not in values:
        values["trace_directory"] = args.output_dir / "traces"
    return Config.model_validate(values)


def build_verifier(config: Config) -> CulturalVerifier:
    llm = HTTPModel(config, os.getenv("OPENROUTER_API_KEY"))
    retriever = TavilyRetriever(os.getenv("TAVILY_API_KEY"), config.search_depth) if config.mode == "LIVE" else None
    return CulturalVerifier(llm=llm, retriever=retriever, config=config)


def row_for_result(case: dict[str, str], result: Any) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "status": result.status,
        "overall_score": "" if result.overall_score is None else f"{result.overall_score:.6f}",
        "candidate_abstained": result.candidate_abstained,
        "evidence_coverage": "" if result.evidence_coverage is None else f"{result.evidence_coverage:.6f}",
        "applicable_count": result.applicable_count,
        "scored_count": result.scored_count,
        "targets_count": len(result.targets),
        "targets_truncated": result.targets_truncated,
        "trace_path": result.trace_path,
        "errors": " | ".join(result.errors),
    }


def run_cases(cases: list[dict[str, str]], verifier: Any, output_dir: Path) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = verifier.verify(prompt=case["prompt"], response=case["response"])
        rows.append(row_for_result(case, result))
    write_results(output_dir, rows)
    return rows


def write_results(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    path = output_dir / "smoke_results.csv"
    fieldnames = [
        "case_id",
        "status",
        "overall_score",
        "candidate_abstained",
        "evidence_coverage",
        "applicable_count",
        "scored_count",
        "targets_count",
        "targets_truncated",
        "trace_path",
        "errors",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "schema_version": "smoke-results-v1",
        "n_cases": len(rows),
        "n_failed": sum(row["status"] == "failed" for row in rows),
        "note": "Development-only smoke traces. Not human-gold evaluation data.",
    }
    (output_dir / "smoke_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("data/dev/verifier_smoke_cases.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/dev_smoke"))
    parser.add_argument("--config", type=Path, help="Config JSON, credentials excluded")
    parser.add_argument("--model")
    parser.add_argument("--provider", choices=("ollama", "openrouter"))
    parser.add_argument("--mode", choices=("LIVE", "REPLAY"))
    parser.add_argument("--cache-directory", type=Path)
    parser.add_argument("--trace-directory", type=Path)
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.cases)
        config = build_config(args)
        verifier = build_verifier(config)
        rows = run_cases(cases, verifier, args.output_dir)
        print(json.dumps({"output_dir": str(args.output_dir), "n_cases": len(rows)}, indent=2))
        return 2 if any(row["status"] == "failed" for row in rows) else 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
