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
import json
from pathlib import Path

from verifier import (
    CulturalVerifier,
    OllamaClient,
    OpenRouterClient,
    RetrievalRoutedClient,
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
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--target-context", default="Germany")
    parser.add_argument("--backend", choices=("ollama", "openrouter"), default="ollama")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--search-provider",
        choices=("same", "openrouter"),
        default="same",
        help="Use the judge backend for evidence calls or route only evidence calls through OpenRouter.",
    )
    parser.add_argument("--search-model", default=None)
    parser.add_argument("--limit", type=int, default=0)
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
        OllamaClient(model=args.model)
        if args.backend == "ollama"
        else OpenRouterClient(model=args.model)
    )
    client = (
        RetrievalRoutedClient(
            judge_client,
            OpenRouterClient(model=args.search_model),
        )
        if args.search_provider == "openrouter" and args.backend != "openrouter"
        else judge_client
    )
    verifier = CulturalVerifier(client)
    summary: list[dict[str, object]] = []
    details: list[dict[str, object]] = []

    retrieval_label = (
        f"openrouter/{client.retrieval_model}"
        if isinstance(client, RetrievalRoutedClient)
        else f"same/{client.model}"
    )
    print(
        f"backend={args.backend} model={client.model} retrieval={retrieval_label}",
        flush=True,
    )

    for index, row in enumerate(rows, 1):
        prompt = row["prompt"]
        case_id = row.get("set_id") or row.get("prompt_id") or f"row_{index}"
        domain_id = (row.get("domain_id") or "").strip().upper()
        print(f"[{index}/{len(rows)}] {case_id}", flush=True)

        applicable_dimensions = verifier.plan_dimensions(
            prompt,
            args.target_context,
            domain_id or None,
        )

        candidate_results = {}
        responses = {}
        for label in "abcd":
            response = row[f"response_{label}"]
            responses[label] = response
            print(f"  candidate {label.upper()}", flush=True)
            candidate_results[label] = verifier.verify(
                prompt,
                response,
                args.target_context,
                applicable_dimensions=applicable_dimensions,
            )

        decided = {
            label: result
            for label, result in candidate_results.items()
            if result.final_score is not None
            and not result.abstained
            and getattr(result, "eligible", not result.hard_fail)
        }
        tied: list[str] = []
        tiebreak_reason = ""
        if not decided:
            winner = None
            tie_status = "abstained"
            ineligible = [
                label
                for label, result in candidate_results.items()
                if not getattr(result, "eligible", not result.hard_fail)
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
                "target_context": args.target_context,
                "backend": args.backend,
                "model": client.model,
                "search_provider": args.search_provider,
                "search_model": getattr(client, "retrieval_model", client.model),
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

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
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
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)

    details_path = args.output_csv.with_suffix(".details.json")
    details_path.write_text(
        json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8"
    )

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


if __name__ == "__main__":
    main()
