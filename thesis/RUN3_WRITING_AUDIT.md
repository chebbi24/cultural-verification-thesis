# Run 3 - Chapters 2 and 3 Writing Audit

## Scope

Run 3 was intentionally limited to the two chapters specified by the staged thesis plan:

- Chapter 2: Background and Foundations
- Chapter 3: Related Work and Research Gap

No Chapter 4 methodology/framework writing, final experiment execution, result population, or conclusion writing was started in this run.

## Files written

- `chapters/02_background.tex`
- `chapters/03_related_work.tex`

Supporting changes:

- `bibliography/run3_sources.bib` adds four verified sources needed for the conceptual background and survey synthesis.
- `main.tex` loads the additional bibliography file.
- `TODO.md` marks Chapters 2 and 3 as drafted.

The richer Run-2 bibliography in `bibliography/references.bib` is left unchanged.

## Chapter 2 coverage

The Background and Foundations chapter now establishes the technical and conceptual vocabulary used later in the thesis without duplicating the related-work chapter. It covers:

1. LLM post-training and alignment, with RLHF as the relevant preference-alignment foundation.
2. Reward models as learned preference evaluators and the distinction between a preference score and an evidence-grounded cultural judgment.
3. Direct LLM-as-a-Judge evaluation and documented judge biases such as position/order effects.
4. Cultural appropriateness as a context-sensitive construct rather than a claim of one universal cultural truth.
5. Distinctions among tendencies, social norms, pragmatic conventions, values, and legal/institutional rules.
6. Retrieval as a mechanism for inspectable evidence and provenance, while explicitly retaining retrieval uncertainty and representation bias.
7. Evaluation concepts needed later: human reference judgments, agreement, abstention/coverage, confidence, paired comparison, contamination, and reproducibility.

The chapter explicitly avoids treating the verifier's architecture as empirical proof of reduced bias or increased cultural accuracy.

## Chapter 3 coverage

The Related Work and Research Gap chapter synthesizes prior work by research objective rather than presenting a list of isolated paper summaries. It contains:

1. A survey-level overview of culturally aware NLP and the lack of a single universally accepted operationalization of culture.
2. A compact comparison table covering representative benchmark/adaptation directions.
3. A substantial CARB treatment covering motivation, construction, four-domain design, Best-of-N evaluation, reported findings, perturbation-based robustness analysis, Think-as-Locals, and limits of comparability to this thesis.
4. CultureLLM as generator adaptation by semantic augmentation and fine-tuning, not post-hoc verification.
5. SafeWorld and Wang et al.'s five-step ethical-reasoning framework with correct attribution.
6. NormAd, CultureBank, GlobalOpinionQA and related work as support for context sensitivity, pluralism, and situated cultural knowledge.
7. ValuesRAG and general RAG as retrieval-for-generation antecedents, contrasted with retrieval-for-post-hoc-verification.
8. Reward-model and direct-judge baselines.
9. A narrowly phrased research gap that does not claim priority for individual components already present in earlier work.

## CARB integrity controls

The chapter preserves the following distinctions:

- CARB / Think-as-Locals is prior work, not an internal runtime component of the verifier.
- Think-as-Locals is part of the CARB paper rather than a separate paper.
- CARB uses 10 culture/language settings, four broad cultural domains, and 8,576 Best-of-N sets in the final ICLR 2026 paper.
- CARB's published percentages are not compared numerically with this thesis's future held-out Best-of-4 results unless a common protocol is actually implemented.
- CARB's four domains are not presented as the derivation of D01--D10.

## Attribution controls

- The five-step ethical-reasoning framework is attributed to Wang et al.; SafeWorld is the benchmark used in that work.
- CultureLLM is described as an adaptation/fine-tuning method.
- ValuesRAG is described as retrieval used to improve generation rather than as a candidate-blind verifier.
- General RAG, selective classification, judge-bias, and contamination literature are used only to motivate bounded methodological concerns, not to claim empirical guarantees for the proposed system.

## New verified sources added in Run 3

- Adilazuarda et al. (2024), *Towards Measuring and Modeling “Culture” in LLMs: A Survey*, EMNLP 2024.
- Liu, Gurevych, and Korhonen (2025), *Culturally Aware and Adapted NLP: A Taxonomy and a Survey of the State of the Art*, TACL 13.
- Pawar et al. (2025), *Survey of Cultural Awareness in Language Models: Text and Beyond*, Computational Linguistics.
- Sorensen et al. (2024), *Position: A Roadmap to Pluralistic Alignment*, ICML 2024.

## Page/compile check

A local LaTeX validation build completed successfully after drafting the two chapters.

Observed chapter ranges in that build:

- Chapter 2: 6 pages of main text.
- Chapter 3: 11 pages of main text.

Chapter 2 is within the planned 6--7 page range. Chapter 3 is approximately one page above the provisional 9--10 page target. No content is removed merely to satisfy a provisional quota at this stage; the chapter can be tightened during the final whole-thesis page-budget pass if necessary.

The validation build produced no unresolved cross-references/citations or overfull-box warnings in these chapters. The total PDF page count is not treated as thesis progress because later chapters are still mostly scaffolds/placeholders.

## Claims deliberately not made

Run 3 does not claim that:

- the verifier outperforms CARB, Skywork, or a direct LLM judge;
- candidate blindness eliminates evaluator bias;
- evidence freezing improves accuracy;
- D01--D10 is a uniquely correct or exhaustive cultural taxonomy;
- human majority labels are universal cultural truth;
- REPLAY makes semantic LLM execution deterministic.

Those points remain implementation properties, methodological hypotheses, or empirical questions depending on the claim.

## Run-3 stopping point

Chapters 2 and 3 are drafted and source-grounded. Run 4, which will address the D01--D10 operational framework and its literature-grounded derivation, has not been started.
