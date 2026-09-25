# Phase 1: local foundation

The repository includes a runnable service skeleton and a verified local stack.

## Requirements

- Docker with Compose and a running container engine. On macOS with Colima: `colima start`.
- For host-side development: Python 3.12, uv 0.11.4, Node.js 22.17.1 and npm 10.9.2.

## First start

1. Copy `.env.example` to `.env` and replace all five secret placeholders with distinct long values. `.env` is ignored by Git. Never use the example text as a deployed credential.
2. Run `docker compose up --build -d`. The `migrate` service installs extensions and applies versioned schema changes before API and worker start.
3. Run `docker compose ps`; `migrate` should have exited successfully and the other services should be running.
4. At `http://localhost:3000` (or the configured `NWIS_WEB_PORT`), enter the viewer token from `.env`. The UI initially shows an empty dataset and precise capability status.
5. Load the fictional fixture once with the admin token:

   `curl -X POST -H "Authorization: Bearer $NWIS_ADMIN_TOKEN" http://localhost:${NWIS_API_PORT:-8000}/api/v1/admin/fixtures/golden`

   If `.env` was copied but not loaded into your shell, export `NWIS_ADMIN_TOKEN` locally first. Alternatively use `docker compose exec api python -m nwis.seed /app/specs/fixtures/golden-demo.json`. Repeat the command to verify idempotency (`repeated: true`).
6. Refresh the UI or call `GET /api/v1/wells` to see four synthetic wells. `GET /api/v1/wells/nearby?active_well_id=<UUID>&radius_km=5` should return SYN-B and SYN-C.

Interactive API docs are at `http://localhost:8000/docs` (or the configured API port). All `/api/v1` endpoints require a local bearer token. `/healthz` only reports process liveness.

## Host-side checks

```sh
cd backend
UV_CACHE_DIR=/private/tmp/nwis-uv-cache uv sync --frozen --extra dev --python 3.12
UV_CACHE_DIR=/private/tmp/nwis-uv-cache uv run --frozen --extra dev ruff check nwis migrations tests
UV_CACHE_DIR=/private/tmp/nwis-uv-cache uv run --frozen --extra dev pytest

cd ../frontend
npm ci
npm run build
```

Use `docker compose logs api worker migrate` for service failures. `docker compose down` stops services and retains the database volume. `docker compose down -v` removes local database contents and should only be used when you intend to discard them.

## Implementation status

Phase 1 includes schema, local roles, read APIs, PostGIS radius lookup, fixture loader and an honest capability shell. The worker is a heartbeat process; report ingestion, review actions, retrieval, replay and risk prediction are implemented in later phases. The synthetic report's event loads as `draft` and is excluded from operational alerting until a future reviewer approves it.

## Validation record

Verified locally on 2026-09-25 with Colima/Docker: the database, migration, API, worker and web images build; migrations apply to a fresh database; API/worker/web start; the web server returns HTTP 200; and the API health proxy returns a running response. The `nwis.smoke` check covers anonymous/viewer/admin access, PostGIS and pgvector, migration version, idempotent fixture loading, the exact nearby-well set, invalid radius rejection, draft review state, and a database depth constraint. Local account hashes are stored in the database and synchronized at startup. Backend Ruff checks and two unit tests pass; frontend `npm ci`, TypeScript and Vite production build pass. npm audit reports zero vulnerabilities for the locked frontend packages.

Local ports 8000 and 3000 were already occupied by unrelated services, so the ignored `.env` in this checkout uses API port 18080 and web port 13000. The Compose defaults remain 8000 and 3000 for other machines. GitHub Actions is configured for the same static and integration checks; its remote run is not asserted here.

This machine's Colima data disk is 5.9 GB and filled during a repeat image build. PostgreSQL recovered after disposable NWIS build layers were removed, and the additive account migration and smoke check then passed without discarding the database volume. Leave enough VM disk headroom for future image rebuilds; increasing Colima disk capacity is preferable before larger phases.
