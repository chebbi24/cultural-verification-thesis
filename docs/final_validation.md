# Final repository validation — Vericult 1.1

Validation target: experiment-ready branch after the Vericult 1.1 selective-decision
implementation and final experiment harness were added.

CI validation on commit `ead68f06572b1a7db0e36a76006f465c405eb618`
(GitHub Actions run `36738629175`) used Python 3.12 and the repository
`requirements.lock`.

Results:

- Compile: `python -m compileall -q src scripts tests` — passed.
- Unit/integration suite: **130 passed, 1 skipped**.
- Ruff lint: `ruff check src scripts tests` — passed.
- Ruff formatting: `ruff format --check src scripts tests` — passed; 34 files formatted.
- The single skipped test is the explicitly gated real-provider LIVE → REPLAY smoke
  test. CI intentionally does not possess Ollama/Tavily credentials.

The passing suite covers the pre-existing verifier architecture plus the Vericult 1.1
decision layer and final-experiment guards: score-0 candidate rejection,
`no_acceptable_candidate`, `insufficient_evidence`, exact eligible ties without a
primary-dimension tie-break, direct-judge deterministic candidate permutation,
canonical PLT input validation, resume behavior, runtime-manifest validation,
evidence-manifest mutation detection, and inference-runner isolation from Human Gold.

## Required local provider gate

Before the final PLT LIVE acquisition, run the credential-gated provider test on the
frozen checkout:

```bash
CULTVERIFY_RUN_LIVE=1 python -m pytest -q -m live
```

This must pass with the final local `qwen3:4b` Ollama installation and Tavily key.
Then run `scripts/preflight_final_experiment.py` to capture the exact Ollama model
digest and runtime versions. No PLT item is used by the provider smoke test.

Software validation establishes implementation conformance and reproducibility
guards; it does not establish cultural accuracy or empirical superiority.
