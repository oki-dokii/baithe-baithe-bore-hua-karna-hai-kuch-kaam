"""Pressure chart must show only cited, independently reviewed evidence."""

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
    os.getenv("NWIS_INTEGRATION") != "1", reason="Needs isolated NWIS test DB"
)


def test_reviewed_pressure_band_requires_citations_and_independent_reviewer():
    client = TestClient(app)
    settings = get_settings()
    bore = stable_id("wellbore", "SYN-B-MAIN")
    dataset = stable_id("dataset", "nwis-synthetic-golden-v1")
    document_id, passage_id = uuid4(), uuid4()
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
        last = conn.execute(
            """SELECT COALESCE(MAX(base_md_m),1890) AS md FROM pressure_window_evidence
               WHERE wellbore_id=%s AND top_md_m>=1900 AND base_md_m<=2090
                 AND review_state='approved'""", (bore,)
        ).fetchone()["md"]
        top_md = max(1900, int(last))
        assert top_md + 10 <= 2090, "Synthetic pressure test range exhausted"
        conn.execute(
            """INSERT INTO source_document(id,dataset_id,external_id,filename,mime_type)
               VALUES (%s,%s,%s,'owned-synthetic-pressure-test.txt','text/plain')""",
            (document_id, dataset, str(document_id)),
        )
        conn.execute(
            "INSERT INTO document_wellbore(document_id,wellbore_id) VALUES (%s,%s)",
            (document_id, bore),
        )
        conn.execute(
            """INSERT INTO extracted_passage(id,document_id,page_number,raw_text)
               VALUES (%s,%s,1,%s)""",
            (passage_id, document_id,
             f"SYNTHETIC TEST ONLY: {top_md}-{top_md + 10} m MD; pore pressure 9 ppg, "
             "fracture gradient 13 ppg, mud weight 10 ppg and ECD 10.5 ppg."),
        )
    viewer = {"Authorization": f"Bearer {settings.viewer_token}"}
    engineer = {"Authorization": f"Bearer {settings.engineer_token}",
                "Idempotency-Key": str(uuid4())}
    reviewer = {"Authorization": f"Bearer {settings.reviewer_token}",
                "Idempotency-Key": str(uuid4())}
    before = client.get(f"/api/v1/wellbores/{bore}/mud-window", headers=viewer)
    assert before.status_code == 200, before.text
    body = {"wellbore_id": str(bore),
            "formation_interval_id": str(stable_id("interval", "B-F1")),
            "top_md_m": top_md, "base_md_m": top_md + 10,
            "pore_pressure_ppg": 9, "fracture_gradient_ppg": 13,
            "mud_weight_ppg": 10, "ecd_ppg": 10.5,
            "pressure_passage_id": str(passage_id), "mud_passage_id": str(passage_id)}
    stage = client.post("/api/v1/pressure-windows", json=body, headers=engineer)
    assert stage.status_code == 201, stage.text
    band_id = stage.json()["id"]
    assert band_id not in [item["id"] for item in
                           client.get(f"/api/v1/wellbores/{bore}/mud-window",
                                      headers=viewer).json()["bands"]]
    assert client.post(f"/api/v1/pressure-windows/{band_id}/review",
                       json={"decision": "approve", "rationale": "Synthetic evidence checked"},
                       headers=engineer).status_code == 403
    approve = client.post(f"/api/v1/pressure-windows/{band_id}/review",
                          json={"decision": "approve", "rationale": "Synthetic evidence checked"},
                          headers=reviewer)
    assert approve.status_code == 200, approve.text
    visible = client.get(f"/api/v1/wellbores/{bore}/mud-window", headers=viewer)
    assert visible.status_code == 200, visible.text
    band = next(item for item in visible.json()["bands"] if item["id"] == band_id)
    assert band["pore_pressure_ppg"] == 9
    assert band["pressure_filename"] == "owned-synthetic-pressure-test.txt"
    assert "not a safe mud-weight window" in visible.json()["notice"]
