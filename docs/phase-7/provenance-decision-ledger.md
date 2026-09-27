# Provenance and decision-chain increment

Implemented after the [Phase 7 plan](README.md). This increment strengthens source-use gates and records **new** reviewer and alert decisions in a verifiable local hash chain. It is not a certification, a field deployment, or a retroactive seal of older history.

## Provenance policy

Migration `0007_provenance_decision_ledger` adds three separate dataset attributes:

| Attribute | Meaning | Fail-closed default |
|---|---|---|
| `origin_kind` | Where the underlying observation came from | `unclassified` |
| `authorization_state` | Whether use rights have been established | `unverified` |
| `applicability` | What the data may be used for | `review_only` |

Existing synthetic datasets backfill to `synthetic / synthetic / demo_only`; public datasets backfill to `public_primary / unverified / review_only`; private datasets remain unclassified and review-only pending an explicit qualification. New inserts default to unclassified/review-only unless the owned synthetic or public staging loaders specify their more precise values. None of these labels means a source is *geologically analogous* to OIL.

Database constraints reject impossible combinations, and a trigger rejects new approved real-source events unless the dataset is `qualified`, has documented permitted/authorized use and is marked `direct_offset` or `analog_only`. Synthetic fixture events may be approved **for the demo** but are never operationally eligible. A second trigger refuses citation links across datasets. The reviewer API checks the same use policy before attempting approval; public staging remains locked. Search/case-file and analogue evidence paths exclude unqualified approved records that may predate the migration. Document and well APIs expose the provenance fields, and the evidence room shows them when a migrated API is available.

Qualification is intentionally not self-service in this increment. An accountable reviewer and rights decision are still required before any real dataset can be elevated; changing a database field without that process would defeat the policy. Existing public reports remain staged and the NOD-511 conflict remains open.

## Decision chain

`decision_ledger` starts at migration time with a zero-hash genesis and sequential entries. It records new manual candidate creation, draft correction/approval/rejection, alert creation with supporting event/passage IDs, lifecycle action and engineer feedback in the *same transaction* as the underlying record. A locked chain-head row serializes concurrent writers; idempotent API retries do not append again. The current canonical format includes sequence, UTC timestamp, actor, action, entity ID, minimal metadata and the previous digest; any future format change will need an explicit versioned migration. Rationale/action text is represented by a SHA-256 digest, not duplicated into the ledger payload. The existing source tables remain the system of record.

From `backend` with the configured database environment, run:

```sh
.venv/bin/python -m nwis.decision_ledger
```

The verifier streams entries in sequence order, checks every link and entry digest against the stored head, and returns only a count/head or an error code. It exits 2 on a mismatch; it prints no report or feedback text. Unit and integration tests cover modification, removal, broken links, head mismatch, concurrent appends, SQL update rejection and the replay/feedback flow.

This is **tamper evidence within one database**, not tamper-proof storage: a sufficiently privileged database operator could rewrite both entries and head, and removal of an entire database or backup is out of scope. Independent signed/off-host checkpoints, access controls, backups, retention and verification after restore are needed before any compliance claim. Events before migration are not backfilled as if they had been hashed at their original time. Browser delivery/view receipts are not yet recorded, so the chain does **not** prove that an alert was shown to a person.

## Validation and rollout

An isolated local database, `nwis_provenance_test`, received the migration from empty state and passed the complete backend suite (93 tests), including the well-provenance API, review, replay and ledger cases. The run also exposed and fixed an older integration test's hidden fixture-order dependency. Static checks and the frontend build passed; the pre-migration public-review preview also passed its desktop/mobile browser smoke with compatibility fallbacks. That preview's older API will not show provenance fields until its database and API are migrated together. Do not migrate a shared or production database without a backup and an explicit deployment window; this migration has no destructive downgrade.

Next increment: independently stored chain checkpoints and authenticated delivery receipts, followed by a reviewer-approved source qualification workflow. Neither should be presented as complete today.
