# Data register and assumptions

Updated: 2026-09-27. `Candidate` means suitability/access/redistribution has not been established by downloading and inspecting selected files. Public availability is not blanket permission to republish raw data.

## Dataset selection

| Source | Intended role | Current decision / gate |
|---|---|---|
| Owned synthetic scenario | Deterministic demo, negative tests, repeatable replay | Selected; fixture in this repository. All records labeled synthetic |
| Equinor Volve | Candidate real reports, well surveys and drilling context | Access now routes through Databricks Marketplace; no source file qualified in this project |
| Utah FORGE | Public multiwell drilling-telemetry/report qualification pilot | 16A and 56-32 file headers and a 16A operations summary inspected; feature/label/well-group gates open. Geothermal benchmark only, not OIL validation; [audit](../phase-5/dataset-candidates.md) |
| DataDRILL | Possible simulator tutorial for kick detection | On The Rig simulator data; wrong hazard and no field-held-out validation for current task; [audit](../phase-5/dataset-candidates.md) |
| NOD 25/10-2 R | Scanned completion report with mud-loss and stuck-pipe narrative | Full 58-page PDF ingested locally; two OCR drafts retained for review. Depth reconciliation and report-specific redistribution rights remain open; [source record](../phase-2/real-source-qualification.md) |
| FORCE 2020 | Possible later lithology/log experiments | Deferred; do not assume matching Volve wells or hazard labels |
| Petrobras 3W | Possible event-detection experiment | Phase 5 metadata audit: published 2.0.0 class list does not match drilling mud-loss target; not selected ([audit](../phase-5/README.md)) |
| Other Sodir well records | Candidate identity/coordinate cross-check | Later, only with exact external well identifiers |
| Texas RRC scans | OCR stress testing | Deferred; not needed for the first complete scenario |
| OIL WCR/DDRs/eRTMAC | Future domain validation/integration | Not supplied in this project; availability through SIH remains unknown |
| DGH/NDR | Potential future Indian data | Access, terms and timing unverified; do not assert approval is impossible |

Equinor's [official Volve page](https://www.equinor.com/energy/volve-data-sharing) provides dataset access guidance and research-use licensing information. It does not establish which particular reports meet this project's requirements. Before redistribution, record the applicable license, selected artifact names, attribution requirements and source checksums.

The [official 3W project](https://github.com/petrobras/3W) describes an evolving event dataset. Its [dataset documentation](https://github.com/petrobras/3W/blob/main/dataset/README.md) specifies CC BY 4.0 for dataset files and version changes. These facts do not establish that a selected release has appropriate drilling kick/loss/stuck-pipe labels. Do not carry the draft TRD's label assertion into model implementation without a class/feature audit.

## Real-source qualification record

Before importing each subset, record: source URL, release/commit, download date, license/attribution, selected files and checksums, well identities, source CRS/depth datum, units, report quality, available event labels, coverage and missing fields. Record redistribution separately from permission to analyze. Retain original locations and formation identity; never present foreign wells as observed Assam wells.

The first local report trial used NOD wellbore 25/10-2 R after Volve access could not be completed without a Databricks account. Its [qualification record](../phase-2/real-source-qualification.md) documents real scanned-report OCR and unresolved depth/rights gates. Volve remains a candidate for a drilling report with associated header and survey. The synthetic scenario remains runnable but cannot satisfy the real-source gate.

## Assumptions and follow-up

| ID | Item | Treatment / revisit point |
|---|---|---|
| A01 | Official SIH year/PS ID | Unverified draft metadata; confirm before pitch/submission |
| A02 | OIL sample data | Not provided; revisit when organizer material arrives |
| A03 | Team size and deadline | Unknown; backlog is dependency-based, without invented calendar estimates |
| A04 | Volve access and usable subset | Candidate; official access currently uses Databricks Marketplace and requires account access. A separate NOD 25/10-2 R scanned report was trialed locally; see the [qualification record](../phase-2/real-source-qualification.md). |
| A05 | 3W label compatibility | Published 2.0.0 metadata incompatible with chosen drilling mud-loss target; no raw-file qualification or training performed |
| A14 | Utah FORGE mud-loss labels | Narrative evidence exists, but exact onsets, negative coverage and positive-well count are not reviewed. Sampled telemetry lacks the required mud-density feature; [qualification plan](../phase-5/dataset-candidates.md). |
| A06 | Cross-source spatial overlap | No assumed overlap; validate using well identity, original CRS and authoritative coordinates |
| A07 | Formation mapping | Prototype heuristic; domain review required before operational use |
| A08 | Cloud model provider/budget | Unselected; adapter permits a later choice; do not send future private documents by default |
| A09 | Physical feature inputs | ECD/kick-tolerance calculations require validated inputs and formulas; absent inputs mean unavailable, not guessed |
| A10 | Rig-day rate | Optional illustrative input only; no OIL rate assumed |
| A11 | ONGC NPT/rig-cost percentages and policy claims in draft PRD | Not independently verified; excluded from factual pitch claims pending primary citations |
| A12 | Model sufficiency | Requires relevant labels and held-out wells; no promise of a calibrated probability per hazard |
| A13 | Licensing | No repository software license chosen; third-party source licenses remain separate |

These follow-ups do not block platform scaffolding. Real-data provenance blocks claims of real-source validation; suitable labels block claims of predictive accuracy; official metadata blocks publishing an asserted SIH identifier. Do not treat an open question as a completed result.
