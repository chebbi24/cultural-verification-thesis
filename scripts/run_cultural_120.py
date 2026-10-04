"""Run Vericult on the 120 exact cultural prompt-response pairs.

This is separate from the frozen PLT001-PLT030 Best-of-4 experiment runner.
Each source record is evaluated independently as one prompt + one associated response.
Results checkpoint to JSONL after every record and completed records are skipped on resume.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from cultverify import Config, CulturalVerifier
from cultverify.llm import HTTPModel
from cultverify.retrieval import TavilyRetriever

RECORD_RE = re.compile(r"(?m)^RECORD (\\d{3})\\n")


def parse_records(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    matches = list(RECORD_RE.finditer(text))
    records: list[dict[str, str]] = []
    for pos, match in enumerate(matches):
        start = match.end()
        end = matches[pos + 1].start() if pos + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        block = re.sub(r"\\n={80}\\s*$", "", block).strip()
        if "\\nPROMPT:\\n" not in block or "\\nRESPONSE:\\n" not in block:
            raise ValueError(f"Record {match.group(1)} is missing PROMPT/RESPONSE markers")
        meta_text, rest = block.split("\\nPROMPT:\\n", 1)
        prompt, response = rest.split("\\nRESPONSE:\\n", 1)
        meta: dict[str, str] = {}
        for line in meta_text.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                meta[key] = value
        records.append(
            {
                "record_id": match.group(1),
                "dataset": meta.get("DATASET", ""),
                "culture": meta.get("CULTURE/COUNTRY", ""),
                "language": meta.get("LANGUAGE", ""),
                "source_split": meta.get("SOURCE_SPLIT/CONFIG", ""),
                "source_row_id": meta.get("SOURCE_ROW/ID", ""),
                "source_url": meta.get("SOURCE_URL", ""),
                "response_type": meta.get("RESPONSE_TYPE", ""),
                "prompt": prompt.strip(),
                "response": response.strip(),
            }
        )
    if len(records) != 120:
        raise ValueError(f"Expected exactly 120 records, found {len(records)}")
    return records


def completed_ids(path: Path, mode: str) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("mode") == mode and row.get("status") == "completed":
            done.add(str(row["record_id"]))
    return done


def build_verifier(config: Config) -> CulturalVerifier:
    api_key = os.getenv("OPENROUTER_API_KEY") if config.verifier_model_provider == "openrouter" else None
    llm = HTTPModel(config, api_key)
    if config.mode == "LIVE":
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise RuntimeError("TAVILY_API_KEY is required in LIVE mode")
        retriever = TavilyRetriever(tavily_key, config.search_depth)
    else:
        retriever = None
    return CulturalVerifier(llm=llm, retriever=retriever, config=config)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("vericult_cultural_prompts_120_exact.txt"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/final_vericult_config.json"),
    )
    parser.add_argument("--mode", choices=("LIVE", "REPLAY"), default="LIVE")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/cultural_120/results.jsonl"),
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/cultural_120"),
    )
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Optional smoke-test limit")
    args = parser.parse_args()

    records = parse_records(args.input)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be >= 1")
        records = records[: args.limit]

    values = json.loads(args.config.read_text(encoding="utf-8"))
    values["mode"] = args.mode
    values["cache_directory"] = str(args.artifact_root / "evidence")
    values["trace_directory"] = str(args.artifact_root / "traces" / args.mode.lower())
    config = Config.model_validate(values)
    verifier = build_verifier(config)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = set() if args.no_resume else completed_ids(args.output, args.mode)

    total = len(records)
    completed = failed = skipped = 0

    with args.output.open("a", encoding="utf-8") as handle:
        for index, item in enumerate(records, 1):
            rid = item["record_id"]
            if rid in done:
                skipped += 1
                print(f"[{index}/{total}] RECORD {rid} already completed; skipping", flush=True)
                continue

            print(
                f"\\n[{index}/{total}] RECORD {rid} | {item['dataset']} | {item['culture']} starting",
                flush=True,
            )
            try:
                result = verifier.verify(prompt=item["prompt"], response=item["response"])
                row = {
                    **item,
                    "mode": args.mode,
                    "status": result.status,
                    "score": result.vericult_score,
                    "overall_score": result.overall_score,
                    "label": result.cultural_appropriateness,
                    "applicable_count": result.applicable_count,
                    "scored_count": result.scored_count,
                    "abstained_dimensions": list(result.abstained_dimensions),
                    "evidence_coverage": result.evidence_coverage,
                    "targets_truncated": result.targets_truncated,
                    "errors": list(result.errors),
                    "trace_path": result.trace_path,
                    "run_id": result.run_id,
                }
            except Exception as exc:
                row = {
                    **item,
                    "mode": args.mode,
                    "status": "exception",
                    "score": None,
                    "overall_score": None,
                    "label": None,
                    "errors": [f"{type(exc).__name__}: {exc}"],
                    "trace_path": None,
                    "run_id": None,
                }

            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\\n")
            handle.flush()

            if row["status"] == "completed":
                completed += 1
            else:
                failed += 1

            print("STATUS:", row["status"], flush=True)
            print("SCORE:", row.get("score"), flush=True)
            print("LABEL:", row.get("label"), flush=True)
            print("ERRORS:", row.get("errors"), flush=True)

    print("\\nFINAL CULTURAL-120 SUMMARY")
    print("=" * 80)
    print(f"Completed this invocation: {completed}")
    print(f"Failed this invocation:    {failed}")
    print(f"Skipped from resume:       {skipped}")
    print(f"Output:                    {args.output}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
