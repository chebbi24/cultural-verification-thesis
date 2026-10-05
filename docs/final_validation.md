# Post-fix repository validation — Vericult cultural-120 semantics

Validation target: commit `c1944bb1df47a8668689c316e62563bdc700fbf3` on
`fix/cultural120-result-semantics`, after the positive-set reliability and
selective-outcome fixes.

GitHub Actions run `37336670390` used Python 3.12 and the repository
`requirements.lock`.

Results:

- Compile: `python -m compileall -q src scripts tests` — passed.
- Unit/integration suite: **141 passed, 1 skipped**.
- Ruff lint: `ruff check src scripts tests` — passed.
- Ruff formatting: `ruff format --check src scripts tests` — passed; **36 files already formatted**.
- The skipped test is the explicitly gated real-provider LIVE → REPLAY smoke test;
  CI intentionally does not possess local Ollama/Tavily credentials.

The passing suite now covers the prior verifier architecture plus the repaired
score validation and expanded selective-result semantics:

- exact-rational validation of `overall_score` and `vericult_score`;
- suppression of the public 0–100 summary when any applicable dimension abstains;
- decisive score-0 findings remaining `culturally_inappropriate` despite partial abstention;
- explicit `not_culturally_applicable` gating before D01–D10 planning;
- explicit `not_assessable` handling for pure refusals/non-answers;
- simplified target selection with Python-owned exact quotes and retrieval routing;
- per-dimension structural recovery if batch dimension scoring is invalid;
- selective contextual fallback only for evidence-unresolved
  `context_dependent_recommendation` targets;
- unresolved external facts/descriptive norms retaining the ability to abstain as
  `insufficient_evidence`;
- the expanded Best-of-4/direct-judge decision space;
- existing evidence blindness, provenance, grounding, replay and trace invariants.

## Required provider/evaluation rerun

Software validation establishes implementation conformance; it does **not** replace
empirical execution with the final local model and retrieval provider.

Before using the repaired results in the thesis:

1. run the credential-gated LIVE → REPLAY provider smoke test;
2. rerun the same frozen positive 120-item external set without replacing difficult cases;
3. classify transport timeouts separately from semantic outcomes;
4. run the planned red-team/inappropriate-response set;
5. only then freeze the definitive code/config/runtime manifest used for Chapter 7.

The existing `experiments/final_manifest.json` predates these semantic fixes and
must not be presented as the freeze manifest for this repaired verifier. Refreeze it
only after the repaired empirical runs are accepted.
