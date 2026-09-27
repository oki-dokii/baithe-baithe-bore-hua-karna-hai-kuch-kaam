import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from nwis.config import get_settings
from nwis.db import connection
from nwis.main import app
from nwis.seed import load_fixture, stable_id

pytestmark = pytest.mark.skipif(
    os.getenv("NWIS_INTEGRATION") != "1", reason="Requires NWIS test database"
)


def test_reviewed_fact_answer_conflict_and_withdrawal():
    client = TestClient(app)
    reviewer = {"Authorization": f"Bearer {get_settings().reviewer_token}"}
    viewer = {"Authorization": f"Bearer {get_settings().viewer_token}"}
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
    dataset = stable_id("dataset", "nwis-synthetic-golden-v1")
    passage = stable_id("passage", "SYN-DDR-B-001:1")
    raw = {
        "dataset_id": str(dataset),
        "passage_id": str(passage),
        "fact_key": f"loss_depth_{uuid4().hex}",
        "answer": "1930 m MD",
        "quote": "Mud losses occurred from 1930 to 1940 m MD.",
        "rationale": "Checked the synthetic source sentence against page one.",
    }
    ask = {"dataset_id": raw["dataset_id"], "fact_key": raw["fact_key"]}
    assert (
        client.post("/api/v1/report-facts/ask", json=ask, headers=viewer).json()["status"]
        == "no_answer"
    )

    assert client.post("/api/v1/report-facts", json=raw, headers=viewer).status_code == 403
    bad = client.post(
        "/api/v1/report-facts", json={**raw, "quote": "Invented quote"}, headers=reviewer
    )
    assert bad.status_code == 422
    assert (
        client.post(
            "/api/v1/report-facts",
            json={key: value for key, value in raw.items() if key != "rationale"},
            headers=reviewer,
        ).status_code
        == 422
    )
    first = client.post("/api/v1/report-facts", json=raw, headers=reviewer)
    assert first.status_code == 201, first.text
    found = client.post("/api/v1/report-facts/ask", json=ask, headers=viewer).json()
    assert found["status"] == "answered" and found["answer"] == "1930 m MD"
    assert found["citations"][0]["page_number"] == 1
    assert "raw_text" not in found["citations"][0]
    document_id = found["citations"][0]["document_id"]
    listed = client.get(f"/api/v1/report-facts/documents/{document_id}", headers=viewer)
    assert listed.status_code == 200
    assert any(item["id"] == first.json()["id"] for item in listed.json())
    mapped = client.post(
        "/api/v1/report-facts/questions",
        json={
            **ask,
            "question": "Where did mud losses occur in this synthetic report?",
            "state": "ready",
        },
        headers=reviewer,
    )
    assert mapped.status_code == 201, mapped.text
    public_list = client.get(f"/api/v1/report-facts/questions?dataset_id={dataset}", headers=viewer)
    assert mapped.json()["id"] in [item["id"] for item in public_list.json()]
    premature = client.post(
        "/api/v1/report-facts/questions",
        json={
            **ask,
            "fact_key": f"missing_{uuid4().hex}",
            "question": "What has not been reviewed yet?",
            "state": "ready",
        },
        headers=reviewer,
    )
    assert premature.status_code == 409
    answer_by_question = client.post(
        "/api/v1/report-facts/ask-question",
        json={"question_id": mapped.json()["id"]},
        headers=viewer,
    ).json()
    assert answer_by_question["status"] == "answered"
    blocked = client.post(
        "/api/v1/report-facts/questions",
        json={
            **ask,
            "question": "Is this depth disputed by the source?",
            "state": "conflict_blocked",
            "reason": "Conflicting depths have not been adjudicated",
        },
        headers=reviewer,
    )
    assert blocked.status_code == 201, blocked.text
    blocked_answer = client.post(
        "/api/v1/report-facts/ask-question",
        json={"question_id": blocked.json()["id"]},
        headers=viewer,
    ).json()
    assert blocked_answer["status"] == "conflict" and blocked_answer["answer"] is None
    second = client.post(
        "/api/v1/report-facts", json={**raw, "answer": "1940 m MD"}, headers=reviewer
    )
    assert second.status_code == 201, second.text
    conflict = client.post("/api/v1/report-facts/ask", json=ask, headers=viewer).json()
    assert conflict["status"] == "conflict" and conflict["answer"] is None
    assert (
        client.post(
            f"/api/v1/report-facts/{second.json()['id']}/withdraw", headers=reviewer
        ).status_code
        == 200
    )
    assert (
        client.post("/api/v1/report-facts/ask", json=ask, headers=viewer).json()["status"]
        == "answered"
    )
    assert (
        client.post(
            f"/api/v1/report-facts/{first.json()['id']}/withdraw", headers=reviewer
        ).status_code
        == 200
    )
    assert (
        client.post("/api/v1/report-facts/ask", json=ask, headers=viewer).json()["status"]
        == "no_answer"
    )


def test_ocr_fact_requires_page_image_acknowledgment():
    client = TestClient(app)
    reviewer = {"Authorization": f"Bearer {get_settings().reviewer_token}"}
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
    passage = stable_id("passage", "SYN-DDR-B-001:1")
    with connection() as conn:
        conn.execute("UPDATE extracted_passage SET ocr_applied=true WHERE id=%s", (passage,))
    try:
        body = {
            "dataset_id": str(stable_id("dataset", "nwis-synthetic-golden-v1")),
            "passage_id": str(passage),
            "fact_key": f"ocr_test_{uuid4().hex}",
            "answer": "1930 m MD",
            "quote": "Mud losses occurred from 1930 to 1940 m MD.",
            "rationale": "Checked the synthetic page image.",
        }
        assert client.post("/api/v1/report-facts", json=body, headers=reviewer).status_code == 422
        accepted = client.post(
            "/api/v1/report-facts", json={**body, "ocr_image_verified": True}, headers=reviewer
        )
        assert accepted.status_code == 201, accepted.text
    finally:
        with connection() as conn:
            conn.execute("UPDATE extracted_passage SET ocr_applied=false WHERE id=%s", (passage,))
