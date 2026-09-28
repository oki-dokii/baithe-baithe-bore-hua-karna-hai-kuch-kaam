# Phase 6 — demonstration readiness, partial rehearsal

2026-09-28 update: [current-code rehearsal](rehearsal-2026-09-28.md) passed on a fresh local database; a separate fresh-image Compose rerun was blocked by host disk capacity. The [gate-led pitch](pitch-gated-evidence-2026-09-28.md) distinguishes authentic staged reports from the owned synthetic alert demo. The [NOD-511 triage decision](../phase-2/nod-511-disposition-2026-09-28.md) retains the conflicting depths and blocks onset approval. A [claim-level analyst pre-review](claim-review-packet-2026-09-28.md) identifies specific candidate gaps; a separate [two-report holdout](heldout-review-protocol-2026-09-28.md) is source-sealed but not yet labeled or scored.

Current-code update: [migration-0017 rehearsal](rehearsal-0017-2026-09-28.md) passed on a new empty local database, including synthetic-only bottom-hole separation and the cited offset brief. [Terminal-position candidate discovery and telemetry dossier](terminal-search-and-telemetry-dossier-2026-09-28.md) were subsequently added and tested on a separate newly migrated database; this does not supersede the historical rehearsal record. A separate fresh-image retry remains blocked by the Colima VM disk limit; A4 print pagination is not yet verified.

Recorded 2026-09-27. This is a software rehearsal and gap register, not a claim of SIH field readiness or model accuracy. The local database already existed; this run did **not** perform a fresh empty-volume Compose setup. No private OIL data were available.

| Gate | Evidence from this run | State |
|---|---|---|
| Backend static and unit | `backend/.venv/bin/ruff check backend/nwis backend/migrations backend/tests`: pass. `backend/.venv/bin/pytest -q backend/tests`: 40 passed, 7 integration tests skipped when integration flag absent. | Pass for checked code |
| Frontend build | `npm run build`: TypeScript and Vite production build passed. | Pass for build |
| End-to-end synthetic paths | With local PostgreSQL and `NWIS_INTEGRATION=1`, backend integration files for ingestion, spatial intelligence, operations replay and prediction readiness: 7 passed. Includes synthetic review/permission, correlation/citation, alert lifecycle/idempotency/staleness and unavailable-score behavior. | Pass for these synthetic checks |
| Scanned public-report trial | [NOD 25/10-2 R](../phase-2/real-source-qualification.md) 58-page OCR staged two cited drafts. Depth mismatch, attribution/rights and human approval remain open. | Partial; not approved operational evidence |
| Public ML source | [FORGE audit](../phase-5/dataset-candidates.md) found telemetry/report candidates, no qualified 100 m mud-loss labels or current feature-schema coverage. | Open |
| Fresh-install rehearsal | Earlier Phase 1 validation is recorded [separately](../phase-1/README.md). CI runs a synthetic end-to-end rehearsal on a new Compose stack. A [separate empty local database and browser preview](semantic-preview-rehearsal-2026-09-27.md) now passed without replacing the existing DB. It reused the old database container, not a new volume/image. | Clean-database software and local browser gates pass; independent deployment gate open |
| Retrieval evaluation | A read-only evaluator scores approved passage recall@5 and abstentions; a 15-question **synthetic** API regression passes. The [three pinned public PDFs](public-benchmark-ingestion-2026-09-27.md) are ingested in a separate, unreviewed database (262 pages, 54 v1 drafts). The 18 questions are [scoped](../../specs/evaluation/public-retrieval-scope-v1.json) into 6 event-retrieval, 10 report-fact QA and 2 conflict-blocked cases. Two extraction misses now have v2 development candidates, but no draft was replaced or approved. These sources informed tuning, so an independent held-out score needs new data. [Local semantic candidate retrieval](../phase-3/semantic-search.md) is opt-in; its cutoff is unvalidated. | Review preview and scope ready; human review, held-out benchmark and scoring open |
| Alert field evaluation | No real labeled replay case count, lead-time distribution or false-alert denominator. Synthetic one-episode behavior is tested only. | Open |
| eRTMAC and field connectivity | No OIL interface contract, credentials or live stream. Fixed replay works; persistent disconnected field operation is not verified. | Open |
| Pitch and SIH metadata | No evidence-backed field ROI or official SIH problem ID confirmed. | Open |

## Rehearsal route with current prototype

Use [local setup](../phase-1/README.md) and [golden demo script](../phase-0/05-demo-and-evaluation.md). Enter the viewer/engineer/reviewer credentials from the local ignored `.env`, then load the synthetic fixture. Show the map, compare `SYN-A` with `SYN-B`, review the draft, start a new replay and step through 2029/2030/2031/2141 m. Demonstrate the cited historical alert and explicitly show `risk_score: null` with `model_not_available`. Treat the scenario as **SIMULATED** on every screen and in narration.

The initial [local visual rehearsal](visual-rehearsal-2026-09-27.md) passed intelligence and operations but found a stale WebSocket process. The [follow-up clean-database browser rehearsal](semantic-preview-rehearsal-2026-09-27.md) passed semantic, operations and fresh-process WebSocket/fallback checks with one approved synthetic source. Operations now has a 6-second silent-socket watchdog and the WebSocket smoke script checks that case, but this latest browser check has not yet been rerun. The [public report reference](public-report-benchmark.md) is page-verified but not domain-approved or API-scored. ML accuracy and OIL integration require external data/access; do not substitute synthetic checks for either.

## Automated clean-database rehearsal

The CI integration job starts Compose on a fresh runner, applies migrations, then runs `python -m nwis.demo_rehearsal` **before** the older integration smoke. The script refuses production or remote-extraction configuration and any pre-existing dataset. It uses the owned `phase3-review-report.txt` to test fixture loading and repeatability, map radius, upload/extraction, reviewer approval, depth mapping, exact citation, filtered retrieval and no-support abstention. A new paused replay steps through 2029/2030/2030/2031/2141 m, checking the alert boundary, one cited episode and `risk_score: null`. Output is a small text-free JSON check summary; it does not print tokens or report passages.

The CI check is a software demonstration with synthetic data, not a reviewed real-source extraction benchmark, an ML model, or eRTMAC connectivity. A browser walkthrough, visual screenshots and load/performance evidence remain separate gates. The command refuses any nonempty database; do not run it on a production or mixed-use database.

## Fixed-question retrieval evaluation

From `backend`, with the local NWIS DB and viewer token configured, run:

```sh
.venv/bin/python -m nwis.retrieval_eval /path/to/reviewed-questions.json
```

The manifest is a JSON object with `schema_version: "retrieval-questions-v1"`, `kind` (`synthetic`, `public` or `private`), `dataset_id`, `source_reference`, `review_reference`, and `questions`. Each question has a unique `id`, `question`, `expected_passage_ids` and optional `wellbore_id`, `formation_id`, `hazard`, `min_md_m`, `max_md_m`. An empty expected-passage list means a reviewed **no-support** case. Freeze the questions and source IDs before tuning search. Use the exact approved passage IDs, not guessed event IDs. Keep private manifests outside Git.

The evaluator calls only `POST /api/v1/query` with `limit: 5`; it performs no DB writes or external model calls. Add manifest `mode: "semantic"` to evaluate an already prepared local semantic index, or omit it for full-text. Its output omits question/source text and tokens. It reports source recall@5, correct/incorrect abstentions, unexpected results on negative questions, false abstentions and missing citation arrays. A zero-item positive answer counts as a false abstention. Exit 2 signals that the 15-question, mixed-positive/negative, real-source gate is unmet; this is **not** a model-performance threshold. Citation presence cannot prove that a quote entails a claim, and expected-source quality still needs human review. The synthetic regression is a software check, not a real-source retrieval result.
