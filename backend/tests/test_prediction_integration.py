import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from nwis.config import get_settings
from nwis.main import app
from nwis.seed import stable_id

pytestmark = pytest.mark.skipif(
    os.getenv("NWIS_INTEGRATION") != "1", reason="Requires NWIS test database"
)


def test_readiness_and_absent_risk():
    client = TestClient(app)
    assert client.get("/api/v1/prediction/readiness").status_code == 401
    headers = {"Authorization": f"Bearer {get_settings().viewer_token}"}
    result = client.get("/api/v1/prediction/readiness", headers=headers)
    assert result.status_code == 200
    assert result.json()["model_version"] is None
    assert result.json()["metrics"] is None
    wellbore = stable_id("wellbore", "SYN-A-MAIN")
    risk = client.get(f"/api/v1/risk/current/{wellbore}", headers=headers)
    assert risk.status_code == 200
    assert risk.json()["score"] is None
    assert risk.json()["reason"] == "model_not_available"
    assert client.get(f"/api/v1/risk/current/{uuid4()}", headers=headers).status_code == 404
