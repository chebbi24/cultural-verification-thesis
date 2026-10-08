# Final experiment protocol — Vericult 1.1 single-response evaluation

This document freezes the execution protocol for the final thesis evaluation. The
unit of evaluation is one fixed prompt–response pair. Vericult does not select a
winner from multiple candidates in the final experiment.

## Frozen inputs

The final evaluation contains exactly **360 fixed prompt–response pairs**:

- **PLT120** — 120 custom cultural red-team prompts, including the original
  PLT001–PLT030 development prompts and PLT031–PLT120 challenge expansion.
- **External120** — 120 multicultural prompts sampled from six public datasets.
- **Redteam120** — 120 externally grounded red-team prompts.

Every final response is generated once with the same frozen generator:

- model: `gpt-oss:120b-mxfp4`
- temperature: `0.8`
- top-p: `0.95`
- maximum completion tokens: `1200`
- responses per prompt: `1`
- system prompt: none
- prompt transformation: none

The three generated CSV files, their SHA-256 hashes, the Vericult configuration
hash, and the semantic code freeze commit are recorded in
`experiments/final_manifest.json`.

The historical `data/evaluation/best_of4_v1.csv` remains development provenance.
Its old Llama-3.2 candidates and Human Gold annotations are **not** final responses
and are never loaded by final inference.

## Vericult input and outputs

For every item the final runner calls:

```python
verifier.verify(prompt, response)
```

It does not call the Best-of-4 ranking API.

The single-response outcome space is:

- `culturally_appropriate`
- `partially_culturally_appropriate`
- `culturally_inappropriate`
- `insufficient_evidence`
- `not_culturally_applicable`
- `not_assessable`

Applicable dimensions are scored 0/1/2/`abstain` under the frozen D01–D10 rubric.
A score of 0 denotes a material cultural misalignment. The public Vericult score is
null whenever any applicable dimension abstains; exact internal aggregation remains
available in the trace for diagnostics.

## Leakage controls

The final Vericult configuration excludes the thesis repository itself and the
released benchmark locations used to construct External120. In particular,
`huggingface.co` is excluded because five External120 source datasets are hosted
there, and the `UpstageAI/ThaiCLI_H6` GitHub repository is excluded for ThaiCLI.

These exclusions are applied before evidence synthesis. Human labels, source
answers, prior verifier outputs, reward-model outputs, and direct-judge outputs are
not available to Vericult.

The Redteam120 provenance sources are public evidence sources rather than released
benchmark answer repositories; they remain eligible evidence unless excluded by the
general path policy.

## Execution order

The order is fixed:

1. **Generated-input validation and runtime preflight**
   - require exactly 360 items;
   - verify canonical IDs and non-empty prompt/response fields;
   - verify prompt and response hashes stored in each generated CSV;
   - verify the same frozen GPT-OSS model/sampling settings for all three corpora;
   - verify the three frozen semantic SHA-256 hashes from the final manifest;
   - require Tavily and the frozen L3S verifier credentials;
   - record Python/package/runtime identity.

2. **LIVE evidence acquisition**
   - evaluate all 360 fixed prompt–response pairs;
   - use Qwen 3.6 as the Vericult backbone and Tavily for retrieval;
   - persist one trace per response and immutable evidence snapshots/schedules;
   - checkpoint each completed item so interrupted execution can resume.

3. **Evidence freeze audit**
   - require 360 completed LIVE records and exactly 360 response traces;
   - verify every referenced evidence snapshot exists;
   - hash the LIVE JSONL, all LIVE traces, and every evidence/schedule file into
     `artifacts/final_experiment/evidence_manifest.json`.

4. **REPLAY primary Vericult evaluation**
   - verify the evidence-manifest hashes;
   - reuse the frozen evidence with no live-retrieval fallback;
   - rerun all 360 responses;
   - report REPLAY as the primary Vericult result.

5. **Independent baselines**
   - direct LLM judge on the same fixed prompt–response pairs, with no retrieval;
   - Skywork reward-model scoring on the same fixed prompt–response pairs.
   These baselines never feed into Vericult.

6. **Analysis**
   - only after machine predictions are persisted, join any separately collected
     human reference labels;
   - compare results by corpus, appropriateness class, D01–D10 behavior,
     abstention/not-assessable rates, evidence coverage, and failure type.

## Resume and failure policy

`scripts/run_final_experiment.py` appends one JSONL record per item. A rerun skips
only item IDs already recorded as `completed` for the requested mode. A failed item
may be rerun only after an execution-only problem (provider outage, timeout, local
storage issue, etc.) is corrected with unchanged frozen semantics. For final
execution, resume requires matching the code/config/dataset/model execution ID,
the prompt and response hashes, and an intact completed trace. Unexpected
per-item exceptions produce failed checkpoints and do not terminate the batch.
A torn final JSONL line is backed up and removed before resuming; corruption
in an earlier record is a hard failure. Never use --no-resume against a
nonempty result file. Keep previous-version output as a separately archived run.

No prompt, generated response, rubric, model, target/search budget, leakage policy,
or decision rule may be tuned in response to final Vericult outcomes.

## Output locations

- Runtime manifest: `artifacts/final_experiment/runtime_manifest.json`
- LIVE summary: `artifacts/final_experiment/results/vericult_live.jsonl`
- LIVE traces: `artifacts/final_experiment/traces/live/`
- Frozen evidence: `artifacts/final_experiment/evidence/`
- Evidence freeze manifest: `artifacts/final_experiment/evidence_manifest.json`
- REPLAY summary: `artifacts/final_experiment/results/vericult_replay.jsonl`
- REPLAY traces: `artifacts/final_experiment/traces/replay/`

The `artifacts/` tree is intentionally ignored by Git. Preserve it separately as
part of the thesis reproducibility archive.

## Pre-run gate

Before final LIVE acquisition:

```bash
python -m pytest -q
ruff check src scripts tests
ruff format --check src scripts tests
CULTVERIFY_RUN_LIVE=1 python -m pytest -q -m live
python scripts/preflight_final_experiment.py
```

The credential-gated smoke test must use development smoke cases, not any of the
360 final prompt–response pairs.

## Post-fix execution identity

The final runner and preflight use the same SHA-256 execution identity covering
the frozen code commit, experiment, verifier model/provider/config, and three
semantic dataset hashes. The LIVE evidence audit requires matching input hashes,
execution identity, traces, and source files before evidence can be frozen.
REPLAY rejects a different evidence execution identity. A remote L3S model name
is recorded as an identity string, **not** a verified immutable weights digest.
