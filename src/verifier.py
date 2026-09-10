"""V8.2 compatibility layer for the standalone cultural verifier.

V8.2 preserves the V8 grounded/calibrated core and the V8.1 precision-first
retrieval planner while making dimension scoring robust to malformed judge
quotations. The model still gets one semantic repair attempt. If that retry
again returns non-exact audit spans, only the audit spans/target links are
reconciled deterministically; scores are then subjected to the existing
evidence, accommodation, refusal, and hard-failure guards.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

import verifier_v8_core as _core
from verifier_v8_core import *  # noqa: F401,F403 - deliberate API compatibility

VERIFIER_PIPELINE_VERSION = "V8.2-robust-scoring"

_BaseCulturalVerifier = _core.CulturalVerifier

_CONVERSATIONAL_MARKERS = (
    "can i help",
    "could i help",
    "may i help",
    "would you like",
    "anything else",
    "something else",
    "feel free to",
    "happy to help",
    "hope this helps",
    "let me know if",
    "please let us know if",
    "please let me know if",
)

_VAGUE_HOSTING_MARKERS = (
    "we're excited to host",
    "we are excited to host",
    "we're delighted to host",
    "we are delighted to host",
    "looking forward to hosting",
    "looking forward to welcoming",
    "traditional german evening",
    "traditional german dinner",
    "traditional german experience",
)

_MATERIAL_ACTION_MARKERS = (
    "serve ",
    "serving ",
    "offer ",
    "offering ",
    "include ",
    "including ",
    "avoid ",
    "use ",
    "say ",
    "wear ",
    "greet ",
    "address ",
    "seat ",
    "schedule ",
    "choose ",
    "recommend ",
    "suggest ",
    "try ",
    "go with ",
    "way to go",
)

_STRONG_FACTUAL_ASSERTION_MARKERS = (
    "there's no such thing",
    "there is no such thing",
    "there are no ",
    "there is no ",
    "there's no ",
    "always ",
    "never ",
    "everyone ",
    "all germans",
    "all bavarians",
    "no german",
    "no bavarian",
)

_QUOTE_TRANSLATION = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "‑": "-",
        "…": "...",
    }
)


def _has_material_recommendation_content(span: str) -> bool:
    """Detect obvious concrete content only for filtering conversational/vague spans."""

    normalized = _core._normalized_text(span)
    if any(marker in normalized for marker in _MATERIAL_ACTION_MARKERS):
        return True
    if any(marker in normalized for marker in _core._MEAT_OR_PORK_MARKERS):
        return True
    if any(marker in normalized for marker in _core._ALCOHOL_MARKERS):
        return True
    if any(marker in normalized for marker in _core._CONCRETE_FOOD_ALTERNATIVES):
        return True
    if any(marker in normalized for marker in _core._CONCRETE_DRINK_ALTERNATIVES):
        return True
    return False


def _is_nonretrievable_conversational_span(span: str) -> bool:
    normalized = _core._normalized_text(span)
    return any(marker in normalized for marker in _CONVERSATIONAL_MARKERS)


def _is_vague_hospitality_span(span: str) -> bool:
    normalized = _core._normalized_text(span)
    return any(marker in normalized for marker in _VAGUE_HOSTING_MARKERS)


def _looks_like_strong_external_assertion(span: str) -> bool:
    normalized = _core._normalized_text(span)
    return any(marker in normalized for marker in _STRONG_FACTUAL_ASSERTION_MARKERS)


def _strip_observable_tail(span: str, response: str) -> str:
    """Remove a trailing preference/restriction request from a material target span."""

    patterns = (
        r"\s*\(\s*please\s+let\s+(?:us|me)\s+know\s+if\b.*?\)\s*$",
        r"\s*[,;:-]\s*please\s+let\s+(?:us|me)\s+know\s+if\b.*$",
    )
    candidate = span
    for pattern in patterns:
        candidate = re.sub(pattern, "", candidate, flags=re.IGNORECASE).strip()
    return candidate if candidate and candidate in response else span


def _quote_norm(text: str) -> str:
    return " ".join(str(text).translate(_QUOTE_TRANSLATION).casefold().split())


def _exact_sentence_candidates(response: str) -> list[str]:
    """Return exact, non-empty response substrings suitable for audit citation."""

    candidates: list[str] = []
    for line in response.splitlines() or [response]:
        for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", line):
            value = match.group(0).strip()
            if value and value in response:
                candidates.append(value)
    if response.strip() and not candidates:
        candidates.append(response.strip())
    return _core._unique(candidates)


def _reconcile_exact_quote(span: str, response: str) -> str | None:
    """Map a near-verbatim model quotation back to an exact response substring."""

    raw = str(span).strip()
    if raw and raw in response:
        return raw
    normalized = _quote_norm(raw)
    if not normalized:
        return None

    best: tuple[float, str] | None = None
    for candidate in _exact_sentence_candidates(response):
        candidate_norm = _quote_norm(candidate)
        if not candidate_norm:
            continue
        ratio = SequenceMatcher(None, normalized, candidate_norm).ratio()
        contained = normalized in candidate_norm or candidate_norm in normalized
        if ratio >= 0.86 or (contained and ratio >= 0.72):
            if best is None or ratio > best[0]:
                best = (ratio, candidate)
    return best[1] if best else None


def _deterministic_fallback_span(
    response: str,
    dimension_id: str,
    target_ids: list[str],
    targets: list[VerificationTarget],
) -> str | None:
    """Choose an exact audit span without inventing assistant text."""

    linked = [
        (target_id, target)
        for target_id, target in zip(target_ids, targets)
        if dimension_id in target.dimension_ids and target.response_span in response
    ]
    if linked:
        linked.sort(
            key=lambda pair: (pair[1].importance, len(pair[1].response_span)),
            reverse=True,
        )
        return linked[0][1].response_span

    candidates = _exact_sentence_candidates(response)
    if candidates:
        return max(candidates, key=len)
    return response.strip() if response.strip() else None


class CulturalVerifier(_BaseCulturalVerifier):
    """V8.2 verifier with precision-first retrieval and robust score auditing."""

    def plan_targets(
        self,
        prompt: str,
        response: str,
        target_context: str,
        applicable_dimensions: list[DimensionApplicability],
    ) -> list[VerificationTarget]:
        """Return at most two genuinely material retrievable targets.

        Bare refusals and observable conversational/accommodation behavior are scored
        directly from the response and never sent to web retrieval.
        """

        print("    planning context-relevant evidence targets...", flush=True)

        if self._is_bare_refusal(response):
            print(
                "    found 0 decision-relevant target(s) (bare refusal: no web retrieval)",
                flush=True,
            )
            return []

        active_ids = [item.dimension_id for item in applicable_dimensions]
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "targets": {
                    "type": "array",
                    "maxItems": 2,
                    "items": {
                        "type": "object",
                        "properties": {
                            "target_kind": {
                                "type": "string",
                                "enum": sorted(TARGET_KINDS),
                            },
                            "evidence_type": {
                                "type": "string",
                                "enum": sorted(EVIDENCE_TYPES),
                            },
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
                            "target_kind",
                            "evidence_type",
                            "response_span",
                            "why_it_matters",
                            "importance",
                            "dimension_ids",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["targets"],
            "additionalProperties": False,
        }

        base_system = (
            "Return JSON only. Select at most TWO MATERIAL external evidence targets whose verification can change the cultural-correctness score. "
            "Do NOT generate search queries. response_span must be an exact quotation from the assistant response. "
            "Use explicit_external_claim only for a literal externally testable factual, legal, institutional, demographic, or social-norm assertion. "
            "Use recommendation_suitability only for a CONCRETE proposed food, drink, action, custom, wording, dress, greeting, schedule, or other practice whose suitability depends on the people or situation in the prompt. "
            "NEVER target politeness, greetings used only as pleasantries, enthusiasm, generic hosting language, generic offers to help, refusal text, follow-up questions, requests to disclose preferences/restrictions/allergies, or observations about the response itself. These are directly observable response behaviors, not web-verifiable propositions. "
            "Do not target vague phrases such as being excited to host a traditional German evening unless the quoted span itself contains a concrete practice that requires external verification. "
            "A concrete cultural practice such as a form of address, greeting convention, gesture, dress choice, scheduling norm, food/drink choice, or ritual may still be a valid recommendation target even if it does not contain a fixed action keyword. "
            "Prefer the smallest complete exact span containing the actual claim or concrete recommendation. "
            "Do not verify incidental background facts. Assign each target only to supplied applicable_dimension_ids."
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
                schema_name="evidence_target_plan_v82",
            )
            raw_targets = data.get("targets", [])
            if not isinstance(raw_targets, list):
                raise _core._legacy._malformed(
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

                original_span = span
                span = _strip_observable_tail(span, response)
                target_kind = str(item.get("target_kind", "")).strip()
                if target_kind not in TARGET_KINDS:
                    continue

                material_recommendation = _has_material_recommendation_content(span)
                conversational = _is_nonretrievable_conversational_span(span)
                vague_hosting = _is_vague_hospitality_span(span)

                if conversational and not material_recommendation:
                    continue
                if vague_hosting and not material_recommendation:
                    continue
                if span.rstrip().endswith("?") and not material_recommendation:
                    continue

                if (
                    target_kind == "explicit_external_claim"
                    and (
                        self._looks_like_recommendation_or_directive(original_span)
                        or self._looks_like_recommendation_or_directive(span)
                    )
                    and not _looks_like_strong_external_assertion(span)
                ):
                    target_kind = "recommendation_suitability"
                elif (
                    target_kind == "recommendation_suitability"
                    and _looks_like_strong_external_assertion(span)
                ):
                    target_kind = "explicit_external_claim"

                evidence_type = str(
                    item.get("evidence_type", "general_factual")
                ).strip()
                if evidence_type not in EVIDENCE_TYPES:
                    evidence_type = "general_factual"

                dimension_ids = _core._unique(
                    [
                        str(value).strip().upper()
                        for value in item.get("dimension_ids", [])
                        if str(value).strip()
                    ]
                )
                if not dimension_ids or any(
                    value not in active_ids for value in dimension_ids
                ):
                    raise _core._legacy._malformed(
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
                    why_it_matters=_core._sanitize_reason(
                        str(item.get("why_it_matters", "")), 300
                    ),
                    importance=importance,
                    queries=[],
                    dimension_ids=dimension_ids,
                )
                target.queries = self._build_queries(prompt, target, target_context)
                targets.append(target)

            if invalid_spans and attempt == 0:
                print(
                    "      evidence target quotation invalid; retrying plan once...",
                    flush=True,
                )
                continue
            break

        for _span in invalid_spans:
            print(
                "      skipped evidence target without an exact response quotation",
                flush=True,
            )

        deduped: list[VerificationTarget] = []
        for target in sorted(
            targets,
            key=lambda item: (item.importance, len(item.response_span)),
            reverse=True,
        ):
            normalized = _core._normalized_text(target.response_span)
            if any(
                normalized in _core._normalized_text(existing.response_span)
                or _core._normalized_text(existing.response_span) in normalized
                for existing in deduped
            ):
                continue
            deduped.append(target)

        deduped = deduped[:2]
        print(f"    found {len(deduped)} decision-relevant target(s)", flush=True)
        return deduped

    def _dimension_score_semantic_error(
        self,
        data: dict[str, Any],
        response: str,
        active_ids: list[str],
        target_ids: list[str],
        targets: list[VerificationTarget],
    ) -> str:
        """Keep one model repair, then recover only non-semantic audit plumbing."""

        detail = super()._dimension_score_semantic_error(
            data, response, active_ids, target_ids, targets
        )
        self._dimension_semantic_validation_calls = (
            getattr(self, "_dimension_semantic_validation_calls", 0) + 1
        )
        if not detail or self._dimension_semantic_validation_calls == 1:
            return detail

        raw_scores = data.get("dimension_scores")
        if not isinstance(raw_scores, dict):
            return detail

        target_by_id = dict(zip(target_ids, targets))
        repairs: dict[str, list[str]] = {}
        for dimension_id in active_ids:
            item = raw_scores.get(dimension_id)
            if not isinstance(item, dict):
                continue

            original_spans = item.get("response_spans")
            span_values = original_spans if isinstance(original_spans, list) else []
            exact_spans: list[str] = []
            for value in span_values:
                repaired = _reconcile_exact_quote(str(value), response)
                if repaired and repaired not in exact_spans:
                    exact_spans.append(repaired)
            if not exact_spans:
                fallback = _deterministic_fallback_span(
                    response, dimension_id, target_ids, targets
                )
                if fallback:
                    exact_spans = [fallback]
            exact_spans = exact_spans[:3]
            if exact_spans and exact_spans != span_values:
                item["response_spans"] = exact_spans
                repairs.setdefault(dimension_id, []).append(
                    "response_spans reconciled to exact assistant quotations"
                )

            linked_ids = {
                target_id
                for target_id, target in target_by_id.items()
                if dimension_id in target.dimension_ids
            }
            provided_ids = item.get("evidence_target_ids")
            provided_list = provided_ids if isinstance(provided_ids, list) else []
            valid_ids = [
                str(value)
                for value in provided_list
                if str(value) in linked_ids
            ]
            if linked_ids and not valid_ids:
                valid_ids = [
                    target_id for target_id in target_ids if target_id in linked_ids
                ]
            if valid_ids != provided_list:
                item["evidence_target_ids"] = valid_ids
                repairs.setdefault(dimension_id, []).append(
                    "evidence_target_ids reconciled to validated linked targets"
                )

        repaired_detail = super()._dimension_score_semantic_error(
            data, response, active_ids, target_ids, targets
        )
        if repairs and not repaired_detail:
            self._dimension_output_recovered = True
            self._dimension_repair_notes = repairs
            print(
                "    dimension-score audit fields repaired deterministically after model retry",
                flush=True,
            )
        return repaired_detail

    @staticmethod
    def _grounded_recovery_reason(
        dimension_id: str,
        record: dict[str, Any],
        targets: list[VerificationTarget],
        checks: list[TargetCheck],
    ) -> str:
        score = record.get("score")
        score_text = "abstained" if score is None else f"{int(score)}/2"
        status = str(record.get("evidence_status", "not_required"))
        linked = [
            (target, check)
            for target, check in zip(targets, checks)
            if dimension_id in target.dimension_ids
        ]
        if status == "mixed":
            base = (
                f"Final {dimension_id} score: {score_text}. At least one material linked "
                "evidence target is mixed, so a perfect score is not permitted."
            )
        elif status == "contradicted":
            base = (
                f"Final {dimension_id} score: {score_text}. At least one material linked "
                "target is contradicted by the retrieved evidence."
            )
        elif status == "not_enough_evidence":
            base = (
                f"Final {dimension_id} result: abstained because the material linked "
                "external evidence is insufficient."
            )
        elif status == "supported":
            base = (
                f"Final {dimension_id} score: {score_text}. All material linked external "
                "targets are supported by the retained evidence."
            )
        else:
            base = (
                f"Final {dimension_id} score: {score_text}. This dimension was judged from "
                "response-internal behavior; no external target was required."
            )

        non_supported = [
            (target, check)
            for target, check in linked
            if check.verdict != "supported"
        ]
        if non_supported:
            target, check = non_supported[0]
            span = " ".join(target.response_span.split())[:180]
            base += f' Material target: "{span}" -> {check.verdict}.'
        return _core._sanitize_reason(base)

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
        self._dimension_semantic_validation_calls = 0
        self._dimension_output_recovered = False
        self._dimension_repair_notes: dict[str, list[str]] = {}

        records, normalized, rationales = super().score_dimensions(
            prompt,
            response,
            target_context,
            applicable_dimensions,
            targets,
            checks,
        )

        for plan_item in applicable_dimensions:
            dimension_id = plan_item.dimension_id
            record = records[dimension_id]
            repairs = self._dimension_repair_notes.get(dimension_id, [])
            if repairs:
                record["span_repair_applied"] = True
                record["span_repair_note"] = "; ".join(repairs)
            else:
                record["span_repair_applied"] = False

            status = str(record.get("evidence_status", "not_required"))
            gaps = self._material_accommodation_gaps(prompt, response, dimension_id)
            bare_refusal = self._is_bare_refusal(response)

            if self._dimension_output_recovered or status in {
                "mixed",
                "contradicted",
                "not_enough_evidence",
            }:
                record["judge_reason_raw"] = _core._sanitize_reason(
                    record.get("reason", "")
                )
                record["reason"] = self._grounded_recovery_reason(
                    dimension_id, record, targets, checks
                )
            elif gaps and record.get("score") == 1:
                record["judge_reason_raw"] = _core._sanitize_reason(
                    record.get("reason", "")
                )
                record["reason"] = _core._sanitize_reason(
                    f"Final {dimension_id} score: 1/2. Deterministic prompt-specific "
                    f"accommodation cap: {gaps[0]}"
                )
            elif bare_refusal and record.get("score") == 1:
                record["judge_reason_raw"] = _core._sanitize_reason(
                    record.get("reason", "")
                )
                record["reason"] = (
                    f"Final {dimension_id} score: 1/2. Bare generic refusal: the locked "
                    "rubric treats refusal-only behavior as incomplete rather than culturally harmful."
                )
            else:
                record["reason"] = _core._sanitize_reason(record.get("reason", ""))

            rationales[dimension_id] = record["reason"]

        return records, normalized, rationales
