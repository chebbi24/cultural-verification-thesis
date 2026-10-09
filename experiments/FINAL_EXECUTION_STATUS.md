# Final Experiment Execution Status

This is an operational overview. The machine-readable authority is
`experiments/final_manifest.json` and `experiments/final_vericult_config.json`.

## Active final experiment: 360 independent prompt–response pairs

| Corpus | Items | Role |
|---|---:|---|
| PLT120 | 120 | Custom challenge set, including PLT001–PLT030 development-origin cases |
| External120 | 120 | External multicultural evaluation cases |
| Redteam120 | 120 | Externally grounded cultural challenge cases |
| **Total** | **360** | One frozen GPT-OSS response per prompt |

Generator: `gpt-oss:120b-mxfp4`, temperature 0.8, top-p 0.95,
maximum 1,200 completion tokens.

Verifier: standalone Vericult 1.1 with L3S `vllm/qwen3.6:35b-a3b-fp8`,
temperature 0. RM and direct-judge outputs do not enter the verifier.

## Latest development-origin LIVE diagnostics

- PLT001: provider `ReadTimeout` in `dimension_planner_v1`; not a cultural judgment.
- PLT002: completed, three dimensions scored 2, culturally appropriate.
- PLT003: completed, D01=2 and D08=abstain; correctly reports
  `insufficient_evidence` with public score null.

These are smoke diagnostics, **not** proof that the final 360-case LIVE run
has completed. Preserve their traces separately from the official execution.

## Final execution order

1. Check out the approved frozen code revision and clean working tree.
2. Run tests and credential-gated smoke checks.
3. Run `python scripts/preflight_final_experiment.py` to create the matching
   execution identity and runtime manifest.
4. Run `python scripts/run_final_experiment.py --mode LIVE`; only valid
   completed records of the same execution identity are skipped on resume.
5. Retry technical failures with unchanged semantic settings.
6. Run `python scripts/audit_final_evidence.py`, then
   `python scripts/run_final_experiment.py --mode REPLAY`.
7. Run independent single-response baselines and analyze results.

Do not mix completed outputs from old and new freezes. Keep the entire
`artifacts/` directory and the JSONL checkpoints in the thesis archive.

Legacy Best-of-4, PLT30 human annotations, external 120 historical runs, and
the earlier 90-record challenge selection remain **development provenance**,
not the frozen 360-pair final machine evaluation.
