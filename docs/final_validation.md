# Final repository validation — Vericult 1.1 launch-safety freeze

## Authoritative semantic revision

- Freeze code commit: `e451ff40b50bf1a91a30175c1885d1660a87e51c`
- GitHub Actions "Verifier tests": run `37713891461`, **success**
- Python 3.12: **159 tests passed, 1 skipped**
- Compile, Ruff lint and Ruff format: **passed**
- Manifest: `experiments/final_manifest.json`; config:
  `experiments/final_vericult_config.json`

Only the manifest and this metadata validation note may be changed after the
above semantic freeze without establishing a new revision.

## Verified semantic corrections

- An applicable cultural prompt cannot silently produce an empty dimension plan.
  Invalid structured planning is retried once, then fails as a technical problem.
- Scored 2 together with an abstention means `insufficient_evidence`,
  **not** `partially_culturally_appropriate`. The public score remains null.
  A material score-0 finding remains culturally inappropriate.
- Final trace validation is synchronized with those same labels.
- PLT002 LIVE completed with D01/D02/D03=2.
- PLT003 LIVE completed with D01=2 and D08=abstain and now validates correctly.
- PLT001 LIVE still fails at L3S `dimension_planner_v1: transport ReadTimeout`;
  the cause is not established. No case-specific heuristic or model change was introduced.

## Launch-safety and evidence fixes

- Every output record carries a deterministic execution ID from the frozen code,
  verifier model/config and semantic dataset hashes.
- Resume skips only the latest valid completed record with matching execution ID,
  prompt and response hashes, and an intact matching trace.
- Unexpected per-item exceptions become failed checkpoints so later items proceed;
  keyboard interrupts and system exits are not swallowed.
- A torn final JSONL line is backed up and removed without discarding valid records.
  Earlier checkpoint corruption remains a hard failure.
- The evidence auditor reads the manifest's actual `semantic_sha256` fields,
  verifies LIVE record identity and prompt/response traces, and freezes hashes.
- REPLAY checks its evidence execution identity and the frozen LIVE output hash.
- Preflight and the runner reject silent model, provider or L3S endpoint changes.
- Direct invocation of `python scripts/preflight_final_experiment.py` imports both frozen-model validation and execution-identity helpers, including the script-mode fallback. A regression subprocess test forces that import path.

## Required local steps before official LIVE

1. Use a clean checkout of the fix branch and run `python -m pytest -q`.
2. Archive previous experimental artifacts (results, traces, cached evidence,
   runtime/evidence manifests) separately. Do not combine old experimental freezes.
3. Run `python scripts/preflight_final_experiment.py`, which checks all 360
   generated pairs and captures the runtime identity.
4. Run `python scripts/run_final_experiment.py --mode LIVE`.
5. Rerun the same command to retry only failed/unresolved items. Then run the
   evidence audit and REPLAY.

The remote L3S identifier is recorded as a model identity string, not an
independently verified immutable weights digest. CI uses deterministic fixtures;
provider reliability and cultural accuracy remain empirical evaluation concerns.
