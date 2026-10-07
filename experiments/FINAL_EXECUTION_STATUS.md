# Final Experiment Execution Status

This file is the operational checkpoint for the final Bachelor-thesis experiment.
It does not redefine the frozen verifier semantics or datasets.

## Frozen inputs

| Block | Size | Status |
|---|---:|---|
| External cross-dataset validation | 120 | Existing corpus and prior Vericult results restored under `data/final/external_120/` |
| Red-team challenge set | 90 | Frozen under `data/final/vericult_redteam_90_final_selection.csv` |
| PLT Best-of-4 | 30 | Frozen under `data/evaluation/best_of4_v1.csv` |
| Total | 240 | Frozen package |

## What is already completed

### External 120
Existing empirical run is preserved in:
`data/final/external_120/results_final_merged.jsonl`

Completion:
- 116/120 completed
- 4 unresolved execution failures
- IDs: 028, 034, 076, 084

Do not rerun the 116 successful rows unless a separate sensitivity/reproduction run is explicitly requested.

### PLT 30
Input:
`data/evaluation/best_of4_v1.csv`

Human reference material already exists:
- `data/evaluation/human_annotations_raw.xlsx`
- `data/evaluation/human_gold_candidates.csv`
- `data/evaluation/human_gold_manifest.json`
- `data/evaluation/human_gold_summary.json`

Machine execution path already exists:
1. `scripts/preflight_final_experiment.py`
2. `scripts/run_final_experiment.py --mode LIVE`
3. `scripts/audit_final_evidence.py`
4. `scripts/run_final_experiment.py --mode REPLAY`
5. `src/baseline_rm.py`
6. `src/baseline_direct_judge.py`

### Red-team 90
Selection and provenance are frozen:
- `data/final/vericult_redteam_90_final_selection.csv`
- `data/final/vericult_redteam_90_freeze_manifest.txt`

No selection/reconstruction work should be repeated.

## Authoritative model/config freeze

Use:
- `experiments/final_manifest.json`
- `experiments/final_vericult_config.json`
- `experiments/backbone_freeze.json`

Do not use conversationally proposed replacement model names unless a new experiment configuration is intentionally created.

## Next execution tasks

1. Preserve the 116 completed external-120 results; rerun only the four failed external rows if needed.
2. Run the frozen PLT30 LIVE -> evidence freeze -> REPLAY pipeline.
3. Run Skywork and direct-LLM baselines on the same PLT30.
4. Join machine predictions with the already-built human gold only after machine outputs are persisted.
5. Run the red-team90 as a separate challenge evaluation once each source-addressed record is available to the runtime; do not alter the frozen selection.
6. Produce final comparison tables, coverage/abstention analysis, confidence intervals, and error analysis.

## Rule

Do not reconstruct or resample any of the three frozen blocks. Any execution fix must preserve the frozen prompt/response identities and must not use human labels for inference.
