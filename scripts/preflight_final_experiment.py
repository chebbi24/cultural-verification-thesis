"""Capture runtime identity for the frozen 360-item single-response experiment."""

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
from dotenv import load_dotenv
from cultverify import Config

try:
    from scripts.run_final_experiment import (
        assert_frozen_checkout,
        experiment_identity,
        load_final_rows,
        sha256_file,
        validate_freeze_files,
        validate_frozen_model,
    )
except ModuleNotFoundError:
    from run_final_experiment import (
        assert_frozen_checkout,
        experiment_identity,
        load_final_rows,
        sha256_file,
        validate_freeze_files,
        validate_frozen_model,
    )


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
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("experiments/final_manifest.json"))
    parser.add_argument("--config", type=Path, default=Path("experiments/final_vericult_config.json"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/final_experiment/runtime_manifest.json"),
    )
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    assert_frozen_checkout(manifest)
    dataset_hashes = validate_freeze_files(manifest, args.config)
    rows = load_final_rows(manifest, "all")
    if len(rows) != 360:
        raise RuntimeError(f"Final experiment must contain exactly 360 prompt-response pairs; found {len(rows)}")

    provider = os.getenv("CULTVERIFY_PROVIDER", config["verifier_model_provider"])
    model_id = os.getenv("CULTVERIFY_MODEL", config["verifier_model_id"])
    l3s_api_url = os.getenv("L3S_API_URL", config.get("l3s_api_url", ""))
    effective = Config.model_validate(
        {**config, "verifier_model_provider": provider, "verifier_model_id": model_id, "l3s_api_url": l3s_api_url}
    )
    validate_frozen_model(effective, manifest)
    if not os.getenv("TAVILY_API_KEY"):
        raise RuntimeError("TAVILY_API_KEY is not set")

    if provider == "ollama":
        try:
            response = requests.get(tags_url(config["ollama_url"]), timeout=10)
            response.raise_for_status()
            installed = response.json()["models"]
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Could not query the local Ollama model registry") from exc
        model = find_ollama_model(installed, model_id)
        verifier_model = {
            "provider": "ollama",
            "requested_id": model_id,
            "installed_name": model.get("name") or model.get("model"),
            "digest": model.get("digest"),
            "size": model.get("size"),
            "modified_at": model.get("modified_at"),
        }
    elif provider == "l3s":
        if not os.getenv("L3S_API_KEY"):
            raise RuntimeError("L3S_API_KEY is not set")
        if not l3s_api_url or "YOUR_L3S_HOST" in l3s_api_url:
            raise RuntimeError("L3S_API_URL is not configured")
        verifier_model = {
            "provider": "l3s",
            "requested_id": model_id,
            "api_url": l3s_api_url,
            "digest": f"remote:{model_id}",
        }
    elif provider == "openrouter":
        if not os.getenv("OPENROUTER_API_KEY"):
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        verifier_model = {
            "provider": "openrouter",
            "requested_id": model_id,
            "digest": f"remote:{model_id}",
        }
    else:
        raise RuntimeError(f"Unsupported final-experiment provider: {provider}")

    runtime = {
        "schema_version": "final-runtime-v3",
        "execution_id": experiment_identity(manifest),
        "freeze_code_commit": manifest["freeze_code_commit"],
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": __import__("subprocess")
        .run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        .stdout.strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "n_items": len(rows),
        "dataset_sha256": dataset_hashes,
        "config_sha256": sha256_file(args.config),
        "verifier_model": verifier_model,
        "packages": {name: importlib.metadata.version(name) for name in ("cultverify", "pydantic", "requests")},
        "credentials_present": {
            "TAVILY_API_KEY": bool(os.getenv("TAVILY_API_KEY")),
            "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
            "L3S_API_KEY": bool(os.getenv("L3S_API_KEY")),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Runtime frozen for {len(rows)} items: "
        f"{runtime['verifier_model'].get('installed_name', runtime['verifier_model']['requested_id'])} "
        f"digest={runtime['verifier_model']['digest']} -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
