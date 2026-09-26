"""Opt-in tests against an initialized NWIS development/test database; retain audit records."""

import os
import time
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from nwis.config import get_settings
from nwis.db import connection
from nwis.ingestion.jobs import tick
from nwis.main import app
from nwis.seed import load_fixture
from test_ingestion import pdf_bytes

pytestmark = pytest.mark.skipif(
    os.getenv("NWIS_INTEGRATION") != "1", reason="Requires an initialized NWIS database"
)


def test_failed_pdf_retry_and_expired_lease():
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {get_settings().reviewer_token}"}
    option = client.get("/api/v1/document-options", headers=headers).json()[0]
    data = {"dataset_id": option["dataset_id"], "wellbore_id": option["wellbore_id"]}
    uploaded = client.post(
        "/api/v1/documents",
        data=data,
        files={"file": ("broken.pdf", f"%PDF-invalid-{uuid4()}".encode(), "application/pdf")},
        headers=headers | {"Idempotency-Key": str(uuid4())},
    )
    assert uploaded.status_code == 202
    document_id = uploaded.json()["id"]
    path = f"/api/v1/documents/{document_id}"
    for _ in range(100):
        tick()
        detail = client.get(path, headers=headers).json()
        if detail["ingest_status"] == "failed":
            break
        time.sleep(0.1)
    assert detail["ingest_status"] == "failed" and detail["pages"] == []
    assert detail["jobs"][0]["error_code"] == "document_parse_error"
    retry_headers = headers | {"Idempotency-Key": str(uuid4())}
    response = client.post(path + "/retry", headers=retry_headers)
    assert response.status_code == 202
    assert client.post(path + "/retry", headers=retry_headers).json() == response.json()
    # Simulate a worker dying after claim. Reclaim must fail safely, without publishing partial pages.
    with connection() as conn:
        conn.execute(
            """UPDATE ingestion_job SET status='processing', claim_token=%s,
            leased_until=now()-interval '1 second',attempts=1 WHERE document_id=%s AND status='pending'""",
            (uuid4(), document_id),
        )
    for _ in range(100):
        tick()
        detail = client.get(path, headers=headers).json()
        if detail["ingest_status"] == "failed":
            break
        time.sleep(0.1)
    assert detail["ingest_status"] == "failed" and detail["pages"] == []
    with connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM ingestion_job WHERE document_id=%s", (document_id,)
            ).fetchone()["n"]
            == 2
        )


@pytest.mark.parametrize("report_kind", ["text", "pdf", "scan"])
def test_upload_extract_review_and_permissions(report_kind):
    settings = get_settings()
    client = TestClient(app)
    reviewer = {"Authorization": f"Bearer {settings.reviewer_token}"}
    viewer = {"Authorization": f"Bearer {settings.viewer_token}"}
    engineer = {"Authorization": f"Bearer {settings.engineer_token}"}
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
    options = client.get("/api/v1/document-options", headers=reviewer).json()
    option = options[0]
    data = {"dataset_id": option["dataset_id"], "wellbore_id": option["wellbore_id"]}
    text = f"SYNTHETIC TEST {uuid4()}\nDatum: RKB\nFormation: F1\nMud losses at 1000 ft MD.\nNo stuck pipe."
    files = (
        {"file": ("owned-test.txt", text.encode(), "text/plain")}
        if report_kind == "text"
        else {
            "file": (
                f"owned-{report_kind}.pdf",
                pdf_bytes(scanned=report_kind == "scan"),
                "application/pdf",
            )
        }
    )
    key = str(uuid4())
    headers = reviewer | {"Idempotency-Key": key}
    assert (
        client.post(
            "/api/v1/documents", data=data, files=files, headers=viewer | {"Idempotency-Key": key}
        ).status_code
        == 403
    )
    first = client.post("/api/v1/documents", data=data, files=files, headers=headers)
    assert first.status_code == 202, first.text
    document_id = first.json()["id"]
    path = f"/api/v1/documents/{document_id}"
    assert (
        client.post("/api/v1/documents", data=data, files=files, headers=headers).json()
        == first.json()
    )
    duplicate = client.post(
        "/api/v1/documents",
        data=data,
        files=files,
        headers=reviewer | {"Idempotency-Key": str(uuid4())},
    )
    assert duplicate.json()["id"] == document_id and duplicate.json()["duplicate"]
    different = {"file": ("another.txt", b"Mud losses at 2000 m MD.", "text/plain")}
    assert (
        client.post("/api/v1/documents", data=data, files=different, headers=headers).status_code
        == 409
    )
    assert client.get(path, headers=viewer).status_code == 404
    for _ in range(100):
        tick()
        detail = client.get(path, headers=reviewer).json()
        if detail["ingest_status"] in ("needs_review", "failed"):
            break
        time.sleep(0.1)
    assert detail["ingest_status"] == "needs_review", detail
    assert len(detail["pages"]) == 1 and len(detail["candidates"]) == 1
    assert detail["pages"][0]["ocr_applied"] is (report_kind == "scan")
    candidate = detail["candidates"][0]
    with connection() as conn:
        assert (
            conn.execute(
                "SELECT canonical_event_id FROM document_event_draft WHERE id=%s",
                (candidate["id"],),
            ).fetchone()["canonical_event_id"]
            is None
        )
    payload = {
        "candidate_id": candidate["id"],
        "expected_version": 1,
        "decision": "approve",
        "rationale": "Verified against source page",
        "acknowledge_issues": True,
    }
    assert (
        client.post(
            path + "/review", json=payload, headers=engineer | {"Idempotency-Key": str(uuid4())}
        ).status_code
        == 403
    )
    key2 = str(uuid4())
    headers2 = reviewer | {"Idempotency-Key": key2}
    approved = client.post(path + "/review", json=payload, headers=headers2)
    assert approved.status_code == 200, approved.text
    assert client.post(path + "/review", json=payload, headers=headers2).json() == approved.json()
    assert (
        client.post(
            path + "/review", json=payload, headers=reviewer | {"Idempotency-Key": str(uuid4())}
        ).status_code
        == 409
    )
    public = client.get(path, headers=viewer).json()
    assert public["pages"] == [] and len(public["candidates"]) == 1 and public["audit"] == []
    assert public["candidates"][0]["state"] == "approved"
    page_id = detail["pages"][0]["id"]
    assert client.get(path + f"/pages/{page_id}/preview", headers=viewer).status_code == 403
    assert (
        client.post(
            path + "/retry", headers=reviewer | {"Idempotency-Key": str(uuid4())}
        ).status_code
        == 409
    )
    reviewed = client.get(path, headers=reviewer).json()
    assert reviewed["ingest_status"] == "reviewed" and len(reviewed["audit"]) == 1
    with connection() as conn:
        event = conn.execute(
            """SELECT e.* FROM drilling_event e JOIN document_event_draft d ON d.canonical_event_id=e.id WHERE d.id=%s""",
            (candidate["id"],),
        ).fetchone()
        assert float(event["start_md_m"]) == 304.8 and event["source_depth_unit"] == "ft"
        assert event["review_state"] == "approved" and event["quality_issues"]
    # A reviewer may add missed evidence, but must cite an exact source span.
    manual = {
        "page_number": 1,
        "expected_version": reviewed["review_version"],
        "fields": candidate["current_fields"] | {"quote": "Invented source"},
        "rationale": "Testing manual review",
    }
    assert (
        client.post(
            path + "/candidates", json=manual, headers=reviewer | {"Idempotency-Key": str(uuid4())}
        ).status_code
        == 422
    )
    manual["fields"] = candidate["current_fields"]
    created = client.post(
        path + "/candidates", json=manual, headers=reviewer | {"Idempotency-Key": str(uuid4())}
    )
    assert created.status_code == 201, created.text
    correction = {
        "candidate_id": created.json()["id"],
        "expected_version": 1,
        "decision": "correct",
        "fields": candidate["current_fields"] | {"severity": "high"},
        "rationale": "Verified severity",
    }
    corrected = client.post(
        path + "/review", json=correction, headers=reviewer | {"Idempotency-Key": str(uuid4())}
    )
    assert corrected.status_code == 200 and corrected.json()["version"] == 2
    correction.update(decision="reject", expected_version=2, rationale="Duplicate evidence")
    assert (
        client.post(
            path + "/review", json=correction, headers=reviewer | {"Idempotency-Key": str(uuid4())}
        ).status_code
        == 200
    )
    with connection() as conn:
        audit = conn.execute(
            "SELECT before_value,after_value FROM review_decision WHERE entity_id=%s AND action='correct'",
            (created.json()["id"],),
        ).fetchone()
        assert (
            audit["before_value"]["severity"] is None and audit["after_value"]["severity"] == "high"
        )
