# Phase 1 verifier audit — pre-gold freeze gate

Branch audited: `agent/clean-standalone-verifier`, created from the clean verifier implementation at commit `2e546a48ba0950e78f7bd244b5b37b7b475ccf2d`.

The audit is architectural and structural. It does not use the PLT human labels to tune verifier behavior and does not claim cultural accuracy.

## Conformance findings

The active `src/cultverify` implementation conforms to the frozen core design in the following ways:

- D01–D10 are the only accepted cultural dimensions in the typed schemas and packaged runtime rubric.
- `rank()` computes prompt context and dimension planning once and reuses the same objects across all four candidates.
- Material targets are capped at three and response quotes are validated verbatim.
- Exactly two initial questions are required for each retrievable target: baseline then variation.
- `BlindEvidenceEngine.evaluate()` accepts only the exact neutral-question tuple and `ContextFrame`; candidate responses and target objects are not accepted by its public API.
- Query rewriting receives only the neutral question and prompt-derived context.
- Retrieval is bounded to round 1 plus at most one follow-up round (`R_max=2`).
- LIVE retrieval is snapshotted and REPLAY has no live fallback.
- Benchmark/thesis leakage filtering is URL/repository/path based and runs before evidence synthesis.
- Evidence memos and nested schema objects are immutable; the pipeline checks memo hashes before and after target comparison.
- Target comparison occurs only after the final memo is frozen.
- Dimension scoring uses 0/1/2/abstain and equal aggregation; no Python score caps or culture-specific score overrides are present.
- Exact score ties and all-abstained Best-of-4 sets return `no_clear_winner`.
- Full trace linkage is validated between targets, questions, queries, snapshots, documents, memos, verdicts and dimension scores.
- The independent reward-model baseline remains outside `cultverify`.

## Phase 1 corrections

Two implementation-quality corrections were made during this gate:

1. `evidence_coverage` now counts any final memo that is not `insufficient` (`sufficient` or `conflicting`) as evidence-covered. Conflicting evidence is still substantive evidence and should not be treated as absence of evidence; the target verdict can then remain `mixed` or otherwise reflect the conflict.
2. GitHub Actions was updated to execute the actual pytest suite and Ruff checks on the clean branch. The previous workflow still invoked `unittest`, although the repository tests are written for pytest.

## Added structural guards

Phase 1 adds tests that:

- rebuild Human Gold v1 from the frozen raw workbook and require byte-identical derived files;
- verify the source and derived SHA-256 hashes in the manifest;
- prevent active verifier code from importing human-gold/evaluation artifacts;
- prevent reintroduction of known retired cultural-heuristic identifiers;
- enforce the unlabeled, non-PLT shape of the ten smoke cases;
- verify that a `conflicting` final EvidenceMemo counts as evidence coverage without changing cultural scores in Python.

The human-gold PLT set remains evaluation-only and must not be used to repair semantic behavior before Verifier v1.0 is frozen.
