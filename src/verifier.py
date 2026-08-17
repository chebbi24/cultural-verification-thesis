"""Standalone evidence-grounded cultural verifier.

Research goal
-------------
Score culturally appropriate responses *independently* of any reward model so
that the verifier can be compared fairly against reward-model baselines.

Primary score
-------------
Five equally weighted dimensions, each normalized to [0, 1]:
1. evidence_grounding
2. contextual_appropriateness
3. nonessentialism
4. variation_and_uncertainty
5. actionable_helpfulness

No reward-model score enters the verifier score. Hard failures are reported as
an interpretable diagnostic and are not given an additional hidden penalty.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

VERDICTS = {"supported", "contradicted", "mixed", "not_enough_evidence"}
RUBRIC_KEYS = (
    "contextual_appropriateness",
    "nonessentialism",
    "variation_and_uncertainty",
    "actionable_helpfulness",
)


@dataclass
class ClaimCheck:
    claim: str
    verdict: str
    confidence: float
    reason: str
    sources: list[dict[str, str]]


@dataclass
class VerifierResult:
    final_score: float
    dimensions: dict[str, float]
    claims: list[str]
    claim_checks: list[dict[str, Any]]
    hard_failures: list[dict[str, str]]


class OpenRouterClient:
    """Small OpenRouter client with optional server-side web search."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set OPENROUTER_API_KEY before running the verifier.")
        self.model = model or DEFAULT_MODEL

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    @staticmethod
    def _sources_from_annotations(message: dict[str, Any]) -> list[dict[str, str]]:
        found: dict[str, dict[str, str]] = {}
        for ann in message.get("annotations") or []:
            citation = ann.get("url_citation") if isinstance(ann, dict) else None
            if not citation and isinstance(ann, dict) and ann.get("type") == "url_citation":
                citation = ann
            if not isinstance(citation, dict):
                continue
            url = str(citation.get("url", "")).strip()
            if not url:
                continue
            found[url] = {
                "url": url,
                "title": str(citation.get("title", "")).strip(),
                "content": str(citation.get("content", "")).strip()[:2500],
            }
        return list(found.values())

    def json_call(
        self,
        system: str,
        user_payload: dict[str, Any],
        *,
        web_search: bool = False,
        max_results: int = 5,
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
        }
        if web_search:
            payload["tools"] = [
                {
                    "type": "openrouter:web_search",
                    "parameters": {
                        "max_results": max_results,
                        "max_total_results": max(8, max_results),
                        "search_context_size": "medium",
                    },
                }
            ]

        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        return self._extract_json(message.get("content") or "{}"), self._sources_from_annotations(message)


class CulturalVerifier:
    """Independent, evidence-grounded verifier for one candidate response."""

    def __init__(self, client: OpenRouterClient):
        self.client = client

    def extract_claims(self, prompt: str, response: str, target_context: str) -> list[str]:
        data, _ = self.client.json_call(
            "Return JSON only. Extract independently verifiable claims from the response that matter for cultural correctness. "
            "A claim is verifiable if external evidence could reasonably support or contradict it. Include claims about laws, statistics, "
            "history, language use, social practices, etiquette, institutions, or claimed cultural norms. Do not invent claims, and do not "
            "turn advice, preferences, hedged possibilities, or pure value judgments into factual claims.",
            {
                "prompt": prompt,
                "response": response,
                "target_context": target_context,
                "schema": {"claims": ["atomic claim"]},
            },
        )
        claims = data.get("claims", [])
        return [str(c).strip() for c in claims if str(c).strip()][:12]

    def check_claim(self, prompt: str, claim: str, target_context: str) -> ClaimCheck:
        data, annotations = self.client.json_call(
            "Return JSON only. Verify the supplied claim using web search. Search broadly across the web; do NOT restrict yourself to a preset "
            "list of websites. Prefer current primary, official, survey, corpus, scholarly, or otherwise authoritative evidence when available, "
            "but use the best relevant evidence you can find. Distinguish a cultural tendency from a universal rule. Do not interpret lack of "
            "evidence as contradiction. Verdict must be exactly one of: supported, contradicted, mixed, not_enough_evidence.",
            {
                "prompt_context": prompt,
                "target_context": target_context,
                "claim": claim,
                "schema": {
                    "verdict": "supported|contradicted|mixed|not_enough_evidence",
                    "confidence": 0.0,
                    "reason": "brief evidence-grounded explanation",
                },
            },
            web_search=True,
        )
        verdict = str(data.get("verdict", "not_enough_evidence")).strip().lower()
        if verdict not in VERDICTS:
            verdict = "not_enough_evidence"
        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        return ClaimCheck(
            claim=claim,
            verdict=verdict,
            confidence=confidence,
            reason=str(data.get("reason", "")).strip(),
            sources=annotations,
        )

    @staticmethod
    def evidence_grounding(checks: list[ClaimCheck]) -> float:
        """Transparent, untuned score: equal credit across claims.

        supported=1.0, mixed=0.5, not_enough_evidence=0.5 (neutral),
        contradicted=0.0. If there are no verifiable claims, use neutral 0.5.
        """
        if not checks:
            return 0.5
        points = {
            "supported": 1.0,
            "mixed": 0.5,
            "not_enough_evidence": 0.5,
            "contradicted": 0.0,
        }
        return sum(points[c.verdict] for c in checks) / len(checks)

    def cultural_rubric(
        self,
        prompt: str,
        response: str,
        target_context: str,
        checks: list[ClaimCheck],
    ) -> dict[str, float]:
        compact_checks = [
            {"claim": c.claim, "verdict": c.verdict, "reason": c.reason}
            for c in checks
        ]
        data, _ = self.client.json_call(
            "Return JSON only. Score the response on four CULTURAL dimensions from 0 to 2 using the prompt/context and supplied claim checks. "
            "Do not re-score factual accuracy; that is handled separately by evidence_grounding. Dimensions: "
            "contextual_appropriateness = fits the stated cultural/local situation rather than defaulting to another culture; "
            "nonessentialism = avoids stereotypes and treating a population as homogeneous; "
            "variation_and_uncertainty = appropriately represents regional, social, individual, or temporal variation when relevant; "
            "actionable_helpfulness = gives useful advice that remains appropriate in the stated context. "
            "Use only integer scores 0, 1, or 2 for each dimension.",
            {
                "prompt": prompt,
                "response": response,
                "target_context": target_context,
                "claim_checks": compact_checks,
                "schema": {key: 0 for key in RUBRIC_KEYS},
            },
        )
        scores: dict[str, float] = {}
        for key in RUBRIC_KEYS:
            try:
                raw = int(data.get(key, 0))
            except (TypeError, ValueError):
                raw = 0
            scores[key] = max(0, min(2, raw)) / 2.0
        return scores

    def detect_hard_failures(
        self,
        prompt: str,
        response: str,
        target_context: str,
        checks: list[ClaimCheck],
    ) -> list[dict[str, str]]:
        compact_checks = [
            {"claim": c.claim, "verdict": c.verdict, "reason": c.reason}
            for c in checks
        ]
        data, _ = self.client.json_call(
            "Return JSON only. Identify only severe, clearly evidenced cultural failures. Allowed categories: fabricated_rule_or_law, "
            "direct_evidence_contradiction, harmful_stereotype, cultural_essentialism, wrong_context_or_country, ignored_explicit_context. "
            "Do not flag merely imperfect wording. Return an empty list if no severe failure is clear. These flags are diagnostics and must not "
            "change the numeric verifier score.",
            {
                "prompt": prompt,
                "response": response,
                "target_context": target_context,
                "claim_checks": compact_checks,
                "schema": {"hard_failures": [{"category": "...", "reason": "..."}]},
            },
        )
        failures = data.get("hard_failures", [])
        clean: list[dict[str, str]] = []
        for item in failures if isinstance(failures, list) else []:
            if isinstance(item, dict) and item.get("category"):
                clean.append({
                    "category": str(item.get("category", "")).strip(),
                    "reason": str(item.get("reason", "")).strip(),
                })
        return clean[:6]

    def verify(self, prompt: str, response: str, target_context: str = "Germany") -> VerifierResult:
        claims = self.extract_claims(prompt, response, target_context)
        checks = [self.check_claim(prompt, claim, target_context) for claim in claims]

        dimensions = {"evidence_grounding": self.evidence_grounding(checks)}
        dimensions.update(self.cultural_rubric(prompt, response, target_context, checks))

        # Option A: equal weighting, no learned/tuned parameters and no RM contribution.
        final_score = sum(dimensions.values()) / len(dimensions)
        failures = self.detect_hard_failures(prompt, response, target_context, checks)

        return VerifierResult(
            final_score=round(final_score, 6),
            dimensions={k: round(v, 6) for k, v in dimensions.items()},
            claims=claims,
            claim_checks=[asdict(c) for c in checks],
            hard_failures=failures,
        )
