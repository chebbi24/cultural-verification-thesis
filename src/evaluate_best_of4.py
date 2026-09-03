"""Evaluate the standalone verifier on Best-of-4 candidate sets.

Expected columns: set_id (optional), prompt_id (optional), prompt,
response_a, response_b, response_c, response_d, human_chosen (optional).

Human labels are used only after candidate scoring/tiebreaking and are never sent
to the verifier. Applicable D01-D10 dimensions are planned once from the prompt
and frozen across all four candidates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from verifier import (
    CulturalVerifier,
    OllamaClient,
    OpenRouterClient,
    RetrievalRoutedClient,
    TavilyGroundedClient,
    DimensionApplicability,
    VerifierResult,
    VERIFIER_PIPELINE_VERSION,
)


SUMMARY_FIELDS = [
    "set_id",
    "prompt_id",
    "domain_id",
    "human_chosen",
    "verifier_winner",
    "verifier_correct",
    "tie_status",
    "tie_candidates",
    "abstained_candidates",
    "hard_fail_candidates",
    "ineligible_candidates",
    "score_a",
    "score_b",
    "score_c",
    "score_d",
]


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _write_outputs(
    output_csv: Path,
    summary: list[dict[str, object]],
    details: list[dict[str, object]],
) -> Path:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_csv.with_name(output_csv.name + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary)
    temporary.replace(output_csv)
    details_path = output_csv.with_suffix(".details.json")
    _atomic_write_text(
        details_path,
        json.dumps(details, ensure_ascii=False, indent=2),
    )
    return details_path


def _load_checkpoint(path: Path, enabled: bool) -> dict[str, Any]:
    if not enabled or not path.exists():
        return {"pipeline_version": VERIFIER_PIPELINE_VERSION, "cases": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"WARN ignoring unreadable checkpoint: {path}", flush=True)
        return {"pipeline_version": VERIFIER_PIPELINE_VERSION, "cases": {}}
    if not isinstance(value, dict) or value.get("pipeline_version") != VERIFIER_PIPELINE_VERSION:
        print("WARN ignoring checkpoint from a different pipeline version", flush=True)
        return {"pipeline_version": VERIFIER_PIPELINE_VERSION, "cases": {}}
    if not isinstance(value.get("cases"), dict):
        value["cases"] = {}
    return value


def _save_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(checkpoint, ensure_ascii=False, indent=2))


def _case_fingerprint(
    row: dict[str, str],
    *,
    target_context: str,
    backend: str,
    model: str,
    search_provider: str,
    retrieval_model: str,
    tie_epsilon: float,
) -> str:
    scoring_inputs = {
        "pipeline_version": VERIFIER_PIPELINE_VERSION,
        "prompt": row.get("prompt", ""),
        "domain_id": (row.get("domain_id") or "").strip().upper(),
        "responses": {label: row.get(f"response_{label}", "") for label in "abcd"},
        "target_context": target_context,
        "backend": backend,
        "model": model,
        "search_provider": search_provider,
        "retrieval_model": retrieval_model,
        "tie_epsilon": tie_epsilon,
    }
    encoded = json.dumps(
        scoring_inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _restore_plan(raw: Any) -> list[DimensionApplicability] | None:
    if not isinstance(raw, list):
        return None
    try:
        plan = [DimensionApplicability(**item) for item in raw]
    except (TypeError, ValueError):
        return None
    if not 1 <= len(plan) <= 3:
        return None
    if sum(item.relevance == "primary" for item in plan) != 1:
        return None
    if len({item.dimension_id for item in plan}) != len(plan):
        return None
    return plan


def _restore_result(raw: Any) -> VerifierResult | None:
    if not isinstance(raw, dict):
        return None
    try:
        return VerifierResult(**raw)
    except TypeError:
        return None


def read_rows(path: Path) -> list[dict[str, str]]:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    first = sample.splitlines()[0] if sample.splitlines() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--target-context", default="Germany")
    parser.add_argument("--backend", choices=("ollama", "openrouter"), default="ollama")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--search-provider",
        choices=("same", "tavily", "openrouter"),
        default="tavily",
        help="Retrieval provider. Tavily is the default; the judging model remains controlled by --backend.",
    )
    parser.add_argument("--search-model", default=None)
    parser.add_argument(
        "--search-depth",
        choices=("basic", "advanced"),
        default=None,
        help="Tavily search depth (default: TAVILY_SEARCH_DEPTH or basic).",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--ollama-timeout",
        type=float,
        default=None,
        help="Seconds allowed for each local Ollama request (default: 300 or OLLAMA_TIMEOUT_SECONDS).",
    )
    parser.add_argument(
        "--ollama-attempts",
        type=int,
        default=None,
        help="Transport attempts for local Ollama timeouts/connections (default: 2).",
    )
    parser.add_argument(
        "--ollama-keep-alive",
        default=None,
        help="How long Ollama keeps the model loaded (default: 30m).",
    )
    parser.add_argument(
        "--checkpoint-path",
        type=Path,
        default=None,
        help="Candidate-level checkpoint path (default: OUTPUT.checkpoint.json).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing checkpoints and recompute every candidate.",
    )
    parser.add_argument(
        "--tie-epsilon",
        type=float,
        default=1e-6,
        help="Scores within this absolute distance from the top score enter comparative tiebreaking.",
    )
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
            judge_client,
            OpenRouterClient(model=args.search_model),
        )
    else:
        client = judge_client
    verifier = CulturalVerifier(client)
    summary: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    checkpoint_path = args.checkpoint_path or args.output_csv.with_suffix(
        ".checkpoint.json"
    )
    checkpoint = _load_checkpoint(checkpoint_path, not args.no_resume)
    checkpoint_cases: dict[str, Any] = checkpoint["cases"]

    retrieval_label = (
        client.retrieval_model
        if hasattr(client, "retrieval_model")
        else f"same/{client.model}"
    )
    print(
        f"pipeline={VERIFIER_PIPELINE_VERSION} backend={args.backend} "
        f"model={client.model} retrieval={retrieval_label}",
        flush=True,
    )

    for index, row in enumerate(rows, 1):
        prompt = row["prompt"]
        case_id = row.get("set_id") or row.get("prompt_id") or f"row_{index}"
        domain_id = (row.get("domain_id") or "").strip().upper()
        print(f"[{index}/{len(rows)}] {case_id}", flush=True)

        case_key = f"{index}:{case_id}"
        fingerprint = _case_fingerprint(
            row,
            target_context=args.target_context,
            backend=args.backend,
            model=client.model,
            search_provider=args.search_provider,
            retrieval_model=retrieval_label,
            tie_epsilon=args.tie_epsilon,
        )
        case_state = checkpoint_cases.get(case_key)
        if not isinstance(case_state, dict) or case_state.get("fingerprint") != fingerprint:
            if isinstance(case_state, dict):
                print("  checkpoint inputs changed; recomputing case", flush=True)
            case_state = {
                "case_id": case_id,
                "fingerprint": fingerprint,
                "applicable_dimensions": None,
                "candidates": {},
                "decision": None,
            }
            checkpoint_cases[case_key] = case_state

        applicable_dimensions = _restore_plan(case_state.get("applicable_dimensions"))
        if applicable_dimensions is None:
            applicable_dimensions = verifier.plan_dimensions(
                prompt,
                args.target_context,
                domain_id or None,
            )
            case_state["applicable_dimensions"] = [
                item.__dict__ for item in applicable_dimensions
            ]
            _save_checkpoint(checkpoint_path, checkpoint)
        else:
            print(
                "    resumed dimension plan: "
                + ", ".join(item.dimension_id for item in applicable_dimensions),
                flush=True,
            )

        candidate_results: dict[str, VerifierResult] = {}
        responses: dict[str, str] = {}
        cached_candidates = case_state.get("candidates")
        if not isinstance(cached_candidates, dict):
            cached_candidates = {}
            case_state["candidates"] = cached_candidates
        for label in "abcd":
            response = row[f"response_{label}"]
            responses[label] = response
            restored = _restore_result(cached_candidates.get(label))
            if restored is not None:
                candidate_results[label] = restored
                print(f"  candidate {label.upper()}: resumed from checkpoint", flush=True)
                continue
            print(f"  candidate {label.upper()}", flush=True)
            try:
                result = verifier.verify(
                    prompt,
                    response,
                    args.target_context,
                    applicable_dimensions=applicable_dimensions,
                )
            except Exception:
                _save_checkpoint(checkpoint_path, checkpoint)
                print(
                    f"  candidate {label.upper()} failed. Rerun the same command to "
                    f"resume from {checkpoint_path}",
                    flush=True,
                )
                raise
            candidate_results[label] = result
            cached_candidates[label] = result.__dict__
            case_state["decision"] = None
            _save_checkpoint(checkpoint_path, checkpoint)

        cached_decision = case_state.get("decision")
        if isinstance(cached_decision, dict):
            raw_winner = cached_decision.get("winner")
            winner = raw_winner if raw_winner in set("abcd") else None
            tied = [
                value
                for value in cached_decision.get("tied", [])
                if value in set("abcd")
            ]
            tie_status = str(cached_decision.get("tie_status", "abstained"))
            tiebreak_reason = str(cached_decision.get("tiebreak_reason", ""))
            print("  resumed final candidate decision", flush=True)
        else:
            decided = {
                label: result
                for label, result in candidate_results.items()
                if result.final_score is not None
                and not result.abstained
                and result.eligible
            }
            tied: list[str] = []
            tiebreak_reason = ""
            if not decided:
                winner = None
                tie_status = "abstained"
                ineligible = [
                    label for label, result in candidate_results.items() if not result.eligible
                ]
                tiebreak_reason = (
                    "All candidates were ineligible due to hard failures."
                    if len(ineligible) == len(candidate_results)
                    else "No eligible candidate could be scored; verifier abstains."
                )
            else:
                top_score = max(float(result.final_score) for result in decided.values())
                tied = [
                    label
                    for label, result in decided.items()
                    if abs(float(result.final_score) - top_score) <= args.tie_epsilon
                ]

            if len(tied) == 1:
                winner = tied[0]
                tie_status = "none"
            elif len(tied) > 1:
                print(
                    f"  pointwise tie: {','.join(label.upper() for label in tied)} "
                    "-> comparative tiebreak",
                    flush=True,
                )
                winner, tiebreak_data = verifier.compare_candidates(
                    prompt,
                    {label: responses[label] for label in tied},
                    args.target_context,
                    applicable_dimensions,
                )
                tiebreak_reason = str(tiebreak_data.get("reason", "")).strip()
                tie_status = "resolved" if winner else "abstained"
                if winner:
                    print(f"  tiebreak winner: {winner.upper()}", flush=True)
                else:
                    print("  tiebreak unresolved: verifier abstains", flush=True)
            case_state["decision"] = {
                "winner": winner,
                "tied": tied,
                "tie_status": tie_status,
                "tiebreak_reason": tiebreak_reason,
            }
            _save_checkpoint(checkpoint_path, checkpoint)

        human = (row.get("human_chosen") or "").strip().lower()
        verifier_winner = winner or "tie"
        correct = "" if not human or not winner else int(winner == human)
        summary.append(
            {
                "set_id": row.get("set_id", case_id),
                "prompt_id": row.get("prompt_id", ""),
                "domain_id": domain_id,
                "human_chosen": human,
                "verifier_winner": verifier_winner,
                "verifier_correct": correct,
                "tie_status": tie_status,
                "tie_candidates": "|".join(tied) if len(tied) > 1 else "",
                "abstained_candidates": "|".join(
                    label for label in "abcd" if candidate_results[label].abstained
                ),
                "hard_fail_candidates": "|".join(
                    label for label in "abcd" if candidate_results[label].hard_fail
                ),
                "ineligible_candidates": "|".join(
                    label
                    for label in "abcd"
                    if not getattr(
                        candidate_results[label],
                        "eligible",
                        not candidate_results[label].hard_fail,
                    )
                ),
                "score_a": candidate_results["a"].final_score,
                "score_b": candidate_results["b"].final_score,
                "score_c": candidate_results["c"].final_score,
                "score_d": candidate_results["d"].final_score,
            }
        )
        details.append(
            {
                "set_id": row.get("set_id", case_id),
                "prompt_id": row.get("prompt_id", ""),
                "domain_id": domain_id,
                "prompt": prompt,
                "human_chosen": human,
                "label_source": (row.get("label_source") or "").strip(),
                "target_context": args.target_context,
                "pipeline_version": VERIFIER_PIPELINE_VERSION,
                "backend": args.backend,
                "model": client.model,
                "search_provider": args.search_provider,
                "search_model": getattr(client, "retrieval_model", client.model),
                "search_depth": getattr(client, "search_depth", None),
                "retrieval_system": getattr(
                    client, "retrieval_system", args.search_provider
                ),
                "retrieval_model_disclosure": getattr(
                    client, "retrieval_model_disclosure", None
                ),
                "applicable_dimensions": [
                    item.__dict__ for item in applicable_dimensions
                ],
                "verifier_winner": verifier_winner,
                "tie_status": tie_status,
                "tie_candidates": tied if len(tied) > 1 else [],
                "tiebreak_reason": tiebreak_reason,
                "candidates": {
                    label: {
                        "response": responses[label],
                        **candidate_results[label].__dict__,
                    }
                    for label in "abcd"
                },
            }
        )
        details_path = _write_outputs(args.output_csv, summary, details)

    details_path = _write_outputs(args.output_csv, summary, details)
    labelled_decided = [
        r for r in summary if r["human_chosen"] and r["verifier_winner"] != "tie"
    ]
    labelled_total = [r for r in summary if r["human_chosen"]]
    if labelled_total:
        accuracy = (
            sum(int(r["verifier_correct"]) for r in labelled_decided)
            / len(labelled_decided)
            if labelled_decided
            else None
        )
        print(
            json.dumps(
                {
                    "n_labelled": len(labelled_total),
                    "n_decided": len(labelled_decided),
                    "coverage": len(labelled_decided) / len(labelled_total),
                    "best_of_4_accuracy_on_decided": accuracy,
                },
                indent=2,
            )
        )
    print(f"Saved {args.output_csv}")
    print(f"Saved {details_path}")
    print(f"Checkpoint {checkpoint_path}")


if __name__ == "__main__":
    main()
