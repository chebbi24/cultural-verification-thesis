from fractions import Fraction
from .schemas import DimensionScore, RankingResult, ScoreBatch, ScoreDraftBatch, TargetVerdict
from .validation import validate_score_drafts, validate_scores, validate_verdict


def _memo_evidence_view(memo):
    return {
        "memo_id": memo.memo_id,
        "sufficiency": memo.sufficiency,
        "confidence": memo.confidence,
        "statements": [statement.model_dump(mode="json") for statement in memo.statements],
    }


def compare_target(session, target, memo):
    # Epistemic consistency: insufficient evidence cannot support a directional verdict.
    if memo.sufficiency == "insufficient":
        return TargetVerdict(
            target_id=target.target_id,
            memo_id=memo.memo_id,
            verdict="insufficient",
            reasoning="Frozen evidence memo is insufficient; no directional verdict is permitted.",
        )
    return session.call(
        "target_comparator_v1",
        {"target": target.model_dump(mode="json"), "memo": _memo_evidence_view(memo)},
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
            "memos": [_memo_evidence_view(m) for m in memos],
            "rubric": rubric,
        },
        ScoreDraftBatch,
        lambda b: validate_score_drafts(b, response, plan, targets, verdicts),
    )
    memo_by_target = {verdict.target_id: verdict.memo_id for verdict in verdicts}
    scores = tuple(
        DimensionScore(
            **score.model_dump(mode="json"),
            memo_ids=tuple(
                dict.fromkeys(
                    memo_by_target[target_id] for target_id in score.target_ids if target_id in memo_by_target
                )
            ),
        )
        for score in result.scores
    )
    final = ScoreBatch(scores=scores)
    validate_scores(final, response, plan, targets, verdicts, memos)
    return final.scores


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
    if any(candidate.status != "completed" for candidate in candidates):
        return RankingResult(
            candidates=tuple(candidates),
            winner="no_clear_winner",
            tied_indices=(),
            coverage_comparable=False,
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
