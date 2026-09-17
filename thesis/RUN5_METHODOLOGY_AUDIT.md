# Run 5 - Verifier Methodology Audit

## Scope

Run 5 writes Chapter 5 only: the code-grounded methodology of the standalone evidence-grounded cultural verifier. It does not modify the frozen implementation and does not populate experimental results.

Authoritative implementation branch:

- `agent/final-verifier`
- pipeline version: `cultverify-1.0.0`

## Implementation files audited

The chapter was checked against the active implementation, especially:

- `src/cultverify/config.py`
- `src/cultverify/planner.py`
- `src/cultverify/targets.py`
- `src/cultverify/evidence.py`
- `src/cultverify/retrieval.py`
- `src/cultverify/scoring.py`
- `src/cultverify/schemas.py`
- `src/cultverify/validation.py`
- `src/cultverify/llm.py`
- `src/cultverify/prompts.py`
- `src/cultverify/trace.py`
- `src/cultverify/pipeline.py`
- `docs/validation.md`

## Methodological claims frozen in Chapter 5

### Independence

The verifier accepts no reward-model score, human reference label, expected issue, benchmark answer or benchmark metadata. Skywork and direct judging remain independent comparison systems.

### Shared prompt-level planning

Best-of-4 ranking computes context and the D01-D10 dimension plan once from the prompt, then evaluates all four candidates under that same plan. Primary/secondary roles indicate relevance only; they do not change score weight.

### Context validation

Context extraction sees the prompt only. Every retained context fact must contain a verbatim `prompt_span`. Persistently invalid context extraction falls back to an empty context frame instead of retaining unsupported facts.

### Material targets

Candidate responses are decomposed into at most three decision-relevant quoted targets. Target quotations must occur verbatim in the response, and target dimensions must be contained in the shared plan.

The active epistemic types are:

- `external_fact`
- `descriptive_cultural_norm`
- `context_dependent_recommendation`
- `response_internal_quality`
- `non_verifiable_value_statement`

Internal-quality and non-verifiable-value targets cannot trigger retrieval.

### Candidate-blind boundary

Question generation is candidate-derived and therefore not blind. The candidate-blind boundary starts only after the baseline/variation questions are generated.

`BlindEvidenceEngine.evaluate(...)` receives only the exact question tuple and exact `ContextFrame`. Runtime type checks and closed Pydantic schemas reject containers that could carry extra candidate fields. A fresh semantic session is created for the evidence stage.

This is described as a structural information boundary, not proof of unbiasedness.

### Retrieval

LIVE retrieval uses Tavily. The adapter stores the search-result content actually used, not full downloaded pages. It records URL, title, excerpt, rank, provider score where available, query, timestamp, document ID and content hash.

The retriever requests up to twice `top_k` before filtering/deduplication and retains at most `top_k`; the default is three accepted documents per question.

### Leakage mitigation

Known thesis/repository/annotation/result sources can be excluded by domains, repositories and path globs. Filtering occurs before semantic evidence synthesis. Unknown mirrors and pretraining contamination remain possible and are explicitly not claimed to be solved.

### Source classification

The active source classes are:

- `official_legal`
- `academic_peer_reviewed`
- `statistical_survey`
- `institutional_professional`
- `community_insider`
- `general_explanatory`
- `commercial_lifestyle`
- `unknown`

No scalar source-quality formula is used.

### Evidence memo

The memo contains answer, scope, variation, agreement/disagreement, sufficiency, confidence, evidence statements and citations.

Sufficiency states:

- `sufficient`
- `conflicting`
- `insufficient`

Confidence states:

- `low`
- `medium`
- `high`

Citation validation guarantees identifier/link integrity only. It does not guarantee semantic entailment.

### Follow-up budget

The first round uses exactly two questions. If the first memo is not sufficient, at most one gap-specific follow-up may be searched in round two. There is no recursive search-until-satisfied loop.

### Evidence freezing

The final `EvidenceMemo` is immutable. The pipeline records a freeze event and checks the memo digest before and after target comparison. This prevents post-comparison mutation of the memo object but is not claimed to improve accuracy by itself.

### Target verdicts

Verdicts are:

- `supported`
- `contradicted`
- `mixed`
- `insufficient`

There is no hard-coded mapping from a target verdict to a D01-D10 score.

### Dimension scoring

Each planned dimension receives `0`, `1`, `2`, or `abstain`. The scorer sees the full prompt/response plus validated intermediate objects. Non-abstained scores must contain exact response quotations, and target/memo references are structurally validated.

Python validates structure and provenance links; it does not encode the substantive cultural score.

### Aggregation

For numerically scored dimensions J:

`overall = mean(score_d / 2)`

Abstentions are excluded. If all applicable dimensions abstain, overall score is null.

`evidence_coverage` is the proportion of retrieval-appropriate targets whose final memo is marked sufficient. It is a sufficiency-coverage measure, not evidence accuracy.

### Best-of-4 ranking

Ranking uses exact rational comparison. A unique highest score wins. An exact maximum tie returns `no_clear_winner`; all-abstained sets also return `no_clear_winner`. There is no epsilon/tie margin.

`coverage_comparable` reports whether the same dimension set was numerically scored for all candidates. Coverage mismatch does not override the frozen highest-score rule.

### LIVE and REPLAY

LIVE collects and freezes retrieval snapshots and schedules.

REPLAY has no live retriever and no live fallback. It verifies stored schedule/snapshot consistency and reuses stored queries and documents. Semantic synthesis/scoring still run, so REPLAY is not a fully deterministic or offline-LLM mode.

### Traceability

Candidate traces record pipeline version, Git commit when available, configuration, prompt/response hashes, rubric/template hashes, semantic calls, target-evidence links, freeze/comparison events, result and partial evidence on failure.

API keys are not part of the serialized configuration. The trace is not automatically anonymous because response quotations and semantic outputs can contain original text fragments.

## Software-validation status

The active validation record states:

- 55 tests passed
- 1 gated live-provider test skipped
- Ruff lint passed
- Ruff formatting check passed

The tests cover software contracts including quote validation, blind boundaries, target/search budgets, source citations, provenance filtering, memo immutability, exact ties, shared planning, REPLAY integrity, provider contracts, CLI behavior and packaging.

This evidence supports claims about software behavior only. It does not establish cultural accuracy or superiority.

## Chapter result

`chapters/05_verifier_methodology.tex` is now a full first draft.

Final local compile after Run 5:

- Chapter 5 document span: pp. 27-39
- Chapter 5 length: 13 pages
- Whole current PDF: 60 pages including incomplete later chapters, bibliography and appendices
- unresolved citations: none
- unresolved cross-references: none
- overfull boxes in Chapter 5: none
- LaTeX compile: successful

## Deliberately withheld claims

Run 5 does **not** claim that:

- candidate blindness eliminates evaluator bias;
- neutral question generation is objectively unbiased;
- Tavily results are complete or representative;
- source classification is always correct;
- citation validity guarantees evidence entailment;
- one follow-up round is empirically optimal;
- evidence freezing improves accuracy;
- abstention provides selective-classification risk guarantees;
- REPLAY makes the semantic pipeline deterministic;
- unit tests demonstrate cultural validity;
- the verifier outperforms Skywork, direct judging or CARB.

These remain empirical questions or explicit limitations.

## Run-5 stopping point

Run 5 stops after completing and validating Chapter 5. Chapter 6 remains the next isolated writing run.
