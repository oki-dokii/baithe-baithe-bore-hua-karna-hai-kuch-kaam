import math
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from nwis.config import get_settings
from nwis.db import connection
from nwis.main import app
from nwis.retrieval_eval import Benchmark, evaluate
from nwis.seed import load_fixture, stable_id

pytestmark = pytest.mark.skipif(
    os.getenv("NWIS_INTEGRATION") != "1", reason="Requires NWIS test database"
)


def test_spatial_correlation_filtered_search_and_citations():
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {get_settings().viewer_token}"}
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
    active = stable_id("wellbore", "SYN-A-MAIN")
    target = stable_id("interval", "A-F1")
    url = f"/api/v1/wellbores/{active}/analogues?target_interval_id={target}&radius_km=5"
    assert client.get(url).status_code == 401
    result = client.get(url, headers=headers)
    assert result.status_code == 200, result.text
    nearby = result.json()["items"]
    assert [r["name"] for r in nearby] == ["SYN-B", "SYN-C"]
    expected = 6371008.8 * math.acos(
        math.sin(math.radians(27)) ** 2
        + math.cos(math.radians(27)) ** 2 * math.cos(math.radians(0.01))
    )
    assert abs(nearby[0]["surface_distance_m"] - expected) < 5
    boundary = nearby[0]["surface_distance_m"] / 1000
    for radius, included in [(boundary - 0.001, False), (boundary + 0.001, True)]:
        data = client.get(
            f"/api/v1/wellbores/{active}/analogues?target_interval_id={target}&radius_km={radius}",
            headers=headers,
        ).json()
        assert any(r["name"] == "SYN-B" for r in data["items"]) is included
    assert nearby[0]["similarity_score"] > nearby[1]["similarity_score"]
    assert "reservoir_properties" in nearby[0]["missing_components"]
    assert (
        client.get(
            f"/api/v1/events/{stable_id('event', 'SYN-E-B-001')}", headers=headers
        ).status_code
        == 404
    )
    event_id = uuid4()
    dataset = stable_id("dataset", "nwis-synthetic-golden-v1")
    passage = stable_id("passage", "SYN-DDR-B-001:1")
    with connection() as conn:
        conn.execute(
            """INSERT INTO drilling_event(id,wellbore_id,formation_interval_id,event_type,start_md_m,end_md_m,
            description,review_state,source_fields) VALUES(%s,%s,%s,'mud_loss',1930,1940,%s,'approved',%s)""",
            (
                event_id,
                stable_id("wellbore", "SYN-B-MAIN"),
                stable_id("interval", "B-F1"),
                f"SYNTHETIC TEST mud losses zzretrievaleval {event_id}",
                Jsonb({"quote": "Mud losses occurred from 1930 to 1940 m MD."}),
            ),
        )
        conn.execute(
            "INSERT INTO event_passage(event_id,passage_id) VALUES(%s,%s)", (event_id, passage)
        )
    try:
        comparison = client.get(url, headers=headers).json()
        mapped = next(
            m for c in comparison["items"] for m in c["mappings"] if m["event_id"] == str(event_id)
        )
        assert mapped["mapped_start_md_m"] == 2130 and mapped["mapped_end_md_m"] == 2140
        body = {
            "dataset_id": str(dataset),
            "question": "mud losses",
            "hazard": "mud_loss",
            "min_md_m": 1900,
            "max_md_m": 2000,
        }
        found = client.post("/api/v1/query", json=body, headers=headers).json()
        assert str(event_id) in [r["id"] for r in found["items"]]
        cite = client.get(f"/api/v1/events/{event_id}/evidence/{passage}", headers=headers).json()
        assert (
            cite["page_number"] == 1
            and cite["quote"] == "Mud losses occurred from 1930 to 1940 m MD."
        )
        assert "raw_text" not in cite
        assert (
            client.get(f"/api/v1/events/{event_id}/evidence/{uuid4()}", headers=headers).status_code
            == 404
        )
        for change in (
            {"hazard": "kick"},
            {"formation_id": str(stable_id("formation", "SYN-F2"))},
            {"question": "nonexistentunicorn"},
            {"min_md_m": 2400, "max_md_m": 2500},
        ):
            empty = client.post("/api/v1/query", json=body | change, headers=headers).json()
            assert (
                not empty["items"]
                and empty["abstention_reason"] == "no_approved_supporting_evidence"
            )
        assert (
            client.post(
                "/api/v1/query", json=body | {"min_md_m": 2100}, headers=headers
            ).status_code
            == 422
        )
        benchmark = Benchmark.model_validate(
            {
                "schema_version": "retrieval-questions-v1",
                "kind": "synthetic",
                "dataset_id": str(dataset),
                "source_reference": "owned golden fixture",
                "review_reference": "synthetic integration assertions",
                "questions": [
                    {
                        "id": f"SYN-Q{i:02d}",
                        "question": "zzretrievaleval" if i == 0 else f"nonexistentunicorn{i}",
                        "hazard": "mud_loss",
                        "expected_passage_ids": [str(passage)] if i == 0 else [],
                    }
                    for i in range(15)
                ],
            }
        )
        evaluation = evaluate(benchmark, client, get_settings().viewer_token)
        assert evaluation["source_recall_at_5"] == 1
        assert evaluation["correct_abstentions"] == 14
        assert evaluation["gates"]["at_least_15_questions"]
        assert not evaluation["gates"]["real_source"]
    finally:
        # Preserve provenance while removing test-approved evidence from operational reads.
        with connection() as conn:
            conn.execute(
                "UPDATE drilling_event SET review_state='rejected' WHERE id=%s", (event_id,)
            )
    assert client.get(f"/api/v1/events/{event_id}", headers=headers).status_code == 404
