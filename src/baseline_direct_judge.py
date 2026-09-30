"""Frozen direct-LLM Best-of-4 cultural-appropriateness baseline.

The baseline uses the same D01-D10 rubric as Vericult but performs one direct
judgment over A-D. It does not retrieve evidence and does not call Vericult.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Literal

import requests
from pydantic import BaseModel, ConfigDict

DEFAULT_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_TIMEOUT = 180.0
DEFAULT_PERMUTATION_SEED = 20260930
RUBRIC_PATH = Path(__file__).resolve().parent / "cultverify" / "resources" / "rubric.csv"

SYSTEM_PROMPT = """You are a direct Best-of-4 evaluator of cultural appropriateness.
Use the supplied D01-D10 rubric as the evaluation framework. Judge only the prompt
and the four candidate responses supplied in this request. Do not retrieve external
evidence, do not assume access to human labels, and do not invent missing context.

First assess whether each candidate is culturally acceptable under the applicable
rubric dimensions. A material cultural misalignment makes that candidate
unacceptable. If every candidate is unacceptable, return no_acceptable_candidate.
If the supplied prompt and responses do not provide a sufficient basis to establish
the comparison without external retrieval, return insufficient_evidence.

Otherwise choose the single most culturally appropriate eligible candidate. Prefer
contextual accuracy, appropriate regional and interpersonal variation,
non-stereotyping, and accurate handling of relevant institutional constraints.
Do not reward verbosity. If eligible candidates share the best position without a
defensible unique winner, return no_clear_winner.

Return only JSON matching the supplied schema."""


class JudgeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    winner: Literal["A", "B", "C", "D", "no_clear_winner", "no_acceptable_candidate", "insufficient_evidence"]
    reasoning: str


def read_rows(path: Path) -> list[dict[str, str]]:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    first = sample.splitlines()[0] if sample.splitlines() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def rubric_text() -> str:
    with RUBRIC_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if [row["dimension_id"] for row in rows] != [f"D{i:02}" for i in range(1, 11)]:
        raise ValueError("Direct judge requires the frozen D01-D10 rubric")
    return "\n".join(
        f"{row['dimension_id']} {row['dimension_name']}: {row['definition']} "
        f"Scoring question: {row['scoring_question']}"
        for row in rows
    )


def decision_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "winner": {
                "type": "string",
                "enum": [
                    "A",
                    "B",
                    "C",
                    "D",
                    "no_clear_winner",
                    "no_acceptable_candidate",
                    "insufficient_evidence",
                ],
            },
            "reasoning": {"type": "string", "minLength": 1},
        },
        "required": ["winner", "reasoning"],
        "additionalProperties": False,
    }


def deterministic_presentation(
    responses: dict[str, str], prompt_id: str, seed: int = DEFAULT_PERMUTATION_SEED
) -> tuple[dict[str, str], dict[str, str], str]:
    """Permute original candidates deterministically and return presented->original mapping."""
    if set(responses) != set("ABCD"):
        raise ValueError("Direct judge requires exactly candidates A-D")
    digest = hashlib.sha256(f"{seed}:{prompt_id}".encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    original_order = list("ABCD")
    rng.shuffle(original_order)
    presented_labels = list("ABCD")
    presented = {
        presented_label: responses[original_label]
        for presented_label, original_label in zip(presented_labels, original_order, strict=True)
    }
    mapping = dict(zip(presented_labels, original_order, strict=True))
    return presented, mapping, "".join(original_order)


def judge(
    prompt: str,
    responses: dict[str, str],
    *,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> JudgeDecision:
    if set(responses) != set("ABCD"):
        raise ValueError("Direct judge requires exactly candidates A-D")

    payload = {
        "rubric": rubric_text(),
        "prompt": prompt,
        "candidates": responses,
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
        ],
        "format": decision_schema(),
        "think": False,
        "stream": False,
        "options": {"temperature": 0},
    }

    last_error: Exception | None = None
    for _ in range(2):
        try:
            response = requests.post(ollama_url, json=body, timeout=timeout)
            response.raise_for_status()
            raw = response.json()["message"]["content"]
            decision = JudgeDecision.model_validate_json(raw)
            return decision
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            last_error = exc
    raise RuntimeError("Direct judge failed after bounded retry") from last_error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--permutation-seed", type=int, default=DEFAULT_PERMUTATION_SEED)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = read_rows(args.input_csv)
    if args.limit > 0:
        rows = rows[: args.limit]

    output = []
    for index, row in enumerate(rows, 1):
        prompt_id = row.get("prompt_id", f"row_{index}")
        responses = {label: row[f"response_{label.lower()}"] for label in "ABCD"}
        presented, mapping, order = deterministic_presentation(responses, prompt_id, args.permutation_seed)
        try:
            decision = judge(
                row["prompt"],
                presented,
                model=args.model,
                ollama_url=args.ollama_url,
                timeout=args.timeout,
            )
            presented_winner = decision.winner
            winner = mapping[presented_winner] if presented_winner in mapping else presented_winner
            status, reasoning, error = "completed", decision.reasoning, ""
        except RuntimeError as exc:
            status, presented_winner, winner, reasoning, error = "failed", "", "", "", str(exc)

        output.append(
            {
                "prompt_id": prompt_id,
                "judge_model": args.model,
                "judge_permutation_seed": args.permutation_seed,
                "judge_status": status,
                "judge_presented_order": order,
                "judge_winner_presented": presented_winner,
                "judge_winner": winner,
                "judge_reasoning": reasoning,
                "judge_error": error,
            }
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "prompt_id",
        "judge_model",
        "judge_permutation_seed",
        "judge_status",
        "judge_presented_order",
        "judge_winner_presented",
        "judge_winner",
        "judge_reasoning",
        "judge_error",
    ]
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)


if __name__ == "__main__":
    main()
