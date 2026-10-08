# 5. The Vericult Verifier

## 5.1 Design

Vericult receives a user prompt and one generated response. It is independent of the response generator, human reference labels, and the reward-model baseline. The verifier does not use benchmark answers at runtime. The final experiment uses one frozen semantic backbone for the stages requiring language understanding.

## 5.2 Overview

```text
Prompt + Response
  -> extract explicit prompt context
  -> decide cultural applicability
  -> plan D01–D10 dimensions
  -> check response assessability
  -> extract up to three material targets
  -> formulate two neutral questions per retrievable target
  -> retrieve and filter evidence without candidate text
  -> create evidence memo; optionally follow up once
  -> freeze memo
  -> compare response target with frozen evidence
  -> score applicable dimensions
  -> produce outcome and trace
```

This sequence is an important part of the method: evidence gathering and response comparison are not the same step.

## 5.3 Context extraction

The context planner reads the prompt and extracts only stated facts. A location, relationship, or religion is not inferred from a person's name. Extracted information must be tied to exact spans in the prompt. This reduces the risk of judging an answer against a situation the user never described.

## 5.4 Dimension planning and assessability

The planner selects the relevant dimensions before detailed response checking. If the response is only a refusal or contains no substantive answer, the system can return `not_assessable`. This matters in a red-team dataset: a refusal should not be mistaken for a culturally correct answer simply because it avoids making a claim.

## 5.5 Material targets

The target extractor selects up to three decision-relevant parts of the response. Each target is grounded in an exact quotation. A target can concern an external fact, a descriptive cultural norm, a context-dependent recommendation, an internal response quality, or a non-verifiable value statement. Only the first three categories normally require external retrieval.

## 5.6 Neutral questions

For each retrievable target, the system asks two questions: one about the basic claim or practice and one about its scope and variation. The questions are designed to avoid assuming the claim is already true or false. **The target is visible during question formation.** Candidate blindness begins after that stage, when evidence is collected and summarized without the candidate's wording.

## 5.7 Retrieval

The LIVE configuration uses Tavily. Queries are rewritten from the neutral questions. Retrieved material is filtered for duplicates, excluded benchmark sources, and provenance concerns. The system classifies source types and builds an evidence memo that records what is supported, what varies, and whether the evidence is sufficient. Source classification is not proof that a document is correct.

## 5.8 Bounded follow-up and freeze

If the evidence is insufficient or conflicting, the system can request one additional gap-specific search. It cannot search indefinitely until a preferred conclusion appears. After retrieval, the memo is frozen before the response target is compared with it. The comparison can return supported, contradicted, mixed, or insufficient.

## 5.9 Scoring and outcomes

The scorer applies the rubric to the planned dimensions. A supported factual target does not automatically imply cultural appropriateness; context and framing still matter. Conversely, an insufficient evidence memo does not automatically prove a claim false. The implementation also has a rule that prevents a response with a material zero-score dimension from being endorsed, without changing the underlying relative score.

## 5.10 LIVE and REPLAY

LIVE makes external searches and saves evidence. An audit checks that the required records and snapshots exist before evidence is frozen. REPLAY evaluates using those stored snapshots. The primary Vericult findings in this thesis are taken from REPLAY, subject to a completed evidence audit.

## 5.11 Implementation excerpts

The following interface illustrates the actual single-response evaluation call used by the final runner:

```python
result = verifier.verify(prompt, response)
```

The experiment is invoked through:

```bash
python scripts/run_final_experiment.py --mode LIVE
python scripts/audit_final_evidence.py
python scripts/run_final_experiment.py --mode REPLAY
```

These are repository interfaces, not pseudocode for a different evaluator. **[CODE AUDIT]** Before submission, insert short verbatim excerpts from `src/cultverify/` for target extraction, memo freezing, and scoring, with exact commit and line ranges.

## 5.12 Traceability and software testing

The verifier writes structured traces linking decisions to questions, evidence, and scoring. Unit tests check behavior such as structural validation, boundaries, and retry limits. Passing software tests is evidence that those tested software properties work; it does not establish cultural accuracy. **[INSERT FINAL TEST COMMIT, TEST COUNT, AND VERIFIED LIVE SMOKE RESULT]**.
