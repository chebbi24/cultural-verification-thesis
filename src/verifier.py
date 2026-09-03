"""V8.1 target-filtering compatibility layer.

The full V8 grounded/calibrated implementation lives in ``verifier_v8_core.py``.
This layer keeps its public API unchanged while tightening evidence-target planning:
only material external claims or concrete recommendations are retrievable targets.
"""

from __future__ import annotations

from typing import Any

import verifier_v8_core as _core
from verifier_v8_core import *  # noqa: F401,F403 - deliberate API compatibility

VERIFIER_PIPELINE_VERSION = "V8.1-material-targets"

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


class CulturalVerifier(_BaseCulturalVerifier):
    """V8.1 verifier with precision-first evidence-target selection."""

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
                schema_name="evidence_target_plan_v81",
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

                target_kind = str(item.get("target_kind", "")).strip()
                if target_kind not in TARGET_KINDS:
                    continue

                material_recommendation = _has_material_recommendation_content(span)
                conversational = _is_nonretrievable_conversational_span(span)
                vague_hosting = _is_vague_hospitality_span(span)

                # Observable conversation/accommodation behavior is not an external
                # proposition. Preserve a span only when it also contains a concrete
                # proposal (for example a menu item followed by an accommodation note).
                if conversational and not material_recommendation:
                    continue
                if vague_hosting and not material_recommendation:
                    continue
                if span.rstrip().endswith("?") and not material_recommendation:
                    continue

                # If the model labels a directive as a factual claim, repair the kind
                # rather than discarding a potentially valid cultural practice.
                if (
                    target_kind == "explicit_external_claim"
                    and self._looks_like_recommendation_or_directive(span)
                ):
                    target_kind = "recommendation_suitability"

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

        # Remove near-duplicate/overlapping targets, preferring higher importance
        # and the more complete exact span.
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
