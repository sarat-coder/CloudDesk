from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.security import create_access_token
from app.main import create_app
from app.models.entities import AuditLog


@pytest.fixture
def client():
    return TestClient(create_app(Settings(_env_file=None)), raise_server_exceptions=False)


def test_missing_token_returns_401(client):
    response = client.post("/api/v1/_test/agent-only")
    assert response.status_code == 401


def test_malformed_token_returns_401(client):
    response = client.post(
        "/api/v1/_test/agent-only",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_agent_token_is_accepted(client):
    token = create_access_token(sub="agent-1", role="agent", name="Test Agent")
    response = client.post(
        "/api/v1/_test/agent-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "agent"


def test_viewer_receives_403_on_agent_route(client):
    token = create_access_token(sub="viewer-1", role="viewer", name="Vic Viewer")
    response = client.post(
        "/api/v1/_test/agent-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_token_passes_agent_route(client):
    token = create_access_token(sub="admin-1", role="admin", name="Admin User")
    response = client.post(
        "/api/v1/_test/agent-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_demo_login_issues_token_for_known_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "sam.agent@clouddesk.demo"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "agent"
    assert body["access_token"]


def test_demo_login_issues_token_for_admin(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@clouddesk.demo"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_demo_login_issues_token_for_viewer(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "vic.viewer@clouddesk.demo"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


def test_demo_login_rejects_unknown_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_non_get_request_writes_audit_log():
    from app.core.database import create_tables, get_session

    await create_tables()

    settings = Settings(_env_file=None)
    app = create_app(settings)

    with TestClient(app, raise_server_exceptions=False) as client:
        token = create_access_token(sub="agent-1", role="agent", name="Test Agent")
        client.post(
            "/api/v1/_test/agent-only",
            headers={"Authorization": f"Bearer {token}"},
        )

    async with get_session() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "POST")
        )
        logs = list(result.scalars().all())

    assert len(logs) >= 1
    log = logs[-1]
    assert log.action == "POST"
    assert log.resource_type is not None


def test_service_role_key_not_in_login_response(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@clouddesk.demo"},
    )
    body = response.json()
    for key in body:
        assert "service" not in str(key).lower()
        assert "supabase" not in str(key).lower()
