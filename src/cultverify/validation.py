"""Structural validation only. Scores and cultural conclusions belong to the LLM."""

from .schemas import ContextFact
from .trace import digest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_prompt_quote(quote, prompt):
    require(bool(quote) and quote in prompt, "Prompt span must occur verbatim")


def validate_response_quote(quote, response):
    require(bool(quote) and quote in response, "Response quote must occur verbatim")


def validate_context(context, prompt):
    for name in type(context).model_fields:
        value = getattr(context, name)
        for fact in value if isinstance(value, tuple) else (value,):
            if isinstance(fact, ContextFact):
                validate_prompt_quote(fact.prompt_span, prompt)


def validate_targets(batch, response, plan, limit):
    require(len(batch.targets) <= limit, "Target budget exceeded")
    allowed = {d.dimension_id for d in plan.dimensions}
    for target in batch.targets:
        validate_response_quote(target.response_quote, response)
        require(set(target.dimension_ids) <= allowed, "Target dimensions must be planned")


def validate_document_citation(memo, documents):
    ids = {d.document_id for d in documents}
    citations = set(memo.citations)
    require(citations <= ids, "Citations must reference retrieved documents")
    statement_citations = {c for s in memo.statements for c in s.citations}
    require(statement_citations == citations, "Every citation must ground a statement")
    if memo.sufficiency != "insufficient":
        require(bool(citations), "Sufficient/conflicting evidence needs citations")
    if not documents:
        require(
            memo.sufficiency == "insufficient" and memo.confidence == "low",
            "No documents requires insufficient/low evidence",
        )


def validate_sources(batch, documents):
    found = [s.document_id for s in batch.sources]
    require(len(found) == len(set(found)), "Duplicate source classifications")
    require(set(found) == {d.document_id for d in documents}, "Classify each document once")


def validate_scores(batch, response, plan, targets, memos):
    ids = [s.dimension_id for s in batch.scores]
    require(len(ids) == len(set(ids)), "Duplicate dimension score")
    require(set(ids) == {d.dimension_id for d in plan.dimensions}, "Score every planned dimension only")
    targets_by_id = {t.target_id: t for t in targets}
    memo_ids = {m.memo_id for m in memos}
    memo_target = {m.memo_id: t for m, t in zip(memos, (t for t in targets if t.retrieval_appropriate))}
    for score in batch.scores:
        for quote in score.response_quotes:
            validate_response_quote(quote, response)
        require(set(score.target_ids) <= targets_by_id.keys(), "Unknown target ID")
        require(set(score.memo_ids) <= memo_ids, "Unknown memo ID")
        for memo_id in score.memo_ids:
            require(score.dimension_id in memo_target[memo_id].dimension_ids, "Memo/dimension mismatch")
        for tid in score.target_ids:
            require(score.dimension_id in targets_by_id[tid].dimension_ids, "Target/dimension mismatch")
        if score.score != "abstain" and response:
            require(bool(score.response_quotes), "A scored response requires a supporting quote")


def validate_verdict(verdict, target, memo):
    require(verdict.target_id == target.target_id, "Wrong target link")
    require(verdict.memo_id == memo.memo_id, "Wrong memo link")
    if memo.sufficiency == "insufficient":
        require(verdict.verdict == "insufficient", "Insufficient evidence requires an insufficient verdict")


def validate_trace_links(trace):
    result = trace.result
    require(trace.run_id == result.run_id, "Run ID mismatch")
    targets = {t.target_id for t in result.targets}
    require(len(targets) == len(result.targets), "Duplicate target IDs")
    memos = {m.memo_id for b in result.evidence for m in b.memos}
    questions = {q.question_id for b in result.evidence for q in b.questions}
    for bundle in result.evidence:
        qids = {q.question_id for q in bundle.questions}
        require(bundle.final_memo_id in {m.memo_id for m in bundle.memos}, "Missing final memo")
        require(len(bundle.questions) in (2, 3), "Invalid question count")
        require(tuple(q.kind for q in bundle.questions[:2]) == ("baseline", "variation"), "Initial question kinds")
        require(len(bundle.queries) == len(bundle.snapshots), "Missing retrieval snapshot")
        for query, snapshot in zip(bundle.queries, bundle.snapshots):
            require(query.question_id in qids, "Query question missing")
            require(query == snapshot.query, "Snapshot query mismatch")
            require(query.round in (1, 2), "Round limit violated")
            for doc in snapshot.documents:
                require(doc.query == query.text, "Document query mismatch")
                require(doc.content_hash == digest(doc.text), "Document hash mismatch")
        for memo in bundle.memos:
            require(set(memo.question_ids) <= qids, "Memo question missing")
            validate_document_citation(memo, bundle.documents)
    for link in trace.target_evidence_links:
        require(link.target_id in targets and link.memo_id in memos, "Invalid target/memo link")
        require(set(link.question_ids) <= questions, "Invalid target/question link")
    for verdict in result.verdicts:
        require(verdict.target_id in targets and verdict.memo_id in memos, "Invalid verdict link")
        require(
            any(
                link.target_id == verdict.target_id and link.memo_id == verdict.memo_id
                for link in trace.target_evidence_links
            ),
            "Verdict has no matching evidence link",
        )
    if result.status == "completed":
        require(
            {v.target_id for v in result.verdicts} == {t.target_id for t in result.targets if t.retrieval_appropriate},
            "Every retrievable target requires a verdict",
        )

    score_ids = [s.dimension_id for s in result.dimension_scores]
    require(len(score_ids) == len(set(score_ids)), "Duplicate trace scores")
    require(
        set(score_ids) == {d.dimension_id for d in result.dimension_plan.dimensions}, "Trace scoring coverage mismatch"
    )
    target_map = {t.target_id: t for t in result.targets}
    for score in result.dimension_scores:
        require(set(score.target_ids) <= targets and set(score.memo_ids) <= memos, "Invalid score references")
        for memo_id in score.memo_ids:
            require(
                any(
                    link.memo_id == memo_id and score.dimension_id in target_map[link.target_id].dimension_ids
                    for link in trace.target_evidence_links
                ),
                "Score memo has no dimension-linked target",
            )
    require(result.scored_count == sum(s.score != "abstain" for s in result.dimension_scores), "Scored count mismatch")
    require(result.applicable_count == len(result.dimension_plan.dimensions), "Applicable count mismatch")
