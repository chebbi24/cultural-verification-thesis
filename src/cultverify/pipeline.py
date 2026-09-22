from uuid import uuid4
from pydantic import ValidationError
from .config import PIPELINE_VERSION
from .evidence import BlindEvidenceEngine
from .llm import SemanticSession, StageError
from .planner import load_rubric, plan_prompt
from .prompts import COMMON, PROMPTS
from .retrieval import RetrievalError, SnapshotStore
from .schemas import CandidateResult, ContextFrame, DimensionPlan, RunTrace, TargetEvidenceLink
from .scoring import abstain_scores, aggregate, compare_target, rank_results, score_dimensions
from .targets import extract_targets, neutral_questions
from .trace import canonical, digest, git_commit, timestamp, write_json
from .validation import validate_trace_links


class CulturalVerifier:
    def __init__(self, *, llm, retriever, config):
        if llm.config != config:
            raise ValueError("One identical model configuration is required for every stage")
        self.llm, self.config = llm, config
        self.store = SnapshotStore(config, retriever)
        self.rubric = load_rubric()

    def verify(self, prompt: str, response: str) -> CandidateResult:
        self._inputs(prompt, response)
        session = SemanticSession(self.llm, self.config)
        try:
            context, plan = plan_prompt(session, prompt, self.rubric)
            planning_error = None
        except StageError as exc:
            context, plan = ContextFrame(), DimensionPlan(dimensions=(), reasoning="Planning failed")
            planning_error = str(exc)
        return self._verify(prompt, response, context, plan, tuple(session.calls), planning_error)

    def rank(self, prompt: str, responses: list[str]):
        if len(responses) != 4:
            raise ValueError("Best-of-4 requires exactly four responses")
        for response in responses:
            self._inputs(prompt, response)
        session = SemanticSession(self.llm, self.config)
        try:
            context, plan = plan_prompt(session, prompt, self.rubric)
            error = None
        except StageError as exc:
            context, plan = ContextFrame(), DimensionPlan(dimensions=(), reasoning="Planning failed")
            error = str(exc)
        return rank_results(
            [self._verify(prompt, response, context, plan, tuple(session.calls), error) for response in responses]
        )

    @staticmethod
    def _inputs(prompt, response):
        if not isinstance(prompt, str) or not prompt.strip() or not isinstance(response, str):
            raise ValueError("A nonempty prompt and a string response are required")

    def _verify(self, prompt, response, context, plan, planning_calls, planning_error):
        run_id = uuid4().hex
        trace_path = str((self.config.trace_directory / f"{run_id}.json").resolve())
        session = SemanticSession(self.llm, self.config)
        targets, bundles, verdicts, links, events, evidence_calls = (), [], [], [], [], []
        errors, truncated, partial_evidence = [], False, None
        status = "completed"
        engine = BlindEvidenceEngine(self.llm, self.config, self.store)
        try:
            if planning_error:
                raise StageError(planning_error)
            if plan.dimensions:
                targets, truncated = extract_targets(session, prompt, response, context, plan)
                for target in targets:
                    if not target.retrieval_appropriate:
                        continue  # assessed directly by the dimension scorer
                    questions = neutral_questions(session, target, context)
                    events.append(f"questions_ready:{target.target_id}")
                    try:
                        bundle = engine.evaluate(questions, context)
                    except (StageError, RetrievalError, ValueError, OSError):
                        partial_evidence = canonical(engine.last_checkpoint)
                        raise
                    finally:
                        evidence_calls.extend(engine.last_calls)
                    bundles.append(bundle)
                    memo = bundle.memos[-1]
                    events.append(f"memo_frozen:{memo.memo_id}")
                    links.append(
                        TargetEvidenceLink(
                            target_id=target.target_id,
                            question_ids=tuple(q.question_id for q in bundle.questions),
                            memo_id=memo.memo_id,
                        )
                    )
                    before = digest(memo)
                    verdicts.append(compare_target(session, target, memo))
                    if digest(memo) != before:
                        raise ValueError("Frozen memo changed")
                    events.append(f"target_compared:{target.target_id}")
                scores = score_dimensions(
                    session,
                    prompt,
                    response,
                    context,
                    plan,
                    targets,
                    verdicts,
                    [b.memos[-1] for b in bundles],
                    self.rubric,
                )
            else:
                scores = ()
        except (StageError, RetrievalError, ValidationError, ValueError, OSError) as exc:
            status = "failed"
            # Our own error messages contain no credentials or raw HTTP body.
            errors.append(str(exc) if isinstance(exc, (StageError, RetrievalError)) else type(exc).__name__)
            scores = abstain_scores(plan, "Pipeline could not produce structurally valid evidence/scoring")
        external_count = sum(t.retrieval_appropriate for t in targets)
        covered_count = sum(b.memos[-1].sufficiency != "insufficient" for b in bundles)
        overall = aggregate(scores)
        result = CandidateResult(
            run_id=run_id,
            context=context,
            dimension_plan=plan,
            targets=targets,
            evidence=tuple(bundles),
            verdicts=tuple(verdicts),
            dimension_scores=scores,
            overall_score=overall,
            applicable_count=len(plan.dimensions),
            scored_count=sum(s.score != "abstain" for s in scores),
            abstained_dimensions=tuple(s.dimension_id for s in scores if s.score == "abstain"),
            evidence_coverage=covered_count / external_count if external_count else None,
            candidate_abstained=overall is None,
            targets_truncated=truncated,
            status=status,
            errors=tuple(errors),
            trace_path=trace_path,
        )
        trace = RunTrace(
            run_id=run_id,
            pipeline_version=PIPELINE_VERSION,
            git_commit=git_commit(),
            timestamp=timestamp(),
            mode=self.config.mode,
            configuration_json=canonical(self.config),
            prompt_hash=digest(prompt),
            response_hash=digest(response),
            rubric_hash=digest(self.rubric),
            template_hash=digest([COMMON, PROMPTS]),
            template_versions=tuple(PROMPTS),
            calls=tuple(
                sorted(planning_calls + tuple(session.calls) + tuple(evidence_calls), key=lambda c: c.timestamp)
            ),
            target_evidence_links=tuple(links),
            events=tuple(events),
            result=result,
            partial_evidence_json=partial_evidence,
        )
        validate_trace_links(trace)
        write_json(trace_path, trace)
        return result
