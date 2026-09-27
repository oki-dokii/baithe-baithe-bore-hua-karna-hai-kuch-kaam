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
    first = client.post("/api/v1/report-facts", json=raw, headers=reviewer)
    assert first.status_code == 201, first.text
    found = client.post("/api/v1/report-facts/ask", json=ask, headers=viewer).json()
    assert found["status"] == "answered" and found["answer"] == "1930 m MD"
    assert found["citations"][0]["page_number"] == 1
    assert "raw_text" not in found["citations"][0]
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
