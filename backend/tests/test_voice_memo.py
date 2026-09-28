import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from nwis.config import get_settings
from nwis.db import connection
from nwis.ingestion.jobs import tick
from nwis.main import app
from nwis.seed import load_fixture, stable_id
from nwis.voice import typed_transcript
from nwis.voice_retention import purge_expired_audio


def test_typed_voice_transcript_preserves_language_without_fake_confidence():
    result = typed_transcript("  Mud losses at 1930 m MD.  ", "en")
    assert result.text == "Mud losses at 1930 m MD."
    assert result.confidence is None
    with pytest.raises(Exception):
        typed_transcript(" ", "hi")
    with pytest.raises(Exception):
        typed_transcript("Some note", "xx")


@pytest.mark.skipif(os.getenv("NWIS_INTEGRATION") != "1", reason="Needs NWIS test DB")
def test_voice_upload_uses_document_review_and_purges_audio(monkeypatch, tmp_path: Path):
    client = TestClient(app)
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_root", tmp_path)
    engineer = {"Authorization": f"Bearer {settings.engineer_token}",
                "Idempotency-Key": str(uuid4())}
    reviewer = {"Authorization": f"Bearer {settings.reviewer_token}"}
    viewer = {"Authorization": f"Bearer {settings.viewer_token}"}
    dataset = stable_id("dataset", "nwis-synthetic-golden-v1")
    bore = stable_id("wellbore", "SYN-B-MAIN")
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
    payload = {"dataset_id": str(dataset), "wellbore_id": str(bore),
               "language": "en", "transcript": "Mud losses at 1930 m MD.", "consent": "true"}
    audio = b"RIFF" + b"\x00" * 4 + b"WAVE" + uuid4().bytes + b"\x00" * 32
    files = {"audio": ("memo.wav", BytesIO(audio), "audio/wav")}
    assert client.post("/api/v1/voice-memos", data={**payload, "consent": "false"},
                       files=files, headers=engineer).status_code == 422
    files = {"audio": ("memo.wav", BytesIO(audio), "audio/wav")}
    assert client.post("/api/v1/voice-memos", data=payload,
                       files=files, headers=viewer).status_code == 403
    files = {"audio": ("memo.wav", BytesIO(audio), "audio/wav")}
    uploaded = client.post("/api/v1/voice-memos", data=payload, files=files, headers=engineer)
    assert uploaded.status_code == 202, uploaded.text
    document_id = uploaded.json()["id"]
    assert uploaded.json()["doc_type"] == "voice_memo"
    for _ in range(10):
        with connection() as conn:
            row = conn.execute("SELECT ingest_status FROM source_document WHERE id=%s",
                               (document_id,)).fetchone()
        if row["ingest_status"] == "needs_review":
            break
        assert tick()
    detail = client.get(f"/api/v1/documents/{document_id}", headers=reviewer)
    assert detail.status_code == 200, detail.text
    data = detail.json()
    assert data["doc_type"] == "voice_memo"
    assert data["pages"][0]["raw_text"] == "Mud losses at 1930 m MD."
    assert data["pages"][0]["transcription_confidence"] is None
    assert data["pages"][0]["transcription_language"] == "en"
    assert all(candidate["state"] == "needs_review" for candidate in data["candidates"])
    assert "voice_transcript_verify" in data["candidates"][0]["issues"]
    assert client.get(f"/api/v1/documents/{document_id}/audio", headers=viewer).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/audio", headers=reviewer).content == audio
    corrected = client.post(f"/api/v1/voice-memos/{document_id}/transcript",
        json={"expected_review_version": data["review_version"],
              "text": "Mud losses at 1931 m MD.",
              "rationale": "Verified the depth against the audio"},
        headers={**engineer, "Idempotency-Key": str(uuid4())})
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["text_version"] == 2
    revised = client.get(f"/api/v1/documents/{document_id}", headers=reviewer).json()
    assert revised["pages"][0]["raw_text"] == "Mud losses at 1931 m MD."
    assert any(item["state"] == "rejected" for item in revised["candidates"])
    new_candidate = next(item for item in revised["candidates"] if item["state"] == "needs_review")
    body = {"candidate_id": new_candidate["id"], "expected_version": new_candidate["version"],
            "decision": "approve", "rationale": "Listened to the original audio",
            "fields": new_candidate["current_fields"], "acknowledge_issues": True}
    unverified = client.post(f"/api/v1/documents/{document_id}/review", json=body,
        headers={**reviewer, "Idempotency-Key": str(uuid4())})
    assert unverified.status_code == 422
    verified = client.post(f"/api/v1/documents/{document_id}/review",
        json={**body, "voice_audio_verified": True},
        headers={**reviewer, "Idempotency-Key": str(uuid4())})
    assert verified.status_code == 200, verified.text
    with connection() as conn:
        conn.execute("UPDATE voice_memo SET audio_retention_until=now()-interval '1 second' WHERE document_id=%s",
                     (document_id,))
    assert purge_expired_audio() >= 1
    assert client.get(f"/api/v1/documents/{document_id}/audio", headers=reviewer).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}", headers=reviewer).json()["pages"][0]["raw_text"]
