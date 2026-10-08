# 2. Background and Foundations

This chapter introduces the concepts needed to understand the problem and the proposed solution. The aim is not to review every paper on cultural NLP. That is done in Chapter 3. Instead, this chapter explains the technical ideas that are used later in the Vericult design and experiment.

## 2.1 Large Language Models and Post-Training Alignment

A large language model learns statistical patterns over text and produces a probability distribution over possible next tokens. Modern instruction-following models are usually not used directly after pre-training. They go through additional post-training so that their outputs better follow human instructions and preferred behaviour.

A common historical example is reinforcement learning from human feedback (RLHF). In the InstructGPT work, human demonstrations were used for supervised fine-tuning, human preference comparisons were used to train a reward model, and the policy was then further optimized with reinforcement learning [Ouyang et al., 2022]. Later systems use several related techniques, but the general principle remains important: a model is not simply trained to predict text. It is also shaped by an operational signal describing desirable behaviour.

This matters for cultural evaluation because the signal is always incomplete. A preference dataset reflects the people, tasks and instructions used to collect it. Even when an aligned model is helpful in general, it may still make assumptions that fit one social setting better than another. A model can also learn to avoid obviously offensive language while still producing subtle cultural errors.

The challenge becomes clearer when the user request involves norms rather than simple facts. Consider a factual question such as the capital of a country. There is usually one straightforward answer. Now consider a question asking how formal a first email to a professor should be, what gift is appropriate for a host family, or how to describe a disputed historical memory. These questions depend on relationships, location, institutional setting, social expectations and sometimes personal preference.

For that reason, this thesis separates general alignment from **cultural appropriateness**. General alignment concerns broad model behaviour such as helpfulness, safety and instruction following. Cultural appropriateness asks whether a response is suitably adapted to the cultural context that is actually relevant to the request.

## 2.2 Preference Alignment and Reward Models

Reward models are one important part of modern alignment pipelines. A typical reward model receives a prompt and response and assigns a scalar score representing learned preference. In pairwise settings, the score can be used to predict which of two responses is preferred. During training, the reward model can guide optimization of the generator. During evaluation, it can also be used as an automated judge.

The advantage of a reward model is efficiency. Once the model is loaded, many prompt-response pairs can be scored without external search. It provides a common scalar that is useful for ranking.

However, the meaning of the scalar depends on the data and objective used to train the reward model. It does not automatically mean “culturally appropriate.” RewardBench was introduced because reward models themselves need careful evaluation. Its datasets contain prompt, chosen-response and rejected-response examples across areas such as chat quality, reasoning and safety [Lambert et al., 2025]. The work shows that reward-model evaluation is not trivial and that different reward models have different strengths and weaknesses.

CARB makes this point more specific to culture. It evaluates reward models on culturally situated preference judgments across several cultures and cultural domains and proposes a “Think-as-Locals” approach for generative reward models [Zhang et al., 2026]. CARB is important for this thesis because it shows that cultural awareness is relevant not only for generators but also for evaluators.

Vericult is deliberately different from a reward model. It does not learn one scalar preference function from labelled comparisons. Instead, it performs a structured verification process on one response. A reward model is therefore used as an independent baseline, not as a component inside Vericult.

The distinction is important for scientific interpretation. If Vericult and a reward model agree, this does not prove that they are correct. If they disagree, the disagreement must be examined. The value of Vericult is partly that its evidence and intermediate decisions can be inspected.

## 2.3 LLM-as-a-Judge

Another widely used evaluation method is to ask a strong language model to judge the output of another model. This is commonly called **LLM-as-a-judge**.

Zheng et al. (2023) studied LLM judges through MT-Bench and Chatbot Arena. They showed that strong LLM judges can correlate well with human preferences in some settings, making them a practical evaluation tool. At the same time, they reported evaluator effects including position, verbosity and self-enhancement bias.

Wang et al. (2024) investigated position bias in more detail. They showed that changing the order of candidate answers can change the judgment of an LLM evaluator. This is especially relevant in Best-of-N experiments where candidates are shown side by side.

A direct LLM judge has several advantages:

- it is simple to implement;
- it can use natural-language evaluation criteria;
- it can return a short explanation;
- it does not require a separately trained reward model;
- it can evaluate open-ended responses.

Its main limitation for the present thesis is that it still relies primarily on the model's internal knowledge unless retrieval is added. If the judge itself has a mistaken cultural belief, the explanation may sound convincing while remaining unsupported. A direct judge also does not automatically separate factual cultural claims from values or internal response quality.

Vericult uses an LLM as a semantic engine inside the pipeline, so it is not free from LLM judgment. The difference is architectural. The semantic model is constrained to specific stages and schemas, while evidence retrieval and frozen support quotes are used where the target is externally checkable.

This distinction should not be overstated. Vericult does not eliminate model bias simply by splitting a judgment into several calls. The same backbone is used for semantic stages. The purpose of decomposition is to create clearer interfaces, allow external evidence to enter, and make failure locations easier to inspect.

## 2.4 Culture as a Computational Construct

The word **culture** is broad and contested. A major problem in cultural NLP research is that papers often study one part of culture without defining the whole concept.

Adilazuarda et al. (2024) surveyed more than 90 studies on culture in LLMs. They observed that work often uses proxies for culture instead of one explicit definition. Their analysis separates demographic and semantic proxies and shows that some aspects are much more studied than others.

Liu et al. (2025) provide a more detailed taxonomy of culturally aware and culturally adapted NLP. Their survey stresses that culture includes both ideational elements such as values and beliefs and social interaction. This is useful for the present thesis because Vericult needs to evaluate both what a response says about a cultural practice and how it handles an interaction.

Two consequences follow.

First, culture should not be equated with nationality. A country may contain many linguistic, religious, ethnic and regional communities. The same community may also exist across borders. A prompt can involve a workplace culture, a religious practice, a local dialect or a historical memory without making nationality the most important variable.

Second, cultural variation must be treated as normal rather than as noise. Statements such as “people in culture X always do Y” should require strong justification. In many cases a more accurate description is that a practice is common in some settings, associated with a particular region, or dependent on generation, institution or relationship.

For this reason, the thesis uses an operational definition:

> Cultural appropriateness is the degree to which a response handles the culturally relevant parts of a stated context accurately, respectfully and with suitable attention to variation, institutional constraints and uncertainty.

This definition is deliberately practical. It is not a philosophical definition of culture. It describes what the verifier is expected to judge.

## 2.5 Cultural Knowledge, Cultural Adaptability and Cultural Appropriateness

Three related concepts should be separated.

### Cultural knowledge

Cultural knowledge concerns whether a model knows information about a cultural context. BLEnD and CulturalBench are examples of benchmarks that strongly involve cultural knowledge.

A model can know that a practice exists without giving appropriate advice about it.

### Cultural adaptability

Cultural adaptability concerns whether the model can change its response when the cultural context changes. NormAd explicitly studies this problem by varying how much cultural information is supplied.

A model may have the relevant knowledge but fail to apply it correctly to a specific user situation.

### Cultural appropriateness

Cultural appropriateness is the focus of this thesis. It concerns the final response in context.

An answer can be factually correct but culturally inappropriate. For example, a model could correctly identify a sacred object but still suggest using it as a joke. The factual statement is correct; the recommendation is not appropriate for the context.

The reverse can also occur. A response can be polite and non-offensive while containing a wrong factual claim. The verifier therefore needs to consider both external accuracy and contextual handling.

## 2.6 Descriptive Practices, Norms, Values and Formal Rules

A recurring source of cultural error is the collapse of different kinds of statements into one category. Vericult therefore relies on several conceptual distinctions.

### Descriptive practice

A descriptive practice states what people often do.

Example:

> Guests often bring a small gift.

This does not mean that every guest must bring one.

### Social norm

A social norm expresses an expectation in a social setting.

Example:

> It is generally considered polite to wait for the host before beginning.

The strength of the norm can vary by context.

### Pragmatic convention

A pragmatic convention concerns how language functions socially.

Example:

> A direct translation may sound too informal in a first professional email.

The wording itself can be grammatically correct while the register is inappropriate.

### Value

A value concerns what a person or community considers important or desirable.

Values can differ within the same society. Evidence can describe value distributions, but a search result does not make one value morally correct.

### Institutional or legal rule

A formal rule is created by a recognized institution or legal authority.

Example:

> A certain document is legally required for a procedure.

This should not be inferred from an etiquette blog or a social custom.

The difference between these categories matters for source selection. A government source can be suitable for a legal requirement but less useful for describing ordinary family practice. A community discussion may be useful for lived experience but should not be treated as proof of a binding law.

## 2.7 Cultural Essentialism and Overgeneralization

**Essentialism** means treating a group as if its members share one fixed set of properties. In cultural evaluation, essentialism often appears through statements such as:

- “All people from this country are indirect.”
- “This religion always requires X.”
- “Women in this culture prefer Y.”
- “This ethnic group is naturally family-oriented.”

Such claims remove internal diversity and can turn statistical tendencies or stereotypes into categorical rules.

The problem is not solved by avoiding every group-level statement. Cultural analysis often requires discussion of recurring patterns. The important issue is calibration.

A careful response may say:

> This practice is common in some settings, but individual families differ.

This preserves useful cultural information while acknowledging variation.

Vericult reflects this principle in several places. Verification questions include a scope or variation question. Evidence memos distinguish tendencies from context-sensitive practices. Scoring instructions tell the model not to turn a common practice into a universal obligation.

## 2.8 Pluralism and Disagreement

Cultural evaluation can involve genuine disagreement. Sorensen et al. (2024) argue for pluralistic alignment and distinguish different ways in which AI systems can represent multiple reasonable perspectives.

This is relevant because not every disagreement can be resolved by finding a more authoritative source. Consider a prompt about whether family obligation should take priority over individual independence. Survey data can show how opinions vary. It cannot prove one moral position universally correct.

For such cases, cultural appropriateness may depend on whether the response fairly represents the conflict rather than whether it chooses one side.

The D04 dimension, “Values, ethics and moral pluralism,” is designed for this kind of issue. A response can score well by explaining competing values without claiming that one majority view represents everyone.

This also supports the use of abstention. If the evaluator lacks a defensible basis for a judgment, abstention is preferable to inventing certainty.

## 2.9 Retrieval-Augmented Evidence

Retrieval-augmented generation (RAG) combines a language model with external information retrieval. Lewis et al. (2020) introduced a widely cited formulation in which a generator uses retrieved documents as non-parametric memory.

Vericult is not a standard RAG generator because it does not retrieve information to answer the user directly. Retrieval is used for **verification**.

The basic pattern is:

1. identify a material proposition;
2. create neutral questions about that proposition;
3. search for relevant evidence;
4. summarise the evidence and its scope;
5. freeze the evidence;
6. compare the original response with the frozen evidence.

This design has two intended benefits.

First, it makes some cultural judgments less dependent on the verifier model's parametric memory.

Second, it creates explicit artifacts that can be inspected later.

However, retrieval does not automatically solve the problem. Search engines can return low-quality sources. Search results can reflect popularity rather than representativeness. English-language search can overrepresent some groups. Some local practices are documented mainly in community sources rather than academic or official sources. These limitations are discussed again in Chapter 9.

## 2.10 Evidence Sufficiency

Evidence quality is not the same as evidence quantity.

Three weak blog posts repeating each other should not necessarily outweigh one direct legal source when the question concerns law. Similarly, one government website may not be sufficient to describe how all families behave in daily life.

Vericult therefore records both source type and evidence sufficiency.

The main evidence states are:

- **sufficient** — the available sources provide a usable basis for the question;
- **conflicting** — useful evidence exists but materially disagrees;
- **insufficient** — the evidence does not provide a defensible basis.

This is separate from the final target verdict:

- supported,
- contradicted,
- mixed,
- insufficient.

A target can be mixed because reliable evidence supports part of the response but contradicts another part. Missing evidence should not be interpreted as contradiction.

## 2.11 Selective Prediction and Abstention

In machine-learning evaluation, a system may be allowed to abstain when confidence or evidence is insufficient. Selective classification studies the trade-off between predictive coverage and error when a classifier can reject difficult examples [Geifman and El-Yaniv, 2017].

Vericult uses a related idea, but not a learned confidence threshold. An applicable D01–D10 dimension can receive:

- 0,
- 1,
- 2, or
- abstain.

Abstention is used when the system does not have a defensible basis for scoring that dimension.

This avoids a common problem with midpoint scores. A score of 1 means the response is mixed, incomplete or limited. It should not also mean “we do not know.” Keeping uncertainty separate makes the output easier to interpret.

## 2.12 Evaluation Contamination

External retrieval creates a special risk in benchmark experiments. The verifier could retrieve the benchmark itself, an annotation file, an answer key, or a repository containing expected outputs.

Research on benchmark contamination shows why this matters. Deng et al. (2024) study overlap between benchmark test data and model training data and show that contamination can inflate apparent performance.

The Vericult problem is different but related. Even if the verifier model was not trained on the benchmark, live search could directly expose benchmark content during evaluation.

The final experiment therefore excludes known benchmark hosting locations from the evidence pipeline. For External120, `huggingface.co` is blocked because several source datasets are hosted there. The ThaiCLI repository is also excluded. The thesis repository itself and common annotation/result paths are blocked.

These controls reduce known leakage. They cannot guarantee that no mirror or copied benchmark item exists elsewhere on the web.

## 2.13 Reproducibility with Changing Web Evidence

Live web retrieval creates temporal variability. A search result available today may disappear tomorrow. Rankings may change. Search providers may update their indexing.

For this reason, the final experiment separates **LIVE** and **REPLAY**.

LIVE mode performs the actual web search and stores the documents and schedules used.

After all LIVE cases are complete, an audit script verifies the expected traces and evidence files and records their hashes.

REPLAY mode then uses the frozen evidence. It does not perform a new live search when evidence is missing.

This does not make the whole system deterministic. The semantic LLM stages still execute. Temperature is set to zero, but remote model infrastructure can still introduce small variation. The important point is narrower: the evidence base is fixed.

## 2.14 Human Judgment as Reference Rather than Absolute Ground Truth

Cultural appropriateness can be subjective, and human annotators can disagree for legitimate reasons.

Plank (2022) argues that human label variation should not automatically be treated as annotation noise. In subjective tasks, multiple interpretations may be reasonable.

This lesson became visible during the development of Vericult. An earlier pilot used five student annotators to judge 30 Best-of-4 items. Agreement was low. The study is discussed later as development evidence, not as final ground truth.

The final 360 responses were generated after that pilot. The old annotations refer to different responses and therefore cannot be reused as labels.

This is methodologically important. A convenient label is not valid simply because it exists. The thesis therefore distinguishes three things:

1. old human annotations for old candidate responses;
2. final machine predictions for new GPT-OSS responses;
3. any future human evaluation of those final responses.

## 2.15 Summary

The central background concepts can now be combined.

Cultural appropriateness is context-dependent and often plural. Reward models and direct LLM judges provide useful automated evaluation, but their scores do not automatically provide external cultural evidence. Retrieval can provide evidence for some claims, but source quality and scope matter. Abstention is needed when evidence is insufficient. Finally, live evidence must be controlled if the experiment is intended to be reproducible.

These principles lead directly to the literature review in Chapter 3 and the operational D01–D10 framework in Chapter 4.
