"""Audit and freeze LIVE evidence for the final 360 single-response items."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.run_final_experiment import experiment_identity, load_final_rows
from cultverify.trace import digest


FINAL_CORPUS_ORDER = ("plt120", "external120", "redteam120")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_item_ids(manifest: dict[str, Any]) -> tuple[str, ...]:
    ids: list[str] = []
    for corpus_name in FINAL_CORPUS_ORDER:
        spec = manifest["dataset"]["corpora"][corpus_name]
        prefix = spec["id_prefix"]
        count = int(spec["items"])
        ids.extend(f"{prefix}{i:03d}" for i in range(1, count + 1))
    return tuple(ids)


def latest_records(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        item_id = record.get("item_id")
        if not item_id:
            raise RuntimeError("LIVE output contains a record without item_id")
        records[item_id] = record
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
        "--manifest",
        type=Path,
        default=Path("experiments/final_manifest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/final_experiment/evidence_manifest.json"),
    )
    args = parser.parse_args(argv)

    experiment_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected_ids = expected_item_ids(experiment_manifest)
    records = latest_records(args.live_output)
    execution_id = experiment_identity(experiment_manifest)
    frozen_rows = {row["item_id"]: row for row in load_final_rows(experiment_manifest, "all")}

    expected_set = set(expected_ids)
    if set(records) != expected_set or len(records) != len(expected_ids):
        missing = [item_id for item_id in expected_ids if item_id not in records]
        extra = [item_id for item_id in records if item_id not in expected_set]
        raise RuntimeError(
            f"LIVE output does not contain exactly the 360 frozen items. Missing={missing[:12]} Extra={extra[:12]}"
        )
    if any(record.get("mode") != "LIVE" or record.get("status") != "completed" for record in records.values()):
        raise RuntimeError("Every final LIVE item must be completed before evidence is frozen")
    for item_id, record in records.items():
        row = frozen_rows[item_id]
        if (
            record.get("execution_id") != execution_id
            or record.get("prompt_sha256") != row["prompt_sha256"]
            or record.get("response_sha256") != row["response_sha256"]
        ):
            raise RuntimeError(f"LIVE checkpoint belongs to a different frozen execution: {item_id}")

    trace_paths: list[Path] = []
    referenced_snapshots: set[str] = set()
    for item_id in expected_ids:
        record = records[item_id]
        trace_path = Path(record["trace_path"])
        if not trace_path.is_file():
            raise RuntimeError(f"Missing response trace for {item_id}: {trace_path}")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        if (
            trace.get("mode") != "LIVE"
            or trace.get("run_id") != record.get("run_id")
            or trace.get("prompt_hash") != digest(frozen_rows[item_id]["prompt"])
            or trace.get("response_hash") != digest(frozen_rows[item_id]["response"])
        ):
            raise RuntimeError(f"Trace mismatch for {item_id}")
        result = trace.get("result", {})
        if result.get("trace_path") != str(trace_path.resolve()):
            raise RuntimeError(f"Trace path self-reference mismatch for {item_id}")
        trace_paths.append(trace_path)
        for bundle in result.get("evidence", []):
            for snapshot in bundle.get("snapshots", []):
                snapshot_id = snapshot.get("snapshot_id")
                if snapshot_id:
                    referenced_snapshots.add(snapshot_id)

    if len(trace_paths) != len(expected_ids):
        raise RuntimeError(f"Expected {len(expected_ids)} response traces, found {len(trace_paths)}")

    evidence_files = sorted(args.evidence_dir.glob("*.json"))
    evidence_names = {path.stem for path in evidence_files}
    missing_snapshots = sorted(referenced_snapshots - evidence_names)
    if missing_snapshots:
        raise RuntimeError("Missing referenced frozen snapshots: " + ", ".join(missing_snapshots))

    dataset_hashes = {
        name: {
            "path": experiment_manifest["dataset"]["corpora"][name]["path"],
            "semantic_sha256": experiment_manifest["dataset"]["corpora"][name]["semantic_sha256"],
            "sha256": sha256_file(Path(experiment_manifest["dataset"]["corpora"][name]["path"])),
        }
        for name in FINAL_CORPUS_ORDER
    }

    manifest = {
        "schema_version": "final-evidence-freeze-v3",
        "execution_id": execution_id,
        "experiment_id": experiment_manifest["experiment_id"],
        "live_output": {
            "path": str(args.live_output),
            "sha256": sha256_file(args.live_output),
        },
        "dataset_sha256": dataset_hashes,
        "n_items": len(records),
        "n_response_traces": len(trace_paths),
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
        f"Frozen {manifest['n_items']} items, {manifest['n_response_traces']} response traces, "
        f"{manifest['n_referenced_snapshots']} referenced snapshots, and "
        f"{len(evidence_files)} evidence/schedule files -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
