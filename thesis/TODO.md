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
- [ ] Continue claim-by-claim source verification during prose drafting; the bibliography is a validated seed, not a closed literature set.

## Writing still required

- [x] Write Chapters 2 and 3 (Run 3).
- [x] Write literature-grounded D01--D10 derivation and operational framework in Chapter 4 (Run 4).
- [x] Write code-grounded Chapter 5 and validate it against the frozen implementation (Run 5).
- [x] Finalize Chapter 6 experimental design and evaluation protocol (Run 6).
- [ ] Populate Chapter 7 only from real frozen outputs.
- [ ] Populate Chapter 8 only from real comparative cases and trace-backed errors.
- [ ] Finalize Chapter 9 threats to validity after the realized annotation and experiment properties are known.
- [ ] Finalize Introduction, Abstract, and Conclusion last.

## Run 6 experimental freeze follow-up

- [ ] Decide whether PLT001--PLT030 remain the sole final evaluation sample or add a genuinely unseen confirmatory set.
- [ ] Freeze and archive the final five-annotator export before system-result analysis.
- [ ] Record whether the human survey randomized candidate order; if not, report fixed order as a limitation.
- [ ] Implement or wrap tie-aware Skywork ranking so an exact top-score tie yields `no_clear_winner`.
- [ ] Freeze the primary direct-judge prompt, backbone model, deterministic permutation schedule, and seed.
- [ ] Freeze the bootstrap replicate count and statistical-analysis seed in the analysis script.
- [ ] Create the final experiment manifest before inspecting comparative results.

## Page-budget follow-up

- [ ] Revisit Chapter 3 during the final whole-thesis editing pass if the main-text page budget requires trimming; the Run-3 draft is approximately one page above its provisional 9--10 page target.
- [x] Keep Chapter 4 within its 6--7 page target during Run 4 (compiled span: pp. 20--26 at that stage).
- [x] Keep Chapter 5 within its 12--13 page target during Run 5 (compiled span: pp. 27--39 at that stage).
- [ ] Recheck Chapter 6 page allocation during the final whole-thesis compile after Chapters 7--10 are populated; the current 64-page project count includes unfinished later chapters and appendices.
