# Vericult Bachelor Thesis — Final Rewrite

This directory contains the rewritten thesis report for the final **360 × 1** Vericult experiment.

## Status

This rewrite replaces the old Best-of-4-centred report as the main narrative. The old PLT30 Best-of-4 study is retained only as development provenance and a small pilot human-annotation study.

The final experimental unit is one fixed prompt-response pair:

- 120 PLT items
- 120 External items
- 120 Red-Team items
- 360 fixed responses in total
- one common generator: `gpt-oss:120b-mxfp4`
- Vericult backbone: `vllm/qwen3.6:35b-a3b-fp8`
- LIVE evidence acquisition
- evidence audit and freeze
- REPLAY as the primary reported Vericult run

## Writing policy

The report is intentionally written in simple Bachelor-level English. It avoids inflated claims and does not present unfinished experiments as completed results.

Final-result placeholders use double square brackets, for example:

`[[VERICULT_REPLAY_OUTCOME_DISTRIBUTION]]`

These must be replaced only from frozen experiment artifacts or values calculated directly from those artifacts.

## Files

- `00_abstract.md`
- `01_introduction.md`
- `02_background.md`
- `03_related_work.md`
- `04_cultural_framework.md`
- `05_vericult.md`
- `06_experimental_design.md`
- `07_results.md`
- `08_discussion.md`
- `09_limitations.md`
- `10_conclusion.md`
- `references.md`

## Main-content target

The target is roughly **60–65 pages of main text**, excluding bibliography and appendices. The chapter split is approximately:

| Chapter | Target pages |
|---|---:|
| 1 Introduction | 4–5 |
| 2 Background | 6–7 |
| 3 Related Work | 8–10 |
| 4 Cultural framework | 6–7 |
| 5 Vericult | 12–13 |
| 6 Experimental design | 7–8 |
| 7 Results | 6–8 |
| 8 Discussion and error analysis | 6–7 |
| 9 Limitations | 3–4 |
| 10 Conclusion | 2–3 |

The report should not be padded to reach the page target. Tables, figures, code excerpts, prompt examples and appendices should be used where they improve understanding.
