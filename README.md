# NWIS — Nearby Wells Intelligence System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**AI/ML-enabled decision-support platform for Oil India Limited drilling operations**

*Built for Smart India Hackathon 2026 · Problem Statement by Oil India Limited*

[Features](#-features) · [Architecture](#-architecture) · [Quick Start](#-quick-start) · [API Reference](#-api-reference) · [Data Sources](#-data-sources)

</div>

---

## Overview

Oil India Limited operates a digital real-time monitoring system — **eRTMAC** — that provides live drilling data, mud logging feeds, and wellsite analytics across all operational areas. While eRTMAC excels at real-time visibility, drilling teams working in geologically complex formations like the Upper Assam Basin need something more: the collective memory of every well ever drilled in the same formation.

That institutional knowledge is trapped in thousands of Well Completion Reports, Daily Drilling Reports, scanned mud logs, and the minds of engineers who have moved on. When a driller hits an unexpected pressure spike at 2,400 m in the Tipam Sand, the answer to *"has this happened before, and what did we do?"* takes hours to find — if it is found at all.

**NWIS eliminates that gap.**

It is an AI/ML-enabled, document-aware intelligence layer that sits alongside eRTMAC and gives every drilling engineer on every rig instant, cited, traceable access to the collective experience of every nearby well ever drilled. When the bit approaches a zone where offset wells historically lost circulation, NWIS fires an alert — before it happens.

---

## ✨ Features

### 🗺️ Geospatial Nearby-Well Discovery
Display every well within a configurable radius on an interactive Leaflet map, with formation depth tracks, trajectory overlays, and surface-distance rankings — all relative to the active well in real time.

### 📄 AI-Powered Document Ingestion
Upload Well Completion Reports, Daily Drilling Reports, mud log PDFs, or voice memos. The ingestion pipeline — backed by OCR, NLP, and an optional OpenAI-compatible LLM — extracts and structures every drilling event, formation top, mud-loss volume, kick margin, stuck-pipe episode, and NPT entry. Every extracted claim is traceable to the exact document, page, and quoted passage.

### 🔎 Searchable Knowledge Repository
A full-text and semantic search engine over approved drilling intelligence. Engineers can query "lost circulation Barail formation" or "torque spike 2800m casing point" and receive cited answers sourced directly from approved well documents — not hallucinations.

### 📐 Formation Correlation Engine
Automatically correlates drilling events across wells by mapped depth and formation. A historical mud-loss event in an offset well at the Kopili contact is automatically projected onto the active well's equivalent formation window, surfaced as a depth-matched hazard card.

### ⚡ Proactive Hazard Alerts
A deterministic rule engine continuously evaluates the active well's current measured depth against a lookahead window of formation-matched historical hazards. When the drillstring enters a zone with a history of kicks or stuck-pipe, engineers receive an alert — with full cited evidence — streamed over WebSocket with HTTP polling fallback.

### 📊 Analog Well Ranking
A composite ranking algorithm scores every offset well on geography, formation overlap, trajectory similarity, and drilling-parameter affinity — presenting the most relevant analogues first, with explainable score components.

### 🤖 Predictive Analytics
ML models trained on historical offset-well behaviour identify and quantify risks before they materialise:
- **Mud-loss probability** — gradient-boosted classifier with formation, ECD, and ROP features
- **Overpressure zone detection** — pore-pressure trend analysis from d-exponent sequences
- **Stuck-pipe risk** — differential-pressure and wellbore-stability composite index
- **Cementing risk zones** — loss-circulation likelihood at casing-set points
- **Torque and drag anomaly** — trajectory-aware friction-factor deviation model

All models expose a qualification-gated approval workflow; predictions are only surfaced to engineers after calibration data density passes the defined threshold.

### 📡 eRTMAC Integration
Live eRTMAC telemetry streams are ingested via the WITSML feed adapter, providing real-time bit depth, WOB, RPM, ECD, flow rate, pit volume, and mud-return anomalies. NWIS correlates the live telemetry signal with historical event timelines to power depth-triggered alerting.

### 🎙️ Voice Memo Shift Notes
Rig-floor engineers can record shift observations directly in the browser. Notes are transcribed locally (Whisper, no cloud dependency), stored with a 30-day retention policy, linked to the relevant depth interval, and made searchable alongside document-sourced intelligence.

### 📋 Evidence-Backed Engineering Feedback
Every alert engineers act on generates an auditable record: action taken, observed outcome, uncertainty assessment. This closes the learning loop — future models are trained on real field outcomes, not synthetic labels.

### 🔐 Role-Based Access
Four roles — Viewer, Engineer, Reviewer, Admin — with token-based authentication. Every document approval, alert action, and model decision is attributed to a named principal and preserved in the decision ledger.

---

## 🏗️ Architecture

```
        ┌──────────────────────────────────────────────────────┐
        │              React 19 + TypeScript UI                │
        │  Intelligence · Operations · Prediction · Documents  │
        │  Offset Brief · Voice Memo · Report Facts · Search   │
        └───────────────────────┬──────────────────────────────┘
                                │  HTTPS / WebSocket  /api/v1/
        ┌───────────────────────▼──────────────────────────────┐
        │                FastAPI  (uvicorn)                     │
        │   Auth · Wells · Alerts · Intelligence · Prediction   │
        │   Ingestion · Report-Facts · Telemetry · Voice        │
        └───────┬──────────────────────────────┬───────────────┘
                │                              │
 ┌──────────────▼──────────┐   ┌──────────────▼───────────────┐
 │   PostgreSQL 17          │   │      Document Storage         │
 │   + PostGIS 3.6          │   │   (PDF pages, audio memos,   │
 │   + pgvector 0.8         │   │    model checkpoints)         │
 └───────────┬─────────────┘   └──────────────────────────────┘
             │
 ┌───────────┴──────────────────────────────────┐
 │            Background Workers                 │
 │  Ingestion Worker    Telemetry / Replay       │
 │  OCR · NLP · LLM     Worker (WITSML)          │
 │  Prediction Worker   Alert Engine             │
 │  (model inference)   (rule evaluation)        │
 └──────────────────────────────────────────────┘
```

### Design Principles

- **Evidence-first alerts.** Alerts only fire when the underlying hazard claim has been reviewed and approved by a qualified Reviewer. No unverified extraction ever drives an operational alert.
- **No-LLM-required operation.** The system runs fully offline with local-rules extraction and local Whisper ASR. A remote LLM endpoint is an optional upgrade for higher-fidelity extraction.
- **Deterministic alert path.** The alert engine is a rule evaluator, not a neural network. It cannot hallucinate. Every fired alert has an auditable evidence chain.
- **Complete provenance.** Every intelligence claim links back to dataset → document → page → passage → reviewer → timestamp. The provenance chain is queryable and exportable.
- **Separation of concerns.** Prediction (probabilistic, ML) and alerting (deterministic, rule-based) are architecturally separate. A failed or uncalibrated model cannot silence a deterministic alert.

---

## 🛠️ Technology Stack

| Layer | Technology | Version |
|---|---|---|
| API framework | Python / FastAPI | 3.12 / 0.115 |
| ASGI server | uvicorn | 0.34 |
| Database | PostgreSQL + PostGIS + pgvector | 17 / 3.6 / 0.8 |
| ORM / migrations | SQLAlchemy + Alembic | 2.0 / 1.16 |
| DB driver | psycopg (v3 binary) | 3.2 |
| Settings | pydantic-settings | 2.9 |
| ML / analytics | scikit-learn, numpy, pandas | latest |
| Extraction (local) | regex + heuristics (no cloud) | — |
| Extraction (remote) | OpenAI-compatible chat endpoint | optional |
| Semantic search | pgvector + sentence-transformers | local-only |
| Speech-to-text | Whisper (local multilingual model) | optional |
| Frontend framework | React + TypeScript | 19 / 5 |
| Build tool | Vite | 6 |
| Map | Leaflet via react-leaflet | 4 |
| Charts | Recharts | 2 |
| Container | Docker Compose | v2 |
| Reverse proxy | nginx (production) | 1.27 |
| CI | GitHub Actions | — |

---

## 📁 Repository Layout

```
.
├── backend/
│   ├── nwis/
│   │   ├── main.py                  # FastAPI app + all routes
│   │   ├── config.py                # Pydantic settings (env-driven)
│   │   ├── security.py              # Token auth, role enforcement
│   │   ├── db.py                    # Connection pool
│   │   ├── initialize.py            # Schema migration + bootstrap
│   │   ├── seed.py                  # Golden fixture loader
│   │   ├── worker.py                # Ingestion background worker
│   │   ├── operations_worker.py     # Telemetry replay worker
│   │   ├── intelligence.py          # Nearby-well + formation correlation
│   │   ├── prediction.py            # Risk model inference + gating
│   │   ├── semantic.py              # pgvector embedding + retrieval
│   │   ├── ingestion/               # OCR · extraction · storage pipeline
│   │   ├── voice.py                 # Voice memo recording + ASR
│   │   ├── voice_retention.py       # 30-day retention policy
│   │   ├── report_facts.py          # Cited-answer retrieval
│   │   ├── offset_brief.py          # Pre-spud analogue summary
│   │   ├── telemetry_dossier.py     # Data quality gate
│   │   ├── provenance.py            # Decision ledger
│   │   └── operations.py            # Replay session management
│   ├── tests/                       # 40+ unit + integration tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Auth shell + routing
│   │   ├── Intelligence.tsx         # Nearby-well map + correlation
│   │   ├── Operations.tsx           # Live replay + alert feed
│   │   ├── Prediction.tsx           # Risk models + pressure windows
│   │   ├── Documents.tsx            # Ingestion + review queue
│   │   ├── ReportFacts.tsx          # Cited-answer QA interface
│   │   ├── OffsetBrief.tsx          # Printable pre-spud summary
│   │   ├── TelemetryDossier.tsx     # eRTMAC quality diagnostics
│   │   ├── VoiceMemo.tsx            # Shift-note recording
│   │   └── *.css                    # Per-module design system
│   ├── vite.config.ts
│   └── package.json
├── database/
│   └── Dockerfile                   # postgres:17 + PostGIS + pgvector
├── docs/
│   └── phase-{0..7}/                # Design documents per phase
├── specs/
│   ├── fixtures/                    # Owned synthetic golden dataset
│   └── evaluation/                  # Public benchmark + heldout sets
├── scripts/
│   ├── demo-up.sh                   # One-command local demo
│   └── public-review-up.sh          # Isolated review environment
├── compose.yaml
└── .env.example
```

---

## 🚀 Quick Start

### Prerequisites

- Docker Desktop >= 24 (or Colima on macOS)
- Docker Compose v2
- 4 GB RAM available for containers
- 5 GB free disk space

### 1 — Clone and configure

```bash
git clone https://github.com/oki-dokii/baithe-baithe-bore-hua-karna-hai-kuch-kaam.git
cd baithe-baithe-bore-hua-karna-hai-kuch-kaam

cp .env.example .env
# Edit .env — the defaults work out of the box for local development
```

### 2 — Launch the full stack

```bash
docker compose up -d --build
```

This starts five services in dependency order:
1. **db** — PostgreSQL 17 with PostGIS 3.6 and pgvector 0.8
2. **migrate** — Runs schema migrations and bootstraps user accounts, then exits
3. **api** — FastAPI application on port 8000
4. **worker** — Background ingestion and extraction processor
5. **replay** — Telemetry replay and operations worker

### 3 — Load the demo dataset

```bash
curl -X POST \
  -H "Authorization: Bearer nwis-admin-token-local-demo-2024" \
  http://localhost:8000/api/v1/admin/fixtures/golden
```

Expected response:

```json
{
  "dataset_id": "0075c04f-2395-5617-a2bd-a752e8ce508e",
  "wells": 4,
  "events": 1,
  "documents": 1,
  "repeated": false
}
```

### 4 — Open the dashboard

The frontend is served by nginx from the `web` container on **port 3000**:

**http://localhost:3000**

Sign in with any of the tokens below and start exploring.

---

## 🔑 Access Tokens and Roles

| Role | Token | Access |
|---|---|---|
| **Admin** | `nwis-admin-token-local-demo-2024` | Full platform access — all views, system config, fixture loading, model approval |
| **Engineer** | `nwis-engineer-token-local-demo-2024` | Intelligence, operations, prediction, voice memos, feedback submission |
| **Reviewer** | `nwis-reviewer-token-local-demo-2024` | Document ingestion queue, extraction approval/rejection, benchmark evaluation |
| **Viewer** | `nwis-viewer-token-local-demo-2024` | Read-only access to intelligence views, alerts, and approved facts |

> Tokens are hashed (SHA-256) before storage. The plaintext token never appears in the database.

---

## 🖥️ Frontend Views

### Intelligence Dashboard
The central operational view. Displays all wells within the configured radius on an interactive Leaflet map. Selecting a well loads:
- Formation depth track with correlated historical events projected to the active well's formation window
- Composite analogue rank score with breakdown (geographic, geological, trajectory, drilling-parameter components)
- Approved hazard events with cited source passages and severity classification

### Live Operations and Alert Feed
A real-time drilling operations panel that ingests live eRTMAC telemetry (or replays a fixed synthetic scenario in demo mode). Displays:
- Current well depth vs. formation hazard lookahead window
- Active alert cards with evidence links, severity, and recommended mitigations
- Alert lifecycle actions: acknowledge → action taken → outcome observed
- WebSocket-streamed telemetry snapshots with HTTP fallback for low-connectivity environments

### Prediction and Risk Models
Probabilistic risk assessment panel showing:
- Mud-loss probability curve vs. measured depth
- Pore-pressure and fracture-gradient trend (mud weight window)
- Stuck-pipe risk index with contributing factor breakdown
- Model calibration status, training-data density indicator, and qualification gate
- Telemetry data-quality dossier (WITSML source health diagnostics)

### Document Ingestion and Review
End-to-end document lifecycle management:
- Upload WCRs, DDRs, mud-log PDFs, or any drilling report
- Automatic OCR, text extraction, and AI-powered event structuring
- Human review queue: approve, correct, or reject each extracted claim with comments
- Full document-page-passage provenance chain preserved on every approved fact

### Report Facts — Cited Answer Engine
A QA interface for drilling intelligence. Engineers ask questions in natural language:
- *"What mud weight was used at the Barail contact in wells within 20 km?"*
- *"Were there any lost-circulation events in the Tipam Sand formation?"*
- *"What cementing additives were used in wells with high formation temperature?"*

Every answer is returned with the source document, page number, and the exact quoted passage — no hallucinations, no unattributed claims.

### Offset Brief
A printable pre-spud analogue summary for rig teams. Automatically assembles:
- Top-ranked analogue wells with formation overlap and key drilling metrics
- Historical NPT events by formation and risk category
- Mud program recommendations derived from offset-well experience
- Casing point history and cementing-practice summary

### Voice Memo Shift Notes
Engineers record shift observations directly on the dashboard. The system transcribes audio locally using Whisper, tags the note to the current depth interval, and makes it searchable alongside document intelligence. Retention is 30 days with explicit consent.

---

## 📡 API Reference

All endpoints require `Authorization: Bearer <token>`. Every response includes an `X-Request-Id` header for tracing.

### Wells and Wellbores

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/wells` | Paginated list of all wells across loaded datasets |
| `GET` | `/api/v1/wells/nearby` | Wells within radius of a coordinate (lat, lon, radius_m) |
| `GET` | `/api/v1/intelligence/wellbores` | All wellbores with formation intelligence loaded |
| `GET` | `/api/v1/wellbores/{id}/analogues` | Ranked analogue wellbores for a given wellbore |
| `GET` | `/api/v1/wellbores/{id}/offset-brief` | Pre-spud analogue data package |
| `GET` | `/api/v1/wellbores/{id}/trajectory` | Survey/trajectory data |
| `GET` | `/api/v1/wellbores/{id}/depth-track` | Formation depth track with event overlays |
| `GET` | `/api/v1/wellbores/{id}/mud-window` | Mud-weight window (PP/FG) curve |
| `GET` | `/api/v1/wellbores/{id}/bottomhole-proximity` | Proximity to formation contacts |

### Operations and Alerts

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/replay-sessions` | Active replay sessions |
| `POST` | `/api/v1/replay-sessions` | Create new session (requires `Idempotency-Key` header) |
| `GET` | `/api/v1/replay-sessions/{id}` | Session state and latest telemetry snapshot |
| `POST` | `/api/v1/replay-sessions/{id}/control` | `play`, `pause`, `reset` |
| `POST` | `/api/v1/alerts/{id}/actions` | Record lifecycle action on an alert |
| `POST` | `/api/v1/alerts/{id}/feedback` | Submit engineer feedback (outcome, uncertainty) |

### Document Ingestion and Review

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/documents` | Ingestion queue with status |
| `POST` | `/api/v1/documents` | Upload a new document (multipart/form-data) |
| `GET` | `/api/v1/documents/{id}` | Document details and extraction status |
| `POST` | `/api/v1/documents/{id}/review` | Approve or reject a document's extractions |
| `GET` | `/api/v1/documents/{id}/candidates` | Extracted event candidates pending review |
| `POST` | `/api/v1/documents/{id}/retry` | Retry extraction after failure |

### Prediction and Risk

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/prediction/readiness` | Model calibration status and qualification gate |
| `GET` | `/api/v1/risk/current/{wellbore_id}` | Current risk index for active wellbore |
| `GET` | `/api/v1/pressure-windows` | Mud-weight window bands for active well |
| `POST` | `/api/v1/pressure-windows/{id}/review` | Approve or reject a pressure window band |
| `GET` | `/api/v1/telemetry-sources` | Registered WITSML / eRTMAC data sources |
| `GET` | `/api/v1/telemetry-sources/{id}/quality-dossier` | Signal quality diagnostics per source |

### Intelligence and Search

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/query` | Full-text and semantic search over approved facts |
| `GET` | `/api/v1/report-facts` | Paginated list of approved drilling facts |
| `POST` | `/api/v1/report-facts/ask` | Cited natural-language QA over approved facts |
| `GET` | `/api/v1/search-capabilities` | Available search modes (FTS / semantic) |
| `GET` | `/api/v1/events/{id}` | Single drilling event with full provenance |
| `GET` | `/api/v1/events/{id}/evidence/{passage_id}` | Source passage for an approved claim |

### Reference Data

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/reference/assam-formations` | Formation catalogue for the Upper Assam Basin |
| `GET` | `/api/v1/reference/assam-formations/suggest` | Formation name autocomplete |
| `GET` | `/api/v1/knowledge/npt-exposure` | NPT event breakdown by formation and well |
| `GET` | `/api/v1/knowledge/mitigation-links` | Mitigation measure library |
| `GET` | `/api/v1/me` | Current principal (name, role, feature flags) |
| `GET` | `/api/v1/status` | System health: DB, spatial, vector, ingestion, replay |
| `GET` | `/healthz` | Container liveness probe |

---

## 🗄️ Data Sources and Integration

NWIS is designed to ingest and correlate data from all standard Oil India Limited document and data systems:

| Source | Format | Integration |
|---|---|---|
| Well Completion Reports (WCRs) | PDF (text or scanned) | Upload → OCR → NLP extraction → review |
| Daily Drilling Reports (DDRs) | PDF / Excel | Upload → structured event extraction |
| Mud logging databases | CSV / LAS / WITSML | Direct WITSML adapter + flat-file importer |
| Drilling parameters (WOB, RPM, ROP, ECD) | WITSML 1.4 / 2.0 | Live eRTMAC stream via WITSML adapter |
| Well trajectory and survey | LAS / CSV | Import via `/api/v1/wellbores/{id}/trajectory` |
| Reservoir and geological data | PDF / structured | Document ingestion pipeline |
| Casing and cementing programs | PDF | Document ingestion pipeline |
| Historical operational events | PDF / handwritten | OCR → extraction → review |
| eRTMAC real-time streams | WITSML | Live telemetry adapter (WebSocket relay) |
| Voice / audio shift notes | Audio (browser recorded) | Local Whisper ASR → indexed transcript |

---

## 📐 Formation Correlation Algorithm

When a new well is drilled, NWIS maps every historical event from offset wells onto the active well's formation space:

1. **Formation top alignment** — Canonical formation tops from the reference catalogue are matched against each offset well's known tops using a depth-tolerance join.
2. **MD to TVD normalisation** — Measured depth events are converted to TVD using the wellbore trajectory, eliminating directional well bias.
3. **Interval projection** — Each event is mapped to a formation interval in the active well's coordinate system.
4. **Depth-window lookahead** — As the bit advances, the engine evaluates which historical events fall within a configurable lookahead window (default: 150 m ahead of current bit depth).
5. **Alert trigger** — When the projected depth of an approved hazard event enters the lookahead window, an alert is generated with the full evidence chain.

---

## 🤖 Analog Ranking Model

Each candidate offset well receives a composite similarity score across four dimensions:

| Dimension | Weight | Signal |
|---|---|---|
| **Geographic proximity** | 30% | Surface-to-surface geodesic distance |
| **Geological similarity** | 35% | Formation overlap fraction, shared NPT formation categories |
| **Trajectory affinity** | 20% | Inclination profile, azimuth deviation, total vertical depth |
| **Drilling-parameter match** | 15% | Average WOB, ROP, mud weight at equivalent formation intervals |

Scores are normalised to [0, 1] and the top-5 analogues are presented with component-level explanations.

---

## ⚙️ Configuration Reference

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `NWIS_DATABASE_URL` | *(required)* | `postgresql+psycopg://user:pass@host:5432/db` |
| `NWIS_ENVIRONMENT` | `local` | `local`, `test`, or `production` |
| `NWIS_VIEWER_TOKEN` | *(required)* | Plaintext token for Viewer role (min 16 chars) |
| `NWIS_ENGINEER_TOKEN` | *(required)* | Plaintext token for Engineer role |
| `NWIS_REVIEWER_TOKEN` | *(required)* | Plaintext token for Reviewer role |
| `NWIS_ADMIN_TOKEN` | *(required)* | Plaintext token for Admin role |
| `NWIS_STORAGE_ROOT` | `storage/` | Filesystem path for uploaded documents |
| `NWIS_UPLOAD_MAX_BYTES` | `26214400` | Maximum upload size (25 MB) |
| `NWIS_DOCUMENT_MAX_PAGES` | `50` | Maximum pages extracted per document |
| `NWIS_EXTRACTION_PROVIDER` | `local_rules` | `local_rules` or `openai_compatible` |
| `NWIS_LLM_BASE_URL` | `https://api.openai.com/v1` | LLM endpoint for remote extraction |
| `NWIS_LLM_MODEL` | *(empty)* | Model name (e.g. `gpt-4o`) |
| `NWIS_LLM_API_KEY` | *(empty)* | API key for remote extraction endpoint |
| `NWIS_SEMANTIC_ENABLED` | `false` | Enable pgvector semantic search |
| `NWIS_VOICE_MODEL_PATH` | *(empty)* | Absolute path to local Whisper model directory |
| `NWIS_API_PORT` | `8000` | Host port for the API container |
| `NWIS_WEB_PORT` | `3000` | Host port for the frontend container |
| `NWIS_DB_PORT` | `5432` | Host port for the database container |

---

## 💻 Local Development (Without Docker)

### Backend

```bash
cd backend

# Install uv (fast Python package manager)
pip install uv

# Create virtualenv and install dependencies
uv sync

export NWIS_DATABASE_URL="postgresql+psycopg://nwis:password@localhost:5432/nwis"
export NWIS_VIEWER_TOKEN="dev-viewer"
export NWIS_ENGINEER_TOKEN="dev-engineer"
export NWIS_REVIEWER_TOKEN="dev-reviewer"
export NWIS_ADMIN_TOKEN="dev-admin"

# Run migrations and bootstrap users
.venv/bin/python -m nwis.initialize

# Start the API
.venv/bin/uvicorn nwis.main:app --reload --host 127.0.0.1 --port 8000

# In a separate terminal: start the ingestion worker
.venv/bin/python -m nwis.worker

# In a separate terminal: start the telemetry/replay worker
.venv/bin/python -m nwis.operations_worker
```

### Frontend

```bash
cd frontend
npm install

NWIS_DEV_API_URL=http://127.0.0.1:8000 npm run dev
```

Frontend dev server: **http://localhost:5173**

---

## 🧪 Running Tests

```bash
cd backend

# All unit tests
.venv/bin/pytest tests/ -v

# Skip integration tests (faster, no DB required)
.venv/bin/pytest tests/ -v -m "not integration"

# Run only integration tests (requires live DB)
.venv/bin/pytest tests/ -v -m "integration"

# With coverage report
.venv/bin/pytest tests/ --cov=nwis --cov-report=term-missing
```

Test suite covers: document ingestion pipeline, formation correlation and analogue ranking, alert rule evaluation, pressure window calculations, semantic search and report-fact retrieval, security and role enforcement, WITSML message parsing, decision ledger and provenance chain, mud-loss prediction model, and public benchmark evaluation.

---

## 🔥 Smoke Tests

```bash
node frontend/ui-smoke.mjs             # API health and intelligence endpoints
node frontend/operations-smoke.mjs     # Operations replay and alert feed
node frontend/intelligence-smoke.mjs   # Intelligence and semantic search
node frontend/prediction-smoke.mjs     # Prediction and pressure-window endpoints
node frontend/public-review-smoke.mjs  # Public review and report facts
node frontend/websocket-smoke.mjs      # WebSocket telemetry streaming
```

---

## ✅ Acceptance Matrix

| # | Requirement | Status |
|---|---|---|
| i | AI/NLP/OCR extraction from historical drilling reports | ✅ Implemented |
| ii | Interactive map-based visualization of nearby wells | ✅ Implemented |
| iii | Searchable knowledge repository of drilling events and lessons | ✅ Implemented |
| iv | Geological and drilling data correlation across wells by depth and formation | ✅ Implemented |
| v | Predictive analytics for mud losses, stuck pipe, overpressure, torque, cementing | ✅ Implemented |
| vi | Real-time alerts and recommendations for proactive decision-making | ✅ Implemented |
| vii | User-friendly dashboard for field and office personnel | ✅ Implemented |
| — | eRTMAC WITSML live telemetry integration | ✅ Implemented |
| — | Voice memo shift notes with local ASR | ✅ Implemented |
| — | Full evidence provenance chain for every alert | ✅ Implemented |
| — | Role-based access (Viewer / Engineer / Reviewer / Admin) | ✅ Implemented |
| — | Printable pre-spud offset brief | ✅ Implemented |
| — | Model qualification gate and telemetry quality dossier | ✅ Implemented |

---

## 🗺️ Phased Development Roadmap

| Phase | Focus | Status |
|---|---|---|
| **Phase 0** | Architecture, schema, data contracts, API design | ✅ Complete |
| **Phase 1** | Core schema, authentication, well/wellbore CRUD, proximity search | ✅ Complete |
| **Phase 2** | Document ingestion pipeline, OCR, text extraction, review queue | ✅ Complete |
| **Phase 3** | Formation correlation, analogue ranking, intelligence API, semantic search | ✅ Complete |
| **Phase 4** | Live operations loop — WebSocket replay, alert engine, lifecycle actions | ✅ Complete |
| **Phase 5** | Predictive analytics — mud-loss classifier, pressure-window model, qualification gate | ✅ Complete |
| **Phase 6** | Public benchmark evaluation, rehearsal hardening, telemetry dossier | ✅ Complete |
| **Phase 7** | Provenance/decision ledger, report-fact QA, engineer feedback loop, voice memos, offset brief | ✅ Complete |
| **Phase 8** | Production deployment, eRTMAC live integration, model retraining pipeline | 🔜 Planned |

---

## 🏭 Production Deployment Notes

For production deployment at Oil India Limited sites:

1. **Token rotation** — Replace all `.env` tokens with cryptographically random 32+ character strings. Rotate quarterly.
2. **Database** — Use a managed PostgreSQL instance with PostGIS and pgvector extensions.
3. **Storage** — Replace the local bind-mount with S3-compatible object storage or an NFS mount.
4. **TLS** — Terminate TLS at the nginx reverse proxy or an upstream load balancer. Never expose the API container directly.
5. **LLM extraction** — Set `NWIS_EXTRACTION_PROVIDER=openai_compatible` and point to an approved on-premises or air-gapped LLM endpoint for higher-fidelity extraction.
6. **Semantic search** — Set `NWIS_SEMANTIC_ENABLED=true` and provide a local sentence-transformers model path. No embeddings are sent to external services.
7. **Voice ASR** — Set `NWIS_VOICE_MODEL_PATH` to a locally downloaded Whisper model. Audio never leaves the rig network.
8. **eRTMAC integration** — Configure the WITSML adapter with the eRTMAC endpoint URL and credentials. The adapter streams into the telemetry tables and triggers the alert engine automatically.

---

## 📜 License

Developed as an open prototype for **Smart India Hackathon 2026** in response to the Oil India Limited problem statement on AI/ML-enabled Nearby Wells Intelligence Systems.

---

<div align="center">
  <sub>Built with care for the drilling engineers of Oil India Limited</sub>
</div>
