# 6. Experimental Design and Evaluation Protocol

This chapter describes the final evaluation protocol. It is intentionally separated from the development history of Vericult.

The final experiment uses one fixed response for every prompt. The older Best-of-4 setup is not the primary experiment.

## 6.1 Evaluation Objectives

The experiment has four objectives.

### Objective 1: test Vericult on varied cultural cases

The final dataset should contain both ordinary multicultural prompts and difficult challenge cases.

### Objective 2: keep response generation consistent

Every final response should come from the same generator and sampling configuration.

This avoids comparing verifier behaviour across a mixture of response generators.

### Objective 3: freeze evidence before final reporting

Live web retrieval should be separated from the final semantic evaluation.

### Objective 4: compare against simpler evaluators

Where comparable single-response baseline outputs are available, Vericult should be compared with a reward model and a direct LLM judge.

The comparison should be descriptive unless an independent response-level reference label is available.

## 6.2 Final Experimental Unit

The final unit is one pair:

[
x_i = (p_i, r_i)
]

where:

- (p_i) is one prompt;
- (r_i) is one frozen GPT-OSS response.

There are:

[
N = 360
]

pairs.

Each item is evaluated independently through:

```python
verifier.verify(prompt, response)
```

This is important because the final research question concerns the quality of one generated response rather than winner selection among four candidates.

## 6.3 Dataset Composition

The 360 items are divided into three equal corpora.

| Corpus | Items | Purpose |
|---|---:|---|
| PLT120 | 120 | custom cultural challenge and red-team cases |
| External120 | 120 | multicultural prompts drawn from existing public datasets |
| Redteam120 | 120 | externally grounded cultural red-team cases |
| **Total** | **360** | final experiment |

The corpus order is frozen as:

1. PLT120
2. External120
3. Redteam120

The runner uses canonical IDs:

- PLT001–PLT120
- EXT001–EXT120
- RT001–RT120

## 6.4 PLT120

PLT120 is the project's custom challenge corpus.

### PLT001–PLT030

The first 30 prompts come from the original development set.

They were initially designed for a Best-of-4 experiment and later reused as prompts only.

The old candidate responses and human labels are not reused in the final response-level evaluation.

### PLT031–PLT120

The additional 90 prompts expand the challenge set.

They were designed to contain subtler cultural traps rather than only obvious unsafe instructions.

Examples include:

- historical-memory framing;
- symbolic gift choices;
- loaded geopolitical wording;
- indigenous cultural performance;
- minority identity categories;
- caste inference;
- family and religious practices.

The final generator sometimes accepts the problematic premise, sometimes corrects it, and sometimes refuses.

For that reason, a PLT prompt is not itself a negative label.

The response must still be evaluated.

## 6.5 External120

External120 contains 20 prompts from each of six public multicultural datasets:

- CARE
- Community Alignment
- PLURAL
- PACT
- ThaiCLI
- PRISM

The purpose of this corpus is breadth.

It exposes the verifier to prompts from sources that were not written only for the custom PLT challenge set.

The older external experiment preserved in `data/final/external_120/` used source responses and an earlier verifier version.

That archived experiment is not the primary final experiment.

For the final 360-item run, the External120 prompts receive new responses from the common GPT-OSS generator.

This creates a consistent generator condition across all three corpora.

## 6.6 Redteam120

Redteam120 is a separately constructed challenge corpus grounded in public sources.

The prompts cover difficult areas such as:

- minority religion;
- ethnic identity;
- historical conflict;
- indigenous representation;
- gender and sexuality;
- stereotypes;
- political and institutional framing;
- intergroup relations.

The public provenance sources were used to construct defensible challenge scenarios.

They are not treated as answer keys during Vericult inference.

Unlike External120 benchmark hosting locations, these public evidence sources remain eligible for retrieval when they are ordinary evidence pages rather than hidden benchmark-label files.

## 6.7 Common Response Generator

All 360 final responses are generated with:

`gpt-oss:120b-mxfp4`

through the L3S inference endpoint.

The frozen sampling configuration is:

| Parameter | Value |
|---|---:|
| temperature | 0.8 |
| top_p | 0.95 |
| maximum generated tokens | 1200 |
| system prompt | none |
| prompt transformation | none |
| responses per prompt | 1 |

The source prompt is sent verbatim.

No human label or expected cultural issue is supplied to the generator.

The aim is to create a realistic fixed response set, not to force the generator to produce errors.

## 6.8 Why One Common Generator Is Important

Earlier project stages combined responses from different sources and models.

That design made some comparisons difficult.

A response from a small local model and a response from a strong external model have different error profiles.

The final design removes this confound.

Every final response comes from the same model under the same sampling setup.

Differences in Vericult outcomes across corpora therefore cannot be explained simply by a different response generator.

## 6.9 Frozen Input Validation

Every generated CSV stores:

- item ID;
- source dataset;
- prompt;
- prompt SHA-256;
- generator model;
- temperature;
- top-p;
- max tokens;
- response;
- response SHA-256;
- generation timestamp;
- token counts.

The final runner recomputes the prompt and response hashes before accepting an item.

It also computes one semantic hash per corpus over the ordered prompt-response identities and generator settings.

The frozen semantic hashes are:

- PLT120:  
  `febf9cf570b31e2f1a1ca5ee61466d6d8618fb7bd8d008a127b6cf6eb80214aa`
- External120:  
  `9d2c0e58afb89d2641adc549d7cfaff5eba9d45d549f728d6cba664778811a96`
- Redteam120:  
  `b0e8f9e81b4020bce0a5355790f511f9efaddc65944eddbdb072bbb2afb5989d`

These hashes protect the semantic content from accidental change while avoiding false mismatch from CSV newline formatting.

## 6.10 Vericult Model Configuration

The final semantic backbone is:

`vllm/qwen3.6:35b-a3b-fp8`

Provider:

`l3s`

Temperature:

`0`

API endpoint:

`https://inference.kbs.uni-hannover.de/v1/chat/completions`

The same backbone is used for all semantic stages.

There is no fallback model.

This differs from earlier development experiments that used much smaller local Qwen models.

## 6.11 Retrieval Configuration

The final LIVE retrieval uses Tavily.

Important values are:

- advanced search;
- top-k = 3;
- retrieval timeout = 45 seconds;
- at most 3 material targets;
- at most 2 retrieval rounds.

These values are frozen before final outcomes are inspected.

## 6.12 Leakage Controls

External retrieval can accidentally expose benchmark content.

The final configuration therefore excludes known benchmark locations.

The main exclusions are:

- `huggingface.co`
- the thesis repository
- `UpstageAI/ThaiCLI_H6`
- common annotation and result paths

The exact configuration is stored in:

`experiments/final_vericult_config.json`

The policy is conservative but not perfect.

Unknown mirrors cannot be excluded automatically.

## 6.13 Execution Sequence

The frozen sequence is:

```text
1. Local runtime preflight
2. Vericult LIVE over 360 items
3. Evidence audit and freeze
4. Vericult REPLAY over 360 items
5. Single-response baselines
6. Post-prediction analysis
```

The primary Vericult results come from REPLAY.

LIVE is used to acquire the evidence.

## 6.14 Runtime Preflight

Before the final run, the preflight verifies:

- the repository state;
- final configuration hash;
- all three dataset hashes;
- 360 item count;
- model provider and ID;
- required credentials;
- runtime environment.

It writes a runtime manifest.

The final runner refuses to execute when the frozen identities do not match.

## 6.15 LIVE Phase

The LIVE phase evaluates every fixed prompt-response pair while allowing real retrieval.

Output:

`artifacts/final_experiment/results/vericult_live.jsonl`

Trace directory:

`artifacts/final_experiment/traces/live`

Evidence directory:

`artifacts/final_experiment/evidence`

The batch runner checkpoints after each item.

If one item fails because of a provider or structural error, the failure is saved and the batch continues.

The overall command returns a non-zero exit status when unresolved failures remain.

## 6.16 Evidence Freeze

The evidence audit requires exactly 360 completed LIVE records.

It verifies the traces and evidence snapshots and hashes the resulting files.

Output:

`artifacts/final_experiment/evidence_manifest.json`

This manifest becomes a requirement for REPLAY.

## 6.17 REPLAY Phase

REPLAY uses the frozen evidence.

Output:

`artifacts/final_experiment/results/vericult_replay.jsonl`

The primary analysis should use the latest completed REPLAY record for every item.

The report must not mix LIVE and REPLAY outcomes without clearly saying so.

## 6.18 Baseline 1: Skywork Reward Model

The frozen repository contains an independent reward-model baseline based on:

`Skywork/Skywork-Reward-V2-Qwen3-4B`

revision:

`fd958fe`

The baseline produces a scalar reward for a prompt-response pair.

In the old script, four candidate scores were used to select a Best-of-4 winner.

The final experiment requires a single-response adapter.

The intended final output per item is:

- raw reward score;
- model identifier;
- status.

Because a scalar reward does not have a built-in Vericult label threshold, the thesis must not invent a culturally appropriate/inappropriate cutoff after looking at the results.

Possible valid comparisons include:

- correlation with Vericult's numeric score on complete cases;
- score distribution by Vericult outcome;
- ranking of cases in manually reviewed subsets;
- agreement after a threshold only if that threshold is independently defined.

Current status:

**[[SKYWORK SINGLE-RESPONSE ADAPTER / OUTPUT STATUS]]**

## 6.19 Baseline 2: Direct LLM Judge

The second baseline is a direct no-retrieval LLM judge.

Its purpose is to test whether a single semantic judgment can provide results comparable to the multi-stage verifier.

The old direct-judge script is Best-of-4 and therefore also requires adaptation for the final 360 × 1 design.

The single-response judge should receive:

- the D01–D10 rubric;
- prompt;
- response.

It should output one of the same broad cultural outcome categories where possible.

It must not use Tavily or Vericult evidence.

Current status:

**[[DIRECT-JUDGE SINGLE-RESPONSE ADAPTER / MODEL / OUTPUT STATUS]]**

## 6.20 CARB's Role in the Final Evaluation

CARB remains important related work.

It is not inserted into the final results table as if it were evaluated on the same 360 responses.

The reasons are:

- different dataset;
- different task format;
- Best-of-N preference selection;
- different model set;
- different metrics.

The thesis can compare design choices and reported findings.

It should not claim that Vericult “beats CARB” from non-comparable percentages.

## 6.21 Human Evaluation

The project contains a completed human annotation pilot from the old PLT30 Best-of-4 phase.

Five students evaluated all 30 old items.

The pilot produced:

- 600 candidate-level ratings;
- 150 Best-Response choices.

However, these labels apply to the old candidate responses.

The final GPT-OSS responses are different.

Therefore:

> the old human labels are not final ground truth for the 360-response experiment.

If a new human evaluation of the final response set is later conducted, it should be described separately and inserted here.

Current status:

**[[FINAL-360 HUMAN ANNOTATION STATUS: none / subset / full]]**

## 6.22 What Can Be Claimed Without New Human Labels

The lack of final response-level human gold changes the interpretation of the experiment.

The thesis can validly report:

- Vericult outcome distribution;
- D01–D10 score distribution;
- abstention rate;
- evidence coverage;
- retrieval failures;
- trace-backed case studies;
- corpus differences;
- Vericult versus baseline agreement;
- reward-score relationships;
- execution efficiency.

The thesis cannot validly claim:

- final Vericult accuracy against humans;
- sensitivity/specificity against cultural ground truth;
- that Vericult objectively outperforms the baselines in correctness.

Such claims require an independent reference for the same final responses.

This limitation is not a minor footnote.

It directly shapes the main evaluation.

## 6.23 Primary Quantities

The final report should calculate the following quantities from the frozen REPLAY output.

### Outcome distribution

For each label (c):

[
P(c)=rac{#{i:y_i=c}}{360}
]

### Completion rate

[
C=rac{N_{completed}}{360}
]

### Dimension frequency

How often each D01–D10 dimension is selected.

### Dimension score distribution

Counts of:

- 0;
- 1;
- 2;
- abstain.

### Evidence coverage

The verifier defines evidence coverage as the proportion of retrievable targets whose final memo is not insufficient.

This is a pipeline diagnostic.

It is not an accuracy score.

### Abstention

Report:

- item-level outcomes involving insufficient evidence;
- dimension-level abstentions;
- partial-abstention cases.

### Target truncation

Count how often more material units existed than the three-target budget could include.

## 6.24 Corpus-Level Analysis

All primary diagnostics should also be shown separately for:

- PLT120;
- External120;
- Redteam120.

This is important because the corpora have different purposes.

However, the thesis should not automatically interpret a higher inappropriate rate in a red-team corpus as better accuracy.

The generator may resist some red-team prompts and produce appropriate responses.

## 6.25 Baseline Comparison Metrics

If both single-response baselines are completed, the following analyses are appropriate.

### Exact categorical agreement

For a direct judge using comparable labels:

[
A = rac{1}{N}sum_i I(v_i = j_i)
]

where (v_i) is the Vericult outcome and (j_i) is the direct-judge outcome.

This measures system agreement, not correctness.

### Cohen's kappa

If the label mapping is suitable and both systems classify all items, Cohen's kappa can describe agreement beyond chance.

It should be interpreted carefully because prevalence can affect kappa.

### Reward-score relationship

For Skywork, report Spearman correlation with the Vericult score only on cases where the Vericult public score is defined.

Also show score distributions by categorical Vericult outcome.

Do not force reward values into arbitrary binary classes unless a threshold is independently justified.

## 6.26 Trace-Backed Qualitative Sample

The quantitative tables should be supplemented by a manually selected but transparent case sample.

Useful categories include:

- clear evidence-supported cultural problem;
- subtle overgeneralization;
- successful variation handling;
- retrieval failure;
- abstention;
- direct-judge disagreement;
- reward-model disagreement;
- culturally non-applicable case;
- refusal / not-assessable case.

Cases should be selected after machine outputs are frozen.

The report should state how the sample was chosen.

## 6.27 Statistical Analysis

The final experiment is primarily descriptive because it lacks final human reference labels.

Confidence intervals can still be reported for proportions such as:

- inappropriate-rate estimates;
- abstention rates;
- completion rates.

A simple non-parametric bootstrap over items can be used where useful.

For comparisons between two systems' categorical outputs, paired disagreement counts can be reported.

McNemar's test should only be used for paired binary **correctness** when an external reference defines correctness.

Without such a reference, applying McNemar to “Vericult versus judge” would be conceptually wrong.

This is one example where using fewer statistical tests is more scientifically appropriate.

## 6.28 Efficiency Metrics

Where trace and runtime logs support them, report:

- total wall-clock time;
- average wall-clock time per item;
- number of semantic calls;
- number of retrieval queries;
- evidence snapshots;
- failure/retry counts.

Token-level API cost should only be reported if exact billing or usage records are available.

Do not estimate a precise monetary total from unsupported assumptions.

## 6.29 Development Pilot as Secondary Evidence

The earlier PLT30 study can still be reported in a short development subsection.

Its main value is showing that:

- the project originally used Best-of-4;
- five annotators showed substantial disagreement;
- a single winner is often difficult to define for cultural appropriateness;
- this motivated stronger uncertainty handling and the move toward absolute single-response verification.

The pilot should not dominate the final results chapter.

## 6.30 Reproducibility Freeze

The final manifest records:

- experiment ID;
- code freeze commit;
- generator configuration;
- corpus semantic hashes;
- Vericult model;
- configuration hash;
- decision space;
- leakage rules;
- execution order.

The semantic code freeze is:

`099e4116a809ee004c1cdea04d1bcc2a14e7d142`

The experiment ID is:

`thesis-final-v4-360x1`

The schema is:

`thesis-final-v4-single-response`

No semantic tuning should be performed after inspecting final outcomes.

Execution-only fixes must preserve the frozen prompt and response identities.

## 6.31 Summary

The final experiment is designed around 360 fixed prompt-response pairs and one common response generator.

The main evaluation does not ask Vericult to choose a winner from four candidates.

Instead, it asks:

> What does Vericult conclude about this individual response, what evidence supports that conclusion, and where does the system remain uncertain?

The next chapter is the results chapter. Values remain as explicit placeholders until the final LIVE → audit → REPLAY run and comparison baselines are complete.
