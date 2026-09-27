# First real-source qualification — NOD wellbore 25/10-2 R

Checked 2026-09-26. This is a local public-source trial, separate from the fictional SYN-A/SYN-B fixture. It does not establish applicability to Assam or OIL wells, and it does not provide predictive training labels.

## Source register

| Field | Recorded value |
|---|---|
| Publisher / source index | Norwegian Offshore Directorate (NOD), [wellbore FactPage 511](https://factpages.sodir.no/en/wellbore/PageView/Exploration/With/Wdss/511) |
| Source PDF | [511_25_10_2_R_COMPLETION_REPORT_AND_LOG.pdf](https://factpages.sodir.no/pbl/wellbore_documents/511_25_10_2_R_COMPLETION_REPORT_AND_LOG.pdf) |
| Local copy | `data/raw/sodir/511_25_10_2_R_COMPLETION_REPORT_AND_LOG.pdf` (ignored, never committed) |
| SHA-256 | `960aaeed8d8a439f098537ca1c01b2d9e99da19f748fa3f57fbd284424e37de5` |
| PDF profile | 58 pages; 11,155,104 bytes; unlocked scanned PDF; first three pages have no useful text layer |
| Well / wellbore | 25/10-2 / 25/10-2 R; NOD wellbore ID 511; North Sea, Norway |
| Original coordinates | 59° 9′ 39.27″ N, 2° 11′ 35.88″ E, **ED50**. The local well point is transformed to WGS84 by PostGIS; original CRS is retained here. |
| Depth metadata | NOD reports MD and TVD in m RKB, RKB elevation 9 m MSL. The scanned narrative reports depths in feet without an explicit MD/KB notation on the incident page. Local depth-reference review remains `needs_review`. |
| Copyright/use | NOD's [site content policy](https://www.sodir.no/en/about-us/use-of-content/) requests date, reference and source link; NOD's [released-data guidance](https://www.sodir.no/en/facts/data-and-analyses/release-of-data/use-of-released-data/) warns that third-party rights may remain. Analyse locally; do not commit or redistribute the PDF or substantial extracted text until report-specific rights are established. |

## Source inspection

- PDF page 1 visibly identifies a geological summary/completion report for *Esso 25/10-2 (re-entry)*, dated July 1972. PDF page 7 has a clearly readable **Drilling Problems** section: it reports lost circulation at 7,733 ft, followed by a stuck-pipe event and sidetrack. The page was visually checked against local OCR.
- PDF page 10 visibly labels its re-entry stratigraphy table **“KB 31 feet”** and its column “Drill Depth (feet).” This gives a report-wide clue to the depth convention, but page 7 does **not** explicitly label the incident depth as MD/KB. Do not promote that clue to an approved event datum without domain review.
- 7,733 ft converts mathematically to **2,357.02 m**. The [NOD wellbore summary](https://factpages.sodir.no/en/wellbore/PageView/Exploration/With/Wdss/511) describes the loss around **2,369 m**. A simple unit or uniform datum conversion cannot turn 7,733 ft into 2,369 m. Three control depths in the same summary match their report values after conversion to roughly 0.5 m, so the 12 m difference is specific to this loss narrative.
- **Further primary-source check, 2026-09-27:** PDF page 19 is a dated May 14, 1972 wellsite sample sheet. Its 7,730-7,740 ft row notes **65 bbl lost at 7,745 ft** (with a question about a pressure surge). PDF page 20, dated May 15, has a 7,760-7,770 ft row marked as **still losing circulation** and notes drilling to **7,773 ft**, with **400 bbl lost over eight hours**. Both pages were rendered and visually checked, not inferred from OCR alone. 7,773 ft converts to **2,369.21 m**, aligning with NOD's rounded 2,369 m. This makes a **loss episode continuing from the page-7 report depth through the later 7,773 ft drilling depth** a plausible contextual reconciliation; the FactPage likely summarizes the later depth. That last interpretation is an inference, not a verified statement about the exact onset.
- **Adjudication:** preserve all four distinct source facts: page 7's 7,733 ft encounter statement, page 19's 7,745 ft loss tally, page 20's continuing losses and 7,773 ft/400-bbl note, and the FactPage's rounded 2,369 m summary. Do not replace 7,733 with 7,773 as an OCR correction, and do not assign 7,745 or 7,773 as the onset. Episode progression is a **plausible explanation** of the headline mismatch, not a resolved event-depth decision. The user confirmed on 2026-09-27 that this event must stay **flagged as conflicting** without a DDR or drilling-engineer adjudication. Precise onset, incident-depth axis/datum, formation and wellbore attribution still need accountable domain review before approved MD or alert use.
- The report combines the original well and the re-entry history. The page 7 event belongs to the re-entry narrative, but precise wellbore attribution, coordinate equivalence and depth datum need reviewer confirmation. The local source record is linked only to 25/10-2 R; no approved correlation interval, trajectory or cross-well analogue was created.

## Local ingestion trial

The full PDF is under the default 25 MiB byte limit but exceeds the default 50-page limit by eight pages. The configured worker page cap was raised to 60 **for this local trial only**, with no production default change. The PDF was uploaded to the local development API and linked to a `public` dataset whose qualification status is `source_trial`. Dataset registration is reproducible from the pinned checksum:

```bash
cd backend
python -m nwis.qualify_public ../data/raw/sodir/511_25_10_2_R_COMPLETION_REPORT_AND_LOG.pdf
```

Registration verifies the exact checksum and page count. The local dataset and wellbore IDs are stable; the original ED50 coordinate is transformed to WGS84 for mapping. Existing records are checked for identity conflicts. This only registers source identity; it does not approve extracted claims, map a formation or create a risk model.

Upload document ID: `469ec1d9-4160-46e9-ae12-ed940eacae5a`. The one local extraction job **completed** with 58/58 pages and no job error. All 58 pages required OCR. PDF page 7's extracted text contains the loss sentence and reports OCR confidence approximately 0.894; this numeric confidence is not proof that every word is correct. The source image was visually compared with the incident text.

Two page-7 drafts were produced: `mud_loss` and `stuck_pipe`. Both are still `needs_review`. The mud-loss draft initially missed the numeric depth because the line says “depth of 7733 feet”; the local extractor now recognizes that phrase. A source-checked transcription correction recorded 7,733 feet and incremented the draft to version 2, with audit rationale. The normalized MD and formation remain null because the source axis, datum and formation are unresolved. Its remaining flags are `unknown_depth_axis`, `unknown_depth_datum`, `formation_unresolved` and `ocr_source_verify`. The stuck-pipe draft retains all original review flags. A viewer request for the unapproved document returned 404.

This trial demonstrates real scanned-report OCR, page citation and conservative review staging. It **does not** satisfy the full real-source acceptance gate for a reviewed, depth-resolved event. The added page-19/20 context may explain the FactPage summary, but the event remains flagged as conflicting by user instruction until an accountable source or drilling reviewer adjudicates it. No source-derived alert was created.

## Follow-up source candidate integrity

A second locally staged file named `4652_1_9_7_COMPLETION_DRILLING_REPORT.pdf` is **not qualified**. The local copy is only about 6.4 MiB and `pdfinfo` cannot recover a valid page tree (invalid cross-reference entries, zero usable pages). The [NOD 1/9-7 document listing](https://factpages.sodir.no/en/wellbore/PageView/Exploration/Wdss/4652) lists that report at about 103.62 MiB. Treat the local file as incomplete; do not ingest it, infer events from it, or count it among reviewed reports. Its local SHA-256 is `77f091424b158765a86e9cd003cc5a8fefb7810340291494d12ce9ce15926f35`. The file remains ignored and has not been overwritten or committed.

## Gate status

| Gate | Result |
|---|---|
| Traceable real PDF and well identity | Pass for the specified local source and NOD FactPage |
| Original file integrity | Pass: full local copy checksum and PDF metadata recorded |
| Rights for local analysis | Publicly accessible; report-specific redistribution remains unresolved |
| OCR/source-page trace | Pass for extraction and page 7 visual spot check: 58/58 OCR pages, two cited drafts |
| Event normalization | Partial: source feet transcribed; episode progression gives context, but MD/datum/formation and flagged conflicting depth remain unresolved |
| Reviewer approval and alert eligibility | Unmet: both drafts still `needs_review`; no approved event or mapped alert |
| Multiwell ML labels / negative windows | Unmet: this one historical report does not provide either |

If this trial succeeds, repeat with a second independently identified report and compare cross-well identities, formation tops and survey datums before any public offset analysis.
