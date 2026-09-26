# Implementation backlog

Phases 0 and 1 are complete. Phase 2 ingestion/review is implemented with public-source qualification and live-provider validation open; see its [implementation record](../phase-2/README.md). Phase 3 core well intelligence is implemented with semantic retrieval still open. Phase 4 core fixed replay/alerts is implemented with streaming and persistent offline recovery open; see its [record](../phase-4/README.md). Phase 5 has started with qualification tooling and model-readiness UI; training and predictive evaluation remain blocked on suitable data ([record](../phase-5/README.md)). Phase 6 remains unstarted. Build one complete mud-loss path before expanding hazard scenarios.

| Phase | Deliverables in dependency order | Exit check |
|---|---|---|
| 0 — Specification | Scope; architecture decisions; logical schema; API/UI contracts; synthetic fixture; data register | These documents and fixture are internally checked and committed |
| 1 — Foundation (complete) | Pin dependencies; Compose with database/API/worker/frontend; extension-enabled image; physical migrations; typed API/OpenAPI; config validation; local identity/roles; fixture loader | Fresh setup works; migrations and seed load are repeatable; DB constraints reject malformed fixtures; status reports SIMULATED/no model |
| 2 — Evidence ingestion | Storage/upload jobs; text/OCR adapters; strict extraction; normalization; typed evidence joins; review UI/audit; real-source qualification | ING-01/02/03 and review permissions; scanned/text evidence survives to a source page; report real-source gate status explicitly |
| 3 — Well intelligence | Radius search; wells/map view; formation/survey mapping; analog scoring; case file; filtered and semantic retrieval | MAP-01, COR-01/02, RET-01/02 pass on golden and negative fixtures |
| 4 — Operations loop | Replay sessions; deterministic alerts; transactional dedup; lifecycle; dashboard; feedback; minimal field view | ALR-01/02/03, UX-01/02, FBK-01 pass across full replay and reconnect; no model required |
| 5 — Predictive validation | Audit data/labels; select one hazard/horizon; feature pipeline; grouped split; baseline/model evaluation; calibration if supported; model card/UI | ML-01/02 with disclosed limits; otherwise mark predictive capability incomplete |
| 6 — Demonstration | Fresh-setup rehearsal; public-report extraction test; performance/evaluation records; offline replay backup; evidence-driven pitch | All applicable acceptance IDs have pass/fail evidence; missing SIH outcomes are explicit |

## Phase 1 work items

| ID | Work | Dependencies | Verification |
|---|---|---|---|
| FND-01 | Scaffold backend/frontend and lock dependency versions | Phase 0 | Install/build/lint/type checks; documented runtime versions |
| FND-02 | Compose DB with PostGIS/pgvector plus API/worker/frontend | FND-01 | Extensions available; readiness reflects DB availability |
| FND-03 | Physical migrations for core wells, references, documents, events, evidence, review, sessions and alerts | FND-02 | Empty-db migration, FK/check constraints and repeat setup |
| FND-04 | Config schema, structured errors, request IDs, identity/role enforcement | FND-01 | Invalid config rejected; forbidden mutation rejected |
| FND-05 | Synthetic loader from golden fixture | FND-03 | Stable ID translation, repeat loading without duplicates, data-kind labels |
| FND-06 | App shell and `/api/v1/status`; OpenAPI contracts | FND-02/04 | Browser reaches shell; statuses report actual capability |
| FND-07 | Minimal CI and contributor setup guide | FND-01–06 | Fresh environment executes meaningful checks without private credentials |

## Working agreements

- Keep implementation changes on feature branches after this initial main baseline.
- Each PR references acceptance IDs, explains observable behavior, and lists relevant verification.
- Change documents and fixtures with behavior; record deviations and their reason.
- Add credentials only through local environment configuration; commit an example with placeholders when needed.
- Do not commit raw reports/datasets, generated binaries or private logs. Small owned synthetic fixtures are allowed.
- No production, predictive-accuracy, avoided-NPT or cost-saving claim without supporting evaluation.

Phase 3 core map, comparison, case file and filtered full-text search are implemented; see the [Phase 3 record](../phase-3/README.md). Semantic retrieval remains open, as do Phase 2's real-source/provider gates. Do not present synthetic test coverage as real-report validation or full-text search as semantic retrieval.
