# Core references

This file lists research and implementation sources by stable URL instead of storing PDF copies in Git.

- CultureLLM: <https://arxiv.org/abs/2402.10946>
- Diverse Human Value Alignment: <https://arxiv.org/abs/2511.00379>
- Supplied `taxonomy_v1.csv`: mapped row-by-row in `data/taxonomy/legacy_v1_crosswalk.csv`; the crosswalk records the exact uploaded-file SHA-256.
- OpenAI Responses API web search: <https://developers.openai.com/api/docs/guides/tools-web-search>
- The five prompt-form construction rules are historical researcher-defined augmentations recorded in `data/taxonomy/attacks.csv`; exact old IDs, source labels, and hashes are in `data/benchmark/source_metadata.csv`.
- Framework/source families supporting each cultural domain are recorded in `data/taxonomy/domains.csv`.

Item-level evidence is not hardcoded here. It is generated and timestamped by the agentic-search workflow, then reviewed for relevance and authority.
