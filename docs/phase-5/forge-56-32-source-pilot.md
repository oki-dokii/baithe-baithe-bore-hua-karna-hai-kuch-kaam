# FORGE 56-32 source-specific telemetry pilot

The [official GDR release](https://gdr.openei.org/submissions/1295) provides
the original 10-second Pason CSV, a standardized companion with a units row,
DDRs and mud logs. The offline mapper `nwis.forge_56_32` accepts **only** the
original 56-32 10-second CSV header. It preserves the exact source-file hash,
raw values and line IDs, maps six channels to the historical sample contract,
and screens one explicitly selected interval. It neither downloads data nor
creates labels. Raw data and mapped batches belong under ignored `data/raw/`.

Run:

```sh
cd backend
.venv/bin/python -m nwis.forge_56_32 \
  --csv ../data/raw/forge-56-32-10s-original.csv \
  --config ../data/raw/forge-56-32-mapping.json \
  --out ../data/raw/forge-56-32-selected-batch.json
```

The config must satisfy `Forge56Config` and supply existing dataset, wellbore
and depth-reference UUIDs; an IANA source timezone; local selection bounds;
the MD datum and evidence for interpreting `Hole Depth` as MD; a documented
observation-to-availability delay; a single pinned timezone-aware `receipt_at`
for repeatable re-import; permission evidence; and the six exact source units.
The config schema is `forge-56-32-raw-10s-v2`. The
[standardized companion](https://gdr.openei.org/files/1295/56-32%2010sec%20data%2027029986_standard.csv)
has a second header row showing feet, klbf, rpm, kft-lbf, gpm and ft/h. That
companion is **supporting metadata, not a reviewed guarantee** that every
raw field and datum is mapped correctly. The source's `Memos` column is
retained as raw evidence only, never auto-labeled. A 56-32 slice is geothermal
analogue data, not OIL field validation.

The output is created only when the drilling-ahead screen passes. Screen v3
requires at least half the slice to be active forward-drilling candidates.
Pass means
`screen_passed_needs_review`, not `qualified`; the batch can then be staged
using `nwis.drilling_parameters` after reviewing source identity and mapping.
The current schema admits one selected continuous interval per source-file
checksum. Multi-interval imports or correction of rejected mapping evidence
need a versioned source-selection model, not a silent change to this pilot.
The selected interval and receipt time must be frozen before first staging;
labels and train/test splits remain separate review steps.

## Actual file diagnostic, 2026-09-28

The original [56-32 10-second file](https://gdr.openei.org/files/1295/56-32%2010sec%20data%2027029986.csv)
was downloaded locally (24,415,711 bytes, SHA-256
`372fe53491f0a0ad704faeea4ed8bec0bdf8de1c946a70810d4d1140a5060a48`)
and kept out of Git. A **provisional, read-only** screen of CSV wall-clock
`2021-02-13 13:00:00–14:00:00` found 360 records, 336 heuristic active rows,
13.11 m net `Hole Depth` gain and 335 increasing-depth steps. Screen v3
returned `screen_passed_needs_review` with no screening blockers. This shows
that this particular slice is not the flat-ROP completion/workover pattern;
it does **not** validate timezone (`America/Denver` was only a screening
hypothesis), datum, near-zero availability lag, rig-state classification,
mud density, event labels or suitability for the 100 m mud-loss task. No
database sample or real training manifest was created from this diagnostic.

## Review-only WITSML messages

`nwis.witsml_messages` parses a local WITSML 1.4.1.1 `messages` XML export
and writes a checksum-pinned JSON file with source well/wellbore UIDs,
message time, optional MD/unit, text and keyword leads. For example:

```sh
cd backend
.venv/bin/python -m nwis.witsml_messages ../data/raw/messages.xml \
  --out ../data/raw/message-leads.json
```

The [Energistics Message schema](https://energistics.org/sites/default/files/schema/WITSML_v1.4.1.1_Data_Schema_with_Raster_v1.0/witsml_v1.4.1.1_data/doc/schema/grp_message.html)
defines `dTim`, optional MD and `messageText`. This parser handles the
`messages` object, **not** arbitrary free-text WITSML log channels. A keyword
hit is a lead even when negated (for example, “no mud loss”); a message time
is not proof of event onset. No real Volve message file has been tested here.
