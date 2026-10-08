# 8. Discussion and Error Analysis

This chapter interprets the final experiment. The current draft separates result-independent discussion from result-dependent claims.

Any statement that depends on the final REPLAY output remains a placeholder until the frozen results are available.

## 8.1 What Vericult Is Trying to Add

The main question is not whether Vericult can produce one more automated label.

Reward models and direct LLM judges can already score or classify responses.

The main design question is whether the extra structure provides useful information that a one-step evaluator does not provide.

Vericult exposes:

- what context it extracted;
- which cultural dimensions it considered;
- which response spans were material;
- what external questions were asked;
- which sources were retrieved;
- whether evidence was sufficient or conflicting;
- how the target related to the evidence;
- why a dimension was scored;
- where the system abstained.

This makes the evaluator easier to inspect.

However, inspectability does not automatically mean correctness.

A detailed trace can still contain a mistaken dimension plan, weak retrieval or a bad semantic judgment.

The final evaluation should therefore judge the trace as an advantage in **diagnosis**, not as proof of superior cultural understanding.

## 8.2 Evidence Grounding Versus Direct Judgment

A direct LLM judge can evaluate a prompt and response in one call.

This is much cheaper and simpler than Vericult.

The comparison therefore asks whether evidence grounding changes the quality or character of the judgment.

There are several situations where external evidence should be useful.

### Formal rules

Legal or institutional claims can often be checked against official sources.

### Specific factual cultural claims

A response may make a concrete historical, linguistic or religious claim.

### Scope-sensitive norms

Evidence can show that a practice exists but also reveal regional or household variation.

### Disputed recommendations

A recommendation may depend on a factual premise that should be verified first.

There are also cases where retrieval adds little.

### Purely internal failure

If a response ignores an explicit prompt requirement, the prompt and response may be sufficient.

### Obvious stereotyping

A categorical demeaning statement may be directly assessable.

### Value disagreement

Web search cannot establish one universally correct moral preference.

The final trace analysis should therefore ask not only “did retrieval happen?” but “was retrieval useful for this target type?”

## 8.3 Case Type: Correct Facts, Inappropriate Recommendation

PLT040 is designed to expose an important failure mode.

The response can correctly explain what a Stolperstein is and still recommend an inappropriate activity around it.

This type of case demonstrates why cultural verification is broader than factual verification.

The final trace should be examined for:

- D09 selection;
- the material recommendation target;
- evidence about commemorative purpose;
- whether the scorer separates factual accuracy from tone and use.

Actual result:

**[[PLT040 DISCUSSION FROM TRACE]]**

If Vericult correctly identifies the cultural problem, the case is a good example of added value from the D01–D10 framework.

If it does not, the failure is equally informative.

## 8.4 Case Type: Friendly Tone Hides a Cultural Error

PLT092 is another useful stress case.

The GPT-OSS response is positive, polite and celebratory.

A superficial evaluator may reward the tone.

The culturally relevant issue is the selected amount and its symbolism.

This case tests whether the verifier can look past general helpfulness and focus on the material cultural target.

Actual result:

**[[PLT092 DISCUSSION FROM TRACE]]**

The trace should show whether:

- the amount itself was selected as a target;
- the search questions were neutral;
- retrieved sources had suitable scope;
- the final score reflected the evidence.

## 8.5 Case Type: Respectful Language but Problematic Category Mapping

PLT120 illustrates a subtler identity issue.

The response explicitly recognizes fa'afafine as a distinct Samoan identity.

This is a positive cultural signal.

At the same time, it recommends that fa'afafine attendees select “Transgender” because it is the closest available option.

The cultural problem is therefore not ignorance alone.

It is the practical consequence of forcing a culturally specific identity into an externally designed category.

This kind of mixed case is one reason Vericult has a score of 1.

Actual result:

**[[PLT120 DISCUSSION FROM TRACE]]**

A useful result would distinguish:

- respectful explanation;
- problematic form design;
- problematic recommendation;
- uncertainty around identity terminology.

## 8.6 Case Type: Indigenous Cultural Performance

PLT116 concerns a haka at an international conference.

The response uses positive language about Māori identity and heritage.

The main question is whether recognition of cultural significance is enough to justify the proposed performance.

Important contextual questions may include:

- who has authority to teach or perform the specific haka;
- whether the sports club's involvement is sufficient;
- what type of haka is intended;
- whether ceremonial use is appropriate in the conference context.

This is a hard case for web retrieval because online sources may discuss haka in general while the specific appropriateness depends on community and performance context.

Actual result:

**[[PLT116 DISCUSSION FROM TRACE]]**

This case can reveal whether Vericult overstates evidence when the sources are too general.

## 8.7 Refusals and Not-Assessable Outputs

Red-team prompts can trigger refusals.

A refusal is not necessarily a bad model behaviour.

However, the thesis evaluates **cultural appropriateness of substantive answers**.

A pure refusal contains little cultural content to score.

The `not_assessable` outcome prevents the system from awarding a perfect cultural score merely because the generator avoided answering.

This distinction is particularly useful in RT002.

Actual refusal count:

**[[FINAL_NOT_ASSESSABLE_COUNT]]**

The discussion should inspect whether all not-assessable cases are genuine refusals/non-answers or whether the gate incorrectly rejected short but substantive responses.

## 8.8 Cultural Applicability Errors

The cultural-applicability gate reduces unnecessary evaluation, but it can fail in two directions.

### False cultural applicability

The system may treat incidental country or identity words as culturally material.

This creates unnecessary retrieval and may lead to invented cultural reasoning.

### Missed cultural applicability

The system may classify a subtle cultural task as generic.

The pipeline then stops too early.

The final analysis should manually review a sample of:

- `not_culturally_applicable` outcomes;
- near-boundary cases.

Result:

**[[NCA MANUAL REVIEW FINDING]]**

Because there is no final human gold, this review should be presented as qualitative error analysis rather than an accuracy estimate unless a formal annotation protocol is added.

## 8.9 Context Extraction Failure Modes

Context extraction is intentionally conservative.

This reduces hallucinated demographic assumptions but can also omit useful implied context.

Possible failures include:

- missing an explicit relationship;
- attaching a span that only partially supports the extracted value;
- treating a broad setting as a precise location;
- failing to capture an explicit user constraint.

The exact-span rule makes these errors easier to inspect.

A sample table should contain:

| Item | Context field | Extracted value | Problem | Downstream effect |
|---|---|---|---|---|
| [[ID]] | [[FIELD]] | [[VALUE]] | [[ERROR]] | [[EFFECT]] |

## 8.10 Dimension Planning Failure Modes

Dimension planning is prompt-level.

This gives consistency but creates a known blind spot.

A response may introduce a new cultural issue that the prompt did not strongly imply.

For example, a neutral prompt about a travel plan could receive a response containing a gender stereotype.

If D07 or D10 was not planned, the scorer cannot freely add it later.

The final error analysis should identify whether this happens in practice.

**[[NUMBER / EXAMPLES OF RESPONSE-INTRODUCED UNPLANNED ISSUES]]**

This limitation could be addressed in future work by adding a response-level safety scan that is separate from prompt-level dimension planning.

That extension is not part of the frozen Vericult 1.1 method.

## 8.11 Target Selection Failure Modes

The maximum target budget is three.

This keeps the pipeline bounded but creates two risks.

### Missing the important target

The model may select a minor sentence instead of the culturally decisive statement.

### Truncation

A long response may contain more than three material issues.

The extractor then sets `targets_truncated=true`.

The final analysis should report how often truncation occurs and manually inspect several cases.

**[[TARGET TRUNCATION ANALYSIS]]**

This is especially important because many External120 and Redteam120 responses hit the 1200-token generation cap.

Long responses naturally create more candidate claims.

## 8.12 Verification-Question Framing

The evidence stage is candidate-blind only after questions have been generated.

The questions can still transmit framing from the original response.

For example, if a target says:

> “Culture X requires women to do Y.”

a badly written neutral question might still assume that the claimed requirement exists.

The prompt tries to prevent this by instructing the model not to presuppose disputed premises.

The final audit should inspect a sample of questions for:

- leading language;
- over-specific location;
- target verdict hints;
- loaded terminology.

**[[QUESTION NEUTRALITY AUDIT RESULT]]**

This is one of the most important remaining methodological risks.

## 8.13 Retrieval Failure Modes

Retrieval can fail even when the questions are good.

Common causes include:

### Search-engine coverage

Some local practices are poorly indexed.

### Language mismatch

English search may not surface the best local-language sources.

### Popularity bias

Commercial travel pages may outrank academic or community sources.

### Overly broad queries

A query can return generic country information instead of the exact norm.

### Overly narrow queries

A query can become so specific that only weak pages match.

### Temporal drift

Current rules or social practice may have changed.

The final report should quantify:

- retrieval timeouts;
- zero-useful-source cases;
- insufficient memos;
- source-type distribution.

It should also present trace examples.

## 8.14 Source Classification Failure Modes

Source classification is itself a model judgment.

A polished website can look institutional even when it is commercial.

A paper repository can host scholarly text without proving peer review.

The final prompts therefore require explicit provenance for strong source categories.

Nevertheless, misclassification can still happen.

The error analysis should inspect cases where:

- a commercial source was labelled institutional;
- a secondary article was labelled official/legal;
- an academic-hosting platform was treated as peer-reviewed provenance.

**[[SOURCE CLASSIFICATION AUDIT]]**

## 8.15 Evidence Memo Overclaiming

One major risk in retrieval-augmented systems is that the synthesis says more than the sources support.

Vericult addresses this through:

- short verbatim quotes;
- deterministic quote grounding;
- support/relevance checking.

However, semantic overclaiming can still happen.

Example:

Source quote:

> “This greeting is common in formal business meetings.”

Memo claim:

> “This greeting is required in all professional situations.”

The quote exists, but the memo strengthens the scope.

The relevance gate is intended to reject such overclaiming.

The final analysis should measure how often evidence statements are removed or downgraded.

**[[EVIDENCE RELEVANCE FILTER ANALYSIS]]**

## 8.16 Conflicting Evidence

Conflicting evidence is not a system failure by itself.

Cultural practice can genuinely vary.

A good verifier should sometimes preserve disagreement instead of forcing consensus.

Cases with `conflicting` memos should therefore be reviewed separately.

The discussion should ask:

- Did the sources represent real variation?
- Was the conflict caused by low-quality sources?
- Did the final target verdict become mixed?
- Did the dimension score reflect the uncertainty appropriately?

**[[CONFLICTING EVIDENCE CASE ANALYSIS]]**

## 8.17 Follow-Up Retrieval

The one-round follow-up is intended to resolve the most important remaining gap.

Its usefulness can be measured.

If follow-up rarely changes evidence sufficiency, it may add complexity without much benefit.

If it often resolves cases, it supports the bounded two-round design.

Final finding:

**[[FOLLOWUP EFFECTIVENESS]]**

## 8.18 Target Comparison Errors

The target comparator sees exact response text only after evidence is frozen.

This is meant to separate evidence construction from candidate judgment.

Possible errors include:

- calling absence of evidence a contradiction;
- ignoring scope mismatch;
- treating mixed sources as support;
- missing that only part of the target is supported.

The final analysis should sample all four verdict types.

**[[TARGET COMPARATOR AUDIT]]**

## 8.19 Dimension Scoring Errors

A correct target verdict does not guarantee a correct cultural score.

The scorer must interpret material cultural relevance.

For example:

- a fact can be supported but irrelevant;
- a common practice can be supported without being mandatory;
- a recommendation can be factually possible but socially inappropriate.

This is why Vericult does not map:

`supported -> score 2`

or:

`contradicted -> score 0`

with hard-coded rules.

The downside is that the final scorer remains an LLM judgment.

The final discussion should show examples where:

- target evidence was correct but scoring was poor;
- target evidence was mixed but scoring was appropriately cautious;
- a score-0 decision was well justified.

## 8.20 Abstention Quality

Abstention is useful only if it occurs for the right reasons.

Too little abstention creates false certainty.

Too much abstention makes the verifier unhelpful.

The final analysis should examine:

- abstention rate;
- dimensions with highest abstention;
- source types preceding abstention;
- whether contextual fallback reduces unnecessary abstention.

A useful result is not necessarily the lowest abstention rate.

The goal is calibrated coverage.

## 8.21 LIVE Versus REPLAY

LIVE and REPLAY share frozen evidence but still run semantic model stages.

The two outputs may therefore differ.

The final report should compare:

- categorical outcome stability;
- dimension-score stability;
- target/question schedule stability;
- execution failures.

**[[LIVE_VS_REPLAY_AGREEMENT]]**

Large differences would be important because they would show that evidence freezing alone does not make the semantic pipeline stable.

## 8.22 Vericult Versus Direct LLM Judge

The direct judge is the strongest simplicity baseline.

Three broad outcomes are possible.

### High agreement

If the systems agree on most cases, the question becomes whether Vericult's diagnostic trace justifies its additional cost.

### Moderate agreement with meaningful Vericult improvements

If disagreement cases show that evidence corrects unsupported direct-judge assumptions, this supports the value of evidence grounding.

### Moderate agreement with frequent Vericult failures

If retrieval and decomposition introduce more errors than they resolve, the simpler judge may be preferable.

The thesis must let the final traces determine which interpretation is justified.

Final finding:

**[[VERICULT_VS_DIRECT_DISCUSSION]]**

## 8.23 Vericult Versus Reward Model

Skywork produces a scalar reward rather than a source-grounded cultural explanation.

The most meaningful analysis is therefore not a forced exact label comparison.

Instead, examine:

- whether culturally inappropriate Vericult cases receive lower rewards;
- whether reward scores separate appropriate from partial cases;
- high-reward cases that Vericult flags;
- low-reward cases that Vericult accepts.

These disagreement examples can reveal whether the systems emphasize different qualities.

Final finding:

**[[VERICULT_VS_SKYWORK_DISCUSSION]]**

## 8.24 Relation to CARB

CARB and Vericult share the motivation that evaluators themselves need cultural awareness.

CARB evaluates whether reward models prefer culturally appropriate candidates.

Vericult asks a different question:

> Can one fixed response be verified through a structured, evidence-grounded process?

The systems therefore occupy different points in the evaluation space.

CARB is stronger as a standardized reward-model benchmark with a known preference target.

Vericult is stronger in traceability and claim-level evidence by design.

These are design differences, not empirical superiority claims.

## 8.25 Relation to CultureLLM and Generator Adaptation

CultureLLM changes the model that produces the answer.

Vericult leaves the generator unchanged.

This creates a possible future loop:

```text
Generator
    |
    v
Vericult verification
    |
    +--> accepted response
    |
    +--> feedback / revision request
```

The current thesis stops before automatic revision.

This is deliberate.

If the verifier both judges and rewrites the answer, it becomes harder to separate evaluation quality from generation quality.

## 8.26 What the Pilot Human Study Tells Us

The five-person PLT30 pilot had low inter-annotator agreement.

The main lesson is not that human evaluation is useless.

The lesson is that cultural appropriateness can be genuinely difficult to aggregate.

The pilot also had methodological limitations:

- only five students;
- not cultural experts;
- fixed four-way candidate choice;
- old responses;
- no direct applicability to the final GPT-OSS outputs.

The final thesis therefore uses the pilot to motivate caution around “ground truth,” not as evidence that Vericult is correct.

## 8.27 Answer to RQ1

**RQ1: How does Vericult classify culturally situated LLM responses across diverse settings?**

Final answer:

**[[RQ1 ANSWER BASED ON REPLAY DISTRIBUTIONS, COVERAGE AND CORPUS ANALYSIS]]**

The answer should include:

- overall completion;
- dominant outcome categories;
- differences between corpora;
- most frequently used dimensions;
- abstention.

## 8.28 Answer to RQ2

**RQ2: How do Vericult judgments compare with an independent reward model and direct LLM judge?**

Final answer:

**[[RQ2 ANSWER]]**

If final human labels do not exist, use the word **agreement**, not **accuracy**.

## 8.29 Answer to RQ3

**RQ3: What additional diagnostic information is provided by target-level evidence and traces?**

Final answer:

**[[RQ3 ANSWER WITH 2–3 TRACE EXAMPLES]]**

This should be supported by examples such as:

- evidence correcting a factual premise;
- variation preventing an overgeneralization;
- abstention revealing missing evidence;
- a failure trace locating the pipeline problem.

## 8.30 Answer to RQ4

**RQ4: Which failure modes arise?**

Final answer:

**[[RQ4 ANSWER]]**

Expected categories include:

- retrieval insufficiency;
- question framing;
- target budget;
- source quality;
- semantic scoring;
- provider failures.

Only include categories that actually occur in the final trace audit.

## 8.31 Main Interpretation

The final thesis should end this chapter with one balanced interpretation.

A suitable form is:

> Vericult should be judged as a verification architecture, not only as a classifier. Its value depends on whether the additional evidence and trace information improves the reliability and interpretability of cultural judgments enough to justify the added complexity.

The final sentence must then state what the completed experiment actually shows.

**[[FINAL DISCUSSION TAKEAWAY]]**
