# 8. Discussion and Error Analysis

## 8.1 Purpose

A final outcome label alone does not explain whether the verifier handled a cultural problem well. The discussion therefore examines complete traces, especially cases where the response is not assessable, external evidence is weak, or dimensions receive different scores.

## 8.2 Evidence that helps

**[SELECT TRACE-BACKED EXAMPLES]** Use actual item IDs and exact short quotations to show a case in which external evidence clarified a practice, rule, or regional difference. Distinguish what the source documented from the model's own judgment.

## 8.3 Evidence that does not settle the issue

Some cultural questions involve values, individual preferences, or communities with different practices. A source can document variation without determining a single correct behavior. **[INSERT TRACE EXAMPLE]** Discuss whether abstention or a qualified score was appropriate.

## 8.4 Pipeline failures

Examine failures in context extraction, target selection, neutral question wording, retrieval, evidence memo construction, target comparison, and scoring. For each case, identify the earliest visible problem rather than blaming the final score alone.

## 8.5 Refusals and assessability

A pure refusal may avoid a harmful claim but provide no substantive answer. This is particularly important for red-team prompts. Report refusals separately from successful culturally appropriate responses. **[INSERT COUNTS BY CORPUS]**.

## 8.6 Baseline disagreements

**[IF BASELINES ARE AVAILABLE]** Compare concrete disagreements, not only aggregate counts. A reward model can prefer an answer for reasons unrelated to cultural accuracy; a direct judge can be right or wrong without retrieval. Without independent labels, disagreement is a diagnostic observation rather than evidence that one evaluator is better.

## 8.7 Relation to the literature

The results should be discussed alongside CARB, cultural benchmarks, and work on pluralistic alignment, but incompatible published benchmark scores must not be presented as direct head-to-head comparisons.

## 8.8 Answering the research questions

**[INSERT RQ1–RQ4 ANSWERS AFTER RESULTS]** Each answer must refer to a specific table or trace and state its limitations.
