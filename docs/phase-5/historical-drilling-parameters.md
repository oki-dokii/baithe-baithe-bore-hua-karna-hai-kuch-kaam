# Historical drilling-parameter staging

Migration `0010` creates `drilling_parameter_source` and append-only
`drilling_parameter_sample`. These tables are separate from live/replay
`telemetry_sample` and do not make a real ML dataset qualified by themselves.

The staging command is:

```sh
cd backend
.venv/bin/python -m nwis.drilling_parameters --source-file /path/to/permitted-export.csv --batch /path/to/mapped-batch.json
```

Run a read-only screen first with the same arguments plus `--screen-only`.
It prints JSON and exits with status 2 if any wellbore fails. The file checksum
is checked in both modes. Normal staging runs the same fail-closed screen
before writing; a correction upload is assessed together with all previously
staged revisions. A failed screen leaves the database unchanged. A source with
multiple wellbores is stopped if **any** wellbore fails; passing one interval
cannot conceal a completion/workover interval in another. This is a
wellbore-level gate (more conservative than grouping sidetracks by physical
well), not an operator-reviewed drilling-state classification.

`drilling-ahead-screen-v2` reports current-row count, span, good five-channel
completeness, rig-state and quality distributions, active rows (ROP >0.5 m/h
and WOB >2 kN), ROP/WOB ranges, measured-depth advancement, regressions,
duplicate timestamps and largest/median gaps. Its explicit initial stop rules
require at least 30 rows spanning 10 minutes, 80% good complete channels,
10 active forward-drilling rows, ROP range at least 1 m/h, WOB range at least
2 kN, 5 m of net MD advancement over at least five steps greater than 0.01 m, and no gap
over 30 minutes, duplicate observation time or >1 m forward-drilling MD
regression. These are **conservative screening heuristics, not validated
engineering thresholds**. A stop means inspect the source/period and mapping;
it must not be overridden by relabeling a completion interval as drilling.
Passing is only `screen_passed_needs_review`, never source qualification,
reviewed outcome coverage or model-training authorization.

The batch must conform to `HistoricalBatch` in
`backend/nwis/drilling_parameters.py`. Its `source_sha256` is verified against
the exact source file bytes. `source_reference` and `permission_reference` must
identify the export and its data-use authority. The caller supplies a
source-specific, reviewed unit mapping, explicit source timezone and measured-
depth datum; the command does not infer or approve them. `observed_at` means
sensor observation time, `available_at` earliest decision-time availability,
and `received_at` import receipt. All are timezone-aware and ordered.
Canonical channels use m/h, kN, rpm, kN·m, L/min, and kg/m³ respectively;
conversion from raw values belongs in a source-specific mapping with an
independently reviewed `mapping_version`. `raw_values` preserves the source
values and quality code. Revision 1 inserts a source record; later revisions
append corrections or a tombstone. Re-importing identical revisions is
idempotent. Changed revisions, source checksums or mappings are rejected.

Every source starts `staged`. A reviewer must verify the permission,
wellbore identity, source units, timestamp semantics, datum, rig-state and
quality mapping, then explicitly qualify the dataset, depth reference and
source. The database blocks qualification without the applicable dataset
provenance and the three source-review flags. Direct SQL qualification is
reserved for authorized review workflows; staging never performs it.
`eligible_anchors()` returns only current non-tombstoned revisions with five
complete canonical sensors, good quality, forward drilling, approved depth
reference, and qualified dataset/source. It does **not** assign train/test
splits, attach measured mud-density validity intervals, certify future
coverage, or infer losses from absent mentions. These still require the
reviewed source assertions of the [mud-loss adapter](mud-loss-adapter.md).

To attempt a real `audit()`, the remaining source-specific work is: import
permitted time-based logs and DDRs, reconcile physical well/wellbore IDs and
clock/depth datums, review correction history, create reviewed mud-density
intervals and 100 m outcome coverage, adjudicate event onset times/depths,
then build a well-grouped manifest. The NOD-2 R conflict remains blocked.
