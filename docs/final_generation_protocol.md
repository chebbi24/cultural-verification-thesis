# Final response-generation protocol

## Frozen generator

- Provider: L3S OpenAI-compatible inference endpoint
- Model: `gpt-oss:120b-mxfp4`
- Candidates per prompt: 4 independent calls (A-D)
- Temperature: 0.8
- Top-p: 0.95
- Max generated tokens per call: 1200
- System prompt: none
- Prompt transformation: none; the source prompt is sent verbatim

The generator is deliberately separate from the Qwen3.6-based Vericult verifier.
The objective is a strong, reproducible candidate source rather than a claim that
GPT-OSS 120B is the globally strongest available model.

## Inputs

The runner supports the three frozen prompt pools (270 prompts total):

1. `plt30`: 30 prompts from `data/evaluation/best_of4_v1.csv`
2. `external120`: 120 prompts parsed from
   `data/final/external_120/prompt_response_pairs_120.txt`
3. `redteam120`: 120 prompts from
   `data/final/vericult_redteam_120_prompts.csv`

Existing responses in those datasets are preserved and never overwritten.
Human-gold files are not read by the generator.

## Safety against incomplete inputs

Before sending any model request, the runner validates the complete requested
corpus. In particular, red-team rows whose prompt text is only source-addressed
and not locally materialized cause a hard preflight failure. The generator never
guesses, reconstructs, or substitutes missing prompt text.

## Commands

Validate input readiness without generating:

```bash
python scripts/generate_final_candidates.py --dry-run --corpus all
```

Small generator smoke test on three PLT prompts:

```bash
python scripts/generate_final_candidates.py --corpus plt30 --limit 3
```

Generate one full corpus:

```bash
python scripts/generate_final_candidates.py --corpus plt30
python scripts/generate_final_candidates.py --corpus external120
python scripts/generate_final_candidates.py --corpus redteam120
```

Generate every ready corpus in one run:

```bash
python scripts/generate_final_candidates.py --corpus all
```

The runner checkpoints after every candidate. Re-running the same command resumes
without regenerating completed candidates.

## Outputs

- `data/generated/gpt_oss_120b/plt30_generated_bestof4.csv`
- `data/generated/gpt_oss_120b/external120_generated_bestof4.csv`
- `data/generated/gpt_oss_120b/redteam120_generated_bestof4.csv`

Each output records the original prompt, response hashes, generation timestamps,
and API token usage per candidate. After generation, these CSVs must be hashed
and frozen before any Vericult evaluation begins.

## Important human-gold boundary

The existing PLT human annotations belong to the old frozen A-D responses in
`best_of4_v1.csv`. They must not be treated as labels for newly generated
GPT-OSS candidates. New GPT-OSS candidates require their own human evaluation if
human agreement is reported for that candidate set.
