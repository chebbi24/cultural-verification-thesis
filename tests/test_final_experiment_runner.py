import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.preflight_final_experiment import find_ollama_model, tags_url
from scripts.audit_final_evidence import main as audit_evidence_main
from cultverify import Config
from cultverify.trace import digest
from scripts.run_final_experiment import (
    execute_item,
    experiment_identity,
    expected_item_ids,
    load_completed,
    read_checkpoint_records,
    read_generated_rows,
    semantic_dataset_sha256,
    sha256_file,
    validate_frozen_model,
    verify_evidence_manifest,
    verify_runtime_manifest,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _generator():
    return {
        "model_id": "gpt-oss:120b-mxfp4",
        "sampling": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 1200},
    }


def _write_generated(path: Path, corpus: str, prefix: str, count: int = 2) -> None:
    fields = [
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
    ]
    rows = []
    for i in range(1, count + 1):
        prompt = f"prompt {i}"
        response = f"response {i}"
        rows.append(
            {
                "corpus": corpus,
                "item_id": f"{prefix}{i:03d}",
                "source_dataset": "fixture",
                "source_record_id": str(i),
                "language": "English",
                "culture": "fixture",
                "prompt": prompt,
                "prompt_sha256": _sha(prompt),
                "generator_model": "gpt-oss:120b-mxfp4",
                "temperature": "0.8",
                "top_p": "0.95",
                "max_tokens": "1200",
                "response": response,
                "response_sha256": _sha(response),
                "generated_at": "2026-10-08T00:00:00+00:00",
                "prompt_tokens": "10",
                "completion_tokens": "20",
                "total_tokens": "30",
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_generated_single_response_reader_validates_canonical_ids_and_hashes(tmp_path):
    path = tmp_path / "generated.csv"
    _write_generated(path, "plt120", "PLT")
    spec = {
        "items": 2,
        "id_prefix": "PLT",
        "generator_corpus": "plt120",
    }
    rows = read_generated_rows(path, "plt120", spec, _generator())
    assert [row["item_id"] for row in rows] == ["PLT001", "PLT002"]
    assert rows[0]["response"] == "response 1"
    assert expected_item_ids(spec) == ("PLT001", "PLT002")


def test_generated_single_response_reader_rejects_mutated_response(tmp_path):
    path = tmp_path / "generated.csv"
    _write_generated(path, "plt120", "PLT")
    text = path.read_text(encoding="utf-8").replace("response 2", "mutated", 1)
    path.write_text(text, encoding="utf-8")
    spec = {"items": 2, "id_prefix": "PLT", "generator_corpus": "plt120"}
    with pytest.raises(ValueError, match="response SHA-256 mismatch"):
        read_generated_rows(path, "plt120", spec, _generator())


def test_final_runner_resume_only_skips_completed_matching_mode(tmp_path):
    output = tmp_path / "results.jsonl"
    records = [
        {"mode": "LIVE", "status": "completed", "item_id": "PLT001"},
        {"mode": "LIVE", "status": "failed", "item_id": "PLT002"},
        {"mode": "REPLAY", "status": "completed", "item_id": "EXT003"},
    ]
    output.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    assert load_completed(output, "LIVE") == {"PLT001"}
    assert load_completed(output, "REPLAY") == {"EXT003"}


def test_runtime_manifest_must_match_config_and_all_dataset_hashes(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"model": "fixture"}\n', encoding="utf-8")

    corpora = {}
    runtime_hashes = {}
    generator = _generator()
    for name, prefix in (("plt120", "PLT"), ("external120", "EXT"), ("redteam120", "RT")):
        path = tmp_path / f"{name}.csv"
        _write_generated(path, name, prefix)
        spec = {
            "path": str(path),
            "items": 2,
            "id_prefix": prefix,
            "generator_corpus": name,
        }
        rows = read_generated_rows(path, name, spec, generator)
        digest = semantic_dataset_sha256(rows)
        spec["semantic_sha256"] = digest
        corpora[name] = spec
        runtime_hashes[name] = digest

    manifest = {
        "experiment_id": "fixture-6",
        "freeze_code_commit": "fixture-code",
        "dataset": {"corpora": corpora},
        "generator": generator,
        "vericult": {
            "config_sha256": sha256_file(config),
            "provider": "l3s",
            "backbone": "fixture-model",
        },
    }
    runtime = tmp_path / "runtime.json"
    runtime.write_text(
        json.dumps(
            {
                "config_sha256": sha256_file(config),
                "dataset_sha256": runtime_hashes,
                "verifier_model": {"digest": "remote:fixture", "provider": "l3s", "requested_id": "fixture-model"},
                "execution_id": experiment_identity(manifest),
            }
        ),
        encoding="utf-8",
    )
    verify_runtime_manifest(runtime, manifest, config)

    config.write_text('{"model": "changed"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="different verifier config"):
        verify_runtime_manifest(runtime, manifest, config)


def test_replay_evidence_manifest_detects_evidence_or_trace_mutation(tmp_path):
    evidence = tmp_path / "snapshot.json"
    evidence.write_text('{"frozen": true}\n', encoding="utf-8")
    trace = tmp_path / "trace.json"
    trace.write_text('{"frozen": true}\n', encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "evidence_files": [{"path": str(evidence), "sha256": sha256_file(evidence)}],
                "trace_files": [{"path": str(trace), "sha256": sha256_file(trace)}],
            }
        ),
        encoding="utf-8",
    )
    verify_evidence_manifest(manifest)

    trace.write_text('{"frozen": false}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="Frozen LIVE trace changed"):
        verify_evidence_manifest(manifest)


def test_preflight_resolves_ollama_registry_and_frozen_model():
    assert tags_url("http://localhost:11434/api/chat") == "http://localhost:11434/api/tags"
    model = find_ollama_model(
        [{"name": "qwen3:4b", "digest": "abc"}, {"name": "other:latest", "digest": "def"}],
        "qwen3:4b",
    )
    assert model["digest"] == "abc"
    with pytest.raises(RuntimeError, match="not installed"):
        find_ollama_model([], "qwen3:4b")


def test_execution_identity_changes_with_freeze_revision():
    manifest = {
        "experiment_id": "fixture",
        "freeze_code_commit": "v1",
        "dataset": {"corpora": {name: {"semantic_sha256": name} for name in ("plt120", "external120", "redteam120")}},
        "vericult": {"config_sha256": "config", "provider": "l3s", "backbone": "model"},
    }
    v1 = experiment_identity(manifest)
    assert v1 != experiment_identity({**manifest, "freeze_code_commit": "v2"})


def test_final_provider_cannot_be_overridden_by_environment():
    manifest = {
        "vericult": {
            "provider": "l3s",
            "backbone": "model-a",
            "api_endpoint": "https://server.test/v1/chat/completions",
        }
    }
    frozen = Config(
        verifier_model_provider="l3s", verifier_model_id="model-a", l3s_api_url=manifest["vericult"]["api_endpoint"]
    )
    validate_frozen_model(frozen, manifest)
    with pytest.raises(RuntimeError, match="model differs"):
        validate_frozen_model(frozen.model_copy(update={"verifier_model_id": "model-b"}), manifest)
    with pytest.raises(RuntimeError, match="endpoint differs"):
        validate_frozen_model(frozen.model_copy(update={"l3s_api_url": "https://wrong.test/api"}), manifest)


def test_unexpected_item_exception_is_checkpointed_and_interrupts_are_not_swallowed():
    row = {
        "item_id": "PLT001",
        "corpus": "plt120",
        "prompt": "Example",
        "response": "Example answer",
        "prompt_sha256": _sha("Example"),
        "response_sha256": _sha("Example answer"),
    }

    class BadVerifier:
        def verify(self, prompt, response):
            raise ValueError("Potentially sensitive raw provider error")

    record = execute_item(BadVerifier(), row, "LIVE", "freeze-123")
    assert record["status"] == "failed"
    assert record["errors"] == ["unhandled:ValueError"]
    assert record["execution_id"] == "freeze-123"
    assert record["trace_path"] is None

    class InterruptedVerifier:
        def verify(self, prompt, response):
            raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        execute_item(InterruptedVerifier(), row, "LIVE", "freeze-123")


def test_resume_rejects_stale_or_missing_trace(tmp_path):
    row = {
        "item_id": "PLT002",
        "prompt": "Example",
        "response": "Example answer",
        "prompt_sha256": _sha("Example"),
        "response_sha256": _sha("Example answer"),
    }
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "mode": "LIVE",
                "prompt_hash": digest(row["prompt"]),
                "response_hash": digest(row["response"]),
                "result": {"status": "completed"},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "results.jsonl"
    valid = {
        "mode": "LIVE",
        "status": "completed",
        "item_id": row["item_id"],
        "execution_id": "freeze-123",
        "prompt_sha256": row["prompt_sha256"],
        "response_sha256": row["response_sha256"],
        "trace_path": str(trace_path),
        "run_id": "run-1",
    }
    output.write_text(json.dumps(valid) + "\n", encoding="utf-8")
    args = {"execution_id": "freeze-123", "rows_by_id": {row["item_id"]: row}}
    assert load_completed(output, "LIVE", **args) == {"PLT002"}
    assert load_completed(output, "LIVE", execution_id="different", rows_by_id=args["rows_by_id"]) == set()
    output.write_text(output.read_text() + json.dumps({**valid, "status": "failed"}) + "\n")
    assert load_completed(output, "LIVE", **args) == set()
    trace_path.unlink()
    output.write_text(json.dumps(valid) + "\n")
    assert load_completed(output, "LIVE", **args) == set()


def test_recovery_preserves_complete_checkpoints_and_backs_up_torn_tail(tmp_path):
    output = tmp_path / "results.jsonl"
    record = {"mode": "LIVE", "status": "completed", "item_id": "PLT001"}
    output.write_bytes((json.dumps(record) + "\n").encode() + b'{"mode": "LIVE", "item_id":')
    assert read_checkpoint_records(output) == [record]
    assert output.read_text() == json.dumps(record) + "\n"
    assert (tmp_path / "results.jsonl.interrupted.bak").exists()

    output.write_text('{"mode": wrong}\n' + json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Corrupt non-final"):
        read_checkpoint_records(output)


def test_evidence_audit_uses_actual_semantic_hash_key_and_execution_identity(tmp_path):
    corpora = {}
    for name, prefix in (("plt120", "PLT"), ("external120", "EXT"), ("redteam120", "RT")):
        source_path = tmp_path / f"{name}.csv"
        _write_generated(source_path, name, prefix)
        spec = {
            "path": str(source_path),
            "id_prefix": prefix,
            "items": 2,
            "generator_corpus": name,
        }
        rows = read_generated_rows(source_path, name, spec, _generator())
        spec["semantic_sha256"] = semantic_dataset_sha256(rows)
        corpora[name] = spec

    manifest = {
        "experiment_id": "audit-fixture",
        "freeze_code_commit": "fixed-revision",
        "dataset": {"items": 6, "corpora": corpora},
        "generator": _generator(),
        "vericult": {
            "config_sha256": "fixture-config",
            "provider": "l3s",
            "backbone": "fixture-model",
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    eid = experiment_identity(manifest)
    records = []
    for name, prefix in (("plt120", "PLT"), ("external120", "EXT"), ("redteam120", "RT")):
        with (tmp_path / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                item_id = row["item_id"]
                trace_path = tmp_path / f"{item_id}.json"
                trace_path.write_text(
                    json.dumps(
                        {
                            "mode": "LIVE",
                            "run_id": item_id,
                            "prompt_hash": digest(row["prompt"]),
                            "response_hash": digest(row["response"]),
                            "result": {"trace_path": str(trace_path.resolve()), "evidence": []},
                        }
                    ),
                    encoding="utf-8",
                )
                records.append(
                    {
                        "mode": "LIVE",
                        "status": "completed",
                        "item_id": item_id,
                        "execution_id": eid,
                        "run_id": item_id,
                        "trace_path": str(trace_path.resolve()),
                        "prompt_sha256": row["prompt_sha256"],
                        "response_sha256": row["response_sha256"],
                    }
                )

    live_path = tmp_path / "live.jsonl"
    live_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    output = tmp_path / "evidence_manifest.json"
    assert (
        audit_evidence_main(
            [
                "--manifest",
                str(manifest_path),
                "--live-output",
                str(live_path),
                "--evidence-dir",
                str(tmp_path / "no-evidence-required"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    audit = json.loads(output.read_text())
    assert audit["execution_id"] == eid
    assert audit["n_items"] == 6
    assert audit["dataset_sha256"]["plt120"]["semantic_sha256"] == corpora["plt120"]["semantic_sha256"]


def test_preflight_script_mode_exposes_both_freeze_helpers():
    """Reproduce python scripts/preflight_final_experiment.py import fallback."""
    code = """
import builtins

original_import = builtins.__import__

def force_script_mode(name, *args, **kwargs):
    if name == "scripts.run_final_experiment":
        raise ModuleNotFoundError("Forced direct-script fallback")
    return original_import(name, *args, **kwargs)

builtins.__import__ = force_script_mode
import preflight_final_experiment as preflight
assert callable(preflight.validate_frozen_model)
assert callable(preflight.experiment_identity)
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1] / "scripts",
        check=True,
        capture_output=True,
        text=True,
    )
