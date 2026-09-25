from fastapi.testclient import TestClient

from nwis.config import Settings, get_settings
from nwis.main import app
from nwis.security import Principal, current_principal


def test_local_auth_and_role_gate_without_database():
    settings = Settings(
        database_url="postgresql+psycopg://nwis:secret@localhost:5432/nwis",
        viewer_token="viewer-1234567890123456",
        engineer_token="engineer-12345678901234",
        reviewer_token="reviewer-12345678901234",
        admin_token="admin-1234567890123456",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app)
        assert client.get("/healthz").status_code == 200
        response = client.post("/api/v1/admin/fixtures/golden")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        app.dependency_overrides[current_principal] = lambda: Principal("test-viewer", "viewer")
        response = client.post("/api/v1/admin/fixtures/golden")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"
    finally:
        app.dependency_overrides.clear()


def test_configuration_rejects_reused_role_tokens():
    try:
        Settings(
            database_url="postgresql+psycopg://nwis:secret@localhost:5432/nwis",
            viewer_token="same-token-1234567890",
            engineer_token="same-token-1234567890",
            reviewer_token="reviewer-12345678901234",
            admin_token="admin-1234567890123456",
        )
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("Reused role token was accepted")
