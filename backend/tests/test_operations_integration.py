import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from nwis.config import get_settings
from nwis.db import connection
from nwis.main import app
from nwis.seed import load_fixture, stable_id

pytestmark = pytest.mark.skipif(
    os.getenv("NWIS_INTEGRATION") != "1", reason="Requires NWIS test database"
)


def test_replay_alert_lifecycle_idempotency_and_stale_receipt():
    client = TestClient(app)
    settings = get_settings()
    engineer = {"Authorization": f"Bearer {settings.engineer_token}"}
    viewer = {"Authorization": f"Bearer {settings.viewer_token}"}
    events = [uuid4(), uuid4()]
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
        for event_id in events:
            conn.execute(
                """INSERT INTO drilling_event(id,wellbore_id,formation_interval_id,event_type,start_md_m,end_md_m,
                description,review_state,source_fields) VALUES(%s,%s,%s,'mud_loss',1930,1940,'SYNTHETIC operations test','approved',%s)""",
                (
                    event_id,
                    stable_id("wellbore", "SYN-B-MAIN"),
                    stable_id("interval", "B-F1"),
                    Jsonb({"quote": "Mud losses occurred from 1930 to 1940 m MD."}),
                ),
            )
            conn.execute(
                "INSERT INTO event_passage(event_id,passage_id) VALUES(%s,%s)",
                (event_id, stable_id("passage", "SYN-DDR-B-001:1")),
            )

    def post(path, body, key=None, headers=None):
        return client.post(
            "/api/v1" + path,
            json=body,
            headers=(headers or engineer) | {"Idempotency-Key": key or str(uuid4())},
        )

    try:
        assert post("/replay-sessions", {}, headers=viewer).status_code == 403
        key = str(uuid4())
        created = post("/replay-sessions", {}, key)
        assert created.status_code == 201, created.text
        assert post("/replay-sessions", {}, key).json() == created.json()
        session_id = created.json()["id"]
        path = f"/replay-sessions/{session_id}"

        def snap():
            return client.get("/api/v1" + path, headers=viewer).json()

        def step():
            data = snap()
            return post(
                path + "/control",
                {"action": "step", "expected_version": data["session"]["revision"]},
            )

        assert snap()["stale"] and snap()["risk_score"] is None
        assert step().json()["md_m"] == 2029
        assert snap()["alerts"] == []
        body = {"action": "step", "expected_version": snap()["session"]["revision"]}
        key = str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: post(path + "/control", body, key), range(2)))
        assert all(r.status_code == 200 for r in responses)
        assert responses[0].json() == responses[1].json()
        data = snap()
        assert data["session"]["next_sequence"] == 2 and len(data["alerts"]) == 1
        alert = data["alerts"][0]
        assert len(alert["evidence"]) >= 2
        alert_id = alert["id"]
        body = {
            "action": "acknowledge",
            "expected_version": alert["revision"],
            "rationale": "Verified synthetic evidence",
        }
        assert post(f"/alerts/{alert_id}/actions", body, headers=viewer).status_code == 403
        key = str(uuid4())
        ack = post(f"/alerts/{alert_id}/actions", body, key)
        assert ack.status_code == 200 and ack.json()["lifecycle"] == "ACKNOWLEDGED"
        assert post(f"/alerts/{alert_id}/actions", body, key).json() == ack.json()
        assert post(f"/alerts/{alert_id}/actions", body).status_code == 409
        assert step().json()["md_m"] == 2030
        assert step().json()["md_m"] == 2031
        assert step().json()["md_m"] == 2141
        data = snap()
        assert len(data["alerts"]) == 1 and data["session"]["state"] == "completed"
        assert (
            data["alerts"][0]["relevance"] == "passed"
            and data["alerts"][0]["lifecycle"] == "ACKNOWLEDGED"
        )
        assert data["alerts"][0]["seen_count"] == 3
        feedback = post(
            f"/alerts/{alert_id}/feedback",
            {
                "action_taken": "Observed the synthetic run",
                "observed_outcome": "no_incident_observed",
                "rationale": "Software rehearsal only",
            },
        )
        assert feedback.status_code == 201 and feedback.json()["adjudicated_label"] is None
        with connection() as conn:
            conn.execute(
                "UPDATE telemetry_sample SET received_at=now()-interval '20 seconds' WHERE replay_session_id=%s",
                (session_id,),
            )
            conn.execute(
                "UPDATE drilling_event SET review_state='rejected' WHERE id=%s", (events[0],)
            )
        data = snap()
        assert data["stale"] and data["alerts"][0]["evidence_changed"]
        assert len(snap()["alerts"]) == 1
        reset = post(
            path + "/control", {"action": "reset", "expected_version": data["session"]["revision"]}
        )
        assert reset.status_code == 200 and reset.json()["id"] != session_id
        assert snap()["session"]["state"] == "stopped"
        fresh = client.get("/api/v1/replay-sessions/" + reset.json()["id"], headers=viewer).json()
        assert fresh["alerts"] == [] and fresh["telemetry"] is None
    finally:
        with connection() as conn:
            conn.execute(
                "UPDATE drilling_event SET review_state='rejected' WHERE id=ANY(%s)", (events,)
            )
