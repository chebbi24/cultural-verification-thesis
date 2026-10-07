import re

from .schemas import (
    EpistemicType,
    InitialQuestions,
    MaterialTarget,
    TargetBatch,
    TargetDraft,
    TargetSelectionBatch,
    VerificationQuestion,
)
from .trace import stable_id
from .validation import validate_target_selections, validate_targets


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=\S)")


def response_spans(response):
    """Return deterministic exact substrings for model selection.

    The model chooses span IDs; Python owns the source text. This preserves the
    existing exact-quote audit invariant without asking a generative model to
    reproduce arbitrary response text byte-for-byte.
    """
    spans = []
    for line in response.splitlines():
        line = line.strip()
        if not line:
            continue
        pieces = tuple(piece.strip() for piece in _SENTENCE_BOUNDARY.split(line) if piece.strip())
        for piece in pieces or (line,):
            spans.append({"span_id": f"S{len(spans) + 1:03d}", "text": piece})
    if response and not spans:
        spans.append({"span_id": "S001", "text": response})
    return tuple(spans)


def _canonical_span_id(raw_span_id, allowed_span_ids):
    raw = raw_span_id.strip().upper()
    if raw in allowed_span_ids:
        return raw
    match = re.fullmatch(r"S?0*(\d+)", raw)
    if not match:
        return None
    candidate = f"S{int(match.group(1)):03d}"
    return candidate if candidate in allowed_span_ids else None


def extract_targets(session, prompt, response, context, plan):
    spans = response_spans(response)
    batch = session.call(
        "target_extractor_v1",
        {
            "prompt": prompt,
            "response_spans": spans,
            "context": context.model_dump(mode="json"),
            "dimension_plan": {
                "dimensions": [
                    {"dimension_id": dimension.dimension_id, "role": dimension.role} for dimension in plan.dimensions
                ]
            },
            "max_material_targets": session.config.max_material_targets,
        },
        TargetSelectionBatch,
        lambda batch: validate_target_selections(
            batch,
            spans,
            plan,
            session.config.max_material_targets,
        ),
    )
    span_text = {span["span_id"]: span["text"] for span in spans}
    allowed_span_ids = set(span_text)
    allowed_dimensions = {dimension.dimension_id for dimension in plan.dimensions}
    drafts = []
    for target in batch.targets:
        span_id = _canonical_span_id(target.span_id, allowed_span_ids)
        if span_id is None:
            continue
        dimension_ids = tuple(
            dict.fromkeys(dimension_id for dimension_id in target.dimension_ids if dimension_id in allowed_dimensions)
        )
        if not dimension_ids:
            continue
        retrieval_appropriate = target.epistemic_type in {
            EpistemicType.EXTERNAL,
            EpistemicType.NORM,
            EpistemicType.RECOMMENDATION,
        }
        response_quote = span_text[span_id]
        drafts.append(
            TargetDraft(
                response_quote=response_quote,
                proposition=response_quote,
                epistemic_type=target.epistemic_type,
                dimension_ids=dimension_ids,
                materiality="Selected as decision-relevant to the planned cultural assessment.",
                retrieval_appropriate=retrieval_appropriate,
            )
        )
    grounded = TargetBatch(targets=tuple(drafts), truncated=batch.truncated)
    validate_targets(grounded, response, plan, session.config.max_material_targets)
    targets = tuple(
        MaterialTarget(**target.model_dump(), target_id=stable_id("target", [i, target.model_dump(mode="json")]))
        for i, target in enumerate(grounded.targets)
    )
    return targets, grounded.truncated


def neutral_questions(session, target, context):
    pair = session.call(
        "verification_question_v1",
        {
            "target": {
                "response_quote": target.response_quote,
                "epistemic_type": target.epistemic_type,
                "dimension_ids": target.dimension_ids,
            },
            "context": context.model_dump(mode="json"),
        },
        InitialQuestions,
    )
    # No target ID, response, verdict, candidate position, or enclosing result is exported.
    return tuple(
        VerificationQuestion(**q.model_dump(), question_id=stable_id("question", q.model_dump(mode="json")))
        for q in pair.questions
    )
