# Archived external-120 pre-freeze experiment

This directory preserves the exact 120 prompt-response corpus and the final merged post-rerun result export from the six-source cross-dataset Vericult validation run.

The experiment remains archived separately from the active final-experiment paths because it was executed before the definitive repository freeze. Its final failed-item rerun occurred after the October 5 result-semantics repair had been validated on `fix/cultural120-result-semantics` at `c1944bb1df47a8668689c316e62563bdc700fbf3`; the exported behavior includes `cultural_applicability_v1` and `not_culturally_applicable`. Those semantics were subsequently restored into the definitive Vericult 1.1 freeze (`286598d5eb642c3d632e7b756ccf1954fb922a13`; final main snapshot `cc2de515cc481a6ec82c8c3edd5611209b84e97b`).

The compact merged result rows do not embed an exact runtime Git SHA. Therefore the archive does not claim commit-level identity for every executed row; it preserves the empirical output exactly and records the validated semantic lineage separately.

Composition: 20 each from CARE, Community Alignment, PLURAL, PACT, ThaiCLI and PRISM.

Final state after rerunning failures: **116/120 completed**. The four unresolved records are:
- 028 — Community Alignment — `cultural_applicability_v1` transport `ReadTimeout`
- 034 — Community Alignment — `cultural_applicability_v1` transport `ReadTimeout`
- 076 — PACT — `target_extractor_v1` invalid output after bounded retry; later diagnosed malformed span ID `S0:01`
- 084 — ThaiCLI — `cultural_applicability_v1` transport `ReadTimeout`

The source corpus consists primarily of reference/preferred/chosen/high-rated responses. It should therefore be interpreted as a positive-control cross-dataset sanity/robustness run, not as a balanced accuracy benchmark and not as the definitive frozen PLT/external experiment.

Importantly, `not_culturally_applicable` is a current final Vericult outcome, not obsolete behavior.
