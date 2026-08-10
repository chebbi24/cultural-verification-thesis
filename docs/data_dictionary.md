# Data dictionary and canonical identifiers

## Identifier policy

Identifiers are stable strings. They must never be reused for a different entity.

| Entity | Format | Example | Meaning |
|---|---|---|---|
| Domain | `Ddd` | `D01` | One of ten cultural content domains |
| Subdimension | `DddSdd` | `D01S01` | Domain-local subdimension; both components are zero-padded |
| Prompt form | `ATdd` | `AT01` | One of five historical prompt constructions |
| Final prompt | `RTddd` | `RT001` | Canonical red-team benchmark item |
| Reference claim | `RTddd-CLdd` | `RT001-CL01` | Item-specific verification boundary |
| Final candidate | `RTddd-Cn` | `RT001-C1` | Candidate position after recorded randomization |
| Legacy prompt | `LGddd` | `LG006` | Historical `G06` item retained only for the pilot |
| Pilot set | `PLTddd` | `PLT001` | One legacy Best-of-4 set |
| Pilot candidate | `PLTddd-Cn` | `PLT001-C1` | Candidate in a legacy pilot set |
| Annotation | `<set>-ANNdd` | `PLT001-ANN01` | One annotation record |
| Legacy output | `OUT-LGddd-Rdd` | `OUT-LG006-R03` | One stored generator run |

Historical `D01S1`, `G06`, `VT001`, and candidate letters `a`–`d` are normalized during migration. Historical parent IDs are retained only in the provenance files, as normalized `LGddd` lineage values and exact `Gdd` source-metadata values.

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

The five source prompt forms: `personal_dilemma`, `social_conflict`, `authority_interaction`, `foreigner_perspective`, and `ethical_justification`. The `attack_id` column name is preserved for compatibility with the rebuilt pipeline.

### `data/benchmark/prompts.csv`

The only authoritative benchmark prompt file.

| Column | Meaning |
|---|---|
| `prompt_id` | Stable `RT` identifier |
| `domain_id` | Primary content domain |
| `subdimension_id` | Closest primary v2 content subdimension |
| `attack_id` | Historical five-form prompt construction |
| `prompt_text` | Exact model input |

The 300 `prompt_text` values are copied unchanged from the historical semicolon-delimited `data/prompts/benchmark.csv` on legacy `main`. The canonical file preserves the rebuilt five-column comma-delimited schema; historical metadata is stored separately.

### `data/benchmark/lineage.csv`

Each historical `G01`–`G60` parent produced five prompt forms. Parent IDs are normalized to `LG001`–`LG060`; `parent_prompt_id` and `lineage_group_id` therefore identify the shared source scenario. `source_row_sha256` freezes every exact historical source row.

### `data/benchmark/source_metadata.csv`

One row per canonical prompt preserving the old benchmark ID, parent ID, form, category, variation, v1 taxonomy IDs, expected issue, legacy attack type, parent source, and exact source-file SHA-256. The parent-source distribution is 54 custom and six SafeWorld-adapted parents.

### `data/benchmark/splits.csv`

Deterministic 60/60/180 development, verifier-validation, and held-out test assignment. Splitting is performed at the 60-parent lineage-group level to prevent the five closely related variants of one scenario from leaking across splits. Each of the twelve historical categories contributes one parent to development, one to verifier validation, and three to test. Every split therefore contains all five prompt forms. The test split must remain untouched during parameter tuning.

### `data/evidence/reference_claims.csv`

One item-level verification plan per prompt. It stores the truth mode, response boundary, expected handling, evidence requirement, and open-web research brief. It is an adjudication scaffold, not a reference answer.

### `data/evidence/source_registry.csv`

An empty versioned schema. Actual sources are produced by an agentic search run under `artifacts/` with timestamps, queries, response IDs, and URLs. Search output must never be silently copied into this file without its run metadata.

### `data/pilot/*`

The only retained legacy experiment. All files are explicitly marked diagnostic. `provisional_annotations.csv` contains AI-generated preliminary selections, not human labels. `provisional_metrics.json` must never be reported as human accuracy.

### `data/manifest.json`

Byte size and SHA-256 for every versioned data artifact, allowing exact snapshot verification.
