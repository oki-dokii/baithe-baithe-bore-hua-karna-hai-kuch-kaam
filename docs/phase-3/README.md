# Phase 3 — Offset atlas and historical evidence

Core implementation: interactive nearby-well map, explainable analogue comparison, formation-relative mapping, approved case files and filtered full-text retrieval. **Phase 3 is not fully closed:** embedding-based semantic retrieval remains unimplemented. Phase 2's real-report and live-provider gates also remain open.

## Try the golden path

1. Open the local frontend (currently `http://127.0.0.1:13001`) and connect with the reviewer token.
2. In **Evidence room**, upload `specs/fixtures/phase3-review-report.txt` against **SYN-B**. It is fictional, owned test data, not an OIL report.
3. Inspect the source, record a rationale, and approve the mud-loss event. Do not change the source datum or formation to guess away warnings.
4. Open **Well intelligence**. Select **SYN-A**, its reviewed **SYN-F1** interval, and a **5 km** radius.
5. SYN-B and SYN-C are geographically nearby. SYN-B shares the reviewed formation; SYN-C does not. The approved SYN-B event at **1930–1940 m MD** maps to **2130–2140 m MD** in SYN-A.
6. Open the case and click its source citation. It identifies the exact document, page and text version. Reviewers can inspect page text; viewers receive only the approved supporting quote.
7. Search `mud losses` with source MD bounds **1900–2000 m**. Search `nonexistentunicorn` to check explicit abstention.

The original golden fixture event stays draft. Ingestion/review or explicitly labeled automated tests create separate approved records; loading a fixture does not grant operational approval.

## Mapping and similarity

Method `formation-relative-tvd-offset-v1` interpolates the source MD endpoints and formation top to TVD, measures the TVD offset below the source top, applies that offset to the target formation top, then inverts the target survey to MD. It does not copy raw MD across wells or silently substitute TVD for MD.

Requirements: approved event with no quality flags, reviewed source/target intervals sharing a canonical formation and dataset, reviewed depth references with known elevations, bounded event depths, and usable survey coverage. Folded/flat TVD trajectories are conservatively rejected as ambiguous. Missing surveys, extrapolation, out-of-formation mappings and ambiguous formation occurrences return null mapped depths with reasons. Latest stored survey versions and source/target interval versions accompany results; a dedicated survey adjudication workflow is still needed before field use. This is a prototype comparison heuristic, not a validated geological model.

Similarity is **not risk**: shared reviewed formation has weight 0.75; the smaller/larger MD-thickness ratio has weight 0.25. Available weights are renormalized if thickness is missing. Reservoir properties and lithology are explicitly listed as absent. Surface distance is displayed separately and only scopes candidate selection. A high score does not mean the well is safe or hazardous.

The Leaflet map uses WGS84 positions and an offline coordinate grid. It supports pan/zoom, a radius ring, markers, scale and an equivalent keyboard-accessible well list. No third-party tile requests disclose the viewed coordinates. Terrain/basemap tiles are not included. Database membership is computed with PostGIS geography distance, not browser pixel distance.

## Read APIs

- `GET /api/v1/intelligence/wellbores`: first 100 wellbores, with explicit dataset/type and coordinates.
- `GET /api/v1/wellbores/{id}/trajectory`: latest survey and formation intervals.
- `GET /api/v1/wellbores/{id}/analogues?target_interval_id=…&radius_km=…`: nearest 100 candidate wellbores, explained scores and up to 100 approved events each; truncation is explicit.
- `GET /api/v1/events/{id}`: approved case, mitigation/outcome/NPT and versioned citations. Draft/rejected cases return 404.
- `GET /api/v1/events/{id}/evidence/{passage_id}`: exact linked source representation, with role-based page visibility.
- `POST /api/v1/query`: dataset-scoped PostgreSQL full-text search over approved descriptions/quotes; optional wellbore, canonical formation, hazard and overlapping source-MD filters. Bound `limit` and `offset`; `next_offset` signals another page. This read-only route is not an idempotent mutation.

Search returns extractive evidence lists, never generated operating advice. It does not search unreviewed page text. Missing support produces `no_approved_supporting_evidence`, not a fabricated answer. **Semantic embeddings and natural-language synthesis are not present**; the response and UI identify full-text mode. Search's bounded offset pagination is an explicit prototype deviation from the original cursor contract.

## Verification and outstanding acceptance

The backend suite covers golden mapping, datum/axis/formation/dataset negatives, ambiguous survey inverse, extrapolation, radius membership and a near-boundary check, independent spherical-distance sanity check, score explanations, approved-only retrieval, filters, exact-page citations, role restrictions and rejected evidence exclusion. Run from `backend` using the Phase 2 environment:

```sh
uv run --frozen --extra dev ruff check nwis migrations tests
uv run --frozen --extra dev pytest -q
NWIS_INTEGRATION=1 uv run --frozen --extra dev pytest -q
```

`frontend/intelligence-smoke.mjs` tests the browser flow with a clearly labeled fictional uploaded/approved report and captures desktop/mobile screenshots in ignored `frontend/artifacts/`. Its Playwright environment variables match the Phase 2 smoke script. Test records remain labeled synthetic; do not use a production database. CI includes the new database integration checks and fresh container build.

MAP-01 and COR-01/02 have prototype regression coverage. RET-01 has extractive cited results and abstention, not generated answers. RET-02 structured filtering is implemented; its semantic retrieval portion remains open. Maps require an existing reviewed target interval in this screen; the Phase 1 well directory remains available for raw radius inspection. No saved mapping snapshots, live alerts, trained risk model, approved private-data authorization scheme, retrieval-scale benchmark or real-geology validation is claimed. These are not production operational recommendations.
