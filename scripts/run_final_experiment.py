"""Run the frozen 360-item single-response Vericult experiment.

LIVE acquires and snapshots evidence. REPLAY is the primary reported Vericult
execution. The runner never loads human labels and checkpoints one JSONL record
per prompt-response pair, so interrupted runs are safe to resume.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from cultverify import Config, CulturalVerifier
from cultverify.llm import HTTPModel
from cultverify.retrieval import TavilyRetriever
from cultverify.trace import digest

SCHEMA_VERSION = "final-vericult-single-v1"
FINAL_CORPUS_ORDER = ("plt120", "external120", "redteam120")
POST_FREEZE_ALLOWED_FILES = {
    "experiments/final_manifest.json",
    "docs/final_validation.md",
    "data/generated/gpt_oss_120b/plt120_generated.csv",
    "data/generated/gpt_oss_120b/external120_generated.csv",
    "data/generated/gpt_oss_120b/redteam120_generated.csv",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def expected_item_ids(spec: dict[str, Any]) -> tuple[str, ...]:
    prefix = spec["id_prefix"]
    count = int(spec["items"])
    return tuple(f"{prefix}{i:03d}" for i in range(1, count + 1))


def read_generated_rows(
    path: Path, corpus_name: str, spec: dict[str, Any], generator: dict[str, Any]
) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    required = {
        "corpus",
        "item_id",
        "source_dataset",
        "source_record_id",
        "language",
        "culture",
        "prompt",
        "prompt_sha256",
        "generator_model",
        "temperature",
        "top_p",
        "max_tokens",
        "response",
        "response_sha256",
        "generated_at",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"{corpus_name}: generated CSV must contain columns: {sorted(required)}")

    expected_ids = expected_item_ids(spec)
    item_ids = tuple(row["item_id"].strip() for row in rows)
    if item_ids != expected_ids:
        raise ValueError(
            f"{corpus_name}: expected {len(expected_ids)} canonical IDs "
            f"{expected_ids[0]}-{expected_ids[-1]} exactly once and in order"
        )

    expected_corpus_value = spec.get("generator_corpus", corpus_name)
    expected_model = generator["model_id"]
    expected_sampling = generator["sampling"]

    normalized: list[dict[str, str]] = []
    for row in rows:
        item_id = row["item_id"].strip()
        prompt = row["prompt"]
        response = row["response"]
        if not prompt.strip():
            raise ValueError(f"{corpus_name}/{item_id}: prompt is empty")
        if not response.strip():
            raise ValueError(f"{corpus_name}/{item_id}: generated response is empty")
        if row["corpus"].strip() != expected_corpus_value:
            raise ValueError(
                f"{corpus_name}/{item_id}: corpus field {row['corpus']!r} does not match {expected_corpus_value!r}"
            )
        if sha256_text(prompt) != row["prompt_sha256"].strip():
            raise ValueError(f"{corpus_name}/{item_id}: prompt SHA-256 mismatch")
        if sha256_text(response) != row["response_sha256"].strip():
            raise ValueError(f"{corpus_name}/{item_id}: response SHA-256 mismatch")
        if row["generator_model"].strip() != expected_model:
            raise ValueError(f"{corpus_name}/{item_id}: generator model differs from frozen manifest")
        if row["temperature"].strip() != str(expected_sampling["temperature"]):
            raise ValueError(f"{corpus_name}/{item_id}: temperature differs from frozen manifest")
        if row["top_p"].strip() != str(expected_sampling["top_p"]):
            raise ValueError(f"{corpus_name}/{item_id}: top_p differs from frozen manifest")
        if row["max_tokens"].strip() != str(expected_sampling["max_tokens"]):
            raise ValueError(f"{corpus_name}/{item_id}: max_tokens differs from frozen manifest")

        normalized.append(
            {
                "corpus": corpus_name,
                "item_id": item_id,
                "source_dataset": row["source_dataset"].strip(),
                "source_record_id": row["source_record_id"].strip(),
                "language": row["language"].strip(),
                "culture": row["culture"].strip(),
                "prompt": prompt,
                "prompt_sha256": row["prompt_sha256"].strip(),
                "response": response,
                "response_sha256": row["response_sha256"].strip(),
                "generator_model": row["generator_model"].strip(),
                "temperature": row["temperature"].strip(),
                "top_p": row["top_p"].strip(),
                "max_tokens": row["max_tokens"].strip(),
                "generated_at": row["generated_at"].strip(),
                "prompt_tokens": row["prompt_tokens"].strip(),
                "completion_tokens": row["completion_tokens"].strip(),
                "total_tokens": row["total_tokens"].strip(),
            }
        )
    return normalized


def semantic_dataset_sha256(rows: list[dict[str, str]]) -> str:
    """Hash the frozen semantic input independently of CSV newline/quoting details."""
    payload = [
        {
            "generator_model": row["generator_model"],
            "item_id": row["item_id"],
            "max_tokens": row["max_tokens"],
            "prompt_sha256": row["prompt_sha256"],
            "response_sha256": row["response_sha256"],
            "temperature": row["temperature"],
            "top_p": row["top_p"],
        }
        for row in rows
    ]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_final_rows(manifest: dict[str, Any], corpus: str = "all") -> list[dict[str, str]]:
    corpora = manifest["dataset"]["corpora"]
    names = FINAL_CORPUS_ORDER if corpus == "all" else (corpus,)
    if any(name not in corpora for name in names):
        missing = [name for name in names if name not in corpora]
        raise ValueError(f"Manifest is missing final corpus specification(s): {missing}")

    rows: list[dict[str, str]] = []
    for name in names:
        spec = corpora[name]
        rows.extend(
            read_generated_rows(
                Path(spec["path"]),
                name,
                spec,
                manifest["generator"],
            )
        )

    item_ids = [row["item_id"] for row in rows]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("Final 360-item input contains duplicate item IDs")
    if corpus == "all" and len(rows) != int(manifest["dataset"]["items"]):
        raise ValueError(f"Final manifest expects {manifest['dataset']['items']} items, found {len(rows)}")
    return rows


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def assert_frozen_checkout(manifest: dict[str, Any]) -> None:
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
    unexpected = changed - POST_FREEZE_ALLOWED_FILES
    if unexpected:
        raise RuntimeError(
            "Checkout differs from the frozen semantic revision outside the permitted "
            "metadata/frozen-input files: " + ", ".join(sorted(unexpected))
        )


def validate_freeze_files(manifest: dict[str, Any], config_path: Path) -> dict[str, str]:
    expected_config = manifest["vericult"].get("config_sha256")
    if expected_config and sha256_file(config_path) != expected_config:
        raise RuntimeError("Verifier config hash does not match final_manifest.json")

    hashes: dict[str, str] = {}
    for corpus_name in FINAL_CORPUS_ORDER:
        spec = manifest["dataset"]["corpora"][corpus_name]
        path = Path(spec["path"])
        if not path.is_file():
            raise RuntimeError(f"Frozen generated dataset is missing: {path}")
        rows = read_generated_rows(path, corpus_name, spec, manifest["generator"])
        actual = semantic_dataset_sha256(rows)
        expected = spec.get("semantic_sha256")
        if expected and actual != expected:
            raise RuntimeError(f"Frozen generated dataset semantic hash mismatch: {path}")
        hashes[corpus_name] = actual
    return hashes


def verify_runtime_manifest(path: Path, manifest: dict[str, Any], config_path: Path) -> None:
    if not path.is_file():
        raise RuntimeError("Final experiment requires the captured runtime manifest")
    runtime = json.loads(path.read_text(encoding="utf-8"))
    if runtime.get("config_sha256") != sha256_file(config_path):
        raise RuntimeError("Runtime manifest was captured for a different verifier config")
    expected_hashes = validate_freeze_files(manifest, config_path)
    if runtime.get("dataset_sha256") != expected_hashes:
        raise RuntimeError("Runtime manifest was captured for different generated datasets")
    if not runtime.get("verifier_model", {}).get("digest"):
        raise RuntimeError("Runtime manifest does not contain a frozen verifier model identity")
    if runtime.get("execution_id") != experiment_identity(manifest):
        raise RuntimeError("Runtime manifest belongs to a different code/input/config freeze")
    if runtime["verifier_model"].get("provider") != manifest["vericult"]["provider"]:
        raise RuntimeError("Runtime verifier provider differs from the frozen manifest")
    if runtime["verifier_model"].get("requested_id") != manifest["vericult"]["backbone"]:
        raise RuntimeError("Runtime verifier model differs from the frozen manifest")


def verify_evidence_manifest(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError("REPLAY requires the frozen LIVE evidence manifest")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for record in manifest.get("evidence_files", []):
        evidence_path = Path(record["path"])
        if not evidence_path.is_file() or sha256_file(evidence_path) != record["sha256"]:
            raise RuntimeError(f"Frozen evidence changed or is missing: {evidence_path}")
    for record in manifest.get("trace_files", []):
        trace_path = Path(record["path"])
        if not trace_path.is_file() or sha256_file(trace_path) != record["sha256"]:
            raise RuntimeError(f"Frozen LIVE trace changed or is missing: {trace_path}")


def experiment_identity(manifest: dict[str, Any]) -> str:
    """Stable identity of code, inputs, model choice and config for safe resumption."""
    payload = {
        "experiment_id": manifest["experiment_id"],
        "freeze_code_commit": manifest["freeze_code_commit"],
        "config_sha256": manifest["vericult"]["config_sha256"],
        "semantic_datasets": {
            name: manifest["dataset"]["corpora"][name]["semantic_sha256"] for name in FINAL_CORPUS_ORDER
        },
        "provider": manifest["vericult"]["provider"],
        "model": manifest["vericult"]["backbone"],
    }
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def validate_frozen_model(config: Config, manifest: dict[str, Any]) -> None:
    """Disallow silent model/endpoint changes via environment overrides."""
    if config.verifier_model_provider != manifest["vericult"]["provider"]:
        raise RuntimeError("Effective verifier provider differs from the frozen manifest")
    if config.verifier_model_id != manifest["vericult"]["backbone"]:
        raise RuntimeError("Effective verifier model differs from the frozen manifest")
    if config.verifier_model_provider == "l3s" and config.l3s_api_url != manifest["vericult"]["api_endpoint"]:
        raise RuntimeError("Effective L3S endpoint differs from the frozen manifest")


def read_checkpoint_records(path: Path) -> list[dict[str, Any]]:
    """Recover only a torn final JSONL write, keeping a complete backup."""
    if not path.exists():
        return []
    records = []
    with path.open("rb+") as handle:
        while True:
            start = handle.tell()
            raw = handle.readline()
            if not raw:
                break
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if not raw.endswith(b"\n") and handle.tell() == os.fstat(handle.fileno()).st_size:
                    backup = path.with_name(path.name + ".interrupted.bak")
                    if backup.exists():
                        raise RuntimeError(f"Checkpoint recovery backup already exists: {backup}") from exc
                    shutil.copy2(path, backup)
                    handle.truncate(start)
                    break
                raise RuntimeError(f"Corrupt non-final JSONL record in {path}") from exc
            if not isinstance(record, dict):
                raise RuntimeError(f"Non-object JSONL checkpoint record in {path}")
            records.append(record)
            if not raw.endswith(b"\n"):
                handle.write(b"\n")
    return records


def _completed_trace_is_valid(record: dict[str, Any], row: dict[str, str]) -> bool:
    path_text = record.get("trace_path")
    if not isinstance(path_text, str) or not path_text:
        return False
    try:
        trace = json.loads(Path(path_text).read_text(encoding="utf-8"))
        return (
            trace.get("mode") == record["mode"]
            and trace.get("run_id") == record.get("run_id")
            and trace.get("prompt_hash") == digest(row["prompt"])
            and trace.get("response_hash") == digest(row["response"])
            and trace.get("result", {}).get("status") == "completed"
        )
    except (OSError, ValueError, TypeError):
        return False


def load_completed(
    path: Path,
    mode: str,
    *,
    execution_id: str | None = None,
    rows_by_id: dict[str, dict[str, str]] | None = None,
) -> set[str]:
    """Only skip the most recent valid completion under the exact current freeze."""
    latest = {}
    for record in read_checkpoint_records(path):
        if record.get("mode") == mode and record.get("item_id"):
            latest[record["item_id"]] = record

    completed = set()
    for item_id, record in latest.items():
        if record.get("status") != "completed":
            continue
        if execution_id is not None:
            row = (rows_by_id or {}).get(item_id)
            if (
                row is None
                or record.get("execution_id") != execution_id
                or record.get("prompt_sha256") != row["prompt_sha256"]
                or record.get("response_sha256") != row["response_sha256"]
                or not _completed_trace_is_valid(record, row)
            ):
                continue
        completed.add(item_id)
    return completed


def execute_item(verifier, row: dict[str, str], mode: str, execution_id: str) -> dict[str, Any]:
    """Isolate unanticipated candidate exceptions without swallowing interrupts."""
    try:
        record = summarize(row, mode, verifier.verify(row["prompt"], row["response"]))
    except Exception as exc:
        # Do not persist raw exception bodies: provider exceptions could expose request data.
        record = {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "corpus": row["corpus"],
            "item_id": row["item_id"],
            "prompt_sha256": row["prompt_sha256"],
            "response_sha256": row["response_sha256"],
            "status": "failed",
            "run_id": None,
            "trace_path": None,
            "errors": [f"unhandled:{type(exc).__name__}"],
        }
    record["execution_id"] = execution_id
    return record


def summarize(row: dict[str, str], mode: str, result) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "corpus": row["corpus"],
        "item_id": row["item_id"],
        "source_dataset": row["source_dataset"],
        "source_record_id": row["source_record_id"],
        "language": row["language"],
        "culture": row["culture"],
        "prompt_sha256": row["prompt_sha256"],
        "response_sha256": row["response_sha256"],
        "generator_model": row["generator_model"],
        "status": result.status,
        "run_id": result.run_id,
        "cultural_appropriateness": result.cultural_appropriateness,
        "overall_score": result.overall_score,
        "vericult_score": result.vericult_score,
        "abstention_reason": result.abstention_reason,
        "applicable_count": result.applicable_count,
        "scored_count": result.scored_count,
        "abstained_dimensions": list(result.abstained_dimensions),
        "evidence_coverage": result.evidence_coverage,
        "targets_truncated": result.targets_truncated,
        "dimension_scores": [
            {
                "dimension_id": score.dimension_id,
                "score": score.score,
                "rationale": score.rationale,
                "response_quotes": list(score.response_quotes),
                "target_ids": list(score.target_ids),
                "memo_ids": list(score.memo_ids),
            }
            for score in result.dimension_scores
        ],
        "trace_path": result.trace_path,
        "errors": list(result.errors),
    }


def build_verifier(config: Config) -> CulturalVerifier:
    api_key = (
        os.getenv("OPENROUTER_API_KEY")
        if config.verifier_model_provider == "openrouter"
        else os.getenv("L3S_API_KEY")
        if config.verifier_model_provider == "l3s"
        else None
    )
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
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("LIVE", "REPLAY"))
    parser.add_argument("--corpus", choices=("all",) + FINAL_CORPUS_ORDER, default="all")
    parser.add_argument("--config", type=Path, default=Path("experiments/final_vericult_config.json"))
    parser.add_argument("--manifest", type=Path, default=Path("experiments/final_manifest.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=Path("artifacts/final_experiment/runtime_manifest.json"),
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=Path("artifacts/final_experiment/evidence_manifest.json"),
    )
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert_frozen_checkout(manifest)
    validate_freeze_files(manifest, args.config)
    rows = load_final_rows(manifest, args.corpus)
    verify_runtime_manifest(args.runtime_manifest, manifest, args.config)
    if args.mode == "REPLAY":
        verify_evidence_manifest(args.evidence_manifest)

    values = json.loads(args.config.read_text(encoding="utf-8"))
    env_overrides = {
        "verifier_model_provider": os.getenv("CULTVERIFY_PROVIDER"),
        "verifier_model_id": os.getenv("CULTVERIFY_MODEL"),
        "ollama_url": os.getenv("OLLAMA_URL"),
        "l3s_api_url": os.getenv("L3S_API_URL"),
    }
    values.update({key: value for key, value in env_overrides.items() if value})
    values["mode"] = args.mode
    trace_root = Path(values["trace_directory"]).parent
    values["trace_directory"] = str(trace_root / args.mode.lower())
    config = Config.model_validate(values)
    validate_frozen_model(config, manifest)
    runtime_model = json.loads(args.runtime_manifest.read_text(encoding="utf-8"))["verifier_model"]
    if config.verifier_model_provider == "l3s" and runtime_model.get("api_url") != config.l3s_api_url:
        raise RuntimeError("Runtime L3S endpoint differs from the effective verifier config")
    verifier = build_verifier(config)
    execution_id = experiment_identity(manifest)

    output = args.output or Path(f"artifacts/final_experiment/results/vericult_{args.mode.lower()}.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = set() if args.no_resume else load_completed(
        output, args.mode, execution_id=execution_id, rows_by_id={row["item_id"]: row for row in rows}
    )
    if args.no_resume and output.is_file() and output.stat().st_size:
        raise RuntimeError("--no-resume requires an empty/new --output; refusing to append duplicate results")

    failures = 0
    with output.open("a", encoding="utf-8") as handle:
        for index, row in enumerate(rows, 1):
            item_id = row["item_id"]
            if item_id in completed:
                print(f"[{item_id}] already completed; skipping", flush=True)
                continue
            print(f"[{index}/{len(rows)}] [{item_id}] {args.mode} starting", flush=True)
            record = execute_item(verifier, row, args.mode, execution_id)
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            if record["status"] != "completed":
                failures += 1
                print(f"[{item_id}] failed; checkpoint saved", file=sys.stderr, flush=True)
            else:
                print(
                    f"[{item_id}] completed -> {record['cultural_appropriateness']}",
                    flush=True,
                )

    if failures:
        print(
            f"Final batch completed with {failures} failed item(s); rerun with resume "
            "after fixing execution-only issues."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
