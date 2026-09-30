"""Capture the local runtime identity required before the frozen final experiment."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from scripts.run_final_experiment import assert_frozen_checkout, sha256_file, validate_freeze_files


def tags_url(chat_url: str) -> str:
    parts = urlsplit(chat_url)
    return urlunsplit((parts.scheme, parts.netloc, "/api/tags", "", ""))


def find_ollama_model(models: list[dict], model_id: str) -> dict:
    aliases = {model_id, model_id + ":latest"} if ":" not in model_id else {model_id}
    for model in models:
        if model.get("name") in aliases or model.get("model") in aliases:
            return model
    raise RuntimeError(f"Frozen Ollama model is not installed: {model_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("experiments/final_manifest.json"))
    parser.add_argument("--config", type=Path, default=Path("experiments/final_vericult_config.json"))
    parser.add_argument("--dataset", type=Path, default=Path("data/evaluation/best_of4_v1.csv"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/final_experiment/runtime_manifest.json"),
    )
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    assert_frozen_checkout(manifest)
    validate_freeze_files(manifest, args.dataset, args.config)

    if config["verifier_model_provider"] != "ollama":
        raise RuntimeError("Frozen final experiment expects the Ollama provider")
    if not os.getenv("TAVILY_API_KEY"):
        raise RuntimeError("TAVILY_API_KEY is not set")

    try:
        response = requests.get(tags_url(config["ollama_url"]), timeout=10)
        response.raise_for_status()
        installed = response.json()["models"]
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Could not query the local Ollama model registry") from exc

    model = find_ollama_model(installed, config["verifier_model_id"])
    runtime = {
        "schema_version": "final-runtime-v1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": __import__("subprocess")
        .run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        .stdout.strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "dataset_sha256": sha256_file(args.dataset),
        "config_sha256": sha256_file(args.config),
        "verifier_model": {
            "provider": "ollama",
            "requested_id": config["verifier_model_id"],
            "installed_name": model.get("name") or model.get("model"),
            "digest": model.get("digest"),
            "size": model.get("size"),
            "modified_at": model.get("modified_at"),
        },
        "packages": {name: importlib.metadata.version(name) for name in ("cultverify", "pydantic", "requests")},
        "credentials_present": {
            "TAVILY_API_KEY": bool(os.getenv("TAVILY_API_KEY")),
            "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Runtime frozen: {runtime['verifier_model']['installed_name']} "
        f"digest={runtime['verifier_model']['digest']} -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
