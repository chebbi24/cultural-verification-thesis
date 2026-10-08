# Vericult Bachelor thesis — Overleaf project

This directory is the active thesis manuscript.

## Import into Overleaf

1. Download the `thesis/overleaf/` directory as a ZIP.
2. In Overleaf choose **New Project → Upload Project**.
3. Upload the ZIP.
4. Use `main.tex` as the main document.
5. Compile with **pdfLaTeX** and **Biber**.

## Current completion state

The report is written against the frozen final **360 × 1** experiment and the final Vericult 1.1 architecture.

Completed in the manuscript:
- Abstract narrative, with only the final empirical paragraph left open.
- Chapters 1–6 fully rewritten for the final experiment.
- Verified related-work section and bibliography.
- Detailed D01–D10 framework.
- Full Vericult methodology with code excerpts from the frozen repository.
- PLT120, External120 and ExternalRedteam120 methodology and concrete prompt examples.
- Frozen generator/verifier configuration and semantic hashes.
- LIVE → audit/freeze → REPLAY protocol.
- Result-independent discussion and error-analysis framework.
- Threats to validity and limitations.
- Conclusion and future work.
- Complete runtime rubric appendix.
- Reproducibility manifest.
- Semantic prompt-template appendix.
- Dataset/prompt-example appendix.

The only red `FINAL RESULTS` placeholders are intentionally result-dependent:
- Chapter 7 quantitative tables and analysis;
- result-dependent paragraphs in the Abstract, Discussion, and Conclusion;
- final evidence/output hashes and run dates.

These placeholders must be filled from the archived final outputs after LIVE, evidence audit, REPLAY, and the final baseline runs. Do not replace them with estimates.

## Frozen experiment references

- Experiment branch: `agent/final-experiment-ready`
- Thesis branch: `thesis/full-report-rewrite`
- Semantic verifier freeze: `099e4116a809ee004c1cdea04d1bcc2a14e7d142`
- Final experiment ID: `thesis-final-v4-360x1`
- Primary Vericult result mode: `REPLAY`


## Writing style for the final pass

Keep the report at Bachelor-thesis level. Use simple English and short, direct sentences. Prefer concrete descriptions of what the code or experiment does over abstract wording. Do not add inflated novelty claims, marketing language, or phrases that sound more certain than the evidence supports. Keep technical terms only when they are needed and define them before use.

This style also applies when the final results are inserted.
