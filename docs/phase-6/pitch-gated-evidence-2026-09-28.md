# NWIS pitch: evidence before prediction

Use this as a ~75-second SIH spoken pitch. “Real” below means the input report is authentic; it does **not** mean its extracted claims are approved for operations. Confirm the official SIH problem ID before submission.

> A drilling engineer needs the current well's data, but also the hard-won lessons in nearby wells. That knowledge is often buried in completion reports and daily drilling records. NWIS is a standalone decision-support layer beside eRTMAC: it puts nearby wells on a map and turns historical reports into traceable, searchable evidence.
>
> Our differentiator is the gate between extraction and action. We can ingest real scanned public drilling reports, preserve the document and page, and produce candidate incidents. A human reviewer must verify the event, depth, datum, wellbore and citation before it can become an approved case or support an alert. If evidence is absent or contradictory, NWIS abstains. In one real report, the loss-depth narrative conflicts with the regulator's summary. We show that conflict; we do not invent a corrected depth.
>
> In the live demo, an owned **synthetic** report goes through that review gate. A cited offset-well loss then appears on the map and triggers one formation-relative replay alert at the expected depth. The score is explicitly unavailable—this is an evidence-backed rule, not a validated ML prediction. We have not connected to OIL's live eRTMAC feed or trained a field-ready risk model. To cross those gates, we need authorized OIL data, independently reviewed labels and no-event coverage, held-out-well evaluation, and a reviewed read-only feed contract. We are building institutional memory without pretending uncertainty has disappeared.

## Four-minute demo cues

1. **Real documents in, staged:** show the public-report registry/preview (three pinned Norwegian reports, 262 pages, 54 initial drafts). Say “authentic public source, not OIL offsets; staged, not operationally approved.” Do not show source PDFs outside permitted local use or claim a real-report accuracy score.
2. **Cited review:** open the owned synthetic report candidate, inspect the page/citation, approve with the reviewer role, then open its case. Mention document and page remain attached, and unapproved drafts are excluded from search/alerts.
3. **One cautious alert:** on synthetic `SYN-A`, show `SYN-B` within 5 km, mapped 2130–2140 m, no alert at 2029 m, one at 2030 m. Point to the supporting page and `risk_score: null / model_not_available`.
4. **Refusal moment:** show the no-support query's abstention and the NOD-511 conflict disposition. The answer is “7,733 ft is what the report states; 2,369 m is the summary; later losses near 7,773 ft plausibly explain the difference, but onset is not approved.”

Use the pinned-document view for NOD-511, not a dataset-wide approved count from the older development database: that database also contains owned test events under the source-trial dataset. The pinned NOD PDF itself has two unreviewed drafts and zero approved linked events.

## Claims the team may and may not make

| Safe, evidenced claim | Do not say |
|---|---|
| Real public PDFs were ingested, OCR'd and staged for review. | “Our real reports are approved offset intelligence.” |
| Synthetic end-to-end ingest, cited approval, mapping, abstention and one alert passed a fresh-database rehearsal. | “We predict mud loss in OIL wells” or “the alert is field validated.” |
| The NOD-511 discrepancy is transparently retained and blocked. | “We resolved the onset as 2,369 m” or “7,733 ft was an OCR typo.” |
| NWIS can show historical response links and an alert budget in replay. | “A mitigation caused the outcome,” “the cap is conformal,” or “critical alerts are safely suppressible.” |

## If judges ask about ML or eRTMAC

**“Where is the ML?”** The training pipeline and approval/readiness gates exist, but no real-data model passed them. We need pre-event telemetry joined to independently reviewed incident times/depths, reviewed no-event coverage, held-out wells, calibration and an alert-burden denominator. Until then the product displays an unavailable score and uses cited historical rules.

**“Is this integrated with Oil India?”** No. We designed a read-only adapter boundary, but OIL must approve the actual eRTMAC interface, identifiers, units, security and data rights. The judged demo is a standalone synthetic replay plus separately staged real public documents.

**“Why show a conflict?”** Because a false precision can be worse than an abstention. The report and summary disagree about the loss depth. Showing both with source pages, keeping the event out of alerts, and recording what evidence would unlock it is the safety property we can demonstrate today.

Supporting records: [2026-09-28 rehearsal](rehearsal-2026-09-28.md), [NOD-511 disposition](../phase-2/nod-511-disposition-2026-09-28.md), [public-report ingestion](public-benchmark-ingestion-2026-09-27.md), and [Phase 5 ML gate](../phase-5/README.md).
