"""Standalone evidence-grounded cultural verifier.

The verifier is independent of reward-model scores. It supports:
- OpenRouter: hosted judge + OpenRouter web search
- Ollama: local judge + Ollama web search

Five equally weighted dimensions:
1. evidence_grounding
2. contextual_appropriateness
3. nonessentialism
4. variation_and_uncertainty
5. actionable_helpfulness
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_LOCAL_CHAT_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_WEB_SEARCH_URL = "https://ollama.com/api/web_search"

DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")

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


class JSONClient(Protocol):
    def json_call(
        self,
        system: str,
        user_payload: dict[str, Any],
        *,
        web_search: bool = False,
        max_results: int = 5,
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        ...


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


class OpenRouterClient:
    """OpenRouter client with optional server-side web search."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set OPENROUTER_API_KEY before using --backend openrouter.")
        self.model = model or DEFAULT_OPENROUTER_MODEL

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
            payload["tools"] = [{
                "type": "openrouter:web_search",
                "parameters": {
                    "max_results": max_results,
                    "max_total_results": max(8, max_results),
                    "search_context_size": "medium",
                },
            }]

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
        return _extract_json(message.get("content") or "{}"), self._sources_from_annotations(message)


class OllamaClient:
    """Local Ollama judge plus Ollama's web-search API for evidence retrieval.

    Local model calls require no API key. Web search requires OLLAMA_API_KEY.
    """

    def __init__(
        self,
        model: str | None = None,
        local_url: str | None = None,
        web_api_key: str | None = None,
    ):
        self.model = model or DEFAULT_OLLAMA_MODEL
        self.local_url = local_url or OLLAMA_LOCAL_CHAT_URL
        self.web_api_key = web_api_key or os.getenv("OLLAMA_API_KEY")

    def _web_search(
        self,
        user_payload: dict[str, Any],
        max_results: int,
    ) -> list[dict[str, str]]:
        if not self.web_api_key:
            raise RuntimeError(
                "OLLAMA_API_KEY is required for evidence retrieval with --backend ollama. "
                "Create a free Ollama API key and export it as OLLAMA_API_KEY."
            )

        claim = str(user_payload.get("claim", "")).strip()
        target = str(user_payload.get("target_context", "")).strip()
        context = str(user_payload.get("prompt_context", "")).strip()
        query = " ".join(part for part in (claim, target, context[:300]) if part).strip()
        if not query:
            query = json.dumps(user_payload, ensure_ascii=False)[:1000]

        response = requests.post(
            OLLAMA_WEB_SEARCH_URL,
            headers={
                "Authorization": f"Bearer {self.web_api_key}",
                "Content-Type": "application/json",
            },
            json={"query": query, "max_results": max_results},
            timeout=90,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        clean: list[dict[str, str]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            clean.append({
                "url": url,
                "title": str(item.get("title", "")).strip(),
                "content": str(item.get("content", "")).strip()[:2500],
            })
        return clean

    def json_call(
        self,
        system: str,
        user_payload: dict[str, Any],
        *,
        web_search: bool = False,
        max_results: int = 5,
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        sources: list[dict[str, str]] = []
        payload_for_model = dict(user_payload)

        if web_search:
            sources = self._web_search(user_payload, max_results)
            payload_for_model["retrieved_web_evidence"] = sources
            system += (
                " Use only the supplied retrieved_web_evidence for external evidence. "
                "Describe it faithfully; do not invent unseen sources."
            )

        response = requests.post(
            self.local_url,
            headers={"Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(payload_for_model, ensure_ascii=False)},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            timeout=300,
        )
        response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        return _extract_json(message.get("content") or "{}"), sources


class CulturalVerifier:
    """Independent, evidence-grounded verifier for one candidate response."""

    def __init__(self, client: JSONClient):
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
        data, sources = self.client.json_call(
            "Return JSON only. Verify the supplied claim using the supplied/retrieved web evidence. Search broadly; do NOT restrict evidence "
            "to a preset list of websites. Prefer current primary, official, survey, corpus, scholarly, or otherwise authoritative evidence "
            "when available. Distinguish a cultural tendency from a universal rule. Lack of evidence is not contradiction. Verdict must be "
            "exactly one of: supported, contradicted, mixed, not_enough_evidence.",
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
            sources=sources,
        )

    @staticmethod
    def evidence_grounding(checks: list[ClaimCheck]) -> float:
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

        final_score = sum(dimensions.values()) / len(dimensions)
        failures = self.detect_hard_failures(prompt, response, target_context, checks)

        return VerifierResult(
            final_score=round(final_score, 6),
            dimensions={k: round(v, 6) for k, v in dimensions.items()},
            claims=claims,
            claim_checks=[asdict(c) for c in checks],
            hard_failures=failures,
        )
