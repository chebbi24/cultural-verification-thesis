# Thesis TODO Register

## Scientific freezes still required

- [ ] Freeze final semantic verifier model, provider, exact identifier/revision and experiment date.
- [ ] Freeze direct LLM judge model and judging prompt.
- [ ] Freeze final evaluation sample and decide whether PLT001--PLT030 are sufficient or whether an additional genuinely unseen confirmatory set is required.
- [ ] Complete five-student human annotation and archive the final export before system-result analysis.
- [x] Define the primary majority / no-clear-winner / unresolved-split aggregation rule (Run 6: >=3 identical votes = majority; otherwise unresolved split).
- [ ] Apply the pre-declared inter-annotator agreement rule to the realized export: Fleiss' kappa for a complete balanced five-rater matrix, otherwise nominal Krippendorff's alpha.
- [ ] Correct or explicitly wrap exact-tie handling in the current Skywork baseline before final comparison so an exact top-score tie yields `no_clear_winner`.
- [ ] Freeze direct-judge candidate permutation schedule and analysis seed before execution.
- [ ] Run final LIVE evidence collection and preserve frozen evidence artifacts.
- [ ] Run primary REPLAY evaluation under frozen evidence.
- [ ] Run independent Skywork baseline.
- [ ] Run direct LLM-as-a-judge baseline.
- [ ] Compute pre-declared comparative statistics, confidence intervals, paired tests, and effect sizes.
- [ ] Perform trace-backed qualitative error analysis only after the quantitative evaluation is frozen.
- [ ] Create the final experiment manifest with evaluation-set hash, annotation-export hash, model revisions, dates, rubric/prompt hashes, evidence inventory, seeds, and analysis-script commit.

## Literature and sourcing

- [x] Verify and populate initial bibliography from primary/final sources (Run 2).
- [x] Build source-to-claim map for Chapters 2--5 (Run 2).
- [x] Record publication-version corrections for CARB/Think-as-Locals, SafeWorld, CulturalBench, Skywork, and Wang et al. (Run 2).
- [x] Add survey/pluralistic-alignment sources required for Chapters 2--3 (Run 3).
- [x] Add dedicated intercultural-pragmatics support for D02 (Kecskes, Run 4).
- [x] Add dedicated family/gender/generational support for D07 (Georgas et al.; Inglehart & Norris, Run 4).
- [x] Add dedicated work/participation support for D08 (Schwartz; Inglehart & Baker, Run 4).
- [x] Add dedicated collective-memory support for D09 (Assmann & Czaplicka, Run 4).
- [x] Keep Chapter 5 literature claims within the source-to-claim boundaries established in Run 2 (Run 5).
- [x] Add statistical-method references required by the pre-declared human-agreement and paired-comparison protocol (Run 6).
- [x] Draft the Introduction from the already-validated literature and implemented methodology without introducing result claims (post-Run-7).
- [ ] Continue claim-by-claim source verification during final prose editing; the bibliography is a validated seed, not a closed literature set.

## Writing and presentation

- [x] Write the full Introduction: motivation, problem statement, research gap, RQ1--RQ4, contributions, and thesis structure (post-Run-7).
- [x] Write Chapters 2 and 3 (Run 3).
- [x] Write literature-grounded D01--D10 derivation and operational framework in Chapter 4 (Run 4).
- [x] Write code-grounded Chapter 5 and validate it against the frozen implementation (Run 5).
- [x] Finalize Chapter 6 experimental design and evaluation protocol (Run 6).
- [x] Build the non-result methodology/evaluation figures and tables, complete reproducibility appendices, and add List of Figures/Tables (Run 7).
- [ ] After final frozen results exist, add only the concise empirical takeaway needed to calibrate the Introduction; do not change the pre-declared RQs post hoc.
- [ ] Populate Chapter 7 only from real frozen outputs and replace all `TBD` cells in the result table.
- [ ] Generate result-dependent plots only from final frozen data (agreement, per-dimension outcomes, coverage/abstention, efficiency as supported).
- [ ] Populate Chapter 8 only from real comparative cases and trace-backed errors.
- [ ] Finalize Chapter 9 threats to validity after the realized annotation and experiment properties are known.
- [ ] Finalize Abstract and Conclusion after the empirical results and discussion are complete.
- [ ] If the final verifier prompt-template hash differs from the Run-7 appendix snapshot, regenerate Appendix B before submission.

## Run 6/7 experimental freeze follow-up

- [ ] Decide whether PLT001--PLT030 remain the sole final evaluation sample or add a genuinely unseen confirmatory set.
- [ ] Freeze and archive the final five-annotator export before system-result analysis.
- [ ] Record whether the human survey randomized candidate order; if not, report fixed order as a limitation.
- [ ] Implement or wrap tie-aware Skywork ranking so an exact top-score tie yields `no_clear_winner`.
- [ ] Freeze the primary direct-judge prompt, backbone model, deterministic permutation schedule, and seed; then insert the exact prompt into Appendix B.
- [ ] Freeze the bootstrap replicate count and statistical-analysis seed in the analysis script.
- [ ] Replace all pending fields in Appendix D with the final experiment manifest before inspecting comparative results.

## Page-budget follow-up

- [ ] Revisit Chapter 3 during the final whole-thesis editing pass if the main-text page budget requires trimming; the Run-3 draft was approximately one page above its provisional 9--10 page target.
- [x] Keep Chapter 4 within its 6--7 page target during Run 4 (current numbered span remains pp. 20--26 after Run 7).
- [ ] Revisit Chapter 5 during final compression: after adding Run-7 explanatory figures its current numbered span is pp. 27--40 (14 pages), one page above the original 12--13 page target.
- [x] Chapter 6 currently occupies pp. 41--48 (8 pages), within its planned 7--8 page range.
- [ ] Revisit the Introduction during final compression if needed; the current full draft spans six numbered pages and is intentionally result-neutral.
- [ ] Recalculate the final 60--65 page main-body target only after Chapters 7--10 are substantively complete.
