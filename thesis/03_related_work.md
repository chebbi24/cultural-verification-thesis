# 3. Related Work and Research Gap

This chapter reviews research that is directly relevant to Vericult. The aim is not to list every cultural NLP paper. Instead, the chapter compares the main ideas that shaped the thesis: cultural benchmarking, cultural adaptation, reward-model evaluation, direct LLM judging, evidence-grounded reasoning and pluralistic evaluation.

## 3.1 Cultural Evaluation of Language Models

Early work on cultural behaviour in language models often asked whether models reflect the values, beliefs or knowledge of different populations. This research is useful because it shows two recurring problems.

The first problem is **uneven representation**. A model trained heavily on English-language internet text may reflect some populations and cultural contexts better than others.

The second problem is **over-simplification**. It is tempting to represent culture only through a country or language label, but culture can also involve region, religion, age, profession, institutional setting and social relationship.

Durmus et al. (2023) studied how model responses compare with survey opinions from different countries. Their GlobalOpinionQA work showed that model outputs can be closer to the opinions of some populations than others, and that prompting for a country perspective does not always solve the problem.

Adilazuarda et al. (2024) reviewed a large body of culture-related LLM research and argued that studies often rely on proxies instead of defining culture directly. Their survey is important for this thesis because it makes clear that “cultural performance” is not one single measurement problem.

Liu et al. (2025) go further by proposing a taxonomy for culturally aware and culturally adapted NLP. Their work highlights the importance of social interaction as well as ideational elements such as values and beliefs.

The conclusion for Vericult is that a cultural verifier needs to avoid one-dimensional reasoning. It should not assume that one national label fully determines the appropriate answer.

## 3.2 BLEnD

BLEnD is a benchmark for everyday cultural knowledge across multiple countries and languages [Myung et al., 2024]. The benchmark was created with native speakers and covers daily-life categories such as food, family, education, work and celebrations.

The relevance of BLEnD is twofold.

First, it demonstrates that everyday cultural knowledge is a serious evaluation target. Many culturally inappropriate answers are not about rare historical facts. They concern ordinary social life.

Second, BLEnD shows that evaluation should include languages and regions beyond English-speaking Western settings.

BLEnD is still a benchmark with predefined questions and answers. It does not provide a general post-hoc verification process for arbitrary free-form model responses. Vericult therefore uses the same broad motivation but a different unit of evaluation.

## 3.3 CulturalBench

CulturalBench contains 1,696 human-written and human-verified cultural knowledge questions covering 45 regions and 17 topics [Chiu et al., 2025]. The authors use a human-AI red-teaming process to create challenging questions.

CulturalBench is especially relevant because it emphasizes human-written questions rather than automatically generated benchmark items. This reduces some common quality problems in synthetic cultural benchmarks.

The benchmark also illustrates the breadth of cultural topics. Cultural knowledge is not limited to national holidays or food. It includes topics such as etiquette and social practice.

For this thesis, CulturalBench supports the decision to use a broad operational framework rather than only one or two categories. However, Vericult does not directly adopt CulturalBench's topic taxonomy. D01–D10 were synthesized for a different purpose: response verification rather than question sampling.

## 3.4 NormAd

NormAd studies cultural adaptability rather than only factual knowledge [Rao et al., 2025]. Its NormAd-Eti benchmark includes 2.6k situations representing social etiquette norms across 75 countries. The framework varies how specific the cultural information is, ranging from abstract values to explicit social norms.

The reported results show that even strong models struggle when the cultural signal is abstract. Performance improves when the relevant norm is explicitly provided, but remains below human performance in the benchmark.

NormAd is important for Vericult because it highlights the difference between **knowing a norm** and **applying it under context**. It also motivates the need to preserve explicit context rather than infer it freely.

At the same time, NormAd focuses strongly on social acceptability and etiquette. Vericult needs to cover additional areas such as institutional rules, religious practice, language pragmatics, historical memory and identity.

## 3.5 SafeWorld

SafeWorld studies geo-diverse safety alignment [Yin et al., 2024]. The benchmark contains 2,775 test queries grounded in cultural norms and legal policies from 50 countries and hundreds of regions or racial groups.

This work is relevant because it directly combines culture with formal legal and safety constraints. It demonstrates why a response cannot always treat “culture” as a matter of informal preference. In some situations a local legal requirement materially changes what a safe or appropriate response should say.

This influenced the separation between D03 social etiquette and D05 law, policy and institutional rules in Vericult.

SafeWorld also shows a limitation of broad cultural evaluation: legal and cultural appropriateness can interact but are not the same thing. A response may be culturally considerate while legally wrong, or legally correct while socially insensitive.

## 3.6 CultureBank

CultureBank is a community-driven cultural knowledge base created from user self-narratives on TikTok and Reddit [Shi et al., 2024]. The resource contains many cultural descriptors and explicitly preserves multiple views rather than assuming one description per culture.

This is particularly relevant to Vericult's treatment of variation. Community evidence can contain valuable lived experience that is not well documented in official sources.

However, community sources also create evidence-quality problems. A forum post may describe one person's experience rather than a widespread norm. Vericult therefore includes a `community_insider` source class but does not treat it as automatically stronger or weaker than every other source. Its usefulness depends on the question.

## 3.7 CultureLLM

CultureLLM takes a generator-focused approach [Li et al., 2024]. It uses World Values Survey data and semantic augmentation to create culture-related training data, then fine-tunes culture-specific models and a unified model.

The paper reports improvements over several comparison models on culture-related datasets.

CultureLLM addresses a different stage of the problem. It tries to make the model generate more culturally adapted outputs. Vericult does not change the generator. It evaluates the output after generation.

The two approaches could be complementary in future work. A system like Vericult could be used as an external diagnostic layer for a culture-adapted generator, but this thesis does not train the generator using Vericult feedback.

## 3.8 Diverse Human Value Alignment Through Ethical Reasoning

Wang et al. (2025) propose a structured ethical reasoning process for diverse human value alignment. Their framework includes five stages: gathering contextual facts, identifying social norms, generating possible actions, evaluating options through ethical perspectives, and reflection.

This work is useful because it shows that decomposition can help cultural and value reasoning. Instead of producing one immediate judgment, the model is guided through explicit intermediate steps.

Vericult shares the broad idea that difficult cultural judgments benefit from structure. However, the two systems are different.

The ethical-reasoning framework is designed to improve the model's reasoning or generation.

Vericult is a post-hoc verifier. It also adds an external evidence stage and freezes the evidence before the original target is reintroduced.

## 3.9 CARB: Cultural Awareness in Reward Models

CARB is one of the most directly relevant works for this thesis because it evaluates the cultural awareness of reward models [Zhang et al., 2026].

The benchmark covers 10 cultures and four cultural domains:

- cultural commonsense knowledge,
- cultural values,
- cultural safety,
- cultural linguistics.

CARB uses a Best-of-N preference-selection setup. A reward model receives a prompt and several candidate responses and should assign the highest score to the culturally appropriate response.

This design is valuable because it tests the evaluator rather than only the generator. It asks whether a reward model can recognize culturally appropriate behaviour.

The CARB paper reports several important findings. First, current reward models show uneven cultural performance. Second, benchmark performance is positively related to downstream multilingual cultural alignment tasks. Third, robustness experiments suggest that some reward models rely on superficial cues such as language patterns or explicit cultural labels rather than deeper cultural concepts.

To reduce these shortcuts, the authors propose **Think-as-Locals**. Instead of producing only a reward score, a generative reward model first creates culturally grounded evaluation criteria and then makes the final judgment. The method is optimized with reinforcement learning from verifiable rewards.

### 3.9.1 Why CARB matters for Vericult

CARB strongly motivates the thesis for three reasons.

First, it confirms that evaluator cultural awareness is a separate research problem.

Second, it provides a meaningful reward-model comparison family.

Third, it suggests that explicit intermediate criteria can improve cultural judgment.

### 3.9.2 Why Vericult is not a reproduction of CARB

The final Vericult experiment is not a CARB reproduction.

CARB asks a reward model to choose a preferred answer among multiple candidates.

Vericult evaluates one response at a time.

CARB is primarily a reward-model benchmark.

Vericult is a verification pipeline with evidence retrieval, source handling, abstention and trace generation.

For this reason, CARB results are discussed as related work rather than copied into the final comparison table as if the numbers were directly comparable.

## 3.10 RewardBench and General Reward-Model Evaluation

RewardBench was created to compare reward models on structured preference tasks [Lambert et al., 2025]. It includes difficult examples across chat, safety, reasoning and related categories.

The benchmark is relevant because it shows that reward models can fail even when the preferred response is objectively better for reasons such as correctness or instruction following.

The main lesson for Vericult is methodological. A reward model should not be treated as a gold standard simply because it outputs a numerical score.

The final thesis uses Skywork-Reward-V2-Qwen3-4B as an independent reward-model baseline. Its score is not used inside Vericult.

## 3.11 Direct LLM Judges

LLM-as-a-judge methods provide a simpler alternative to reward models. Zheng et al. (2023) show that strong LLM judges can agree well with human preferences in some general evaluation settings.

However, several biases have been documented.

A judge may prefer the answer shown in a particular position.

It may reward longer responses.

It may favour outputs that resemble its own style.

Wang et al. (2024) show that candidate ordering can materially change evaluation results.

For Vericult, this supports the use of a direct LLM judge as a baseline rather than as ground truth.

The direct judge tests an important alternative hypothesis:

> Is the full Vericult pipeline necessary, or can a strong model simply read the prompt and response and make an equally useful cultural judgment?

The final analysis should therefore compare not only labels but also what diagnostic information is available when systems disagree.

## 3.12 Retrieval-Augmented Cultural or Value Alignment

Several lines of work use retrieval to provide external cultural or value context to a language model.

The general RAG idea comes from work such as Lewis et al. (2020), where external documents are retrieved and supplied to the generator.

CultureBank can also be used as an external cultural resource.

Other research retrieves value-related context to improve generation.

The central difference in Vericult is that retrieval is used for **verification**, not to generate the final user answer.

This changes the question from:

> What context should help the model answer?

to:

> What external evidence is needed to test the claims and recommendations already present in this answer?

This distinction is important because a verifier should preserve the original response rather than silently rewrite it.

## 3.13 Evidence-Grounded Verification

General factual verification systems often decompose claims, retrieve documents and classify support. Vericult borrows this broad pattern but adapts it to cultural evaluation.

Three adaptations are necessary.

### Scope

A cultural statement may be true only for a region, generation or social setting. Evidence must therefore be checked for scope.

### Variation

Evidence that one practice exists does not prove that it is universal. Vericult uses a second verification question specifically to search for variation.

### Epistemic type

Not every cultural issue is factual. Values and internal response quality cannot always be resolved through external evidence.

These differences mean that ordinary fact-checking is not sufficient by itself.

## 3.14 Human Annotation and Disagreement

Human evaluation is often used as a reference for culturally sensitive tasks. However, cultural judgments can show high disagreement.

Plank (2022) argues that label variation can reflect legitimate differences rather than mere annotation error. This is especially relevant to cultural appropriateness.

During Vericult development, five students evaluated the original 30 PLT Best-of-4 items. The low agreement in this small panel was itself informative. It demonstrated that cultural appropriateness can be difficult to collapse into one winner.

However, those annotations refer to old Llama-3.2 candidate responses. The final experiment uses new GPT-OSS responses. Reusing the old labels would be invalid.

The final report therefore keeps the pilot human study as development history rather than claiming that it is a gold standard for the final 360 items.

## 3.15 Benchmark Contamination and Leakage

When a verifier can search the web, benchmark leakage becomes a direct experimental risk.

Deng et al. (2024) show that benchmark contamination can affect LLM evaluation more generally.

In Vericult, the risk is even easier to understand: the retrieval system could search and find the exact benchmark record.

The final configuration blocks known benchmark hosting locations before evidence synthesis.

This does not guarantee zero contamination. Copies and mirrors can exist. The goal is to reduce direct, known leakage and make the exclusion policy explicit.

## 3.16 Summary of the Research Gap

The literature shows substantial progress in cultural evaluation, but the exact system studied in this thesis sits between several existing areas.

Cultural benchmarks provide structured test sets.

Culture-adaptation methods improve generators.

Reward models provide preference scores.

Direct judges provide flexible automated evaluation.

Retrieval methods provide external evidence.

Human studies provide subjective reference judgments.

What remains useful to investigate is a **single-response, post-hoc verifier** that combines these ideas without turning into one of them.

The research gap can therefore be stated more precisely.

Existing methods do not, as a common default, provide all of the following in one evaluation pipeline:

- prompt-only explicit context extraction;
- a multi-dimensional cultural rubric;
- material target selection from the response;
- different handling for facts, norms, recommendations and values;
- neutral evidence questions;
- a structural evidence boundary;
- bounded retrieval;
- source-type classification;
- evidence-scope and variation analysis;
- benchmark-leakage filtering;
- evidence freezing before final comparison;
- dimension-level abstention;
- a single-response cultural outcome; and
- a complete machine-readable trace.

This list does not prove that the combined design is better. It defines the design that the thesis implements and evaluates.

The next chapter explains the D01–D10 cultural framework used to make these judgments operational.
