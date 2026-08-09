#!/usr/bin/env python3
"""Run agentic retrieval, evidence-only judging, verifier scoring, and hybrid fusion."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from cultural_verifier.io import append_jsonl, read_csv, write_csv, write_json
from cultural_verifier.judge import EvidenceJudge
from cultural_verifier.scoring import (
    ScoringConfig,
    aggregate_evidence,
    hybrid_probabilities,
    softmax,
    verifier_score,
)
from cultural_verifier.search import AgenticWebSearch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Long-form candidates with raw_rm_score")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--reference-claims", type=Path, default=REPO_ROOT / "data/evidence/reference_claims.csv")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config/scoring.json")
    parser.add_argument("--search-model", default="gpt-5.5")
    parser.add_argument("--judge-model", default="gpt-5.4-mini")
    parser.add_argument("--reasoning-effort", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--max-claims", type=int, default=6)
    parser.add_argument("--limit-candidates", type=int)
    args = parser.parse_args()

    config = ScoringConfig.from_json(args.config)
    rows = read_csv(args.input)
    if args.limit_candidates is not None:
        rows = rows[: args.limit_candidates]
    required = {"set_id", "prompt_id", "candidate_id", "prompt_text", "response_text", "raw_rm_score"}
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise ValueError(f"Input is missing columns: {', '.join(sorted(missing))}")

    references = {row["prompt_id"]: row for row in read_csv(args.reference_claims)}
    search = AgenticWebSearch(model=args.search_model, reasoning_effort=args.reasoning_effort)
    judge = EvidenceJudge(model=args.judge_model)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    details_path = args.output_dir / "candidate_details.jsonl"
    details_path.unlink(missing_ok=True)

    result_rows = []
    started_at = datetime.now(UTC).isoformat()
    for candidate_index, row in enumerate(rows, 1):
        reference = references[row["prompt_id"]]
        try:
            claims = judge.extract_claims(
                prompt_text=row["prompt_text"],
                response_text=row["response_text"],
                max_claims=args.max_claims,
            )
            claim_results = []
            search_runs = []
            for claim_index, claim in enumerate(claims, 1):
                if claim["type"] == "value_judgment":
                    claim_results.append(
                        {
                            **claim,
                            "label": "not_applicable",
                            "reason": "Value judgment is handled by the cultural rubric.",
                            "cited_urls": [],
                        }
                    )
                    continue
                claim_id = f"{row['candidate_id']}-CL{claim_index:02d}"
                search_row = {
                    "reference_claim_id": claim_id,
                    "prompt_text": row["prompt_text"],
                    "reference_claim_text": claim["claim"],
                    "evidence_requirement": reference["evidence_requirement"],
                    "search_brief": (
                        f"Verify this candidate claim in its exact German context: {claim['claim']}"
                    ),
                }
                search_run = search.search_reference_claim(search_row)
                source_urls = [source.url for source in search_run.sources]
                judgment = judge.judge_claim(
                    prompt_text=row["prompt_text"],
                    candidate_claim=claim["claim"],
                    evidence_brief=search_run.output_text,
                    source_urls=source_urls,
                )
                claim_results.append({**claim, **judgment, "search_claim_id": claim_id})
                search_runs.append(search_run.to_dict())

            evidence = aggregate_evidence(
                result["label"]
                for result in claim_results
                if result["label"] != "not_applicable"
            )
            rubric = judge.score_rubric(
                prompt_text=row["prompt_text"],
                response_text=row["response_text"],
                reference_claim=reference,
                evidence_summary=claim_results,
            )
            score, aligned, effective_weight = verifier_score(
                rubric_score=rubric["rubric_score"],
                evidence=evidence,
                hard_fail=rubric["hard_fail"],
                config=config,
            )
            result = {
                **row,
                "evidence_score": "" if evidence.evidence_score is None else evidence.evidence_score,
                "evidence_coverage": evidence.coverage,
                "contradiction_fraction": evidence.contradiction_fraction,
                "rubric_score": rubric["rubric_score"],
                "hard_fail": str(rubric["hard_fail"]).lower(),
                "hard_fail_reason": rubric["hard_fail_reason"],
                "effective_evidence_weight": effective_weight,
                "verifier_score": score,
                "verifier_label": "aligned" if aligned else "misaligned",
                "score_version": config.score_version,
                "error": "",
            }
            append_jsonl(
                details_path,
                {
                    "candidate_id": row["candidate_id"],
                    "reference_claim": reference,
                    "claims": claim_results,
                    "search_runs": search_runs,
                    "rubric": rubric,
                    "scoring": {
                        "evidence": evidence.__dict__,
                        "effective_evidence_weight": effective_weight,
                        "verifier_score": score,
                    },
                },
            )
        except Exception as exc:  # Preserve other candidates and make failure visible.
            result = {
                **row,
                "evidence_score": "",
                "evidence_coverage": "",
                "contradiction_fraction": "",
                "rubric_score": "",
                "hard_fail": "",
                "hard_fail_reason": "",
                "effective_evidence_weight": "",
                "verifier_score": "",
                "verifier_label": "error",
                "score_version": config.score_version,
                "error": f"{type(exc).__name__}: {exc}",
            }
        result_rows.append(result)
        print(f"[{candidate_index}/{len(rows)}] {row['candidate_id']} {result['verifier_label']}")

    by_set: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in result_rows:
        by_set[row["set_id"]].append(row)
    prompt_rows = []
    for set_id, candidates in sorted(by_set.items()):
        candidates.sort(key=lambda item: item["candidate_id"])
        if not all(row["verifier_score"] != "" for row in candidates):
            continue
        if not all(row.get("rm_probability", "") != "" for row in candidates):
            probabilities = softmax(float(row["raw_rm_score"]) for row in candidates)
            for row, probability in zip(candidates, probabilities, strict=True):
                row["rm_probability"] = probability
        hybrid = hybrid_probabilities(
            rm_probabilities=[float(row["rm_probability"]) for row in candidates],
            verifier_scores=[float(row["verifier_score"]) for row in candidates],
            hard_fails=[row["hard_fail"] == "true" for row in candidates],
            config=config,
        )
        for row, probability in zip(candidates, hybrid, strict=True):
            row["hybrid_probability"] = probability

        def winner(field: str) -> str:
            return max(candidates, key=lambda item: (float(item[field]), item["candidate_id"]))[
                "candidate_id"
            ]

        rm_winner = winner("raw_rm_score")
        verifier_winner = winner("verifier_score")
        hybrid_winner = winner("hybrid_probability")
        prompt_rows.append(
            {
                "set_id": set_id,
                "prompt_id": candidates[0]["prompt_id"],
                "rm_winner": rm_winner,
                "verifier_winner": verifier_winner,
                "hybrid_winner": hybrid_winner,
                "score_version": config.score_version,
            }
        )

    fields = list(result_rows[0])
    if "hybrid_probability" not in fields:
        fields.append("hybrid_probability")
    write_csv(args.output_dir / "candidate_results.csv", result_rows, fields)
    if prompt_rows:
        write_csv(args.output_dir / "prompt_results.csv", prompt_rows, list(prompt_rows[0]))
    write_json(
        args.output_dir / "run_metadata.json",
        {
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "input": str(args.input),
            "candidate_count": len(result_rows),
            "completed_set_count": len(prompt_rows),
            "search_model": args.search_model,
            "judge_model": args.judge_model,
            "search_tool": "Responses API web_search",
            "search_domain_allowlist": None,
            "scoring_config": json.loads(args.config.read_text(encoding="utf-8")),
            "accuracy_status": "not_computed_without_real_human_labels",
        },
    )


if __name__ == "__main__":
    main()
