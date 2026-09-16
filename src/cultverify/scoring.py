from fractions import Fraction
from .schemas import DimensionScore, RankingResult, ScoreBatch, TargetVerdict
from .validation import validate_scores, validate_verdict


def compare_target(session, target, memo):
    return session.call(
        "target_comparator_v1",
        {"target": target.model_dump(mode="json"), "memo": memo.model_dump(mode="json")},
        TargetVerdict,
        lambda v: validate_verdict(v, target, memo),
    )


def score_dimensions(session, prompt, response, context, plan, targets, verdicts, memos, rubric):
    result = session.call(
        "dimension_scorer_v1",
        {
            "prompt": prompt,
            "response": response,
            "context": context.model_dump(mode="json"),
            "dimension_plan": plan.model_dump(mode="json"),
            "targets": [t.model_dump(mode="json") for t in targets],
            "verdicts": [v.model_dump(mode="json") for v in verdicts],
            "memos": [m.model_dump(mode="json") for m in memos],
            "rubric": rubric,
        },
        ScoreBatch,
        lambda b: validate_scores(b, response, plan, targets, memos),
    )
    return result.scores


def abstain_scores(plan, reason):
    return tuple(
        DimensionScore(
            dimension_id=d.dimension_id,
            score="abstain",
            rationale=reason,
            response_quotes=(),
            target_ids=(),
            memo_ids=(),
        )
        for d in plan.dimensions
    )


def exact_score(scores):
    values = [s.score for s in scores if s.score != "abstain"]
    return Fraction(sum(values), 2 * len(values)) if values else None


def aggregate(scores):
    score = exact_score(scores)
    return float(score) if score is not None else None


def rank_results(candidates):
    scores = [exact_score(c.dimension_scores) for c in candidates]
    comparable = (
        len({tuple(sorted(s.dimension_id for s in c.dimension_scores if s.score != "abstain")) for c in candidates})
        <= 1
    )
    available = [s for s in scores if s is not None]
    tied = tuple(i for i, s in enumerate(scores) if s is not None and s == max(available)) if available else ()
    # Implements the frozen highest-score rule, with an explicit coverage diagnostic.
    return RankingResult(
        candidates=tuple(candidates),
        winner=tied[0] if len(tied) == 1 else "no_clear_winner",
        tied_indices=tied,
        coverage_comparable=comparable,
    )
