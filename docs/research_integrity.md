# Research-integrity boundary

The repository separates four kinds of provenance:

| Provenance | Permitted use |
|---|---|
| `human_independent` | Primary annotation before adjudication |
| `human_adjudicated` | Frozen gold label after disagreement resolution |
| `synthetic_model_provisional` | Pilot triage and user review only |
| `llm_judge` | Experimental verifier output only |

Synthetic labels cannot be reported as human annotations, even if a supervisor permits a 20-student annotation design in principle. Permission to recruit students is not evidence that students were recruited or performed the task.

The final thesis must state the actual annotator count, recruitment method, assignment design, compensation if any, agreement statistic, adjudication process, and exclusions. Any deviation must be logged rather than backfilled with invented records.

Generated evidence is also provenance-sensitive. A URL is not automatically authoritative. Search results remain `unreviewed` until their relevance, jurisdiction, date, and source role have been assessed. Search failure is an abstention and must not be converted into evidence against a candidate.
