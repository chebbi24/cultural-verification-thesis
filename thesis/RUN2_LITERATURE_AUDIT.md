# Run 2 - Literature Inventory and Source Validation

## Scope

This run validates the literature base and maps sources to thesis claims. It deliberately does **not** draft Chapters 2 or 3 yet. The aim is to prevent citation drift, version mismatches, and unsupported claims before prose is written.

## Source-selection rule

Priority is given to final peer-reviewed proceedings or official institutional publications. ArXiv is retained only where a final publication is unavailable or where the arXiv record is itself the canonical source. When a final published version differs numerically from an earlier preprint, the final published version is authoritative for the thesis.

## A. Cultural alignment, cultural evaluation, and cultural knowledge

### CARB / Think-as-Locals

**Zhang, Hongbin; Chen, Kehai; Bai, Xuefeng; Xiang, Yang; Zhang, Min. _Evaluating and Improving Cultural Awareness of Reward Models for LLM Alignment_. ICLR 2026.**

Use for:
- CARB benchmark motivation and construction;
- 10 cultures and four domains: cultural commonsense knowledge, cultural value, cultural safety, cultural linguistic;
- Best-of-N reward-model evaluation;
- reported reward-model weaknesses and spurious-correlation analysis;
- Think-as-Locals.

Integrity note: **Think-as-Locals is part of the CARB paper, not a separate paper.** The method is proposed in the same work as a generative-RM improvement based on RLVR and explicit culturally grounded evaluation criteria.

### CultureLLM

**Li, Cheng; Chen, Mengzhuo; Wang, Jindong; Sitaram, Sunayana; Xie, Xing. _CultureLLM: Incorporating Cultural Differences into Large Language Models_. NeurIPS 2024. DOI: 10.52202/079017-2693.**

Use for:
- cultural adaptation through WVS seed data, semantic augmentation, and fine-tuning;
- culture-specific vs unified cultural models;
- contrast with this thesis: CultureLLM changes the generator; this thesis evaluates an already-generated response post hoc.

### SafeWorld

**Yin, Da; Qiu, Haoyi; Huang, Kung-Hsiang; Chang, Kai-Wei; Peng, Nanyun. _SafeWorld: Geo-Diverse Safety Alignment_. NeurIPS 2024. DOI: 10.52202/079017-4089.**

Use for:
- geo-diverse safety and the importance of legal/cultural context;
- human-verified cultural norms and legal policies;
- distinction between contextual appropriateness, accuracy, and comprehensiveness.

Version note: the final NeurIPS publication reports **2,775 test queries**, 50 countries and 493 regions/races. An earlier arXiv record reports 2,342. The thesis must use the final published NeurIPS figure.

### Diverse Human Value Alignment via Ethical Reasoning

**Wang, Jiahao; Xue, Songkai; Li, Jinghui; Wang, Xiaozhen. _Diverse Human Value Alignment for Large Language Models via Ethical Reasoning_. AIES 2025, 8(3), 2637--2648. DOI: 10.1609/aies.v8i3.36744.**

Use for:
- context-dependent human values;
- five-step ethical reasoning: contextual fact gathering, social-norm identification, option generation, multi-lens ethical evaluation, reflection;
- separation of laws/policies, social values, cultural norms and taboos.

Integrity note: **the five-step method belongs to Wang et al.; SafeWorld is the benchmark used for evaluation, not the origin of the five-step method.**

### ValuesRAG

**Seo, Wonduk; Yuan, Zonghao; Bu, Yi. _ValuesRAG: Enhancing Cultural Alignment Through Retrieval-Augmented Contextual Learning_. AIES 2025, 8(3), 2307--2318. DOI: 10.1609/aies.v8i3.36717.**

Use for:
- retrieval-based cultural/value alignment;
- dynamic use of external value/context information;
- contrast with this thesis: ValuesRAG provides retrieved context to improve generation, whereas the verifier retrieves evidence for post-hoc evaluation.

### NormAd

**Rao, Abhinav; Yerukola, Akhila; Shah, Vishwa; Reinecke, Katharina; Sap, Maarten. _NormAd: A Framework for Measuring the Cultural Adaptability of Large Language Models_. NAACL 2025, 2373--2403. DOI: 10.18653/v1/2025.naacl-long.120.**

Use for:
- social etiquette and cultural norm specificity;
- adaptation from abstract values to explicit social norms;
- empirical motivation for treating cultural appropriateness as context-sensitive rather than universal.

### CultureBank

**Shi, Weiyan; Li, Ryan; Zhang, Yutong; Ziems, Caleb; Yu, Sunny; Horesh, Raya; De Paula, Rogério Abreu; Yang, Diyi. _CultureBank: An Online Community-Driven Knowledge Base Towards Culturally Aware Language Technologies_. Findings of EMNLP 2024, 4996--5025. DOI: 10.18653/v1/2024.findings-emnlp.288.**

Use for:
- community-derived cultural knowledge;
- contextualized and diverse cultural descriptions rather than one monolithic national profile;
- evidence that culture-related knowledge can be grounded in situated self-narratives.

### CulturalBench

**Chiu, Yu Ying; Jiang, Liwei; Lin, Bill Yuchen; Park, Chan Young; Li, Shuyue Stella; Ravi, Sahithya; Bhatia, Mehar; Antoniak, Maria; Tsvetkov, Yulia; Shwartz, Vered; Choi, Yejin. _CulturalBench: A Robust, Diverse and Challenging Benchmark for Measuring LMs' Cultural Knowledge Through Human-AI Red-Teaming_. ACL 2025, 25663--25701. DOI: 10.18653/v1/2025.acl-long.1247.**

Use for:
- human-authored and human-verified cultural benchmarking;
- breadth across regions and topics;
- human-AI red-teaming methodology.

Version note: the final ACL paper reports **1,696 questions**, 45 regions, 17 topics, with five independent annotators per question. Do not use the older 1,227-question preprint count.

### BLEnD

**Myung, Junho et al. _BLEnD: A Benchmark for LLMs on Everyday Knowledge in Diverse Cultures and Languages_. NeurIPS 2024, Vol. 37.**

Use for:
- everyday/material culture and mundane cultural knowledge;
- 52.6k QA pairs across 16 countries/regions and 13 languages;
- low-resource cultural/language coverage.

### CANDLE

**Nguyen, Tuan-Phong; Razniewski, Simon; Varde, Aparna; Weikum, Gerhard. _Extracting Cultural Commonsense Knowledge at Scale_. The Web Conference 2023, 1907--1917. DOI: 10.1145/3543507.3583535.**

Use for:
- cultural commonsense as conditioned on socio-cultural context;
- facets including food, drinks, clothing, traditions, rituals and behaviours;
- support for D01, D06 and parts of D09.

### GlobalOpinionQA

**Durmus, Esin et al. _Towards Measuring the Representation of Subjective Global Opinions in Language Models_. arXiv:2306.16388, 2023.**

Use for:
- cross-national opinion distributions;
- warning against treating prompted national perspectives as homogeneous ground truth;
- evidence that culture prompting can move model outputs while also introducing stereotypes.

### Cultural bias and cultural alignment of LLMs

**Tao, Yan; Viberg, Olga; Baker, Ryan S.; Kizilcec, René F. _Cultural bias and cultural alignment of large language models_. PNAS Nexus 3(9), pgae346, 2024. DOI: 10.1093/pnasnexus/pgae346.**

Use for:
- empirical evidence of cultural skew in LLM outputs relative to national survey data;
- effect of cultural prompting;
- motivation for human-grounded cultural evaluation.

## B. Reward models, judges, retrieval, abstention, and contamination

### RLHF foundation

**Ouyang, Long et al. _Training language models to follow instructions with human feedback_. NeurIPS 2022. DOI: 10.52202/068431-2011.**

Use for:
- preference data and RLHF background;
- the role of human rankings in alignment.

### RewardBench

**Lambert, Nathan et al. _RewardBench: Evaluating Reward Models for Language Modeling_. Findings of NAACL 2025, 1755--1797. DOI: 10.18653/v1/2025.findings-naacl.96.**

Use for:
- reward-model evaluation as preference discrimination;
- why an RM score is a useful independent baseline but not itself an evidence-grounded cultural explanation.

### Skywork-Reward-V2

**Liu, Yuhao; Zeng, Liang; Xiao, Yuzhen; He, Jujie; Liu, Jiacai; Wang, Chaojie; Yan, Rui; Shen, Wei; Zhang, Fuxiang; Xu, Jiacheng; Liu, Yang. _Skywork-Reward-V2: Scaling Preference Data Curation via Human-AI Synergy_. ICLR 2026.**

Use for:
- provenance of the exact reward-model family used by the thesis baseline;
- preference-data curation and general RM capability.

Version note: use the official ICLR 2026 author list in the bibliography. Do not silently mix it with a differently versioned arXiv author list.

### LLM-as-a-Judge

**Zheng, Lianmin et al. _Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena_. NeurIPS 2023, Datasets and Benchmarks Track. DOI: 10.52202/075280-2020.**

Use for:
- scalable direct LLM judging;
- reported position, verbosity and self-enhancement biases;
- human/judge agreement as background, not as evidence that every judge/model is reliable.

### Position bias in LLM evaluation

**Wang, Peiyi et al. _Large Language Models are not Fair Evaluators_. ACL 2024, 9440--9450. DOI: 10.18653/v1/2024.acl-long.511.**

Use for:
- order/position bias in LLM comparison;
- justification for freezing response-order handling in the direct-judge baseline.

### Retrieval-Augmented Generation

**Lewis, Patrick et al. _Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks_. NeurIPS 2020.**

Use for:
- general background on combining parametric models with explicit retrieved evidence;
- provenance/updateability motivation.

Important limitation: this paper motivates retrieval as a general paradigm; it does **not** validate this thesis's candidate-blind verifier architecture.

### Selective classification / reject option

**Geifman, Yonatan; El-Yaniv, Ran. _Selective Classification for Deep Neural Networks_. NeurIPS 2017.**

Use cautiously for:
- the general concept that withholding a prediction can trade coverage for reliability.

Do **not** claim that the verifier implements the paper's selective-classification algorithm or its risk guarantees. The thesis's `abstain` mechanism is an architectural analogue, not an implementation of SelectiveNet-style risk control.

### Benchmark contamination

**Deng, Chunyuan; Zhao, Yilun; Tang, Xiangru; Gerstein, Mark; Cohan, Arman. _Investigating Data Contamination in Modern Benchmarks for Large Language Models_. NAACL 2024, 8706--8719. DOI: 10.18653/v1/2024.naacl-long.482.**

Use for:
- why benchmark contamination can inflate evaluation performance;
- motivation for provenance filtering and exclusion of known answer/annotation sources.

Important limitation: the paper does not establish that the verifier's URL filters eliminate contamination. They only motivate contamination controls.

## C. Culture as a construct

### UNESCO Universal Declaration on Cultural Diversity

**UNESCO. _Universal Declaration on Cultural Diversity_. Paris, 2 November 2001.**

Use for:
- broad framing of culture as encompassing material, intellectual and emotional features, lifestyles, ways of living together, values, traditions and beliefs;
- identity, diversity and pluralism.

### UN CESCR General Comment No. 21

**UN Committee on Economic, Social and Cultural Rights. _General Comment No. 21: Right of everyone to take part in cultural life_. E/C.12/GC/21, 21 December 2009.**

Use for:
- culture as broad and evolving rather than a fixed list of national traits;
- cultural life, participation, identity, language, traditions, beliefs and intergenerational transmission.

## D. D01--D10 literature support map

The D01--D10 framework is a **literature-grounded synthesis plus an operational design choice**. It is not a taxonomy copied from one paper, and the thesis must never imply one-to-one derivation from a single source.

| Dimension | Strongest validated support | Run-2 assessment |
|---|---|---|
| D01 Everyday life and material culture | BLEnD; CANDLE; UNESCO/CESCR | Strong |
| D02 Language, discourse and pragmatics | CARB linguistic domain; UNESCO/CESCR; multilingual cultural benchmarks | Good, but pragmatics should be sourced more directly if treated in depth |
| D03 Social etiquette and interpersonal norms | NormAd; CulturalBench | Strong |
| D04 Values, ethics and moral pluralism | CultureLLM/WVS; GlobalOpinionQA; SafeWorld; Wang et al. | Strong |
| D05 Law, policy and institutional rules | SafeWorld; Wang et al. | Strong |
| D06 Religion, ritual and taboo | CANDLE; CultureLLM/WVS; UNESCO/CESCR | Strong |
| D07 Family, kinship, gender and generations | UNESCO/CESCR; WVS-related sources | **Partial: targeted dedicated source still required before making a strong derivation claim** |
| D08 Work, education and civic participation | UNESCO/CESCR; WVS political participation; CANDLE occupation facet | **Partial: add a dedicated source if this dimension receives detailed theoretical claims** |
| D09 Cultural heritage, history, arts and collective memory | UNESCO/CESCR; CANDLE traditions/rituals | **Good for heritage/arts/tradition; collective-memory component needs a dedicated source if emphasized** |
| D10 Identity, diversity and intergroup relations | UNESCO; CESCR; CultureLLM; GlobalOpinionQA; Tao et al. | Good |

## E. Claims that are intentionally NOT supported yet

The literature inventory does not yet justify any of the following statements:

- that D01--D10 is the uniquely correct or universally exhaustive cultural taxonomy;
- that candidate-blind evidence synthesis eliminates evaluator bias;
- that evidence freezing improves accuracy;
- that the verifier outperforms CARB;
- that the verifier outperforms Skywork or direct LLM judging;
- that five student annotators provide cultural ground truth;
- that REPLAY makes the full LLM pipeline deterministic.

These must remain methodological hypotheses, implementation properties, or empirical questions until final experiments are complete.

## F. Version and attribution corrections frozen in Run 2

1. Think-as-Locals belongs to the CARB paper.
2. The five-step ethical-reasoning paradigm belongs to Wang et al.; SafeWorld is its evaluation benchmark.
3. SafeWorld: use the final NeurIPS count of 2,775 queries, not the older 2,342 preprint count.
4. CulturalBench: use the final ACL count of 1,696 questions, not the older preprint count.
5. Skywork-Reward-V2: use the official ICLR 2026 author list for the final-paper citation.
6. D01--D10 must be described as a synthesis/operationalization, not as a taxonomy directly inherited from CARB or another single source.

## Run-2 stopping point

Literature inventory and claim mapping are now prepared. Chapters 2 and 3 remain unwritten by design; writing them is Run 3.
