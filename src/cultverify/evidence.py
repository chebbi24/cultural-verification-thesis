"""Blind evidence engine: its public input contains no candidate or target object."""

from .config import PIPELINE_VERSION
from .llm import SemanticSession, StageError
from .prompts import COMMON, PROMPTS
from .retrieval import RetrievalError
from .schemas import (
    ContextFrame,
    EvidenceBundle,
    EvidenceMemo,
    EvidenceSchedule,
    EvidenceStatement,
    EvidenceSupport,
    Followup,
    MemoDraft,
    QueryDraft,
    SearchQuery,
    SourceBatch,
    SourceClassification,
    SourceType,
    StatementRelevanceBatch,
    VerificationQuestion,
)
from .trace import digest, stable_id, write_json
from .validation import (
    matching_support_documents,
    require,
    validate_sources,
    validate_statement_relevance,
)

LLM_DOCUMENT_TEXT_LIMIT = 2000


def _llm_document(document):
    data = document.model_dump(mode="json")
    data.pop("document_id")
    data["text"] = document.text[:LLM_DOCUMENT_TEXT_LIMIT]
    return data


def _normalized_source_classification(source):
    reason = " ".join(source.reason.casefold().split())
    source_type = source.source_type
    provenance_basis = source.provenance_basis
    strong_types = {
        SourceType.OFFICIAL,
        SourceType.ACADEMIC,
        SourceType.SURVEY,
        SourceType.INSTITUTIONAL,
    }
    explicit_contradictions = {
        SourceType.OFFICIAL: (
            "not official",
            "not an official",
            "not government",
            "not a government",
            "not legal",
            "not a legal",
            "not public-authority",
            "not a public authority",
        ),
        SourceType.ACADEMIC: (
            "not peer-reviewed",
            "not peer reviewed",
            "not academic",
            "not an academic",
            "not scholarly",
        ),
        SourceType.INSTITUTIONAL: (
            "not a recognized institution",
            "not a recognised institution",
            "not a professional body",
        ),
    }
    contradicts_selected = any(phrase in reason for phrase in explicit_contradictions.get(source_type, ()))
    contradicts_enum = any(
        other is not source_type
        and (
            f"should be {other.value}" in reason
            or f"should be classified as {other.value}" in reason
            or f"source type should be {other.value}" in reason
        )
        for other in SourceType
    )
    if (source_type in strong_types and provenance_basis != "explicit") or contradicts_selected or contradicts_enum:
        source_type = SourceType.UNKNOWN
        provenance_basis = "unclear"
    return source.model_copy(update={"source_type": source_type, "provenance_basis": provenance_basis})


def _downgrade_confidence(confidence):
    return {"high": "medium", "medium": "low", "low": "low"}[confidence]


class BlindEvidenceEngine:
    def __init__(self, llm, config, store):
        self._llm = llm
        self._config = config
        self._store = store
        self.last_calls = ()
        self.last_checkpoint = None

    def evaluate(
        self, questions: tuple[VerificationQuestion, VerificationQuestion], context: ContextFrame
    ) -> EvidenceBundle:
        # Reject lookalike/subclass containers that could carry extra candidate fields.
        require(type(context) is ContextFrame, "Exact context schema required")
        require(
            type(questions) is tuple
            and len(questions) == 2
            and all(type(q) is VerificationQuestion for q in questions),
            "Exact neutral-question schemas required",
        )
        require(tuple(q.kind for q in questions) == ("baseline", "variation"), "Initial question pair required")
        session = SemanticSession(self._llm, self._config)  # fresh call records, no candidate history
        all_questions, queries, snapshots, docs, classes, memos = list(questions), [], [], [], [], []
        followup_reason = None
        key = stable_id(
            "schedule",
            {
                "version": PIPELINE_VERSION,
                "context": context.model_dump(mode="json"),
                "questions": [q.model_dump(mode="json") for q in questions],
                "retrieval": self._store.config_hash,
                "rounds": self._config.max_retrieval_rounds,
                "model": self._config.verifier_model_id,
                "provider": self._config.verifier_model_provider,
                "temperature": self._config.temperature,
                "prompts": digest([COMMON, PROMPTS]),
            },
        )
        path = self._config.cache_directory / f"{key}.json"
        schedule = None
        try:
            if self._config.mode == "REPLAY" or path.exists():
                if not path.exists():
                    raise RetrievalError(f"Missing frozen question/query schedule: {key}")
                schedule = EvidenceSchedule.model_validate_json(path.read_text(encoding="utf-8")).model_dump(
                    mode="json"
                )
                require(schedule["schedule_id"] == key, "Schedule ID mismatch")
                frozen_questions = tuple(VerificationQuestion.model_validate(q) for q in schedule["questions"])
                require(frozen_questions[:2] == questions, "Schedule question mismatch")
                require(len(frozen_questions) in (2, 3), "Schedule question count")
                if len(frozen_questions) == 3:
                    require(
                        frozen_questions[2].kind == "followup" and self._config.max_retrieval_rounds == 2,
                        "Schedule followup/round mismatch",
                    )
                require(
                    len(schedule["queries"])
                    == len(frozen_questions)
                    == len(schedule["snapshots"])
                    == len(schedule["snapshot_hashes"]),
                    "Incomplete frozen schedule",
                )

            def retrieve(question, round_number):
                if schedule is None:
                    query_text = session.call(
                        "query_rewriter_v1",
                        {"question": question.model_dump(mode="json"), "context": context.model_dump(mode="json")},
                        QueryDraft,
                    )
                    query = SearchQuery(
                        text=query_text.text,
                        question_id=question.question_id,
                        round=round_number,
                        query_id=stable_id("query", [question.question_id, query_text.text, round_number]),
                    )
                    snapshot = self._store.get(query)
                else:
                    index = len(queries)
                    query = SearchQuery.model_validate(schedule["queries"][index])
                    require(
                        query.question_id == question.question_id and query.round == round_number,
                        "Frozen query does not match question/round",
                    )
                    snapshot = self._store.read_by_id(schedule["snapshots"][index])
                    require(snapshot.query == query, "Frozen snapshot/query mismatch")
                    require(
                        digest(snapshot) == schedule["snapshot_hashes"][index], "Frozen snapshot integrity mismatch"
                    )
                queries.append(query)
                snapshots.append(snapshot)
                known_ids = {d.document_id for d in docs}
                new = tuple(d for d in snapshot.documents if d.document_id not in known_ids)
                if new:
                    classifier_documents = [
                        {
                            "document_id": d.document_id,
                            "url": d.url,
                            "title": d.title,
                            "text": d.text[:LLM_DOCUMENT_TEXT_LIMIT],
                        }
                        for d in new
                    ]
                    try:
                        classified = session.call(
                            "source_classifier_v1",
                            {"documents": classifier_documents},
                            SourceBatch,
                            lambda b: validate_sources(b, new),
                        )
                        classified_sources = tuple(
                            _normalized_source_classification(source) for source in classified.sources
                        )
                    except StageError:
                        classified_sources = tuple(
                            SourceClassification(
                                document_id=d.document_id,
                                source_type=SourceType.UNKNOWN,
                                provenance_basis="unclear",
                                reason="Source classification was unavailable; conservatively marked unknown.",
                            )
                            for d in new
                        )
                    types = {s.document_id: s.source_type for s in classified_sources}
                    classes.extend(classified_sources)
                    docs.extend(d.model_copy(update={"source_type": types[d.document_id]}) for d in new)

            def synthesize():
                memo = session.call(
                    "evidence_memo_v1",
                    {
                        "questions": [q.model_dump(mode="json") for q in all_questions],
                        "context": context.model_dump(mode="json"),
                        "documents": [_llm_document(d) for d in docs],
                    },
                    MemoDraft,
                )
                # Ground supports deterministically. Malformed/paraphrased supports are discarded
                # rather than allowed to influence downstream judgments.
                mapped_statements = []
                grounding_loss = False
                for statement in memo.statements:
                    resolved_supports = []
                    seen_supports = set()
                    for support in statement.supports:
                        matches = matching_support_documents(support.quote, docs)
                        if len(matches) != 1:
                            grounding_loss = True
                            continue
                        matching_document = matches[0]
                        support_key = (matching_document.document_id, support.quote)
                        if support_key in seen_supports:
                            continue
                        seen_supports.add(support_key)
                        resolved_supports.append(
                            EvidenceSupport(document_id=matching_document.document_id, quote=support.quote)
                        )
                    if not resolved_supports:
                        grounding_loss = True
                        continue
                    cited_docs = tuple(
                        next(document for document in docs if document.document_id == support.document_id)
                        for support in resolved_supports
                    )
                    kind = statement.kind
                    if kind == "legal_institutional_rule" and not any(
                        document.source_type == SourceType.OFFICIAL for document in cited_docs
                    ):
                        kind = "context_sensitive_practice"
                    mapped_statements.append(
                        EvidenceStatement(
                            text=statement.text,
                            kind=kind,
                            citations=tuple(dict.fromkeys(document.document_id for document in cited_docs)),
                            supports=tuple(resolved_supports),
                        )
                    )

                # Independent blind semantic gate: a grounded claim must both be supported
                # by its quoted spans and materially answer at least one verification question.
                semantic_filter_loss = False
                if mapped_statements:
                    try:
                        relevance = session.call(
                            "evidence_relevance_v1",
                            {
                                "questions": [q.model_dump(mode="json") for q in all_questions],
                                "statements": [
                                    {
                                        "statement_index": index,
                                        "text": statement.text,
                                        "kind": statement.kind,
                                        "support_quotes": [support.quote for support in statement.supports],
                                    }
                                    for index, statement in enumerate(mapped_statements)
                                ],
                            },
                            StatementRelevanceBatch,
                            lambda batch: validate_statement_relevance(batch, len(mapped_statements)),
                        )
                        accepted_indices = {
                            judgment.statement_index
                            for judgment in relevance.judgments
                            if judgment.supported_by_quotes and judgment.relevant
                        }
                        semantic_filter_loss = len(accepted_indices) != len(mapped_statements)
                        mapped_statements = [
                            statement for index, statement in enumerate(mapped_statements) if index in accepted_indices
                        ]
                    except StageError:
                        semantic_filter_loss = True
                        mapped_statements = []

                citations = tuple(dict.fromkeys(c for statement in mapped_statements for c in statement.citations))
                if not mapped_statements:
                    sufficiency = "insufficient"
                    confidence = "low"
                else:
                    sufficiency = memo.sufficiency
                    confidence = "low" if sufficiency == "insufficient" else memo.confidence
                    if sufficiency != "insufficient" and (grounding_loss or semantic_filter_loss):
                        confidence = _downgrade_confidence(confidence)
                frozen_payload = {
                    "answer": memo.answer,
                    "scope": memo.scope,
                    "variation": memo.variation,
                    "agreement": memo.agreement,
                    "sufficiency": sufficiency,
                    "confidence": confidence,
                    "statements": tuple(statement.model_dump(mode="json") for statement in mapped_statements),
                    "citations": citations,
                }
                frozen = EvidenceMemo(
                    **frozen_payload,
                    memo_id=stable_id("memo", [key, len(memos), frozen_payload]),
                    question_ids=tuple(q.question_id for q in all_questions),
                )
                memos.append(frozen)

            for question in questions:
                retrieve(question, 1)
            synthesize()
            followup = None
            if schedule is not None:
                if len(frozen_questions) == 3:
                    followup = frozen_questions[2]
                    followup_reason = schedule["followup_reason"]
            elif memos[-1].sufficiency != "sufficient" and self._config.max_retrieval_rounds == 2:
                try:
                    decision = session.call(
                        "followup_v1",
                        {
                            "questions": [q.model_dump(mode="json") for q in all_questions],
                            "context": context.model_dump(mode="json"),
                            "memo": {
                                "sufficiency": memos[-1].sufficiency,
                                "confidence": memos[-1].confidence,
                                "statements": [statement.model_dump(mode="json") for statement in memos[-1].statements],
                            },
                        },
                        Followup,
                    )
                except StageError:
                    decision = None
                    followup_reason = "Follow-up planning unavailable; retained the current frozen memo."
                if decision is not None:
                    followup_reason = decision.reason
                    if decision.question:
                        candidate_text = " ".join(decision.question.text.lower().split())
                        existing_texts = {" ".join(q.text.lower().split()) for q in all_questions}
                        if candidate_text not in existing_texts:
                            followup = VerificationQuestion(
                                **decision.question.model_dump(),
                                question_id=stable_id("question", decision.question.model_dump(mode="json")),
                            )
            if followup:
                all_questions.append(followup)
                retrieve(followup, 2)
                synthesize()  # terminal round, never recursively search
            if schedule is None:
                write_json(
                    path,
                    {
                        "schedule_id": key,
                        "questions": [q.model_dump(mode="json") for q in all_questions],
                        "queries": [q.model_dump(mode="json") for q in queries],
                        "snapshots": [s.snapshot_id for s in snapshots],
                        "snapshot_hashes": [digest(s) for s in snapshots],
                        "followup_reason": followup_reason,
                    },
                )
            return EvidenceBundle(
                questions=tuple(all_questions),
                queries=tuple(queries),
                snapshots=tuple(snapshots),
                documents=tuple(docs),
                source_classifications=tuple(classes),
                memos=tuple(memos),
                final_memo_id=memos[-1].memo_id,
                followup_reason=followup_reason,
                calls=tuple(session.calls),
            )
        finally:
            self.last_calls = tuple(session.calls)
            self.last_checkpoint = {
                "questions": [q.model_dump(mode="json") for q in all_questions],
                "queries": [q.model_dump(mode="json") for q in queries],
                "snapshots": [s.model_dump(mode="json") for s in snapshots],
                "memos": [m.model_dump(mode="json") for m in memos],
            }
