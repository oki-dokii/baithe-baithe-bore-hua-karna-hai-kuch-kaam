"""Prospective, append-only decision digest chain; not external notarization."""

import argparse
import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import UUID

from psycopg.types.json import Jsonb

from nwis.db import connection

GENESIS = "0" * 64


def canonical(row: dict) -> bytes:
    timestamp = row["recorded_at"].astimezone(timezone.utc).isoformat(timespec="microseconds")
    body = {
        "sequence": row["sequence"],
        "recorded_at": timestamp,
        "actor_name": row["actor_name"],
        "action": row["action"],
        "entity_type": row["entity_type"],
        "entity_id": str(row["entity_id"]),
        "payload": row["payload"],
        "previous_hash": row["previous_hash"],
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(row: dict) -> str:
    return hashlib.sha256(canonical(row)).hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def append_decision(
    conn,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: UUID,
    payload: dict,
) -> int:
    """Append inside the caller's transaction so the decision and source row commit together."""
    state = conn.execute(
        "SELECT last_sequence,last_hash FROM decision_chain_state WHERE singleton=true FOR UPDATE"
    ).fetchone()
    if state is None:
        raise RuntimeError("Decision chain state is missing")
    row = {
        "sequence": state["last_sequence"] + 1,
        "recorded_at": datetime.now(timezone.utc),
        "actor_name": actor,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload,
        "previous_hash": state["last_hash"],
    }
    entry_hash = digest(row)
    conn.execute(
        """INSERT INTO decision_ledger(sequence,recorded_at,actor_name,action,entity_type,
        entity_id,payload,previous_hash,entry_hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            row["sequence"],
            row["recorded_at"],
            actor,
            action,
            entity_type,
            entity_id,
            Jsonb(payload),
            row["previous_hash"],
            entry_hash,
        ),
    )
    conn.execute(
        "UPDATE decision_chain_state SET last_sequence=%s,last_hash=%s WHERE singleton=true",
        (row["sequence"], entry_hash),
    )
    return row["sequence"]


def verify_rows(rows: Iterable[dict], state: dict) -> dict:
    previous = GENESIS
    count = 0
    for row in rows:
        expected_sequence = count + 1
        if row["sequence"] != expected_sequence:
            return {"ok": False, "checked": count, "error": "sequence_gap"}
        if row["previous_hash"] != previous:
            return {"ok": False, "checked": count, "error": "broken_link"}
        if row["entry_hash"] != digest(row):
            return {"ok": False, "checked": count, "error": "entry_digest_mismatch"}
        previous = row["entry_hash"]
        count += 1
    if state["last_sequence"] != count or state["last_hash"] != previous:
        return {"ok": False, "checked": count, "error": "head_mismatch"}
    return {"ok": True, "checked": count, "head": previous}


def verify(conn) -> dict:
    state = conn.execute(
        "SELECT last_sequence,last_hash FROM decision_chain_state WHERE singleton=true"
    ).fetchone()
    if state is None:
        return {"ok": False, "checked": 0, "error": "missing_chain_state"}
    with conn.cursor(name="nwis_decision_ledger_verify") as rows:
        rows.execute("SELECT * FROM decision_ledger ORDER BY sequence")
        return verify_rows(rows, state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the local decision ledger without printing payloads")
    parser.parse_args()
    with connection() as conn:
        result = verify(conn)
    print(json.dumps(result, indent=2))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
