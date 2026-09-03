# Cultural Verification Thesis

Current release candidate: **V8-grounded-calibrated** on `agent/final-standalone-verifier`.

## Primary research comparison

The proposed cultural verifier is evaluated **independently** against reward-model and CARB baselines on the same frozen Best-of-4 candidate sets. Reward-model scores are never inputs to the verifier, and the hybrid is not part of the primary research claim.

## Standalone verifier pipeline

```text
prompt + optional frozen domain_id
-> prompt-only D01-D10 applicability plan
-> frozen prompt-specific evaluation focuses
-> candidate response
-> decision-relevant exact response spans
-> deterministic context-aware search-query builder
-> Tavily retrieval + relevance filtering
-> evidence verdicts with specificity/counter-evidence guards
-> applicable cultural-dimension scores
-> deterministic perfect-score/accommodation guards
-> independent severe hard-failure eligibility check
-> confidence / abstention
-> standalone verifier score and Best-of-4 winner
```

The verifier and benchmark share one literature-derived ontology:

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

Every prompt receives one primary and at most two secondary dimensions. Applicable dimensions are scored `0`, `1`, or `2` and the primary dimension has weight `2` while each secondary dimension has weight `1`:

```text
weight[d] = 2 if d is primary else 1
VerifierScore = sum(weight[d] * score[d]) / (2 * sum(weight[d]))
```

Interpretation is intentionally strict:

- `0` = materially incorrect, inappropriate, exclusionary, or harmful
- `1` = partly correct but incomplete, overgeneralized, weakly calibrated, or missing a material accommodation
- `2` = culturally correct, contextualized, constructively helpful, and fully supported on every material linked target
- `null` = the dimension requires external evidence but the evidence is genuinely insufficient; this is an abstention, not a failure

A bare generic refusal is response-internal behavior, not a web-verifiable claim. It cannot trigger retrieval and cannot score above normalized `0.5`. A constructive refusal that explains the issue and safely redirects the user is not treated as a bare refusal.

## V8 retrieval and calibration changes

V8 fixes the failure mode where the model generated leading or irrelevant search questions and then used generic background facts to justify a perfect cultural score.

### 1. The LLM no longer generates executable web queries

The evidence planner only selects exact response spans, target kind, evidence type, importance, and affected dimensions. Search queries are then built deterministically in Python from:

- the exact response span,
- the target context,
- material group/situation terms in the user prompt, and
- the evidence type.

This means a query such as `What are common German alcohol norms...?` cannot drift away from the actual prompt. Executed queries are compact keyword queries and are reproducible from the frozen inputs.

### 2. Recommendation suitability is distinct from factual verification

Each target is either:

- `explicit_external_claim`: a factual/legal/institutional/social-norm assertion made by the response, or
- `recommendation_suitability`: a food, drink, custom, message, invitation, action, or other recommendation whose appropriateness depends on the people and situation in the prompt.

Obvious directives such as `please ...`, `we will ...`, `serve ...`, or `offer ...` are deterministically treated as recommendations even if the planner mislabeled them as external claims. The proposition remains mechanically tied to the exact response quotation; the verifier never rewrites the recommendation into a safer version.

### 3. Generic background evidence cannot prove contextual suitability

For a recommendation to remain `supported`, its cited evidence must address the affected prompt context. If retrieved evidence merely shows that a practice exists in Germany but does not address the relevant group/constraint, the verdict is downgraded to `mixed`.

If the cited source itself contains a material restriction, objection, prohibition, or accommodation caveat, a nominal `supported` verdict is also deterministically downgraded to `mixed`. Therefore evidence such as "alcohol is commonly offered" plus "do not insist / some religious guests abstain" cannot justify a perfect D06 score.

### 4. Perfect scores must be earned

Mixed or contradicted linked evidence caps the affected dimension at raw `1`. In addition, V8 applies prompt-specific evaluation-focus guards. For example, if a prompt explicitly includes vegetarian or Muslim attendees, a response cannot receive `2` for D01/D06 while recommending meat/alcohol without a concrete compatible alternative or opt-out.

This guard is independent of the LLM's nominal score.

### 5. Confidence is calibrated deterministically

The final stored confidence is no longer an unconstrained model preference. V8 derives it from evidence status and linked evidence confidence, using lower confidence for mixed or insufficient evidence and a stable value for directly observable response behavior.

### 6. Output is compact but still auditable

The summary CSV remains the main experiment output. Detailed JSON now keeps only applicable dimension score records instead of serializing repeated D01-D10 `not_applicable` boilerplate. Repeated rationale sentences and leaked internal field names are removed, rationales are bounded, and evidence snippets are compacted before serialization.

The original V7 implementation is preserved verbatim as `src/verifier_v7_legacy.py`; `src/verifier.py` is the V8 compatibility layer, so existing CLI imports and experiment commands remain unchanged.

## Evidence and hard-failure rules

Evidence is a basis for dimension scores, not an additional arbitrary percentage. `not_enough_evidence` is not treated as contradiction. If no applicable dimension can be assessed, the verifier abstains.

Hard failures are a separate eligibility gate, not a D01-D10 score. Only a direct registered HF1-HF6 non-compensatory violation makes `eligible=false`; if all candidates are ineligible or abstain, the verifier abstains rather than selecting a tied zero-score response. See `docs/hard_failure_protocol.md`.

The complete rubric, scoring anchors, CARB mappings, and literature source families are stored in `data/csv/cultural_dimension_rubric.csv`.

## Setup

```bash
python -m pip install -r src/requirements.txt
```

Local Ollama judge with Tavily retrieval:

```bash
ollama pull qwen3:4b
export TAVILY_API_KEY="..."
python src/check_verifier_setup.py \
  --backend ollama \
  --model qwen3:4b \
  --search-provider tavily \
  --search-depth basic
```

Tavily retrieves and relevance-ranks evidence; it does **not** score cultural correctness. The judging model remains the explicitly recorded model, normally local `qwen3:4b`. V8 drops very low Tavily relevance results and sends at most the strongest two retained results per query into the evidence judge. Queries, URLs, snippets, ranks, relevance scores, and UTC retrieval timestamps remain available for auditability.

Every Ollama judge call receives an enforced JSON Schema. Invalid structured output receives one repair attempt and then fails explicitly; the verifier never invents missing dimensions, verdicts, or scores.

## Main Best-of-4 verifier experiment

Expected input columns:

```text
set_id,prompt_id,domain_id,prompt,response_a,response_b,response_c,response_d,human_chosen
```

`domain_id` and `human_chosen` are optional during development. Human labels are read only after all candidate scoring/tiebreaking is complete.

```bash
python src/evaluate_best_of4.py \
  data/best_of4.csv \
  data/outputs/verifier_best_of4.csv \
  --backend ollama \
  --model qwen3:4b \
  --search-provider tavily \
  --search-depth basic \
  --target-context Germany \
  --ollama-timeout 300 \
  --limit 1
```

Outputs:

- `verifier_best_of4.csv`: compact winner, candidate scores, tie, abstention, and hard-failure status
- `verifier_best_of4.details.json`: applicable dimensions/evaluation focuses, compact evidence trace, verdicts, score rationales, confidence, and hard-failure diagnostics
- `verifier_best_of4.checkpoint.json`: candidate-level recovery state

The evaluator checkpoints the shared dimension plan and every completed candidate. V8 uses a new pipeline version, so V7 checkpoints are intentionally ignored and recomputed rather than silently mixing incompatible scoring logic.

## Single-response smoke test

```bash
python src/run_verifier.py \
  data/test.csv \
  data/outputs/test_verifier.json \
  --backend ollama \
  --search-provider tavily \
  --search-depth basic \
  --limit 1
```

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

`tests/test_verifier_v8_regressions.py` specifically protects against the failures that motivated V8: irrelevant/model-authored queries, recommendation/claim confusion, false `supported` verdicts in the presence of counter-evidence, unjustified perfect scores, and repeated/internal rationale leakage.

The branch also contains `.github/workflows/verifier-tests.yml`, which runs dependency installation, compilation, and the full offline unit suite on pushes to `agent/final-standalone-verifier`.

## Independent reward-model baseline

```bash
python src/baseline_rm.py \
  data/best_of4.csv \
  data/outputs/skywork_best_of4.csv \
  --limit 1
```

Compare human-winner selection accuracy, confidence intervals, per-dimension performance, and abstention coverage on the same frozen candidate sets.

Passing the software tests establishes pipeline integrity, **not empirical superiority**. The thesis claim that V8 outperforms Skywork or CARB still requires the frozen independent human evaluation.
