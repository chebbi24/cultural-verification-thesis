# Cleanup and migration record

## Source state

The previous `main` snapshot mixed multiple benchmark generations, duplicate outputs, a committed local virtual environment, source PDFs, a Numbers file, a Colab setup notebook, and three verifier generations. During the initial rebuild, a newer synthetic V3 matrix was incorrectly treated as authoritative. The canonical benchmark has now been restored from the historical 300-row `data/prompts/benchmark.csv`, which is byte-identical to `german_culture_benchmark_300_no_prefixes.csv`.

## Retained concepts and data

- The historical 60-parent × five-form benchmark, normalized to `RT001`–`RT300` without changing prompt text.
- Ten domains, thirty available subdimensions, fourteen issues, and five historical prompt forms.
- Full source metadata and hashes, including 54 custom and six SafeWorld-adapted parent prompts.
- One merged, remapped 450-response legacy pool.
- One 30×4 diagnostic legacy pilot.
- Compact legacy candidate scores needed to reproduce the pilot agreement analysis.
- Explicit migration script, hashes, and data manifest.
- A 19-row crosswalk from the supplied `taxonomy_v1.csv` to the canonical v2 issue taxonomy.

## Removed from the working tree

- Committed `.venv` and platform-specific binaries.
- Duplicate prompt files (`german_culture*`, `redteam_v1`, `redteam_v2*`, and the semicolon-delimited source snapshot). Their authoritative prompt text and metadata are retained in the canonical benchmark and source-metadata files.
- The synthetic V3 prompt matrix as the canonical benchmark; it remains only in external migration history and is not used for experiments.
- Duplicate raw Llama output files and test output.
- Superseded taxonomy inventories and Swiss-only source tables. The user-supplied v1 taxonomy is retained only as the normalized crosswalk, not as a second active taxonomy.
- Two large vendored PDFs; references now use source metadata and URLs.
- Obsolete verifier, pretest, runner, and empty web-search scripts.
- Colab bootstrap notebook and temporary archive formats.

All tracked removals remain recoverable from Git history. `scripts/rebuild_canonical_data.py` records the August 2026 migration rules.
