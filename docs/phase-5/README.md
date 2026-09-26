# Phase 5 — Predictive validation (started, not complete)

## Current capability

No predictive model has been trained or deployed. Historical alerts continue to use the Phase 4 evidence rule. This delivery adds a model-readiness workspace, authenticated readiness/current-risk APIs, and a local JSON-window qualification command. ML-01 remains unmet; ML-02's unavailable-score path is implemented, not its trained-model path.

The first **proposed** task is mud-loss onset in `(anchor MD, anchor MD + 100 m]` during forward drilling. It differs from Phase 4's offset-event lookahead. Prediction excludes events already ongoing at the anchor. Full 100 m observed outcome coverage is required even for positives in this initial contract. No-event labels require reviewed coverage, not merely an absence of report mentions. The horizon and feature choices require domain review.

## Data needed before training

Request a permitted, de-identified sample covering multiple physical wells and their sidetracks, with original identities linked consistently, timestamps, MD/datum and units; pre-onset ROP, WOB, RPM, torque, flow-in and mud density; reviewed loss onsets; drilling-state/coverage records; and permission/provenance references. Preserve original geography. Do not send private reports to cloud providers by default.

Feature schema `mud-loss-features-v1`: `rop_m_per_h`, `wob_kn`, `rpm`, `torque_kn_m`, `flow_in_l_per_min`, `mud_density_kg_per_m3`. Values must be finite and nonnegative. These are candidate pre-anchor features, not proven causal predictors. A reviewed source adapter must ensure availability at prediction time, forward-drilling segments, sensor quality, gaps, units and no future aggregation. This adapter is not yet implemented.

## Local audit

From `backend`: `.venv/bin/python -m nwis.prediction ../specs/fixtures/prediction-window-example.json`.

The owned example intentionally exits **2**, reporting synthetic-only and insufficient split coverage. Exit 0 means structural checks passed, never permission to train or operational validation. The command performs no network calls or DB writes. Keep real inputs under ignored `data/raw/` or outside the repository. Invalid schemas raise validation errors locally; avoid publishing raw error output from private inputs.

The manifest records kind, source reference/checksum, permission reference and domain-review assertion. Each window records sample/physical-well/wellbore IDs, explicit train/validation/test split, anchor, feature cutoff, observed-through depth, next onset (or null), reviewed label source and fixed features. Output contains split counts, blockers and a normalized manifest checksum. Source checksums and permission assertions are metadata, not independently verified by this command.

All sidetracks and synthetic replicas must share the physical-well ID. The validator rejects known cross-split groups and inconsistent bore parents, duplicates, censored windows and unknown features. Two wells and both classes per split are only a structural floor, **not** a statistically sufficient sample size. The checks cannot discover incorrectly renamed wells or feature values that secretly contain future information.

## Candidate data audit — 2026-09-26

The official [3W dataset configuration](https://github.com/petrobras/3W/blob/main/dataset/dataset.ini), reporting dataset version 2.0.0 when inspected, lists production-flow/valve/hydrate events and production-system measurements. Its published class list does not supply drilling mud-loss, kick or stuck-pipe labels. **Not selected for this mud-loss target**; do not relabel its production events as drilling hazards. This is a metadata compatibility audit, not a downloaded-file qualification. No 3W files are included here.

Volve remains a candidate for report/telemetry qualification, not a selected training dataset. OIL labeled telemetry has not been supplied. No real dataset currently passes the predictive gate.

## Next gates

1. Qualify source files, permissions, coverage, labels and independent well identities; implement a source-specific feature/label adapter and reviewed split manifest.
2. Freeze one grouped split with chronology preserved. Fit preprocessing only on training wells. Propose a simple logistic baseline/model first; compare with training prevalence. Do not tune on the held-out wells.
3. Report well/sample counts, class balance, precision/recall/F1, PR-AUC where valid, lead distance and uncertainty. Select thresholds on validation wells. Sample-size adequacy needs separate review.
4. Calibrate only if data supports it; report calibration evidence before calling scores probabilities. Persist model/version, split and source hashes, feature schema and metrics in a model card.
5. Add inference only for qualified input; keep model signals separate from historical evidence alerts. Unsupported inputs return null with reason.

The current model card has null model version, score, metrics and calibration. Approved historical-event inventory is informational and is explicitly not a training-data count. No model-selection, model-training, inference, performance or operational-safety claim is made in this increment.
