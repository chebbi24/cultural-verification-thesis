# Best-of-4 v2 generation

Best-of-4 v2 reuses the frozen PLT001-PLT030 prompts but replaces the candidate
responses with outputs from four stronger local Ollama models.

Generation is intentionally independent of Vericult, the D01-D10 rubric, human
labels, and any cultural winner signal. Only a minimal technical quality gate is
applied (successful, nonempty response). The model-to-candidate mapping is hidden
from the human-facing dataset and retained separately for analysis.

The frozen generation models and settings are in
`experiments/best_of4_v2_generation.json`.

Install the models once:

```bash
ollama pull qwen3:8b
ollama pull gemma3:12b
ollama pull llama3.1:8b
ollama pull mistral-nemo:12b
```

Smoke test one prompt:

```bash
python scripts/generate_best_of4_v2.py --prompt-id PLT001
```

Then generate all PLT001-PLT030:

```bash
python scripts/generate_best_of4_v2.py
```

The script checkpoints each completed model/prompt pair and resumes automatically.
Local models are run sequentially by design to avoid loading several large models
into Mac unified memory simultaneously. The final manifest records each Ollama
model digest for reproducibility.
