# Data dictionary and canonical identifiers

## Identifier policy

Identifiers are stable strings. They must never be reused for a different entity.

| Entity | Format | Example | Meaning |
|---|---|---|---|
| Domain | `Ddd` | `D01` | One of ten cultural content domains |
| Subdimension | `DddSdd` | `D01S01` | Domain-local subdimension; both components are zero-padded |
| Attack | `ATdd` | `AT01` | One of ten cross-cutting prompt constructions |
| Final prompt | `RTddd` | `RT001` | Canonical red-team benchmark item |
| Reference claim | `RTddd-CLdd` | `RT001-CL01` | Item-specific verification boundary |
| Final candidate | `RTddd-Cn` | `RT001-C1` | Candidate position after recorded randomization |
| Legacy prompt | `LGddd` | `LG006` | Historical `G06` item retained only for the pilot |
| Pilot set | `PLTddd` | `PLT001` | One legacy Best-of-4 set |
| Pilot candidate | `PLTddd-Cn` | `PLT001-C1` | Candidate in a legacy pilot set |
| Annotation | `<set>-ANNdd` | `PLT001-ANN01` | One annotation record |
| Legacy output | `OUT-LGddd-Rdd` | `OUT-LG006-R03` | One stored generator run |

Historical `D01S1`, `G06`, `VT001`, and candidate letters `a`–`d` are normalized only during migration. They do not appear in canonical files.

## Canonical data files

### `data/taxonomy/domains.csv`

One row per content domain. `carb_parent_mapping` is retained solely for backward comparison.

### `data/taxonomy/subdimensions.csv`

Three rows per domain. `domain_id` is a foreign key into `domains.csv`.

### `data/taxonomy/issues.csv`

Cross-cutting response failures. These are not prompt content domains.

### `data/taxonomy/legacy_v1_crosswalk.csv`

Migration-only mapping for the supplied 19-row `taxonomy_v1.csv`. The older dimensions mixed communication contexts with failure types, so they are mapped into the broader v2 issues instead of remaining a competing active taxonomy. Every row preserves the supplied description, example, source filename, and exact source-file SHA-256.

### `data/taxonomy/attacks.csv`

The ten balanced prompt-construction methods. `method_source_url` supports method provenance and is not item-level answer evidence.

### `data/benchmark/prompts.csv`

The only authoritative benchmark prompt file.

| Column | Meaning |
|---|---|
| `prompt_id` | Stable `RT` identifier |
| `domain_id` | Primary content domain |
| `subdimension_id` | Primary balanced subdimension |
| `attack_id` | Prompt-construction attack |
| `prompt_text` | Exact model input |

### `data/benchmark/lineage.csv`

The final `RT` items were independently authored in a balanced attack matrix. They are not children of the superseded `Pxxx`/60-seed dataset. Therefore `parent_prompt_id` is empty and `lineage_group_id` equals `prompt_id`. `source_row_sha256` freezes the migrated row.

### `data/benchmark/splits.csv`

Deterministic 60/60/180 development, verifier-validation, and held-out test assignment. Each split contains every domain, every subdimension, and all ten attacks. The test split must remain untouched during parameter tuning.

### `data/evidence/reference_claims.csv`

One item-level verification plan per prompt. It stores the truth mode, response boundary, expected handling, evidence requirement, and open-web research brief. It is an adjudication scaffold, not a reference answer.

### `data/evidence/source_registry.csv`

An empty versioned schema. Actual sources are produced by an agentic search run under `artifacts/` with timestamps, queries, response IDs, and URLs. Search output must never be silently copied into this file without its run metadata.

### `data/pilot/*`

The only retained legacy experiment. All files are explicitly marked diagnostic. `provisional_annotations.csv` contains AI-generated preliminary selections, not human labels. `provisional_metrics.json` must never be reported as human accuracy.

### `data/manifest.json`

Byte size and SHA-256 for every versioned data artifact, allowing exact snapshot verification.
