# Source-to-Claim Map

This map is a writing control for Chapters 2--5. A source appearing here authorizes only the bounded claim described below. It does not authorize stronger causal or evaluative claims.

## Chapter 2 - Background and Foundations

| Planned claim/topic | Primary source(s) | What the source supports | Boundary |
|---|---|---|---|
| RLHF uses human demonstrations/preferences to align language models | Ouyang et al. (2022) | InstructGPT training via demonstrations, output rankings and RLHF | Does not establish cultural appropriateness |
| Reward models require dedicated evaluation | Lambert et al. (2025), RewardBench | RM evaluation using prompt/chosen/rejected comparisons | RewardBench is general, not culturally specific |
| Thesis RM baseline belongs to Skywork-Reward-V2 family | Liu et al. (2026) | Skywork-Reward-V2 model family and preference-data curation | Do not transfer published benchmark scores to our experiment |
| LLM-as-a-judge can approximate human preferences but has biases | Zheng et al. (2023) | Judge paradigm, human agreement, position/verbosity/self-enhancement biases | Agreement is model/task dependent |
| Candidate order can affect LLM judging | Wang et al. (2024) | Positional bias in LLM evaluators | Motivates order controls; does not prove our judge will exhibit the same magnitude |
| Retrieval provides explicit non-parametric evidence/provenance | Lewis et al. (2020) | RAG and explicit retrieved memory/provenance motivation | Not evidence for our candidate-blind architecture |
| Abstention/reject option can trade coverage for reliability | Geifman & El-Yaniv (2017) | Selective classification as reject-option paradigm | Our abstention is not their algorithm and has no inherited risk guarantee |
| Benchmark contamination threatens evaluation validity | Deng et al. (2024) | Evidence and methods for studying benchmark contamination | Does not prove our URL filtering eliminates contamination |
| Culture is broader than nationality and includes lifestyles, values, traditions, beliefs, identities | UNESCO (2001); CESCR (2009) | Broad institutional definitions and plural/dynamic cultural framing | Use as conceptual framing, not computational taxonomy ground truth |

## Chapter 3 - Related Work and Research Gap

| Work | Claims it can support in the thesis | Contrast/relevance to this thesis |
|---|---|---|
| CARB / Zhang et al. (2026) | 10 cultures, four cultural domains, Best-of-N RM evaluation, RM cultural-awareness findings, spurious-correlation analysis, Think-as-Locals | Closest RM-focused cultural evaluation reference; our verifier is independent, post-hoc, evidence-grounded and not an RM improvement method |
| CultureLLM / Li et al. (2024) | WVS seed data, semantic augmentation, fine-tuning for nine cultures, culture-specific/unified models | Generator adaptation rather than standalone post-hoc verification |
| SafeWorld / Yin et al. (2024) | Geo-diverse cultural/legal safety, human-verified norms/policies, 2,775 final test queries across 50 countries/493 regions-races | Supports separating law/policy from cultural norms and context-sensitive safety; not the source of Wang et al.'s five-step reasoning method |
| Wang et al. (2025) ethical reasoning | Five-step ethical reasoning and hierarchical social-norm identification | Deliberative generation/alignment method; our verifier instead independently evaluates a candidate response using evidence |
| ValuesRAG / Seo et al. (2025) | Retrieval of culturally/demographically relevant value information for generation | Retrieval for alignment/generation rather than candidate-blind post-hoc verification |
| NormAd / Rao et al. (2025) | Cultural adaptability, social etiquette, norm specificity from abstract values to explicit norms | Strong motivation for context-sensitive norm evaluation and D03 |
| CultureBank / Shi et al. (2024) | Community-driven cultural knowledge, contextualized cultural descriptions | Supports situated/plural cultural knowledge rather than monolithic national assumptions |
| CulturalBench / Chiu et al. (2025) | Human-written/human-verified cultural benchmark, 45 regions, 17 topics, five annotators/question | Supports rigorous human validation and broad topical coverage |
| BLEnD / Myung et al. (2024) | Everyday culture and multilingual everyday knowledge across 16 regions/13 languages | Strong support for D01 and resource-availability limitations |
| CANDLE / Nguyen et al. (2023) | Cultural commonsense conditioned on socio-cultural context; food, clothing, rituals, traditions, behaviours | Supports everyday/material/religious/traditional facets |
| GlobalOpinionQA / Durmus et al. (2023) | Cross-national subjective opinion distributions and stereotype risks under cultural prompting | Supports pluralism and caution around national-value essentialism |
| Tao et al. (2024) | Cultural bias/alignment assessed against national survey data | Empirical motivation for cultural evaluation and human/survey grounding |
| RewardBench / Lambert et al. (2025) | General RM evaluation | Shows RM evaluation infrastructure but not cultural specificity |
| Zheng et al. (2023); Wang et al. (2024) | Direct judging and known judge biases | Motivates an independent direct-judge comparator and order controls |

## Chapter 4 - Operational Framework D01--D10

### D01 Everyday life and material culture

Primary support: BLEnD; CANDLE; UNESCO; CESCR.

Safe claim: everyday practices, food, clothing, routines, leisure and material practices are meaningful cultural content and can be underrepresented in standard web knowledge.

Do not claim: D01 as named in this thesis is inherited verbatim from those sources.

### D02 Language, discourse and pragmatics

Primary support: CARB cultural-linguistic domain; UNESCO/CESCR linguistic framing; multilingual cultural benchmarks.

Safe claim: linguistic form and cultural context interact and are evaluated as part of cultural awareness in prior work.

Gap: if Chapter 4 develops pragmatic concepts such as implicature/register in theoretical detail, add a dedicated pragmatics/intercultural-communication source in a later targeted literature pass.

### D03 Social etiquette and interpersonal norms

Primary support: NormAd; CulturalBench.

Safe claim: social acceptability and etiquette vary with contextual norm specificity and are a distinct, empirically studied aspect of cultural adaptation.

### D04 Values, ethics and moral pluralism

Primary support: CultureLLM/WVS; GlobalOpinionQA; SafeWorld; Wang et al.; Tao et al.

Safe claim: cultural/value alignment includes plural and geographically varying values and opinions; one national majority must not be equated with moral unanimity.

### D05 Law, policy and institutional rules

Primary support: SafeWorld; Wang et al.

Safe claim: legal requirements and public policy are context-relevant but conceptually distinct from informal cultural norms.

### D06 Religion, ritual and taboo

Primary support: CANDLE; CultureLLM/WVS; UNESCO/CESCR.

Safe claim: religion, beliefs, rituals and traditions form recurrent components of cultural representations and benchmarks.

### D07 Family, kinship, gender and generations

Current support: UNESCO/CESCR broad framing; WVS/value-oriented sources.

Status: **partial**.

Do not yet write a strong claim that the literature uniquely warrants this exact dimension. Add at least one dedicated family/kinship/gender/intergenerational cultural source if this subsection makes detailed theoretical claims.

### D08 Work, education and civic participation

Current support: CANDLE occupation facet; WVS political participation; UNESCO/CESCR participation framing.

Status: **partial**.

Do not overstate derivation. Add a dedicated work/education/civic cultural source if this subsection goes beyond operational coverage rationale.

### D09 Cultural heritage, history, arts and collective memory

Current support: UNESCO/CESCR heritage, arts, traditions; CANDLE traditions/rituals.

Status: **good for heritage/arts/tradition, partial for collective memory**.

If collective memory becomes a substantive theoretical concept rather than a rubric label, add a dedicated collective-memory source.

### D10 Identity, diversity and intergroup relations

Primary support: UNESCO; CESCR; CultureLLM; GlobalOpinionQA; Tao et al.

Safe claim: culture intersects with multiple identities and plural viewpoints; cultural evaluation should avoid collapsing a population into one fixed identity profile.

## Chapter 5 - Verifier Methodology

The chapter must distinguish literature-motivated design requirements from properties uniquely established by our code.

| Design choice | Literature that motivates the problem | What we may claim | What we may NOT claim before experiments |
|---|---|---|---|
| Context extraction before cultural judgment | NormAd; SafeWorld; Wang et al. | Cultural/social/legal interpretation can depend on explicit situation and regional context | Our extraction algorithm is empirically superior |
| Shared prompt-level dimension plan | General evaluation comparability requirement; our design | Code enforces the same prompt-level plan across A--D | Literature proves this exact design improves accuracy |
| Material target decomposition | CANDLE/knowledge grounding; our design | Code decomposes responses into bounded decision-relevant targets | Three targets are universally optimal |
| Neutral question generation | LLM-judge bias literature provides bias motivation | Questions are instructed to avoid proving/refuting the candidate and candidate text is removed afterward | Generated questions are objectively unbiased |
| Candidate-blind evidence engine | Zheng et al.; Wang et al. motivate concerns about judge conditioning/order; our architecture supplies the mechanism | After question generation, evidence retrieval/synthesis structurally cannot receive candidate/target objects | Candidate blindness eliminates all evaluator bias |
| Retrieval/provenance | Lewis et al.; Deng et al. | External evidence and provenance can support auditability; code records/filter sources | Search results are complete, unbiased or contamination-free |
| Source-type classification | Our design; question-dependent evidence practice | Code classifies source type and asks semantic stage to consider fitness to question | One source category is universally more truthful than another |
| Evidence memo and scope/variation | CultureBank, NormAd, GlobalOpinionQA motivate contextual variation | Code records scope, variation, sufficiency and citations | Memo correctness is guaranteed by citations |
| Bounded follow-up | Reproducibility/fair-comparison design goal | Code allows at most one follow-up round | Two rounds are empirically optimal |
| Evidence freezing before target comparison | Our anti-contamination design | Code freezes/hashes memo before target is reintroduced | Freezing has already been shown to increase human agreement |
| Abstention | Geifman & El-Yaniv provides general reject-option precedent | Code can abstain when a valid score cannot be established | The verifier inherits selective-classification risk guarantees |
| LIVE/REPLAY | Reproducibility and retrieval-drift design goal | REPLAY freezes the retrieved evidence set and fails on missing/inconsistent snapshots | REPLAY makes the semantic LLM deterministic |
| Leakage filtering | Deng et al. motivates contamination controls | Code blocks known repos/domains/paths and records filtering | Unknown mirrors or pretraining contamination are eliminated |

## Final writing rule

A citation should appear only where the mapped source directly supports the sentence. If a sentence describes our implementation, cite the thesis/repository artifact or explain it as our method rather than laundering it through unrelated literature.
