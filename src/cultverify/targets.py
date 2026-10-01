import re

from .schemas import (
    InitialQuestions,
    MaterialTarget,
    TargetBatch,
    TargetDraft,
    TargetSelectionBatch,
    VerificationQuestion,
)
from .trace import stable_id
from .validation import validate_target_selections, validate_targets


_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\\s+(?=[A-Z0-9"\'“‘(\\[])')


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
        lambda b: validate_target_selections(b, spans, plan, session.config.max_material_targets),
    )
    span_text = {span["span_id"]: span["text"] for span in spans}
    drafts = tuple(
        TargetDraft(
            response_quote=span_text[target.span_id],
            proposition=target.proposition,
            epistemic_type=target.epistemic_type,
            dimension_ids=target.dimension_ids,
            materiality=target.materiality,
            retrieval_appropriate=target.retrieval_appropriate,
        )
        for target in batch.targets
    )
    grounded = TargetBatch(targets=drafts, truncated=batch.truncated)
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
