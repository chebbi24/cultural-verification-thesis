from fractions import Fraction

from .llm import StageError
from .schemas import (
    DimensionScore,
    DimensionScoreDecision,
    EpistemicType,
    RankingResult,
    ScoreBatch,
    ScoreDecisionBatch,
    SingleScoreDecision,
    TargetVerdict,
    TargetVerdictDraft,
)
from .validation import validate_score_decisions, validate_scores, validate_verdict


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


def _single_dimension_decision(session, stage, payload, dimension_id, relevant_targets, verdicts):
    decision = session.call(stage, payload, SingleScoreDecision)
    verdicts_by_target = {verdict.target_id: verdict for verdict in verdicts}
    directional = any(
        target.target_id in verdicts_by_target
        and verdicts_by_target[target.target_id].verdict in {"supported", "mixed", "contradicted"}
        for target in relevant_targets
    )
    if directional and decision.score == "abstain":
        raise ValueError("Directional evidence exists for this dimension; score 0, 1 or 2 instead of abstain")
    return DimensionScoreDecision(
        dimension_id=dimension_id,
        score=decision.score,
        rationale=decision.rationale,
    )


def _dimension_payload(prompt, response, context, dimension, targets, verdicts, memos, rubric):
    target_ids = {target.target_id for target in targets}
    relevant_verdicts = tuple(verdict for verdict in verdicts if verdict.target_id in target_ids)
    memo_ids = {verdict.memo_id for verdict in relevant_verdicts}
    relevant_memos = tuple(memo for memo in memos if memo.memo_id in memo_ids)
    return {
        "prompt": prompt,
        "response": response,
        "context": context.model_dump(mode="json"),
        "dimension_plan": {"dimensions": [{"dimension_id": dimension.dimension_id}]},
        "targets": [_target_scoring_view(target) for target in targets],
        "verdicts": [_verdict_scoring_view(verdict) for verdict in relevant_verdicts],
        "memos": [_memo_evidence_view(memo) for memo in relevant_memos],
        "rubric": rubric,
    }


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

    drafts_by_dimension = {}
    if active_dimensions:
        try:
            result = session.call(
                "dimension_scorer_v1",
                {
                    "prompt": prompt,
                    "response": response,
                    "context": context.model_dump(mode="json"),
                    "dimension_plan": {
                        "dimensions": [{"dimension_id": dimension.dimension_id} for dimension in active_dimensions]
                    },
                    "targets": [_target_scoring_view(target) for target in active_targets],
                    "verdicts": [_verdict_scoring_view(verdict) for verdict in active_verdicts],
                    "memos": [_memo_evidence_view(memo) for memo in active_memos],
                    "rubric": rubric,
                },
                ScoreDecisionBatch,
                lambda batch: validate_score_decisions(
                    batch,
                    plan,
                    targets,
                    verdicts,
                    ignored_dimensions=forced_abstentions,
                ),
            )
            drafts_by_dimension = {score.dimension_id: score for score in result.scores}
        except StageError:
            # Structural fallback only: the same semantic decision is requested one
            # dimension at a time, while Python attaches the known dimension ID.
            for dimension in active_dimensions:
                relevant_targets = tuple(target for target in targets if dimension.dimension_id in target.dimension_ids)
                drafts_by_dimension[dimension.dimension_id] = _single_dimension_decision(
                    session,
                    "dimension_scorer_single_v1",
                    _dimension_payload(
                        prompt,
                        response,
                        context,
                        dimension,
                        relevant_targets,
                        verdicts,
                        memos,
                        rubric,
                    ),
                    dimension.dimension_id,
                    relevant_targets,
                    verdicts,
                )

    # Selective contextual fallback is deliberately narrower than general scoring:
    # only context-dependent recommendations may be judged from their observable
    # cultural handling when external evidence remains unresolved. External facts
    # and descriptive norms remain abstentions if retrieval cannot establish them.
    fallback_by_dimension = {}
    for dimension in plan.dimensions:
        if dimension.dimension_id not in forced_abstentions:
            continue
        relevant_targets = tuple(target for target in targets if dimension.dimension_id in target.dimension_ids)
        recommendation_targets = tuple(
            target for target in relevant_targets if target.epistemic_type == EpistemicType.RECOMMENDATION
        )
        if not recommendation_targets:
            continue
        fallback_by_dimension[dimension.dimension_id] = _single_dimension_decision(
            session,
            "contextual_fallback_v1",
            {
                "prompt": prompt,
                "response": response,
                "context": context.model_dump(mode="json"),
                "dimension": {"dimension_id": dimension.dimension_id},
                "targets": [_target_scoring_view(target) for target in recommendation_targets],
                "verdicts": [
                    _verdict_scoring_view(verdict)
                    for verdict in verdicts
                    if verdict.target_id in {target.target_id for target in recommendation_targets}
                ],
                "rubric": rubric,
            },
            dimension.dimension_id,
            recommendation_targets,
            (),
        )

    verdicts_by_target = {verdict.target_id: verdict for verdict in verdicts}
    memo_by_target = {verdict.target_id: verdict.memo_id for verdict in verdicts}
    scores = []
    for dimension in plan.dimensions:
        dimension_id = dimension.dimension_id
        relevant_targets = [target for target in targets if dimension_id in target.dimension_ids]
        fallback = fallback_by_dimension.get(dimension_id)
        if fallback is not None and fallback.score != "abstain":
            recommendation_targets = [
                target for target in relevant_targets if target.epistemic_type == EpistemicType.RECOMMENDATION
            ]
            response_quotes = tuple(target.response_quote for target in recommendation_targets)
            if response and not response_quotes:
                response_quotes = (response,)
            score = DimensionScore(
                **fallback.model_dump(mode="json"),
                response_quotes=response_quotes,
                target_ids=tuple(target.target_id for target in recommendation_targets),
                memo_ids=(),
            )
        elif dimension_id in forced_abstentions:
            linked_target_ids = tuple(target.target_id for target in relevant_targets if target.retrieval_appropriate)
            score = DimensionScore(
                dimension_id=dimension_id,
                score="abstain",
                rationale="All relevant retrievable targets are insufficient; dimension remains unresolved.",
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
            response_quotes = tuple(
                target.response_quote for target in relevant_targets if target.target_id in linked_target_ids
            )
            if draft.score != "abstain" and response and not response_quotes:
                response_quotes = (response,)
            score = DimensionScore(
                **draft.model_dump(mode="json"),
                response_quotes=response_quotes,
                target_ids=linked_target_ids,
                memo_ids=tuple(
                    dict.fromkeys(
                        memo_by_target[target_id] for target_id in linked_target_ids if target_id in memo_by_target
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


def vericult_score(scores):
    """Human-readable 0-100 summary for fully scored assessments only.

    Selective abstention is not a cultural penalty. When any applicable dimension
    abstains, suppress the public numeric summary rather than presenting a
    misleading perfect/partial score combination. Internal aggregation and
    Best-of-4 ranking remain unchanged.
    """
    if any(s.score == "abstain" for s in scores):
        return None
    score = exact_score(scores)
    return float(score * 100) if score is not None else None


def cultural_appropriateness(scores):
    """Quality label only when the evidence supports that conclusion.

    Abstention represents unresolved cultural assessment, never a score of 1.
    A demonstrated material violation (score 0) remains a violation even if
    other dimensions cannot be assessed. Otherwise incomplete coverage is
    explicitly reported as insufficient evidence instead of a partial defect.
    """
    scored = [s.score for s in scores if s.score != "abstain"]
    if not scored:
        return "insufficient_evidence"
    if any(value == 0 for value in scored):
        return "culturally_inappropriate"
    if any(s.score == "abstain" for s in scores):
        return "insufficient_evidence"
    if all(value == 2 for value in scored):
        return "culturally_appropriate"
    return "partially_culturally_appropriate"


def abstention_reason(scores):
    abstained = [s for s in scores if s.score == "abstain"]
    if not abstained:
        return None
    return " | ".join(f"{s.dimension_id}: {s.rationale}" for s in abstained)


def rank_results(candidates):
    """Rank only candidates that pass the absolute cultural-appropriateness gate.

    A scored dimension value of 0 is already defined by the frozen rubric as a
    material cultural misalignment, so such a candidate is ineligible for
    endorsement. The gate does not alter any candidate's relative score.
    """
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
            tie_break_reason="At least one candidate failed technically; no ranking was forced.",
        )

    labels = [candidate.cultural_appropriateness for candidate in candidates]
    if any(label == "not_culturally_applicable" for label in labels):
        indices = tuple(i for i, label in enumerate(labels) if label == "not_culturally_applicable")
        return RankingResult(
            candidates=tuple(candidates),
            winner="not_culturally_applicable",
            tied_indices=indices,
            coverage_comparable=comparable,
            tie_break_reason="The shared prompt does not require a cultural appropriateness judgment.",
        )
    if any(label == "not_assessable" for label in labels):
        indices = tuple(i for i, label in enumerate(labels) if label == "not_assessable")
        return RankingResult(
            candidates=tuple(candidates),
            winner="not_assessable",
            tied_indices=indices,
            coverage_comparable=comparable,
            tie_break_reason="At least one response contains no substantive culturally assessable answer content.",
        )
    if any(label == "insufficient_evidence" for label in labels):
        unresolved = tuple(i for i, label in enumerate(labels) if label == "insufficient_evidence")
        return RankingResult(
            candidates=tuple(candidates),
            winner="insufficient_evidence",
            tied_indices=unresolved,
            coverage_comparable=comparable,
            tie_break_reason=(
                "At least one candidate has no scored cultural basis; the full Best-of-4 comparison is unresolved."
            ),
        )

    eligible = tuple(
        i for i, label in enumerate(labels) if label in {"culturally_appropriate", "partially_culturally_appropriate"}
    )
    if not eligible:
        available = [score for score in scores if score is not None]
        relative_top = (
            tuple(i for i, score in enumerate(scores) if score is not None and score == max(available))
            if available
            else ()
        )
        return RankingResult(
            candidates=tuple(candidates),
            winner="no_acceptable_candidate",
            tied_indices=relative_top,
            coverage_comparable=comparable,
            tie_break_reason=(
                "Every candidate contains at least one score-0 material cultural misalignment; "
                "relative scores are retained diagnostically but no candidate is endorsed."
            ),
        )

    eligible_scores = {i: scores[i] for i in eligible if scores[i] is not None}
    if len(eligible_scores) != len(eligible):
        return RankingResult(
            candidates=tuple(candidates),
            winner="insufficient_evidence",
            tied_indices=tuple(i for i in eligible if scores[i] is None),
            coverage_comparable=comparable,
            tie_break_reason="An otherwise eligible candidate has no exact aggregate score.",
        )

    best = max(eligible_scores.values())
    tied = tuple(i for i in eligible if eligible_scores[i] == best)
    if len(tied) == 1:
        return RankingResult(
            candidates=tuple(candidates),
            winner=tied[0],
            tied_indices=tied,
            coverage_comparable=comparable,
            tie_break_reason="Unique highest exact score among culturally eligible candidates.",
        )

    return RankingResult(
        candidates=tuple(candidates),
        winner="no_clear_winner",
        tied_indices=tied,
        coverage_comparable=comparable,
        tie_break_reason="Eligible candidates share the exact highest score; no arbitrary tie-break was applied.",
    )
