# Phase 5 refinement: source-timed labels

This refines the provisional mud-loss-only experiment. A reviewer-approved `drilling_event` is a cited historical fact, **not automatically a timed pre-event ML label**. The pasted plan supplied by the project owner ends mid-sentence; only its complete rules were adopted. No real Volve file, model or OIL feed was qualified by this change.

## Event onset review

Migration `0006_event_onset_bounds` adds `onset_time_earliest`, `onset_time_latest` and `onset_time_basis` to `drilling_event`. Existing events migrate to `unspecified` with null bounds; there is no inferred timestamp. The review API and editorial document-review form allow a reviewer to enter timezone-aware source-supported bounds, with a rationale. An exact timelog requires equal bounds. A day-only DDR requires local 00:00:00 through 23:59:59.999999 with an explicit offset. Shift reports may have another reviewed interval. No time evidence means `unspecified`, which remains usable as historical evidence but not as a positive temporal label. A reviewer must document the source page and reporting timezone in the rationale; the API validates the shape of bounds, not their truth.

The API does **not** auto-populate these columns from a report date, upload timestamp, model text or depth. Nor does an approved event with timing automatically become an alert-eligible offset event or a model training row.

## Qualification without fitting

The Volve inventory audit can now record DDR and telemetry calendar periods per wellbore. File coexistence and actual calendar overlap are reported separately; a reviewed time/depth join requires both. It still does not open source files or grant training authorization.

The new offline `nwis.temporal_qualification` manifest audits **asserted** windows for one hazard (`mud_loss`, `stuck_pipe` or `kick`) and one explicit horizon in minutes. A positive window must end strictly before the earliest plausible onset, and the latest plausible onset must fall within the future horizon and observed telemetry coverage. The horizon condition prevents a window arbitrarily far before an incident from being mislabeled positive. A negative window requires reviewed, source-backed, event-free coverage that extends through the *entire future horizon*, not merely an absence of a report mention. A source-specific adapter and domain review must establish the coverage assertion; the CLI cannot do that from metadata.

The audit tabulates train/validation/test windows and independent physical wells, rejects well/sidetrack split leakage, requires at least two positive physical wells and a negative-only physical well, and requires both classes in every split. The last split check is stricter than the pasted plan's minimum two-positive-well floor: with only two positive wells, an independent train/validation/test evaluation cannot include a positive in every partition. Structural success still says `training_authorized: false` until source identities, permissions, chronology, label adjudication, independence and sample-size adequacy are independently checked. No model fitting or performance metric is implemented by this audit.

Run the owned synthetic example from the repository root:

```sh
backend/.venv/bin/python -m nwis.temporal_qualification specs/fixtures/temporal-qualification-example.json
```

The example intentionally reports blockers and exits 2. Keep actual metadata under ignored `data/raw/` or elsewhere outside Git. Do not commit report text, telemetry or private identifiers.

## Selection and evaluation sequence

1. Obtain permitted Volve DDR and WITSML inventory. Count physical-well/wellbore calendar overlap and review time/depth joins.
2. Extract report events and separately adjudicate onset bounds and contiguous event-free coverage. Exclude events with only unbounded timing from temporal prediction labels.
3. Freeze one hazard and horizon based on *measured* qualifying coverage; mud loss remains provisional. Use physical-well grouping across sidetracks and chronology-safe feature cutoffs.
4. If independently adequate, compare a simple supervised baseline with a normal-only anomaly baseline. Normal-only training still needs independently reviewed positive incidents for evaluation and a validation set for threshold selection.
5. Report event-level recall, warning lead time, false-alert rate over reviewed drilling exposure, well counts and uncertainty. Never cite the published autoencoder's internally inconsistent headline metrics as an NWIS result. If data is insufficient, publish the coverage table and stop before fitting.

The existing depth-horizon `mud-loss-windows-v1` validator remains a separate provisional contract. It must not be passed off as this temporal experiment or combined with its labels without an explicit, reviewed time-depth mapping.
