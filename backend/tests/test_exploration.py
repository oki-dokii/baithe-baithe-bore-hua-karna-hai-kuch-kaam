import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from nwis.config import get_settings
from nwis.db import connection
from nwis.exploration import PlanningPoint
from nwis.main import app
from nwis.seed import load_fixture, stable_id


def test_planning_contract_rejects_reversed_and_nonfinite_depth():
    for extra in ({"min_md_m": 2000, "max_md_m": 1000}, {"longitude": float("nan")}):
        with pytest.raises(ValueError):
            PlanningPoint(dataset_id=uuid4(), **{"latitude": 27, "longitude": 95, **extra})


@pytest.mark.skipif(os.getenv("NWIS_INTEGRATION") != "1", reason="Needs NWIS test DB")
def test_location_picture_depth_track_and_cited_response_graph():
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {get_settings().viewer_token}"}
    dataset = stable_id("dataset", "nwis-synthetic-golden-v1")
    bore = stable_id("wellbore", "SYN-B-MAIN")
    passage = stable_id("passage", "SYN-DDR-B-001:1")
    event_id, mitigation_id = uuid4(), uuid4()
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
        conn.execute(
            """INSERT INTO drilling_event(id,wellbore_id,formation_interval_id,
               event_type,start_md_m,end_md_m,description,review_state)
               VALUES (%s,%s,%s,'mud_loss',1930,1940,'Owned synthetic graph test','approved')""",
            (event_id, bore, stable_id("interval", "B-F1")),
        )
        conn.execute("INSERT INTO event_passage(event_id,passage_id) VALUES (%s,%s)",
                     (event_id, passage))
        conn.execute(
            """INSERT INTO mitigation(id,event_id,action_taken,effectiveness)
               VALUES (%s,%s,'Owned synthetic response','partial')""",
            (mitigation_id, event_id),
        )
    try:
        body = {"dataset_id": str(dataset), "latitude": 27, "longitude": 95.01,
                "radius_km": 3, "formation_id": str(stable_id("formation", "SYN-F1")),
                "min_md_m": 1900, "max_md_m": 2000}
        picture = client.post("/api/v1/planning/offset-picture", json=body, headers=headers)
        assert picture.status_code == 200, picture.text
        data = picture.json()
        assert data["score_kind"] == "historical_count_not_risk"
        assert any(str(event_id) in [e["id"] for e in item["events"]]
                   for item in data["items"])
        assert client.post("/api/v1/planning/offset-picture", json={**body,
               "dataset_id": str(uuid4())}, headers=headers).status_code == 422
        links = client.get(f"/api/v1/knowledge/mitigation-links?dataset_id={dataset}",
                           headers=headers)
        assert links.status_code == 200, links.text
        item = next(item for item in links.json()["items"] if str(event_id) in item["event_ids"])
        assert item["effectiveness_counts"] == {"partial": 1}
        assert "causal" in links.json()["notice"]
        track = client.get(f"/api/v1/wellbores/{bore}/depth-track", headers=headers)
        assert track.status_code == 200, track.text
        assert str(event_id) in [e["id"] for e in track.json()["events"]]
        assert track.json()["intervals"]
        assert "reviewed_casing" in track.json()["missing_lanes"]
    finally:
        with connection() as conn:
            conn.execute("UPDATE drilling_event SET review_state='rejected' WHERE id=%s", (event_id,))
