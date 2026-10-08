# 2. Background

## 2.1 Language models and alignment

A language model generates text from the input and the patterns it learned during training. Instruction tuning and preference-based post-training can make responses more helpful, but helpfulness is not identical to cultural appropriateness. The distinction is important when a response involves local practices, religion, social relationships, or history. Ouyang et al. (2022) describe a widely used human-feedback training pipeline; this thesis does not reproduce that training procedure.

## 2.2 Reward models

A reward model estimates a preference-related score for a prompt and response. Such a score is useful for comparing candidate outputs under the model's learned preferences. It is not, by itself, a source citation or an explanation of a cultural claim. Skywork-Reward-V2 is considered as an independent comparison system, not a component of Vericult. Its exact checkpoint and input format must be frozen before comparison.

## 2.3 LLM judges

A direct LLM judge receives an evaluation instruction and the response to be judged. It can give an understandable explanation without requiring a complex retrieval pipeline. Research on LLM-based evaluation has also reported evaluator effects, including sensitivity to presentation and ordering (Zheng et al., 2023; Wang et al., 2024). These findings motivate careful baseline design; they do not prove that every direct judge is unreliable.

## 2.4 Cultural appropriateness

This thesis uses *cultural appropriateness* to mean how well a response handles the cultural concerns relevant to the explicit situation. It is not a score for whether a person follows a majority custom. For example, a description that a greeting is *common* differs from a claim that it is *required*. Advice about law also differs from advice about etiquette. The verifier must distinguish descriptive claims, institutional rules, recommendations, and value judgments.

## 2.5 Evidence and uncertainty

Retrieval-augmented generation uses external documents to inform a model's answer (Lewis et al., 2020). Vericult uses retrieval differently: it checks claims in an already generated response. Documents can help establish an institutional rule or document regional variation, but they cannot always decide a contested ethical question. Missing evidence should be recorded as missing evidence, not treated as proof that a claim is false.

## 2.6 Reproducibility

An online search can change over time. Vericult therefore separates LIVE retrieval from REPLAY using saved evidence snapshots. This preserves the evidence inputs for later inspection. It does not guarantee identical language-model outputs on every replay, nor does it guarantee that the retrieved documents represent every relevant community.
