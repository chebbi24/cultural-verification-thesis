# Run 6 - Experimental Design and Evaluation Protocol Audit

## Scope

Run 6 writes Chapter 6 only. It does not generate or analyze final results.

## What was fixed in the protocol

- Primary comparison target is agreement with an aggregated human reference, not CARB or provisional labels.
- Human reference uses five student annotators with A/B/C/D/No clear winner plus confidence 1-5.
- Primary vote aggregation: >=3 identical votes = majority; >=3 No clear winner = human no-clear-winner; otherwise unresolved split.
- Confidence does not weight the primary vote.
- Fleiss kappa is used for a complete balanced five-rater nominal matrix; nominal Krippendorff alpha is the fallback for missing/unbalanced ratings.
- PLT provisional AI labels remain development-only and are excluded from final reference construction.
- PLT001-PLT030 are described as a fixed evaluation sample, not automatically as strictly held-out, because they existed during project development.
- Verifier implementation is tied to cultverify-1.0.0 / commit 2e546a48ba0950e78f7bd244b5b37b7b475ccf2d.
- Final semantic verifier model remains explicitly unfrozen.
- LIVE is evidence acquisition; primary evaluation is planned in REPLAY against archived evidence.
- Skywork baseline remains independent and prompt-response only.
- Current Skywork exact-tie-by-order behavior is explicitly flagged for correction before the final run; protocol rule is exact maximum tie -> no_clear_winner.
- Primary direct judge should use the same semantic backbone as the verifier where possible, to isolate pipeline effects.
- Direct-judge candidate order uses a deterministic pre-generated permutation schedule.
- CARB is related work and qualitative discussion context, not a numerical head-to-head baseline unless actually reproduced on the same items.
- Primary outcome is top-choice agreement on resolved human-majority items.
- System abstention, execution failure, human no-clear-winner, and unresolved human split are distinct states.
- Coverage and selective agreement are reported together.
- Item-level bootstrap CIs and paired McNemar comparisons are pre-declared; exact McNemar is preferred for small discordant counts.
- Cost/latency are reported only if supported by provider logs or an external wrapper; they are not fabricated from traces.

## New statistical-method references

- Fleiss (1971), nominal agreement among many raters, DOI 10.1037/h0031619.
- Krippendorff (2018), Content Analysis, 4th ed.
- McNemar (1947), paired correlated proportions, DOI 10.1007/BF02295996.
- Efron & Tibshirani (1993), bootstrap methodology.

## Important unresolved freezes

1. Final semantic model/provider/revision/date.
2. Final direct-judge prompt and model.
3. Final human-annotation export.
4. Whether PLT001-PLT030 remain the sole final evaluation set or an additional genuinely unseen confirmatory set is added.
5. Candidate-order status in the already deployed human survey; do not claim randomization without logs.
6. Skywork tie-handling code must be corrected or wrapped before final results.
7. Exact experiment date and manifest hashes.

## Integrity decisions

The chapter intentionally does not call provisional AI annotations human ground truth. It also does not describe the PLT collection as strictly held-out without a provenance audit, does not interpret RM scores as probabilities, does not equate verifier abstention with human no-clear-winner, and does not claim CARB is outperformed.

## Validation status

A local LaTeX build with the Run-6 chapter and bibliography additions completed successfully. The generated manuscript was 64 pages at this stage. No unresolved citations, cross-references, or overfull-box warnings were present in the final build log. This page count is an intermediate project count and not a claim that all 64 pages are final substantive thesis content.
