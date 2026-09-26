"""Rehearse the owned synthetic demo against a fresh, migrated test database.

This deliberately creates only synthetic records. It is not a field-data or ML
validation, and it must never run against a production database.
"""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from nwis.config import get_settings
from nwis.db import connection
from nwis.ingestion.jobs import tick
from nwis.main import app
from nwis.seed import stable_id


def checked(response, status=200):
    if response.status_code != status:
        raise AssertionError(f"Expected HTTP {status}, got {response.status_code}: {response.text}")
    return response.json()


def rehearse():
    settings = get_settings()
    if settings.environment == "production" or settings.extraction_provider != "local_rules":
        raise ValueError("Demo rehearsal requires a non-production local-rules environment")
    with connection() as conn:
        existing = conn.execute("SELECT count(*) AS n FROM dataset").fetchone()["n"]
    if existing:
        raise ValueError("Fresh rehearsal requires an empty migrated database")

    with TestClient(app) as client:
        def auth(token):
            return {"Authorization": f"Bearer {token}"}

        viewer = auth(settings.viewer_token)
        reviewer = auth(settings.reviewer_token)
        engineer = auth(settings.engineer_token)
        admin = auth(settings.admin_token)
        assert client.get("/api/v1/status").status_code == 401
        seeded = checked(client.post("/api/v1/admin/fixtures/golden", headers=admin))
        assert seeded["wells"] == 4 and not seeded["repeated"]
        repeated = checked(client.post("/api/v1/admin/fixtures/golden", headers=admin))
        assert repeated["repeated"] and repeated["wells"] == 0

        dataset = stable_id("dataset", "nwis-synthetic-golden-v1")
        source_bore = stable_id("wellbore", "SYN-B-MAIN")
        active_bore = stable_id("wellbore", "SYN-A-MAIN")
        target = stable_id("interval", "A-F1")
        nearby = checked(
            client.get(
                f"/api/v1/wells/nearby?active_well_id={stable_id('well', 'SYN-A')}&radius_km=5",
                headers=viewer,
            )
        )
        assert {item["external_id"] for item in nearby["items"]} == {"SYN-B", "SYN-C"}

        fixture = Path("specs/fixtures/phase3-review-report.txt")
        if not fixture.exists():
            fixture = Path("../specs/fixtures/phase3-review-report.txt")
        report = fixture.read_text()
        report += f"\nRehearsal reference: {uuid4()}\n"
        uploaded = checked(
            client.post(
                "/api/v1/documents",
                data={"dataset_id": str(dataset), "wellbore_id": str(source_bore)},
                files={"file": ("SYNTHETIC-rehearsal.txt", report.encode(), "text/plain")},
                headers=reviewer | {"Idempotency-Key": str(uuid4())},
            ),
            202,
        )
        document = f"/api/v1/documents/{uploaded['id']}"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            tick()
            detail = checked(client.get(document, headers=reviewer))
            if detail["ingest_status"] in ("needs_review", "failed"):
                break
            time.sleep(0.1)
        else:
            raise AssertionError("Synthetic extraction did not finish within 30 seconds")
        assert detail["ingest_status"] == "needs_review" and len(detail["candidates"]) == 1
        candidate = detail["candidates"][0]
        assert candidate["state"] == "needs_review"
        assert client.get(document, headers=viewer).status_code == 404
        approval = checked(
            client.post(
                document + "/review",
                json={
                    "candidate_id": candidate["id"],
                    "expected_version": candidate["version"],
                    "decision": "approve",
                    "rationale": "Verified owned synthetic report and fixture datum for CI rehearsal",
                    "acknowledge_issues": True,
                },
                headers=reviewer | {"Idempotency-Key": str(uuid4())},
            )
        )
        assert approval["state"] == "approved"
        reviewed = checked(client.get(document, headers=reviewer))
        event_id = reviewed["candidates"][0]["canonical_event_id"]
        assert event_id
        passage_id = detail["pages"][0]["id"]
        assert checked(client.get(document, headers=viewer))["candidates"][0]["state"] == "approved"

        comparison = checked(
            client.get(
                f"/api/v1/wellbores/{active_bore}/analogues?target_interval_id={target}&radius_km=5",
                headers=viewer,
            )
        )
        mapped = [
            mapping
            for offset in comparison["items"]
            for mapping in offset["mappings"]
            if mapping["event_id"] == event_id
        ]
        assert len(mapped) == 1 and mapped[0]["mapped_start_md_m"] == 2130
        assert mapped[0]["mapped_end_md_m"] == 2140
        query = checked(
            client.post(
                "/api/v1/query",
                json={"dataset_id": str(dataset), "question": "mud losses", "hazard": "mud_loss"},
                headers=viewer,
            )
        )
        assert event_id in {item["id"] for item in query["items"]}
        evidence = checked(
            client.get(f"/api/v1/events/{event_id}/evidence/{passage_id}", headers=viewer)
        )
        assert evidence["page_number"] == 1 and "1930 to 1940 m MD" in evidence["quote"]
        unsupported = checked(
            client.post(
                "/api/v1/query",
                json={"dataset_id": str(dataset), "question": "nonexistentunicorn"},
                headers=viewer,
            )
        )
        assert not unsupported["items"]
        assert unsupported["abstention_reason"] == "no_approved_supporting_evidence"

        created = checked(
            client.post(
                "/api/v1/replay-sessions",
                json={},
                headers=engineer | {"Idempotency-Key": str(uuid4())},
            ),
            201,
        )
        session = f"/api/v1/replay-sessions/{created['id']}"
        assert created["source_mode"] == "SIMULATED"
        observations = []
        for expected_md in (2029, 2030, 2030, 2031, 2141):
            before = checked(client.get(session, headers=viewer))
            sample = checked(
                client.post(
                    session + "/control",
                    json={"action": "step", "expected_version": before["session"]["revision"]},
                    headers=engineer | {"Idempotency-Key": str(uuid4())},
                )
            )
            assert sample["md_m"] == expected_md
            snapshot = checked(client.get(session, headers=viewer))
            assert snapshot["source_mode"] == "SIMULATED"
            assert snapshot["risk_score"] is None and snapshot["risk_reason"] == "model_not_available"
            alerts = snapshot["alerts"]
            if expected_md == 2029:
                assert not alerts
            else:
                assert len(alerts) == 1
                assert any(item["passage_id"] == passage_id for item in alerts[0]["evidence"])
            observations.append({"md_m": expected_md, "alert_count": len(alerts)})
        assert snapshot["session"]["state"] == "completed"
        assert snapshot["alerts"][0]["relevance"] == "passed"
        assert snapshot["alerts"][0]["seen_count"] == 3
        return {
            "scenario": "golden-mud-loss-v1",
            "source_mode": "SIMULATED",
            "fresh_database_required": True,
            "ingestion_reviewed": True,
            "cited_event": True,
            "mapping_m": [2130, 2140],
            "abstention_checked": True,
            "observations": observations,
            "risk_score": None,
            "risk_reason": "model_not_available",
            "field_or_ml_validation": False,
        }


def main():
    parser = argparse.ArgumentParser(description="Run the owned synthetic demo end to end")
    parser.parse_args()
    print(json.dumps(rehearse(), indent=2))


if __name__ == "__main__":
    main()
