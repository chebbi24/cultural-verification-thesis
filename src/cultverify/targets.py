from .schemas import InitialQuestions, MaterialTarget, TargetBatch, VerificationQuestion
from .trace import stable_id
from .validation import validate_targets


def extract_targets(session, prompt, response, context, plan):
    batch = session.call(
        "target_extractor_v1",
        {
            "prompt": prompt,
            "response": response,
            "context": context.model_dump(mode="json"),
            "dimension_plan": {
                "dimensions": [
                    {"dimension_id": dimension.dimension_id, "role": dimension.role} for dimension in plan.dimensions
                ]
            },
            "max_material_targets": session.config.max_material_targets,
        },
        TargetBatch,
        lambda b: validate_targets(b, response, plan, session.config.max_material_targets),
    )
    targets = tuple(
        MaterialTarget(**t.model_dump(), target_id=stable_id("target", [i, t.model_dump(mode="json")]))
        for i, t in enumerate(batch.targets)
    )
    return targets, batch.truncated


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
