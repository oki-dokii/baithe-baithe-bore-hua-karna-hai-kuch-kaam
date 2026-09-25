# Golden demo and evaluation

## Fixed scenario

The [fixture](../../specs/fixtures/golden-demo.json) is an owned synthetic contract, not OIL data or an empirical geological model. All depths are m, all wells are vertical with MD=TVD, and all use the same explicit synthetic reference elevation. Synthetic formation names do not certify real local geology.

Active well `SYN-A` has formation interval 2000–2300 m. Offset `SYN-B`, within a 5 km surface radius, has the same reviewed formation interval at 1800–2100 m and a reviewed mud-loss event at 1930–1940 m. Formation-relative mapping produces active interval 2130–2140 m. `SYN-C` is nearby but has a different formation; `SYN-D` has the same formation but is outside the radius. Neither supports the golden alert.

## Script and expected results

1. Ingest the fixture's synthetic report as a page-preserving document; extract the mud-loss interval and the recorded action/outcome. Initially it is draft, and cannot trigger an operational alert.
2. Review the values and approve. Display `SYN-B` on the map and open its cited case. Duplicate upload/retry must not duplicate records.
3. Choose `SYN-A`, 5 km radius, 100 m lookahead, the synthetic formation interval and a new replay session. Show mapped depths and raw offset depths side by side.
4. At active MD 2029 m, no alert. At 2030 m, the inclusive window reaches 2130 m and creates one NEW alert. Risk score is null, reason `model_not_available`.
5. Repeat ticks at 2030/2031 m and reconnect. Retain one episode, updating count/last-seen. Acknowledge it without claiming the hazard is resolved.
6. At 2141 m, mark relevance passed. Record engineer action and an unknown/observed outcome separately. Do not auto-label no observed incident as a false positive.
7. Pause receipt beyond the stale threshold: show stale cached state and stop new alert evaluation. Reset via a new replay session and reproduce the original trigger.

## Negative and edge fixtures for implementation

- Unapproved or rejected event: excluded from operational alert/search evidence.
- Wrong formation, out-of-radius, or active well itself: excluded as offset support.
- Missing source page: flagged for evidence review; no approved sourced assertion.
- Unknown MD datum/unit; missing formation base; ambiguous formation occurrence: unresolved mapping, no invented active depth.
- Inclined well with MD != TVD: use survey mapping; never silently copy MD.
- Negative formation thickness or event outside source formation: invalid mapping.
- Exact radius boundary: use inclusive distance <= radius with a documented numerical tolerance.
- Two supporting events in one episode band: one alert with both evidence links.
- Event correction/revocation: invalidate mappings/cache; retained alerts show changed-evidence review state.
- Replay restart, duplicated/out-of-order messages, concurrent ticks: no unintended duplicate episodes.
- Provider outage: preserve draft job/failure; previously approved evidence remains available.

## Separate evaluation tracks

Synthetic regression verifies software behavior only. A real-source track must independently ingest a licensed public report and preserve actual text/page evidence; do not relocate its well into synthetic Assam geography or attach fabricated real-world hazards. Qualification selects specific files and records checksums before this track is claimed complete.

For extraction, create a manually reviewed reference set of at least 20 passages across at least 3 reports where feasible, including scanned text and hard negatives. Report exact document count, event detection precision/recall, field accuracy (depth/unit/type), missing-value errors, and citation correctness. These are prototype sample targets, not a claim of statistical representativeness. Keep evaluation passages out of extraction tuning examples.

For retrieval, maintain at least 15 fixed questions: hazard/formation/depth filters, mitigation/outcomes, wrong-dataset cases, and questions without evidence. Record source recall@5, unsupported-claim count and correct abstentions. Golden fixtures require zero unsupported claims; public-report results are measured and disclosed.

For alerts, measure event recall and lead distance/time on labeled replay cases, plus false alerts per operating hour (or per 100 m for depth-only replay), duplicate notifications, and missed hazards. Cooldown reduces repeated notifications; it does not measure or improve semantic false-positive rate by itself. Define the matching interval/horizon and denominator before scoring.

For ML, qualify features and labels first, group all records from a physical well and its sidetracks into one split, preserve chronology within prediction windows, and prevent outcome-text/future-telemetry leakage. Fit transforms on training data only; tune on validation wells; evaluate once on held-out wells. Synthetic replicas of a real well remain in the same group. Report sample/well counts, class balance, precision/recall/F1 and PR-AUC where valid, with uncertainty limitations. Compare against a simple prevalence or rules baseline. Calibrate on validation data before calling scores probabilities; report alert lead time for an explicitly defined prediction horizon. Insufficient positives/wells means the model gate remains open.

No quantitative predictive performance or operational ROI is established by Phase 0.
