# Volve overlap and feed-contract experiments

These are local qualification aids, not a trained model, WITSML implementation, or live eRTMAC validation. They perform no network calls or database writes. The examples under `specs/fixtures/` are **owned synthetic data** and must never be described as Volve or OIL observations.

## 1. Volve file-overlap audit

Equinor's [Volve release](https://www.equinor.com/energy/volve-data-sharing) is a petroleum-domain candidate. Its [inventory description](https://cdn.equinor.com/files/h61q9gi9/global/de6532f6134b9a953f6c41bac47a0c055a3712d3.pdf?equinor-hrs-terms-and-conditions-for-licence-to-data-volve.pdf=) lists DDRs in HTML, PDF and WITSML XML, but real-time WITSML only for newer wells. The public description does not establish per-wellbore DDR/telemetry overlap, mud-loss labels or negative drilling coverage. Access to the actual files through Databricks Marketplace has **not** been obtained in this experiment, so there is no measured real Volve overlap count.

Run the owned example from the repository root:

```sh
backend/.venv/bin/python -m nwis.volve_overlap specs/fixtures/volve-overlap-example.json
```

To audit permitted Volve metadata, copy the example into an ignored local path such as `data/raw/volve/overlap.json`; replace every example identifier with verified physical-well and wellbore identities and exact local file references. Set `source_kind` to `public_metadata`, initially leave review fields false/zero, then have a domain reviewer assess the time/depth join and onset/no-event coverage. Do not put report text, telemetry or restricted paths in Git. The output counts file overlap, reviewed joins, and wellbores asserting both positive and negative coverage, but does **not** open or authenticate source files. It always says `training_authorized: false`. It does not replace the stricter prepared-window validator in [Phase 5](README.md).

## 2. Transport-neutral feed-change harness

Run the owned replay:

```sh
backend/.venv/bin/python -m nwis.feed_contract specs/fixtures/feed-contract-replay.json
```

It has one stream and one channel with an initial reading, a later reading, a correction to the older reading, a duplicate delivery, and a delayed old reading. The harness requires contiguous **locally synthesized** cursors per stream, monotone record revisions, idempotent duplicate payloads, timezone-aware timestamps, finite values and explicit units. It refuses gaps, cursor collisions, unknown deletes and unversioned corrections. The latest view uses observation time rather than arrival order; bad quality and stale readings cannot be presented as current.

This is **not** an ETP cursor or WITSML message format. Energistics [ETP 1.2](https://docs.energistics.org/EO_Resources/ETP_Specification_v1.2_Doc_v1.1.pdf) describes channel range retrieval, subscriptions, replacements/truncations and outage recovery using store timestamps/change retention. A real adapter must discover OIL's actual WITSML/API version and map those source semantics into this contract, including revisions, deletes, auth, time/depth-index metadata and reconnect backfill. An adapter-generated contiguous cursor can be committed only after a source change is durably stored; a gap requires re-fetch, not skipping ahead. No XML parsing, ETP session, real source QC or OIL link is exercised here.

## Exit checks for the next step

1. Obtain a permitted Volve inventory export. Verify files and identities, then report actual DDR/telemetry overlap and domain-reviewed onset/negative coverage. If no independent positive and negative well groups exist, stop before training.
2. Obtain OIL's current endpoint/protocol version, channel metadata, authentication/permission scope and a de-identified sample including a disconnect and corrected reading. Select a version-specific parser/transport only after that. Test it against this contract and add a protocol-level conformance suite.
3. Preserve the existing synthetic replay and `risk_score: null` until a separately qualified model passes the [prediction gates](README.md). The feed harness alone cannot authorize live alerts or model inference.
