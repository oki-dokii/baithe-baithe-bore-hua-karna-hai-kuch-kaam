# Provisional public-report reference set

Prepared 2026-09-27. This is an analyst page-verified **reference set**, not domain-approved drilling evidence, a scored retrieval benchmark or ML labels. The [machine-readable annotations](../../specs/evaluation/public-report-reference-v1.json) contain paraphrased source-page facts and hard negatives; the [fixed questions](../../specs/evaluation/public-retrieval-questions-v1.json) contain reference item IDs. Neither file contains raw report pages or substantial extracted text. All report PDFs and OCR remain in ignored local storage. The three reports are Norwegian offshore examples, not OIL/Assam analogues.

| Source | Identity | PDF pages | Reference items | Integrity |
|---|---|---:|---:|---|
| NOD-511 | [25/10-2 R report](https://factpages.sodir.no/pbl/wellbore_documents/511_25_10_2_R_COMPLETION_REPORT_AND_LOG.pdf) | 58 | 10 | Pages 7, 19 and 20 visually checked; SHA-256 pinned; loss-depth conflict [remains flagged](../phase-2/real-source-qualification.md) |
| NOD-399 | [31/2-6 well summary](https://factpages.sodir.no/pbl/wellbore_documents/399_01_31_2_6_Well_summary_by_Anchor.pdf) | 38 | 8 | Page 23 rendered and compared to text layer; SHA-256 pinned |
| NOD-6599 | [35/7-1 S completion report](https://factpages.sodir.no/pbl/wellbore_documents/6599_35_7_1_S_COMPLETION_DRILLING_REPORT.pdf) | 166 | 7 | Pages 14 and 17 rendered and compared to text layer; SHA-256 pinned |

The set has **25 page-verified items**: 9 observed events, 7 hard negatives, 4 action/outcome statements and 5 context statements. Eighteen fixed questions cover source facts, depth/datum, mitigation, negative flow checks, wrong-domain/no-support answers and the NOD-511 conflict. Item boundaries intentionally distinguish a fish-bottom depth from a stuck-pipe onset, a riser-level drop from a loss volume, a leak-off test from a loss incident, and a negative check from a positive influx. The additional NOD-511 context tracks losses at 7,745 ft and continuing through drilling to 7,773 ft, which may explain the rounded 2,369 m summary as a later episode depth. NOD-511's 7,733 ft remains source-reported but **not** approved as normalized MD or an alert trigger.

Run metadata and optional local file-integrity checks from the repository root:

```sh
backend/.venv/bin/python -m nwis.public_reference
backend/.venv/bin/python -m nwis.public_reference --raw-dir data/raw/sodir
```

The second command verifies SHA-256 and PDF page counts against the three ignored originals. It reports counts and gate flags only; it does not approve any event or publish report text. Unit tests reject malformed source/page IDs, missing event types, incorrect no-support answers and falsely elevated approval status. The machine-readable set must be frozen before tuning extraction/retrieval to it; changes need a documented revision.

The reference set is now a **development diagnostic**, because its pages were used to refine conservative extraction rules v2. It is not an independent held-out test set. A separate untouched corpus is required for unbiased accuracy claims. The [question-scope manifest](../../specs/evaluation/public-retrieval-scope-v1.json) classifies the 18 fixed questions as 6 event-retrieval, 10 report-fact QA and 2 conflict-blocked; it does not map them to approved passage IDs or create a score.

The [isolated ingestion run](public-benchmark-ingestion-2026-09-27.md) now has all three pinned PDFs staged as unreviewed documents. To inspect how those local copies line up with the frozen reference pages, run the read-only candidate audit from `backend` with its **public-report dataset** UUID:

```sh
.venv/bin/python -m nwis.public_passage_audit --dataset-id YOUR_PUBLIC_DATASET_UUID
```

It matches documents by pinned PDF hash, lists page passage UUIDs, same-hazard draft IDs and counts approved events of the matching hazard type. It emits no report text and writes no database records. `draft_review_required` is only a page-level candidate, **not** a correct extraction. `claim_level_review_required` means an approved event occurs on the same page, but a reviewer must still establish that the exact reference statement supports that specific event and question. `R002` is always `disputed_depth_blocked`; this audit cannot clear the 25/10-2 R depth conflict. Hard negatives and contextual facts are marked `not_event_indexed`, because current search indexes approved event claims, not arbitrary report facts. Consequently the 18-question reference set is **not** directly scorable as an event-retrieval benchmark, even after page IDs are present; separate event-retrieval and report-QA scopes before assigning scores.

## Initial local-rules probe, not a benchmark score

The existing conservative extractor was run read-only on OCR from NOD-511 page 7 and text layers from NOD-399 page 23 and NOD-6599 page 14. It produced 2, 2 and 2 candidates respectively. It found the 7,733 ft loss and a stuck-pipe statement, but no equipment-loss candidate; it found the 31/2-6 lost-circulation statement and later slight losses, but left both depths null and missed the 1,485 m partial returns; it found the 1,855 m MD RKB loss but also treated that section heading as a second event, and missed the positive-flow/kill-return incidents. This is a **diagnostic sample**, not precision/recall: page segmentation and candidate-to-reference matching were not frozen, and the three selected pages do not represent all 262 PDF pages. Do not turn these observations into model-performance claims.

## Gates still open

1. Independent domain reviewer confirms event boundaries, depths/datum, wellbore attribution and rights before these labels become a gold set. The NOD-511 loss depth needs an independent DDR/log or an explicit conflict adjudication; no source-derived alert may use it in the meantime.
2. Ingest qualified files locally with the appropriate page cap and preserve database passage UUIDs. Map the fixed question references to **approved** passage UUIDs, then use `nwis.retrieval_eval` to measure recall@5 and abstention. The current JSON question set is not directly executable against that API and no public-report retrieval score is claimed.
3. Evaluate extraction on a **new, untouched held-out corpus** with a defined candidate-to-reference match rule and count true/false positives, missing fields and citation correctness. These three reports can support development diagnostics only. A visual page check by this assistant is not independent domain review.

NOD's [content policy](https://www.sodir.no/en/about-us/use-of-content/) and [released-data guidance](https://www.sodir.no/en/facts/data-and-analyses/release-of-data/use-of-released-data/) should be rechecked before any report redistribution or deployment. This repository commits only source links, identifiers, hashes and short paraphrased annotations.
