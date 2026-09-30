# Learner model v2

The learner-state field `support_estimate` was misleadingly named. The legacy
algorithm already moved the value upward for positive evidence of understanding
and downward for negative evidence. Version 2 therefore renames it to
`understanding_estimate` without inverting existing numeric values.

Interpretation:

- `0.0` – strong evidence of weak demonstrated understanding
- `0.5` – uncertain / insufficient evidence
- `1.0` – strong evidence of good demonstrated understanding

This is an internal, uncertain estimate. It is not a grade and must not be shown
to the learner as an objective measure.

## Evidence policy

The classifier should use `positive` only when the learner clearly demonstrates
correct understanding, and `negative` only when the learner clearly demonstrates
incorrect understanding. Asking for help, pasting broken code, reporting an
error, or expressing uncertainty is normally `neutral`.

Neutral observations increase `observations` but do not change the estimate.

## Stored topic fields

- `understanding_estimate`: current 0..1 estimate
- `observations`: all classified messages for the topic
- `evidence_observations`: new positive + negative evidence observations
- `positive_evidence`: count of new positive evidence observations
- `negative_evidence`: count of new negative evidence observations
- `legacy_evidence_observations`: historical weight retained from the previous model
- `legacy_evidence`: marks records that include pre-v2 history

The migration cannot reconstruct the exact historical mix of positive, neutral,
and negative classifications because those per-message signals were not stored in
the learner-state files. It therefore preserves the old numeric estimate and uses
old observations only as historical weight instead of fabricating evidence counts.

## Migration

Dry-run:

`python scripts/migrate_understanding_estimate.py`

Apply:

`python scripts/migrate_understanding_estimate.py --apply`

Before writing any migrated student files, the script creates a backup under
`data/backups/learner_model_v2_<timestamp>/students/`.
