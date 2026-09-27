"""Database guards and concurrent append checks on an isolated integration database."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import CheckViolation

from nwis.config import get_settings
from nwis.db import connection
from nwis.decision_ledger import append_decision, verify
from nwis.main import app
from nwis.seed import load_fixture, stable_id

pytestmark = pytest.mark.skipif(
    os.getenv("NWIS_INTEGRATION") != "1", reason="Requires an initialized NWIS test database"
)


def test_unqualified_public_event_and_cross_dataset_citation_are_rejected():
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
    dataset_id, well_id, bore_id, event_id, document_id, passage_id = [uuid4() for _ in range(6)]
    with connection() as conn:
        try:
            conn.execute(
                """INSERT INTO dataset(id,external_id,name,kind,version,qualification_status,
                origin_kind,authorization_state,applicability)
                VALUES(%s,%s,'Test public source','public','1','staged_unreviewed',
                'public_primary','unverified','review_only')""",
                (dataset_id, str(dataset_id)),
            )
            with pytest.raises(CheckViolation), conn.transaction():
                conn.execute(
                    "UPDATE dataset SET applicability='direct_offset' WHERE id=%s", (dataset_id,)
                )
            conn.execute(
                """INSERT INTO well(id,dataset_id,external_id,name,surface_point)
                VALUES(%s,%s,%s,'Test well',ST_SetSRID(ST_MakePoint(2,59),4326)::geography)""",
                (well_id, dataset_id, str(well_id)),
            )
            conn.execute(
                "INSERT INTO wellbore(id,well_id,external_id) VALUES(%s,%s,%s)",
                (bore_id, well_id, str(bore_id)),
            )
            with pytest.raises(CheckViolation), conn.transaction():
                conn.execute(
                    """INSERT INTO drilling_event(id,wellbore_id,event_type,review_state)
                    VALUES(%s,%s,'mud_loss','approved')""",
                    (event_id, bore_id),
                )
            conn.execute(
                "INSERT INTO source_document(id,dataset_id,external_id,filename,mime_type) VALUES(%s,%s,%s,'public.txt','text/plain')",
                (document_id, dataset_id, str(document_id)),
            )
            conn.execute(
                "INSERT INTO extracted_passage(id,document_id,page_number,raw_text) VALUES(%s,%s,1,'Test')",
                (passage_id, document_id),
            )
            with pytest.raises(CheckViolation), conn.transaction():
                conn.execute(
                    "INSERT INTO event_passage(event_id,passage_id) VALUES(%s,%s)",
                    (stable_id("event", "SYN-E-B-001"), passage_id),
                )
        finally:
            conn.rollback()  # Temporary test records never enter another test's dataset.


def test_concurrent_append_and_immutability():
    def write_one(n: int) -> int:
        with connection() as conn:
            return append_decision(
                conn, actor="integration-test", action="check", entity_type="test",
                entity_id=uuid4(), payload={"worker": n},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        sequences = list(pool.map(write_one, (1, 2)))
    assert max(sequences) - min(sequences) == 1
    with connection() as conn:
        assert verify(conn)["ok"]
        with pytest.raises(CheckViolation), conn.transaction():
            conn.execute(
                "UPDATE decision_ledger SET actor_name='forged' WHERE sequence=%s",
                (sequences[0],),
            )
        with pytest.raises(CheckViolation), conn.transaction():
            conn.execute("TRUNCATE decision_ledger")
        assert verify(conn)["ok"]


def test_well_api_exposes_synthetic_provenance_without_operational_claim():
    with connection() as conn:
        load_fixture(conn, Path("../specs/fixtures/golden-demo.json"))
    client = TestClient(app)
    response = client.get(
        "/api/v1/wells?kind=synthetic",
        headers={"Authorization": f"Bearer {get_settings().viewer_token}"},
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["origin_kind"] == "synthetic"
    assert item["authorization_state"] == "synthetic"
    assert item["applicability"] == "demo_only"
    assert item["qualification_status"] == "demo_fixture"
