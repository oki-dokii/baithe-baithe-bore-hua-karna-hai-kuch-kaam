# Isolated public-report ingestion — 2026-09-27

Three locally retained NOD PDFs were checked against the frozen SHA-256 and page-count registry, then uploaded through the normal NWIS API and processed by the normal local-rules ingestion worker in a **separate** local database, `nwis_public_benchmark`. Raw PDFs, extracted text, page previews and this database remain local/ignored; none are committed. The existing `nwis_demo_clean` synthetic preview and main development database were not used for this ingestion.

The staging command `python -m nwis.public_benchmark_ingest prepare` refuses production, remote extraction, a non-loopback or differently named database, a different storage directory, and a page cap below 166. It also refuses a mixed dataset or any approved event. It creates three `benchmark_unlocated` wells with `(0,0)` schema-sentinel coordinates because verified surface locations were not supplied for all three sources. The map APIs hide these sentinels, and the review API rejects approvals while the dataset has `staged_unreviewed` status (verified locally with HTTP 409 and zero map-visible wells). **This database is for retrieval/extraction review only; do not use it for correlation or alerts.** The wellbore attribution for 35/7-1 S/T2 narrative also remains for reviewer confirmation.

| Source | Pages extracted | OCR pages | Unreviewed drafts | Status |
|---|---:|---:|---:|---|
| NOD-399 | 38/38 | 5 | 5 | needs_review |
| NOD-511 | 58/58 | 58 | 2 | needs_review; loss-depth conflict remains flagged |
| NOD-6599 | 166/166 | 1 | 47 | needs_review |

The read-only `nwis.public_passage_audit` found an extracted page for all 25 frozen reference items. Of the nine observed-event references, six had same-page, same-hazard drafts requiring claim-level review, two had **no matching draft** (`R005` equipment loss and `R020` positive flow/kick), and the NOD-511 loss item `R002` remained `disputed_depth_blocked` despite a same-page draft. The 16 hard-negative/action/context references are outside the current event-only search index. A same-page draft is **not** a correct extraction; the 47 drafts in NOD-6599 especially need false-positive review. There are zero approved drilling events and no real-report retrieval score, ML label or operational alert from this dataset.

## Repeatable local procedure

Provision a new local PostgreSQL database named exactly `nwis_public_benchmark` (never reuse `nwis` or `nwis_demo_clean`). From `backend`, set the usual local role tokens and DB password from the ignored root `.env`, plus:

```sh
export NWIS_DATABASE_URL="postgresql+psycopg://nwis:${NWIS_DB_PASSWORD}@127.0.0.1:${NWIS_DB_PORT:-5432}/nwis_public_benchmark"
export NWIS_STORAGE_ROOT="$PWD/storage/public-benchmark"
export NWIS_DOCUMENT_MAX_PAGES=200
export NWIS_EXTRACTION_PROVIDER=local_rules
.venv/bin/python -m nwis.initialize
.venv/bin/python -m nwis.public_benchmark_ingest prepare
.venv/bin/python -m nwis.public_benchmark_ingest process-one
```

Run `process-one` again for each remaining pending report; it is deliberately one job at a time so page coverage, OCR failures and available disk can be checked between reports. Run the read-only candidate audit after ingestion:

```sh
.venv/bin/python -m nwis.public_passage_audit --dataset-id 3bf95e06-3441-591e-a870-408525be726f
```

The current local run used about 83 MiB of ignored document storage; the host had about 1.9 GiB free afterward. The database itself is additional local state. The scripts do not delete or reset it. Before scoring, a reviewer must inspect the source pages and drafts, explicitly map claims to passage UUIDs, resolve attribution/rights, and split event retrieval from report-fact QA. The staging qualification status must stay approval-blocked until a separate accountable qualification decision; NOD-511's disputed depth must not be approved by this workflow.
