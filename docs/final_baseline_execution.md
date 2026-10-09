# Final single-response baseline execution

This branch contains baseline-only runner changes. It must not replace the frozen
Vericult LIVE/REPLAY worktree while the primary experiment is running.

## Local layout

Keep the frozen verifier worktree unchanged:

```bash
# from the existing verifier checkout
git fetch origin
git worktree add ../cultural-verification-baselines \
  origin/baseline/final-360-parallel-runners
```

The original worktree keeps its ignored `artifacts/` directory. The baseline
worktree has its own independent `artifacts/` directory.

## Direct LLM-as-a-judge on KBS/L3S

```bash
cd ../cultural-verification-baselines
python -m venv .venv
source .venv/bin/activate
pip install -e .

cp /path/to/original/.env .env
set -a
source .env
set +a

python scripts/run_direct_judge_kbs.py
```

Output:

- `artifacts/final_experiment/results/direct_judge.jsonl`
- `artifacts/final_experiment/results/direct_judge.csv`

The runner uses the frozen Qwen3.6 L3S model, temperature 0, the D01-D10 rubric,
and no retrieval. Every item is checkpointed immediately. Re-running the command
skips valid completed items and retries failures.

## Skywork Reward V2 on Google Colab

Select a GPU runtime first, then:

```python
!git clone -b baseline/final-360-parallel-runners \
  https://github.com/chebbi24/cultural-verification-thesis.git
%cd cultural-verification-thesis
!pip install -e '.[rm]'
```

Run:

```python
!python scripts/run_reward_model_colab.py
```

Output:

- `artifacts/final_experiment/results/reward_model.jsonl`
- `artifacts/final_experiment/results/reward_model.csv`

The frozen model is `Skywork/Skywork-Reward-V2-Qwen3-4B` at revision
`fd958fe`. The output is the raw scalar reward only; no cultural threshold is
invented.

To download the results in Colab:

```python
from google.colab import files
files.download("artifacts/final_experiment/results/reward_model.jsonl")
files.download("artifacts/final_experiment/results/reward_model.csv")
```

## Smoke tests

Use a temporary output path so a smoke test never contaminates the full result:

```bash
python scripts/run_direct_judge_kbs.py --limit 2 \
  --output /tmp/direct_judge_smoke.jsonl
```

For Colab:

```bash
python scripts/run_reward_model_colab.py --limit 2 \
  --output /tmp/reward_model_smoke.jsonl
```

The full run should use the default output paths.
