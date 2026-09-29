# NWIS frontend redesign plan

## Goal

Keep the Subsurface Observatory palette and evidence-led character from `pages.md`, while making every workspace easier to read, navigate, and act on. The interface should feel like a useful operational desk: clear priorities, descriptive navigation, balanced use of space, and source context close to every decision.

## Current problems to fix

- The screenshots show that styling is inconsistent, not just too small: some search, number, and action controls render with browser-default white backgrounds and borders against the dark interface. Create a complete control baseline for `input`, `select`, `textarea`, `button`, range controls, disabled/focus/error states, and apply it consistently across shared and page-specific styles.
- In the Explore screenshot, the map is a small schematic grid floating in a very large empty canvas. It does not orient the user in India, and the pin/list panel is visually detached from the map. Replace this mock surface with an India map whose zoom and selected well define the view.
- The screenshots show the user several screens down a long Explore page, where search, response network, operations ledger, and assumption desk blend into a dense sequence with weak grouping. Promote the primary map and offset selection, then structure research tools into clearly named sections or tabs with compact summaries and expandable details.
- `frontend/src/styles.css` sets the root to 14px, then uses many `0.5–0.75rem` labels. This produces 7–10.5px text in navigation, context chips, and metadata.
- `frontend/src/App.tsx` renders a 56px icon-only navigation rail. Plate numbers and hover titles carry most of the meaning, so destinations are hard to scan or discover.
- The persistent context bar packs well, basin, coordinates, mode, environment, dataset, and transport into one 44px strip. It gives low-priority metadata the same visual weight as the active well and data state.
- Several workspaces stack many full-width panels, making the primary task hard to locate while leaving underused space inside or beside sections.
- At widths below 768px, CSS hides the navigation, Explore sidebar, and parts of the review workbench. Those tasks need an accessible responsive route rather than disappearing.
- `pages.md` describes light paper tokens, while the implemented shell uses dark ocean surfaces. Preserve the **implemented palette and its semantic colors**; decide surface treatment per workspace instead of introducing a new palette.

## Design principles

1. **One obvious task per view.** Place its primary control and result in the first screen. Put supporting analysis nearby and long reference material behind tabs, accordions, or drawers.
2. **Use space to communicate hierarchy.** Empty space should separate task groups; content within a group should align to a shared grid. Avoid both huge blank cards and tightly packed text.
3. **Make labels self-explanatory.** Use plain destination names and short descriptions. Keep plate numbers as secondary wayfinding.
4. **Show what is known.** Distinguish live, replay, historical, unverified, disputed, and unavailable states with text as well as color. Keep citations visible at the point of use.
5. **Keep all workflows reachable at every size.** Responsive layouts may collapse and reorder panels, but must preserve navigation, filters, evidence, and actions.

## Global shell and navigation

### Desktop shell

- Replace the narrow rail with a **224–248px sidebar** at widths of 1200px and above. Give each item an icon, full label, plate number, and one-line purpose. Example: `Observe` / `Live well desk`; `Explore` / `Offsets and geology`; `Investigate` / `Answers and citations`; `Validate` / `Review source material`; `Directory` / `Wells and system`; `Evaluate` / `Model readiness`.
- Put product name and a concise descriptor at the top: **NWIS / Subsurface Observatory**. Group task destinations first; place Directory, Evaluate, and Disconnect in a quieter lower group. Show the active item with a strong left marker, filled surface, and `aria-current`.
- Make the sidebar compactable to an icon rail only by user action. Persist this display preference locally if desired; never make a collapsed rail the only navigation on first use.
- Use a sticky top context header inside the content column. First row: active well switcher, current workspace title, mode/freshness state, and the main workspace action. Second row or disclosure: basin, coordinates, dataset, environment, and transport. The active well and stale/live/replay state remain visible while scrolling.
- Keep the footer low emphasis and short. Place the simulation disclaimer near any replay or apparent prediction where it affects interpretation.

### Tablet and mobile

- At 768–1199px, use a 72px compact rail with a visible navigation menu button and a labeled drawer. At less than 768px, use a top bar with the current workspace name and menu button; open the same labeled drawer. Provide a visible way to close it, keyboard focus management, and Escape support.
- Reflow context chips into two short rows or a disclosure. Never truncate the active well or state label without an accessible full value.
- Convert three-column workbenches into a task sequence: queue/list → selected item → evidence/detail → action. Keep a persistent back link or step tabs so users can move between them.

### Sidebar enhancements

- Make the expanded sidebar a useful orientation and work selector, not a strip of unlabeled icons. Include NWIS branding, the active well summary, six clearly named destinations with short descriptions, and a lower utility area for help/tour, connection state, and disconnect.
- Group navigation by user task: **Monitor** (Observe), **Find evidence** (Explore, Investigate), **Review data** (Validate), and **Platform** (Directory, Evaluate). Keep plate numbers as quiet identifiers and show which destination is active with label, icon, background, and a high-contrast edge marker.
- Show a compact active-well block near the top with well ID, synthetic/public provenance, basin, and mode. Selecting the well block opens the same well selector used elsewhere; it must not silently switch wells.
- Provide an explicit collapse/expand control with an accessible name and tooltip. Expanded is the first-use desktop state; collapsed is a user preference, not a default. In collapsed mode retain tooltips, keyboard focus labels, active marker, and a persistent control to expand.
- At tablet/mobile sizes, use the same destination order and descriptions in a drawer. Keep the current page title in the top bar, show a clear close control, close after navigation, and support Escape and focus return to the menu button.
- Add a `Take a tour` help action at the bottom of the sidebar/drawer. The user can reopen the tour at any time, including after choosing to skip it.

## Type, spacing, and component rules

| Element | Target | Use |
|---|---:|---|
| Root and body text | 16px, 1.5–1.6 line height | Default reading size |
| Secondary text | 14px minimum | Descriptions, metadata, table cells |
| Small labels | 12px minimum | Eyebrows, chips, axis labels; use sparingly |
| Page title | 30–36px desktop; 26–30px mobile | One per view |
| Section title | 20–24px | Major task groups |
| Card title | 16–18px | Scan-friendly panels |
| Metric value | 28–40px | Only for the few decision-critical numbers |
| Control target | 44px minimum height | Buttons, inputs, nav items |

- Use a 12-column desktop content grid with a readable maximum width around 1440–1520px. At large widths, enlarge useful map/chart/evidence areas before widening prose. Keep prose around 65–80 characters per line.
- Use an 8px spacing scale: 8px inside compact groups, 16px between related controls, 24px inside cards, 32–40px between major sections. Standard card padding: 20–24px. Avoid repeated nested card borders where one clear surface is enough.
- Keep serif for page titles and selected editorial headings; use sans-serif for controls and explanations; monospace only for numerical data, depth axes, timestamps, and identifiers.
- Preserve the existing teal, ochre, red, ocean, and paper relationships. Audit contrast on actual surfaces; reserve red for safety/conflict, ochre for historical/replay/caution, and teal for selected/verified/action.
- Prefer explicit text such as `Historical evidence`, `Stale · last sample 21s ago`, and `No trained model` over color or unexplained abbreviations.

## Page layouts and content priorities

| View | First screen | Main layout | Secondary content |
|---|---|---|---|
| Landing | Mission, short product explanation, clear token form, simulation status | Two balanced columns on desktop: narrative and sign-in; single column on mobile | Show three compact examples of tasks, then trust/source principles. Avoid a large decorative void. |
| 00 Observe | Active depth, stream freshness, replay controls, alert count and most urgent alert | Main column for depth/alerts; narrower persistent context column for session and lookahead | Put alert budget and suppression history in a disclosure. Show evidence and actions together within the selected alert. |
| 01 Explore | Active well, comparison basis and radius, map, ranked offsets | Map and offset list as the primary split; selected offset detail directly below or in a side inspector | Tabs for Depth & formations, Pressure, Incidents, Search, Planning. Keep the citation path available from each result. |
| 02 Investigate | Question search/list, answer status, cited passage | Search/list column and generous answer/evidence column | Filters in a collapsible filter row; conflicting passages displayed side by side with source labels. |
| 03 Validate | Review queue, selected source, candidate decision status | Desktop three-column workbench sized for reading: queue 260–300px, viewer flexible, editor 340–400px | Tabs for Document, Facts, Voice. Keep source page and editable extraction simultaneously visible where width permits. |
| 04 Directory | Active well selector and nearby results | Well list and selected-well detail with radius control near results | Move component health to a compact status section; expand only degraded/error details. |
| 05 Evaluate | Readiness verdict with reason and next qualification gate | Gate checklist and telemetry dossier as two clear sections | Keep unavailable metrics visibly unavailable; explain the evidence needed to unlock each gate. |

### Page-specific interaction details

- **Observe:** Make `Next depth step` the primary action in paused replay. Group play/pause/reset as session controls. Alert cards should show severity, mapped interval, cited source, state, and the one next action before expanding rationale/history.
- **Explore:** Keep map and offset list synchronized. Selecting a pin highlights its list row and opens a compact analogue summary. Avoid forcing a long scroll from map to incident details. Give each subview a concise heading and a one-sentence explanation.
- **Investigate:** Make the answer status (`Answered`, `Disputed`, `Insufficient evidence`) the first line of the result. Put source title, page, review state, and passage directly beside the claim. Never present a disputed answer as a single resolved sentence.
- **Validate:** Make review progress obvious (`Queue → Source → Extraction → Decision`). Keep approve/correct/reject controls fixed within the editor as it scrolls. Ask for rationale in the decision flow, not far away from the action.
- **Directory:** Describe distance as **surface distance** and keep the radius control next to the nearby list. Show what switching wells will update in a small helper line.
- **Evaluate:** Use a short readiness summary and ordered blocker list. Treat scientific thresholds as gate criteria, with a visible distinction between proposed and met criteria.

## Interactive India map and well data

### Product behavior

- Make the map a major part of Explore and a useful locator on the operations dashboard. Start at a whole-India extent; fit to the active well and selected offsets after selection. Support wheel/pinch zoom, drag pan, zoom buttons, reset-to-India, and a clear selected-well action.
- Show synthetic demo wells as well symbols, with accessible labels and a legend. Use distinct visual states for active well, selected offset, other synthetic well, and a selected planning point. A click or keyboard activation selects a well and updates the adjacent well summary, offset ranking, radius results, and applicable formation/depth views.
- Add map filters for dataset, basin/region, formation match, event type/severity, and active radius. Keep surface-distance and trajectory/geology analogue ranking separate and label them as separate measures.
- Open a compact detail card for a selected well: well ID, synthetic/public-analogue badge, basin/region, coordinates, distance basis/value, reviewed formation, available event count, and data provenance. Link to the full case/evidence view. Never imply a synthetic well is a real OIL well.
- Selecting a region can filter or zoom to its wells; it must not create guessed well locations. Well coordinates come from the dataset record, or from an explicitly synthetic fixture with reproducible coordinates and a synthetic label.
- Preserve keyboard use: markers need focusable controls and names; include an equivalent searchable/selectable well list because canvas markers alone are not accessible.

### Map source and accuracy standard

“100% accurate” cannot be guaranteed for a web map in every zoom level, projection, boundary edition, or source dataset. Set a measurable standard instead: **use Survey of India (SoI) published political/administrative boundary data as the authoritative India boundary source; preserve its geometry and attribution/version; validate geometry and coordinates; and show data dates and provenance.** Do not digitize a screenshot or use a generic world outline as the national boundary.

1. Obtain India/state/district boundary vectors from the official [Survey of India Online Maps Portal](https://onlinemaps.surveyofindia.gov.in/) or [India Maps product portal](https://indiamaps.gov.in/product). The SoI catalog lists administrative boundary shapefiles and political-map products; check the current product, scale, edition, access conditions, and reuse terms before bundling. SoI states that its published maps or digital boundary data are the standard to use for political maps of India in its [geospatial guidelines](https://onlinemaps.surveyofindia.gov.in/GeospatialGuidelines.aspx). Use administrative boundary vectors for interactive outlines; use the current political map PDF as a visual reference/QA source, not as a georeferenced tile layer.
2. Keep source files, source URL, download/access date, edition/scale, coordinate reference system, and applicable license/terms in a data manifest. Preserve the original file and produce a reproducible, documented web derivative. Do not silently simplify or alter politically sensitive boundary geometry. For app performance, use a controlled simplification tolerance only after visual/topological checks at intended scales.
3. Normalize map data to WGS 84 (`EPSG:4326`) for API/PostGIS interchange, with correct axis order (longitude, latitude), then create vector tiles or GeoJSON for the browser. Prefer self-hosted vector tiles for stable offline/demo use and predictable styling; a raster or vector tile basemap may be added only if its source license and attribution are satisfied. Keep boundaries and wells as separate layers.
4. Validate source and derivative geometry: valid polygons, no unintended gaps/slivers, expected state/district counts and names, extent and island coverage, known control points, and comparison against the matching SoI edition. Add automated checks for coordinate range/order, null/out-of-India demo points, duplicate IDs, and stable fixture locations. Have a GIS-capable reviewer visually inspect the full-country and regional zoom levels.
5. Treat well-position accuracy separately from boundary accuracy. A synthetically generated Assam-basin dataset is appropriate for the prototype, but its marker must be labeled `SYNTHETIC DEMO`; document its seed/coordinate-generation method and avoid fabricated operational precision. Public analogue wells retain the source's published location and its uncertainty/provenance. Do not place synthetic wells by random jitter across India or represent them as real OIL assets.
6. Show map source, edition/date, coordinate reference system, and dataset kind in a small `Map data` disclosure. Include `Reset map`, `Locate active well`, and `Fit visible wells` controls. Show a useful empty/low-zoom state if the selected dataset has no wells in the current extent.

### Recommended implementation shape

- Frontend: React + TypeScript + Leaflet, consistent with the build specification. Use a tile/vector-grid layer based on approved SoI boundary vectors; layer wells and selection overlays independently. Keep the map component controlled by selected well, visible well set, filters, and radius so map clicks and list selection stay synchronized.
- Backend: store point coordinates as PostGIS `geography(Point, 4326)` as specified; provide nearby results from the spatial API. Return source dataset, coordinate provenance, and whether a location is synthetic with each well. Keep radius queries based on surface distance; show trajectory-aware/geology similarity as a separately computed analogue ranking.
- Demo data: use synthetic Assam-basin wells with plausible region and formation context; fixtures should be stable and clearly synthetic. Add public analogue datasets only with their real source locations and provenance. The National Data Repository (DGH) is a stated future path for Indian petroleum data; the build specification notes its access requires registration/approval, so do not imply that the prototype currently uses it.
- Network behavior: bundle/cache the boundary layer and demo well fixtures for the demo where licensing permits. The map should still render the last available boundary and wells when external tile connectivity fails; disclose stale/offline state.

### Map acceptance criteria

- The initial view clearly shows India and relevant surrounding context with recognizable state boundaries, then zooms to the selected synthetic/public well set without changing its coordinates.
- Each well marker and list row are linked, selectable, and expose identical identity, type, and provenance. Surface distance is clearly labeled; analogue similarity is not shown as risk.
- All interactive map functions have keyboard-operable equivalents in the well list and controls.
- Boundary dataset edition/source/terms are recorded; geometry and coordinate checks pass; map rendering is visually checked at national and regional scales. The UI never promises absolute accuracy and never presents synthetic wells as real locations.
- Map and sidebar remain usable at 375px, 768px, 1440px, and 1920px; map receives enough height to inspect geography and the controls remain reachable without covering selected markers.

## Alignment with NWIS Build Specification (SIH 2026, PS 26121)

The redesign must express the actual target: an evidence-backed decision-support layer beside eRTMAC, never a control system or replacement. It must retain visible `SIMULATED` status because real eRTMAC integration is explicitly out of scope. Prioritize the specified P0 end-to-end flow: ingest a WCR/DDR, review extracted event and confidence, show its source-backed location/correlation, search cited records, and trigger a deterministic formation/depth alert in simulated replay.

- **Dashboard / Observe:** active well, MD/TVD, formation, connectivity state, distinct risk and confidence, lookahead timeline, map locator, alert feed, cooldown state, cited matched offsets, acknowledge/dismiss/outcome actions. Show `unknown`/`insufficient data` rather than invented zeroes or risk percentages.
- **Explore / Map:** user radius and event/severity/formation filters; surface-nearby results distinct from trajectory/geology-ranked analogues; formation/depth-aligned correlation, not raw-depth comparisons alone; map selection opens an evidence-linked case file.
- **Investigate:** natural-language search with structured filters and hybrid retrieval; every answer cites document and page/section. Disputed/low-confidence evidence stays explicit. The model must not produce or execute raw SQL.
- **Validate:** WCR/DDR ingestion, OCR/extraction confidence, review queue, editable event fields, human validation, and source provenance. Human review is visible as a workflow, not just a confidence number.
- **Fishing / Analytics / Evaluate:** organize fishing/recovery history and NPT/cost analytics as clearly scoped views or sections. Label any rig-day cost as user-entered illustrative calculation. Show model card/limitations, well-level split evidence, separate risk and confidence, and `insufficient data` where justified.
- **Field-lite:** treat the spec's mobile/poor-connectivity mode as a first-class layout: large touch targets, minimal alert and evidence payload, cached last-known status with timestamp, and no map/charts until requested. Do not hide tasks when the desktop layout collapses.

The specification's non-negotiable guardrails become interface acceptance checks: no uncited claims, no alert without a matched evidence record/defined trigger, deterministic alert logic independent from ML score, configurable thresholds/cooldown, explicit synthetic/public-analogue labeling, and human decision authority throughout.

## Visual impact and problem-statement priority

Use two dimensions when sequencing work: **PS priority** (does it complete a required NWIS workflow?) and **visual impact** (how much it improves clarity and credibility in the first screen). A polished feature with no evidence path cannot outrank a working P0 flow. Visual priority decides the order *within* those functional gates.

| Order | Change | PS link | Visual impact | Why it comes here |
|---|---|---|---|---|
| **V0 · Fix first** | Shared CSS/control baseline, 16px body type, contrast, spacing, descriptive sidebar, stable responsive shell | Core dashboard usable by field and office staff | **Very high, every page** | The screenshots currently show tiny text, unlabeled navigation, browser-default controls, and weak hierarchy. Every later screen inherits these defects. |
| **V1 · Primary demo** | Real India map foundation, Assam zoom, clearly synthetic well pins, radius, filters, linked well list/details | P0 interactive nearby-well map | **Very high, Explore and dashboard** | Replaces the empty schematic canvas with a geographic, interactive centerpiece that directly demonstrates the PS. Complete source/geometry checks before presenting the boundary as authoritative. |
| **V1 · Primary demo** | Observe dashboard: active MD/TVD, current formation, simulated stream state, 50/100/200m lookahead, one cited alert and next action | P0 dashboard and deterministic alerting | **Very high, Observe** | Lets a reviewer understand the active-well story at a glance and follow the alert to evidence. |
| **V1 · Primary demo** | One complete document → reviewed event → map/correlation → cited search result → replay alert path | P0 ingestion, repository, correlation, alerting; demo success metric | **High, cross-page** | Connects otherwise separate screens into a credible product. Each transition needs a visible link, status, and source citation. |
| **V2 · Evidence depth** | Formation-aligned offset comparison, case file, source viewer, confidence review queue | P0 correlation and ingestion; cited knowledge | **High, Explore/Validate** | Adds scientific meaning to nearby pins and makes the source trail inspectable without long scrolling. |
| **V2 · Field utility** | Field-lite alert view with cached timestamp, large controls, low-bandwidth payload | P1 field-lite; rig-site persona | **Medium on desktop, very high on mobile** | Preserves the core decision flow under field conditions; should follow the working alert path. |
| **V3 · Differentiators** | Trajectory ranking, fishing advisor, NPT/cost analytics, feedback, model card | P1 differentiators | **Medium** | Add as clearly labeled modules after the P0 data path works. Never fill missing data with invented scores or success rates. |
| **V4 · Finish** | Tour refinement, animation, decorative geology motifs, micro-interactions | Onboarding and presentation | **Low to medium** | Helpful for comprehension once the information architecture and interactions are stable. Keep the tour's basic skip/reopen behavior in V0. |

### Attention order within each screen

- **Observe:** first attention to well + simulation/freshness, then current depth/formation, then the next historical hazard, then evidence and action. Large numeric treatment belongs to depth and lookahead distance, not to decorative counters.
- **Explore:** first attention to India/Assam geography and active well, then the selected radius and offset list, then formation match and event evidence. Give the map a useful height and avoid an empty full-width stage when only a few wells are present; auto-fit the visible markers and offer a region inset or well list.
- **Investigate:** first attention to the question and answer status, then the cited passages. Search controls and filters should be visually joined; the evidence should occupy the largest reading area.
- **Validate:** first attention to what needs review, then the source page, then editable extraction and decision. Put source and decision in the same visible work area on desktop.
- **Directory:** first attention to well selection and nearby wells. Put healthy platform component detail behind a compact status disclosure; expose degraded/error states immediately.
- **Evaluate:** first attention to the readiness verdict and blockers, then gate detail and telemetry quality. Do not let empty model score cards dominate the screen.

### Extra PS-driven interface opportunities

- Add a compact **demo journey** reachable from the landing page or sidebar help: `Choose synthetic well → inspect nearby history → open source → advance replay → review alert`. Each step navigates to existing screens with the same selected well and event. This gives judges a clear route through the required end-to-end story without inventing separate demo-only behavior.
- Add a **lookahead depth strip** in Observe that places upcoming hazards on the same MD axis as the active position and links each marker to its matched offset case. Use explicit formation labels and source counts; an unavailable risk score stays `unknown`.
- Add a **case file drawer** from every map pin, search result, and alert citation. Keep one consistent layout for well, event, mapped depth, action taken, outcome, NPT, and source page so users do not learn a different evidence view in each workspace.
- Show **data provenance at decision points**: a small source badge and freshness/review status beside an alert or comparison, with the full passage one click away. Keep synthetic fixture provenance distinct from real public analogue citations.
- Add a **comparison legend and basis selector** wherever distance or similarity appears: `Surface distance`, `Trajectory separation`, and `Formation similarity` are separate values. Do not present a blended similarity number as a hazard probability.
- Add a **quiet alert-state history** with active/acknowledged/resolved and cooldown count, so the dashboard demonstrates alarm-fatigue handling without repeating the same alert card.
- For analytics, show **sample size before a chart**. When the sample is too small, show the actual cited cases and an `Insufficient data for rate` label instead of an empty or misleading histogram.

## Content and naming pass

- Replace cryptic top-level labels and bare icons with the destination descriptions above. Retain plate numbers as subtle metadata.
- Add a one-sentence purpose under each page title and a short section description only where a user must interpret specialized data.
- Write action labels as verb + object (`Review source`, `Open case file`, `Prepare offset brief`, `Start replay`). Use the same term for the same object across pages: `well`, `offset well`, `source passage`, `case file`, `review candidate`.
- Spell out abbreviations on first use within a view: Measured Depth (MD), True Vertical Depth (TVD), Rate of Penetration (ROP), Equivalent Circulating Density (ECD), Non-Productive Time (NPT).
- For empty, loading, error, and unavailable states, state what happened, why it matters, and the next available action. Do not fill empty space with oversized decorative panels.

## First-use product tour

- Offer a short, skippable tour after the user connects and the app has loaded the initial well context. Keep the page usable while the tour is open. Include `Skip tour`, `Next`, `Back`, and `Finish`; closing the overlay also skips. Do not block access to navigation or require completion.
- Use 5–6 focused steps: (1) active well and synthetic/live status, (2) sidebar destinations and how to return to this tour, (3) Observe dashboard and alert evidence, (4) Explore map, synthetic well selection and surface-radius control, (5) Investigate/Validate source citations and review, (6) Directory/Evaluate readiness and limitations. Use only steps relevant to available features; avoid promising unfinished functionality.
- Each step has a short heading, one plain-language explanation, and a visible progress indicator such as `2 of 6`. Highlight the target with a restrained outline and place the message card so it does not cover the control being explained. If a target is unavailable or off-screen, skip that step or navigate to its page with the user's consent via a clear `Open Explore` action.
- Make the tour responsive and keyboard accessible: trap focus only inside the tour dialog, provide an accessible dialog title, support Escape to skip, set focus to the dialog on open and return focus to the launch point on close, and ensure target descriptions are not conveyed by color alone. Respect reduced-motion preferences.
- Persist completion/skip state per browser so the tour does not appear on every visit; expose `Take a tour` in the sidebar help area and an optional `Replay tour` in help/settings. Do not persist tour state to an account or backend unless a later product requirement calls for it.
- Ensure synthetic/demo caveats are part of the tour: the displayed wells are demo data, live eRTMAC is not connected, and evidence-backed historical patterns are not operational instructions. Keep this factual and brief.

## Implementation order

1. **V0 · Foundation and shell:** Introduce type and spacing tokens, style all form controls and states, enlarge body text, rebuild the sidebar/context header, add responsive drawer, and make the tour skippable/reopenable. Audit contrast and 200% zoom.
2. **V1 · Geographic centerpiece:** Acquire and document the SoI boundary source and terms, build the map derivative, create stable synthetic Assam fixtures, and implement the map, filters, synchronized well list, selection details, and radius results.
3. **V1 · Operational story:** Rework Observe around current well/depth, simulated telemetry, lookahead, one evidence-backed alert, and the replay action. Wire map/case selection and alert citations into the same event story.
4. **V1/V2 · Evidence path:** Make a reviewed ingested event visible in Validate, Explore correlation, Investigate search, and Observe alert. Refine the source viewer, case file, and answer status so every claim has a readable path to its source.
5. **V2/V3 · Field and support views:** Build the field-lite layout, then refine Landing, Directory, Evaluate, fishing/analytics modules, and terminology according to actual data availability.
6. **V4 · Finish:** Refine tour copy and transitions, add restrained visual details, and inspect 375, 768, 1024, 1440, and 1920px layouts. Verify no horizontal scrolling or hidden workflows, inspect India/Assam map extents and provenance labels, and check keyboard access through each page.

## Acceptance criteria

- Every destination is understandable from visible text without hover, and every destination remains reachable on mobile.
- The desktop sidebar and mobile drawer show descriptive destinations, active well context, current location, and a reachable tour/help action; collapse and drawer controls work with keyboard and screen readers.
- First-time users can understand the shell and core workflows with a 5–6 step tour, skip it immediately, close it at any step, and reopen it later.
- Body copy is at least 16px; supporting content is at least 14px; only short metadata/axis labels may be 12px. No 7–11px interface copy remains.
- The first screen of each view shows its purpose, current operational context, primary control, and primary result or clear empty state at 1440×900.
- Evidence is reachable within one interaction from any alert, answer, incident, or extracted fact that depends on it.
- At 375px width and 200% zoom, controls remain operable, no content needed for a task is hidden, and the page has no unintended horizontal scroll.
- Colors retain their current semantic meanings, status is understandable without color, focus is visible, and controls have descriptive accessible names.

## Primary files to touch when implementing

`frontend/src/App.tsx`, `frontend/src/styles.css`, then the corresponding view files and local styles: `Operations.tsx`/`operations.css`, `Intelligence.tsx`/`intelligence.css`/`exploration.css`, `ReportQuestions.tsx`, `Documents.tsx`/`report-facts.css`/`voice-memo.css`, and `Prediction.tsx`.
