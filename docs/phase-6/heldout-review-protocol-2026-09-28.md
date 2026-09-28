# Sealed public-report holdout — 2026-09-28

The [source registry](../../specs/evaluation/public-heldout-sources-v1.json) freezes **two** different NOD PDFs (195 pages total) before reading their report contents or tuning against them. Source-level search snippets were used to screen for likely incident terminology, so this is a **hazard-enriched holdout**, not a random sample or an incident-prevalence estimate. The frozen extractor base is `97779b68d00b2bc0950190b381b894756fdb352c` (main before this registry). Do not update rules, prompts, thresholds, or question wording after seeing these reports and then call the same reports untouched. Any such iteration makes them development data; procure a fresh holdout.

The ignored local files are under `data/raw/sodir/heldout-2026-09-28/`. Verify identities with:

```sh
cd backend
.venv/bin/python -m nwis.public_heldout --raw-dir ../data/raw/sodir/heldout-2026-09-28
```

NOD-4955 was considered but **excluded before the seal**: its 315 pages exceed the current 200-page ingestion cap. The two included PDFs have 98 and 97 pages. No source text, event labels, question answers, or derived embeddings are committed. NOD's [content policy](https://www.sodir.no/en/about-us/use-of-content/) and [released-data guidance](https://www.sodir.no/en/facts/data-and-analyses/release-of-data/use-of-released-data/) warrant a report-specific rights check before any redistribution or operational deployment. Public Norwegian examples are not OIL offsets.

## Evaluation procedure (not yet executed)

1. In a new isolated local database/storage root, verify the two SHA-256 hashes and page counts. Run the frozen extractor revision **once** and export immutable candidate IDs, page citations, fields and run config. Keep outputs private; no approvals or operational alerts.
2. A drilling-domain reviewer, blinded to the candidate list, labels all report pages using a short claim record: report/page/span, event type or hard negative, original/sidetrack wellbore, onset versus subsequent observation, depth/unit/axis/datum, polarity, mitigation/outcome, and ambiguity. A second reviewer adjudicates disagreements. Record rights and reviewer IDs/dates.
3. Freeze the gold records and match rule **before** inspecting predictions: same report + claim span/event boundary + event type; depth correct only if value, unit, axis and datum are supported, with null permitted when unstated. Duplicate candidates count as false positives. A candidate citing only the same page without the right claim does not match. Score extraction recall/precision and field/citation correctness separately, with all ambiguous claims reported but excluded from definitive metrics.
4. Freeze separate retrieval questions **after** gold review: event questions whose answers can be tied to approved event passages; report-fact QA questions over broader page text; contradiction/no-support questions; and conflicts. Event retrieval gets recall@5 and abstention only where approved passage IDs exist. Report-fact QA requires its own index/evaluation, not the event-only index. Do not report one pooled score across these tasks.
5. Report denominators, missing pages/OCR failures, page-level provenance, no-support behavior, uncertainty and rights limits. Keep NOD-511 in development; it is not part of this holdout and its depth discrepancy remains unresolved.

Current state: source identities sealed and locally verified only. There are **zero** holdout labels, reviewed claims, retrieval queries, extraction scores, ML labels or real-data alarms. Independent review and a rights decision are the remaining gates. The development [claim packet](claim-review-packet-2026-09-28.md) is a separate triage aid and must not contaminate this holdout.
