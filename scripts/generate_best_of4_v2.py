"""Generate Best-of-4 v2 from the same frozen PLT001-PLT030 prompts.

v2 is a realistic strong-model candidate set. It does not use Vericult, human
labels, D01-D10, or any cultural winner signal during generation.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import random
import time
from pathlib import Path

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
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


def call_model(api_key: str, model: str, prompt: str, cfg: dict) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": cfg["system_prompt"]},
            {"role": "user", "content": prompt},
        ],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_error = None
    for attempt in range(cfg["retry_count"] + 1):
        try:
            r = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=body,
                timeout=cfg["timeout_seconds"],
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("empty generation")
            return text.strip()
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            last_error = exc
            if attempt < cfg["retry_count"]:
                time.sleep(2 ** attempt)
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
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--prompt-id", help="Optional single PLT id for smoke testing")
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required")

    source = Path(cfg["source_dataset"])
    output = Path(cfg["output_dataset"])
    raw_path = Path(cfg["raw_output"])
    mapping_path = Path(cfg["mapping_output"])
    manifest_path = Path(cfg["manifest_output"])

    prompts = read_prompts(source)
    if args.prompt_id:
        prompts = [r for r in prompts if r["prompt_id"] == args.prompt_id]
        if not prompts:
            raise ValueError(f"Unknown prompt id: {args.prompt_id}")

    completed = load_raw(raw_path)
    models = cfg["models"]

    for row in prompts:
        prompt_id, prompt = row["prompt_id"], row["prompt"]
        missing = [m for m in models if (prompt_id, m) not in completed]
        if missing:
            print(f"[{prompt_id}] generating {len(missing)} model response(s)", flush=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.max_workers, len(missing))) as pool:
                futures = {pool.submit(call_model, api_key, m, prompt, cfg): m for m in missing}
                for future in concurrent.futures.as_completed(futures):
                    model = futures[future]
                    try:
                        response = future.result()
                        rec = {
                            "prompt_id": prompt_id,
                            "model": model,
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
                            "status": "failed",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                        append_raw(raw_path, rec)
                        print(f"  FAILED {model}: {exc}", flush=True)

    # Only build the canonical dataset when all 30x4 generations exist.
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
            mapping_rows.append({"prompt_id": pid, "candidate": label, "model": model})
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
        writer = csv.DictWriter(f, fieldnames=["prompt_id", "candidate", "model"])
        writer.writeheader()
        writer.writerows(mapping_rows)

    manifest = {
        "schema_version": "best-of4-v2-generation-v1",
        "purpose": "realistic strong-model Best-of-4 candidate generation",
        "source_dataset": str(source),
        "source_sha256": sha256_file(source),
        "output_dataset": str(output),
        "output_sha256": sha256_file(output),
        "models": models,
        "assignment_seed": cfg["assignment_seed"],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
        "system_prompt": cfg["system_prompt"],
        "human_labels_used": False,
        "vericult_outputs_used": False,
        "cultural_quality_filter_used": False,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nCreated {output}")
    print(f"SHA256: {manifest['output_sha256']}")
    print(f"Mapping: {mapping_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
