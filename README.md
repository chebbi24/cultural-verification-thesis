# Cultural Verification Thesis

## Primary research comparison

The proposed cultural verifier is evaluated **independently** against reward-model and CARB baselines on the same Best-of-4 candidate sets. Reward-model scores are never inputs to the verifier, and the hybrid is not part of the primary research claim.

## Standalone verifier pipeline

```text
prompt + optional frozen domain_id
-> prompt-only D01-D10 applicability plan
-> candidate response
-> decision-relevant evidence targets linked to active dimensions
-> web evidence and claim verdicts
-> applicable cultural-dimension scores
-> independent severe hard-failure eligibility check
-> confidence / abstention
-> standalone verifier score and Best-of-4 winner
```

The verifier and benchmark now share one literature-derived ontology:

1. D01 Everyday life and material culture
2. D02 Language, discourse and pragmatics
3. D03 Social etiquette and interpersonal norms
4. D04 Values, ethics and moral pluralism
5. D05 Law, policy and institutional rules
6. D06 Religion, ritual and taboo
7. D07 Family, kinship, gender and generations
8. D08 Work, education and civic participation
9. D09 Cultural heritage, history, arts and collective memory
10. D10 Identity, diversity and intergroup relations

Every prompt receives one primary and at most two secondary dimensions. Each applicable dimension is scored `0`, `1`, or `2`; irrelevant dimensions are explicitly `N/A`. The final score is the equal-weight normalized mean over applicable, scorable dimensions:

```text
VerifierScore = sum(applicable dimension scores) / (2 * number scored)
```

Evidence is a basis for the affected dimension scores, not an additional arbitrary percentage. A directly contradicted linked claim caps that dimension at `1`. `not_enough_evidence` is not contradiction. If no applicable dimension can be assessed, the verifier abstains.

Hard failures are a separate eligibility gate, not a score on D01-D10. Only a direct, registered HF1-HF6 non-compensatory violation makes `eligible=false`; the `0` score is retained only for output compatibility. If all candidates are ineligible or abstain, the verifier abstains rather than selecting a tied zero-score response. See `docs/hard_failure_protocol.md`.

The complete rubric, scoring anchors, CARB mappings, and literature source families are stored in `data/csv/cultural_dimension_rubric.csv`.

## Setup

```bash
python -m pip install -r src/requirements.txt
```

Local Ollama judge with Tavily retrieval (default):

```bash
ollama pull qwen3:4b
export TAVILY_API_KEY="..."
python src/check_verifier_setup.py \
  --backend ollama \
  --model qwen3:4b \
  --search-provider tavily \
  --search-depth basic
```

Tavily Search retrieves and relevance-ranks evidence; it does not score cultural
correctness. Tavily publicly identifies its ranking technology only as
proprietary AI, without a named or versioned model. The judging model remains
the explicitly recorded local `qwen3:4b`. The default `basic` search depth,
returned URLs, snippets, and relevance scores are preserved for auditability.

Every Ollama judge call receives an enforced JSON Schema rather than only a
prompt example. If a local model returns valid JSON with the wrong fields, the
verifier makes one repair attempt and then fails explicitly. It never invents
missing dimensions, evidence verdicts, or scores.

Dimension scoring and hard-failure detection are separate model calls. The
hard-failure contract requires an explicit boolean and an empty list when no
violation occurs. A semantic validator checks boolean/list consistency,
duplicate categories, and exact quoted trigger spans; it allows one targeted
repair and then aborts. Negative checklist entries such as "HF2 did not occur"
can therefore never zero a candidate. Evidence planning also drops
response-internal observations and targets without an exact response quotation,
so Tavily is used only for external, decision-relevant factual claims.

Optional legacy OpenRouter backend:

```bash
export OPENROUTER_API_KEY="..."
export OPENROUTER_MODEL="openai/gpt-4.1-mini"
export OPENROUTER_WEB_ENGINE="exa"  # optional; explicit default
python src/check_verifier_setup.py \
  --backend openrouter \
  --search-provider same
```

OpenRouter can run the entire verifier with `--backend openrouter`, or it can replace only the failed Ollama hosted-search stage while local Qwen remains the judge. Evidence calls use OpenRouter's current `plugins: [{"id": "web"}]` contract and preserve standardized URL-citation annotations. Web retrieval consumes OpenRouter credits even when the selected model is free.

## Single-response smoke test

Input CSV requires `prompt,response`; `prompt_id` and `domain_id` are optional.

```bash
python src/run_verifier.py \
  data/test.csv \
  data/outputs/test_verifier.json \
  --backend ollama \
  --search-provider tavily \
  --search-depth basic \
  --limit 1
```

## Main Best-of-4 verifier experiment

Input columns:

```text
set_id,prompt_id,domain_id,prompt,response_a,response_b,response_c,response_d,human_chosen
```

`domain_id` and `human_chosen` are optional during development. Human labels are read only after all candidates are scored.

```bash
python src/evaluate_best_of4.py \
  data/best_of4.csv \
  data/outputs/verifier_best_of4.csv \
  --backend ollama \
  --model qwen3:4b \
  --search-provider tavily \
  --search-depth basic \
  --target-context Germany \
  --limit 1
```

Outputs:

- `verifier_best_of4.csv`: winner, candidate scores, tie and abstention status
- `verifier_best_of4.details.json`: applicable dimensions, all ten score records, evidence targets, sources, verdicts, confidence and hard-failure diagnostics

## Hard-failure validation

Annotate the candidate rows using `data/annotations/hard_failure_validation_template.csv`, then evaluate the verifier eligibility gate against the independent labels:

```bash
python src/evaluate_hard_failures.py \
  data/outputs/verifier_best_of4.details.json \
  data/annotations/hard_failure_annotations.csv \
  data/outputs/hard_failure_metrics.json
```

This reports hard-failure precision, recall, false-positive rate, and the full confusion matrix. The detailed protocol and registry are in `docs/hard_failure_protocol.md` and `src/hard_failures.py`.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests

# Optional: real local-Qwen structured-output smoke test (no web search)
RUN_OLLAMA_INTEGRATION=1 python -m unittest tests.test_ollama_integration -v
```

## Independent reward-model baseline

```bash
python src/baseline_rm.py \
  data/best_of4.csv \
  data/outputs/skywork_best_of4.csv \
  --limit 1
```

Compare human-winner selection accuracy, confidence intervals, per-dimension performance, and abstention coverage on the same frozen candidate sets.
