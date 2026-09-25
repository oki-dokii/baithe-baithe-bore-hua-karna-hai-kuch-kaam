"""Integration smoke check against a running Phase 1 Compose stack."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from nwis.config import get_settings
from nwis.db import connection
from nwis.seed import stable_id


def request(method: str, path: str, token: str | None = None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = Request(f"http://127.0.0.1:8000{path}", headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def main() -> None:
    settings = get_settings()
    status, _ = request("GET", "/api/v1/status")
    assert status == 401, "Protected status endpoint allowed anonymous access"
    status, _ = request("POST", "/api/v1/admin/fixtures/golden", settings.viewer_token)
    assert status == 403, "Viewer could mutate fixture data"
    status, body = request("GET", "/api/v1/status", settings.viewer_token)
    assert status == 200 and body["database"]["state"] == "ready"
    assert body["spatial"]["state"] == "ready" and body["vector"]["state"] == "ready"
    assert body["source_mode"] == "SIMULATED" and body["prediction"]["state"] == "not_implemented"

    status, first = request("POST", "/api/v1/admin/fixtures/golden", settings.admin_token)
    assert status == 200 and first["wells"] in (0, 4), first
    status, repeat = request("POST", "/api/v1/admin/fixtures/golden", settings.admin_token)
    assert status == 200 and repeat["repeated"] and repeat["wells"] == 0, repeat

    status, page = request("GET", "/api/v1/wells?kind=synthetic", settings.viewer_token)
    assert status == 200 and {w["external_id"] for w in page["items"]} >= {
        "SYN-A", "SYN-B", "SYN-C", "SYN-D"
    }
    active = stable_id("well", "SYN-A")
    status, nearby = request(
        "GET", f"/api/v1/wells/nearby?active_well_id={active}&radius_km=5", settings.viewer_token
    )
    assert status == 200 and {w["external_id"] for w in nearby["items"]} == {
        "SYN-B", "SYN-C"
    }, nearby
    status, _ = request(
        "GET", f"/api/v1/wells/nearby?active_well_id={active}&radius_km=0", settings.viewer_token
    )
    assert status == 422

    with connection() as conn:
        users = conn.execute("SELECT username, role FROM app_user ORDER BY username").fetchall()
        assert {(u["username"], u["role"]) for u in users} == {
            ("local-admin", "admin"), ("local-engineer", "engineer"),
            ("local-reviewer", "reviewer"), ("local-viewer", "viewer"),
        }
        assert conn.execute("SELECT count(*) AS n FROM audit_log WHERE actor_name='local-admin'").fetchone()["n"] >= 2
        row = conn.execute(
            "SELECT review_state FROM drilling_event WHERE id=%s", (stable_id("event", "SYN-E-B-001"),)
        ).fetchone()
        assert row["review_state"] == "draft"
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "0003_document_ingestion"
        try:
            with conn.transaction():
                conn.execute(
                    """INSERT INTO drilling_event(id, wellbore_id, event_type, start_md_m)
                       VALUES (%s,%s,'mud_loss',-1)""",
                    (uuid4(), stable_id("wellbore", "SYN-B-MAIN")),
                )
        except Exception as exc:
            assert getattr(exc, "sqlstate", None) == "23514", exc
        else:
            raise AssertionError("Negative depth bypassed database CHECK constraint")

    print("Phase 1 smoke passed: auth, extensions, migration, fixture repeatability, spatial query, constraints")


if __name__ == "__main__":
    main()
