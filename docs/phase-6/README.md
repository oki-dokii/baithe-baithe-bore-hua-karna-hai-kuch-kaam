# Phase 6 — demonstration readiness, partial rehearsal

Recorded 2026-09-27. This is a software rehearsal and gap register, not a claim of SIH field readiness or model accuracy. The local database already existed; this run did **not** perform a fresh empty-volume Compose setup. No private OIL data were available.

| Gate | Evidence from this run | State |
|---|---|---|
| Backend static and unit | `backend/.venv/bin/ruff check backend/nwis backend/migrations backend/tests`: pass. `backend/.venv/bin/pytest -q backend/tests`: 40 passed, 7 integration tests skipped when integration flag absent. | Pass for checked code |
| Frontend build | `npm run build`: TypeScript and Vite production build passed. | Pass for build |
| End-to-end synthetic paths | With local PostgreSQL and `NWIS_INTEGRATION=1`, backend integration files for ingestion, spatial intelligence, operations replay and prediction readiness: 7 passed. Includes synthetic review/permission, correlation/citation, alert lifecycle/idempotency/staleness and unavailable-score behavior. | Pass for these synthetic checks |
| Scanned public-report trial | [NOD 25/10-2 R](../phase-2/real-source-qualification.md) 58-page OCR staged two cited drafts. Depth mismatch, attribution/rights and human approval remain open. | Partial; not approved operational evidence |
| Public ML source | [FORGE audit](../phase-5/dataset-candidates.md) found telemetry/report candidates, no qualified 100 m mud-loss labels or current feature-schema coverage. | Open |
| Fresh-install rehearsal | Earlier Phase 1 validation is recorded [separately](../phase-1/README.md). CI now runs a synthetic end-to-end rehearsal on its newly built Compose stack and rejects a nonempty database. A local empty-volume UI rehearsal and captured evidence are still pending. | Automated gate added; local visual gate open |
| Retrieval evaluation | A read-only fixed-question evaluator now scores approved passage recall@5 and abstentions. A 15-question **synthetic** API regression passes; the reviewed real-source set and its result do not exist yet. Current retrieval is filtered full-text, not embeddings. | Tooling and synthetic check pass; real-source gate open |
| Alert field evaluation | No real labeled replay case count, lead-time distribution or false-alert denominator. Synthetic one-episode behavior is tested only. | Open |
| eRTMAC and field connectivity | No OIL interface contract, credentials or live stream. Fixed replay works; persistent disconnected field operation is not verified. | Open |
| Pitch and SIH metadata | No evidence-backed field ROI or official SIH problem ID confirmed. | Open |

## Rehearsal route with current prototype

Use [local setup](../phase-1/README.md) and [golden demo script](../phase-0/05-demo-and-evaluation.md). Enter the viewer/engineer/reviewer credentials from the local ignored `.env`, then load the synthetic fixture. Show the map, compare `SYN-A` with `SYN-B`, review the draft, start a new replay and step through 2029/2030/2031/2141 m. Demonstrate the cited historical alert and explicitly show `risk_score: null` with `model_not_available`. Treat the scenario as **SIMULATED** on every screen and in narration.

The next honest demo gate is a fresh-install run plus recorded screenshots/API results, a fixed retrieval question set, and a reviewed public-report case. ML accuracy and OIL integration require external data/access; do not substitute synthetic checks for either.

## Automated clean-database rehearsal

The CI integration job starts Compose on a fresh runner, applies migrations, then runs `python -m nwis.demo_rehearsal` **before** the older integration smoke. The script refuses production or remote-extraction configuration and any pre-existing dataset. It uses the owned `phase3-review-report.txt` to test fixture loading and repeatability, map radius, upload/extraction, reviewer approval, depth mapping, exact citation, filtered retrieval and no-support abstention. A new paused replay steps through 2029/2030/2030/2031/2141 m, checking the alert boundary, one cited episode and `risk_score: null`. Output is a small text-free JSON check summary; it does not print tokens or report passages.

The CI check is a software demonstration with synthetic data, not a reviewed real-source extraction benchmark, an ML model, or eRTMAC connectivity. A browser walkthrough, visual screenshots and load/performance evidence remain separate gates. The command refuses any nonempty database; do not run it on a production or mixed-use database.

## Fixed-question retrieval evaluation

From `backend`, with the local NWIS DB and viewer token configured, run:

```sh
.venv/bin/python -m nwis.retrieval_eval /path/to/reviewed-questions.json
```

The manifest is a JSON object with `schema_version: "retrieval-questions-v1"`, `kind` (`synthetic`, `public` or `private`), `dataset_id`, `source_reference`, `review_reference`, and `questions`. Each question has a unique `id`, `question`, `expected_passage_ids` and optional `wellbore_id`, `formation_id`, `hazard`, `min_md_m`, `max_md_m`. An empty expected-passage list means a reviewed **no-support** case. Freeze the questions and source IDs before tuning search. Use the exact approved passage IDs, not guessed event IDs. Keep private manifests outside Git.

The evaluator calls only `POST /api/v1/query` with `limit: 5`; it performs no DB writes or external model calls. Its output omits question/source text and tokens. It reports source recall@5, correct/incorrect abstentions, unexpected results on negative questions, false abstentions and missing citation arrays. A zero-item positive answer counts as a false abstention. Exit 2 signals that the 15-question, mixed-positive/negative, real-source gate is unmet; this is **not** a model-performance threshold. Citation presence cannot prove that a quote entails a claim, and expected-source quality still needs human review. The synthetic regression is a software check, not a real-source retrieval result.
