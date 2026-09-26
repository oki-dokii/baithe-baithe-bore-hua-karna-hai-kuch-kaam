# Phase 4 — Synthetic operations loop (core)

Phases 2 and 3 were merged into `main` before this work. Their real-report/live-provider and semantic-search gates remain open.

## What is implemented

- Fixed, explicitly **SIMULATED** golden replay for SYN-A / SYN-F1: MD 2029, 2030, 2030, 2031, 2141 m. Creation starts paused. Engineer/admin controls support manual step, resume, pause and reset into a new session. Viewers/reviewers cannot control replay or mutate alerts.
- A dedicated `replay` Compose service advances due sessions independently of document ingestion. Session-row locks, sequence uniqueness, optimistic versions and idempotency receipts prevent duplicate steps. Reset stops the old session and retains its samples, alerts and history.
- A 100 m inclusive lookahead over reviewed, source-backed, successfully mapped offset incidents within 5 km. No new alert at 2029; one episode at 2030; repeat samples update its count rather than duplicate it. Episodes group by session, target formation, hazard and 50 m mapped-start band. Multiple citations are retained within an episode.
- Mapping/evidence snapshots preserve the source quote, document/page/text versions, raw and mapped MD, survey/interval versions and surface distance. New alerts exclude draft/rejected/quality-flagged/unresolved evidence. Changed event review/version, interval versions, survey versions, reference review and missing source joins produce review-required indications. Original snapshots are never deleted to hide a later change.
- Lifecycle is independent of relevance. NEW → ACKNOWLEDGED does not mean RESOLVED; explicit review, resolve, dismiss and reopen actions require a rationale, current version and authorized role. Moving past the interval changes relevance, not the human lifecycle decision.
- Engineer feedback separates action taken, observed outcome and rationale. `adjudicated_label` remains null; no incident observed is not automatically a false positive.
- Responsive editorial operations screen with sample receipt time, 15-second stale indication, worker readiness, replay controls, expandable evidence, action/feedback histories and a persistent no-model label. Disconnected cached data is not presented as fresh; actions require a server response. The map module loads only when its workspace is opened.

## Try it

Refresh `http://127.0.0.1:13001` and sign in with `NWIS_ENGINEER_TOKEN` from your local `.env`. Ensure a reviewed synthetic SYN-B incident exists using the [Phase 3 report and instructions](../phase-3/README.md).

1. In **Operations**, choose **New synthetic replay**.
2. Click **Next depth sample**. At 2029 m there should be no alert.
3. Click again. At 2030 m there should be one mud-loss episode with source evidence mapping to 2130–2140 m.
4. Enter a rationale and acknowledge it. It remains ACKNOWLEDGED, not resolved.
5. Step through repeated 2030 and 2031. The episode remains the same.
6. At 2141 m its relevance is passed. The lifecycle still reflects the human decision.
7. Reset into a new session, then use **Play replay**. Server-side playback completes the five samples. Reloading the page never advances samples.
8. Leave the receipt unchanged for over 15 seconds: the displayed telemetry becomes stale. Historical alerts remain visible; no GET or stale cached sample creates new alerts.

The local preview uses host API 18081, web 13001 and DB 15432. `python -m nwis.operations_worker` runs the dedicated worker from `backend` with the same environment. A normal fresh install uses `docker compose up --build -d --wait`, including the new replay service. Migration `0004_operations` adds replay version/progress metadata and alert action history; it is additive and retains previous records.

## APIs and tests

`POST /replay-sessions`, `GET /replay-sessions`, `GET /replay-sessions/{id}`, `POST /replay-sessions/{id}/control`, `POST /alerts/{id}/actions`, and `POST /alerts/{id}/feedback`. Mutations require `Idempotency-Key`; controls/actions also require `expected_version`. GET returns a full persisted snapshot, never advances replay, and can be used after reconnect. ML score is null with `model_not_available`.

From `backend`, with an initialized development DB and environment: `NWIS_INTEGRATION=1 uv run --frozen --extra dev pytest -q`. The new integration test checks concurrent duplicate step submission, trigger boundaries, one episode with multiple evidence links, role denials, stale versions, acknowledgment, relevance passage, reset isolation, feedback and changed-evidence visibility. Tests retain synthetic audit records.

`frontend/operations-smoke.mjs` uses Playwright and `NWIS_ENGINEER_TOKEN`; the remaining runtime variables match the Phase 2 browser script. It expects previously reviewed synthetic evidence and a running replay worker. It tests manual boundaries, deduplication, acknowledgment, reset, automatic playback and mobile overflow. Screenshots remain ignored under `frontend/artifacts/`.

## Explicit limits / acceptance status

This is the **core fixed-scenario prototype**, not a completed live operations platform. ALR-01/02 have golden regression coverage. ALR-03 covers stale receipts and common evidence invalidation but not an externally supplied telemetry protocol. UX-01/02 have responsive operations/evidence views, not full offline persistence. FBK-01 captures action/outcome/uncertainty, not a reviewer adjudication workflow.

- Polling snapshots every 1.5 seconds replace the planned WebSocket/cursor transport for now. They recover persisted current state, not an event-stream backlog. No push notifications are sent.
- Only the owned fixed golden scenario is supported. There is no live eRTMAC input, arbitrary-well replay editor, physical simulator, equipment control or trained probability model.
- No persistent offline storage or queued offline acknowledgment; losing connectivity disables mutations and labels cached state. A reload while offline cannot restore the prior in-memory snapshot.
- Evidence versions must be bumped when underlying surveys/intervals are revised. Unversioned direct database edits are outside the contract. A complete supersession/revocation UI and exhaustive concurrent metadata-mutation hardening remain future work.
- No data-scale latency or real-world risk-performance claim is made. Performance, authorization hardening, production identity, notification policy and private-data validation remain open.

Historical responses are cited observations, never instructions to repeat them. Resolving an alert in this prototype does not certify that drilling is safe.
