"""V8 compatibility layer for the standalone evidence-grounded cultural verifier.

V8 keeps the validated V7 clients, schemas, hard-failure protocol, and Best-of-4
interfaces while replacing the failure-prone parts of evidence planning and score
calibration:

* model-authored search questions are never executed directly;
* recommendation/directive spans cannot masquerade as external factual claims;
* recommendation support must be specific to the people/context in the prompt;
* material counter-evidence deterministically downgrades a false ``supported``;
* perfect dimension scores are capped when prompt-specific accommodation is missing;
* confidence and rationales are normalized deterministically; and
* serialized results omit repeated non-applicable dimension boilerplate.

The previous implementation is preserved verbatim in ``verifier_v7_legacy.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import verifier_v7_legacy as _legacy
from verifier_v7_legacy import *  # noqa: F401,F403 - deliberate public API compatibility

VERIFIER_PIPELINE_VERSION = "V8-grounded-calibrated"

_LegacyCulturalVerifier = _legacy.CulturalVerifier
_LegacyDimensionApplicability = _legacy.DimensionApplicability


@dataclass
class DimensionApplicability(_LegacyDimensionApplicability):
    """Prompt-only dimension plan plus frozen prompt-specific evaluation focuses."""

    evaluation_focus: list[str] | None = None


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "been", "being",
    "but", "by", "can", "could", "do", "does", "for", "from", "had", "has",
    "have", "he", "her", "here", "hers", "him", "his", "how", "i", "if", "any", "know",
    "in", "into", "is", "it", "its", "just", "let", "may", "me", "more",
    "my", "of", "on", "or", "our", "please", "should", "so", "some", "than",
    "that", "the", "their", "them", "there", "these", "they", "this", "those",
    "to", "too", "us", "very", "was", "we", "were", "what", "when", "where",
    "which", "who", "why", "will", "with", "would", "you", "your", "draft",
    "write", "make", "help", "assistant", "response", "answer",
}

_CONTEXT_HINTS = {
    "muslim", "muslims", "islam", "islamic", "halal", "jew", "jews", "jewish",
    "kosher", "christian", "christians", "hindu", "hindus", "sikh", "sikhs",
    "religious", "religion", "vegetarian", "vegetarians", "vegan", "vegans",
    "allergy", "allergies", "dietary", "restriction", "restrictions", "disabled",
    "disability", "elderly", "children", "child", "women", "woman", "men", "man",
    "israel", "israeli", "israelis", "arab", "arabs", "turkish", "german",
    "germany", "frankfurt", "berlin", "munich", "workplace", "office", "team",
    "school", "university", "family", "wedding", "funeral", "holiday", "festival",
}

_EVIDENCE_QUERY_TERMS = {
    "legal_or_policy": ["law", "policy", "official guidance"],
    "dietary_or_religious": ["dietary", "religious practice", "accommodation"],
    "social_norm_or_etiquette": ["etiquette", "social norm", "variation"],
    "inclusion_or_discrimination": ["inclusion", "accommodation", "discrimination"],
    "language_or_usage": ["language usage", "pragmatics", "forms of address"],
    "local_or_regional": ["local custom", "regional variation"],
    "historical_or_traditional": ["history", "tradition", "current practice"],
    "demographic_or_statistical": ["survey", "statistics", "population"],
    "institutional_process": ["institutional practice", "official process"],
    "general_factual": ["practice", "context", "evidence"],
}

_DIRECTIVE_MARKERS = (
    "please ", "we'll ", "we will ", "we can ", "i recommend", "i suggest",
    "you should", "you can", "you could", "consider ", "try ", "serve ",
    "offer ", "use ", "say ", "wear ", "choose ", "include ", "avoid ",
    "let us ", "let's ", "here's ", "here is ",
)

_COUNTEREVIDENCE_MARKERS = (
    "prohibit", "prohibited", "forbidden", "religious ban", "avoid alcohol",
    "avoid pork", "do not insist", "should not", "not appropriate", "not accepted",
    "not suitable", "criticized", "criticism", "unwise", "abstain", "abstinence",
    "incompatible", "excluded", "cannot consume", "must not", "not permitted",
)

_INTERNAL_LEAK_MARKERS = (
    "assistant_response_to_score", "user_prompt_context", "retrieved_web_evidence",
    "evidence_checks", "dimension_scores", "schema_name", "response_schema",
)

_MEAT_OR_PORK_MARKERS = (
    "pork", "mett", "ham", "bacon", "sausage", "bratwurst", "schnitzel",
    "sauerbraten", "meat", "beef", "veal", "chicken",
)
_ALCOHOL_MARKERS = (
    "alcohol", "beer", "wine", "schnapps", "schnaps", "spirits", "cocktail",
)
_CONCRETE_FOOD_ALTERNATIVES = (
    "vegetarian option", "vegetarian alternative", "vegan option", "vegan alternative",
    "plant-based", "plant based", "meat-free", "meat free", "halal option",
    "kosher option", "alternative dish", "alternative menu", "separate menu",
)
_CONCRETE_DRINK_ALTERNATIVES = (
    "non-alcoholic", "non alcoholic", "alcohol-free", "alcohol free", "soft drinks",
    "soft drink", "juice", "water", "mocktail", "non-drinkers", "don't drink",
    "do not drink", "without alcohol",
)


def _normalized_text(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = " ".join(str(item).split()).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return output


def _content_terms(text: str, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9'’-]*", text)
    selected: list[str] = []
    for token in tokens:
        normalized = token.casefold().strip("'’-_")
        if len(normalized) < 3 or normalized in _STOPWORDS:
            continue
        if normalized not in selected:
            selected.append(normalized)
        if len(selected) >= limit:
            break
    return selected


def _prompt_context_terms(prompt: str, limit: int = 8) -> list[str]:
    all_terms = _content_terms(prompt, limit=32)
    priority = [term for term in all_terms if term in _CONTEXT_HINTS]
    remaining = [term for term in all_terms if term not in priority]
    return (priority + remaining)[:limit]


def _constraint_evidence_terms(prompt: str) -> set[str]:
    normalized = _normalized_text(prompt)
    terms: set[str] = set()
    mapping = {
        "muslim": {"muslim", "muslims", "islam", "islamic", "halal"},
        "islam": {"muslim", "muslims", "islam", "islamic", "halal"},
        "vegetarian": {"vegetarian", "vegetarians", "vegan", "plant-based"},
        "vegan": {"vegan", "vegans", "vegetarian", "plant-based"},
        "jewish": {"jewish", "jews", "kosher"},
        "kosher": {"jewish", "kosher"},
        "halal": {"muslim", "islam", "halal"},
        "israel": {"israel", "israeli", "israelis"},
        "dietary": {"dietary", "allergy", "allergies", "restriction", "restrictions"},
        "allerg": {"allergy", "allergies", "allergen", "allergens"},
        "disab": {"disabled", "disability", "accessible", "accessibility"},
    }
    for needle, related in mapping.items():
        if needle in normalized:
            terms.update(related)
    return terms


def _sanitize_reason(reason: str, max_chars: int = 700) -> str:
    """Remove repeated model prose and accidental prompt/schema leakage."""

    text = " ".join(str(reason).split()).strip()
    if not text:
        return "No rationale supplied."
    pieces = re.split(r"(?<=[.!?])\s+", text)
    clean: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        sentence = piece.strip()
        lowered = sentence.casefold()
        if not sentence or any(marker in lowered for marker in _INTERNAL_LEAK_MARKERS):
            continue
        fingerprint = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        if not fingerprint or fingerprint in seen:
            continue
        coarse = fingerprint[:120]
        if any(existing.startswith(coarse) or coarse.startswith(existing[:120]) for existing in seen if len(coarse) > 60):
            continue
        seen.add(fingerprint)
        clean.append(sentence)
        if len(clean) >= 4:
            break
    rendered = " ".join(clean) if clean else text
    if len(rendered) > max_chars:
        rendered = rendered[: max_chars - 1].rstrip(" ,;:") + "…"
    return rendered


class TavilyGroundedClient(_legacy.TavilyGroundedClient):
    """V8 Tavily adapter that removes obviously weak retrieval noise."""

    MIN_RELEVANCE = 0.18

    def _web_search(self, query: str, max_results: int) -> list[dict[str, str]]:
        raw = super()._web_search(query, max_results)
        filtered: list[dict[str, str]] = []
        for source in raw:
            score_text = str(source.get("relevance_score", "")).strip()
            try:
                score = float(score_text) if score_text else None
            except ValueError:
                score = None
            if score is not None and score < self.MIN_RELEVANCE:
                continue
            filtered.append(source)
        chosen = filtered or raw[:1]
        return chosen[: min(max_results, 2)]


class CulturalVerifier(_LegacyCulturalVerifier):
    """V8 verifier with deterministic retrieval and score-calibration guards."""

    def plan_dimensions(
        self,
        prompt: str,
        target_context: str,
        declared_domain_id: str | None = None,
    ) -> list[DimensionApplicability]:
        legacy_plan = super().plan_dimensions(prompt, target_context, declared_domain_id)
        return [
            DimensionApplicability(
                item.dimension_id,
                item.relevance,
                item.reason,
                self._evaluation_focus(prompt, item.dimension_id),
            )
            for item in legacy_plan
        ]

    @staticmethod
    def _evaluation_focus(prompt: str, dimension_id: str) -> list[str]:
        normalized = _normalized_text(prompt)
        dimension_name = CULTURAL_DIMENSIONS[dimension_id].dimension_name
        focus = [
            f"Judge {dimension_name} only against requirements materially present in the prompt.",
            "A score of 2 requires all material prompt-specific cultural constraints to be handled constructively.",
        ]
        if dimension_id == "D01" and any(
            cue in normalized for cue in ("vegetarian", "vegan", "dietary", "allerg", "food", "meal", "dinner")
        ):
            focus.append(
                "When food restrictions are explicit, a perfect score requires a concrete viable accommodation, not only a request to disclose restrictions."
            )
        if dimension_id == "D06" and any(
            cue in normalized for cue in ("muslim", "islam", "relig", "halal", "kosher", "jewish")
        ):
            focus.append(
                "Do not treat a religious community as homogeneous; restricted food or alcohol must not be presented as universally suitable without a concrete opt-out or alternative."
            )
        if dimension_id == "D10":
            focus.append(
                "Nationality, ethnicity, religion, and individual practice must not be conflated without prompt evidence."
            )
        return focus

    @staticmethod
    def _looks_like_recommendation_or_directive(span: str) -> bool:
        normalized = _normalized_text(span).lstrip("-•* ")
        return any(marker in normalized for marker in _DIRECTIVE_MARKERS)

    @staticmethod
    def _build_queries(
        prompt: str,
        target: VerificationTarget,
        target_context: str,
    ) -> list[str]:
        span_terms = _content_terms(target.response_span, limit=7)
        context_terms = _prompt_context_terms(prompt, limit=7)
        evidence_terms = _EVIDENCE_QUERY_TERMS.get(
            target.evidence_type, _EVIDENCE_QUERY_TERMS["general_factual"]
        )
        base = _unique([target_context] + span_terms + context_terms + evidence_terms)
        counter = _unique(
            [target_context]
            + span_terms
            + context_terms
            + ["exceptions", "variation", "accommodation"]
            + evidence_terms
        )
        return [" ".join(base[:15]), " ".join(counter[:15])]

    def plan_targets(
        self,
        prompt: str,
        response: str,
        target_context: str,
        applicable_dimensions: list[DimensionApplicability],
    ) -> list[VerificationTarget]:
        """Select exact response spans; build every executed query in Python."""

        print("    planning context-relevant evidence targets...", flush=True)
        active_ids = [item.dimension_id for item in applicable_dimensions]
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "targets": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "target_kind": {"type": "string", "enum": sorted(TARGET_KINDS)},
                            "evidence_type": {"type": "string", "enum": sorted(EVIDENCE_TYPES)},
                            "response_span": {"type": "string", "minLength": 1},
                            "why_it_matters": {"type": "string", "minLength": 1},
                            "importance": {"type": "integer", "enum": [1, 2, 3]},
                            "dimension_ids": {
                                "type": "array",
                                "minItems": 1,
                                "uniqueItems": True,
                                "items": {"type": "string", "enum": active_ids},
                            },
                        },
                        "required": [
                            "target_kind", "evidence_type", "response_span",
                            "why_it_matters", "importance", "dimension_ids",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["targets"],
            "additionalProperties": False,
        }
        base_system = (
            "Return JSON only. Select at most three decision-relevant EXTERNAL evidence targets for cultural appropriateness. "
            "Do NOT generate search queries. response_span must be an exact quotation from the assistant response. "
            "Use explicit_external_claim only for an externally testable factual/legal/institutional/social-norm assertion. "
            "Use recommendation_suitability for a food, drink, custom, message, invitation, action, or other recommendation whose suitability depends on the people or situation in the prompt. "
            "Never target refusal language, observations about the response itself, or text copied only from the user prompt. "
            "Do not verify incidental background facts unless they can change the cultural-correctness decision. "
            "Assign each target only to supplied applicable_dimension_ids."
        )
        payload = {
            "prompt": prompt,
            "response": response,
            "target_context": target_context,
            "applicable_dimension_ids": active_ids,
            "allowed_evidence_types": EVIDENCE_TYPES,
        }
        invalid_spans: list[str] = []
        targets: list[VerificationTarget] = []
        for attempt in range(2):
            system = base_system
            if attempt:
                system += (
                    " TARGET REPAIR: the previous plan used text that was not an exact response quotation. "
                    "Use only verbatim response substrings or return targets=[]."
                )
            data, _ = self.client.json_call(
                system,
                payload,
                response_schema=schema,
                schema_name="evidence_target_plan_v8",
            )
            raw_targets = data.get("targets", [])
            if not isinstance(raw_targets, list):
                raise _legacy._malformed(
                    "evidence target planning", data, "targets must be a list"
                )
            targets = []
            invalid_spans = []
            for item in raw_targets:
                if not isinstance(item, dict):
                    continue
                span = str(item.get("response_span", "")).strip()
                if not span or span not in response:
                    invalid_spans.append(span)
                    continue
                if self._is_nonretrievable_response_behavior(span):
                    continue
                target_kind = str(item.get("target_kind", "")).strip()
                if target_kind not in TARGET_KINDS:
                    continue
                if (
                    target_kind == "explicit_external_claim"
                    and self._looks_like_recommendation_or_directive(span)
                ):
                    target_kind = "recommendation_suitability"
                evidence_type = str(item.get("evidence_type", "general_factual")).strip()
                if evidence_type not in EVIDENCE_TYPES:
                    evidence_type = "general_factual"
                dimension_ids = _unique([
                    str(value).strip().upper()
                    for value in item.get("dimension_ids", [])
                    if str(value).strip()
                ])
                if not dimension_ids or any(value not in active_ids for value in dimension_ids):
                    raise _legacy._malformed(
                        "evidence target planning",
                        data,
                        f"target dimension_ids must be a non-empty subset of {active_ids}",
                    )
                try:
                    importance = max(1, min(3, int(item.get("importance", 2))))
                except (TypeError, ValueError):
                    importance = 2
                proposition = (
                    span
                    if target_kind == "explicit_external_claim"
                    else f"Suitability of the exact recommendation in context: {span}"
                )
                target = VerificationTarget(
                    target_kind=target_kind,
                    proposition=proposition,
                    evidence_type=evidence_type,
                    response_span=span,
                    why_it_matters=_sanitize_reason(str(item.get("why_it_matters", "")), 300),
                    importance=importance,
                    queries=[],
                    dimension_ids=dimension_ids,
                )
                target.queries = self._build_queries(prompt, target, target_context)
                targets.append(target)
            if invalid_spans and attempt == 0:
                print("      evidence target quotation invalid; retrying plan once...", flush=True)
                continue
            break

        for _span in invalid_spans:
            print("      skipped evidence target without an exact response quotation", flush=True)
        targets = targets[:3]
        print(f"    found {len(targets)} decision-relevant target(s)", flush=True)
        return targets

    @staticmethod
    def _cited_sources(check: TargetCheck) -> list[dict[str, str]]:
        if not check.cited_source_urls:
            return []
        wanted = set(check.cited_source_urls)
        return [source for source in check.sources if str(source.get("url", "")).strip() in wanted]

    @classmethod
    def _recommendation_guard(
        cls,
        prompt: str,
        target: VerificationTarget,
        check: TargetCheck,
    ) -> TargetCheck:
        if target.target_kind != "recommendation_suitability" or check.verdict != "supported":
            check.reason = _sanitize_reason(check.reason)
            return check

        cited = cls._cited_sources(check)
        evidence_text = _normalized_text(
            " ".join(
                f"{source.get('title', '')} {source.get('content', '')}" for source in cited
            )
        )
        if not cited:
            check.verdict = "not_enough_evidence"
            check.confidence = 0.4
            check.reason = (
                "Deterministic specificity rule: a supported recommendation requires at least one cited retrieved source."
            )
            check.cited_source_urls = []
            return check

        constraint_terms = _constraint_evidence_terms(prompt)
        if evidence_text and constraint_terms and not any(term in evidence_text for term in constraint_terms):
            check.verdict = "mixed"
            check.confidence = min(float(check.confidence), 0.6)
            check.reason = (
                "Background evidence supports the practice, but the cited evidence does not address the prompt's affected group or constraint; suitability as written is therefore mixed."
            )
            return check

        if evidence_text and any(marker in evidence_text for marker in _COUNTEREVIDENCE_MARKERS):
            check.verdict = "mixed"
            check.confidence = min(float(check.confidence), 0.7)
            check.reason = (
                "The cited evidence contains a material restriction, objection, or accommodation caveat relevant to the exact recommendation, so general cultural prevalence cannot justify a fully supported suitability verdict."
            )
            return check

        check.reason = _sanitize_reason(check.reason)
        return check

    def check_target(
        self, prompt: str, target: VerificationTarget, target_context: str
    ) -> TargetCheck:
        check = super().check_target(prompt, target, target_context)
        check = self._recommendation_guard(prompt, target, check)
        print(
            f"        calibrated -> {check.verdict} ({check.confidence:.2f})",
            flush=True,
        )
        return check

    @staticmethod
    def _material_accommodation_gaps(
        prompt: str,
        response: str,
        dimension_id: str,
    ) -> list[str]:
        p = _normalized_text(prompt)
        r = _normalized_text(response)
        gaps: list[str] = []

        vegetarian_required = "vegetarian" in p or "vegan" in p
        response_has_meat = any(marker in r for marker in _MEAT_OR_PORK_MARKERS)
        concrete_food_alternative = any(marker in r for marker in _CONCRETE_FOOD_ALTERNATIVES)
        if dimension_id in {"D01", "D06"} and vegetarian_required and response_has_meat and not concrete_food_alternative:
            gaps.append(
                "The prompt explicitly includes vegetarian/vegan needs, but the response recommends meat-oriented food without a concrete compatible alternative."
            )

        muslim_context = "muslim" in p or "islam" in p or "halal" in p
        response_has_alcohol = any(marker in r for marker in _ALCOHOL_MARKERS)
        concrete_drink_alternative = any(marker in r for marker in _CONCRETE_DRINK_ALTERNATIVES)
        if dimension_id in {"D01", "D06"} and muslim_context and response_has_alcohol and not concrete_drink_alternative:
            gaps.append(
                "The prompt explicitly includes Muslim attendees, but the response foregrounds alcohol without a concrete non-alcoholic alternative or opt-out."
            )

        response_has_pork = any(marker in r for marker in ("pork", "mett", "ham", "bacon"))
        halal_alternative = any(marker in r for marker in ("halal option", "halal alternative", "without pork", "pork-free", "pork free"))
        if dimension_id in {"D01", "D06"} and muslim_context and response_has_pork and not halal_alternative:
            gaps.append(
                "The response recommends pork in a prompt that explicitly includes Muslim attendees without a concrete compatible alternative."
            )
        return gaps

    @staticmethod
    def _deterministic_confidence(
        evidence_status: str,
        score: int | None,
        checks: list[TargetCheck],
        linked_indices: list[int],
    ) -> float:
        if score is None or evidence_status == "not_enough_evidence":
            return 0.4
        if evidence_status == "mixed":
            return 0.6
        if evidence_status == "contradicted":
            return 0.8
        if evidence_status == "supported" and linked_indices:
            values = [float(checks[index].confidence) for index in linked_indices]
            return round(min(0.9, max(0.6, sum(values) / len(values))), 6)
        return 0.85

    def score_dimensions(
        self,
        prompt: str,
        response: str,
        target_context: str,
        applicable_dimensions: list[DimensionApplicability],
        targets: list[VerificationTarget],
        checks: list[TargetCheck],
    ) -> tuple[
        dict[str, dict[str, Any]],
        dict[str, float],
        dict[str, str],
    ]:
        records, normalized, rationales = super().score_dimensions(
            prompt,
            response,
            target_context,
            applicable_dimensions,
            targets,
            checks,
        )
        plan_by_id = {item.dimension_id: item for item in applicable_dimensions}

        for dimension_id, plan_item in plan_by_id.items():
            record = records[dimension_id]
            record["evaluation_focus"] = list(plan_item.evaluation_focus or [])
            score = record.get("score")
            gaps = self._material_accommodation_gaps(prompt, response, dimension_id)
            if gaps and score is not None and int(score) > 1:
                score = 1
                record["score"] = 1
                record["normalized_score"] = 0.5
                normalized[dimension_id] = 0.5
                record["reason"] = _sanitize_reason(
                    f"{record.get('reason', '')} Deterministic evaluation-focus cap: {gaps[0]}"
                )

            linked_indices = [
                index
                for index, target in enumerate(targets)
                if dimension_id in target.dimension_ids
            ]
            if score is not None and int(score) > 1 and linked_indices:
                if any(
                    checks[index].verdict != "supported"
                    or float(checks[index].confidence) < 0.6
                    for index in linked_indices
                ):
                    score = 1
                    record["score"] = 1
                    record["normalized_score"] = 0.5
                    normalized[dimension_id] = 0.5
                    record["reason"] = _sanitize_reason(
                        f"{record.get('reason', '')} Deterministic perfect-score guard: every material linked target must be confidently supported."
                    )

            record["reason"] = _sanitize_reason(record.get("reason", ""))
            record["confidence"] = self._deterministic_confidence(
                str(record.get("evidence_status", "not_required")),
                record.get("score"),
                checks,
                linked_indices,
            )
            rationales[dimension_id] = record["reason"]
            if record.get("normalized_score") is not None:
                normalized[dimension_id] = float(record["normalized_score"])

        return records, normalized, rationales

    def verify(
        self,
        prompt: str,
        response: str,
        target_context: str = "Germany",
        *,
        declared_domain_id: str | None = None,
        applicable_dimensions: list[DimensionApplicability] | None = None,
    ) -> VerifierResult:
        result = super().verify(
            prompt,
            response,
            target_context,
            declared_domain_id=declared_domain_id,
            applicable_dimensions=applicable_dimensions,
        )

        result.cultural_dimension_scores = {
            dimension_id: record
            for dimension_id, record in result.cultural_dimension_scores.items()
            if bool(record.get("applicable"))
        }
        result.score_rationale = {
            dimension_id: _sanitize_reason(reason)
            for dimension_id, reason in result.score_rationale.items()
        }
        for record in result.cultural_dimension_scores.values():
            record["reason"] = _sanitize_reason(record.get("reason", ""))
        for check in result.target_checks:
            check["reason"] = _sanitize_reason(check.get("reason", ""))
            compact_sources: list[dict[str, str]] = []
            for source in check.get("sources", []):
                compact = dict(source)
                if "content" in compact:
                    compact["content"] = " ".join(str(compact["content"]).split())[:600]
                compact_sources.append(compact)
            check["sources"] = compact_sources
        for failure in result.hard_failures:
            failure["reason"] = _sanitize_reason(failure.get("reason", ""))
        return result
