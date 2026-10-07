#!/usr/bin/env python3
"""Generate frozen Best-of-4 candidates for the final thesis prompt pools.

The generator never reads human-gold files and never overwrites the existing
source/native responses. Each candidate is produced by an independent API call
using the original prompt verbatim.

Examples:
    python scripts/generate_final_candidates.py --dry-run --corpus all
    python scripts/generate_final_candidates.py --corpus plt30 --limit 3
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
LABELS = ("A", "B", "C", "D")


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
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^RECORD\s+(\d{3})\s*$", text))
    rows: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end]
        prompt_match = re.search(r"(?ms)^PROMPT:\s*\n(.*?)\nRESPONSE:\s*\n", block)
        if not prompt_match:
            raise ValueError(f"Could not parse PROMPT for external RECORD {match.group(1)}")
        rows.append(
            {
                "item_id": f"EXT{match.group(1)}",
                "prompt": prompt_match.group(1).strip(),
                "source_dataset": _field(block, "DATASET"),
                "source_record_id": _field(block, "SOURCE_ROW/ID"),
                "language": _field(block, "LANGUAGE"),
                "culture": _field(block, "CULTURE/COUNTRY"),
            }
        )
    return rows


def load_redteam120(spec: dict[str, Any]) -> list[dict[str, str]]:
    path = ROOT / spec["input"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "item_id": row[spec["id_field"]].strip(),
            "prompt": (row.get(spec["prompt_field"]) or "").strip(),
            "source_dataset": (row.get("source") or "").strip(),
            "source_record_id": (row.get("source_record_key") or "").strip(),
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
            "Generation is intentionally blocked rather than inventing or reconstructing prompt text."
        )
    return rows


def output_fields() -> list[str]:
    base = [
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
    ]
    for label in LABELS:
        lower = label.lower()
        base.extend(
            [
                f"response_{lower}",
                f"response_{lower}_sha256",
                f"generated_at_{lower}",
                f"prompt_tokens_{lower}",
                f"completion_tokens_{lower}",
                f"total_tokens_{lower}",
            ]
        )
    return base


def initialize_rows(
    corpus: str,
    items: list[dict[str, str]],
    generator: dict[str, Any],
    sampling: dict[str, Any],
) -> list[dict[str, str]]:
    rows = []
    for item in items:
        row = {
            "corpus": corpus,
            **item,
            "prompt_sha256": sha256_text(item["prompt"]),
            "generator_model": generator["model_id"],
            "temperature": str(sampling["temperature"]),
            "top_p": str(sampling["top_p"]),
            "max_tokens": str(sampling["max_tokens"]),
        }
        for label in LABELS:
            lower = label.lower()
            row[f"response_{lower}"] = ""
            row[f"response_{lower}_sha256"] = ""
            row[f"generated_at_{lower}"] = ""
            row[f"prompt_tokens_{lower}"] = ""
            row[f"completion_tokens_{lower}"] = ""
            row[f"total_tokens_{lower}"] = ""
        rows.append(row)
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
            raise ValueError(f"{row['item_id']}: generator model differs from existing generation output")
        for label in LABELS:
            lower = label.lower()
            keys = (
                f"response_{lower}",
                f"response_{lower}_sha256",
                f"generated_at_{lower}",
                f"prompt_tokens_{lower}",
                f"completion_tokens_{lower}",
                f"total_tokens_{lower}",
            )
            for key in keys:
                if old.get(key):
                    row[key] = old[key]
    return fresh


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields(), extrasaction="ignore")
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
            token_usage = {
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            }
            return content.strip(), token_usage
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            last_error = exc
            if attempt > retries:
                break
            time.sleep(2 * attempt)
    raise RuntimeError(f"Generation failed after {retries + 1} attempts: {last_error}")


def validate_existing_config(rows: list[dict[str, str]], sampling: dict[str, Any]) -> None:
    expected = {
        "temperature": str(sampling["temperature"]),
        "top_p": str(sampling["top_p"]),
        "max_tokens": str(sampling["max_tokens"]),
    }
    for row in rows:
        for key, value in expected.items():
            if row.get(key) != value:
                raise ValueError(
                    f"{row['item_id']}: existing {key}={row.get(key)!r} differs from frozen {value!r}"
                )


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

    if int(sampling["candidates_per_prompt"]) != len(LABELS):
        raise ValueError("This frozen runner requires exactly four candidates A-D")

    names = (
        ("plt30", "external120", "redteam120")
        if args.corpus == "all"
        else (args.corpus,)
    )

    # Validate every requested corpus before making a single paid/remote model call.
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
        validate_existing_config(rows, sampling)
        write_rows(output_path, rows)

        total_candidates = len(rows) * len(LABELS)
        completed_before = sum(
            1
            for row in rows
            for label in LABELS
            if row[f"response_{label.lower()}"].strip()
        )
        print(
            f"\n{name}: {len(rows)} prompts / {total_candidates} candidates "
            f"({completed_before} already complete)"
        )

        for row_index, row in enumerate(rows, start=1):
            for label in LABELS:
                lower = label.lower()
                response_key = f"response_{lower}"
                if row[response_key].strip():
                    continue

                print(f"[{name} {row_index}/{len(rows)}] {row['item_id']} candidate {label} ...", flush=True)
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

                row[response_key] = content
                row[f"response_{lower}_sha256"] = sha256_text(content)
                row[f"generated_at_{lower}"] = datetime.now(timezone.utc).isoformat()
                row[f"prompt_tokens_{lower}"] = str(usage["prompt_tokens"])
                row[f"completion_tokens_{lower}"] = str(usage["completion_tokens"])
                row[f"total_tokens_{lower}"] = str(usage["total_tokens"])
                write_rows(output_path, rows)

                print(
                    f"  saved in {elapsed:.1f}s; "
                    f"tokens={usage['total_tokens'] or 'not reported'}",
                    flush=True,
                )

        missing = [
            f"{row['item_id']}:{label}"
            for row in rows
            for label in LABELS
            if not row[f"response_{label.lower()}"].strip()
        ]
        if missing:
            raise RuntimeError(f"{name}: incomplete candidates remain: {missing[:10]}")

        print(f"{name}: COMPLETE -> {output_path.relative_to(ROOT)}")

    print("\nGeneration completed. Freeze/hash the generated CSVs before Vericult evaluation.")


if __name__ == "__main__":
    main()
