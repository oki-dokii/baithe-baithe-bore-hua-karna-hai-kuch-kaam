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
- 7,733 ft converts mathematically to **2,357.02 m**. The [NOD wellbore summary](https://factpages.sodir.no/en/wellbore/PageView/Exploration/With/Wdss/511) describes a lost-circulation depth around 2,369 m in its history. The approximately 12 m difference remains unresolved; do not silently replace either value or approve a mapped event.
- This is an isolated discrepancy in the checked narrative values, not a general conversion rule: report 7,187 ft = 2,190.60 m versus NOD 2,191 m (original TD); 7,262 ft = 2,213.46 m versus NOD 2,213 m (fish); 8,192 ft = 2,496.92 m versus NOD 2,497 m (sidetrack cones). NOD 2,369 m is approximately 7,772 ft, about 39 ft above the source's 7,733 ft. A transcription/summary error is a **hypothesis**, not a resolved fact.
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

This trial demonstrates real scanned-report OCR, page citation and conservative review staging. It **does not** satisfy the full real-source acceptance gate for a reviewed, depth-resolved event. The reviewer must reconcile the source and FactPage depths before approving a claim. No source-derived alert was created.

## Follow-up source candidate integrity

A second locally staged file named `4652_1_9_7_COMPLETION_DRILLING_REPORT.pdf` is **not qualified**. The local copy is only about 6.4 MiB and `pdfinfo` cannot recover a valid page tree (invalid cross-reference entries, zero usable pages). The [NOD 1/9-7 document listing](https://factpages.sodir.no/en/wellbore/PageView/Exploration/Wdss/4652) lists that report at about 103.62 MiB. Treat the local file as incomplete; do not ingest it, infer events from it, or count it among reviewed reports. Its local SHA-256 is `77f091424b158765a86e9cd003cc5a8fefb7810340291494d12ce9ce15926f35`. The file remains ignored and has not been overwritten or committed.

## Gate status

| Gate | Result |
|---|---|
| Traceable real PDF and well identity | Pass for the specified local source and NOD FactPage |
| Original file integrity | Pass: full local copy checksum and PDF metadata recorded |
| Rights for local analysis | Publicly accessible; report-specific redistribution remains unresolved |
| OCR/source-page trace | Pass for extraction and page 7 visual spot check: 58/58 OCR pages, two cited drafts |
| Event normalization | Partial: source feet transcribed, MD/datum/formation unresolved; conflicting summary depth requires investigation |
| Reviewer approval and alert eligibility | Unmet: both drafts still `needs_review`; no approved event or mapped alert |
| Multiwell ML labels / negative windows | Unmet: this one historical report does not provide either |

If this trial succeeds, repeat with a second independently identified report and compare cross-well identities, formation tops and survey datums before any public offset analysis.
