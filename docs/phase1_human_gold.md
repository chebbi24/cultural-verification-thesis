# Phase 1 freeze: human reference data and verifier pre-evaluation gate

This phase is completed **before** the human-gold PLT001–PLT030 set is used to assess verifier performance. Its purpose is to freeze the reference data, protect the evaluation from tuning contamination, and establish software-level validity gates for the verifier.

## Frozen human reference

The source workbook is stored as `data/evaluation/human_annotations_raw.xlsx` and is immutable for Human Gold v1. Its SHA-256 digest is recorded in `human_gold_manifest.json`.

`python scripts/build_human_gold.py data/evaluation/human_annotations_raw.xlsx` deterministically derives:

- `human_gold_candidates.csv`: one row for each of the 120 PLT candidate responses, containing the mean and median 1–3 appropriateness rating, rating counts, normalized `[0,1]` human score, and Best-of-4 winner-vote count.
- `human_gold_prompts.csv`: one row per PLT with the A–D vote distribution, human top set, majority winner only when a unique candidate receives at least 3/5 votes, maximum vote count, and consensus category.
- `human_gold_summary.json`: aggregate annotation counts and winner Fleiss' kappa.
- `human_gold_manifest.json`: hashes of the immutable source and every derived output.

The normalized candidate score is a scale transformation only:

`human_score_normalized = (human_mean - 1) / 2`.

Consensus categories are fixed as:

- `strong_consensus`: a unique candidate receives 4/5 or 5/5 votes.
- `majority`: a unique candidate receives 3/5 votes.
- `ambiguous`: no unique candidate receives at least 3/5 votes.

Human Gold v1 contains 5 complete submissions, 30 prompts, 120 candidate responses, 600 candidate-level ratings, and 150 Best-of-4 votes. The observed winner Fleiss' kappa is 0.090494. Seventeen prompts have a unique >=3/5 human-majority winner, seven have strong consensus, and thirteen are ambiguous under the frozen rule.

No respondent/submission identifiers are copied into the derived gold tables. The original workbook is preserved only as the immutable source record.

## Contamination rule

The human-gold files are evaluation artifacts. `src/cultverify` must never load them, and human labels must never enter planner, target extraction, retrieval, evidence synthesis, comparison or scoring. Once Verifier v1.0 is frozen, PLT001–PLT030 may be run and joined with the human tables only after verifier outputs have been persisted.

## Structural verifier gate

Before the PLT gold run, the test suite must establish the software contracts of the frozen architecture: D01–D10 only, prompt-level plan reuse across Best-of-4 candidates, target and question budgets, structural candidate blindness during query/retrieval/evidence, bounded retrieval (`R_max=2`), citation integrity, benchmark leakage filtering, frozen evidence memos, equal aggregation, abstention and exact-tie behavior, replay without live retrieval, and complete trace links.

These tests establish implementation conformance; they do **not** establish cultural accuracy.

## Non-gold smoke cases

`data/dev/verifier_smoke_cases.json` contains ten development-only prompt/response pairs spanning diverse cultural situations. They have no human labels, winners, expected verifier scores or expected evidence verdicts. They are used only to inspect the pipeline trace before Verifier v1.0 is frozen.

The smoke cases must never be reported as evaluation data and must not be used to create benchmark-specific cultural rules.
