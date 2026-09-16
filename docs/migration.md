# Clean verifier migration

Base: `agent/final-standalone-verifier` at `06e629a86d8b7fe30ae2ba7d10652854b85bfa3a`.
Implementation branch: `agent/final-verifier` (the user's opening branch instruction).
The source branch is unchanged. No history rewrite is performed.

## Removed active implementation

- `src/verifier.py`, `src/verifier_v7_legacy.py`, `src/verifier_v8_core.py`:
  replaced from first principles, with no inherited semantic implementation.
- `src/run_verifier.py`, `src/evaluate_best_of4.py`, `src/check_verifier_setup.py`:
  replaced by `python -m cultverify.cli verify|rank`.
- `src/hard_failures.py`, `src/evaluate_hard_failures.py`: retired safety/eligibility
  pipeline; it is not part of cultural scoring or ranking.
- `src/pretest.py`: retired taxonomy-dependent preparation.
- `src/web_search.py`: empty unused file.
- Three old verifier test modules: their imports and expected heuristics no longer
  describe the method; replaced by contract, pipeline, replay, adapter and CLI tests.
- Old verifier specification, release checklist and hard-failure protocol:
  replaced by the active README and this migration note.

## Removed retired taxonomy assets

`data/csv/taxonomy_v1.csv`, `taxonomy_swiss_ai.csv`, `PRISM.csv`, `categories.csv`,
`data/prompts/benchmark.csv` and `german_culture.csv` contain the retired taxonomy
or dependent mappings. They are available in the parent commit if needed for historical
reconstruction. Valid D01–D10 resources were inspected and retained.

`src/cultural_dimensions.py` is retained as the original D01–D10 research utility;
`cultverify` does not import it or depend on its benchmark alignment checks.
The standalone reward-model baseline is unchanged and needs no retired imports.

Tracked `.venv` files were removed from the Git index, not from the user's local
virtual environment. The new package depends only on Pydantic and requests; the
heavy reward-model dependencies are optional.

## Intentional scope

No benchmark expansion, human annotation collection, silver labeling, UI, CARB
integration or tuning on pilot winners was added. Mock output scores are fixtures,
never evaluation results. The frozen highest-score ranking rule is preserved;
unequal coverage is exposed as a diagnostic, not a new winner-selection policy.
