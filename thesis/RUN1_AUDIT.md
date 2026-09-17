# Run 1 - Authoritative Audit and Thesis Scaffold

## Scope

This run deliberately does **not** attempt the full thesis. It establishes a clean project, records what is verified from the current implementation, and separates unresolved empirical work from implemented behaviour.

## Verified implementation facts

Authoritative code base: `chebbi24/cultural-verification-thesis`, branch `agent/final-verifier`.

- Pipeline version is `cultverify-1.0.0`.
- The verifier accepts one prompt and one response, and Best-of-4 requires exactly four responses.
- Best-of-4 reuses one prompt-level context and dimension plan across all four candidates.
- The verifier uses one identical semantic-model configuration across stages.
- Default temperature is 0; maximum material targets is 3; maximum retrieval rounds is 2; default `top_k` is 3.
- LIVE and REPLAY are explicit modes.
- The thesis repository itself and known annotation/result paths are excluded from retrieval by default.
- Evidence processing begins from exactly two neutral question objects and the validated context object.
- The evidence engine creates a fresh semantic session and has no candidate/target argument in its public `evaluate` interface.
- A candidate target is reintroduced only after the final evidence memo has been created; the memo hash is checked before/after comparison.
- Dimension scores are 0/1/2 or abstain.
- Aggregation is an equal mean over non-abstained dimensions, normalized by 2.
- Best-of-4 uses exact rational comparison. Exact ties return `no_clear_winner`.
- `coverage_comparable` is diagnostic only; it does not override the highest-score rule.
- The independent Skywork reward-model baseline is separate from `cultverify`.

## Important discrepancy found before the final experiment

The current `src/baseline_rm.py` uses Python's `max(scores, key=scores.get)` over scores inserted in A/B/C/D order. Therefore an exact reward-score tie is broken by first occurrence rather than being represented as `no_clear_winner`.

This is not consistent with the verifier's explicit exact-tie rule and should be corrected or explicitly frozen/documented before the final comparative experiment. Do not retrospectively alter results after seeing the final human labels.

## Claims not yet established

The current software design does **not** by itself establish:

- superior cultural accuracy,
- superior agreement with humans,
- elimination of evaluator bias,
- validity of D01--D10 as a universally correct cultural taxonomy,
- empirical superiority to CARB,
- final model suitability,
- generalization across cultures, languages, or user populations.

These require the final held-out human-grounded evaluation and careful statistical analysis.

## Run partition for the remaining work

1. **Run 1 - completed:** authoritative code audit + clean LaTeX scaffold + TODO registry + build check.
2. **Run 2:** literature inventory and verified bibliography/source-to-claim map only.
3. **Run 3:** write Background and Related Work (Chapters 2--3) only.
4. **Run 4:** write the D01--D10 operational framework (Chapter 4) only.
5. **Run 5:** write the verifier methodology from code (Chapter 5) only.
6. **Run 6:** write/freeze experimental protocol and baseline semantics (Chapter 6) only.
7. **Run 7:** build figures, tables, appendices, and reproducibility material only.
8. **Run 8:** after real experiment outputs exist, populate Comparative Results (Chapter 7) only.
9. **Run 9:** trace-backed error analysis, discussion, and validity (Chapters 8--9) only.
10. **Run 10:** Introduction, Conclusion, abstract, global consistency audit, page balancing and final compilation.

Each run should persist its files before the next run starts.
