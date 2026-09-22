# Phase 2: smoke trace audit and Verifier v1.0 freeze gate

Phase 2 is the final pre-evaluation gate before the human-gold PLT001–PLT030 set is used. It runs only the development-only smoke cases from `data/dev/verifier_smoke_cases.json` and inspects their traces for architectural behavior.

## Inputs

- Branch: `agent/clean-standalone-verifier`
- Cases: `data/dev/verifier_smoke_cases.json`
- Config template: `configs/verifier_v1.example.json`
- Runner: `scripts/run_smoke_cases.py`

The smoke cases are unlabeled. They contain no expected score, winner, verdict, PLT ID or human annotation. They are not benchmark data and must not be reported as evaluation results.

## Local run

```bash
git fetch origin
git switch agent/clean-standalone-verifier
git pull
python -m pip install -e '.[test]'
pytest -q

export CULTVERIFY_PROVIDER=openrouter
export CULTVERIFY_MODEL='provider/model-version-to-freeze'
export OPENROUTER_API_KEY='...'
export TAVILY_API_KEY='...'
export CULTVERIFY_MODE=LIVE

python scripts/run_smoke_cases.py \
  --cases data/dev/verifier_smoke_cases.json \
  --output-dir results/dev_smoke \
  --cache-directory artifacts/evidence/verifier_v1_smoke \
  --trace-directory artifacts/traces/verifier_v1_smoke
```

For Ollama, set `CULTVERIFY_PROVIDER=ollama`, a local model ID, and `OLLAMA_URL` instead of the OpenRouter key. Tavily is still required for LIVE retrieval.

## Outputs

`results/dev_smoke/smoke_results.csv` contains one row per smoke case with status, score, abstention, evidence coverage, target count and trace path.

`results/dev_smoke/smoke_manifest.json` records the number of cases and failures.

Full traces are written to the configured trace directory. Evidence snapshots and schedules are written to the configured evidence directory.

## Manual audit questions

Inspect each trace in order. The purpose is software and methodology conformance, not performance tuning.

### Planner

- Does the `ContextFrame` only contain prompt-supported facts?
- Are unsupported demographic, religious, national or regional assumptions absent?
- Is the prompt-level `DimensionPlan` defensible from the prompt?

### Target extraction

- Are there no more than three material targets?
- Do target quotes occur verbatim in the response?
- Are the selected targets culturally consequential rather than random sentences?
- Are internal-quality and non-verifiable-value targets not forced into web retrieval?

### Neutral questions and blindness

- Does each retrievable target produce exactly one baseline and one variation question?
- Are the questions neutral rather than framed to prove the response wrong or right?
- Do query rewriting, retrieval, source classification and evidence synthesis avoid receiving the candidate response or target object?

### Retrieval and evidence

- Are benchmark/thesis sources filtered before synthesis?
- Do retrieved documents address the verification question?
- Are citations valid retrieved document IDs?
- Does the evidence memo distinguish tendency, context-sensitive practice, institutional/legal rule and universal claim?
- If evidence is insufficient or conflicting, is there at most one follow-up round?

### Comparison and scoring

- Is the final evidence memo frozen before target comparison?
- Does the target verdict follow from the frozen memo?
- Do dimension scores use only 0, 1, 2 or `abstain`?
- Is the overall score equal-weighted with no culture-specific cap or Python override?
- Are failures expressed as abstentions rather than fabricated scores?

## Allowed fixes after smoke audit

Allowed:

- schema or validation bug fixes;
- trace-link or artifact-writing fixes;
- replay/snapshot handling fixes;
- prompt-template clarification that improves general structure;
- provider/config handling fixes;
- leakage-filter configuration gaps.

Not allowed:

- special rules for a smoke case;
- hard-coded cultural answers;
- score caps tied to a country, religion, demographic group or benchmark item;
- tuning against PLT human labels;
- changing the smoke cases into evaluation data.

## Freeze condition

Verifier v1.0 can be frozen when:

1. all structural tests pass;
2. smoke traces show the intended pipeline structure;
3. the model ID, provider, temperature, retrieval provider, `top_k`, target budget, retrieval-round limit, rubric and prompt-template versions are recorded;
4. no semantic change has been made based on human-gold performance.

The next artifact after this audit should be `docs/verifier_v1_freeze.md`, created only after the selected model/config and smoke trace inspection are final.
