# 1. Introduction

## 1.1 Motivation

Large language models (LLMs) are now used for tasks that go far beyond factual question answering. People ask them how to write an email to a professor, how to behave at a family dinner, how to prepare a gift for a colleague, how to discuss a religious practice, how to describe a historical conflict, or how to adapt a message for a particular audience. In such cases, the usefulness of the answer depends not only on grammar and factual accuracy. It also depends on whether the response fits the cultural and social context in which it will be used.

This is easy to underestimate because many cultural failures do not look like obvious model errors. A sentence can be fluent and confident and still be inappropriate. For example, a model may describe a regional custom as if it were followed by everybody in a country. It may treat a social tendency as a binding rule. It may recommend an informal form of address in a setting where the relationship is formal. It may give a historically insensitive suggestion while the factual details around it are correct. It may also use a broad identity label in a way that hides important differences inside a community.

Research on cultural behaviour in NLP has grown quickly in recent years. Surveys by Adilazuarda et al. (2024) and Liu et al. (2025) show that there is no single agreed computational definition of culture. Existing work studies different proxies such as values, everyday practices, language, social interaction, identity, religion or institutions. This diversity is important because it shows why a single nationality label is not enough to represent cultural context.

Several benchmarks have demonstrated that LLM performance differs across cultural settings. BLEnD studies everyday cultural knowledge in multiple countries and languages [Myung et al., 2024]. CulturalBench uses human-written and human-verified questions across many regions and topics [Chiu et al., 2025]. NormAd studies whether models can judge social acceptability when different amounts of cultural context are provided [Rao et al., 2025]. SafeWorld focuses on geographically diverse safety and legal expectations [Yin et al., 2024]. CARB studies whether reward models make culturally aware preference judgments across several cultures and domains [Zhang et al., 2026]. Together, these works provide strong evidence that cultural evaluation is a real and separate challenge.

However, benchmark performance is not the same as verifying one concrete answer produced for one concrete user. A benchmark often asks whether a model knows a fact, selects a correct option, follows a social norm, or prefers one response over another. In practice, a user may already have one generated response and want to know whether it is culturally appropriate and why.

This thesis focuses on that post-hoc verification problem.

The central idea is simple: if an LLM response makes an important cultural claim or recommendation, the evaluator should not have to rely only on another model's internal knowledge. Where the claim is externally checkable, the evaluator should be able to retrieve relevant evidence, inspect the scope of that evidence, distinguish strong from weak sources, and preserve uncertainty where the evidence is not sufficient. At the same time, not every cultural question can be resolved through web search. Some issues concern values, tone, stereotypes or the way a response handles explicit context. A useful verifier therefore needs both evidence-grounded checking and direct contextual assessment.

This motivates **Vericult**, the system developed in this thesis. Vericult is a standalone verifier. It is not a reward model and it is not part of the generator. It receives a fixed prompt and a fixed response after generation has already happened. It then evaluates the response through a structured pipeline.

The design is also motivated by auditability. A scalar reward such as 0.72 can be useful for ranking, but it does not explain what cultural issue was found, what evidence was used, or whether the evaluator was uncertain. Vericult therefore stores intermediate artifacts such as the extracted context, selected dimensions, material response targets, verification questions, retrieved documents, evidence memos, target verdicts and final scores.

The goal is not to claim that web evidence creates an objective answer for every cultural question. Culture is often plural, changing and disputed. The goal is narrower: to test whether a structured and evidence-aware process can make cultural evaluation more transparent and reproducible.

## 1.2 Problem Statement

The technical problem studied in this thesis can be expressed as follows.

Given:

- a user prompt (p), and
- one generated response (r),

the system should decide whether (r) is culturally appropriate for the situation described by (p).

This apparently simple task contains several separate problems.

First, the relevant context must be identified. A model should not infer that a person belongs to a religion because of a name, infer a location because of a nationality, or invent a relationship that was not stated. The verifier therefore needs a strict separation between explicit prompt information and assumptions.

Second, the system must determine whether the prompt is materially cultural at all. The word *culture* may appear in a prompt without cultural reasoning being necessary. Running a complex cultural pipeline on every prompt would create false positives and unnecessary cost.

Third, the response may contain several statements, but not all of them are equally important. A verifier that tries to fact-check every sentence will spend resources on irrelevant details. The system therefore needs to identify a small number of material targets that could change the cultural judgment.

Fourth, different target types require different treatment. Consider the following examples:

- “This law requires X” is an external factual claim.
- “Guests usually remove their shoes” is a descriptive cultural norm.
- “You should bring this gift” is a context-dependent recommendation.
- “The response ignores the user's stated preference” is an internal response-quality issue.
- “This value is more important than that value” may be a non-verifiable value judgment.

It would be wrong to handle all five cases as ordinary factual search questions.

Fifth, external evidence itself can introduce bias. If the retrieval system directly sees the exact candidate claim and is told to prove or disprove it, search and synthesis may become directional. If benchmark answer files or repositories are retrieved, evaluation may also become contaminated. The verifier therefore needs a controlled evidence boundary and explicit leakage filtering.

Sixth, cultural evidence can be incomplete or contradictory. Different communities, regions and generations may follow different practices. A system that always forces a yes/no decision can turn missing evidence into false certainty. Abstention and evidence sufficiency therefore need to be first-class outcomes.

Finally, the complete experiment must be reproducible. Live web search changes over time. Search rankings, pages and snippets may differ from one day to the next. If the evidence used in the final evaluation is not frozen, it becomes difficult to reproduce the experiment later.

These requirements lead to the main research problem:

> How can a standalone system verify the cultural appropriateness of an LLM response in a way that is contextual, evidence-aware, uncertainty-sensitive and auditable?

## 1.3 Research Gap

Existing work covers important parts of this problem, but the combination studied here remains less explored.

Cultural benchmarks mainly evaluate model capability. BLEnD measures everyday cultural knowledge. CulturalBench tests cultural knowledge through human-written questions. NormAd evaluates social acceptability under cultural context. SafeWorld studies geo-diverse safety. These benchmarks are valuable, but they are designed around fixed benchmark tasks rather than around a general post-hoc verifier for arbitrary free-form responses.

A second group of methods aims to improve the generator. CultureLLM fine-tunes models with culture-related data [Li et al., 2024]. CultureBank creates a community-driven cultural knowledge resource and also studies fine-tuning [Shi et al., 2024]. Other work uses retrieved cultural or value information to improve generation. These methods change how the answer is produced. Vericult instead evaluates an answer after it has already been generated.

A third group concerns general evaluators. Reward models are trained to assign preference scores or distinguish preferred from rejected responses. RewardBench shows that reward-model evaluation is itself a substantial research problem [Lambert et al., 2025]. CARB directly studies cultural awareness in reward models and demonstrates that preference evaluation can be culturally sensitive [Zhang et al., 2026]. Reward models are therefore a highly relevant comparison. However, a reward score is not designed to provide a full external evidence trace for every judgment.

Direct LLM judges are another important baseline. They are flexible and can give natural-language reasons, but previous work has shown evaluator effects such as position bias and sensitivity to prompt formulation [Zheng et al., 2023; Wang et al., 2024]. A direct judge can also make the same unsupported cultural assumptions as the model it evaluates.

The gap addressed in this thesis is therefore not “culture has never been evaluated before.” That would be false. The narrower gap is the design and assessment of a **standalone post-hoc cultural verifier** that combines:

1. explicit prompt context,
2. a multidimensional cultural rubric,
3. material target selection,
4. neutral evidence questions,
5. a structural separation between evidence gathering and final response comparison,
6. external retrieval for suitable target types,
7. source and contamination controls,
8. explicit abstention,
9. evidence freezing, and
10. detailed traces for later audit.

This thesis does not assume in advance that this design is better than a reward model or a direct LLM judge. It implements the design and evaluates its behaviour.

## 1.4 Research Questions

The final thesis uses four research questions.

### RQ1 — Verification behaviour

**How does Vericult classify culturally situated LLM responses across diverse cultural, linguistic and challenge settings?**

This question focuses on the final 360 prompt-response pairs. It includes outcome distributions, dimension scores, evidence coverage and abstention.

### RQ2 — Comparison with simpler evaluators

**How do Vericult's judgments compare with an independent reward-model baseline and a direct LLM judge on the same fixed responses?**

This question concerns agreement, disagreement and coverage between evaluation systems. It does not automatically imply that one system is correct when they disagree.

### RQ3 — Diagnostic value of evidence grounding

**What additional diagnostic information is provided by Vericult's target-level evidence, source handling, dimension scores and abstention behaviour?**

This question addresses the main design motivation. Even if two systems return the same final label, Vericult may provide a more inspectable basis for that label.

### RQ4 — Failure modes and limitations

**Which failure modes occur in context extraction, target selection, retrieval, evidence synthesis and scoring, and what do they imply for automated cultural verification?**

This question is important because a complex pipeline can fail for reasons that are different from cultural misunderstanding. For example, a retrieval timeout and a wrong cultural claim should not be treated as the same type of error.

The earlier Best-of-4 experiment with PLT001–PLT030 is not the final answer to these questions. It remains useful as development history and as evidence about the difficulty of human cultural annotation, but its labels refer to different candidate responses and cannot be transferred to the final GPT-OSS responses.

## 1.5 Contributions

The thesis makes the following contributions.

### 1. A practical D01–D10 cultural framework

The thesis defines ten operational dimensions for judging culturally situated responses:

- D01 Everyday life and material culture
- D02 Language, discourse and pragmatics
- D03 Social etiquette and interpersonal norms
- D04 Values, ethics and moral pluralism
- D05 Law, policy and institutional rules
- D06 Religion, ritual and taboo
- D07 Family, kinship, gender and generations
- D08 Work, education and civic participation
- D09 Cultural heritage, history, arts and collective memory
- D10 Identity, diversity and intergroup relations

These dimensions are a research instrument. They are not presented as a universal definition of culture.

### 2. The Vericult verification pipeline

The thesis implements a complete verifier that moves from prompt context to evidence-grounded target checking and dimension-level scoring. It supports absolute single-response judgments rather than requiring a Best-of-N comparison.

### 3. Candidate-blind evidence handling

The candidate response is used to form material targets and verification questions, but the later evidence-retrieval and evidence-memo stages operate through a restricted interface that does not receive the candidate response or target object. This does not make the whole pipeline blind, because question generation has already seen the target. It creates a narrower and testable separation between evidence construction and final candidate comparison.

### 4. LIVE and REPLAY evidence control

LIVE mode collects and stores web evidence. The evidence is then audited and frozen. REPLAY reuses the frozen search schedule and evidence without falling back to live retrieval. This reduces one major source of experimental variation.

### 5. A 360-item final evaluation package

The final experiment contains three different 120-item corpora and regenerates every response with one common model and one common sampling configuration. This removes the earlier mixture of response generators from the main experiment.

### 6. Reproducibility and diagnostic traces

The implementation stores model configuration, hashes, prompt and response identities, semantic calls, evidence records, scores, errors and trace links. The aim is to make later inspection possible rather than reducing the experiment to one final percentage.

## 1.6 Scope and Non-Goals

Several boundaries are important.

Vericult is not a system for defining which culture is “correct.” It evaluates how a response handles a stated cultural context under an explicit rubric.

It is not a replacement for community consultation, domain experts or legal advice. A web-based verifier cannot fully represent lived cultural knowledge.

It is not a safety classifier for every possible harm. Some safety issues are culturally relevant and fall within the rubric, but general model safety is broader than this thesis.

It is also not a new reward model. Reward models are used only as independent comparisons.

Finally, the thesis does not treat a retrieval result as ground truth merely because it appears on the web. Source type, scope, disagreement and sufficiency are part of the evidence process.

## 1.7 Thesis Structure

Chapter 2 introduces the technical and conceptual background needed for the thesis, including LLM alignment, reward models, LLM-as-a-judge evaluation, cultural appropriateness and retrieval-based evidence.

Chapter 3 reviews related work in cultural benchmarking, cultural adaptation, reward-model evaluation and evidence-grounded reasoning. It then derives the narrower research gap addressed by Vericult.

Chapter 4 presents the D01–D10 operational framework and explains why distinctions such as tendency, norm, value and formal rule are important.

Chapter 5 describes Vericult in detail. It follows the pipeline from context extraction to cultural applicability, target extraction, neutral questions, candidate-blind evidence processing, memo freezing, target comparison and final scoring. It also explains the main implementation safeguards and includes selected repository code excerpts.

Chapter 6 defines the final experiment. It describes the three 120-item corpora, the common generator, the final Qwen3.6 verifier backbone, LIVE and REPLAY, leakage controls, baselines and the analysis plan.

Chapter 7 reports the final quantitative results. Values that are not yet available in the frozen outputs remain explicit placeholders in the current draft.

Chapter 8 discusses representative cases and failure modes. It focuses on what the traces show rather than only on aggregate metrics.

Chapter 9 describes threats to validity and technical limitations.

Chapter 10 summarizes the findings, answers the research questions and outlines future work.
