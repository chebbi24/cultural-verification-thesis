"""Generate Best-of-4 v2 locally with Ollama from frozen PLT001-PLT030 prompts.

v2 is a realistic stronger-model candidate set. It does not use Vericult, human
labels, D01-D10, or any cultural winner signal during generation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import time
from pathlib import Path

import requests

LABELS = "ABCD"
EXPECTED_IDS = tuple(f"PLT{i:03d}" for i in range(1, 31))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_prompts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    ids = tuple(r["prompt_id"] for r in rows)
    if ids != EXPECTED_IDS:
        raise ValueError("Source dataset must contain PLT001-PLT030 in canonical order")
    return [{"prompt_id": r["prompt_id"], "prompt": r["prompt"]} for r in rows]


def installed_models(tags_url: str, timeout: float) -> dict[str, str]:
    r = requests.get(tags_url, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    result = {}
    for model in data.get("models", []):
        name = model.get("name")
        digest = model.get("digest")
        if name and digest:
            result[name] = digest
    return result


def call_model(model: str, prompt: str, cfg: dict) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": cfg["system_prompt"]},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": cfg["temperature"],
            "num_predict": cfg["num_predict"],
        },
    }
    last_error = None
    for attempt in range(cfg["retry_count"] + 1):
        try:
            r = requests.post(
                cfg["ollama_url"],
                json=body,
                timeout=cfg["timeout_seconds"],
            )
            r.raise_for_status()
            data = r.json()
            text = data["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("empty generation")
            return text.strip()
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            last_error = exc
            if attempt < cfg["retry_count"]:
                time.sleep(2**attempt)
    raise RuntimeError(f"{model} failed after bounded retry: {last_error}")


def assignment(prompt_id: str, models: list[str], seed: int) -> list[str]:
    digest = hashlib.sha256(f"{seed}:{prompt_id}".encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    order = list(models)
    rng.shuffle(order)
    return order


def load_raw(path: Path) -> dict[tuple[str, str], dict]:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("status") == "completed":
                out[(rec["prompt_id"], rec["model"])] = rec
    return out


def append_raw(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/best_of4_v2_generation.json"),
    )
    parser.add_argument("--prompt-id", help="Optional single PLT id for smoke testing")
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    source = Path(cfg["source_dataset"])
    output = Path(cfg["output_dataset"])
    raw_path = Path(cfg["raw_output"])
    mapping_path = Path(cfg["mapping_output"])
    manifest_path = Path(cfg["manifest_output"])

    local_models = installed_models(cfg["ollama_tags_url"], cfg["timeout_seconds"])
    missing_installed = [m for m in cfg["models"] if m not in local_models]
    if missing_installed:
        commands = "\n".join(f"  ollama pull {m}" for m in missing_installed)
        raise RuntimeError(
            "Required Ollama models are not installed:\n"
            + "\n".join(f"  - {m}" for m in missing_installed)
            + "\nInstall them first:\n"
            + commands
        )

    prompts = read_prompts(source)
    if args.prompt_id:
        prompts = [r for r in prompts if r["prompt_id"] == args.prompt_id]
        if not prompts:
            raise ValueError(f"Unknown prompt id: {args.prompt_id}")

    completed = load_raw(raw_path)
    models = cfg["models"]

    # Local models are intentionally run sequentially to avoid loading several
    # large models into unified memory at the same time.
    for row in prompts:
        prompt_id, prompt = row["prompt_id"], row["prompt"]
        missing = [m for m in models if (prompt_id, m) not in completed]
        for model in missing:
            print(f"[{prompt_id}] {model} starting", flush=True)
            try:
                response = call_model(model, prompt, cfg)
                rec = {
                    "prompt_id": prompt_id,
                    "model": model,
                    "model_digest": local_models[model],
                    "status": "completed",
                    "response": response,
                }
                completed[(prompt_id, model)] = rec
                append_raw(raw_path, rec)
                print(f"  OK {model}", flush=True)
            except Exception as exc:
                rec = {
                    "prompt_id": prompt_id,
                    "model": model,
                    "model_digest": local_models.get(model, ""),
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                append_raw(raw_path, rec)
                print(f"  FAILED {model}: {exc}", flush=True)

    # Build the canonical dataset only after all 30 x 4 generations exist.
    all_prompts = read_prompts(source)
    missing_pairs = [
        (row["prompt_id"], model)
        for row in all_prompts
        for model in models
        if (row["prompt_id"], model) not in completed
    ]
    if missing_pairs:
        print(f"Generation incomplete: {len(missing_pairs)} model response(s) still missing.")
        return 2

    dataset_rows = []
    mapping_rows = []
    for row in all_prompts:
        pid = row["prompt_id"]
        model_order = assignment(pid, models, cfg["assignment_seed"])
        candidate_values = {}
        for label, model in zip(LABELS, model_order, strict=True):
            response = completed[(pid, model)]["response"]
            if len(response.strip()) < 20:
                raise RuntimeError(f"{pid}/{model} failed minimal nonempty quality gate")
            candidate_values[f"response_{label.lower()}"] = response
            mapping_rows.append(
                {
                    "prompt_id": pid,
                    "candidate": label,
                    "model": model,
                    "model_digest": local_models[model],
                }
            )
        dataset_rows.append({"prompt_id": pid, "prompt": row["prompt"], **candidate_values})

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["prompt_id", "prompt", "response_a", "response_b", "response_c", "response_d"],
        )
        writer.writeheader()
        writer.writerows(dataset_rows)

    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with mapping_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["prompt_id", "candidate", "model", "model_digest"],
        )
        writer.writeheader()
        writer.writerows(mapping_rows)

    manifest = {
        "schema_version": "best-of4-v2-generation-v1",
        "purpose": "realistic stronger-model Best-of-4 candidate generation",
        "provider": "ollama",
        "source_dataset": str(source),
        "source_sha256": sha256_file(source),
        "output_dataset": str(output),
        "output_sha256": sha256_file(output),
        "models": [
            {"model": model, "digest": local_models[model]}
            for model in models
        ],
        "assignment_seed": cfg["assignment_seed"],
        "temperature": cfg["temperature"],
        "num_predict": cfg["num_predict"],
        "system_prompt": cfg["system_prompt"],
        "human_labels_used": False,
        "vericult_outputs_used": False,
        "cultural_quality_filter_used": False,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nCreated {output}")
    print(f"SHA256: {manifest['output_sha256']}")
    print(f"Mapping: {mapping_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
