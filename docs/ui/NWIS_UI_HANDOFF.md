# NWIS — future-state UI/UX blueprint

**Purpose:** a single design-and-implementation brief for agents building the ideal NWIS interface. **Product:** Nearby Wells Intelligence System for Oil India Limited. **Status:** target-state vision, not an assertion that every feature or data connection already exists.

## 1. Product premise and assumptions

NWIS is the drilling team's institutional memory beside eRTMAC. It joins live drilling telemetry to authorized historical well reports, trajectories, geology and operational events; compares the current well with relevant offsets; forecasts hazards; and presents evidence-backed options for an engineer to evaluate. It never controls the rig or replaces the engineer.

For this design exercise, assume the following are solved: OIL has authorized the data and interface; well identities, depth datums, units and time zones are reconciled; historical documents and events are reviewed; eRTMAC telemetry is flowing with quality metadata; prediction models have passed held-out-well evaluation and calibration; role/rights policy is in place. Design a **fully realized product** around that state. Do not limit the UI to today's prototype routes or synthetic fixtures.

The UI should let an engineer answer four questions in under a minute:

1. Where are we now, and what is changing?
2. What happened in genuinely comparable wells at this formation/depth?
3. What might happen next, with what confidence and lead distance?
4. What evidence and assumptions support each option?

## 2. Creative direction — “The Living Well Atlas”

Imagine a geological field notebook made interactive: pale paper, deep ink, restrained mineral greens and copper, precise depth rulers, cartographic linework and annotated source excerpts. It should feel authored for drilling—not like a generic AI dashboard, stock fintech UI or sci-fi control room.

**The signature visual grammar:** horizontal geography (wells on the map) meets vertical geology (formation/depth lanes) meets time (telemetry/replay). A selected well, interval or event remains the same selected object across all three views. This cross-view continuity is the product's distinctive interaction.

References for interaction patterns, **not visual copying**: [BGS GeoIndex](https://mapapps.bgs.ac.uk/geoindex/home.html) for borehole/geology navigation; [Copernicus Browser](https://browser.dataspace.copernicus.eu/) for A/B comparison and layered exploration; [Global Fishing Watch](https://globalfishingwatch.org/platform/map) for trajectory/time interaction; [Open Targets](https://platform.opentargets.org/) for evidence drill-down; [Felt Energy Dashboard](https://www.felt.com/gallery/energy-company-dashboard) for map-led analysis.

### Visual system starting point

| Element | Direction |
|---|---|
| Canvas | Warm off-white `#F5F3EC`, paper surface `#FCFBF7`, dark ink `#222A27`; avoid pure-white card grids |
| Primary accent | Deep forest `#36594C`, with lighter chart tints; use copper `#A66B42` for annotation/attention |
| Hazard colors | A small, accessible categorical scale; severity uses label + icon/shape + color, never color alone |
| Type | Editorial serif for page titles and well/formation names; clean sans for UI; tabular mono for depth, timestamp, units and event IDs |
| Geometry | Hairline dividers, inset labels, map grids, index numbers, modest corners; no glass, neon glow or 3D decoration |
| Motion | Purposeful linked selection, drawer transitions, timeline scrub; 150–250 ms, reduced-motion equivalent |
| Imagery | Prefer maps, diagrams, rock/stratigraphy textures built as SVG/CSS. No AI-generated generic rigs or oilfield stock images |

Contrast and legibility win over the exact hex values. The design agent may refine the palette, but should preserve this restrained character and document the token set.

## 3. Roles and principal tasks

| Role | Typical context | Primary task |
|---|---|---|
| Drilling engineer | Office, large display | Monitor current well, investigate lookahead risks, compare offsets, document a decision |
| Rig-site engineer | Tablet/phone, constrained connection | Check current state and highest-priority alert, inspect evidence, acknowledge/hand over |
| Geologist | Desktop | Compare formation tops, lithology, pressure and well trajectories along a shared depth axis |
| Reviewer/data steward | Desktop | Validate extracted event/fact against source pages and maintain provenance |
| Supervisor | Desktop/tablet | See alert burden, decision trail, exposure trends and model/stream health |

Permission-dependent controls must be explicit. A viewer may inspect evidence, but only an authorized reviewer approves facts and only an authorized engineer records alert actions. Design both read and edit states.

## 4. Global information architecture

Use a compact primary nav with these destinations. A global well selector and source-status strip stay visible inside every operational workspace.

| Destination | Job |
|---|---|
| **Shift desk** | Live state, lookahead forecast, alerts, quick evidence |
| **Well atlas** | Map, offsets, trajectory-aware proximity, planning locations |
| **Subsurface** | Formation-aligned cross-well depth tracks and engineering parameters |
| **Knowledge** | Search, cited case files, mitigation/outcome patterns |
| **Evidence room** | Report ingestion, OCR/ASR review, approval queue, source pages |
| **Analysis** | Historical NPT, alert performance, model evaluation and data quality |
| **Handover** | A signed, printable/shareable shift brief and decision history |

Do not duplicate the same map/chart on every page. The nav moves between *tasks*, while selected well/formation/time range persists. Every page has a clear object breadcrumb: `Field / Well / Wellbore / Formation or event`.

### Persistent context strip

Show: field + wellbore name; current MD and TVD with reference; current formation; data mode (`LIVE eRTMAC`, `REPLAY`, `HISTORICAL`); last observation and receipt times; connection freshness; model version/status. The strip collapses to two lines on mobile. Live and replay are visually distinct throughout the product.

## 5. Flagship screens

### 5.1 Shift desk — a live, readable decision surface

**Primary question:** “What is happening now, and what should I inspect before we enter the next interval?”

Desktop wireframe (content hierarchy, not pixel layout):

```text
┌ Field / Well / Wellbore ─ MD 2,030 m KB ─ Formation ─ LIVE ─ updated 8 s ago ┐
│  Current state            Lookahead: next 100 m       Alert priority           │
│  ROP / WOB / torque       Formation + event markers   2 active / 1 watching    │
├───────────────────────────────┬─────────────────────────────────────────────────┤
│ Live parameter trends         │ Selected risk / historical alert              │
│ + sensor quality and gaps     │ why now · predicted horizon · uncertainty      │
│                               │ comparable wells · cited events · action log   │
├───────────────────────────────┴─────────────────────────────────────────────────┤
│  Source status · decision history · open full atlas / subsurface / handover      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

Forecast cards exist for mud loss, kick/overpressure, stuck pipe, torque and cementing only when each hazard model is validated for this well/formation. Show predicted probability **and** confidence/calibration separately, forecast horizon in metres/time, trend versus prior observation, model scope and an “out of distribution” warning when appropriate. No confidence badge should be mistaken for risk. A hazard with insufficient input becomes “Cannot assess” with the reason.

The lookahead strip combines formation boundaries, casing points, reviewed offset incidents and forecast intervals. Zoom to 50/100/200 m. Hover/focus reveals exact MD/TVD, source well and citation. Clicking an event opens its case file without changing the live-well context.

Telemetry lines have synchronized cursor, original units, quality flags, gap/stale bands and rig-state shading. A line discontinuity is a data gap, not interpolated certainty. A compact map preview links to the atlas, but the shift desk prioritizes depth and evidence.

### 5.2 Well atlas — geography with subsurface truth

**Primary question:** “Which wells are relevant to this target, and why?”

Full-height map with left search/filter rail and right offset inspector. Use subdued basemap styling, wellhead markers, optionally reviewed trajectories/terminal points, radius or polygon selection and formation/hazard filters. A selected well highlights in map, list and depth strip simultaneously.

Two selectable proximity modes: **surface wellhead** and **reviewed trajectory/target-depth proximity**. Report each distance with its basis. For deviated wells, show wellhead and terminal/selected-depth position as distinct symbols connected by the reviewed path. Where positional uncertainty exists, display it as a separate layer; never present endpoint distance as collision clearance. Each offset card explains comparability: geology/formation match, depth overlap, trajectory, drilling environment, available evidence and missing data. A similarity score is explainable, not a risk score.

Provide a “Compare wells” tray (2–4 pinned offsets) and a **planning point** mode: choose a proposed location and target formation to preview nearby wells and documented hazards. Do not silently switch the active well when exploring a hypothetical point. Shareable state should preserve filters, map extent and selected wells without leaking restricted source text.

### 5.3 Subsurface — the distinctive NWIS screen

**Primary question:** “Where do the offset experiences land on our current depth/formation frame?”

Use a multi-lane synchronized depth canvas, not independent mini charts:

```text
Depth MD │ Formation/lithology │ Active parameters │ Offset A │ Offset B │ Events
2,000 m  │ Barail             │ ROP · torque       │ …        │ …        │ loss ●
2,100 m  │                    │ MW · ECD           │ …        │ …        │ stuck ◆
2,200 m  │ Tipam              │ pressure envelope │ …        │ …        │ casing ┃
```

Offer alignment by MD, TVD and reviewed formation-relative mapping; label the active mode and reference datum. Preserve source depth and mapped active depth together in a selected-event inspector. When alignment is ambiguous, show a hatched unresolved band and the exact cause. Do not draw a precise event point when the source only supports a broad or day-level interval. Let users brush a depth range once to filter the map, event list, telemetry and cases. A/B comparison may use synchronized side-by-side, overlay or swipe where legible. Use clear lane labels and axis ticks at all zoom levels.

The pressure view shows pore-pressure/fracture-gradient context, current mud weight and ECD with units, source and uncertainty, but never turns the visual into an automatic operating instruction. Casing and cementing markers sit on the same ruler.

### 5.4 Knowledge and case file — institutional memory with receipts

Search supports natural language and structured filters (field, well, formation, hazard, MD/TVD, time period, event outcome and source tier). The result card states the supported claim, source well, depth/formation, review status and citation. Group results by event/case instead of showing duplicate passages as independent incidents. Search has an explicit “No supported result” state.

Case file structure:

1. Event identity: well, formation, source depth/time, event type, mechanism and severity.
2. What was observed: short incident narrative, parameter signature and timeline leading into onset.
3. What was done: recorded mitigation(s), responsible record/source and duration.
4. What followed: outcome, NPT, uncertainty and whether effectiveness was observed or unassessed.
5. Why it is comparable: formation/depth/trajectory and parameter factors, with missing factors.
6. Source drawer: PDF page or memo transcript/audio, highlighted passage, document metadata, version and reviewer decision.

The source drawer is a central design element: click a citation and keep the case visible behind/alongside it. Support next/previous citation and a page number deep link. A mitigation graph can summarize recorded event → action → outcome links, but the UI must not infer causation from co-occurrence.

### 5.5 Alert centre — explain, act, learn

Alert list columns/filters: urgency, hazard, predicted interval, lead distance/time, status, affected well, evidence count, model/rule source and owner. An alert detail reveals **why now**, live sensor context, similar historical cases, model explanation/calibration, confidence and uncertainty, proposed checks/options, and full citations. Keep model-generated reasoning visually distinct from reviewed historical facts.

Lifecycle: new → acknowledged → under review → resolved/dismissed; reopening is explicit. Action requires rationale. Feedback records what the engineer actually did and observed; adjudication of a false alert is separate. Show suppressed low-priority alerts and the budget rule in a digest, while critical alerts bypass that budget. Notification cooldown is visible as a continuing episode, not duplicate cards.

### 5.6 Evidence room — human review as a polished workflow

Three-pane desktop layout: queue, source page and structured extraction form. On mobile/tablet use a stepper rather than squeezed columns. The original page is the authority; OCR/NLP/ASR are drafts. Align each extracted field with its quoted span. Inline validation surfaces unit, depth axis, datum, negation, formation name and conflicting values. Reviewers can correct, approve or reject with rationale and compare versions. A second reviewer/adjudicator state is available when the workflow requires it.

Voice memos use the same passage-review path: consent, language, transcript confidence, audio playback, corrected text and retention deadline are visible. Document and source rights are part of the provenance panel. Provide bulk triage only for safe actions such as assigning or filtering; no one-click mass approval of drilling events.

### 5.7 Analysis and model assurance

Show historical event frequency and NPT by formation/operation with denominator, sample count, coverage and source selection. Keep illustrative exposure separate from actual economic loss. Model panels report version, training population, applicable formations, held-out-well performance, calibration, lead distance, false-alert burden and drift. Let a supervisor compare versions and inspect an out-of-distribution slice. A trained model is not “healthy” merely because its API responds.

### 5.8 Handover and field-lite

Generate a one-page handover brief from selected active state: well/formation/MD, alerts and ownership, unresolved questions, top cited offset cases, telemetry freshness, decisions made this shift and next check. Every line has provenance or is clearly marked as an engineer note. The brief must print cleanly to A4 and retain source references.

Field-lite is a first-class compact route: context and freshness → highest-priority alert → one-line evidence → open case → permitted action. Text-first payload, optional charts/map on demand, large targets and graceful intermittent-network behavior. Offline/cached information shows the last synchronized timestamp. An action is not presented as server-confirmed until acknowledgement arrives.

## 6. Shared interaction and component system

Build these as reusable, typed components rather than page-specific ad hoc markup:

`WellContextHeader`, `SourceModeBadge`, `FreshnessIndicator`, `DepthValue`, `FormationBand`, `WellMapMarker`, `TrajectoryPath`, `SimilarityBreakdown`, `RiskForecast`, `ConfidenceIndicator`, `LookaheadTrack`, `TelemetryChart`, `EventMarker`, `CitationLink`, `SourceDrawer`, `ReviewDecision`, `AlertCard`, `DecisionHistory`, `DataQualityPanel`, `EmptyEvidence`, `ConflictNotice`, `FieldLiteCard`.

**DepthValue** always knows value, unit, MD/TVD axis, reference/datum and precision. **CitationLink** always resolves to a document/page/passage. **RiskForecast** carries hazard, horizon, probability, confidence/calibration, model version, freshness and applicability. **SourceModeBadge** distinguishes live, replay, historical, synthetic and staged public data. **SimilarityBreakdown** does not reuse the visual language of a risk probability.

Shared states for every data-bound component: loading, populated, no data, filtered-to-none, stale, partial quality, source conflict, access denied, network loss and service unavailable. Empty states should say what is missing and how to proceed, not simply “No data.”

## 7. Data and copy rules

- Units and axes are inseparable from measurements: `2,130 m MD (KB)` is useful; `2,130 m` alone may be misleading. Preserve source and normalized values when they differ.
- Use exact timestamps with timezone and observed-versus-received distinction. `LIVE` refers to the feed, not the age of an old offset event.
- Use “predicted probability” only for validated calibrated output; “historical occurrence” for counts; “similarity” for analogue ranking; “confidence” for data/model certainty. Never collapse them into one gauge.
- Approved, pending, rejected, conflict and withdrawn evidence have distinct text labels. Unknown is not zero and absence of an event is not proof of a risk-free interval.
- Recommendations are phrased as **options to consider/check**, show assumptions and evidence, and require engineer sign-off. Avoid imperative drilling instructions.
- Keep public analogues, OIL operational records and synthetic demos distinguishable even in an idealized product. A model result must disclose applicability outside its training population.

## 8. Responsive, accessibility and performance

Design desktop at 1440 px, tablet at 768 px and narrow mobile at 375 px. The multi-pane atlas/subsurface views may use task-specific mobile navigation, but must preserve selection and back-path. No horizontal page overflow. Touch targets at least ~44 px on field-critical controls. Charts and map markers need keyboard-accessible list/table equivalents. Focus order follows visual reading order; drawers close with Escape and restore focus. All controls have labels; state changes are announced appropriately. Meet WCAG AA contrast; reduced-motion and high-contrast modes should be intentional.

Render current context and alerts first; defer heavy map/3D/chart layers. Virtualize long well/event lists. A delayed or missing layer must not freeze the entire shift desk. Cache only permitted field data, show the age of cached values and purge on sign-out/retention policy. Print layouts for case files and handover remain legible in grayscale.

## 9. Agent deliverables and acceptance

Produce a design system page plus clickable prototypes or working frontend for these frames: (1) shift desk normal, (2) high-priority alert detail, (3) atlas with two offsets selected, (4) formation-aligned subsurface comparison, (5) case file with source drawer, (6) evidence review/conflict, (7) analysis/model assurance, (8) field-lite mobile, (9) A4 handover. Include loaded, stale, conflict, empty and permission-denied examples. Use realistic drilling terminology and **clearly labelled illustrative data** in design mockups; do not pass mock numbers into operational UI as real API values.

Recommended parallel ownership: one agent owns tokens/navigation/shared components; one owns shift desk + alerts; one owns atlas + subsurface; one owns evidence room + case file; one integration owner checks field-lite, handover, accessibility and data/copy rules. Shared component APIs should be agreed before parallel implementation so each screen does not invent a different depth or provenance badge.

Acceptance is not just visual similarity: a selected event must stay linked across map, depth and case; every quantitative claim must have a unit/basis; every historical claim must reach source evidence; live/replay and probability/similarity/confidence must remain visually distinct; an engineer can complete core tasks with keyboard or phone; and the interface remains coherent when data is stale, missing or conflicting.

## 10. Implementation translation for the current repository

The existing React/Vite frontend is in `frontend/src/`; its current route-like tabs are assembled in `App.tsx`. Existing feature modules include `Operations.tsx`, `Intelligence.tsx`, `Documents.tsx`, `ReportQuestions.tsx`, `Prediction.tsx`, `ExplorationExtras.tsx` and `OffsetBrief.tsx`. The backend lives in `backend/nwis/`, with current endpoints for maps, analogues, cited search, report review, replay alerts, telemetry screening and model readiness. Agents should use the present components as scaffolding, but this document describes the **target experience** and may require new backend contracts. Record every missing endpoint/data dependency explicitly; do not fake successful responses or treat a prototype capability as field validation.

The original user-authored UI/UX specification is a useful starting inventory, especially its map, case file, alert and field-lite concepts. This future-state brief expands the product into a coherent spatial–subsurface–temporal interaction system and gives agents one shared visual language.
