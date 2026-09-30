"""Run the frozen PLT001-PLT030 Vericult batch without loading human labels.

LIVE is evidence acquisition. REPLAY is the primary reported verifier execution.
The script checkpoints one JSONL record per prompt and is safe to resume.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from cultverify import Config, CulturalVerifier
from cultverify.llm import HTTPModel
from cultverify.retrieval import TavilyRetriever

SCHEMA_VERSION = "final-vericult-batch-v1"
EXPECTED_PROMPT_IDS = tuple(f"PLT{i:03d}" for i in range(1, 31))
CANDIDATE_LABELS = "ABCD"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"prompt_id", "prompt", "response_a", "response_b", "response_c", "response_d"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Input must contain columns: {sorted(required)}")
    prompt_ids = tuple(row["prompt_id"] for row in rows)
    if prompt_ids != EXPECTED_PROMPT_IDS:
        raise ValueError("Final input must contain PLT001-PLT030 exactly once and in canonical order")
    if any(not row["prompt"].strip() for row in rows):
        raise ValueError("Every final row requires a nonempty prompt")
    for row in rows:
        if any(not isinstance(row[f"response_{label.lower()}"], str) for label in CANDIDATE_LABELS):
            raise ValueError(f"{row['prompt_id']} contains a non-string response")
    return rows


def winner_label(winner: int | str) -> str:
    if isinstance(winner, int):
        if winner not in range(4):
            raise ValueError(f"Invalid winner index: {winner}")
        return CANDIDATE_LABELS[winner]
    return winner


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def assert_frozen_checkout(manifest: dict) -> None:
    freeze = manifest["freeze_code_commit"]
    try:
        head = _git("rev-parse", "HEAD")
        dirty = _git("status", "--porcelain")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Final experiment must run from a Git checkout") from exc
    if dirty:
        raise RuntimeError("Working tree is dirty; commit or discard changes before the final experiment")
    if head == freeze:
        return
    changed = set(filter(None, _git("diff", "--name-only", f"{freeze}..{head}").splitlines()))
    if changed - {"experiments/final_manifest.json"}:
        raise RuntimeError(
            "Checkout differs from the frozen code revision outside experiments/final_manifest.json: "
            + ", ".join(sorted(changed))
        )


def validate_freeze_files(manifest: dict, dataset: Path, config_path: Path) -> None:
    expected_dataset = manifest["dataset"].get("sha256")
    if expected_dataset and sha256_file(dataset) != expected_dataset:
        raise RuntimeError("Canonical evaluation dataset hash does not match final_manifest.json")
    expected_config = manifest["vericult"].get("config_sha256")
    if expected_config and sha256_file(config_path) != expected_config:
        raise RuntimeError("Verifier config hash does not match final_manifest.json")


def verify_evidence_manifest(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError("REPLAY requires the frozen LIVE evidence manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for record in manifest.get("evidence_files", []):
        evidence_path = Path(record["path"])
        if not evidence_path.is_file() or sha256_file(evidence_path) != record["sha256"]:
            raise RuntimeError(f"Frozen evidence changed or is missing: {evidence_path}")


def load_completed(path: Path, mode: str) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("mode") == mode and record.get("status") == "completed":
            completed.add(record["prompt_id"])
    return completed


def summarize(prompt_id: str, mode: str, ranking) -> dict:
    candidates = []
    for index, candidate in enumerate(ranking.candidates):
        candidates.append(
            {
                "candidate": CANDIDATE_LABELS[index],
                "run_id": candidate.run_id,
                "status": candidate.status,
                "overall_score": candidate.overall_score,
                "vericult_score": candidate.vericult_score,
                "cultural_appropriateness": candidate.cultural_appropriateness,
                "applicable_count": candidate.applicable_count,
                "scored_count": candidate.scored_count,
                "abstained_dimensions": list(candidate.abstained_dimensions),
                "evidence_coverage": candidate.evidence_coverage,
                "targets_truncated": candidate.targets_truncated,
                "trace_path": candidate.trace_path,
                "errors": list(candidate.errors),
            }
        )
    failed = any(candidate["status"] != "completed" for candidate in candidates)
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "prompt_id": prompt_id,
        "status": "failed" if failed else "completed",
        "winner": winner_label(ranking.winner),
        "tied_candidates": [CANDIDATE_LABELS[index] for index in ranking.tied_indices],
        "coverage_comparable": ranking.coverage_comparable,
        "decision_reason": ranking.tie_break_reason,
        "candidates": candidates,
    }


def build_verifier(config: Config) -> CulturalVerifier:
    api_key = os.getenv("OPENROUTER_API_KEY") if config.verifier_model_provider == "openrouter" else None
    llm = HTTPModel(config, api_key)
    if config.mode == "LIVE":
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise RuntimeError("TAVILY_API_KEY is required for the frozen LIVE acquisition")
        retriever = TavilyRetriever(tavily_key, config.search_depth)
    else:
        retriever = None
    return CulturalVerifier(llm=llm, retriever=retriever, config=config)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("LIVE", "REPLAY"))
    parser.add_argument("--input", type=Path, default=Path("data/evaluation/best_of4_v1.csv"))
    parser.add_argument("--config", type=Path, default=Path("experiments/final_vericult_config.json"))
    parser.add_argument("--manifest", type=Path, default=Path("experiments/final_manifest.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=Path("artifacts/final_experiment/evidence_manifest.json"),
    )
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert_frozen_checkout(manifest)
    validate_freeze_files(manifest, args.input, args.config)
    rows = read_rows(args.input)
    if args.mode == "REPLAY":
        verify_evidence_manifest(args.evidence_manifest)

    values = json.loads(args.config.read_text(encoding="utf-8"))
    values["mode"] = args.mode
    trace_root = Path(values["trace_directory"]).parent
    values["trace_directory"] = str(trace_root / args.mode.lower())
    config = Config.model_validate(values)
    verifier = build_verifier(config)

    output = args.output or Path(f"artifacts/final_experiment/results/vericult_{args.mode.lower()}.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = set() if args.no_resume else load_completed(output, args.mode)

    failures = 0
    with output.open("a", encoding="utf-8") as handle:
        for row in rows:
            prompt_id = row["prompt_id"]
            if prompt_id in completed:
                print(f"[{prompt_id}] already completed; skipping", flush=True)
                continue
            responses = [row[f"response_{label}"] for label in "abcd"]
            print(f"[{prompt_id}] {args.mode} starting", flush=True)
            ranking = verifier.rank(row["prompt"], responses)
            record = summarize(prompt_id, args.mode, ranking)
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            if record["status"] != "completed":
                failures += 1
                print(f"[{prompt_id}] failed; checkpoint saved", file=sys.stderr, flush=True)
            else:
                print(f"[{prompt_id}] completed -> {record['winner']}", flush=True)

    if failures:
        print(f"Final batch completed with {failures} failed prompt(s); rerun with resume after fixing execution issues.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
