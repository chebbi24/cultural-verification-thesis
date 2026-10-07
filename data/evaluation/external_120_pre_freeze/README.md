# Archived external-120 pre-freeze experiment

This directory preserves the exact 120 prompt-response corpus and the final merged result export from the earlier cross-dataset Vericult validation run.

It is deliberately archived on this branch rather than restored to the active final-experiment paths. The run predates the frozen Vericult 1.1 decision semantics and contains the older `cultural_applicability_v1` / `not_culturally_applicable` behavior.

Composition: 20 each from CARE, Community Alignment, PLURAL, PACT, ThaiCLI and PRISM.

Final state after rerunning failures: 116/120 completed. The four unresolved records are 028, 034, 076 and 084; see `summary.json`.

The source corpus consists primarily of reference/preferred/chosen/high-rated responses. It should therefore be interpreted as a positive-control cross-dataset sanity/robustness run, not as a balanced accuracy benchmark and not as the final frozen Vericult 1.1 external evaluation.
