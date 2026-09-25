# Phase 0 baseline

Version: 0.1.0 · Recorded: 2026-09-25 · Status: specification complete; implementation unstarted.

This baseline translates the user-supplied problem statement and six HTML drafts into build contracts. Draft document language is reference material. The current user request authorizes Phase 0 and repository setup; subsequent phases remain backlog work.

## Source material

The six drafts reviewed were:

- NWIS — PRD.html
- NWIS — TRD.html
- NWIS — Architecture & Data Flow.html
- NWIS — Database Schema.html
- NWIS — UI_UX Specification.html
- NWIS — Constraints & Assumptions (1).html

Their product intent is preserved in this baseline. Original HTML exports remain with the user; these Markdown documents are the implementation reference. The official SIH identifier/year in the drafts has not been independently verified and is not used as a confirmed project identifier here.

## Decisions relative to the drafts

| Topic | Baseline decision | Reason |
|---|---|---|
| Alert path | Reviewed historical evidence fires deterministic alerts; ML attaches optional context | Resolves diagram/prose ambiguity and works without a model |
| Correlation | Explicit formation-relative mapping with quality and datum checks | Comparing raw MD across wells is not a defined correlation algorithm |
| MVP versus final demonstration | Rules MVP first; predictive-model evidence remains a later SIH acceptance gate | ML is an expected outcome, not optional for claiming full coverage |
| Dataset count | Start with owned synthetic fixtures and a small Volve candidate subset | Six source integrations would dominate the early build |
| 3W | Candidate only, pending label/feature compatibility audit | Dataset name alone does not establish kick/loss/stuck-pipe training labels |
| Coordinates | Preserve original CRS and validate transformations using known well identities | FORCE and Volve must not be assumed to describe the same block or wells |
| Formation aliases | Basin-scoped, reviewed aliases; uncertain matches stay unresolved | A shorthand such as Barail does not automatically establish sandstone lithology |
| Alert evidence | Relational evidence table, source snapshots, versioned rule/config | Preserves referential integrity and reproducibility |
| Review | Draft extraction is searchable only in review; approved facts can support operational answers/alerts | A confidence number alone is insufficient validation |
| Feedback | Store engineer action separately from observed outcome and adjudicated label | A prevented incident is not automatically a false positive |
| Financial label | Illustrative historical NPT exposure | Rig rate × past NPT is not causal proof of savings or cost of inaction |
| Field-lite and deduplication | Core operational scope | Both directly support intended users and usable alerts |
| Fishing advisor | Deferred historical analytics, no continue/sidetrack threshold in MVP | Requires adequate cases and a defensible method |

## Completion checklist

- [x] Problem outcomes mapped to acceptance IDs.
- [x] MVP, later deliverables, and non-goals distinguished.
- [x] Units, coordinate handling, depth references, event and formation contracts defined.
- [x] Provenance, review, model output, evidence links, and alert lifecycle specified.
- [x] REST/WebSocket behavior and primary screens defined.
- [x] Synthetic golden scenario fixed in a machine-readable fixture.
- [x] Dataset candidates, factual uncertainty, and qualification gates recorded.
- [x] Implementation order and exit checks defined.

Completion means the specification is reviewable and sufficient to begin Phase 1. It does not imply that source datasets have been downloaded, real-report extraction verified, a domain expert has approved geological mappings, or any software acceptance test has passed.

Changes to this baseline should record a reason and update the relevant acceptance criteria and fixtures together.
