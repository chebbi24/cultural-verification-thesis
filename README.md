# Standalone cultural verifier

`cultverify` evaluates one **prompt + response** pair using an evidence-grounded
D01–D10 rubric. Reward models are independent baselines: neither their scores nor
human labels, expected issues, benchmark answers or benchmark metadata enter the
verifier. No cultural rules, keyword overrides, score caps or hard-failure gates
are hard-coded in Python.

## Method

Prompt → supported context → shared dimension plan → up to three material targets
→ two neutral questions per retrievable target → **candidate-blind evidence**
→ query rewriting → retrieval and provenance filtering → source classification
→ evidence memo → exact-span grounding → blind support/relevance gate
→ optional single gap-specific follow-up → **frozen memo**
→ target comparison → D01–D10 scoring → equal aggregation → JSON trace.

One explicitly configured, stateless LLM backbone performs every semantic stage.
Temperature defaults to zero; there is no model fallback. Python validates structure,
quotes, citations, links and budgets; it does not decide cultural appropriateness.
Each nonempty dimension plan has one primary dimension, but **all dimensions have
equal scoring weight**. No external search is performed for internal-quality or
non-verifiable-value targets. These are assessed directly in dimension scoring.

The runtime rubric preserves the existing D01–D10 definitions and scoring anchors.
Its packaged copy standardizes the requested names, removes benchmark parent mappings,
and replaces Germany-specific question wording with the stated context. Original
D01–D10 CSV resources remain under `data/csv/`; neither they nor any benchmark are
required at runtime. The empirical validation of the rubric is a separate thesis phase.

## Install

Python 3.10+; run from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
```

`src/requirements.txt` is a compatibility install entry point. `requirements.lock`
pins the tested dependency environment, including test tools; install it before
`pip install --no-deps -e .` when reproducing that environment (tested on Python 3.12).
The local virtual environment is ignored and no longer tracked; Git history is not rewritten.

## Configuration and CLI

The model must be selected explicitly. Export variables from `.env.example` as
appropriate; the program does **not** automatically source `.env` files.

```bash
export CULTVERIFY_PROVIDER=ollama
export CULTVERIFY_MODEL='qwen3:4b'  # setup example, not a recommended final research model
export TAVILY_API_KEY='your-key'
python -m cultverify.cli verify \
  --prompt 'How should I write a first email to a university professor?' \
  --response 'Use a polite greeting and clearly explain the purpose of your message.'
```

Ollama must be running with the selected model installed. For OpenRouter, set
`CULTVERIFY_PROVIDER=openrouter`, an explicit model ID, and `OPENROUTER_API_KEY`.
Choose a model supporting JSON-schema structured output. Pin its revision/digest
where the provider permits it; a mutable model alias is not a reproducibility guarantee.
No credentials are included in traces or configuration JSON.

For Best-of-4, `responses.json` is a plain JSON array of four response strings:

```bash
python -m cultverify.cli rank --prompt-file prompt.txt --responses-file responses.json
```

`--config config.json` accepts the fields in `cultverify.config.Config`, including
timeouts, target/search budgets, exclusion lists and artifact directories. Priority:
configuration file → supported environment variables → explicit CLI flags.

Both commands print structured JSON. Exit code 0 indicates completed execution
(including genuine abstention); 2 indicates invalid configuration or pipeline failure.
Winner indices are **zero-based**; ties and all-abstained sets return `no_clear_winner`.

## Python API

```python
import os
from cultverify import Config, CulturalVerifier
from cultverify.llm import HTTPModel
from cultverify.retrieval import TavilyRetriever

config = Config(verifier_model_provider='ollama', verifier_model_id='qwen3:4b')
verifier = CulturalVerifier(
    llm=HTTPModel(config),
    retriever=TavilyRetriever(os.environ['TAVILY_API_KEY'], config.search_depth),
    config=config,
)
result = verifier.verify(prompt='Your prompt', response='Your response')
ranking = verifier.rank(prompt='Your prompt', responses=['A text', 'B text', 'C text', 'D text'])
```

Custom adapters implement `LLM.complete(...)` and `Retriever.search(...)`; LLM
adapters must be stateless, use the supplied immutable configuration and never keep
conversation history between stages. The included adapters satisfy this contract.
The public verification methods accept no benchmark/annotation metadata.

## LIVE, REPLAY and evidence freezing

LIVE uses the implemented Tavily adapter. It filters results before any evidence
LLM call and persists full records of the **search content actually used**, URLs,
ranks, provider scores, timestamps and hashes. This adapter uses search excerpts,
not a claim to have downloaded entire source pages. It requests up to twice `top_k`
results to allow filtering and deduplication; fewer than three useful sources may remain.
Two initial questions share round 1. At most one additional question is searched
in round 2 **per target**, with no recursive searching.

Snapshots and question/query schedules are stored under `artifacts/evidence`.
Existing snapshots and schedules are reused. Use a new cache directory for a new
LIVE evidence collection; preserve the frozen directory with the experiment records.

The primary thesis experiment uses **REPLAY**:

```bash
python -m cultverify.cli verify --mode REPLAY --prompt-file prompt.txt --response-file response.txt
```

REPLAY requires the same initial context/questions and configuration as the LIVE
collection, loads its saved queries, follow-up schedule and exact documents, and
never retains or invokes a live retriever. Missing or inconsistent snapshots fail
explicitly—there is no live fallback. LLM synthesis/scoring still run and can incur
model costs; REPLAY is not an offline substitute for an LLM. If model nondeterminism
changes the initial context/questions, a schedule miss is explicit. Temperature zero
and fixed artifacts reduce variation; they do not promise identical model output.

## Blindness, contamination and traceability

`BlindEvidenceEngine.evaluate(questions, context)` accepts only the exact, closed
question/context schemas. Candidate text, target objects, candidate letters and
verdicts are not passed to query rewriting, retrieval, classification or synthesis.
The two neutral questions necessarily convey the issue under investigation; this
is a structural candidate-blind boundary, **not proof that question wording is unbiased**.
Source text is untrusted data in all semantic prompts.

The memo and its nested records/collections are immutable. Free-form memo summaries are
not passed to the follow-up planner, target comparator or dimension scorer; those stages
receive only grounded frozen statement-level evidence. Only after the memo is frozen
does target comparison receive the target again. Trace events record this ordering.
Every cited factual statement links to retrieved document IDs. Python resolves citations
only from source spans that match retrieved text after conservative formatting
normalization. A separate candidate-blind semantic gate rejects statements that exceed
their quoted supports or do not materially answer a verification question. These checks
reduce unsupported synthesis but remain model judgments that require empirical audit.

Configure `excluded_domains`, `excluded_repos` (owner/repository) and
`excluded_paths` (URL/path globs) for the exact external benchmark sources used.
The thesis repository, local resources and common annotation/result paths are
blocked by default. GitHub/raw/API repository paths are recognized. Filtered URLs
and reasons are traced. Unknown mirrors cannot be ruled out by provenance filtering;
review and freeze the exclusion list before held-out evaluation. No label files
are loaded by the package.

`artifacts/traces/<run_id>.json` records configuration, model ID, Git commit,
prompt/response hashes, rubric/template hashes and versions, timestamped semantic
calls and retry outcomes, context, plan, targets, questions, queries, documents,
source classifications, memo revisions, final memo links, verdicts, scores, coverage,
errors and partial evidence on failed runs. Ranking writes one complete trace per
candidate and reuses the exact prompt-level plan across all four.

## Scores and limitations

Dimensions receive 0, 1, 2 or `abstain`. If every retrievable target relevant to a
dimension ends `insufficient` and there is no relevant non-retrieval target that can be
assessed directly, that dimension must abstain. The overall score is the mean of scored
dimensions divided by two; if none can be scored it is `null`. There are no caps or
primary/secondary weighting differences. Ranking uses exact rational comparison,
so floating-point rounding cannot break a mathematical tie. No tie margin is added.

- `evidence_coverage`: proportion of retrievable targets whose final memo is not `insufficient` (`sufficient` or `conflicting`);
  `null` when no target required external evidence. This is not factual accuracy.
- `scored_count`, `applicable_count`, `abstained_dimensions`: scoring coverage.
- `coverage_comparable`: whether all candidates scored the same dimension set.
  Per the frozen specification, a difference is reported but does not override the
  highest-score rule. Compare partially abstained rankings cautiously.
- `targets_truncated`: the extractor reported more material units than its budget.
- `status=failed`: invalid structural output or provider/replay failure; dimensions
  abstain rather than receiving fabricated scores. Valid context extraction failure
  handling is conservative: after bounded retries the context becomes unknown.

The prompt-level plan can omit concerns introduced only by a response. Quoted targets
cannot directly represent omissions, although the scorer sees the full prompt/response
and is instructed to consider unmet explicit requirements. These are limitations of
the frozen method, not hidden special-case corrections.

## Tests and independent baseline

```bash
pytest -q
ruff check src/cultverify tests
ruff format --check src/cultverify tests
```

Normal tests use deterministic fixtures and mocked HTTP boundaries, require no paid
API calls, and include verification, Best-of-4 and CLI end-to-end paths. They establish
software contracts, not empirical cultural accuracy or superiority to reward models.
For the separately gated real-provider LIVE → REPLAY smoke test, configure the model
and keys, then run `CULTVERIFY_RUN_LIVE=1 pytest -q -m live`.

`src/baseline_rm.py` remains independent and unchanged. Install its optional stack
with `pip install -e '.[rm]'`. Its input and output never enter `cultverify`.

## Repository cleanup

The previous verifier implementation, its runners, scoring/hard-failure regression
tests and retired setup/release instructions were removed. The old T1–T19 taxonomy,
its mappings, taxonomy-only benchmark and preparation code were removed from this
branch. The old `data/prompts/benchmark.csv` is not a final benchmark and is removed.
Original D01–D10 resources, pilot candidates, research documents and historical outputs
remain. Historical notebooks and generation scripts are research records, not active
package entry points; their old paths may no longer work. See `docs/migration.md`.

Provider contracts: [Ollama chat](https://docs.ollama.com/api/chat),
[OpenRouter chat](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion),
[Tavily search](https://docs.tavily.com/documentation/api-reference/endpoint/search).
