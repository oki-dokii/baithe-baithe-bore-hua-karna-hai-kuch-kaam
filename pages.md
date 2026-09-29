# NWIS (Nearby Wells Intelligence System) — Pages & Views Specification

> **Platform Concept**: *The Subsurface Observatory*  
> **Mission**: What one well teaches, the next should know. Bringing historical drilling memory, geological correlation, and evidence-backed lookahead intelligence to operational decision-makers without opaque recommendations or unverified claims.

---

## 1. System Architecture & Navigation Overview

The NWIS web interface is organized around a unified persistent shell adhering to the **Place · Depth · Time** coordinate system. Rather than disconnected SaaS pages, NWIS utilizes numbered task-oriented plates (`00` to `05`) accessible via the left navigation rail, unified by a persistent context bar and linked selection cursor.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PERSISTENT CONTEXT BAR: Active Well · Basin · Coords · Mode · Env · Stream (WS/HTTP)   │
├────┬───────────────────────────────────────────────────────────────────────────────────┤
│    │ ACTIVE WORKSPACE CANVAS (One of 6 Plates):                                       │
│ N  │                                                                                   │
│ A  │  [00] Observe     ─ Live well desk, telemetry replay, lookahead & alert triage    │
│ V  │  [01] Explore     ─ Offset well atlas, Leaflet map, depth track, mud window       │
│    │  [02] Investigate ─ Question answering with cited report passages & case search   │
│ R  │  [03] Validate    ─ Source review studio, OCR/ASR validation, report facts        │
│ A  │  [04] Directory   ─ Wellbore directory, search radius, platform component health │
│ I  │  [05] Evaluate    ─ Model readiness, qualification gates & telemetry dossier      │
│ L  │                                                                                   │
├────┴───────────────────────────────────────────────────────────────────────────────────┤
│ FOOTER: System Status · Provenance Tags · Prototype Disclaimers                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Comprehensive Page-by-Page Specifications

---

### Unauthenticated: Landing & Authentication View

- **Location / Component**: `frontend/src/App.tsx` (`Landing` component)
- **Purpose**: Welcoming engineers/reviewers, establishing the subsurface observatory aesthetic, and connecting securely using a memory-only local access token.

#### Key Features & UI Sections:
1. **Depth Ruler Marginalia**: Vertical geological depth ticks on the left margin (`1,800 m`, `2,000 m`, `2,141 m`, etc.) creating the observatory atmosphere.
2. **Hero Mission Statement**: 
   - Headline: *"What one well teaches, the next should know."*
   - Explanatory subtitle and feature matrix previewing plates `00` through `04`.
3. **Platform Connection Form (`#auth-form`)**:
   - Token Input: Password input requiring $\ge 16$ characters (`#access-token`). Token remains strictly in memory; never persisted to `localStorage`.
   - Submit Action: Dispatches parallel status and wellbore fetch requests.
   - Simulation Disclaimer: Explicit notice noting synthetic rehearsal status without live eRTMAC feeds.

#### APIs & Backend Integration:
- `GET /api/v1/status` (Validates token, loads environment and component states)
- `GET /api/v1/wells` (Fetches initial well list and selects default active well e.g. `SYN-A`)

---

### Persistent Shell & Context Bar

- **Location / Component**: `frontend/src/App.tsx` (`ContextBar`, `nav-rail`, shell wrapper)
- **Purpose**: Ensures the engineer always knows the active operational context, depth position, data freshness, and transport layer without navigating away.

#### Key Elements:
1. **Nav Rail**:
   - Logo Mark (`N`) with tooltip.
   - Navigation Buttons with plate numbers (`00` to `05`) and custom SVG icons (`IconObserve`, `IconExplore`, `IconInvestigate`, `IconValidate`, `IconDirectory`, `IconEvaluate`).
   - Disconnect Action (`IconDisconnect`) to clear state and return to Landing.
2. **Context Header Chips**:
   - `Well`: Active wellbore ID (e.g. `SYN-A` in Mineral Teal).
   - `Basin`: Geological basin name (e.g. `Upper Assam Basin`).
   - `Coords`: Latitude & Longitude in 4-decimal precision.
   - `Mode`: `SYNTHETIC` (Ochre dot) or `LIVE` (Teal pulsing dot).
   - `Env`: Current deployment tier (`LOCAL`, `DEV`, `PROD`).
   - `Transport Badge`: Indicates real-time protocol: `⚡ WebSocket` (active bidirectional stream) or `↺ HTTP` (polling fallback).
   - `Datasets`: Active fixture or authorized dataset identifier.

---

### Plate 00: Observe — The Live Well Desk

- **Route / View ID**: `operations`
- **Location / Files**: `frontend/src/Operations.tsx`, `frontend/src/operations.css`
- **Target Persona**: Drilling Rig Engineer, eRTMAC Operations Specialist, Shift Supervisor.
- **Purpose**: Real-time telemetry monitoring, replay simulation control, forward-drilling lookahead (100 m interval), and evidence-backed alert management.

#### Primary Layout & Sections:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [00] OBSERVE  ─  "Before the next interval."               [SIMULATED · NOT LIVE eRTMAC]
├────────────────────────────────────────────────────────────────────────────────────────┤
│ REPLAY PANEL: Session Selector · Speed (0.1x / 1x / 2x) · Advisory Cap · [+ New Replay]│
├───────────────────────┬───────────────────────────────┬────────────────────────────────┤
│ MEASURED DEPTH READOUT│ RECEIPT & STREAM STATUS       │ HISTORICAL LOOKAHEAD           │
│ 2,030 m MD            │ Fresh Sample / WebSocket      │ 100 m horizon · SYN-F1         │
│ Datum: synthetic_ref  │ Step 2/4 · Paused             │ ML Risk: unavailable (no model)│
├───────────────────────┴───────────────────────────────┴────────────────────────────────┤
│ REPLAY CONTROLS (Engineers): [▶ Next Depth Step] [▷ Play Replay] [⏸ Pause] [↺ Reset]  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ALERT BUDGET: Issued Advisories / Cap · Suppressed Alert Digest (Safety bypass enabled)│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ EVIDENCE-BACKED ALERTS LIST:                                                           │
│ ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ ⚠️ MUD LOSS INCIDENT · Safety Critical · Revision 3 · Seen 4 ticks                  │ │
│ │ Supporting Evidence: SYN-B (MD 2,040-2,055m -> mapped 2,030-2,045m)                │ │
│ │ "Severe partial losses (35 bbl/hr) upon entering Tipam sandstone..." (p.14)        │ │
│ │ Decision Actions: [Acknowledge] [Review] [Resolve] [Dismiss]                       │ │
│ │ Feedback Form: Action Taken, Observed Outcome, Rationale                           │ │
│ │ Audit Trails: Decision History & Feedback History                                  │ │
│ └────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Key Workflows & Features:
1. **Replay Engine & Telemetry Stream**:
   - WebSocket connection (`/api/v1/replay-sessions/:id/stream`) with 6-second watchdog timer and automatic HTTP reconnect fallback.
   - Stepping depth progression (`2029 m` $\to$ `2030 m` $\to$ `2031 m` $\to$ `2141 m`).
   - Replay speed selection (`0.1×` 20s/step, `1×` 2s/step, `2×` 1s/step).
2. **Alert Budgeting**:
   - Configurable low-priority advisory cap per 12-hour shift (0, 1, 2, 3, 5).
   - Safety-critical bypass: Kick, blowout, and safety-critical alerts are *never* suppressed.
   - Suppressed advisories ledger with mapped depth, source well, and report page.
3. **Alert Action & Human Decision Protocol**:
   - State transitions: `NEW` $\to$ `ACKNOWLEDGED` $\to$ `UNDER_REVIEW` $\to$ `RESOLVED` / `DISMISSED` $\to$ `REOPEN`.
   - Every action requires a documented `rationale` ($\ge 3$ characters) and version locking.
   - Engineer Feedback recording with observed outcome tracking (`incident_observed`, `no_incident_observed`, `unknown`).
4. **Stale Data Guard**: Highlights telemetry in ochre when sample age exceeds 15 seconds.

#### APIs & Backend Integration:
- `GET /api/v1/replay-sessions`
- `POST /api/v1/replay-sessions` (creates replay with scenario, speed, advisory cap)
- `GET /api/v1/replay-sessions/:id` (snapshot polling)
- `POST /api/v1/replay-sessions/:id/control` (`step`, `resume`, `pause`, `reset`)
- `POST /api/v1/alerts/:id/actions` (transition lifecycle with rationale)
- `POST /api/v1/alerts/:id/feedback` (feedback capture)
- `WS /api/v1/replay-sessions/:id/stream`

---

### Plate 01: Explore — The Offset Atlas & Subsurface Canvas

- **Route / View ID**: `intelligence`
- **Location / Files**: `frontend/src/Intelligence.tsx`, `frontend/src/ExplorationExtras.tsx`, `frontend/src/OffsetBrief.tsx`, `frontend/src/exploration.css`, `frontend/src/intelligence.css`
- **Target Persona**: Geologist, Subsurface Specialist, Drilling Engineer, Well Planner.
- **Purpose**: Multidimensional offset well comparison, spatial mapping, geological depth tracking, pore pressure envelopes, response networks, and hypothetical location planning.

#### Subviews & Integrated Panels:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [01] EXPLORE  ─  "Nearby is a starting point."                       NO PREDICTIVE MODEL│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ATLAS CONTROLS: Active Wellbore · Reviewed Formation · Proximity Basis · Radius Slider │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ INTERACTIVE LEAFLET MAP                   │ OFFSET WELL INDEX (Ranked Analogue List)   │
│ - Surface wellhead & candidate pins       │ - Well name & distance (km)                │
│ - Radius boundary circle                  │ - Similarity Score (0-100 breakdown)       │
│ - Click to drop planning pin              │ - Formation match status                   │
├───────────────────────────────────────────┴────────────────────────────────────────────┤
│ CITED OFFSET BRIEF: [Prepare One-Page Offset Brief] -> Printable A4 Shift Dossier      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ FORMATION-RELATIVE COMPARISON PANEL:                                                   │
│ - Bottomhole horizontal separation calculation & true-north survey status              │
│ - Score explanation (formation match, MD-thickness ratio, missing components)          │
│ - Approved Historical Incidents Table (Historical MD vs Mapped Active MD via TVD)      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ CITED DEPTH REGISTER (Synchronized Multi-Lane Canvas):                                 │
│ [Ruler / MD] ──── Formation Lanes ──── Incidents (Click to open) ──── ROP ──── Torque  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PRESSURE RECORD & MUD WINDOW:                                                          │
│ - Pore pressure, fracture gradient, mud weight, ECD envelope with citations            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ APPROVED KNOWLEDGE SEARCH:                                                             │
│ - Modes: Exact Terms (Full-Text) / Related Meaning (Local Semantic Embeddings)         │
│ - Filters: Hazard type, Depth MD from/to, Selected formation only                      │
│ - Search results linking directly to Case Files and Source Excerpts                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ RESPONSE NETWORK (MitigationGraph):                                                    │
│ Event / Formation ──> Reported Response ──> Recorded Effectiveness ──> Cited Case      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ OPERATIONS LEDGER & ASSUMPTION DESK:                                                   │
│ - Fishing & cementing case outcomes (n < threshold marked "insufficient")              │
│ - Assumption Desk: User-entered Rig-Day Rate -> Illustrative NPT Exposure Calculation  │
│ - Upper Assam Formation Name Reference Table & regional geological source link         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PLANNING DESK (PlanningPanel):                                                         │
│ - Drop pin on map -> Real-time offset hazard aggregation within radius                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ CASE FILE DRAWER / MODAL:                                                              │
│ - Narrative spine: Before / Onset / Response / Outcome / Reported NPT / Quality Issues│
│ - Direct citations & Raw OCR source text preview                                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Detailed Sub-Components in Explore:
1. **Interactive Well Map (`WellMap`)**:
   - Leaflet-powered canvas centered on active well coordinates.
   - Draws dynamic latitude/longitude reference gridlines, surface radius buffer, and marker pins.
   - Supports interactive map clicking to drop a hypothetical well point for the Planning Desk.
2. **One-Page Offset Brief (`OffsetBrief`)**:
   - Collates active well context, target formation, offset incidents, mud window bounds, and cited report references into a printable A4 technical brief (`window.print()`).
3. **Multi-Lane Depth Track (`DepthTrack`)**:
   - SVG visualization sharing a unified Measured Depth axis.
   - Synchronizes 4 vertical lanes: *Formations*, *Incident markers* (interactive), *ROP ($m/h$)*, and *Torque ($kN\cdot m$)*.
4. **Pore Pressure & Mud Window (`MudWindow`)**:
   - SVG depth envelope plotting Pore Pressure, Fracture Gradient, Mud Weight, and ECD ($ppg$).
   - Tooltips show exact page citations for both pressure tests and daily mud reports.
5. **Mitigation Graph (`MitigationGraph`)**:
   - Displays historical response networks: `Event / Formation` $\to$ `Reported Response` $\to$ `Recorded Effectiveness Counts` with direct links to case dossiers.
6. **Assumption Desk & Operations Ledger (`OperationalEvidence`)**:
   - Special operations breakdown (fishing, cementing, sidetracks) with strict small-sample safeguards.
   - User-defined rig day rate calculation multiplying documented NPT hours into illustrative exposure in INR or USD without hardcoding proprietary OIL rates.
   - Upper Assam regional formation alias dictionary.
7. **Planning Desk (`PlanningPanel`)**:
   - Allows exploration of un-drilled locations by calculating nearby hazard frequency from the reviewed archive.
8. **Case File & Source Drawer (`record` / `source` state)**:
   - Deep-dive panel displaying complete incident narrative, NPT duration, recorded mitigations, quality warnings, and verbatim OCR/ASR passage text.

#### APIs & Backend Integration:
- `GET /api/v1/intelligence/wellbores`
- `GET /api/v1/wellbores/:id/trajectory`
- `GET /api/v1/wellbores/:id/analogues?target_interval_id=...&radius_km=...&proximity_basis=...`
- `GET /api/v1/wellbores/:id/bottomhole-proximity?offset_wellbore_id=...`
- `GET /api/v1/wellbores/:id/offset-brief`
- `GET /api/v1/wellbores/:id/depth-track`
- `GET /api/v1/wellbores/:id/mud-window`
- `GET /api/v1/search-capabilities`
- `POST /api/v1/query` (Full-text & local semantic vector search)
- `GET /api/v1/events/:id` & `GET /api/v1/events/:id/evidence/:passage_id`
- `GET /api/v1/knowledge/mitigation-links`
- `GET /api/v1/knowledge/special-operations`
- `POST /api/v1/knowledge/npt-exposure`
- `GET /api/v1/reference/assam-formations`
- `POST /api/v1/planning/offset-picture`

---

### Plate 02: Investigate — Questions with a Paper Trail

- **Route / View ID**: `questions`
- **Location / Files**: `frontend/src/ReportQuestions.tsx`
- **Target Persona**: Drilling Engineer, Reviewer, Technical Investigator.
- **Purpose**: Direct inspection of structured report questions mapped to reviewed document passages. Guarantees no hallucinated answers by enforcing explicit abstentions and conflict indicators.

#### Primary Layout & Sections:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [02] INVESTIGATE  ─  "Questions with a paper trail."                                   │
├────────────────────────────────────────┬───────────────────────────────────────────────┤
│ QUESTION INDEX                         │ REVIEWED ANSWER PANE                          │
│ ┌────────────────────────────────────┐ │                                               │
│ │ 01 / FORMATION · verified          │ │ Status: [ANSWERED / DISPUTED / UNANSWERED]    │
│ │ "What was the top of Barail sand?" │ │                                               │
│ │ [READY]                            │ │ Answer Statement:                             │
│ ├────────────────────────────────────┤ │ "Barail sandstone top confirmed at 2,141 m MD│
│ │ 02 / CASING · needs review         │ │ with 12.2 ppg mud."                           │
│ │ "Was 9-5/8 casing set in Tipam?"   │ │                                               │
│ │ [CONFLICT_BLOCKED]                 │ │ Reviewer Reason / Conflict Notice:            │
│ └────────────────────────────────────┘ │ "Verified against DDR #24 mud log."          │
│                                        │                                               │
│                                        │ CITED SOURCE PASSAGES:                        │
│                                        │ ┌───────────────────────────────────────────┐ │
│                                        │ │ "Drilled 8-1/2 hole to 2141m. Entered     │ │
│                                        │ │ Barail top..."                            │ │
│                                        │ │ synthetic_ddr.pdf · page 12 · text v2     │ │
│                                        │ │ [OCR image checked]                       │ │
│                                        │ └───────────────────────────────────────────┘ │
└────────────────────────────────────────┴───────────────────────────────────────────────┘
```

#### Key Workflows & Features:
1. **Question List**: Filterable catalog of reviewer-verified questions tagged with category, qualification state, and resolution status.
2. **Conflict & Abstention Handling**: If multiple report sources disagree, status displays `DISPUTED` with the competing claims rather than picking a single synthetic guess.
3. **Passage Citation Block**: Every answer quotes the exact text, file name, page number, text version, and whether the underlying OCR image was human-verified.

#### APIs & Backend Integration:
- `GET /api/v1/report-facts/questions`
- `POST /api/v1/report-facts/ask-question` (body: `{ question_id }`)

---

### Plate 03: Validate — The Source Review Studio

- **Route / View ID**: `documents`
- **Location / Files**: `frontend/src/Documents.tsx`, `frontend/src/ReportFacts.tsx`, `frontend/src/VoiceMemo.tsx`, `frontend/src/report-facts.css`, `frontend/src/voice-memo.css`
- **Target Persona**: Data Steward, Domain Expert, Senior Drilling Engineer, Report Reviewer.
- **Purpose**: End-to-end ingestion and governance studio for drilling reports, completion logs, DDRs, and voice memos. Enables reviewers to inspect OCR/ASR extracts, correct field mappings, record rationale, and adjudicate source contradictions.

#### Layout Architecture:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [03] VALIDATE  ─  "The authority is the page."                      Role: REVIEWER     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TABS: [Document Review Queue] | [Report Facts Ledger] | [Voice Memo Studio]            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ THREE-COLUMN WORKBENCH (In Document Review):                                           │
│ ┌──────────────────────┬───────────────────────────────┬─────────────────────────────┐ │
│ │ 1. INGESTION QUEUE   │ 2. PAGE / OCR / AUDIO VIEWER  │ 3. EXTRACTION EDITOR        │ │
│ │ - Upload PDF/DDR/WAV │ - PDF Page Render / Canvas    │ - Event Type & Quote        │ │
│ │ - Document List      │ - Raw Text vs OCR Output      │ - Start/End Depth & Datum   │ │
│ │ - Ingest Status      │ - Confidence Score (94%)      │ - Severity & Formation      │ │
│ │ - Origin & Auth Flags│ - Voice Audio Player (if memo)│ - Mitigation & Outcome      │ │
│ │                      │                               │ - Rationale & Decision:     │ │
│ │                      │                               │   [Approve] [Correct]       │ │
│ │                      │                               │   [Reject]  [Adjudicate]    │ │
│ └──────────────────────┴───────────────────────────────┴─────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Detailed Workbenches & Sub-modules:
1. **Document Review Workbench (`Documents.tsx`)**:
   - Upload Dropzone supporting PDF completion reports, daily drilling logs, and audio recordings.
   - Visual Page & OCR text viewer showing confidence percentage and unit interpretations.
   - Form-level Candidate Extractor allowing editing of 13 granular fields: `event_type`, `quote`, `description`, `depth_start`, `depth_end`, `depth_unit`, `depth_axis`, `depth_datum`, `formation_name`, `severity`, `mitigation`, `outcome`, and `npt_hours`.
   - Onset Basis Selector: `exact_timestamp`, `shift_interval`, `depth_window`, `unspecified`.
   - Audit trail tracking reviewer identity, action, timestamp, and mandatory written rationale.
2. **Sentence-Level Report Facts Ledger (`ReportFacts.tsx`)**:
   - Granular fact workbench where reviewers approve atomic facts extracted from passages without blanket-approving entire multi-page documents.
   - Links approved facts to searchable question templates.
   - Fact withdrawal action preserving the audit log.
3. **Voice Memo Capture & Local ASR Studio (`VoiceMemo.tsx`)**:
   - Microphone audio recording with WebM/Opus or MP4 codecs (60s timer cap).
   - Strict 30-day retention consent agreement checkbox.
   - Multi-language selection (English, Hindi, Assamese).
   - Integration with local Whisper ASR for transcription drafting.
   - Converts reviewed transcripts into standard reviewable document candidates.

#### APIs & Backend Integration:
- `GET /api/v1/documents` & `GET /api/v1/documents/:id`
- `POST /api/v1/documents` (Multipart file upload)
- `POST /api/v1/documents/:id/review` (Records `approve`, `correct_and_approve`, `reject`, `escalate`)
- `POST /api/v1/voice-memos` (Multipart audio upload with consent and metadata)
- `GET /api/v1/report-facts/documents/:id` & `POST /api/v1/report-facts`
- `POST /api/v1/report-facts/:id/withdraw`
- `GET /api/v1/me` (Identity, role, permissions, extraction engine)

---

### Plate 04: Directory — Well Directory & Platform Status

- **Route / View ID**: `foundation`
- **Location / Component**: `frontend/src/App.tsx` (`FoundationView`)
- **Target Persona**: All Users, System Administrators.
- **Purpose**: System health inspection, well catalog navigation, active well switching, and surface proximity radius configuration.

#### Primary Layout & Sections:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [04] DIRECTORY  ─  "Well directory & platform"                       SYNTHETIC · LOCAL │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PLATFORM COMPONENT STATUS GRID:                                                        │
│ ┌──────────────────────┬──────────────────────┬──────────────────────┐                 │
│ │ Database: [READY]    │ Spatial: [READY]     │ Vector: [READY]      │                 │
│ ├──────────────────────┼──────────────────────┼──────────────────────┤                 │
│ │ Ingestion: [READY]   │ Replay: [READY]      │ Prediction: [ABSENT] │                 │
│ └──────────────────────┴──────────────────────┴──────────────────────┘                 │
├──────────────────────────────────────┬─────────────────────────────────────────────────┤
│ WELL SELECTOR (Loaded Wellbores)     │ NEARBY WELLS DISCOVERY                          │
│ - Dropdown selector with Data Kind   │ - Search radius slider (1 to 25 km)             │
│ - Active Well Details Card:          │ - Proximity list showing calculated surface km │
│   * External ID: SYN-A               │ - Real-time filtering                           │
│   * Basin: Upper Assam               │                                                 │
│   * Coordinates: 27.4728°N 94.9120°E │                                                 │
│   * Data Kind: SYNTHETIC_DEMO        │                                                 │
└──────────────────────────────────────┴─────────────────────────────────────────────────┘
```

#### Key Workflows & Features:
1. **Platform Component Monitor**: Shows live status (`READY`, `ABSENT`, `DEGRADED`, `ERROR`) and detail strings for Database, Spatial (PostGIS), Vector (pgvector/semantic models), Ingestion pipeline, Replay worker, and Prediction engine.
2. **Active Well Switching**: Changes the active global wellbore, propagating updates across Explore, Observe, and Investigate workspaces.
3. **Surface Distance Radius Slider**: Interactively recalculates nearby wells using Euclidean/spatial surface distance.

#### APIs & Backend Integration:
- `GET /api/v1/status`
- `GET /api/v1/wells`
- `GET /api/v1/wells/nearby?active_well_id=...&radius_km=...`

---

### Plate 05: Evaluate — Model Assurance & Telemetry Dossier

- **Route / View ID**: `prediction`
- **Location / Files**: `frontend/src/Prediction.tsx`, `frontend/src/TelemetryDossier.tsx`
- **Target Persona**: Machine Learning Engineer, Subsurface Technical Auditor, Rig Superintendent.
- **Purpose**: Model readiness assessment, qualification gate evaluation, feature contract auditing, and historical telemetry screening dossier.

#### Primary Layout & Sections:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [05] EVALUATE  ─  "Evidence before confidence."                      [NO TRAINED MODEL]│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ MODEL READINESS METRICS:                                                               │
│ ┌───────────────────┬───────────────────┬───────────────────┬────────────────────────┐ │
│ │ Research Target   │ Risk Score        │ Held-Out Metrics  │ Historical Inventory   │ │
│ │ Mud loss (100m)   │ — (Unavailable)   │ — (Uncalibrated)  │ 4 approved / 2 wells   │ │
│ └───────────────────┴───────────────────┴───────────────────┴────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ARCHIVE CAPABILITY & INVENTORY NOTE:                                                   │
│ "Assessment of current historical data volume versus statistical training requirements"│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ QUALIFICATION GATES (Prerequisites before model deployment):                          │
│ 1. Minimum 30 independent physical wells with reviewed mud-loss onsets.                │
│ 2. Unambiguous depth datum & sensor quality flags on all training channels.            │
│ 3. Explicit held-out cohort calibration with brier-score verification.                 │
│ [Proposed Feature Contract]: List of 18 pre-anchor channels (ROP, WOB, Torque, Flow...)│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ HISTORICAL TELEMETRY QUALITY DOSSIER (TelemetryDossier):                               │
│ - Telemetry Source Selector (Dataset / External ID)                                    │
│ - Screening Decision: [PASSED / BLOCKED / PENDING_REVIEW]                              │
│ - Quality Review Flags: Units reviewed, Timezone reviewed, Datum reviewed              │
│ - Wellbore Screening Stats: Good complete %, Active drilling %, Largest gap, ROP range │
│ - Screen Thresholds & Quality Sensor Counts                                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Key Workflows & Features:
1. **Model Governance & Ethics Gates**: Enforces rigorous scientific standards by displaying transparent gate requirements before any ML prediction can be deployed or shown on the rig desk.
2. **Historical Telemetry Screening Dossier (`TelemetryDossier`)**:
   - Inspects raw historical sensor streams for gaps, negative spikes, and unverified units.
   - Calculates good-channel completeness ratios and active drilling fractions.
   - Flags data blockers prior to any potential training inclusion.

#### APIs & Backend Integration:
- `GET /api/v1/prediction/readiness`
- `GET /api/v1/telemetry-sources`
- `GET /api/v1/telemetry-sources/:id/quality-dossier`

---

## 3. Design System & Visual Grammar

NWIS uses a curated **Subsurface Observatory** design language tailored for scientific rigor, visual density, and clarity under challenging lighting or high-zoom conditions:

### Color Palette Tokens

| Token Name | Hex Code | Purpose & Semantic Application |
|---|---|---|
| `--chalk` | `#F2F0E9` | Main workspace canvas and background paper |
| `--survey-paper` | `#FFFDF8` | Source cards, excerpts, printable brief sheets |
| `--basalt-ink` | `#182B34` | Primary high-contrast text, borders, axis lines |
| `--slate` | `#5F7075` | Secondary text, inactive layers, axis tick marks |
| `--mineral-teal` | `#176A70` | Primary actions, active well selection, verified data |
| `--teal-glow` | `#33B3A6` | Active indicators, live sensor status, focus highlights |
| `--ochre` | `#B47832` | Lookahead annotations, historical events, replay mode |
| `--signal-red` | `#AD4C3E` | Safety-critical hazards, kicks, unresolved conflicts |
| `--quiet-rule` | `#CDD4D1` | Delicate gridlines, depth rulers, panel dividers |

### Typography

- **Display & Headings**: High-character editorial serif (Georgia / Times New Roman / Palatino fallback) for screen titles and formation names.
- **UI & Controls**: Clean, highly legible sans-serif (`Inter`, `-apple-system`, `sans-serif`) at standard sizes ($11\text{px}$ to $14\text{px}$).
- **Numerals & Metrics**: Strict tabular monospaced font (`ui-monospace`, `Menlo`, `Monaco`, monospace) for Measured Depth, TVD, timestamps, coordinates, sensor readings, and ID hashes.

---

## 4. Role-Based Access Control (RBAC) Matrix

| Workspace / Capability | Viewer | Reviewer | Engineer | Administrator |
|---|:---:|:---:|:---:|:---:|
| View Live Telemetry & Alerts | ✅ | ✅ | ✅ | ✅ |
| Replay Control (Step / Pause / Play) | ❌ | ❌ | ✅ | ✅ |
| Create New Replay Session | ❌ | ❌ | ✅ | ✅ |
| Alert Actions (Acknowledge / Review) | ❌ | ❌ | ✅ | ✅ |
| Alert Decision Feedback | ❌ | ❌ | ✅ | ✅ |
| Explore Map & Depth Registers | ✅ | ✅ | ✅ | ✅ |
| Search Knowledge Base & Cases | ✅ | ✅ | ✅ | ✅ |
| Run Planning Scenarios | ✅ | ✅ | ✅ | ✅ |
| Upload Documents / Voice Memos | ❌ | ✅ | ❌ | ✅ |
| Approve / Correct Extracted Candidates| ❌ | ✅ | ❌ | ✅ |
| Withdraw Report Facts | ❌ | ✅ | ❌ | ✅ |
| Inspect Model Readiness & Dossiers | ✅ | ✅ | ✅ | ✅ |

---

## 5. File Structure Reference Guide

```
frontend/src/
├── main.tsx                  # React DOM root entry point
├── App.tsx                   # Top-level shell, Navigation Rail, ContextBar, Landing, Directory View
├── Operations.tsx            # [Plate 00] Live Well Desk, Telemetry Replay, Alert Feed & Budget
├── Intelligence.tsx          # [Plate 01] Offset Atlas, Map, Analogue Index, Search & Case Drawer
├── ExplorationExtras.tsx     # [Plate 01 Subviews] DepthTrack, MudWindow, MitigationGraph, PlanningPanel, OpsLedger
├── OffsetBrief.tsx           # [Plate 01 Subview] One-page printable technical offset brief
├── ReportQuestions.tsx       # [Plate 02] Question answering workbench with passage citations
├── Documents.tsx             # [Plate 03] Document Ingestion, 3-column OCR Review & Extraction Workbench
├── ReportFacts.tsx           # [Plate 03 Subview] Atomic sentence-level fact review & question mapping
├── VoiceMemo.tsx             # [Plate 03 Subview] Audio capture, 30-day retention consent & local ASR
├── Prediction.tsx            # [Plate 05] ML readiness metrics & qualification gate audits
├── TelemetryDossier.tsx      # [Plate 05 Subview] Historical telemetry source screening dossier
├── styles.css                # Global design system, typography, color tokens, layout grids
├── operations.css            # Plate 00 specific styles (replay panel, alert cards)
├── intelligence.css          # Plate 01 specific styles (atlas controls, Leaflet map)
├── exploration.css           # Plate 01 sub-panel styles (depth tracks, mud window, networks)
├── report-facts.css          # Plate 02/03 fact workbench styles
└── voice-memo.css            # Plate 03 voice recording and audio player styles
```

---

## 6. Development & Testing Cheatsheet

- **Dev Server**: `npm run dev` in `frontend/` (runs on `http://localhost:5173`)
- **Backend API**: Proxied via Vite to `http://localhost:8000`
- **Smoke Tests**:
  - UI Smoke: `node frontend/ui-smoke.mjs`
  - Intelligence Smoke: `node frontend/intelligence-smoke.mjs`
  - Operations & Replay: `node frontend/operations-smoke.mjs`
  - Semantic Search: `node frontend/semantic-smoke.mjs`
  - WebSocket Stream: `node frontend/websocket-smoke.mjs`
