import pytest
from fastapi.testclient import TestClient

from nwis.config import Settings, get_settings
from nwis.main import app


@pytest.fixture(autouse=True)
def configure_test_settings():
    settings = Settings(
        database_url="postgresql+psycopg://nwis:secret@localhost:5432/nwis",
        viewer_token="viewer-token-12345678",
        engineer_token="engineer-token-1234",
        reviewer_token="reviewer-token-1234",
        admin_token="admin-token-12345678",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.clear()


def test_auth_roles_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/auth/roles")
    assert response.status_code == 200
    data = response.json()
    assert "roles" in data
    role_names = [r["role"] for r in data["roles"]]
    assert "viewer" in role_names
    assert "engineer" in role_names
    assert "reviewer" in role_names
    assert "admin" in role_names


def test_auth_login_with_role_convenience(configure_test_settings):
    settings = configure_test_settings
    client = TestClient(app)
    res = client.post("/api/v1/auth/login", json={"role": "engineer"})
    assert res.status_code == 200
    body = res.json()
    assert body["authenticated"] is True
    assert body["role"] == "engineer"
    assert body["username"] == "local-engineer"
    assert body["token"] == settings.engineer_token

    # Test session verification with bearer token
    session_res = client.get(
        "/api/v1/auth/session",
        headers={"Authorization": f"Bearer {settings.engineer_token}"},
    )
    assert session_res.status_code == 200
    session_data = session_res.json()
    assert session_data["role"] == "engineer"
    assert session_data["username"] == "local-engineer"


def test_auth_login_rejects_invalid():
    client = TestClient(app)
    res = client.post("/api/v1/auth/login", json={"token": "invalid-token-here"})
    assert res.status_code == 401
