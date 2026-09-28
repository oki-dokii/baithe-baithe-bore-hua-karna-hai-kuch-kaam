# Public-report claim pre-review — 2026-09-28

This is an analyst triage of the **development** corpus, not drilling-engineer approval, ground truth for ML, or an API retrieval score. The 25 frozen [reference items](../../specs/evaluation/public-report-reference-v1.json) were compared to rendered source pages and the 54 v1 drafts in the isolated `nwis_public_benchmark` database. A page match is not a claim match. No staged event was approved or changed. The NOD-511 depth conflict remains blocked.

| Reference | Source PDF page | Claim-level disposition against current v1 draft | Next reviewer check |
|---|---:|---|---|
| R001 | NOD-511 7 | Hard negative; original phase described as normal | Do not infer incident |
| R002 | NOD-511 7 | Loss draft `a0bcad04` quotes 7,733 ft, but onset/axis/datum conflict unresolved | Keep approval and alert use blocked; independent log or explicit adjudication required |
| R003 | NOD-511 7 | Stuck-pipe draft `49e4e9fc` has no onset depth; 7,262 ft is fish bottom | Confirm event boundary from page image; never copy fish depth to onset |
| R004 | NOD-511 7 | Sidetrack is a response/outcome, not a new event | Link to R003 only if reviewer agrees |
| R005 | NOD-511 7 | Six lost cones at 8,192 ft: no v1 equipment-loss draft | Decide `other` taxonomy and exact claim span; v2 rule is development-only |
| R006 | NOD-511 7 | Coring interval hard negative | Do not label nearby loss/stuck pipe |
| R007 | NOD-511 10 | Stratigraphy gives KB context, not incident-page datum proof | Leave R002 datum unset |
| R008 | NOD-399 23 | Leak-off test at 825 m is a hard negative | Do not label uncontrolled loss |
| R009 | NOD-399 23 | Loss draft `2b4766e7` captures hazard but omits 1,305 m | Correct reported depth only after reviewer checks claim span; axis/datum unknown |
| R010 | NOD-399 23 | Reduced pump rate/regained circulation is response/outcome | Link to R009, not separate onset |
| R011 | NOD-399 23 | Partial returns at 1,485 m lack a dedicated v1 draft | Decide continuation versus distinct episode before event counting |
| R012 | NOD-399 23 | Mica/reduced strokes left partial returns | Do not mark mitigation successful |
| R013 | NOD-399 23 | Tight hole at 1,400 m is not stuck pipe | Hard negative for stuck-pipe extraction |
| R014 | NOD-399 23 | LCM circulation before cementing is preparation | Hard negative for incident/cementing failure |
| R015 | NOD-6599 14 | Draft `c909820d` has 1,855 m MD but omits explicit RKB; `886ff334` is a heading-like duplicate | Verify original S wellbore, RKB and duplicate rejection |
| R016 | NOD-6599 14 | 40 m describes riser-level drop | Do not use as event depth or loss volume |
| R017 | NOD-6599 14 | LCM/cement/lower-weight attempts did not restore circulation | Record attempts as unsuccessful/unknown, not cures |
| R018 | NOD-6599 14 | T2 later drilled without losses | Hard negative for T2 loss |
| R019 | NOD-6599 14 | Flow check at 3,876 m was negative | Hard negative for kick at that depth |
| R020 | NOD-6599 14 | Positive 400 L flow at 3,893 m has no v1 kick draft | Reviewer to check wellbore, depth axis/datum and claim span; v2 candidate is not approval |
| R021 | NOD-6599 14 | Returns were lost during kill, distinct from earlier 1,855 m loss | Same-page mud-loss drafts do not prove this later claim; no independent onset depth |
| R022 | NOD-399 23 | Draft `6e5eb6f9` captures slight losses while reaming; source supplies no onset depth | Preserve null depth; do not borrow adjacent 1,400/1,485 m |
| R023 | NOD-511 19 | Later 65 bbl loss tally at 7,745 ft is context, not proven onset | Keep linked to unresolved episode only |
| R024 | NOD-511 20 | Losses continued in 7,760–7,770 ft sample interval | Interval is not onset |
| R025 | NOD-511 20 | 7,773 ft later drilled depth with 400 bbl/8 h loss | Near rounded 2,369 m summary but does not resolve R002 |

Draft IDs above are shortened prefixes for navigation; use the full UUID in the reviewer UI/database. Candidate passage UUIDs are NOD-511 p7 `739a7377-3787-4283-bde5-0ad3d483bd88`, NOD-399 p23 `dac91463-6d43-4fe2-9280-8c701c93cada`, and NOD-6599 p14 `59009a43-3bb7-4186-ae7e-3456bdec2a53`. The three pages were rendered or visually checked against their source PDFs; this is not domain adjudication. Report-fact QA references (negatives, responses, context) must not be counted as event-index retrieval failures.

Reviewer handoff: for every proposed event, record exact source page and claim span, polarity/negation, original versus sidetrack wellbore, onset versus later observation, depth value/unit/axis/datum, mitigation and observed effectiveness, and a keep/correct/reject decision with reviewer/date. Separately record whether source rights permit the intended use. Do not promote any draft merely because this packet calls it a candidate. In particular, R002 remains conflict-blocked until new evidence or accountable adjudication.
