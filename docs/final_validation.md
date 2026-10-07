# Final repository validation — Vericult 1.1 thesis freeze

Frozen semantic/code revision: `200bca4575304795f491e76308d9be327ca269da`.

GitHub Actions validation run: `37602825309` (**Verifier tests**, success) on Python 3.12.

Validated gates:

- dependency installation from `requirements.lock` — passed;
- `python -m compileall -q src scripts tests` — passed;
- full `python -m pytest -q` unit/integration suite — passed;
- `ruff check src scripts tests` — passed;
- `ruff format --check src scripts tests` — passed.

The frozen code includes deterministic response-span grounding: the semantic model
selects supplied span IDs instead of reproducing candidate quotations, Python resolves
those IDs back to exact response substrings, and validation rejects unknown spans.
The corresponding deterministic-grounding regression tests are part of the passing
suite.

## Repository-scope cleanup

Before this freeze, retired thesis-development material was removed from the active
tree: abandoned root-level cultural prompt-set exports, historical red-team prompt
and model-output files, the old Ollama generation runner, the retired cultural-set
builder/workflow, a dead Best-of-4 conversion script, temporary retest logs, and the
development notebook. Repository guards now fail if these retired paths are
reintroduced.

The frozen PLT input, Human Gold provenance, D01–D10 research assets, independent
baselines, smoke cases, experiment protocol/manifests, research documentation and
external-validation protocol remain tracked.

## Freeze metadata policy

`experiments/final_manifest.json` identifies the semantic/code revision above as
`freeze_code_commit`. Only the manifest itself and this validation document are
allowed to differ in the post-freeze metadata commit; the final experiment runner
rejects any other tracked changes relative to the frozen code revision.

## Required local provider gate

CI does not have the local Ollama runtime or Tavily credentials. Before final LIVE
evidence acquisition, run on the frozen checkout:

```bash
CULTVERIFY_RUN_LIVE=1 python -m pytest -q -m live
python scripts/preflight_final_experiment.py
```

The provider gate must use the final local `qwen3:4b` installation and the Tavily
credential. The preflight captures the exact Ollama digest and runtime versions in
`artifacts/final_experiment/runtime_manifest.json`.

Software validation establishes implementation conformance and reproducibility
guards; it does not establish cultural accuracy or empirical superiority.
