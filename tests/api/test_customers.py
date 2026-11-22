"""Phase 4 — Customer API tests.

Covers:
- GET /customers (list, pagination, search)
- GET /customers/{id} (detail with subscription, workspace, ticket history)
- GET /customers/{id} (404)
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
# GET /customers
# ---------------------------------------------------------------------------

def test_list_customers_requires_auth(client):
    response = client.get("/api/v1/customers")
    assert response.status_code == 401


def test_list_customers_returns_paginated(client, agent_headers):
    response = client.get("/api/v1/customers", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body


def test_list_customers_seed_data_loaded(client, agent_headers):
    response = client.get("/api/v1/customers?page_size=100", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 8, "Expected at least 8 seed customers"


def test_list_customers_viewer_can_read(client, viewer_headers):
    response = client.get("/api/v1/customers", headers=viewer_headers)
    assert response.status_code == 200


def test_list_customers_search(client, agent_headers):
    response = client.get("/api/v1/customers?search=Acme", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    for item in body["items"]:
        name_or_email = item["name"] + item["email"]
        assert "acme" in name_or_email.lower() or "Acme" in name_or_email


# ---------------------------------------------------------------------------
# GET /customers/{id}
# ---------------------------------------------------------------------------

def test_get_customer_detail_includes_subscription(client, agent_headers):
    list_resp = client.get("/api/v1/customers?page_size=100", headers=agent_headers)
    items = list_resp.json()["items"]
    # Find a non-free customer who likely has a subscription
    customer = next(
        (c for c in items if c["plan"] in ("pro", "business", "enterprise")), items[0]
    )
    response = client.get(f"/api/v1/customers/{customer['id']}", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    assert "subscription" in body
    assert "workspace" in body
    assert "tickets" in body
    assert "memory" in body


def test_get_customer_detail_includes_ticket_history(client, agent_headers):
    list_resp = client.get("/api/v1/customers?page_size=100", headers=agent_headers)
    items = list_resp.json()["items"]
    customer = items[0]
    response = client.get(f"/api/v1/customers/{customer['id']}", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    # Tickets list should exist (may be empty for some customers)
    assert isinstance(body["tickets"], list)


def test_get_customer_detail_known_customer(client, agent_headers):
    """CD-1001 belongs to Priya Sharma at Acme Corp (cust-0001)."""
    list_resp = client.get("/api/v1/customers?search=Acme&page_size=10", headers=agent_headers)
    items = list_resp.json()["items"]
    assert items, "Acme Corp customer not found"
    customer = items[0]
    response = client.get(f"/api/v1/customers/{customer['id']}", headers=agent_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["company"] == "Acme Corp"


def test_get_customer_detail_404(client, agent_headers):
    response = client.get(
        "/api/v1/customers/00000000-0000-0000-0000-000000000000",
        headers=agent_headers,
    )
    assert response.status_code == 404


def test_get_customer_detail_viewer_can_read(client, viewer_headers):
    list_resp = client.get("/api/v1/customers?page_size=1", headers=viewer_headers)
    cust_id = list_resp.json()["items"][0]["id"]
    response = client.get(f"/api/v1/customers/{cust_id}", headers=viewer_headers)
    assert response.status_code == 200
