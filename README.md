# Nearby Wells Intelligence System (NWIS)

NWIS is a proposed decision-support platform for Oil India Limited's SIH problem statement. It connects historical drilling reports, nearby wells, formation correlation, and proactive hazard alerts alongside eRTMAC.

**Status: Phase 1 foundation complete.** The repository contains a runnable service skeleton, database migration, synthetic fixture loader and status/well browser. Historical report ingestion, correlation, alerting and ML remain future phases.

Repository: https://github.com/oki-dokii/baithe-baithe-bore-hua-karna-hai-kuch-kaam

## Specification

Read these in order:

1. [Scope and acceptance criteria](docs/phase-0/01-scope-and-acceptance.md)
2. [Architecture and operating decisions](docs/phase-0/02-architecture.md)
3. [Data model and normalization contracts](docs/phase-0/03-data-contracts.md)
4. [API and user experience contracts](docs/phase-0/04-api-and-ux.md)
5. [Golden demo and evaluation plan](docs/phase-0/05-demo-and-evaluation.md)
6. [Dataset register and unresolved assumptions](docs/phase-0/06-data-and-assumptions.md)
7. [Phased implementation backlog](docs/phase-0/07-backlog.md)

[Phase 0 decisions and completion record](docs/phase-0/README.md) explains changes from the six source drafts. The [machine-readable demo fixture](specs/fixtures/golden-demo.json) fixes the expected correlation and alert behavior. It contains fictional wells and invented reports, explicitly labeled synthetic.

[Phase 1 local setup and validation](docs/phase-1/README.md) covers Docker Compose, access tokens, migration and fixture loading.

## Intended implementation

Python/FastAPI; PostgreSQL with PostGIS and pgvector; React/TypeScript; Leaflet; Docker Compose. Dependency versions will be pinned and checked together in Phase 1. Operational history and source citations are the core product. Deterministic historical matching generates alerts; optional ML adds a separately labeled score.

Current and planned directories:

```text
backend/          API, migration, fixture loader, worker shell
database/         PostgreSQL image with spatial/vector extensions
frontend/         status and nearby-well browser
data_pipeline/    later source adapters and normalization
ml/               later evaluation and model cards
config/           later versioned defaults; environment overrides
tests/            backend and integration checks
docs/             specifications and decisions
specs/fixtures/   small synthetic contract fixtures
```

## Repository workflow

The repository was initialized on `main` with the Phase 0 specification. Subsequent work uses `codex/<phase-or-feature>` branches and pull requests. Each implementation PR references acceptance IDs and records verification. Update affected specifications in the same PR when behavior changes.

Commit application code, migrations, documentation, and small synthetic fixtures. Keep credentials, raw third-party datasets, generated OCR text, uploaded reports, model binaries, and local databases out of Git. Data licensing and redistribution are assessed per source; no software license is selected by this baseline.

The prototype uses replayed telemetry labeled **SIMULATED**. It does not control drilling equipment. Synthetic examples establish behavior, not predictive accuracy or expected field performance.
