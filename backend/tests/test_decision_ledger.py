from datetime import datetime, timezone
from uuid import uuid4

from nwis.decision_ledger import GENESIS, digest, verify_rows


def sample_row(sequence: int, previous_hash: str) -> dict:
    row = {
        "sequence": sequence,
        "recorded_at": datetime(2026, 9, 27, 10, sequence, tzinfo=timezone.utc),
        "actor_name": "test-reviewer",
        "action": "review_reject",
        "entity_type": "document_event_draft",
        "entity_id": uuid4(),
        "payload": {"version": sequence, "rationale_sha256": "a" * 64},
        "previous_hash": previous_hash,
    }
    row["entry_hash"] = digest(row)
    return row


def test_chain_detects_edit_removal_and_head_rewrite():
    first = sample_row(1, GENESIS)
    second = sample_row(2, first["entry_hash"])
    state = {"last_sequence": 2, "last_hash": second["entry_hash"]}
    assert verify_rows([first, second], state)["ok"]
    assert verify_rows([first, {**second, "payload": {"version": 99}}], state)["error"] == (
        "entry_digest_mismatch"
    )
    assert verify_rows([second], state)["error"] == "sequence_gap"
    assert verify_rows([first], state)["error"] == "head_mismatch"
    assert verify_rows([first, {**second, "previous_hash": GENESIS}], state)["error"] == (
        "broken_link"
    )
