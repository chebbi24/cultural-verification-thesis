# Best-of-4 v2 generation

Best-of-4 v2 reuses the frozen PLT001-PLT030 prompts but replaces the candidate
responses with outputs from four strong independent model families.

Generation is intentionally independent of Vericult, the D01-D10 rubric, human
labels, and any cultural winner signal. Only a minimal technical quality gate is
applied (successful, nonempty response). The model-to-candidate mapping is hidden
from the human-facing dataset and retained separately for analysis.

Models are frozen in `experiments/best_of4_v2_generation.json`.

Run:

```bash
export OPENROUTER_API_KEY=...
python scripts/generate_best_of4_v2.py
```

Smoke test one prompt without building the canonical dataset yet:

```bash
python scripts/generate_best_of4_v2.py --prompt-id PLT001
```

The script checkpoints raw generations and resumes completed model/prompt pairs.
