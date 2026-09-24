from fractions import Fraction
from .schemas import (
    DimensionScore,
    RankingResult,
    ScoreBatch,
    ScoreDraftBatch,
    TargetVerdict,
    TargetVerdictDraft,
)
from .validation import validate_score_drafts, validate_scores, validate_verdict


def _memo_evidence_view(memo):
    return {
        "memo_id": memo.memo_id,
        "sufficiency": memo.sufficiency,
        "evidence_groups": [
            {"supports": [support.model_dump(mode="json") for support in statement.supports]}
            for statement in memo.statements
        ],
    }


def _target_comparison_view(target):
    return {"target_id": target.target_id, "response_quote": target.response_quote}


def _target_scoring_view(target):
    return {
        "target_id": target.target_id,
        "response_quote": target.response_quote,
        "dimension_ids": target.dimension_ids,
        "epistemic_type": target.epistemic_type,
        "retrieval_appropriate": target.retrieval_appropriate,
    }


def _verdict_scoring_view(verdict):
    return {
        "target_id": verdict.target_id,
        "memo_id": verdict.memo_id,
        "verdict": verdict.verdict,
    }


def _plan_scoring_view(plan):
    return {"dimensions": [{"dimension_id": dimension.dimension_id} for dimension in plan.dimensions]}


def compare_target(session, target, memo):
    # Epistemic consistency: insufficient evidence cannot support a directional verdict.
    if memo.sufficiency == "insufficient":
        return TargetVerdict(
            target_id=target.target_id,
            memo_id=memo.memo_id,
            verdict="insufficient",
            reasoning="Frozen evidence memo is insufficient; no directional verdict is permitted.",
        )
    draft = session.call(
        "target_comparator_v1",
        {"target": _target_comparison_view(target), "memo": _memo_evidence_view(memo)},
        TargetVerdictDraft,
    )
    verdict = TargetVerdict(
        **draft.model_dump(mode="json"),
        target_id=target.target_id,
        memo_id=memo.memo_id,
    )
    validate_verdict(verdict, target, memo)
    return verdict


def _forced_abstain_dimensions(plan, targets, verdicts):
    verdicts_by_target = {verdict.target_id: verdict for verdict in verdicts}
    forced = set()
    for dimension in plan.dimensions:
        relevant_targets = [target for target in targets if dimension.dimension_id in target.dimension_ids]
        external_targets = [target for target in relevant_targets if target.retrieval_appropriate]
        direct_targets = [target for target in relevant_targets if not target.retrieval_appropriate]
        if (
            external_targets
            and not direct_targets
            and all(
                verdicts_by_target.get(target.target_id) is not None
                and verdicts_by_target[target.target_id].verdict == "insufficient"
                for target in external_targets
            )
        ):
            forced.add(dimension.dimension_id)
    return forced


def score_dimensions(session, prompt, response, context, plan, targets, verdicts, memos, rubric):
    forced_abstentions = _forced_abstain_dimensions(plan, targets, verdicts)
    active_dimensions = tuple(
        dimension for dimension in plan.dimensions if dimension.dimension_id not in forced_abstentions
    )
    active_ids = {dimension.dimension_id for dimension in active_dimensions}
    active_targets = tuple(target for target in targets if active_ids.intersection(target.dimension_ids))
    active_target_ids = {target.target_id for target in active_targets}
    active_verdicts = tuple(verdict for verdict in verdicts if verdict.target_id in active_target_ids)
    active_memo_ids = {verdict.memo_id for verdict in active_verdicts}
    active_memos = tuple(memo for memo in memos if memo.memo_id in active_memo_ids)

    if active_dimensions:
        result = session.call(
            "dimension_scorer_v1",
            {
                "prompt": prompt,
                "response": response,
                "context": context.model_dump(mode="json"),
                "dimension_plan": {
                    "dimensions": [{"dimension_id": dimension.dimension_id} for dimension in active_dimensions]
                },
                "targets": [_target_scoring_view(t) for t in active_targets],
                "verdicts": [_verdict_scoring_view(v) for v in active_verdicts],
                "memos": [_memo_evidence_view(m) for m in active_memos],
                "rubric": rubric,
            },
            ScoreDraftBatch,
            lambda b: validate_score_drafts(
                b,
                response,
                plan,
                targets,
                verdicts,
                ignored_dimensions=forced_abstentions,
            ),
        )
        drafts_by_dimension = {score.dimension_id: score for score in result.scores}
    else:
        drafts_by_dimension = {}

    verdicts_by_target = {verdict.target_id: verdict for verdict in verdicts}
    memo_by_target = {verdict.target_id: verdict.memo_id for verdict in verdicts}
    scores = []
    for dimension in plan.dimensions:
        dimension_id = dimension.dimension_id
        relevant_targets = [target for target in targets if dimension_id in target.dimension_ids]
        if dimension_id in forced_abstentions:
            linked_target_ids = tuple(target.target_id for target in relevant_targets if target.retrieval_appropriate)
            score = DimensionScore(
                dimension_id=dimension_id,
                score="abstain",
                rationale="All relevant retrievable targets are insufficient; dimension abstained deterministically.",
                response_quotes=(),
                target_ids=linked_target_ids,
                memo_ids=tuple(
                    dict.fromkeys(
                        memo_by_target[target_id] for target_id in linked_target_ids if target_id in memo_by_target
                    )
                ),
            )
        else:
            draft = drafts_by_dimension[dimension_id]
            direct_target_ids = {target.target_id for target in relevant_targets if not target.retrieval_appropriate}
            directional_target_ids = {
                target.target_id
                for target in relevant_targets
                if target.target_id in verdicts_by_target
                and verdicts_by_target[target.target_id].verdict in {"supported", "mixed", "contradicted"}
            }
            linked_target_ids = tuple(
                target.target_id
                for target in relevant_targets
                if target.target_id in direct_target_ids | directional_target_ids
            )
            score = DimensionScore(
                **draft.model_dump(mode="json"),
                target_ids=linked_target_ids,
                memo_ids=tuple(
                    dict.fromkeys(
                        memo_by_target[target_id]
                        for target_id in linked_target_ids
                        if target_id in memo_by_target
                    )
                ),
            )
        scores.append(score)

    final = ScoreBatch(scores=tuple(scores))
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
