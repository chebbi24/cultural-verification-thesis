"""Audit and freeze LIVE evidence before the primary REPLAY experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_PROMPT_IDS = tuple(f"PLT{i:03d}" for i in range(1, 31))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_records(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[record["prompt_id"]] = record
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-output",
        type=Path,
        default=Path("artifacts/final_experiment/results/vericult_live.jsonl"),
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path("artifacts/final_experiment/evidence"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/final_experiment/evidence_manifest.json"),
    )
    args = parser.parse_args(argv)

    records = latest_records(args.live_output)
    if tuple(records) != EXPECTED_PROMPT_IDS:
        raise RuntimeError("LIVE output does not contain exactly PLT001-PLT030 in canonical order")
    if any(record.get("mode") != "LIVE" or record.get("status") != "completed" for record in records.values()):
        raise RuntimeError("Every final LIVE prompt must be completed before evidence is frozen")

    trace_paths: list[Path] = []
    referenced_snapshots: set[str] = set()
    for record in records.values():
        candidates = record.get("candidates", [])
        if len(candidates) != 4:
            raise RuntimeError(f"{record['prompt_id']} does not contain four candidate summaries")
        for candidate in candidates:
            trace_path = Path(candidate["trace_path"])
            if not trace_path.is_file():
                raise RuntimeError(f"Missing candidate trace: {trace_path}")
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            if trace.get("mode") != "LIVE" or trace.get("run_id") != candidate["run_id"]:
                raise RuntimeError(f"Trace mismatch for {record['prompt_id']} candidate {candidate['candidate']}")
            trace_paths.append(trace_path)
            for bundle in trace["result"].get("evidence", []):
                for snapshot in bundle.get("snapshots", []):
                    referenced_snapshots.add(snapshot["snapshot_id"])

    evidence_files = sorted(args.evidence_dir.glob("*.json"))
    evidence_names = {path.stem for path in evidence_files}
    missing = sorted(referenced_snapshots - evidence_names)
    if missing:
        raise RuntimeError("Missing referenced frozen snapshots: " + ", ".join(missing))

    manifest = {
        "schema_version": "final-evidence-freeze-v1",
        "live_output": {
            "path": str(args.live_output),
            "sha256": sha256_file(args.live_output),
        },
        "n_prompts": len(records),
        "n_candidate_traces": len(trace_paths),
        "n_referenced_snapshots": len(referenced_snapshots),
        "evidence_directory": str(args.evidence_dir),
        "evidence_files": [
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in evidence_files
        ],
        "trace_files": [
            {
                "path": str(path),
                "sha256": sha256_file(path),
            }
            for path in sorted(trace_paths)
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Frozen {manifest['n_prompts']} prompts, {manifest['n_candidate_traces']} traces, "
        f"and {len(evidence_files)} evidence/schedule files -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
