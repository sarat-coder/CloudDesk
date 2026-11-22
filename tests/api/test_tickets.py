"""Phase 4 — Ticket API tests.

Covers:
- POST /tickets (all channels, auth, 404 for unknown customer)
- GET /tickets (list)
- GET /tickets/{id} (detail, 404)
- PATCH /tickets/{id} (update, viewer 403)
- POST /tickets/{id}/run (409 when waiting_on_approval)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(_env_file=None)), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /tickets
# ---------------------------------------------------------------------------

def test_list_tickets_requires_auth(client):
    response = client.get("/api/v1/tickets")
    assert response.status_code == 401


def test_list_tickets_returns_paginated(client, agent_headers):
    response = client.get("/api/v1/tickets", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert body["page"] == 1


def test_list_tickets_viewer_can_read(client, viewer_headers):
    response = client.get("/api/v1/tickets", headers=viewer_headers)
    assert response.status_code == 200


def test_list_tickets_seed_data_loaded(client, agent_headers):
    response = client.get("/api/v1/tickets?page_size=100", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    # 13 seed tickets must be present
    assert body["total"] >= 13


def test_list_tickets_filter_by_status(client, agent_headers):
    response = client.get("/api/v1/tickets?status=new", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    for ticket in body["items"]:
        assert ticket["status"] == "new"


# ---------------------------------------------------------------------------
# POST /tickets
# ---------------------------------------------------------------------------

def _get_first_customer_id(client, headers) -> str:
    r = client.get("/api/v1/customers?page_size=1", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert items, "No customers in DB"
    return items[0]["id"]


@pytest.mark.parametrize("channel", ["email", "chat", "web", "api"])
def test_create_ticket_all_channels(client, agent_headers, channel):
    cust_id = _get_first_customer_id(client, agent_headers)
    response = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": cust_id,
            "subject": f"Test ticket via {channel}",
            "body": "This is a test body.",
            "channel": channel,
        },
        headers=agent_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["channel"] == channel
    assert body["status"] == "new"
    assert body["ticket_number"].startswith("CD-")


def test_create_ticket_viewer_forbidden(client, viewer_headers):
    cust_id = _get_first_customer_id(client, viewer_headers)
    response = client.post(
        "/api/v1/tickets",
        json={"customer_id": cust_id, "subject": "Test", "body": "Body"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_create_ticket_unknown_customer_404(client, agent_headers):
    response = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "subject": "Test",
            "body": "Body",
        },
        headers=agent_headers,
    )
    assert response.status_code == 404


def test_create_ticket_requires_auth(client):
    response = client.post(
        "/api/v1/tickets",
        json={"customer_id": "x", "subject": "Test", "body": "Body"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /tickets/{id}
# ---------------------------------------------------------------------------

def test_get_ticket_cd1001_detail(client, agent_headers):
    list_resp = client.get("/api/v1/tickets?page_size=100", headers=agent_headers)
    items = list_resp.json()["items"]
    ticket_1001 = next((t for t in items if t["ticket_number"] == "CD-1001"), None)
    assert ticket_1001 is not None, "CD-1001 not found in list"

    response = client.get(f"/api/v1/tickets/{ticket_1001['id']}", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_number"] == "CD-1001"
    assert "messages" in body
    assert "customer" in body
    assert body["workflow"] is None


def test_get_ticket_seed_range(client, agent_headers):
    list_resp = client.get("/api/v1/tickets?page_size=100", headers=agent_headers)
    items = list_resp.json()["items"]
    numbers = {t["ticket_number"] for t in items}
    for n in range(1001, 1014):
        assert f"CD-{n}" in numbers, f"CD-{n} missing from seed data"


def test_get_ticket_404(client, agent_headers):
    response = client.get(
        "/api/v1/tickets/00000000-0000-0000-0000-000000000000",
        headers=agent_headers,
    )
    assert response.status_code == 404


def test_get_ticket_viewer_can_read(client, viewer_headers):
    list_resp = client.get("/api/v1/tickets?page_size=1", headers=viewer_headers)
    item_id = list_resp.json()["items"][0]["id"]
    response = client.get(f"/api/v1/tickets/{item_id}", headers=viewer_headers)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# PATCH /tickets/{id}
# ---------------------------------------------------------------------------

def test_patch_ticket_viewer_forbidden(client, viewer_headers):
    list_resp = client.get("/api/v1/tickets?page_size=1", headers=viewer_headers)
    item_id = list_resp.json()["items"][0]["id"]
    response = client.patch(
        f"/api/v1/tickets/{item_id}",
        json={"status": "in_progress"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_patch_ticket_status(client, agent_headers):
    list_resp = client.get("/api/v1/tickets?page_size=1", headers=agent_headers)
    item = list_resp.json()["items"][0]
    response = client.patch(
        f"/api/v1/tickets/{item['id']}",
        json={"status": "in_progress"},
        headers=agent_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


# ---------------------------------------------------------------------------
# POST /tickets/{id}/run — 409 when waiting_on_approval
# ---------------------------------------------------------------------------

def test_run_409_when_waiting_on_approval(client, agent_headers):
    # First patch a ticket to waiting_on_approval
    list_resp = client.get("/api/v1/tickets?page_size=100", headers=agent_headers)
    items = list_resp.json()["items"]
    # Use CD-1002 for the approval test
    ticket = next((t for t in items if t["ticket_number"] == "CD-1002"), items[0])

    client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        json={"status": "waiting_on_approval"},
        headers=agent_headers,
    )

    response = client.post(f"/api/v1/tickets/{ticket['id']}/run", headers=agent_headers)
    assert response.status_code == 409
