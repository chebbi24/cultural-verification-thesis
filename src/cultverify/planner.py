import csv
from importlib.resources import files
from .llm import StageError
from .schemas import ContextFrame, DimensionPlan
from .validation import validate_context


def load_rubric():
    with files("cultverify").joinpath("resources/rubric.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if [r["dimension_id"] for r in rows] != [f"D{i:02}" for i in range(1, 11)]:
        raise ValueError("Rubric must contain exactly D01-D10")
    if any(not value.strip() for row in rows for value in row.values()):
        raise ValueError("Empty rubric field")
    return rows


def plan_prompt(session, prompt, rubric):
    try:
        context = session.call(
            "context_planner_v1", {"prompt": prompt}, ContextFrame, lambda c: validate_context(c, prompt)
        )
    except StageError:
        # Explicit conservative fallback: do not carry unsupported facts forward.
        context = ContextFrame()
    plan = session.call(
        "dimension_planner_v1",
        {"prompt": prompt, "context": context.model_dump(mode="json"), "rubric": rubric},
        DimensionPlan,
    )
    return context, plan
