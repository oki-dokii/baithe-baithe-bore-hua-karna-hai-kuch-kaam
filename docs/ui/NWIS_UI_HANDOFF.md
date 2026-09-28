# NWIS — greenfield UI/UX specification

**Design mandate:** create a completely new interface for the Nearby Wells Intelligence System. Do not reuse the existing frontend's navigation, composition, components, CSS, copy or visual hierarchy. This document is a greenfield product design brief for agents. It describes the **ideal target product**, assuming authorized OIL data, a reliable eRTMAC feed, reviewed historical records and validated predictive models. It is not a claim that those prerequisites are implemented today.

## 1. The product to design

Oil India Limited's drilling team has a live view of the active well, but much of the useful experience from nearby wells is buried in completion reports, daily drilling records, mud logs and individual memory. NWIS joins that institutional memory to current conditions. It must help an engineer see nearby/analog wells, understand what happened in comparable formations, anticipate hazards and inspect the evidence behind every conclusion.

The product's promise is **orientation before decision**. An engineer should be able to answer, in this order:

1. **Where are we?** Current well, depth, formation, drilling state and telemetry quality.
2. **What lies ahead?** Formation boundaries, forecast hazards and known historical events in the next chosen depth interval.
3. **Why should I believe it?** Comparable wells, source pages, model limits and data provenance.
4. **What are the options?** Recorded mitigations and evaluated scenarios, without autonomous rig control.

The application serves an office engineer on a large screen, a geologist comparing depth and formation, a reviewer validating reports, a supervisor following operational decisions and a rig engineer on a tablet or phone.

## 2. Original design thesis: “The Subsurface Observatory”

The interface should feel like an instrument made for the subsurface: measured, quiet, information-dense and beautifully legible. Its identity comes from geological survey plates, plotted well logs, map marginalia and engineering notebooks—not conventional SaaS cards or a cinematic control room.

Three coordinates organize the entire product:

- **Place:** map location, surface-to-bottomhole trajectory and proximity.
- **Depth:** measured depth, true vertical depth, formation intervals and events.
- **Time:** live sensor stream, historic event timing and shift decisions.

The signature interaction is a **linked focus cursor**. Select an offset well, depth, event or timestamp anywhere; all relevant panes align to that same selection. The engineer never has to mentally reconcile three disconnected charts. A clear “current focus” bar states `Active well / Formation / MD range / Offset selection / Time range`, with one action to clear it.

The UI should look distinctive even with all data removed. Its character is in typography, strong spatial organization, considered gridlines, disciplined annotation and a recurring depth ruler. Do not add decorative drill-bit illustrations, AI-generated oilfields, gradients, glowing hazard gauges or walls of equal-sized cards.

### Proposed visual language

| Token | Starting value | Use |
|---|---|---|
| Chalk | `#F2F0E9` | Main working canvas, not pure white |
| Survey paper | `#FFFDF8` | Source excerpts, notes and printable surfaces |
| Basalt ink | `#182B34` | Primary type, borders and chart axes |
| Slate | `#5F7075` | Secondary type and inactive mapping layers |
| Mineral teal | `#176A70` | Selection, active trajectory and primary actions |
| Ochre | `#B47832` | Lookahead annotations and historical markers |
| Signal red | `#AD4C3E` | High-severity events and genuine conflicts only |
| Quiet rule | `#CDD4D1` | Delicate dividers and gridlines |

Use a high-character editorial serif for screen titles and well/formation names, a robust sans-serif for UI text, and tabular monospaced numerals for MD/TVD, timestamps, rates and IDs. Type should still be readable at 125–150% browser zoom. The palette is a design hypothesis; an agent may refine it after contrast testing but should retain the quiet scientific character.

Visual motifs: numbered plate labels (`01 / LIVE`, `02 / OFFSETS`), precise ruler ticks, lithology hatch patterns, small source annotations, restrained marker shapes and line weights that distinguish observed from inferred data. Animation is limited to meaningful state changes; honor reduced motion.

## 3. Entirely new information architecture

Do not mirror the old page list. Build the product around five tasks, with contextual subviews instead of a long menu of disconnected destinations.

| Workspace | User's question | Core objects |
|---|---|---|
| **Observe** | What is happening in the active well now? | Telemetry, drilling state, lookahead, alerts |
| **Explore** | Which nearby wells and subsurface intervals are comparable? | Map, trajectory, depth section, formation correlation |
| **Investigate** | What actually happened, and where is the source? | Search, case file, mitigations, cited report pages |
| **Validate** | Can this document/event be trusted and used? | Ingestion queue, OCR/ASR review, conflict resolution, provenance |
| **Evaluate** | How well is the system performing? | Model assurance, alert burden, data coverage, historical analytics |

**Handover** is a persistent action, not an isolated silo: save the current focus, selected alerts, sources and engineer notes into a printable shift brief. A global search opens from every workspace and returns to the previous focus.

### Shell and persistent context

The shell has a narrow nav rail, a well-context header, a main analysis canvas and a contextual inspector. The header always shows field/well/wellbore, current MD/TVD and datum, formation, operating mode (`LIVE`, `REPLAY`, `HISTORICAL`), last observed/received timestamps and stream quality. Model availability is shown beside, not merged with, data freshness. A transient toast never carries essential safety status; stale/outage states persist until resolved.

At desktop widths, the contextual inspector can pin to the right. On tablet it becomes a drawer. On phone it becomes a separate step with an obvious back path. The selected well/interval/event survives workspace changes.

## 4. Principal experience flows

### Flow A — lookahead investigation

The engineer opens **Observe**, selects a 100 m lookahead, sees a mud-loss forecast and a historical offset event near the approaching formation top. Clicking the forecast aligns the telemetry window and formation section, highlights the relevant offset wells in **Explore**, and opens a compact evidence chain. The engineer opens the cited source page, compares conditions, records an assessment and includes it in handover. One focused object persists throughout.

### Flow B — geographical to geological comparison

The geologist starts in **Explore**, selects a target formation and an active well, then filters candidate wells by radius and reviewed trajectory/target-depth proximity. Pinning two offsets opens a three-well section aligned by the chosen geological basis. A change in alignment mode (MD, TVD, formation-relative) updates axes and mapping explanations, never silently repositions events. Brushing a depth interval filters map markers, incidents and report search together.

### Flow C — report into institutional memory

A reviewer opens **Validate**, examines a newly extracted DDR candidate beside the original page, checks event type, depth axis/datum, onset time, formation, mitigation and negation, then corrects or approves with rationale. The approved case becomes discoverable in **Investigate** with page-level citation and a recorded provenance trail. Contradictory report facts remain a visible dispute until adjudicated.

### Flow D — field handover

The rig engineer opens a bandwidth-light **Observe** view on mobile, checks source freshness and the highest-priority alert, reads its one-sentence evidence summary, acknowledges it if authorized, adds a shift note and exports/synchronizes the handover. Offline actions are visibly pending and never masquerade as server-confirmed.

## 5. Workspace specifications

### 5.1 Observe — the live well desk

The first viewport should communicate the well's state without scrolling: active well, depth/formation, mode/freshness, current drilling phase, top alert and next formation boundary. A large depth-forward lookahead is more valuable than six equal KPI cards.

```text
┌─ WELL CONTEXT ─ MD/TVD ─ FORMATION ─ LIVE ─ DATA AGE ─ MODEL STATUS ────────┐
│  LIVE PARAMETER STRIP          │  LOOKAHEAD / NEXT 100 m                    │
│  ROP · WOB · RPM · torque       │  formation boundaries · casing · events    │
│  flow · SPP · mud weight       │  validated hazard bands + lead distance    │
├───────────────────────────────┴──────────────────────────────────────────────┤
│  Synchronized telemetry trends              │  Selected alert / evidence   │
│  sensor quality · rig state · data gaps      │  why now · cases · actions   │
└──────────────────────────────────────────────────────────────────────────────┘
```

The parameter strip exposes primary channels, trend arrows and quality status. Synchronized charts show the last selectable 15/60/240 minutes, rig-state shading and non-interpolated gaps. The lookahead shows both historical event markers and model forecasts with distinct shapes. A forecast display includes hazard, probability, calibrated confidence/uncertainty, horizon, model version and applicable formation. Do not encode probability and evidence quality with the same color or circle size.

Alerts form an ordered queue by urgency and relevance. The selected alert explains the trigger, sensor context, comparable wells, source reports, uncertainty and potential next checks. Actions are `Acknowledge`, `Under review`, `Resolve`, `Dismiss`, `Record outcome`; each requires role and rationale as appropriate. Repeated observations update one episode rather than creating a stack of clones. An advisory alert budget has a visible suppression digest; critical alerts bypass it.

### 5.2 Explore — map + section as one instrument

The default composition is a map on the left, candidate index on the right and a slim depth section docked below. The engineer can expand either map or section to full canvas. Map layers: wellheads, trajectories, target-depth positions, field/formation extents, historical event symbols and optional approved geological surfaces. Layer controls show legend and data coverage, not just on/off switches.

Search basis is explicit: surface radius, terminal position, or a reviewed trajectory/target-depth comparison. Every distance is labelled with its basis and uncertainty. A trajectory path is never equivalent to an anti-collision clearance calculation. Offset ranking has an explanation panel: formation match, depth overlap, lateral distance, trajectory, reservoir/parameter context and missing inputs. Similarity is not a risk probability.

The subsurface section is a multi-lane depth canvas sharing one ruler:

```text
MD/TVD │ Formation │ Lithology │ Active well │ Offset A │ Offset B │ Events
2,000  │ Barail    │ ▤ shale   │ ROP/torque  │ ROP      │ ROP      │ loss ●
2,100  │           │ ▧ sand    │ MW/ECD      │ MW       │ MW       │ kick ◆
2,200  │ Tipam     │ ▤ shale   │ casing      │ casing   │ casing   │ stuck ■
```

Alignment modes are selectable and displayed at the ruler: MD, TVD and reviewer-approved formation-relative. Raw source depth and mapped active depth appear together in the inspector. Uncertain onset spans render as bands, not fabricated exact dots. Formation, casing, cementing, mud-weight/ECD, pore pressure, fracture gradient and operational incidents occupy separate labelled lanes. Pressure bands include uncertainty and source provenance. Missing lanes remain empty with a reason.

Selecting a formation highlights all intersecting well intervals, related cases and model applicability. Brushing a depth range updates map/list/search; a breadcrumb chip shows the filter. A planning mode accepts a hypothetical location/trajectory and shows offset-risk context with assumptions, separated visually from live operations.

### 5.3 Investigate — search and cited cases

This is a research environment, not a chatbot wall. A prominent query bar accepts natural language; a structured filter rail supports formation, event type, well, depth, operation, outcome, period and source type. Search results group by **case**, not by duplicate passage. Each result includes a short answer/summary, comparable-well context, depth, reviewed status and a citation preview. A model-generated synthesis is labeled separately from reviewed source facts. No-evidence and conflicting-evidence answers are first-class results.

The case file uses a narrative spine: `Before event → Onset → Response → Outcome → Lesson/uncertainty`. Alongside it, a compact parameter signature and depth position keep the technical context. The inspector lists all citations, original report pages, reviewer corrections and version history. Clicking a citation opens a source drawer with the highlighted passage while retaining the case in view. A recorded mitigation can be compared across cases, but the UI must not imply it caused success merely because it co-occurred with an outcome.

The “response network” is an evidence graph with nodes for event, formation, mitigation and outcome. Edges mean *recorded relationship*, not causal proof. Edge thickness can encode count only when the denominator and selection are shown. An illustrative NPT exposure calculation requires a user-provided rig-day rate and displays the assumption prominently.

### 5.4 Validate — the source review studio

Use a three-column desktop workbench: review queue, document page, structured extraction. The page is the authority. Highlight exactly which words support each extracted field. Reviewers can inspect OCR original versus corrected text, unit/depth interpretation, onset precision, formation alias, negation and quality warnings. A conflict view places competing passages side by side with source metadata, without forcing a false single answer.

Decisions are `Approve`, `Correct and approve`, `Reject`, `Escalate/adjudicate`; every decision captures rationale, actor and version. A reviewer sees what the approval would unlock (search, correlation, alert support) before committing it. Voice memo transcripts use the same review path, with audio playback, language, ASR confidence and consent/retention state. Batch actions can triage or assign work, but cannot mass-approve unexamined drilling events.

### 5.5 Evaluate — system and evidence health

Separate four panels that are often incorrectly mixed: **data coverage**, **model performance**, **operational alert burden** and **historical outcomes**. Data coverage shows well/formation/period, channel completeness, source review and quality failures. Model performance shows held-out-well cohort, calibration, precision/recall, lead distance, drift and applicability. Alert burden shows per-shift firing/suppression, engineer actions and adjudicated outcomes. Historical analytics show event counts and NPT with sample size and observation coverage.

A beautiful chart is not a substitute for denominators. Every rate shows `n`, cohort and date range. Supervisors can compare model versions and export a model card. An out-of-distribution or degraded-feed banner changes the status of the relevant forecast without erasing its historical audit record.

### 5.6 Handover — a portable decision artifact

From any workspace, “Add to handover” captures the current focus, selected case/alert, citations and an engineer note. The handover composer generates a one-page shift summary with active well state, depth/formation, outstanding alerts and owners, decisions taken, next checks, unresolved conflicts and linked sources. It is printable in A4 and shareable under the organization's access policy. The author can edit their notes but cannot silently edit cited source facts.

## 6. Shared component grammar

The following are greenfield conceptual components, not existing frontend modules:

| Component | Must communicate |
|---|---|
| `WellContext` | Wellbore, field, mode, MD/TVD/datum, formation, timestamps and stream quality |
| `DepthRuler` | Axis, unit, datum, alignment mode, interval and precision |
| `LinkedFocus` | Selected well/event/depth/time, source of selection, clear/back action |
| `ProximityBasis` | Surface vs trajectory/target-depth distance and positional uncertainty |
| `ForecastBand` | Hazard, horizon, probability, calibration/confidence, applicability and model version |
| `EvidenceChip` | Source type, document/page, review state and direct open action |
| `CaseSpine` | Before/onset/response/outcome, with uncertainty and source links |
| `QualityMark` | Good/suspect/bad/missing sensor quality without using color alone |
| `DecisionEntry` | Actor, timestamp, action, rationale, version and audit link |
| `ConflictPanel` | Two or more source-backed values, what differs and who must adjudicate |
| `EmptyState` | What is missing, effect on the view, and next valid action |

Use an icon + word + position system, not dozens of interchangeable colored pills. All numeric components carry units and basis. Inferred and observed values have different line styles and legend labels. Any chart with selectable marks has an equivalent keyboard-accessible list/table.

## 7. Copy, trust and human decision-making

The tone is precise and calm: “Similar wells reported losses in this interval” is better than “Danger ahead.” Use “predicted probability” for a validated calibrated model, “historical frequency” for counts, “similarity” for ranking and “confidence/quality” for evidence. Never merge these into one score. Unknown is not zero; no historical event is not proof of no hazard.

Every claim has a provenance path. Every recommendation displays its assumptions and is framed for engineer review, never as an automatic drilling instruction. Keep live, replay, public-analogue and synthetic contexts distinguishable. Show `observed_at` and `received_at` separately when lag matters. A stale feed or unresolved depth mapping remains visible near the affected decision, not buried in a settings page.

## 8. Mobile, accessibility and performance

At 1440 px, the observatory can use linked panes; at 768 px, prioritize one primary canvas plus inspector drawer; at 375 px, present a deliberate step-by-step flow. The mobile **Observe** view loads text/current state and the top alert before heavy chart/map code. Large touch targets, offline timestamps and action-confirmation states are essential for field use.

Meet WCAG AA contrast, visible keyboard focus and logical focus return from drawers. Map and depth interactions require keyboard equivalents; alert severity cannot depend on color. Screen readers must receive selected-object and status changes. Respect reduced-motion and browser zoom. Avoid horizontal page overflow. Print handover and case evidence in grayscale without navigation chrome. Long lists should virtualize; telemetry downsampling must preserve spikes and gaps rather than smoothing away hazards.

## 9. Agent deliverables

Produce a design system (tokens, typography, marker language, chart/axis rules) and high-fidelity responsive screens for:

1. Observe: normal live state and critical-alert state.
2. Explore: map plus two selected offsets; expanded depth section; alignment conflict.
3. Investigate: search results and case file with source drawer.
4. Validate: report page plus extraction editor and contradictory-source adjudication.
5. Evaluate: model/data/alert-health panels.
6. Handover: A4 brief and mobile field-lite view.

For each, provide loaded, loading, stale, empty, conflict, error and permission-denied states. Mock data must be labelled illustrative. Prototype these interactions: linked map/depth/event selection; depth brushing; A/B well comparison; open source page from a claim; acknowledge an alert with rationale; approve/correct a report event; add a cited case to handover.

Agent ownership can split by design system/shell, Observe+alerts, Explore+subsurface, Investigate+Validate, and Evaluate+Handover. Agree the shared `WellContext`, `DepthRuler`, `LinkedFocus` and `EvidenceChip` contracts first. One integration owner checks the full journey and responsive consistency. Do not pull visual code from the old frontend; create a new component architecture around this specification.

### Design acceptance test

Give a drilling engineer an unfamiliar well and ask them to find the most relevant offset incident, explain why it is comparable, open the original report page, understand a forecast's horizon and uncertainty, and record a handover note. If they can do that without explaining the UI aloud—and can repeat it on a tablet—the design has achieved its purpose.
