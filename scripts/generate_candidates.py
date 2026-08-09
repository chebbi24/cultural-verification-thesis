#!/usr/bin/env python3
"""Generate reproducible long-form Best-of-N candidates through local Ollama."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cultural_verifier.io import read_csv, write_csv, write_json


def request_json(url: str, payload: dict | None = None, timeout: int = 600) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Ollama at {url}: {exc}") from exc


def generate(base_url: str, model: str, prompt: str, seed: int, args: argparse.Namespace) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": args.temperature,
            "top_p": args.top_p,
            "repeat_penalty": 1.0,
            "num_predict": args.max_tokens,
            "num_ctx": args.context_tokens,
            "seed": seed,
        },
    }
    response = request_json(f"{base_url}/api/chat", payload)
    text = str(response.get("message", {}).get("content", "")).strip()
    if not text:
        raise RuntimeError(f"Ollama returned an empty answer for seed {seed}")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", type=Path, default=REPO_ROOT / "data/benchmark/prompts.csv")
    parser.add_argument("--splits", type=Path, default=REPO_ROOT / "data/benchmark/splits.csv")
    parser.add_argument("--split", choices=["development", "verifier_validation", "test", "all"], default="development")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--n", type=int, default=4, choices=range(2, 9))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--context-tokens", type=int, default=4096)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    base_url = args.ollama_url.rstrip("/")
    installed = {item.get("name", "") for item in request_json(f"{base_url}/api/tags", timeout=20).get("models", [])}
    if args.model not in installed and not any(name.startswith(f"{args.model}:") for name in installed):
        raise RuntimeError(f"Ollama model {args.model!r} is not installed")

    split_by_prompt = {row["prompt_id"]: row["split"] for row in read_csv(args.splits)}
    prompts = [
        row
        for row in read_csv(args.prompts)
        if args.split == "all" or split_by_prompt[row["prompt_id"]] == args.split
    ]
    existing = {}
    if args.output.exists() and not args.no_resume:
        existing = {row["candidate_id"]: row for row in read_csv(args.output)}

    rows = []
    for prompt_index, prompt in enumerate(prompts):
        for position in range(1, args.n + 1):
            candidate_id = f"{prompt['prompt_id']}-C{position}"
            if candidate_id in existing:
                rows.append(existing[candidate_id])
                continue
            seed = args.seed + prompt_index * args.n + position - 1
            response = generate(base_url, args.model, prompt["prompt_text"], seed, args)
            rows.append(
                {
                    "set_id": prompt["prompt_id"],
                    "prompt_id": prompt["prompt_id"],
                    "candidate_id": candidate_id,
                    "candidate_position": position,
                    "domain_id": prompt["domain_id"],
                    "subdimension_id": prompt["subdimension_id"],
                    "attack_id": prompt["attack_id"],
                    "prompt_text": prompt["prompt_text"],
                    "response_text": response,
                    "generator_model": args.model,
                    "generation_seed": seed,
                }
            )
            write_csv(args.output, rows, list(rows[0]))
            print(f"{candidate_id} seed={seed}")
            if args.delay:
                time.sleep(args.delay)

    write_csv(args.output, rows, list(rows[0]))
    write_json(
        args.output.with_suffix(".metadata.json"),
        {
            "prompt_file": str(args.prompts),
            "split": args.split,
            "generator_model": args.model,
            "n": args.n,
            "base_seed": args.seed,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "repeat_penalty": 1.0,
            "max_tokens": args.max_tokens,
            "context_tokens": args.context_tokens,
            "candidate_count": len(rows),
        },
    )


if __name__ == "__main__":
    main()
