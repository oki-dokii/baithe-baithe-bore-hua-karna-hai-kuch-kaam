import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from nwis.config import get_settings
from nwis.db import connection
from nwis.main import app
from nwis.operational_views import ExposureInput, suggest_assam_formation
from nwis.seed import load_fixture, stable_id


def test_assam_reference_is_exact_and_non_authoritative():
    assert suggest_assam_formation("  Kopili Formation  ")["code"] == "kopili"
    assert suggest_assam_formation("Kopili hazard at 3000m") is None
    assert suggest_assam_formation("unknown") is None


def test_exposure_input_needs_positive_explicit_rate_and_iso_currency():
    for rate, currency in (("0", "INR"), ("-1", "INR"), ("nan", "INR"), ("1", "rupees")):
        with pytest.raises(ValueError):
            ExposureInput(dataset_id=uuid4(), rig_day_rate=rate, currency=currency)


@pytest.mark.skipif(os.getenv("NWIS_INTEGRATION") != "1", reason="Needs isolated NWIS test DB")
def test_gated_special_operations_and_per_episode_exposure():
    client = TestClient(app)
    viewer = {"Authorization": f"Bearer {get_settings().viewer_token}"}
    dataset = stable_id("dataset", "nwis-synthetic-golden-v1")
    bore = stable_id("wellbore", "SYN-B-MAIN")
    passage = stable_id("passage", "SYN-DDR-B-001:1")
    cited, uncited, fishing_id, npt_id = uuid4(), uuid4(), uuid4(), uuid4()
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
        for event_id in (cited, uncited):
            conn.execute(
                """INSERT INTO drilling_event(id,wellbore_id,event_type,start_md_m,
                   description,review_state) VALUES (%s,%s,'fishing',1950,
                   'Synthetic operational test','approved')""", (event_id, bore),
            )
        conn.execute("INSERT INTO event_passage(event_id,passage_id) VALUES (%s,%s)",
                     (cited, passage))
        conn.execute("INSERT INTO fishing_operation(id,event_id,outcome,duration_h) VALUES (%s,%s,'recovered',12)",
                     (fishing_id, cited))
        conn.execute("INSERT INTO npt_event(id,event_id,duration_h,duration_source) VALUES (%s,%s,12,'synthetic_test')",
                     (npt_id, cited))
    try:
        reference = client.get("/api/v1/reference/assam-formations", headers=viewer)
        assert reference.status_code == 200
        assert reference.json()["status"] == "reference_suggestion_only"
        special = client.get(f"/api/v1/knowledge/special-operations?dataset_id={dataset}",
                             headers=viewer)
        assert special.status_code == 200, special.text
        fishing = next(x for x in special.json()["items"] if x["event_type"] == "fishing")
        assert fishing["sample_count"] == 1
        assert fishing["state"] == "insufficient" and not fishing["outcome_counts"]
        assert [x["event_id"] for x in fishing["cases"]] == [str(cited)]
        exposure = client.post("/api/v1/knowledge/npt-exposure", headers=viewer,
                               json={"dataset_id": str(dataset), "rig_day_rate": "1000", "currency": "INR"})
        assert exposure.status_code == 200, exposure.text
        assert exposure.json()["total"] is None
        assert exposure.json()["items"] == [{"npt_id": str(npt_id), "event_id": str(cited),
            "event_type": "fishing", "formation_name": "Formation unrecorded",
            "duration_h": 12, "duration_source": "synthetic_test", "illustrative_exposure": 500.0}]
        assert client.get(f"/api/v1/knowledge/special-operations?dataset_id={uuid4()}",
                          headers=viewer).status_code == 422
    finally:
        with connection() as conn:
            conn.execute("DELETE FROM npt_event WHERE id=%s", (npt_id,))
            conn.execute("DELETE FROM fishing_operation WHERE id=%s", (fishing_id,))
            conn.execute("DELETE FROM event_passage WHERE event_id=%s", (cited,))
            conn.execute("DELETE FROM drilling_event WHERE id IN (%s,%s)", (cited, uncited))
