# 3. Related Work

## 3.1 Cultural evaluation benchmarks

Cultural benchmarks make different parts of culture measurable. BLEnD (Myung et al., 2024) studies everyday knowledge across cultures and languages. CulturalBench (Chiu et al., 2025) focuses on cultural knowledge with challenging evaluation items. NormAd (Rao et al., 2025) examines adaptation to social norms. These tasks are useful references, but performance on a fixed benchmark is not the same as verifying a new, open-ended response.

## 3.2 CARB

CARB, *Evaluating and Improving Cultural Awareness of Reward Models for LLM Alignment* (Zhang et al., 2026), investigates the cultural awareness of reward models. It is especially relevant because Vericult is compared conceptually with preference-based evaluation. CARB and Vericult answer related but different questions: CARB studies reward-model behavior under its benchmark design; Vericult checks individual generated answers through a traceable evidence pipeline. **[SOURCE AUDIT: Insert CARB's exact domains, task construction, sample sizes and reported results from the original paper, with page-specific citations.]** No head-to-head performance claim is justified without running both approaches on equivalent data.

## 3.3 Cultural adaptation methods

CultureLLM (Li et al., 2024) addresses cultural differences through model adaptation. ValuesRAG (Seo et al., 2025) studies retrieval-supported cultural or value alignment. Both are relevant because they aim to improve the content of model outputs. Vericult is post-hoc: it does not fine-tune the generator or rewrite the response during evaluation.

## 3.4 Safety and plural perspectives

SafeWorld (Yin et al., 2024) investigates geographically diverse safety alignment. Work on pluralistic alignment (Sorensen et al., 2024) argues that legitimate human differences should not always be collapsed into a single preference. These ideas matter when a cultural judgment concerns rights, competing values, or minority perspectives. A common local tendency must not automatically become the only acceptable answer.

## 3.5 General evaluators

RewardBench (Lambert et al., 2025) provides a framework for studying reward-model evaluation. MT-Bench and Chatbot Arena (Zheng et al., 2023) are important references for LLM-based judging. They help position the independent baselines, but their reported scores cannot be transferred to the present 360-item dataset.

## 3.6 Research gap

The literature contains benchmarks, cultural adaptation methods, preference evaluators, and retrieval techniques. The specific design tested here combines a post-hoc prompt–response interface with explicit cultural dimensions, external evidence only where appropriate, a candidate-blind evidence stage, evidence freezing, and diagnostic traces. The thesis tests whether these choices are useful in practice. It does not claim priority as the first cultural verifier.

**[LITERATURE AUDIT REQUIRED]** The final bibliography must be checked against the original papers for author names, years, venues, exact titles, and each numerical claim. The prose above deliberately avoids unverified benchmark statistics.
