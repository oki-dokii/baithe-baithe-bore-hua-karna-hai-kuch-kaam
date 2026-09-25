# API and user experience contracts

## Common behavior

Prefix REST with `/api/v1`. Persistent IDs are UUIDs. JSON uses snake_case and unit-bearing field names (`md_m`, `radius_km`, `duration_h`). Timestamps are UTC RFC3339. Use cursor pagination (`items`, `next_cursor`) with default limit 25 and maximum 100. Missing values are null with a reason where decision-relevant.

Errors: `{ "error": { "code": "depth_reference_missing", "message": "...", "details": {} }, "request_id": "..." }`. Use 400 for malformed requests, 401/403 for access, 404 for absent records, 409 for version/idempotency conflicts, 413 for excessive uploads, 422 for invalid field values, and 503 for unavailable dependencies. Retrieval with no evidence is a successful empty result, not an error. Bound initial radius to 0.1–100 km and uploads to PDF/text files <=25 MiB; make limits configurable.

Mutations accept `Idempotency-Key`; reuse with different content returns 409. Updates use `expected_version` to avoid silently overwriting concurrent actions. Server-derived actor identity is never trusted from a request body.

## Routes

| Route | Request / response behavior | Role |
|---|---|---|
| GET /status | component readiness, dataset kinds, replay/live mode, model availability, dependency degradation; no credentials | all authenticated |
| GET /wells | filters: dataset, basin, formation, status; paginated summary | viewer+ |
| GET /wells/nearby | active_wellbore_id, radius_km; distances and coordinate basis | viewer+ |
| GET /wells/{id} | identity, data kind, wellbores and source coverage | viewer+ |
| GET /wellbores/{id}/trajectory | survey stations with version, units and depth reference | viewer+ |
| GET /wellbores/{id}/events | hazard/formation/depth filters; approved operational events by default | viewer+ |
| GET /wellbores/{id}/analogues | target_interval_id, radius_km; component scores and missing-data reasons | viewer+ |
| GET /wellbores/{id}/correlation | target interval, candidate IDs; mapped intervals or unresolved reason | viewer+ |
| GET /events/{id} | case file, mitigations/outcomes, evidence and source versions | viewer+ |
| POST /query | question, active_wellbore_id, dataset_id, optional structured filters; answer, supported claims/citations, abstention reason | viewer+ |
| POST /documents | multipart file and dataset/wellbore metadata; 202 document_id/job_id | reviewer/admin |
| GET /documents/{id}/jobs | stage, progress if measurable, attempts, actionable failure | reviewer/admin |
| GET /documents/{id}/extraction | passages, draft facts, quality flags, version | reviewer/admin |
| POST /documents/{id}/review | expected_version, approve/reject/correct decisions and rationale | reviewer/admin |
| GET /documents/{id}/pages/{page} | access-controlled page/representation and optional highlighted span | viewer+ for approved evidence |
| POST /replay-sessions | scenario_id, speed; new session and initial sequence | engineer/admin |
| POST /replay-sessions/{id}/control | pause/resume/reset/speed; reset creates a new session | engineer/admin |
| GET /telemetry/current/{wellbore_id} | current sample, receipt time, stale flag, source mode | viewer+ |
| GET /risk/current/{wellbore_id} | per-hazard assessment or null + reason; model/version/horizon | viewer+ |
| GET /alerts | active wellbore/session/status/relevance filters | viewer+ |
| GET /alerts/{id} | trigger, evidence, mapping and optional model assessment | viewer+ |
| POST /alerts/{id}/actions | acknowledge/review/resolve/dismiss/reopen, expected_version, reason | engineer/admin |
| POST /alerts/{id}/feedback | action taken, observed outcome, uncertainty; adjudication separate | engineer/admin |

Static paths such as `/wells/nearby` must not be swallowed by dynamic ID routes. Document storage paths are not exposed as unrestricted filesystem URLs. Query scope includes dataset identity so a synthetic Assam demonstration does not retrieve unrelated Volve facts as though they describe the same field.

## WebSocket

`/ws/v1/telemetry/{wellbore_id}?session_id=...&after_sequence=...` uses authenticated session context. Envelope: `type`, `session_id`, `sequence`, `observed_at`, `received_at`, `source_mode`, `payload`. Types: `telemetry`, `alert_created`, `alert_updated`, `replay_state`, `heartbeat`, `error`.

Reconnect resumes after the last sequence. If replay retention cannot fulfill the cursor, send an explicit resync response and fetch the current snapshot. Deduplication is persisted server-side; refreshing a browser cannot create a new alert episode. A stale indicator reflects receipt freshness, not the historical timestamp of replayed source data.

## Screen contract

1. Operations dashboard: active wellbore and session, MD/TVD with reference, formation and mapping quality, SIMULATED label, last update time, map preview, lookahead interval, alert feed.
2. Wells/correlation: radius, dataset, formation and hazard filters; separate surface/interval distances; raw source depths and mapped active intervals; unresolved mapping explanations.
3. Alert/case file: why it fired, depth window, historical evidence, cited mitigation/outcome, lifecycle controls, separate optional model score and feedback form.
4. Ingestion/review: upload job, page preview, extracted fields, missing units/references, corrections and approval history.
5. Field view: compact single-column alerts and current state; maps/charts loaded only on request; timestamped cached data, explicit offline state and no false server acknowledgment.

Every screen needs loading, empty, failure, stale, unknown and permission-denied states. Use text/icons as well as color for severity, keyboard-accessible controls and readable mobile touch targets. Source clicks must reach the correct page, not only the document title. Display source-data kind alongside well/case identity.

## Future analytics contracts

NPT exposure is `historical_duration_h * assumed_rig_day_rate / 24`, displaying currency, source duration and assumed rate. Do not sum overlapping episodes or label the result proven savings. Aggregate evidence must disclose sample count and selection. Model performance, fishing distributions and advanced cost views are added in Phase 5 only when their data is qualified.
