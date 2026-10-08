# 6. Experimental Design

## 6.1 Main design

The final experiment evaluates 360 fixed prompt–response pairs, not four candidates per prompt. Each response is assessed independently. The previous Best-of-4 experiments were development work and must not be presented as final results for the new responses.

## 6.2 Corpora

The evaluation contains three equally sized corpora:

| Corpus | Items | Purpose |
|---|---:|---|
| PLT120 | 120 | Researcher-designed cultural situations |
| External120 | 120 | Prompts sourced from external multicultural datasets |
| Redteam120 | 120 | Culturally challenging cases with external provenance |
| Total | 360 | Fixed prompt–response pairs |

External120 contains material from CARE, Community Alignment, PLURAL, PACT, ThaiCLI, and PRISM, with 20 prompts from each. Exact source records and license conditions must be cited from the dataset manifest. The Redteam120 provenance should be described from its frozen source records, not from a generic label.

## 6.3 Generator

One generator produces one fixed response for each prompt. The frozen identifier is `gpt-oss:120b-mxfp4`, with temperature 0.8, top-p 0.95, maximum output tokens 1200, and no additional system prompt. The generator's output is not regenerated during verifier evaluation. Each response has a recorded hash.

## 6.4 Verifier

The semantic backbone is `vllm/qwen3.6:35b-a3b-fp8` through L3S. The verifier configuration is frozen separately from the generator. It uses Tavily for LIVE retrieval and stored evidence for REPLAY. The maximum number of material targets is three; retrievable targets receive two initial questions and at most one follow-up. **[INSERT EXACT FINAL CONFIG HASH, COMMIT, AND RUN DATES]**.

## 6.5 Execution and checks

The runner validates item IDs, prompt and response hashes, generator metadata, and experiment configuration. LIVE runs first. Evidence audit must complete before REPLAY. A failed prompt may be recorded without stopping the whole batch; incomplete runs cannot be treated as a completed 360-item experiment.

## 6.6 Comparison systems

Skywork-Reward-V2 is an independent reward-model baseline. A separate direct LLM judge is another planned baseline. Neither is used inside Vericult. Because the final task is single-response evaluation, both baselines must be given a documented mapping from their native output to the outcome or reference being compared. A reward score is not automatically a cultural-appropriateness category. **[FREEZE EXACT BASELINE MODEL, PROMPT, SCORE MAPPING, AND RUN STATUS]**.

## 6.7 Human references

Five students previously annotated 30 Best-of-4 items with four candidate responses each. Those labels refer to different responses and cannot be reused as gold labels for the GPT-OSS outputs. If new human judgments are collected for the final 360 responses, report the recruitment, instructions, coverage, aggregation, and disagreement. Without them, report outcome distributions, trace quality, and cross-system agreement descriptively, not accuracy against human ground truth.

## 6.8 Metrics

The main descriptive measures are: counts and proportions for each outcome, assessability rate, dimension-score distribution, abstention rate, evidence sufficiency, completed trace coverage, and execution failures. Record runtime and retrieval counts where logs support them. If an independent reference becomes available, calculate agreement with clear denominators and confidence intervals. Do not use McNemar's test without paired correctness labels for the same items.

## 6.9 Reproducibility

The frozen inputs are the three generated CSV files, semantic hashes, generator settings, verifier code/configuration, and evidence snapshots. The REPLAY result is the main reported output. Any rerun or configuration change must be documented rather than silently merged with the original experiment.
