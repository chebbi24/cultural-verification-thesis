"""Run the standalone cultural verifier on rows containing prompt + response.

For the thesis's main Best-of-4 comparison, prefer evaluate_best_of4.py.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from verifier import (
    CulturalVerifier,
    OllamaClient,
    OpenRouterClient,
    RetrievalRoutedClient,
    TavilyGroundedClient,
    VERIFIER_PIPELINE_VERSION,
)


def read_rows(path: Path) -> list[dict[str, str]]:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    first = sample.splitlines()[0] if sample.splitlines() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--target-context", default="Germany")
    parser.add_argument("--backend", choices=("ollama", "openrouter"), default="ollama")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--search-provider",
        choices=("same", "tavily", "openrouter"),
        default="tavily",
    )
    parser.add_argument("--search-model", default=None)
    parser.add_argument(
        "--search-depth", choices=("basic", "advanced"), default=None
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ollama-timeout", type=float, default=None)
    parser.add_argument("--ollama-attempts", type=int, default=None)
    parser.add_argument("--ollama-keep-alive", default=None)
    args = parser.parse_args()

    rows = read_rows(args.input_csv)
    if args.limit > 0:
        rows = rows[: args.limit]

    judge_client = (
        OllamaClient(
            model=args.model,
            timeout_seconds=args.ollama_timeout,
            max_attempts=args.ollama_attempts,
            keep_alive=args.ollama_keep_alive,
        )
        if args.backend == "ollama"
        else OpenRouterClient(model=args.model)
    )
    if args.search_provider == "tavily":
        client = TavilyGroundedClient(
            judge_client,
            search_depth=args.search_depth,
        )
    elif args.search_provider == "openrouter" and args.backend != "openrouter":
        client = RetrievalRoutedClient(
            judge_client, OpenRouterClient(model=args.search_model)
        )
    else:
        client = judge_client
    verifier = CulturalVerifier(client)
    results = []
    for index, row in enumerate(rows, 1):
        if "prompt" not in row or "response" not in row:
            raise ValueError(
                "Input CSV must contain columns named 'prompt' and 'response'. Use evaluate_best_of4.py for response_a..response_d files."
            )
        case_id = row.get("prompt_id") or row.get("case_id") or f"row_{index}"
        domain_id = (row.get("domain_id") or "").strip().upper()
        print(f"[{index}/{len(rows)}] verifying {case_id}", flush=True)
        result = verifier.verify(
            row["prompt"],
            row["response"],
            args.target_context,
            declared_domain_id=domain_id or None,
        )
        results.append(
            {
                "case_id": case_id,
                "prompt": row["prompt"],
                "response": row["response"],
                "pipeline_version": VERIFIER_PIPELINE_VERSION,
                "backend": args.backend,
                "judge_model": client.model,
                "search_provider": args.search_provider,
                "retrieval_system": getattr(
                    client, "retrieval_system", args.search_provider
                ),
                "retrieval_model": getattr(
                    client, "retrieval_model", client.model
                ),
                "retrieval_model_disclosure": getattr(
                    client, "retrieval_model_disclosure", None
                ),
                "search_depth": getattr(client, "search_depth", None),
                **result.__dict__,
            }
        )
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output_json.with_name(args.output_json.name + ".tmp")
        temporary.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(args.output_json)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved {args.output_json}")


if __name__ == "__main__":
    main()
