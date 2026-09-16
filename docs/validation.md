# Implementation validation

Validation environment: Python 3.12; exact tested dependency versions in
`requirements.lock`. No paid model or search calls were made.

- Full active suite: **55 passed, 1 skipped** (`pytest -q`).
- Lint: `ruff check src/cultverify tests` passed.
- Formatting: `ruff format --check src/cultverify tests` passed.
- Built a distribution wheel, installed it with the locked dependencies into a new
  virtual environment, then ran rubric loading, mocked verification and Best-of-4
  outside the repository checkout. All passed.
- CLI verification and ranking are covered end-to-end with injected deterministic
  model/search adapters. The installed CLI help also passed.
- Real Ollama/OpenRouter and Tavily request shapes are tested at mocked HTTP boundaries.
  End-to-end real provider behavior is **not verified**: no model selection,
  `TAVILY_API_KEY` or `OPENROUTER_API_KEY` was configured in this environment.
  `test_real_live_then_replay` is the skipped, explicitly gated test.
- Legacy imports, old taxonomy IDs, cultural marker lists and expected-issue usage
  were checked in `src/cultverify`; none are present.
- Zero `.venv` files remain tracked. `src/baseline_rm.py` is unchanged.

The tests cover quote validation and recovery, schema/ID restrictions, target budgets,
neutral question shape, candidate-blind call boundaries, query inputs, bounded search,
source citations, provenance filtering, duplicate evidence, immutable memos, equal
aggregation, abstention, exact ties, shared planning, replay without search or query
rewriting, replay corruption/missing evidence, failed-run traces, model configuration,
provider transport errors, CLI operation and packaging resources.

The frozen ranking rule is unchanged: highest exact mean wins; exact ties abstain.
Unequal scoring coverage is exposed through `coverage_comparable` rather than silently
changing the winner rule. No empirical superiority or cultural-accuracy claim follows
from these software tests. The real smoke test and held-out human comparison remain
necessary before reporting empirical thesis results.
