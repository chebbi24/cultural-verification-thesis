# Run 7 - Figures, Tables, Appendices, and Reproducibility Audit

## Scope
Run 7 adds only presentation and reproducibility infrastructure. It does **not** create empirical results, select qualitative cases, freeze the final semantic model, or execute the comparative experiment.

## Added methodology/evaluation figures
Seven self-contained TikZ figures were added under `thesis/figures/`:

1. `d01d10_framework.tex` - equal, non-hierarchical view of D01--D10.
2. `verifier_architecture.tex` - end-to-end verifier control flow.
3. `blind_boundary.tex` - exact location and limitation of the candidate-blind evidence stage.
4. `best_of4_shared_plan.tex` - shared prompt-level planning with independent A--D evaluation and exact tie behavior.
5. `live_replay.tex` - distinction between LIVE evidence acquisition and REPLAY reuse/verification.
6. `research_design.tex` - independent human/verifier/Skywork/direct-judge comparison design.
7. `human_annotation_workflow.tex` - five-annotator vote/confidence and majority/unresolved-split construction.

The figures intentionally avoid result values. Their claims are limited to the frozen implementation and the pre-declared experimental protocol.

## Added tables
Run 7 added reusable table fragments under `thesis/tables/`:

- `source_types.tex` - exact runtime source-category labels with provenance descriptions.
- `evaluation_systems.tex` - independent-system input/output separation.
- `experiment_freeze.tex` - implemented constants vs values still pending freeze.
- `evaluation_metrics.tex` - pre-declared primary/secondary evaluation quantities.
- `results_template.tex` - Chapter 7 result shell with every empirical cell set to `TBD`.
- `error_case_template.tex` - qualitative-analysis shell that is intentionally not yet populated or inserted into the discussion chapter.

No numerical result has been invented.

## Appendix completion

### Appendix A - Complete runtime rubric
The appendix now reproduces the exact D01--D10 definitions, scoring questions, and 0/1/2 anchors from `src/cultverify/resources/rubric.csv` at implementation commit `2e546a48ba0950e78f7bd244b5b37b7b475ccf2d`. `abstain` is documented separately because it is a runtime scoring state rather than a CSV anchor.

### Appendix B - Semantic prompts
The current versioned `COMMON` instruction and all ten semantic stage templates from `src/cultverify/prompts.py` are reproduced verbatim except for visual line wrapping. The appendix explicitly requires regeneration if the final experiment prompt hash changes. The direct-judge prompt remains a marked placeholder because it has not yet been scientifically frozen.

### Appendix C - Human annotation protocol
The appendix records the five-student A/B/C/D/No-clear-winner task, required confidence 1--5 field, majority/unresolved-split rule, blinding requirements, and minimum archived export fields. It does not assume candidate-order randomization or verbal confidence anchors that are not yet verified from the final survey export.

### Appendix D - Reproducibility manifest
The appendix records already fixed implementation properties (repository, branch/commit, pipeline version, rubric, prompt location, budgets and Skywork identifier) separately from fields that remain pending (final semantic model, annotation hash, evidence inventory, direct-judge configuration, statistical seed, experiment dates). It also records the required execution order from Chapter 6.

## Main-document integration
- Added `List of Figures` and `List of Tables` to the front matter.
- Added TikZ, TabularX, Listings and related presentation packages required by the self-contained thesis.
- Added the primary result-table shell to Chapter 7 without populating results.
- Result-dependent plots remain explicitly deferred until the final frozen experiment.

## Compile and visual validation
Final Run-7 local build:

- `latexmk -pdf` completed successfully.
- 76 total PDF pages including front matter, bibliography and expanded appendices after adding List of Figures and List of Tables.
- Numbered main body currently ends at p. 54; Chapters 7--10 remain substantially unfinished, so this is **not** the final main-body page count.
- Chapter 4: pp. 20--26.
- Chapter 5: pp. 27--40 after adding figures; one page above its original provisional target and flagged for final compression.
- Chapter 6: pp. 41--48, within its planned 7--8 page range.
- No unresolved citations or cross-references.
- No overfull-box warnings after the final layout pass.
- Key pages containing figures, tables and appendices were re-rendered and visually inspected after the final compile.

## Claims deliberately withheld
Run 7 does not claim that:
- the verifier outperforms Skywork, a direct judge, CARB, or humans;
- candidate blindness eliminates bias;
- evidence coverage is correctness;
- the five annotators constitute cultural ground truth;
- LIVE/REPLAY is fully deterministic;
- the `TBD` result-table entries have any implied expected ordering.

## Stopping point
Runs 1--7 are complete. Run 8 must begin only after the required empirical freezes and real system/human outputs exist; it will populate Chapter 7 from those frozen outputs rather than from development artifacts.
