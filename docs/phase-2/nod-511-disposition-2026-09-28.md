# NOD-511 depth discrepancy — final triage disposition

Checked 2026-09-28 against the SHA-256-pinned, 58-page local copy of the [25/10-2 R completion report](https://factpages.sodir.no/pbl/wellbore_documents/511_25_10_2_R_COMPLETION_REPORT_AND_LOG.pdf) (`960aaeed8d8a439f098537ca1c01b2d9e99da19f748fa3f57fbd284424e37de5`) and the [NOD wellbore summary](https://factpages.sodir.no/en/wellbore/PageView/With/Wdss/511). Scanned pages 7, 10, 19 and 20 were rendered and visually rechecked. This is analyst source triage, **not** independent drilling-engineer adjudication.

| Source location | What it establishes | What it does not establish |
|---|---|---|
| PDF p. 7, “Drilling Problems” | Re-entry narrative reports lost circulation at **7,733 ft**, then stuck pipe and sidetrack. | Incident page does not explicitly specify MD/KB datum or an exact timestamp. Do not silently alter 7,733 to 7,773. |
| PDF p. 10, re-entry stratigraphy | Drill-depth table states **KB 31 feet**. | A table heading is not direct proof of the p. 7 incident's depth axis/datum. |
| PDF p. 19, 14 May sample sheet | Records **65 bbl lost at 7,745 ft**, with a pressure-surge question. | The note is not proof that 7,745 ft was the first loss. |
| PDF p. 20, 15 May sample sheet | Says circulation was still being lost, and notes drilling to **7,773 ft** with **400 bbl lost over eight hours**. | Later drilled depth and cumulative loss are not an onset. |
| NOD FactPage | Summarizes loss at about **2,369 m**. | It does not explain its chosen source depth or supersede the scanned narrative. |

Arithmetic: 7,733 ft = **2,357.02 m**, while 7,773 ft = **2,369.21 m**. The rounded FactPage value is numerically consistent with the *later* 7,773-ft depth. The plausible explanation is that the summary compressed a continuing loss episode and used its later depth. This is an **inference**, not a correction of the p. 7 statement or proof of onset. No independently dated DDR/log or accountable drilling review in the reviewed material resolves which depth should be normalized for an event.

**Decision:** close the source-triage question, but leave the operational evidence gate **blocked**. Preserve R002 as a source-reported 7,733-ft observation with `axis=null`, `datum=null`, and `disputed_depth_blocked`; keep R023–R025 as later context, not onset labels. PQ01/PQ18 remain conflict-answerable research questions, not operational facts. Do not approve a normalized MD, infer formation-specific alert depth, use this case as an ML positive onset label, or claim a correct real-report retrieval score. This follows the user's earlier direction to keep the conflict flagged.

**Local database audit:** the pinned PDF's SHA-256 identifies one `needs_review` document with two drafts and **zero approved events cited to that document**. The broader development dataset `NOD-511-source-trial` does contain 15 `approved` mud-loss rows, but all 15 cite owned test files (`owned-test.txt`, `owned-pdf.pdf` or `owned-scan.pdf`), carry unresolved-quality flags, and sit at 304.8 m; none has an alert-evidence link. These are test artifacts, **not** approval of NOD-511. Do not use a dataset-wide approved-event count as a real-report claim. This read-only audit made no status changes.

**Unlock condition:** obtain a contemporaneous drilling log/DDR with time/depth and explicit reference, or a documented decision by an authorized drilling engineer who reviews the conflicting pages and states onset, depth axis, datum, wellbore and uncertainty. Separately settle report-specific usage rights and independent claim review. A new source or decision should be appended to the qualification record; it must not overwrite these four source facts.
