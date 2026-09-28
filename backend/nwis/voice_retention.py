"""Delete only expired voice-audio blobs; retain reviewed transcript provenance."""

from nwis.db import connection
from nwis.decision_ledger import append_decision
from nwis.ingestion.storage import path_for


def purge_expired_audio() -> int:
    purged = 0
    with connection() as conn:
        rows = conn.execute(
            """SELECT v.document_id,d.storage_key,d.sha256 FROM voice_memo v
               JOIN source_document d ON d.id=v.document_id
               WHERE v.audio_purged_at IS NULL AND v.audio_retention_until<=now()
               ORDER BY v.audio_retention_until FOR UPDATE OF v SKIP LOCKED LIMIT 10"""
        ).fetchall()
        for row in rows:
            key = row["storage_key"]
            if not key or not key.startswith("voice/"):
                raise RuntimeError("Expired voice memo has an invalid storage key")
            path = path_for(key)
            if not path.is_relative_to(path_for("voice")):
                raise RuntimeError("Expired voice memo resolves outside voice storage")
            path.unlink(missing_ok=True)
            conn.execute("UPDATE voice_memo SET audio_purged_at=now() WHERE document_id=%s",
                         (row["document_id"],))
            append_decision(
                conn, actor="nwis-retention", action="voice_audio_purged",
                entity_type="source_document", entity_id=row["document_id"],
                payload={"audio_sha256": row["sha256"], "retained": "reviewed_transcript_only"},
            )
            purged += 1
    return purged
