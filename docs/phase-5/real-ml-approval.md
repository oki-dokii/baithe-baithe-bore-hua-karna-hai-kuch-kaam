# Real-data ML experiment gate

This is an **offline experiment path**, not permission to deploy risk scores or give drilling instructions. The synthetic trainer remains synthetic-only. `/api/v1/risk/current` still reports no model.

## What must exist first

1. A permitted public/private dataset and a **qualified** `drilling_parameter_source` with approved depth reference, units, timezone, rig-state interpretation, and complete forward-drilling sensor rows.
2. A `mud-loss-adapter-input-v1` evidence JSON. Every anchor `sample_id` must be the UUID of a current qualified `drilling_parameter_sample`; its well, wellbore, timestamp, depth, source record ID, and five sensor values must match the database. The six-feature window is completed using a reviewed mud-program density.
3. Density and coverage assertions must cite a linked source document as `document:<source_document UUID>`. These intervals, values, and `event_free_reviewed` are **manual reviewer attestations**; a document link alone does not prove them. A negative requires explicit reviewed event-free coverage through the full 100 m horizon. A positive must identify an approved `drilling_event` and linked `extracted_passage` by UUID, with matching depth and onset bounds. Approved mud-loss events cannot be omitted from a horizon to create a negative. Anchors with a possibly ongoing approved loss are excluded when an end depth is absent or overlaps the anchor.
4. Physical wells (including sidetracks) must be disjoint across train/validation/test; each split needs at least two physical wells and both classes. This is a structural floor, **not statistical adequacy**.

## Submission and approval

The engineer/reviewer submits the bundle to `POST /api/v1/ml/evidence/submit` with `{ "source_id": "...", "evidence": { ... } }`. This validates the source join and records an immutable evidence digest with the authenticated submitter. A different authenticated reviewer uses `POST /api/v1/ml/experiments/approve` with `{ "submission_id": "...", "review_reference": "...", "evidence": { ... } }`. The exact digest must match, `domain_reviewed` must be true, and the manifest audit must have no blockers. A ledger entry and immutable approval row bind the reviewer, source checksum, evidence checksum, and manifest checksum. The `review_reference` should point to the signed review record; it is not automatically verified by the application.

The bundle is not stored by this approval workflow. Retain it securely alongside the review record; do not commit private source data or raw report excerpts. Submission and approval are separate authenticated actions, but source/coverage/density interpretations still require substantive domain review outside the software.

## Offline training only

From `backend/`, with a configured database:

```sh
.venv/bin/python -m nwis.train_real_mud_loss /secure/path/evidence.json \
  --source-id SOURCE_UUID --approval-id APPROVAL_UUID --out-dir /secure/path/experiment-output
```

The trainer re-checks the evidence digest, current qualified source rows, cited events, manifest hash, and structural audit. It fits a deterministic logistic baseline on training wells, selects a threshold on validation wells, and compares against prevalence on untouched test wells. Output is labeled `offline_real_experiment_only`, carries the approval ID, and is never loaded by the API. Do not interpret test metrics as OIL transfer validity or operational readiness. Site-specific external validation, lead-time and alert-burden analysis, calibration, and separate deployment governance remain required.

Current repository state: no real evidence bundle meets these requirements, no experiment approval has been granted, and no real model has been trained.
