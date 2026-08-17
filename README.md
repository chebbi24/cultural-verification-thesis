# Cultural Verification Thesis

## Primary research comparison

The proposed cultural verifier is evaluated **independently** against reward-model baselines. Reward-model scores are never inputs to the verifier.

### Standalone verifier pipeline

`prompt + candidate response + target context`
→ atomic verifiable claim extraction
→ OpenRouter `openrouter:web_search` evidence search
→ claim verification
→ cultural rubric
→ equal-weight verifier score
→ Best-of-4 winner

The five equal-weight dimensions are:

1. evidence grounding
2. contextual appropriateness
3. non-essentialism
4. variation and uncertainty
5. actionable helpfulness

Hard failures are logged for interpretability but do not receive an additional hidden numeric penalty.

## Setup

```bash
cd src
pip install -r requirements.txt
export OPENROUTER_API_KEY="..."
# Optional; defaults to openai/gpt-4.1-mini
export OPENROUTER_MODEL="openai/gpt-4.1-mini"
```

## Quick smoke test: one or more prompt/response rows

Input CSV columns: `prompt,response` (optional `prompt_id`).

```bash
python src/run_verifier.py data/test.csv data/outputs/test_verifier.json --limit 1
```

## Main Best-of-4 verifier experiment

Input columns:

`set_id,prompt_id,prompt,response_a,response_b,response_c,response_d,human_chosen`

`human_chosen` is optional while developing. It is read **only after** the four candidates have been scored.

```bash
python src/evaluate_best_of4.py \
  data/best_of4.csv \
  data/outputs/verifier_best_of4.csv \
  --target-context Germany \
  --limit 1
```

Outputs:

- `verifier_best_of4.csv`: winner and candidate scores
- `verifier_best_of4.details.json`: claims, web evidence, verdicts, dimension scores and hard-failure diagnostics

## Independent reward-model baseline

```bash
python src/baseline_rm.py \
  data/best_of4.csv \
  data/outputs/skywork_best_of4.csv \
  --limit 1
```

Compare `best_of_4_accuracy` from the standalone verifier and RM on the same labelled candidate sets. The hybrid approach is intentionally not part of the primary experiment.
