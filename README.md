# NWIS — Nearby Wells Intelligence System

> **SIH 2026 Prototype · Oil India Limited problem statement**
> Subsurface observatory connecting historical drilling experience, nearby-well analogues, formation correlation, and proactive hazard alerts alongside eRTMAC.

**Status:** Synthetic demo rehearsed; no trained risk model or live eRTMAC.
Ingestion/review, offset-well comparison, cited full-text and opt-in local semantic search support fixed synthetic replay, evidence-backed alerts, lifecycle actions and engineer feedback.

---

## Table of Contents

1. [What NWIS Does](#1-what-nwis-does)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Repository Layout](#4-repository-layout)
5. [Quick Start — Docker Compose](#5-quick-start--docker-compose)
6. [Access Tokens & Roles](#6-access-tokens--roles)
7. [Loading Demo Data](#7-loading-demo-data)
8. [Frontend Views](#8-frontend-views)
9. [API Reference](#9-api-reference)
10. [Data Model Overview](#10-data-model-overview)
11. [Alert System](#11-alert-system)
12. [Formation Correlation Algorithm](#12-formation-correlation-algorithm)
13. [Analog Ranking](#13-analog-ranking)
14. [Configuration Reference](#14-configuration-reference)
15. [Local Development (No Docker)](#15-local-development-no-docker)
16. [Running Tests](#16-running-tests)
17. [Smoke Tests](#17-smoke-tests)
18. [Acceptance Matrix](#18-acceptance-matrix)
19. [Phased Roadmap](#19-phased-roadmap)
20. [Important Caveats](#20-important-caveats)

---

## 1. What NWIS Does

An engineer drilling a new well faces hazards that have been encountered in nearby wells before — mud losses, stuck-pipe, kicks, well-control events. That experience is locked in PDFs, handwritten notebooks, and the memory of people who may no longer be on site. NWIS makes that institutional memory accessible, traceable, and proactive.

**Core capabilities:**

| Capability | Description |
|---|---|
| **Document ingestion** | Upload drilling reports (PDF or scanned) → text extraction / OCR → structured fact extraction → human review queue |
| **Evidence review** | Reviewers approve, correct, or reject extracted events; every change is versioned and auditable |
| **Nearby-well map** | Geodesic surface-distance radius search; Leaflet map with formation depth-track overlay |
| **Formation correlation** | Heuristic MD→TVD mapping of historical events onto the active well's formation interval |
| **Analog ranking** | Geography + geology + trajectory composite score — a ranking heuristic, never a risk score |
| **Proactive alerts** | Deterministic rule engine fires when a mapped historical hazard enters the lookahead window; WebSocket + HTTP polling |
| **Institutional retrieval** | Cited full-text answers from approved passages; optional local-only semantic search (no remote LLM required) |
| **Engineer feedback** | Action taken, observed outcome, and uncertainty fields — auditable and separate from approval |
| **Prediction readiness** | Model qualification gate display; telemetry quality dossier; no trained model yet |
| **Voice memos** | Shift-note audio capture with consent gate, 30-day retention, local Whisper ASR (optional) |

---

## 2. Architecture

```
                        ┌──────────────────────────────────────────┐
                        │           React / TypeScript UI           │
                        │  (Vite dev server or nginx in container)  │
                        └────────────────┬─────────────────────────┘
                                         │ HTTP / WebSocket  /api/v1/…
                        ┌────────────────▼─────────────────────────┐
                        │          FastAPI  (uvicorn)               │
                        │  auth · wells · alerts · ingestion API    │
                        │  intelligence · prediction · report-facts │
                        └──────┬──────────────┬────────────────────┘
                               │              │
              ┌────────────────▼──┐   ┌───────▼──────────────┐
              │  PostgreSQL 16     │   │  Document storage    │
              │  + PostGIS 3       │   │  (local bind-mount)  │
              │  + pgvector 0.8    │   └──────────────────────┘
              └───────┬───────────┘
                      │ (background workers)
        ┌─────────────┴──────────────────────────────┐
        │   Ingestion worker          Replay worker   │
        │   (text + OCR + extract)    (telemetry sim) │
        └────────────────────────────────────────────┘
```

**Key design decisions:**
- No ML dependency on the alert path. Deterministic rules fire from approved evidence.
- REST for all records and actions; WebSocket for streaming replay snapshots and alert updates with HTTP long-poll fallback.
- All tokens are hashed (SHA-256) at rest; no token is stored in plaintext.
- Every approved claim records document, page, quote, and reviewer — the evidence chain is complete before alerts can reference it.

---

## 3. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| API | Python / FastAPI | 3.12 / 0.115 |
| ASGI server | uvicorn | 0.34 |
| Database | PostgreSQL + PostGIS + pgvector | 16 / 3.x / 0.8 |
| ORM / migrations | SQLAlchemy + Alembic | 2.0 / 1.16 |
| DB driver | psycopg (v3 binary) | 3.2 |
| Settings | pydantic-settings | 2.9 |
| Frontend framework | React 19 + TypeScript 5.8 | — |
| Build tool | Vite | 6.4 |
| Map | Leaflet | 1.9 |
| Container runtime | Docker Compose | v2 |
| Optional ASR | faster-whisper | ≥1.2 |
| Optional semantic | fastembed | 0.8 |
| Linter | Ruff | 0.11 |

---

## 4. Repository Layout

```
.
├── backend/
│   ├── nwis/
│   │   ├── main.py              # FastAPI app, route registration, middleware
│   │   ├── config.py            # pydantic-settings, env-prefix NWIS_
│   │   ├── security.py          # Bearer token auth, role-based dependency
│   │   ├── db.py                # Connection pool helper
│   │   ├── seed.py              # Golden fixture loader (synthetic only)
│   │   ├── schemas.py           # Shared response models
│   │   ├── intelligence.py      # Nearby-well map + analogue ranking API
│   │   ├── operations.py        # Replay session + alert lifecycle API
│   │   ├── operations_worker.py # Background telemetry replay worker
│   │   ├── ingestion/           # Upload, job queue, text/OCR, extraction
│   │   ├── prediction.py        # Model readiness + gate display
│   │   ├── report_facts.py      # Structured fact review + approval
│   │   ├── exploration.py       # Depth-track, mud-window, planning panel
│   │   ├── telemetry_dossier.py # Historical telemetry quality screening
│   │   ├── voice.py             # Voice memo upload + retention
│   │   ├── offset_brief.py      # Printable offset-well evidence brief
│   │   ├── drilling_parameters.py # ROP/WOB/ECD parameter queries
│   │   ├── pressure_window.py   # Pore-pressure / fracture-gradient bands
│   │   ├── real_ml_approval.py  # ML model approval gate (not yet active)
│   │   ├── train_mud_loss.py    # Local mud-loss model training stub
│   │   ├── semantic.py          # fastembed vector retrieval (optional)
│   │   └── …                    # Additional utility modules
│   ├── migrations/              # Alembic migration scripts
│   ├── tests/                   # pytest integration tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Root: auth landing + nav rail + shell
│   │   ├── Operations.tsx       # 00 · Observe — live alerts + replay
│   │   ├── Intelligence.tsx     # 01 · Explore — map + analogue + depth-track
│   │   ├── ReportQuestions.tsx  # 02 · Investigate — cited Q&A
│   │   ├── Documents.tsx        # 03 · Validate — document review
│   │   ├── Prediction.tsx       # 05 · Evaluate — model readiness
│   │   ├── ExplorationExtras.tsx# Depth-track, mud-window, planning panel
│   │   ├── TelemetryDossier.tsx # Telemetry quality dossier
│   │   ├── OffsetBrief.tsx      # Printable offset-evidence brief
│   │   ├── VoiceMemo.tsx        # Shift-note audio capture
│   │   ├── ReportFacts.tsx      # In-document fact review panel
│   │   └── styles.css           # Design system (2 500+ lines, dark theme)
│   ├── vite.config.ts           # Proxy /api → backend:8000
│   └── package.json
├── database/
│   └── Dockerfile               # PostgreSQL 16 + PostGIS + pgvector
├── specs/
│   └── fixtures/
│       └── golden-demo.json     # Fictional synthetic demo fixture
├── docs/
│   ├── phase-0/                 # Spec: scope, arch, data model, UX, backlog
│   ├── phase-1/ … phase-7/     # Phase decision records and completion notes
│   └── ui/                     # Greenfield UI/UX handoff specification
├── compose.yaml
├── .env.example
└── .gitignore
```

---

## 5. Quick Start — Docker Compose

### Prerequisites

- Docker ≥ 24 with Compose v2 (`docker compose version`)
- 4 GB RAM available for containers

### Step 1 — Create `.env`

```bash
cp .env.example .env
```

Edit `.env` and set **unique** values for every token (minimum 16 characters each). The four tokens must all be different:

```env
NWIS_DB_PASSWORD=change-me-long-password-here
NWIS_VIEWER_TOKEN=nwis-viewer-token-local-2024
NWIS_ENGINEER_TOKEN=nwis-engineer-token-local-2024
NWIS_REVIEWER_TOKEN=nwis-reviewer-token-local-2024
NWIS_ADMIN_TOKEN=nwis-admin-token-local-2024
```

> **Demo tokens (testing only):**
> ```
> NWIS_VIEWER_TOKEN=nwis-viewer-token-local-demo-2024
> NWIS_ENGINEER_TOKEN=nwis-engineer-token-local-demo-2024
> NWIS_REVIEWER_TOKEN=nwis-reviewer-token-local-demo-2024
> NWIS_ADMIN_TOKEN=nwis-admin-token-local-demo-2024
> ```
> These match the committed `.env` if you ran the setup above. Never use these in any shared or external environment.

### Step 2 — Build and start

```bash
docker compose up --build -d
```

Services start in dependency order:
1. **db** — PostgreSQL with PostGIS + pgvector (healthcheck: pg_isready)
2. **migrate** — Alembic migrations + user seeding
3. **api** — FastAPI on port 8000 (healthcheck: `/healthz`)
4. **worker** — ingestion background worker
5. **replay** — telemetry replay worker
6. **web** — nginx serving the built frontend, proxying `/api` to api:8000

### Step 3 — Verify

```bash
# API health
curl http://localhost:8000/healthz
# → {"state":"running"}

# Platform status (replace token)
curl -H "Authorization: Bearer nwis-viewer-token-local-demo-2024" \
     http://localhost:8000/api/v1/status | python3 -m json.tool
```

Open **http://localhost:3000** in your browser and enter any of the tokens from `.env`.

---

## 6. Access Tokens & Roles

Tokens are stored as SHA-256 hashes. There is no session cookie or JWT — the token is sent as `Authorization: Bearer <token>` on every request and stays in browser memory only (never localStorage).

| Role | Token env var | Permissions |
|---|---|---|
| **viewer** | `NWIS_VIEWER_TOKEN` | Read all approved data, alerts, wells, documents (approved content only) |
| **engineer** | `NWIS_ENGINEER_TOKEN` | Viewer + acknowledge/dismiss alerts, record feedback, upload voice memos |
| **reviewer** | `NWIS_REVIEWER_TOKEN` | Engineer + approve/reject document candidates, correct extracted facts, manage source qualification |
| **admin** | `NWIS_ADMIN_TOKEN` | All above + load fixtures, manage users, access admin endpoints |

Role hierarchy: `viewer ⊂ engineer ⊂ reviewer ⊂ admin`

Unauthorized actions return **HTTP 403**. Unauthenticated requests return **HTTP 401**. All privileged actions are written to `audit_log`.

---

## 7. Loading Demo Data

The golden fixture is a fully fictional, labeled-synthetic dataset with 3 wells, pre-mapped formation intervals, mud-loss events, and supporting evidence passages.

```bash
# Load the golden demo fixture (admin token required)
curl -X POST \
     -H "Authorization: Bearer nwis-admin-token-local-demo-2024" \
     http://localhost:8000/api/v1/admin/fixtures/golden
```

Response:
```json
{
  "dataset_id": "…uuid…",
  "wells": 3,
  "events": 8,
  "documents": 2,
  "repeated": false
}
```

Loading the same fixture a second time is safe — it returns `"repeated": true` without duplicating data.

After loading, select **SYN-A** as the active well and set radius to **5 km** to see nearby wells. Navigate to **Observe (00)** to start the replay and see alerts appear at MD 2030 m.

---

## 8. Frontend Views

The UI uses a fixed vertical navigation rail (left side, 56 px wide) with six views:

### 00 · Observe (`/` → `operations`)
**Live telemetry and evidence-backed alerts.**

- Connects via WebSocket (`/api/v1/operations/stream`) with automatic HTTP long-poll fallback
- Shows current measured depth, replay session state, and alert budget (shift advisory cap)
- Alert cards display: hazard type, lifecycle state, mapped depth interval, supporting evidence quotes, document page links
- Per-alert actions: **Acknowledge**, **Dismiss** (requires reason), **Escalate**
- Engineer feedback panel: action taken / observed outcome / uncertainty rating
- Suppressed-alert budget panel with suppression reasons
- Source mode badge: `SIMULATED` (replay) or `LIVE` (future eRTMAC)

### 01 · Explore (`intelligence`)
**Nearby-well map and formation depth correlation.**

- Leaflet interactive map showing surface positions of all loaded wells
- Active well picker + radius slider (1–25 km)
- Analogue ranking table with similarity score breakdown (geography / geology / trajectory)
- **Depth track**: color-coded formation intervals, historical hazard events, drilling parameters (ROP, torque)
- **Mud window**: pore-pressure / fracture-gradient / ECD bands by depth interval
- **Planning panel**: formation hazard picture (radius-aggregated hazard counts per formation)
- **Operational evidence**: special operations summary, NPT exposure, mitigation graph
- **Offset brief**: printable single-page evidence summary for field use
- **Bottomhole proximity**: terminal survey position comparison (reviewed pairs only)

### 02 · Investigate (`questions`)
**Cited Q&A from the institutional memory.**

- Predefined questions scoped to the loaded dataset
- Answers contain: status, answer text, rationale, and full citations (document, page, passage quote)
- Zero evidence → explicit "no evidence" response (no hallucinated answers)
- Requires at least one approved document with extracted passages

### 03 · Validate (`documents`)
**Document ingestion and evidence review.**

- Upload drilling reports: PDF (text or scanned), up to 25 MB / 50 pages
- Document list with: ingest status, qualification state, authorization state, extraction job progress
- Per-page raw text / OCR confidence display
- Per-candidate review panel: approve / correct / reject extracted events
- Field-level correction with before/after audit trail
- Document-level approval (reviewer role required)
- Voice memo capture tab: audio recording with consent gate, language selector (English / Hindi / Assamese), optional local Whisper ASR

### 04 · Directory (`foundation`)
**Well directory and platform status.**

- Platform component health grid: Database / Spatial / Vector / Ingestion / Replay / Prediction
- Active well selector with coordinates and basin info
- Nearby wells list by surface distance
- Dataset inventory and environment badge

### 05 · Evaluate (`prediction`)
**Model readiness and qualification gate.**

- Historical inventory: approved mud-loss events and physical well count by source type
- Qualification gates: what must pass before a model score is permitted
- Proposed feature contract (14+ features, pre-anchor only)
- Telemetry quality dossier: per-wellbore screening (row count, depth advance, gap analysis, rig-state distribution, quality fractions)
- Clear "NO TRAINED MODEL" state — no fabricated risk scores

---

## 9. API Reference

All endpoints require `Authorization: Bearer <token>`. Base path: `/api/v1/`.

### Core

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/healthz` | none | Liveness check |
| GET | `/api/v1/status` | viewer | Platform component status |
| GET | `/api/v1/wells` | viewer | Paginated well list (cursor-based) |
| GET | `/api/v1/wells/nearby` | viewer | Surface-distance nearby wells |
| POST | `/api/v1/admin/fixtures/golden` | admin | Load synthetic golden fixture |

### Operations (Alerts & Replay)

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/operations/snapshot` | viewer | Current replay snapshot (HTTP) |
| GET | `/api/v1/operations/stream` | viewer | WebSocket streaming snapshots |
| POST | `/api/v1/operations/session` | engineer | Create/reset replay session |
| POST | `/api/v1/operations/alerts/{id}/acknowledge` | engineer | Acknowledge alert |
| POST | `/api/v1/operations/alerts/{id}/dismiss` | engineer | Dismiss alert (reason required) |
| POST | `/api/v1/operations/alerts/{id}/escalate` | engineer | Escalate alert |
| POST | `/api/v1/operations/alerts/{id}/feedback` | engineer | Record observed outcome |
| GET | `/api/v1/operations/alerts/{id}/decision-ledger` | viewer | Full audit trail for alert |

### Intelligence (Analogues & Exploration)

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/intelligence/analogues` | viewer | Ranked analogue wells for a formation interval |
| GET | `/api/v1/intelligence/formation-intervals` | viewer | Approved intervals for a wellbore |
| GET | `/api/v1/intelligence/depth-track/{wellbore_id}` | viewer | Depth-track data (intervals + events + params) |
| GET | `/api/v1/intelligence/mud-window/{wellbore_id}` | viewer | Pressure window bands |
| GET | `/api/v1/intelligence/planning-picture` | viewer | Radius hazard picture for planning |
| GET | `/api/v1/intelligence/mitigation-links` | viewer | Mitigation → outcome links |
| GET | `/api/v1/intelligence/operational-evidence` | viewer | Special ops + NPT exposure |
| GET | `/api/v1/intelligence/offset-brief` | viewer | Printable offset brief JSON |
| GET | `/api/v1/intelligence/bottomhole-proximity` | viewer | Terminal position proximity |

### Ingestion (Document Review)

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/api/v1/ingestion/documents` | reviewer | Upload a report document |
| GET | `/api/v1/ingestion/documents` | reviewer | List documents |
| GET | `/api/v1/ingestion/documents/{id}` | reviewer | Document detail with candidates and pages |
| POST | `/api/v1/ingestion/documents/{id}/approve` | reviewer | Approve document and all reviewed candidates |
| POST | `/api/v1/ingestion/candidates/{id}/approve` | reviewer | Approve individual candidate |
| POST | `/api/v1/ingestion/candidates/{id}/correct` | reviewer | Correct extracted fields |
| POST | `/api/v1/ingestion/candidates/{id}/reject` | reviewer | Reject a candidate |
| POST | `/api/v1/voice-memos` | engineer | Upload voice memo (multipart) |
| GET | `/api/v1/voice-memos` | engineer | List retained memos |

### Report Facts (Structured Retrieval)

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/report-facts/questions` | viewer | Predefined questions for dataset |
| POST | `/api/v1/report-facts/ask-question` | viewer | Answer a question with citations |
| GET | `/api/v1/report-facts/facts/{document_id}` | reviewer | Facts extracted from a document |
| POST | `/api/v1/report-facts/facts` | reviewer | Record a manual fact |
| POST | `/api/v1/report-facts/facts/{id}/approve` | reviewer | Approve a fact |
| POST | `/api/v1/report-facts/facts/{id}/block` | reviewer | Block a fact with reason |

### Prediction & Telemetry

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/prediction/readiness` | viewer | Model qualification gate status |
| GET | `/api/v1/telemetry-sources` | viewer | List historical telemetry sources |
| GET | `/api/v1/telemetry-sources/{id}/quality-dossier` | viewer | Wellbore-level quality screen |

---

## 10. Data Model Overview

```
dataset ─────────────────────────────────────────────────────────┐
│  id, external_id, name, kind (synthetic/public/private)        │
│  qualification_status, origin_kind, authorization_state        │
└──┬─────────────────────────────────────────────────────────────┘
   │ 1:N
   ├── well  (surface_point: PostGIS geography, basin_name)
   │     └── wellbore  (name, trajectory_survey → survey_station[])
   │
   ├── formation  (canonical_code, display_name, basin_name)
   │     └── formation_interval  (top_md_m, base_md_m, depth_reference, review_state)
   │
   ├── document  (filename, doc_type, ingest_status, page_count)
   │     ├── document_page  (raw_text, ocr_applied, ocr_confidence)
   │     └── extraction_candidate  (state, current_fields{}, version)
   │           └── extraction_history  (before/after, reviewer, timestamp)
   │
   ├── drilling_event  (event_type, source_interval, review_state)
   │     ├── event_passage  (quote, page_number, passage_id, ocr_image_verified)
   │     └── event_mapping  (mapped_interval, method, version, uncertainty)
   │
   └── telemetry_source  (external_id, source_kind, units_reviewed …)
         └── drilling_record  (md_m, rop, wob, ecd, rig_state, revision)

replay_session  (state, revision, current_md_m, steps_total)
  └── alert_episode  (hazard_type, lifecycle, depth_band, revision)
        ├── alert_evidence  (snapshot of event_passage at alert creation)
        └── alert_action   (acknowledge/dismiss/escalate/feedback)

app_user  (username, role, token_hash[SHA-256], active)
audit_log (actor_name, action, entity_type, entity_id, details, created_at)
ingestion_job  (document_id, status, attempt_count, lease_expires_at)
service_heartbeat  (service, last_seen_at)
```

**Key invariants:**
- Only `approved` event versions contribute to alert evidence
- A formation interval requires `review_state = 'approved'` before correlation
- Depth references must be explicit and compatible; MD ≠ TVD unless fixture certifies vertical
- Evidence snapshots are immutable after creation; re-extraction creates a new version

---

## 11. Alert System

### How Alerts Fire

For current measured depth `d`, mapped event interval `[a, b]`, and lookahead `L = 100 m`:

```
Event is relevant when:  b >= d  AND  a <= d + L
Distance-to-start:       max(0, a - d)
```

One episode per `(replay_session, active_well, target_formation_interval, hazard_type, depth_band)` where `depth_band = floor(mapped_start_md / 50)`. A database unique constraint enforces deduplication under concurrent writes.

### Alert Lifecycle

```
OPEN → ACKNOWLEDGED → RESOLVED (by engineer feedback)
     → DISMISSED    (reason required)
     → ESCALATED
```

- **Repeated ticks** within the same episode only update `last_seen_at` and `seen_count` — no duplicate alerts
- **Reconnects** replay the current state — no re-firing
- **Evidence changes** (reviewer corrections) increment the episode revision and notify connected clients
- **Stale telemetry** stops new alerts (`ALR-03`)
- **Missing ML score** does not stop historical-evidence alerts

### Alert Budget

A shift budget caps advisory alerts to prevent alarm fatigue:
- Default: 3 advisories per shift (8 hours)
- Safety-critical alerts bypass the cap
- Suppressed alerts are shown with their reason in the budget panel
- Budget state is shown in the context bar

---

## 12. Formation Correlation Algorithm

The heuristic maps historical event depths from an offset well into the active well's coordinate system using approved formation interval boundaries.

**Steps (v1):**

1. Select offset wells inside the surface radius, same dataset/basin; exclude active well
2. Resolve formation identity: requires approved `top_md_m` / `base_md_m` intervals and compatible depth references in both wells
3. Convert to TVD using survey stations; do not extrapolate or assume MD = TVD (exception: golden fixture certifies vertical wells)
4. Compute fractional position in the offset well's formation: `f = (event_tvd − offset_top_tvd) / (offset_base_tvd − offset_top_tvd)`, require `f ∈ [0, 1]` and positive formation thickness
5. Map to active: `active_top_tvd + f × (active_base_tvd − active_top_tvd)`, convert back to MD via active survey
6. Persist source interval, target interval, method, version, and uncertainties

**Unresolved conditions** (blocks numerical mapping, preserves human-readable case):
- Missing base interval
- Ambiguous repeated formation occurrences
- Incompatible depth datum (e.g., KB vs RT without elevation)
- Invalid or non-monotonic survey stations
- Extrapolation required beyond survey coverage

A reviewer can record an explicit override mapping with full provenance.

---

## 13. Analog Ranking

Similarity score formula (configurable weights):

| Component | Weight | Formula |
|---|---|---|
| Geography | 0.30 | `max(0, 1 − distance_m / radius_m)` |
| Geology | 0.50 | `1.0` if approved target formation present, `0.0` for known mismatch, `null` if unknown |
| Trajectory | 0.20 | Same normalized distance function applied at the target interval, not just at TD |

- Missing components renormalize weights over available data; absent components are disclosed
- Score is a ranking heuristic — **never** a calibrated risk probability
- Top-K display cutoff does not silently discard alert evidence; evidence from below-cutoff wells is preserved

---

## 14. Configuration Reference

All settings are read from environment variables with the `NWIS_` prefix.

| Variable | Required | Default | Description |
|---|---|---|---|
| `NWIS_DATABASE_URL` | ✅ | — | `postgresql+psycopg://user:pass@host/db` |
| `NWIS_VIEWER_TOKEN` | ✅ | — | Bearer token for viewer role (≥16 chars) |
| `NWIS_ENGINEER_TOKEN` | ✅ | — | Bearer token for engineer role (≥16 chars) |
| `NWIS_REVIEWER_TOKEN` | ✅ | — | Bearer token for reviewer role (≥16 chars) |
| `NWIS_ADMIN_TOKEN` | ✅ | — | Bearer token for admin role (≥16 chars) |
| `NWIS_ENVIRONMENT` | | `local` | `local` \| `test` \| `production` |
| `NWIS_DB_PASSWORD` | ✅ (compose) | — | PostgreSQL password (used in compose URL) |
| `NWIS_API_PORT` | | `8000` | Host port for API container |
| `NWIS_WEB_PORT` | | `3000` | Host port for frontend container |
| `NWIS_DB_PORT` | | `5432` | Host port for PostgreSQL container |
| `NWIS_STORAGE_ROOT` | | `storage` | Absolute path for document storage |
| `NWIS_UPLOAD_MAX_BYTES` | | `26214400` | Max upload size (25 MB) |
| `NWIS_DOCUMENT_MAX_PAGES` | | `50` | Max pages per document |
| `NWIS_EXTRACTION_PROVIDER` | | `local_rules` | `local_rules` \| `openai_compatible` |
| `NWIS_SEMANTIC_ENABLED` | | `false` | Enable local fastembed retrieval |
| `NWIS_LLM_BASE_URL` | | `https://api.openai.com/v1` | Base URL for OpenAI-compatible LLM |
| `NWIS_LLM_MODEL` | | — | Model name (required if provider=openai_compatible) |
| `NWIS_LLM_API_KEY` | | — | API key (required if provider=openai_compatible) |
| `NWIS_WORKER_POLL_S` | | `2` | Ingestion worker poll interval (seconds) |
| `NWIS_JOB_LEASE_S` | | `180` | Job lease duration (seconds) |
| `NWIS_VOICE_MODEL_PATH` | | — | Absolute path to local Whisper model directory |

**Constraints enforced at startup:**
- All four tokens must be unique
- Database URL must use `postgresql+psycopg://` scheme
- `openai_compatible` provider requires model name, API key, and HTTPS base URL
- Fixture loading is blocked in `production` environment

---

## 15. Local Development (No Docker)

### Backend

```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

cd backend

# Create venv and install
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"

# Set environment (or export individually)
export NWIS_DATABASE_URL="postgresql+psycopg://nwis:nwis@localhost:5432/nwis"
export NWIS_ENVIRONMENT=local
export NWIS_VIEWER_TOKEN=nwis-viewer-token-local-demo-2024
export NWIS_ENGINEER_TOKEN=nwis-engineer-token-local-demo-2024
export NWIS_REVIEWER_TOKEN=nwis-reviewer-token-local-demo-2024
export NWIS_ADMIN_TOKEN=nwis-admin-token-local-demo-2024

# Run migrations
python -m nwis.initialize

# Start API
uvicorn nwis.main:app --reload --port 8000

# Start ingestion worker (separate terminal)
python -m nwis.worker

# Start replay worker (separate terminal)
python -m nwis.operations_worker
```

### Frontend

```bash
cd frontend
npm install

# Point Vite proxy at local API (optional, defaults to localhost:8000)
# NWIS_DEV_API_URL=http://localhost:8000 npm run dev

npm run dev
# → http://localhost:5173
```

The Vite dev server proxies `/api/*` and `/healthz` to `http://localhost:8000` automatically.

---

## 16. Running Tests

```bash
cd backend
source .venv/bin/activate

# All tests
pytest

# Specific module
pytest tests/test_intelligence.py -v

# With coverage
pytest --cov=nwis --cov-report=term-missing
```

Frontend type check:

```bash
cd frontend
npm run typecheck
```

---

## 17. Smoke Tests

The frontend directory contains Node.js smoke test scripts that validate API contracts without a browser:

```bash
cd frontend

# System status + wells
node ui-smoke.mjs

# Intelligence / analogue ranking
node intelligence-smoke.mjs

# Operations / alert lifecycle
node operations-smoke.mjs

# Prediction readiness
node prediction-smoke.mjs

# Public/benchmark document flow
node public-review-smoke.mjs

# Semantic retrieval (requires NWIS_SEMANTIC_ENABLED=true)
node semantic-smoke.mjs

# WebSocket streaming
node websocket-smoke.mjs
```

Each smoke test exits 0 on success and prints a structured summary of checked endpoints.

---

## 18. Acceptance Matrix

Status of planned acceptance checks (from Phase 0 specification):

| ID | Requirement | Status |
|---|---|---|
| ING-01 | Text + scanned report ingestion, page/section evidence preserved | ✅ Implemented |
| ING-02 | Null-preserving normalization, unknown values enter review | ✅ Implemented |
| ING-03 | Correction audit trail; no duplicate documents on retry | ✅ Implemented |
| MAP-01 | Radius search matches geodesic expectations | ✅ Implemented (PostGIS ST_DWithin) |
| COR-01 | Golden interval maps to active MD 2130–2140 m | ✅ Verified in fixture tests |
| COR-02 | Surface distance and analog score displayed separately | ✅ Implemented |
| RET-01 | Cited answers; explicit no-evidence for zero support | ✅ Implemented |
| RET-02 | Hazard/formation/depth filters; no LLM-authored SQL | ✅ Implemented |
| ALR-01 | Mud-loss alert at MD 2030 m with approved evidence | ✅ Implemented (golden fixture) |
| ALR-02 | No duplicate alerts on repeated ticks / reconnects | ✅ Implemented |
| ALR-03 | Stale telemetry stops alerts; missing ML score does not | ✅ Implemented |
| UX-01 | Dashboard: MD, formation, mode, alerts, evidence accessible | ✅ All 6 views implemented |
| UX-02 | Field-friendly layout (mobile-responsive) | ⚠️ Partial — desktop-first, narrow layout works |
| FBK-01 | Action, outcome, uncertainty — auditable and separate | ✅ Implemented |
| ML-01 | Hazard model vs baseline on held-out wells, metrics documented | ❌ No trained model; gate display only |
| ML-02 | Score carries model version, horizon, calibration evidence | ❌ Pending trained model |
| OPS-01 | Fresh setup, migration, fixture loading documented | ✅ This README |
| OPS-02 | Role-based access, server-side rejection, audit log | ✅ Implemented |
| PERF-01 | p95 < 2 s for radius + retrieval queries (100 wells, 10k passages) | ⚠️ Not benchmarked; synthetic demo only |
| PERF-02 | < 120 s for ≤10-page demo report ingestion | ⚠️ Not benchmarked |

---

## 19. Phased Roadmap

| Phase | Focus | Key Deliverables |
|---|---|---|
| 0 | Specification | Scope, arch, data model, UX, acceptance criteria, backlog |
| 1 | Foundation | Docker Compose, migrations, seed, smoke tests, token auth |
| 2 | Ingestion & Review | Upload, OCR, rule extraction, reviewer correction, audit trail |
| 3 | Nearby Wells & Correlation | PostGIS radius, analogue ranking, depth-track, formation mapping |
| 4 | Alerts & Operations | WebSocket replay, deterministic rule engine, alert lifecycle, feedback |
| 5 | Prediction Gate | Model readiness display, telemetry quality screen, dataset research |
| 6 | Integration & Polish | Semantic search, voice memos, offset brief, public benchmark staging |
| 7 *(planned)* | Extensions | Live eRTMAC adapter, stuck-pipe/kick scenarios, advanced analytics, mobile field view |

**Phase 7 candidate additions** (all require evidence and domain review before claiming they work):
- Live WITSML/eRTMAC adapter (replacing synthetic replay)
- Kick and stuck-pipe alert rules alongside mud-loss
- Formation-pressure window integration with real survey data
- Multi-basin onboarding pipeline
- ML model card with held-out evaluation on OIL-approved data
- Native mobile field view (PWA)

---

## 20. Important Caveats

> **This is a prototype for demonstration purposes. Read these before citing any output.**

1. **No operational use.** NWIS does not control drilling equipment and must not be used for operational decisions.

2. **Synthetic data only.** The golden fixture contains entirely fictional wells, formations, events, and reports — explicitly labeled `data_kind: synthetic`. No OIL proprietary data is included or should be committed to this repository.

3. **No trained model.** The Evaluate view shows a qualification gate, not a trained classifier. `NO TRAINED MODEL` is the correct, honest system state. No risk score is displayed because none has been validated.

4. **No ground-truth labels.** Acknowledgments and "no incident observed" feedback are engineer observations, not ground-truth labels for ML training.

5. **Historical mitigations are observations.** Cited historical actions are observations for engineer review. They do not establish guaranteed efficacy.

6. **Analog score ≠ risk score.** The similarity score is a ranking heuristic combining geography, geology, and trajectory. It is not a calibrated probability of any outcome.

7. **Formation names ≠ matching conditions.** Two wells penetrating the same named formation may face different pressure, lithology, and hazard conditions.

8. **Local tokens only.** Tokens in `.env` are for local development. Never expose them in shared environments, version control, or CI logs.

9. **NOD-511 depth conflict.** A real-data depth datum conflict (NOD-511) and public report rights are open issues identified in Phase 2. Real data requires separate qualification and rights review before inclusion.

10. **SIMULATED badge.** The `SIMULATED` source mode badge is always visible when the replay worker is running. This is intentional — it must not be confused with live sensor data.

---

## Repository

```
https://github.com/oki-dokii/baithe-baithe-bore-hua-karna-hai-kuch-kaam
```

Branches follow `codex/<phase-or-feature>`. Each implementation PR references acceptance IDs and records verification. Specifications in `docs/` are updated in the same PR when behavior changes.

**Commit:** application code, migrations, documentation, small synthetic fixtures.  
**Do not commit:** credentials, raw third-party datasets, generated OCR text, uploaded reports, model binaries, local databases, `.env`.

---

*The prototype uses replayed telemetry labeled SIMULATED. It does not control drilling equipment. Synthetic examples establish behavior, not predictive accuracy or expected field performance.*
