# Standalone Cultural Verifier Specification

## Research claim

The primary experiment tests whether the proposed evidence-grounded cultural verifier selects the human-preferred culturally appropriate response more accurately than independent reward-model baselines on the same Best-of-4 candidate sets.

The reward-model score is **never** an input feature of the verifier.

## Input

For one candidate:

```json
{
  "prompt": "...",
  "response": "...",
  "target_context": "Germany"
}
```

For the primary Best-of-4 experiment:

```text
set_id,prompt_id,prompt,response_a,response_b,response_c,response_d,human_chosen
```

`human_chosen` is optional during development and is not passed to the verifier.

## Stage 1 — Atomic claim extraction

Input: prompt, response, target context.

Output:

```json
{
  "claims": [
    "One independently verifiable cultural/factual claim",
    "Another independently verifiable claim"
  ]
}
```

No fixed claim-type routing is used. Claims may concern laws, statistics, history, language, etiquette, social practices, institutions, or claimed cultural norms as long as external evidence can reasonably support or contradict them.

Pure advice, preferences, hedged possibilities, and value judgments should not be converted into factual claims.

## Stage 2 — Broad evidence search and claim verification

Each claim is sent independently to OpenRouter with the `openrouter:web_search` server tool.

There is **no preset website allowlist** and no claim-type-to-source routing.

The verifier instructs the search-enabled model to search broadly and prefer stronger evidence when available, such as current primary, official, survey, corpus, scholarly, or otherwise authoritative sources.

Claim-verification output:

```json
{
  "claim": "...",
  "verdict": "supported | contradicted | mixed | not_enough_evidence",
  "confidence": 0.0,
  "reason": "...",
  "sources": [
    {
      "url": "...",
      "title": "...",
      "content": "..."
    }
  ]
}
```

Absence of evidence must not be treated as contradiction.

## Stage 3 — Evidence-grounding dimension

The evidence-grounding score is deliberately transparent and untuned:

- supported = 1.0
- mixed = 0.5
- not_enough_evidence = 0.5
- contradicted = 0.0

The candidate's evidence-grounding score is the arithmetic mean across its independently checked claims.

If no externally verifiable claims are extracted, evidence grounding is neutral at 0.5.

## Stage 4 — Cultural rubric

The cultural judge scores four dimensions on an integer 0–2 scale. They are normalized to 0–1:

1. **contextual appropriateness** — response fits the stated local/cultural situation rather than defaulting to another culture;
2. **non-essentialism** — avoids stereotypes and treating a population as homogeneous;
3. **variation and uncertainty** — appropriately represents regional, social, individual, or temporal variation when relevant;
4. **actionable helpfulness** — provides useful advice that remains appropriate within the stated context.

Factual accuracy is not re-scored in this stage because it is represented by evidence grounding.

## Stage 5 — Primary verifier score (Option A)

No calibration or learned weights are used.

All five normalized dimensions have equal weight:

```text
VerifierScore = mean(
    evidence_grounding,
    contextual_appropriateness,
    nonessentialism,
    variation_and_uncertainty,
    actionable_helpfulness
)
```

This is the primary score used to select the verifier's Best-of-4 winner.

## Stage 6 — Hard-failure diagnostics

The verifier separately reports severe failures under these diagnostic categories:

- fabricated_rule_or_law
- direct_evidence_contradiction
- harmful_stereotype
- cultural_essentialism
- wrong_context_or_country
- ignored_explicit_context

Hard failures do **not** receive an extra numeric penalty in the primary score. This avoids introducing another arbitrary hyperparameter. Their effect should already be visible through evidence grounding and/or the cultural dimensions, while the explicit flag provides interpretability and qualitative error analysis.

## Output

```json
{
  "final_score": 0.0,
  "dimensions": {
    "evidence_grounding": 0.0,
    "contextual_appropriateness": 0.0,
    "nonessentialism": 0.0,
    "variation_and_uncertainty": 0.0,
    "actionable_helpfulness": 0.0
  },
  "claims": [],
  "claim_checks": [],
  "hard_failures": []
}
```

## Primary empirical comparison

Every system receives exactly the same prompt and candidates A–D.

The verifier and each reward-model baseline independently choose one winner.

When human labels are available, the primary metric is Best-of-4 agreement with `human_chosen`:

```text
accuracy = number of system winners equal to human_chosen / number of labelled sets
```

The hybrid method is intentionally excluded from the primary research claim and may be explored later only as a secondary application experiment.
