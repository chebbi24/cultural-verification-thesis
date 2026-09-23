"""Immutable, closed data contracts; no cultural decisions are encoded here."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1)]
DimensionID = Literal["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContextFact(Record):
    value: Text
    prompt_span: Text


class ContextFrame(Record):
    setting: ContextFact | None = None
    participants: tuple[ContextFact, ...] = ()
    relationships: tuple[ContextFact, ...] = ()
    location: ContextFact | None = None
    temporal_context: ContextFact | None = None
    explicit_constraints: tuple[ContextFact, ...] = ()
    user_goal: ContextFact | None = None


class DimensionApplicability(Record):
    dimension_id: DimensionID
    role: Literal["primary", "secondary"]
    reason: Text


class DimensionPlan(Record):
    dimensions: tuple[DimensionApplicability, ...]
    reasoning: Text

    @model_validator(mode="after")
    def unique(self):
        ids = [d.dimension_id for d in self.dimensions]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate dimensions")
        if self.dimensions and sum(d.role == "primary" for d in self.dimensions) != 1:
            raise ValueError("Nonempty plans require one primary dimension")
        return self


class EpistemicType(str, Enum):
    EXTERNAL = "external_fact"
    NORM = "descriptive_cultural_norm"
    RECOMMENDATION = "context_dependent_recommendation"
    INTERNAL = "response_internal_quality"
    VALUE = "non_verifiable_value_statement"


class TargetDraft(Record):
    response_quote: Text
    proposition: Text
    epistemic_type: EpistemicType
    dimension_ids: tuple[DimensionID, ...] = Field(min_length=1)
    materiality: Text
    retrieval_appropriate: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def retrieval_type(self):
        if self.retrieval_appropriate and self.epistemic_type in (EpistemicType.INTERNAL, EpistemicType.VALUE):
            raise ValueError("Internal quality/value targets must not trigger retrieval")
        if len(set(self.dimension_ids)) != len(self.dimension_ids):
            raise ValueError("Duplicate target dimensions")
        return self


class MaterialTarget(TargetDraft):
    target_id: Text


class TargetBatch(Record):
    targets: tuple[TargetDraft, ...] = Field(max_length=3)
    truncated: bool = False


class QuestionDraft(Record):
    kind: Literal["baseline", "variation", "followup"]
    text: Text


class InitialQuestions(Record):
    questions: tuple[QuestionDraft, QuestionDraft]

    @model_validator(mode="after")
    def pair(self):
        if tuple(q.kind for q in self.questions) != ("baseline", "variation"):
            raise ValueError("Require baseline then variation questions")
        return self


class VerificationQuestion(QuestionDraft):
    question_id: Text


class QueryDraft(Record):
    text: Text


class SearchQuery(QueryDraft):
    query_id: Text
    question_id: Text
    round: Annotated[int, Field(strict=True, ge=1, le=2)]


class SourceType(str, Enum):
    OFFICIAL = "official_legal"
    ACADEMIC = "academic_peer_reviewed"
    SURVEY = "statistical_survey"
    INSTITUTIONAL = "institutional_professional"
    COMMUNITY = "community_insider"
    GENERAL = "general_explanatory"
    COMMERCIAL = "commercial_lifestyle"
    UNKNOWN = "unknown"


class RetrievedDocument(Record):
    document_id: Text
    query: Text
    url: Text
    title: str
    text: Text
    rank: Annotated[int, Field(strict=True, ge=1)]
    provider_score: float | None = None
    retrieved_at: Text
    source_type: SourceType = SourceType.UNKNOWN
    content_hash: Text


class SourceClassification(Record):
    document_id: Text
    source_type: SourceType
    provenance_basis: Literal["explicit", "inferred", "unclear"]
    reason: Text


class SourceBatch(Record):
    sources: tuple[SourceClassification, ...]


class EvidenceSupportDraft(Record):
    source_ref: Annotated[int, Field(strict=True, ge=1)]
    quote: Annotated[str, Field(min_length=1, max_length=300)]


class EvidenceSupport(Record):
    document_id: Text
    quote: Annotated[str, Field(min_length=1, max_length=300)]


class EvidenceStatementDraft(Record):
    text: Text
    kind: Literal["tendency", "context_sensitive_practice", "legal_institutional_rule", "universal_claim"]
    supports: tuple[EvidenceSupportDraft, ...] = Field(min_length=1)


class EvidenceStatement(Record):
    text: Text
    kind: Literal["tendency", "context_sensitive_practice", "legal_institutional_rule", "universal_claim"]
    citations: tuple[Text, ...] = Field(min_length=1)
    supports: tuple[EvidenceSupport, ...] = ()


class MemoDraft(Record):
    answer: Text
    scope: Text
    variation: Text
    agreement: Text
    sufficiency: Literal["sufficient", "conflicting", "insufficient"]
    confidence: Literal["low", "medium", "high"]
    statements: tuple[EvidenceStatementDraft, ...] = Field(max_length=5)


class EvidenceMemo(Record):
    answer: Text
    scope: Text
    variation: Text
    agreement: Text
    sufficiency: Literal["sufficient", "conflicting", "insufficient"]
    confidence: Literal["low", "medium", "high"]
    statements: tuple[EvidenceStatement, ...] = Field(max_length=5)
    citations: tuple[Text, ...]
    memo_id: Text
    question_ids: tuple[Text, ...]


class Followup(Record):
    question: QuestionDraft | None
    reason: Annotated[str, Field(min_length=1, max_length=400)]

    @model_validator(mode="after")
    def kind(self):
        if self.question and self.question.kind != "followup":
            raise ValueError("Followup kind required")
        return self


class TargetVerdict(Record):
    target_id: Text
    memo_id: Text
    verdict: Literal["supported", "contradicted", "mixed", "insufficient"]
    reasoning: Text


class DimensionScore(Record):
    dimension_id: DimensionID
    score: Annotated[int, Field(strict=True, ge=0, le=2)] | Literal["abstain"]
    rationale: Text
    response_quotes: tuple[Text, ...]
    target_ids: tuple[Text, ...]
    memo_ids: tuple[Text, ...]


class ScoreBatch(Record):
    scores: tuple[DimensionScore, ...]


class FilteredResult(Record):
    url: str
    reason: Text


class RetrievalSnapshot(Record):
    snapshot_id: Text
    query: SearchQuery
    documents: tuple[RetrievedDocument, ...]
    filtered: tuple[FilteredResult, ...]
    config_hash: Text
    provider: Text


class CallRecord(Record):
    stage: Text
    attempt: int
    timestamp: Text
    input_hash: Text
    output_json: str | None
    error: str | None


class EvidenceBundle(Record):
    questions: tuple[VerificationQuestion, ...]
    queries: tuple[SearchQuery, ...]
    snapshots: tuple[RetrievalSnapshot, ...]
    documents: tuple[RetrievedDocument, ...]
    source_classifications: tuple[SourceClassification, ...]
    memos: tuple[EvidenceMemo, ...]
    final_memo_id: Text
    followup_reason: str | None
    calls: tuple[CallRecord, ...]


class TargetEvidenceLink(Record):
    target_id: Text
    question_ids: tuple[Text, ...]
    memo_id: Text


class CandidateResult(Record):
    run_id: Text
    context: ContextFrame
    dimension_plan: DimensionPlan
    targets: tuple[MaterialTarget, ...]
    evidence: tuple[EvidenceBundle, ...]
    verdicts: tuple[TargetVerdict, ...]
    dimension_scores: tuple[DimensionScore, ...]
    overall_score: float | None
    applicable_count: int
    scored_count: int
    abstained_dimensions: tuple[DimensionID, ...]
    evidence_coverage: float | None
    candidate_abstained: bool
    targets_truncated: bool
    status: Literal["completed", "failed"]
    errors: tuple[str, ...]
    trace_path: str


class RankingResult(Record):
    candidates: tuple[CandidateResult, ...]
    winner: int | Literal["no_clear_winner"]
    tied_indices: tuple[int, ...]
    coverage_comparable: bool


class RunTrace(Record):
    run_id: Text
    pipeline_version: Text
    git_commit: str | None
    timestamp: Text
    mode: Literal["LIVE", "REPLAY"]
    configuration_json: Text
    prompt_hash: Text
    response_hash: Text
    rubric_hash: Text
    template_hash: Text
    template_versions: tuple[str, ...]
    calls: tuple[CallRecord, ...]
    target_evidence_links: tuple[TargetEvidenceLink, ...]
    events: tuple[str, ...]
    result: CandidateResult
    partial_evidence_json: str | None = None


class EvidenceSchedule(Record):
    schedule_id: Text
    questions: tuple[VerificationQuestion, ...] = Field(min_length=2, max_length=3)
    queries: tuple[SearchQuery, ...] = Field(min_length=2, max_length=3)
    snapshots: tuple[Text, ...] = Field(min_length=2, max_length=3)
    snapshot_hashes: tuple[Text, ...] = Field(min_length=2, max_length=3)
    followup_reason: str | None
