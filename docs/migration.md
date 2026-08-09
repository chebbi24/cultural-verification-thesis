# Cleanup and migration record

## Source state

The previous `main` snapshot mixed multiple benchmark generations, duplicate outputs, a committed local virtual environment, source PDFs, a Numbers file, a Colab setup notebook, and three verifier generations. The latest authoritative `RT` benchmark and verifier pilot existed outside that old repository snapshot.

## Retained concepts and data

- Final 300-item `RT` benchmark.
- Ten domains, thirty subdimensions, fourteen issues, and ten attacks.
- One merged, remapped 450-response legacy pool.
- One 30×4 diagnostic legacy pilot.
- Compact legacy candidate scores needed to reproduce the pilot agreement analysis.
- Explicit migration script, hashes, and data manifest.
- A 19-row crosswalk from the supplied `taxonomy_v1.csv` to the canonical v2 issue taxonomy.

## Removed from the working tree

- Committed `.venv` and platform-specific binaries.
- Superseded prompt files (`german_culture*`, `redteam_v1`, `redteam_v2*`, old `benchmark.csv`).
- Duplicate raw Llama output files and test output.
- Superseded taxonomy inventories and Swiss-only source tables. The user-supplied v1 taxonomy is retained only as the normalized crosswalk, not as a second active taxonomy.
- Two large vendored PDFs; references now use source metadata and URLs.
- Obsolete verifier, pretest, runner, and empty web-search scripts.
- Colab bootstrap notebook and temporary archive formats.

All tracked removals remain recoverable from Git history. `scripts/rebuild_canonical_data.py` records the August 2026 migration rules.
