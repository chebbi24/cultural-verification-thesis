# 9. Threats to Validity and Limitations

Vericult is a research prototype. Its design adds structure and evidence to cultural evaluation, but it does not remove the fundamental difficulty of the task.

This chapter summarizes the most important limitations.

## 9.1 Construct Validity

The first limitation concerns the target concept itself.

“Cultural appropriateness” is not directly observable like a physical measurement.

The D01–D10 framework is one operationalization.

Another reasonable framework could group the same problems differently.

The dimensions were designed from literature and project needs, but they are still a thesis design choice.

This means that a Vericult score should not be interpreted as a universal measurement of culture.

It is a measurement under a declared rubric.

## 9.2 Cultural Diversity Inside Groups

Country and community labels can hide variation.

People differ by:

- region;
- language;
- religion;
- generation;
- class;
- profession;
- political view;
- family;
- personal preference.

Vericult tries to reduce essentialism through scope questions, variation questions and cautious scoring.

It cannot guarantee that retrieved evidence represents all relevant subgroups.

This is especially difficult when one group is much better documented online than another.

## 9.3 Web Evidence Is Uneven

The web is not a neutral sample of culture.

Some practices have extensive English-language documentation.

Others are mainly transmitted through local-language sources, oral tradition or community experience.

Search engines can overrepresent:

- commercial tourism pages;
- popular English explanations;
- highly linked institutions;
- majority-group perspectives.

The verifier's source classification helps interpretation but does not solve this representational problem.

## 9.4 Source Quality Is Context-Dependent

No one source hierarchy works for all cultural questions.

An official government page may be excellent evidence for a legal rule but poor evidence for informal family practice.

A community post may be useful for lived experience but weak evidence for how common that experience is.

Vericult therefore classifies source type rather than assigning one universal authority score.

This still leaves difficult semantic judgments about source suitability.

## 9.5 Retrieval Coverage

The final system uses a bounded search.

This makes the experiment manageable and reproducible, but it can miss relevant evidence.

At most:

- three material targets are selected;
- two initial questions are asked per retrievable target;
- one follow-up question can be added;
- three accepted documents are retained per query.

A failure to find evidence therefore does not prove that no evidence exists.

## 9.6 Question Framing

Candidate blindness begins only after verification-question generation.

The question generator has seen the target.

A biased or leading question can therefore influence the later evidence set even if retrieval itself does not see the candidate.

This is one of the main limitations of the architecture.

Future work could compare several independently generated neutral questions or use an adversarial question-neutrality checker.

## 9.7 One Semantic Backbone

The final verifier uses one Qwen3.6 backbone for all semantic stages.

This simplifies configuration and reduces model-to-model inconsistency.

It also creates correlated error.

If the backbone has a particular cultural misconception, the same misconception could affect:

- dimension planning;
- target selection;
- source classification;
- memo synthesis;
- final scoring.

The retrieval evidence reduces but does not eliminate this risk.

## 9.8 Temperature Zero Does Not Mean Full Determinism

The semantic temperature is zero.

However, the model is accessed through a remote inference service.

Backend changes, numerical differences or serving configuration can still create different outputs.

REPLAY freezes evidence, not every semantic token.

The thesis therefore claims evidence reproducibility, not perfect bitwise reproducibility.

## 9.9 Generator Dependence

All final responses come from one generator.

This improves internal consistency.

It limits external validity.

The observed Vericult outcome distribution may depend strongly on GPT-OSS response style.

A different generator could produce:

- shorter answers;
- more refusals;
- more stereotypes;
- fewer factual claims;
- more cautious language.

Future work should repeat the experiment with several generators.

## 9.10 Response-Length Cap

The generator uses a 1200-token maximum.

Many External120 and Redteam120 responses reach that cap.

A truncated response can create problems:

- unfinished reasoning;
- incomplete caveats;
- claims without later qualification;
- more material targets than the verifier budget.

This is a property of the frozen final corpus and must be considered when interpreting individual cases.

## 9.11 No Final Human Gold for the 360 GPT-OSS Responses

This is the most important limitation of the final comparative evaluation.

The existing human annotations apply to old PLT30 Best-of-4 responses.

They do not apply to the newly generated GPT-OSS responses.

Without new human annotation of the final responses, the thesis cannot report final Vericult accuracy against human ground truth.

It can report system behaviour, agreement with baselines and trace-backed analysis.

Any stronger correctness claim would require a new independent annotation study.

## 9.12 Pilot Annotator Sample

The earlier human pilot used only five students.

The panel was useful for development but is not representative of all cultures in the dataset.

The low agreement also demonstrates that cultural appropriateness is a difficult subjective construct.

The pilot should therefore be treated as exploratory.

## 9.13 Baseline Comparability

The reward model and direct judge are different kinds of evaluators.

Skywork returns a scalar preference reward.

Vericult returns categorical outcomes plus dimensions and evidence.

A direct judge can be configured to use the same categories, but it still has a different architecture.

Comparisons should therefore separate:

- output agreement;
- coverage;
- runtime;
- diagnostic information.

A single “winner” metric may hide important differences.

## 9.14 CARB Is Not a Head-to-Head Baseline

CARB uses a different dataset and Best-of-N task.

Its published scores cannot be compared directly with Vericult percentages.

The thesis uses CARB as related work and motivation for culturally aware evaluator research.

## 9.15 Benchmark Leakage

The final configuration blocks known benchmark hosting locations.

This reduces direct leakage.

It cannot guarantee that benchmark content is absent from:

- mirrors;
- copied blog posts;
- search snippets;
- model pre-training data.

Leakage control is therefore a mitigation, not a proof of complete isolation.

## 9.16 Temporal Validity

Culture and formal rules change.

A response that is appropriate in 2026 may become outdated.

This is particularly important for:

- policy;
- law;
- institutional procedure;
- language use;
- identity terminology.

The LIVE evidence snapshot records one point in time.

Future users should not assume that the frozen result remains current indefinitely.

## 9.17 Political and Historical Disputes

Some prompts concern contested political or historical questions.

External evidence may reflect institutional or geopolitical viewpoints.

Vericult can record conflict and scope, but it cannot turn a contested political narrative into an objective cultural fact.

Such cases require especially careful qualitative analysis.

## 9.18 Language Coverage

The final dataset includes multilingual material, but the verifier backbone and web search environment may still perform unevenly across languages.

Translation or English-language sources can lose pragmatic detail.

A stronger future design would use multilingual retrieval strategies and local-language source evaluation.

## 9.19 Efficiency

Vericult is much more expensive than a one-call direct judge.

One item may require multiple semantic calls and several searches.

This limits real-time deployment.

The thesis therefore treats efficiency as part of the trade-off.

A verifier that is slightly more interpretable but hundreds of times slower would not automatically be useful in every application.

## 9.20 Privacy and Deployment

The research experiment sends prompts and responses to external inference and search services.

A production verifier for sensitive user data would require:

- privacy review;
- data-retention controls;
- provider agreements;
- possibly local models and retrieval.

These deployment concerns are outside the empirical scope of this thesis.

## 9.21 Summary

The main validity threats are not hidden edge cases.

They are central to the problem:

- culture is difficult to operationalize;
- evidence is uneven;
- human judgments can disagree;
- retrieval can miss sources;
- the semantic model can make mistakes;
- the final corpus has one generator;
- final response-level human gold is absent.

The contribution of Vericult should therefore be interpreted as a structured and auditable verification approach, not as a solved universal cultural oracle.
