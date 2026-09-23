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
    Followup,
    MemoDraft,
    QueryDraft,
    SearchQuery,
    SourceBatch,
    SourceClassification,
    SourceType,
    VerificationQuestion,
)
from .trace import digest, stable_id, write_json
from .validation import require, validate_memo_draft, validate_sources

LLM_DOCUMENT_TEXT_LIMIT = 2000


def _llm_document(document, source_ref):
    data = document.model_dump(mode="json")
    data.pop("document_id")
    data["source_ref"] = source_ref
    data["text"] = document.text[:LLM_DOCUMENT_TEXT_LIMIT]
    return data


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
                        normalized = []
                        for source in classified.sources:
                            reason = source.reason.lower()
                            source_type = source.source_type
                            if source_type == SourceType.ACADEMIC and any(
                                phrase in reason
                                for phrase in (
                                    "not peer-reviewed",
                                    "not peer reviewed",
                                    "not academic",
                                    "not a peer-reviewed",
                                )
                            ):
                                source_type = SourceType.UNKNOWN
                            if source_type == SourceType.OFFICIAL and any(
                                phrase in reason
                                for phrase in (
                                    "not official",
                                    "not an official",
                                    "not legal",
                                    "not a legal",
                                    "not government",
                                )
                            ):
                                source_type = SourceType.UNKNOWN
                            normalized.append(source.model_copy(update={"source_type": source_type}))
                        classified_sources = tuple(normalized)
                    except StageError:
                        classified_sources = tuple(
                            SourceClassification(
                                document_id=d.document_id,
                                source_type=SourceType.UNKNOWN,
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
                        "documents": [_llm_document(d, i) for i, d in enumerate(docs, start=1)],
                    },
                    MemoDraft,
                    lambda m: validate_memo_draft(m, docs),
                )
                # Map simple local source refs back to exact frozen document IDs.
                mapped_statements = []
                for statement in memo.statements:
                    cited_docs = tuple(docs[ref - 1] for ref in dict.fromkeys(statement.source_refs))
                    kind = statement.kind
                    if kind == "legal_institutional_rule" and not any(
                        document.source_type == SourceType.OFFICIAL for document in cited_docs
                    ):
                        kind = "context_sensitive_practice"
                    mapped_statements.append(
                        EvidenceStatement(
                            text=statement.text,
                            kind=kind,
                            citations=tuple(document.document_id for document in cited_docs),
                        )
                    )
                citations = tuple(
                    dict.fromkeys(c for statement in mapped_statements for c in statement.citations)
                )
                frozen_payload = {
                    "answer": memo.answer,
                    "scope": memo.scope,
                    "variation": memo.variation,
                    "agreement": memo.agreement,
                    "sufficiency": memo.sufficiency,
                    "confidence": memo.confidence,
                    "statements": tuple(mapped_statements),
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
                decision = session.call(
                    "followup_v1",
                    {
                        "questions": [q.model_dump(mode="json") for q in all_questions],
                        "context": context.model_dump(mode="json"),
                        "memo": memos[-1].model_dump(mode="json"),
                    },
                    Followup,
                )
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
