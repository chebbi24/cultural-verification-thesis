"""Reward-model ranking plus search-augmented German cultural verification.

Primary result: CARB-comparable pointwise Best-of-4 accuracy.
Secondary result: an experimental evidence-augmented cultural score.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:  # Allows --help and static validation before optional dependencies are installed.
    requests = None


DEFAULT_RM = "Skywork/Skywork-Reward-V2-Qwen3-4B"

SOURCE_ALLOWLIST = {
    "D01": ["destatis.de", "umweltbundesamt.de", "bundesumweltministerium.de", "verbraucherzentrale.de", "deutschland.de"],
    "D02": ["ids-mannheim.de", "dwds.de", "duden.de", "atlas-alltagssprache.de"],
    "D03": ["destatis.de", "antidiskriminierungsstelle.de", "gesetze-im-internet.de", "bpb.de"],
    "D04": ["worldvaluessurvey.org", "europeanvaluesstudy.eu", "gesis.org", "destatis.de"],
    "D05": ["gesetze-im-internet.de", "bundesregierung.de", "bund.de", "kmk.org", "antidiskriminierungsstelle.de"],
    "D06": ["gesetze-im-internet.de", "antidiskriminierungsstelle.de", "europeanvaluesstudy.eu", "worldvaluessurvey.org"],
    "D07": ["destatis.de", "bmfsfj.de", "gesetze-im-internet.de", "antidiskriminierungsstelle.de"],
    "D08": ["kmk.org", "arbeitsagentur.de", "gesetze-im-internet.de", "bundeswahlleiterin.de", "unesco.de"],
    "D09": ["bpb.de", "unesco.de", "stiftung-denkmal.de", "dhm.de", "gesetze-im-internet.de"],
    "D10": ["destatis.de", "antidiskriminierungsstelle.de", "bamf.de", "kmk.org", "gesetze-im-internet.de"],
}

TRUTH_MODE = {
    "D01": "contextual_practice", "D02": "linguistic_context", "D03": "contextual_norm",
    "D04": "survey_distribution", "D05": "current_authoritative_rule", "D06": "plural_contextual_practice",
    "D07": "mixed_statistics_and_context", "D08": "mixed_institution_and_context",
    "D09": "historical_context", "D10": "mixed_statistics_rights_and_context",
}


@dataclass
class Evidence:
    title: str
    url: str
    content: str
    score: float | None = None


@dataclass
class CandidateResult:
    label: str
    raw_rm_score: float
    rm_probability: float
    supported_claim_fraction: float
    cultural_rubric: float
    contradiction_fraction: float
    verified_reward: float
    claims: list[dict[str, Any]]
    sources: list[str]


class SkyworkRewardModel:
    """Pointwise Bradley-Terry reward model used in the CARB model suite."""

    def __init__(self, model_name: str = DEFAULT_RM, device_map: str = "auto"):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install verifier_core/requirements.txt before loading the reward model") from exc
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            torch_dtype="auto",
            device_map=device_map,
            num_labels=1,
        ).eval()

    def score(self, prompt: str, response: str) -> float:
        # Skywork's model card specifies a user/assistant exchange and no system message.
        messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": response}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=4096)
        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with self.torch.no_grad():
            return float(self.model(**inputs).logits.squeeze().float().cpu())


class TavilySearch:
    """Domain-constrained search using Tavily's documented REST endpoint."""

    def __init__(self, api_key: str | None = None, max_results: int = 5):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set TAVILY_API_KEY for search-augmented verification")
        self.max_results = max_results

    def search(self, query: str, domains: list[str]) -> list[Evidence]:
        if requests is None:
            raise RuntimeError("Install verifier_core/requirements.txt before using web search")
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "include_domains": domains,
            "include_answer": False,
            "include_raw_content": False,
            "max_results": self.max_results,
        }
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=45)
        response.raise_for_status()
        data = response.json()
        return [Evidence(r.get("title", ""), r["url"], r.get("content", ""), r.get("score")) for r in data.get("results", [])]


class OpenAICompatibleJudge:
    """JSON judge for any OpenAI-compatible endpoint, including a local server."""

    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("JUDGE_MODEL", "Qwen/Qwen3-8B")
        self.base_url = (base_url or os.getenv("JUDGE_BASE_URL", "http://localhost:8000/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("JUDGE_API_KEY", "local")

    def json_call(self, system: str, user: str) -> Any:
        if requests is None:
            raise RuntimeError("Install verifier_core/requirements.txt before calling the judge")
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
        }
        res = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.I).strip()
        return json.loads(content)


class SearchAugmentedVerifier:
    """SAFE/FActScore-inspired claim decomposition, retrieval, and checking."""

    def __init__(self, judge: OpenAICompatibleJudge, search: TavilySearch):
        self.judge = judge
        self.search = search

    def decompose(self, prompt: str, response: str, truth_mode: str) -> list[dict[str, str]]:
        result = self.judge.json_call(
            "Return JSON only. Decompose the answer into independently checkable claims. "
            "Classify each as factual, legal_current, survey_distribution, linguistic, contextual_norm, or value_judgment. "
            "Do not convert advice or acknowledged uncertainty into a false factual claim.",
            json.dumps({"prompt": prompt, "response": response, "truth_mode": truth_mode, "schema": {"claims": [{"claim": "...", "type": "..."}]}}),
        )
        return result.get("claims", [])[:12]

    def query_for(self, claim: str, prompt: str, domain_id: str) -> str:
        result = self.judge.json_call(
            "Return JSON only. Write one short German-or-English web query that can verify the claim using an official German, survey, corpus, or scholarly source. Include Germany and the relevant institution or concept; do not include site: syntax.",
            json.dumps({"claim": claim, "prompt": prompt, "allowed_domains": SOURCE_ALLOWLIST[domain_id], "schema": {"query": "..."}}),
        )
        return str(result["query"])[:300]

    def check_claim(self, claim: dict[str, str], evidence: list[Evidence], truth_mode: str) -> dict[str, Any]:
        packet = [{"title": e.title, "url": e.url, "content": e.content[:1800]} for e in evidence]
        result = self.judge.json_call(
            "Return JSON only. Judge the claim solely from the evidence. Labels: supported, contradicted, mixed, or not_enough_evidence. "
            "For survey claims require population, item wording, date/wave, and a distribution or uncertainty. "
            "For norms do not treat a descriptive source as a universal rule. For law require a current competent authority.",
            json.dumps({"claim": claim, "truth_mode": truth_mode, "evidence": packet, "schema": {"label": "supported|contradicted|mixed|not_enough_evidence", "reason": "...", "source_urls": []}}),
        )
        return result

    def cultural_rubric(self, prompt: str, response: str, domain_id: str, checked_claims: list[dict[str, Any]]) -> float:
        result = self.judge.json_call(
            "Return JSON only. Score each dimension 0, 1, or 2: situated_appropriateness, uncertainty_and_variation, nonessentialism, actionable_helpfulness. "
            "Do not award factual accuracy here; use the supplied claim checks. Penalise US-default assumptions, invented nationwide rules, stereotypes, and treating survey majorities as every German's view.",
            json.dumps({"prompt": prompt, "response": response, "domain_id": domain_id, "claim_checks": checked_claims, "schema": {"situated_appropriateness": 0, "uncertainty_and_variation": 0, "nonessentialism": 0, "actionable_helpfulness": 0}}),
        )
        values = [max(0, min(2, int(result.get(k, 0)))) for k in ("situated_appropriateness", "uncertainty_and_variation", "nonessentialism", "actionable_helpfulness")]
        return sum(values) / 8.0

    def verify(self, prompt: str, response: str, domain_id: str) -> tuple[float, float, float, list[dict[str, Any]], list[str]]:
        truth_mode = TRUTH_MODE[domain_id]
        claims = self.decompose(prompt, response, truth_mode)
        checked, all_urls = [], []
        for claim in claims:
            # Pure value judgments are rubric-scored, not falsely fact-checked.
            if claim.get("type") == "value_judgment":
                continue
            query = self.query_for(claim["claim"], prompt, domain_id)
            evidence = self.search.search(query, SOURCE_ALLOWLIST[domain_id])
            verdict = self.check_claim(claim, evidence, truth_mode)
            verdict["claim"] = claim["claim"]
            verdict["query"] = query
            checked.append(verdict)
            all_urls.extend(verdict.get("source_urls", []))
        labels = [c.get("label") for c in checked]
        supported = labels.count("supported") / len(labels) if labels else 0.5
        contradicted = labels.count("contradicted") / len(labels) if labels else 0.0
        rubric = self.cultural_rubric(prompt, response, domain_id, checked)
        return supported, contradicted, rubric, checked, sorted(set(all_urls))


def softmax(values: list[float]) -> list[float]:
    top = max(values)
    exps = [math.exp(v - top) for v in values]
    total = sum(exps)
    return [v / total for v in exps]


def rank_set(prompt: str, domain_id: str, candidates: dict[str, str], rm: SkyworkRewardModel, verifier: SearchAugmentedVerifier) -> dict[str, Any]:
    labels = list(candidates)
    raw = [rm.score(prompt, candidates[label]) for label in labels]
    probabilities = softmax(raw)
    # Independent pointwise judgments plus deterministic shuffling reduce position effects.
    order = labels[:]
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    random.Random(seed).shuffle(order)
    verified = {}
    for label in order:
        supported, contradicted, rubric, claims, sources = verifier.verify(prompt, candidates[label], domain_id)
        verified[label] = (supported, contradicted, rubric, claims, sources)
    results = []
    for label, rm_raw, rm_prob in zip(labels, raw, probabilities):
        supported, contradicted, rubric, claims, sources = verified[label]
        # Novel secondary reward. Keep separate from the CARB-comparable RM winner.
        evidence_culture = 0.55 * supported + 0.45 * rubric
        combined = 0.60 * rm_prob + 0.40 * evidence_culture - 0.25 * contradicted
        results.append(CandidateResult(label, rm_raw, rm_prob, supported, rubric, contradicted, combined, claims, sources))
    rm_winner = max(results, key=lambda r: r.raw_rm_score).label
    verified_winner = max(results, key=lambda r: (r.verified_reward, r.raw_rm_score)).label
    return {"rm_winner": rm_winner, "verified_winner": verified_winner, "candidates": [asdict(r) for r in results]}


def infer_domain(prompt_id: str, prompt_to_domain: dict[str, str]) -> str:
    try:
        return prompt_to_domain[prompt_id]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt_id {prompt_id}; pass --prompts with the final prompt CSV") from exc


def load_domains(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {row["prompt_id"]: row["domain_id"] for row in csv.DictReader(f)}


def evaluate_file(input_path: Path, prompts_path: Path, output_path: Path, model_name: str):
    domains = load_domains(prompts_path)
    rm = SkyworkRewardModel(model_name)
    verifier = SearchAugmentedVerifier(OpenAICompatibleJudge(), TavilySearch())
    output_rows, detailed = [], []
    with input_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        candidates = {k: row[f"response_{k}"] for k in "abcd"}
        result = rank_set(row["prompt"], infer_domain(row["prompt_id"], domains), candidates, rm, verifier)
        human = row.get("human_chosen", "").strip().lower()
        output_rows.append({
            "set_id": row["set_id"], "prompt_id": row["prompt_id"], "human_chosen": human,
            "rm_winner": result["rm_winner"], "verified_winner": result["verified_winner"],
            "rm_correct": int(bool(human) and result["rm_winner"] == human),
            "verified_correct": int(bool(human) and result["verified_winner"] == human),
        })
        detailed.append({"set_id": row["set_id"], **result})
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0]))
        writer.writeheader(); writer.writerows(output_rows)
    output_path.with_suffix(".details.json").write_text(json.dumps(detailed, ensure_ascii=False, indent=2), encoding="utf-8")
    labelled = [r for r in output_rows if r["human_chosen"]]
    if labelled:
        print(json.dumps({
            "n": len(labelled),
            "carb_comparable_best_of_4_accuracy": sum(r["rm_correct"] for r in labelled) / len(labelled),
            "experimental_verified_best_of_4_accuracy": sum(r["verified_correct"] for r in labelled) / len(labelled),
        }, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Best-of-4 response CSV")
    parser.add_argument("--prompts", type=Path, required=True, help="final_prompts.csv")
    parser.add_argument("--output", type=Path, default=Path("verification_results.csv"))
    parser.add_argument("--reward-model", default=DEFAULT_RM)
    args = parser.parse_args()
    evaluate_file(args.input, args.prompts, args.output, args.reward_model)


if __name__ == "__main__":
    main()
