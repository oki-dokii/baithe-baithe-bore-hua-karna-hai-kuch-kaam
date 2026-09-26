# Phase 6 — demonstration readiness, partial rehearsal

Recorded 2026-09-27. This is a software rehearsal and gap register, not a claim of SIH field readiness or model accuracy. The local database already existed; this run did **not** perform a fresh empty-volume Compose setup. No private OIL data were available.

| Gate | Evidence from this run | State |
|---|---|---|
| Backend static and unit | `backend/.venv/bin/ruff check backend/nwis backend/migrations backend/tests`: pass. `backend/.venv/bin/pytest -q backend/tests`: 35 passed, 7 integration tests skipped when integration flag absent. | Pass for checked code |
| Frontend build | `npm run build`: TypeScript and Vite production build passed. | Pass for build |
| End-to-end synthetic paths | With local PostgreSQL and `NWIS_INTEGRATION=1`, backend integration files for ingestion, spatial intelligence, operations replay and prediction readiness: 7 passed. Includes synthetic review/permission, correlation/citation, alert lifecycle/idempotency/staleness and unavailable-score behavior. | Pass for these synthetic checks |
| Scanned public-report trial | [NOD 25/10-2 R](../phase-2/real-source-qualification.md) 58-page OCR staged two cited drafts. Depth mismatch, attribution/rights and human approval remain open. | Partial; not approved operational evidence |
| Public ML source | [FORGE audit](../phase-5/dataset-candidates.md) found telemetry/report candidates, no qualified 100 m mud-loss labels or current feature-schema coverage. | Open |
| Fresh-install rehearsal | A fresh empty database, image rebuild and migration from scratch were **not** exercised in this run. Earlier Phase 1 validation is recorded [separately](../phase-1/README.md). | Open for final demonstration |
| Retrieval evaluation | The 15-question real-source relevance/abstention set and recall@5 result are not yet produced. Current retrieval is filtered full-text, not embeddings. | Open |
| Alert field evaluation | No real labeled replay case count, lead-time distribution or false-alert denominator. Synthetic one-episode behavior is tested only. | Open |
| eRTMAC and field connectivity | No OIL interface contract, credentials or live stream. Fixed replay works; persistent disconnected field operation is not verified. | Open |
| Pitch and SIH metadata | No evidence-backed field ROI or official SIH problem ID confirmed. | Open |

## Rehearsal route with current prototype

Use [local setup](../phase-1/README.md) and [golden demo script](../phase-0/05-demo-and-evaluation.md). Enter the viewer/engineer/reviewer credentials from the local ignored `.env`, then load the synthetic fixture. Show the map, compare `SYN-A` with `SYN-B`, review the draft, start a new replay and step through 2029/2030/2031/2141 m. Demonstrate the cited historical alert and explicitly show `risk_score: null` with `model_not_available`. Treat the scenario as **SIMULATED** on every screen and in narration.

The next honest demo gate is a fresh-install run plus recorded screenshots/API results, a fixed retrieval question set, and a reviewed public-report case. ML accuracy and OIL integration require external data/access; do not substitute synthetic checks for either.
