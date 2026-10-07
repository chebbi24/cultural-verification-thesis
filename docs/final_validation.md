# Final repository validation — restored Vericult 1.1 thesis freeze

Frozen semantic/code revision: `286598d5eb642c3d632e7b756ccf1954fb922a13`.

GitHub Actions validation run: `37608290712` (**Verifier tests**, success) on Python 3.12.

This freeze restores the verifier semantics that had already been validated on
October 5 on branch `fix/cultural120-result-semantics` at
`c1944bb1df47a8668689c316e62563bdc700fbf3` (CI run `37336670390`), but were
never merged into `main`. Those semantics were used for the final failed-item rerun
of the 120-case cross-dataset experiment. The restoration was applied selectively
onto the cleaned thesis repository; retired challenge builders/datasets were not
reintroduced.

Validated gates:

- dependency installation from `requirements.lock` — passed;
- `python -m compileall -q src scripts tests` — passed;
- full `python -m pytest -q` unit/integration suite — passed;
- `ruff check src scripts tests` — passed;
- `ruff format --check src scripts tests` — passed;
- current repository-scope guards — passed.

## Restored final semantics

The frozen verifier now contains the full validated October 5 result semantics:

- prompt-level `cultural_applicability_v1` before D01–D10 planning;
- `not_culturally_applicable` when cultural reasoning is not materially required;
- `response_assessability_v1` for culturally applicable prompts;
- `not_assessable` for pure refusals/non-answers with no substantive assessable answer;
- deterministic response-span selection with Python-owned exact quotations;
- normalization of equivalent span IDs while retaining the exact-span invariant;
- deterministic retrieval routing from epistemic type;
- per-dimension structural recovery when batch scoring remains invalid after bounded retry;
- dimension outcomes 0, 1, 2 or `abstain`;
- `insufficient_evidence` only for culturally applicable, assessable responses with no defensible scored basis;
- selective `contextual_fallback_v1` only for unresolved context-dependent recommendations;
- unresolved external facts and descriptive cultural norms remaining eligible for abstention;
- public `vericult_score=null` whenever any applicable dimension abstains;
- a score-0 material cultural failure remaining `culturally_inappropriate` even with partial abstention;
- expanded Best-of-4/direct-judge outcomes including `not_culturally_applicable` and `not_assessable`.

These distinctions keep three different cases separate: the task is not materially
cultural, the response contains no assessable answer, or the task is cultural and
assessable but the verifier lacks sufficient evidence.

## Repository-scope cleanup

The earlier cleanup remains intact. Retired root-level cultural prompt exports,
historical model-output files, obsolete generators/runners, temporary retest logs,
and abandoned challenge artifacts are not restored to the active tree. The frozen
PLT input, Human Gold provenance, D01–D10 research assets, independent baselines,
smoke cases, experiment protocols/manifests, research documentation and
external-validation protocol remain tracked.

## Freeze metadata policy

`experiments/final_manifest.json` identifies the semantic/code revision above as
`freeze_code_commit`. Only the manifest itself and this validation document are
allowed to differ in the post-freeze metadata commit; the final experiment runner
rejects other tracked semantic changes relative to the frozen revision.

## Required local provider gate

CI does not have the local Ollama runtime or Tavily credentials. Before final LIVE
evidence acquisition, run on the frozen checkout:

```bash
CULTVERIFY_RUN_LIVE=1 python -m pytest -q -m live
python scripts/preflight_final_experiment.py
```

The provider gate must use the final local `qwen3:4b` installation and Tavily
credential. The preflight captures the exact Ollama digest and runtime versions in
`artifacts/final_experiment/runtime_manifest.json`.

Software validation establishes implementation conformance and reproducibility
guards; it does not by itself establish cultural accuracy or empirical superiority.
