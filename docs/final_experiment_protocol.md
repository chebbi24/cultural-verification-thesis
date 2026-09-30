# Final experiment protocol — Vericult 1.1

This document freezes the execution protocol before PLT001–PLT030 machine predictions
are produced. It is an execution contract, not a results document.

## Frozen inputs

- Canonical Best-of-4 input: `data/evaluation/best_of4_v1.csv`.
- 30 prompts, four candidates per prompt, fixed A–D order in the canonical file.
- Vericult configuration: `experiments/final_vericult_config.json`.
- Human reference: already frozen separately as Human Gold v1. Human-gold files are
  forbidden inputs to Vericult and both baselines.

The exact dataset/config hashes and frozen code commit are recorded in
`experiments/final_manifest.json`.

## Vericult 1.1 decision semantics

Dimension scoring remains 0/1/2/`abstain` with equal aggregation. The new
Best-of-4 decision layer does not change those scores.

Candidate labels:

- `culturally_appropriate`: every applicable dimension is scored 2 and none abstains.
- `partially_culturally_appropriate`: at least one dimension is scored and no
  dimension is 0, but the candidate is not fully 2/2 on every applicable dimension.
- `culturally_inappropriate`: at least one scored dimension is 0, whose frozen
  rubric meaning is material cultural misalignment.
- `insufficient_evidence`: no applicable dimension can be scored.

Best-of-4 outcomes:

1. If any candidate fails technically, return `no_clear_winner` and report the failure.
2. If any completed candidate is `insufficient_evidence`, return
   `insufficient_evidence`; the full comparison is unresolved.
3. Otherwise exclude `culturally_inappropriate` candidates from endorsement.
4. If no candidate remains eligible, return `no_acceptable_candidate`. Relative
   candidate scores remain available only for diagnosis.
5. Among eligible candidates, the unique highest exact aggregate wins.
6. An exact highest-score tie returns `no_clear_winner`. There is no
   primary-dimension tie-break and no tie margin.

This gate is derived from the pre-existing semantic meaning of dimension score 0;
it is not fitted to Human Gold or PLT outcomes.

## Execution order

The order is fixed:

1. **Runtime preflight** — verify the frozen checkout/dataset/config, require the
   Tavily credential, confirm the local `qwen3:4b` installation and record its
   Ollama digest plus Python/package versions.
2. **LIVE acquisition** — run all 30 Best-of-4 sets. LIVE may retrieve web evidence
   and stores immutable evidence snapshots/schedules.
3. **Evidence freeze audit** — require 30 completed prompt records and 120 candidate
   traces; hash the LIVE output, every candidate trace and every evidence/schedule
   file into `artifacts/final_experiment/evidence_manifest.json`.
4. **REPLAY primary Vericult evaluation** — verify the evidence-manifest hashes,
   reuse the frozen evidence without live retrieval, and rerun the semantic stages.
5. **Skywork reward-model baseline** — score the same 120 candidates independently.
6. **Direct Qwen judge baseline** — one no-retrieval Best-of-4 judgment using the
   same D01–D10 rubric and selective decision space. Candidate presentation is
   deterministically permuted with seed `20260930` and mapped back to canonical A–D.
7. **Only after all predictions are persisted**, join them to Human Gold for analysis.

REPLAY is the primary reported Vericult result. LIVE exists to acquire and freeze
external evidence and is not substituted for the primary REPLAY result.

## Resume and failure policy

`scripts/run_final_experiment.py` checkpoints one JSONL record per prompt. A rerun
skips only prompt IDs already recorded as `completed` for the same mode. Failed
prompt records do not become results: after correcting an execution-only problem
(provider outage, local model process, disk issue), rerun with the unchanged frozen
code/config so the failed prompt is appended again and completed.

No semantic prompt, rubric, decision rule, model, target/search budget, source
exclusion policy or candidate data may be changed after the freeze in response to
final PLT results. Any unavoidable execution-only deviation must be documented.

## Output locations

- Runtime manifest: `artifacts/final_experiment/runtime_manifest.json`
- LIVE summary: `artifacts/final_experiment/results/vericult_live.jsonl`
- LIVE traces: `artifacts/final_experiment/traces/live/`
- Frozen evidence: `artifacts/final_experiment/evidence/`
- Evidence freeze manifest: `artifacts/final_experiment/evidence_manifest.json`
- REPLAY summary: `artifacts/final_experiment/results/vericult_replay.jsonl`
- REPLAY traces: `artifacts/final_experiment/traces/replay/`
- Skywork: `artifacts/final_experiment/results/skywork.csv`
- Direct judge: `artifacts/final_experiment/results/direct_judge.csv`

The `artifacts/` tree is intentionally ignored by Git. Preserve it as part of the
thesis reproducibility archive after the experiment.

## Pre-run gate

Before LIVE:

```bash
python -m pytest -q
ruff check src scripts tests
ruff format --check src scripts tests
CULTVERIFY_RUN_LIVE=1 python -m pytest -q -m live
python scripts/preflight_final_experiment.py
```

The credential-gated smoke test is development-only and must not use PLT001–PLT030.
The final experiment begins only after these checks pass on the frozen checkout.
