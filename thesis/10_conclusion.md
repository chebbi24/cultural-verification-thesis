# 10. Conclusion and Future Work

## 10.1 Research Summary

This thesis studied the post-hoc verification of cultural appropriateness in large language model outputs.

The starting problem was that a fluent answer can still be culturally wrong. It can overgeneralize a social practice, misrepresent a religion, use an inappropriate register, confuse custom with law, stereotype a group, or handle historical memory insensitively.

Existing cultural benchmarks and alignment methods show that these problems are real. However, many existing approaches either test a model on a fixed benchmark, improve the generator, or return a general preference score.

Vericult was developed as a different kind of system: a standalone verifier for one prompt-response pair.

The final pipeline:

1. extracts explicit prompt context;
2. checks cultural applicability;
3. selects relevant D01–D10 dimensions;
4. checks whether the response is assessable;
5. extracts up to three material response targets;
6. generates neutral evidence questions;
7. performs candidate-blind evidence processing;
8. filters known benchmark leakage;
9. classifies sources;
10. builds and validates an evidence memo;
11. optionally performs one bounded follow-up;
12. freezes the evidence;
13. compares the response target with the frozen evidence;
14. scores the cultural dimensions;
15. returns a final cultural outcome and complete trace.

The final experiment uses 360 fixed prompt-response pairs and one common GPT-OSS generator. LIVE search is separated from the primary REPLAY evaluation through an evidence-freeze step.

## 10.2 Research Questions

### RQ1

**How does Vericult classify culturally situated LLM responses across diverse settings?**

**[[FINAL RQ1 ANSWER]]**

### RQ2

**How do Vericult judgments compare with an independent reward model and a direct LLM judge?**

**[[FINAL RQ2 ANSWER]]**

If no response-level human reference is added, the answer must discuss system agreement rather than accuracy.

### RQ3

**What diagnostic information is provided by the evidence-grounded pipeline?**

**[[FINAL RQ3 ANSWER]]**

The final answer should refer to concrete traces showing where evidence, scope, variation or abstention changed the interpretation of a response.

### RQ4

**Which failure modes occur and what do they imply?**

**[[FINAL RQ4 ANSWER]]**

The answer should identify the most important observed failure categories rather than repeat every theoretical limitation.

## 10.3 Main Contributions

The thesis contributes:

- a practical ten-dimensional cultural-appropriateness framework;
- a single-response post-hoc verifier;
- explicit separation of target selection, evidence construction and final comparison;
- bounded external retrieval with provenance controls;
- evidence sufficiency and abstention;
- LIVE/REPLAY evidence freezing;
- a three-corpus 360-item final evaluation protocol;
- detailed execution traces for error analysis.

The contribution is mainly methodological and engineering-oriented.

It does not claim to define culture universally.

## 10.4 Main Empirical Conclusion

**[[FINAL EMPIRICAL CONCLUSION — 1 paragraph based only on completed REPLAY and baseline outputs.]]**

This paragraph should answer the practical question:

> Did the additional evidence-grounded structure provide useful cultural verification beyond a simpler automated judge, and at what cost?

If the results are mixed, the conclusion should say so.

A balanced mixed result is more valuable than an unsupported success claim.

## 10.5 Future Work

Several extensions are natural.

### Final-response human annotation

The most important next step is an independent human evaluation of the final GPT-OSS responses.

A strong design would use:

- multiple annotators;
- relevant cultural familiarity;
- item-level uncertainty;
- retained disagreement rather than forced consensus.

### Multiple verifier backbones

The same frozen evidence could be replayed with different semantic models.

This would show how much the result depends on Qwen3.6.

### Multilingual retrieval

Queries could be issued both in the prompt language and in locally relevant languages.

This could improve evidence for underrepresented contexts.

### Independent question generation

Several independently generated neutral questions could be compared before retrieval.

This may reduce framing bias.

### Better target coverage

Long responses could use hierarchical target selection instead of a hard three-target cap.

### Community-aware evidence

Future systems could combine public web retrieval with curated community knowledge such as CultureBank-style resources.

### Response revision

Vericult could eventually provide structured feedback to a generator and request a corrected response.

This should be evaluated separately because verification and generation would then become coupled.

### User-facing interface

A practical interface could show:

- final outcome;
- affected cultural dimensions;
- short evidence explanation;
- important uncertainty;
- expandable source trace.

The user should not have to read the full internal JSON trace.

## 10.6 Final Statement

Cultural evaluation is difficult because culture is contextual, internally diverse and only partly reducible to factual claims.

A useful verifier should therefore be able to say more than “good” or “bad.”

It should be able to show what it checked, what evidence it found, what remained uncertain and why it reached its conclusion.

Vericult is one attempt to build that kind of verification layer.

Its final value is determined not by the complexity of the pipeline, but by whether the evidence and trace make culturally situated LLM evaluation more reliable, transparent and useful in practice.
