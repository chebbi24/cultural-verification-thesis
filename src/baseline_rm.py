"""Independent Skywork reward-model Best-of-4 baseline.

This file is intentionally separate from verifier.py: the reward-model score is
never used by the proposed cultural verifier.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

DEFAULT_RM = "Skywork/Skywork-Reward-V2-Qwen3-4B"


class SkyworkRewardModel:
    def __init__(self, model_name: str = DEFAULT_RM, device_map: str = "auto"):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            torch_dtype="auto",
            device_map=device_map,
            num_labels=1,
        ).eval()

    def score(self, prompt: str, response: str) -> float:
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response},
        ]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=4096)
        device = next(self.model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with self.torch.no_grad():
            return float(self.model(**inputs).logits.squeeze().float().cpu())


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
    parser.add_argument("--model", default=DEFAULT_RM)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = read_rows(args.input_csv)
    if args.limit > 0:
        rows = rows[: args.limit]
    rm = SkyworkRewardModel(args.model)
    output = []

    for index, row in enumerate(rows, 1):
        scores = {label: rm.score(row["prompt"], row[f"response_{label}"]) for label in "abcd"}
        winner = max(scores, key=scores.get)
        human = (row.get("human_chosen") or "").strip().lower()
        output.append({
            "set_id": row.get("set_id", f"row_{index}"),
            "prompt_id": row.get("prompt_id", ""),
            "human_chosen": human,
            "rm_winner": winner,
            "rm_correct": int(bool(human) and winner == human),
            **{f"rm_score_{label}": scores[label] for label in "abcd"},
        })

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["set_id", "prompt_id", "human_chosen", "rm_winner", "rm_correct"] + [f"rm_score_{x}" for x in "abcd"]
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(output)

    labelled = [row for row in output if row["human_chosen"]]
    if labelled:
        accuracy = sum(int(row["rm_correct"]) for row in labelled) / len(labelled)
        print(json.dumps({"n_labelled": len(labelled), "best_of_4_accuracy": accuracy}, indent=2))


if __name__ == "__main__":
    main()
