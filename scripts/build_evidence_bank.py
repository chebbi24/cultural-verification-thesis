#!/usr/bin/env python3
"""Populate an auditable evidence bank with agentic open-web search."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cultural_verifier.io import append_jsonl, read_csv, write_csv, write_json
from cultural_verifier.search import AgenticWebSearch


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    completed = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                completed.add(json.loads(line)["reference_claim_id"])
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--reasoning-effort", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    claims = read_csv(args.claims)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bank_path = args.output_dir / "evidence_bank.jsonl"
    sources_path = args.output_dir / "source_registry.csv"
    if args.no_resume:
        bank_path.unlink(missing_ok=True)
        sources_path.unlink(missing_ok=True)
    completed = completed_ids(bank_path)
    search = AgenticWebSearch(model=args.model, reasoning_effort=args.reasoning_effort)

    existing_sources = read_csv(sources_path) if sources_path.exists() else []
    sources = list(existing_sources)
    processed = 0
    started_at = datetime.now(UTC).isoformat()
    for row in claims:
        if row["reference_claim_id"] in completed:
            continue
        if args.limit is not None and processed >= args.limit:
            break
        run = search.search_reference_claim(row)
        append_jsonl(bank_path, run.to_dict())
        for index, source in enumerate(run.sources, 1):
            sources.append(
                {
                    "source_id": f"{run.reference_claim_id}-SRC{index:02d}",
                    "reference_claim_id": run.reference_claim_id,
                    "prompt_id": row["prompt_id"],
                    "url": source.url,
                    "title": source.title,
                    "retrieved_at": run.searched_at,
                    "search_model": run.model,
                    "search_response_id": run.response_id,
                    "queries": " | ".join(run.queries),
                    "source_role": "agentic_web_search_result",
                    "verification_status": "unreviewed",
                }
            )
        write_csv(
            sources_path,
            sources,
            [
                "source_id",
                "reference_claim_id",
                "prompt_id",
                "url",
                "title",
                "retrieved_at",
                "search_model",
                "search_response_id",
                "queries",
                "source_role",
                "verification_status",
            ],
        )
        processed += 1
        print(f"[{processed}] {run.reference_claim_id}: {len(run.sources)} sources")

    write_json(
        args.output_dir / "run_metadata.json",
        {
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "claims_file": str(args.claims),
            "search_model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "retrieval_method": "Responses API hosted web_search",
            "domain_allowlist": None,
            "site_filters": None,
            "processed_this_run": processed,
            "total_completed": len(completed_ids(bank_path)),
        },
    )


if __name__ == "__main__":
    main()
