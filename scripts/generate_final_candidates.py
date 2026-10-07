#!/usr/bin/env python3
"""Generate one frozen GPT-OSS response per prompt for the final thesis corpora.

The generator never reads human-gold files and never overwrites the original
source/native responses. The original prompt is sent verbatim.

Examples:
    python scripts/generate_final_candidates.py --dry-run --corpus all
    python scripts/generate_final_candidates.py --corpus redteam120 --limit 3
    python scripts/generate_final_candidates.py --corpus all
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "experiments" / "generator_freeze.json"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_plt30(spec: dict[str, Any]) -> list[dict[str, str]]:
    path = ROOT / spec["input"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "item_id": row[spec["id_field"]].strip(),
            "prompt": row[spec["prompt_field"]].strip(),
            "source_dataset": "PLT",
            "source_record_id": row.get("legacy_prompt_id", "").strip(),
            "language": "",
            "culture": "",
        }
        for row in rows
    ]


def _field(block: str, name: str) -> str:
    match = re.search(rf"(?m)^{re.escape(name)}:\s*(.*)$", block)
    return match.group(1).strip() if match else ""


def load_external120(spec: dict[str, Any]) -> list[dict[str, str]]:
    path = ROOT / spec["input"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "item_id": row[spec["id_field"]].strip(),
            "prompt": row[spec["prompt_field"]].strip(),
            "source_dataset": (row.get("dataset") or "").strip(),
            "source_record_id": (row.get("source_row_id") or "").strip(),
            "language": (row.get("language") or "").strip(),
            "culture": (row.get("culture_country") or "").strip(),
        }
        for row in rows
    ]


def load_redteam120(spec: dict[str, Any]) -> list[dict[str, str]]:
    path = ROOT / spec["input"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "item_id": row[spec["id_field"]].strip(),
            "prompt": (row.get(spec["prompt_field"]) or "").strip(),
            "source_dataset": (row.get("source_name") or row.get("source") or "").strip(),
            "source_record_id": (row.get("source_record_key") or row.get("final_id") or "").strip(),
            "language": (row.get("language") or "").strip(),
            "culture": (row.get("country_culture") or "").strip(),
        }
        for row in rows
    ]


def load_corpus(name: str, spec: dict[str, Any]) -> list[dict[str, str]]:
    if name == "plt30":
        rows = load_plt30(spec)
    elif name == "external120":
        rows = load_external120(spec)
    elif name == "redteam120":
        rows = load_redteam120(spec)
    else:
        raise ValueError(f"Unknown corpus: {name}")

    expected = int(spec["expected_prompts"])
    if len(rows) != expected:
        raise ValueError(f"{name}: expected {expected} prompts, found {len(rows)}")

    ids = [row["item_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{name}: duplicate item IDs detected")

    missing = [row["item_id"] for row in rows if not row["prompt"]]
    if missing:
        preview = ", ".join(missing[:12])
        suffix = "" if len(missing) <= 12 else f", ... (+{len(missing) - 12} more)"
        raise ValueError(
            f"{name}: {len(missing)} prompts are not locally materialized: {preview}{suffix}. "
            "Generation is blocked rather than reconstructing prompt text."
        )
    return rows


FIELDS = [
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


def initialize_rows(
    corpus: str,
    items: list[dict[str, str]],
    generator: dict[str, Any],
    sampling: dict[str, Any],
) -> list[dict[str, str]]:
    rows = []
    for item in items:
        rows.append(
            {
                "corpus": corpus,
                **item,
                "prompt_sha256": sha256_text(item["prompt"]),
                "generator_model": generator["model_id"],
                "temperature": str(sampling["temperature"]),
                "top_p": str(sampling["top_p"]),
                "max_tokens": str(sampling["max_tokens"]),
                "response": "",
                "response_sha256": "",
                "generated_at": "",
                "prompt_tokens": "",
                "completion_tokens": "",
                "total_tokens": "",
            }
        )
    return rows


def read_existing(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["item_id"]: row for row in csv.DictReader(handle)}


def merge_existing(
    fresh: list[dict[str, str]], existing: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    for row in fresh:
        old = existing.get(row["item_id"])
        if not old:
            continue
        if old.get("prompt_sha256") != row["prompt_sha256"]:
            raise ValueError(f"{row['item_id']}: prompt changed since existing generation output")
        if old.get("generator_model") != row["generator_model"]:
            raise ValueError(f"{row['item_id']}: generator model differs from existing output")
        for key in (
            "response",
            "response_sha256",
            "generated_at",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        ):
            if old.get(key):
                row[key] = old[key]
    return fresh


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def generate_one(
    session: requests.Session,
    api_url: str,
    api_key: str,
    model_id: str,
    prompt: str,
    sampling: dict[str, Any],
    timeout: float,
    retries: int,
) -> tuple[str, dict[str, int]]:
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": sampling["temperature"],
        "top_p": sampling["top_p"],
        "max_tokens": sampling["max_tokens"],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            response = session.post(api_url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"Empty/non-text assistant content: {message!r}")
            usage = data.get("usage") or {}
            return content.strip(), {
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            }
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            last_error = exc
            if attempt > retries:
                break
            time.sleep(2 * attempt)
    raise RuntimeError(f"Generation failed after {retries + 1} attempts: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--corpus",
        choices=("plt30", "external120", "redteam120", "all"),
        default="all",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = load_config(Path(args.config))
    generator = config["generator"]
    sampling = config["sampling"]

    if int(sampling["candidates_per_prompt"]) != 1:
        raise ValueError("This final runner requires exactly one generated response per prompt")

    names = (
        ("plt30", "external120", "redteam120")
        if args.corpus == "all"
        else (args.corpus,)
    )

    loaded: dict[str, list[dict[str, str]]] = {}
    for name in names:
        rows = load_corpus(name, config["corpora"][name])
        loaded[name] = rows
        print(f"{name}: {len(rows)} prompts ready")

    if args.dry_run:
        print(f"TOTAL: {sum(len(rows) for rows in loaded.values())} prompts ready")
        print("DRY RUN PASS: no generation requests were sent")
        return

    api_key_env = generator["api_key_env"]
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing {api_key_env} in local .env")

    api_url = os.getenv(
        generator["api_url_env"],
        "https://inference.kbs.uni-hannover.de/v1/chat/completions",
    )
    session = requests.Session()

    for name in names:
        spec = config["corpora"][name]
        items = loaded[name][: args.limit] if args.limit else loaded[name]
        output_path = ROOT / spec["output"]

        rows = initialize_rows(name, items, generator, sampling)
        rows = merge_existing(rows, read_existing(output_path))
        write_rows(output_path, rows)

        completed_before = sum(1 for row in rows if row["response"].strip())
        print(
            f"\n{name}: {len(rows)} prompts / {len(rows)} responses "
            f"({completed_before} already complete)"
        )

        for row_index, row in enumerate(rows, start=1):
            if row["response"].strip():
                continue

            print(f"[{name} {row_index}/{len(rows)}] {row['item_id']} ...", flush=True)
            started = time.monotonic()
            content, usage = generate_one(
                session=session,
                api_url=api_url,
                api_key=api_key,
                model_id=generator["model_id"],
                prompt=row["prompt"],
                sampling=sampling,
                timeout=args.timeout,
                retries=args.retries,
            )
            elapsed = time.monotonic() - started

            row["response"] = content
            row["response_sha256"] = sha256_text(content)
            row["generated_at"] = datetime.now(timezone.utc).isoformat()
            row["prompt_tokens"] = str(usage["prompt_tokens"])
            row["completion_tokens"] = str(usage["completion_tokens"])
            row["total_tokens"] = str(usage["total_tokens"])
            write_rows(output_path, rows)

            print(
                f"  saved in {elapsed:.1f}s; tokens={usage['total_tokens'] or 'not reported'}",
                flush=True,
            )

        missing = [row["item_id"] for row in rows if not row["response"].strip()]
        if missing:
            raise RuntimeError(f"{name}: incomplete responses remain: {missing[:10]}")

        print(f"{name}: COMPLETE -> {output_path.relative_to(ROOT)}")

    print("\nGeneration completed. Freeze/hash the generated CSVs before Vericult evaluation.")


if __name__ == "__main__":
    main()
