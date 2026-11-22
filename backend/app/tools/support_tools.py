"""Read-only support tools — no approval required.

Tools:
  get_customer           — look up customer profile + subscription + workspace
  get_subscription       — subscription details for a customer
  get_ticket_history     — recent tickets for a customer
  search_docs            — semantic/keyword search over the knowledge base
  check_service_status   — current incident / service health
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.database import get_session
from app.models.entities import Customer, Incident, Subscription, Ticket, Workspace
from app.tools.policy import ToolResult
from sqlalchemy import select

if TYPE_CHECKING:
    from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


async def get_customer(customer_id: str) -> ToolResult:
    """Return customer profile, subscription plan, workspace info, and status.

    Args:
        customer_id: The internal UUID of the customer.
    """
    try:
        async with get_session() as session:
            customer: Customer | None = await session.get(Customer, customer_id)
            if customer is None:
                return ToolResult(ok=False, error=f"Customer '{customer_id}' not found.")

            sub_result = await session.execute(
                select(Subscription).where(Subscription.customer_id == customer_id)
            )
            subscription = sub_result.scalars().first()

            ws_result = await session.execute(
                select(Workspace).where(Workspace.customer_id == customer_id)
            )
            workspace = ws_result.scalars().first()

            data: dict[str, Any] = {
                "id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "company": customer.company,
                "plan": customer.plan,
                "status": customer.status,
                "subscription": None,
                "workspace": None,
            }
            if subscription:
                data["subscription"] = {
                    "plan": subscription.plan,
                    "seats": subscription.seats,
                    "seats_used": subscription.seats_used,
                    "status": subscription.status,
                    "billing_cycle": subscription.billing_cycle,
                    "amount": subscription.amount,
                    "currency": subscription.currency,
                    "renewal_date": subscription.renewal_date,
                }
            if workspace:
                data["workspace"] = {
                    "id": workspace.id,
                    "name": workspace.name,
                    "slug": workspace.slug,
                    "region": workspace.region,
                    "storage_used_gb": workspace.storage_used_gb,
                    "storage_limit_gb": workspace.storage_limit_gb,
                    "member_count": workspace.member_count,
                }
            return ToolResult(ok=True, data=data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_customer failed for %s", customer_id)
        return ToolResult(ok=False, error=str(exc))


async def get_subscription(customer_id: str) -> ToolResult:
    """Return the active subscription for a customer.

    Args:
        customer_id: The internal UUID of the customer.
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.customer_id == customer_id)
            )
            subscription = result.scalars().first()
            if subscription is None:
                return ToolResult(ok=False, error=f"No subscription found for customer '{customer_id}'.")
            return ToolResult(
                ok=True,
                data={
                    "id": subscription.id,
                    "plan": subscription.plan,
                    "seats": subscription.seats,
                    "seats_used": subscription.seats_used,
                    "status": subscription.status,
                    "billing_cycle": subscription.billing_cycle,
                    "amount": subscription.amount,
                    "currency": subscription.currency,
                    "renewal_date": subscription.renewal_date,
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_subscription failed for %s", customer_id)
        return ToolResult(ok=False, error=str(exc))


async def get_ticket_history(customer_id: str, limit: int = 10) -> ToolResult:
    """Return recent support tickets for a customer (excluding the current one).

    Args:
        customer_id: The internal UUID of the customer.
        limit: Maximum number of tickets to return (default 10).
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Ticket)
                .where(Ticket.customer_id == customer_id)
                .order_by(Ticket.created_at.desc())
                .limit(min(limit, 20))
            )
            tickets = result.scalars().all()
            return ToolResult(
                ok=True,
                data={
                    "tickets": [
                        {
                            "id": t.id,
                            "ticket_number": t.ticket_number,
                            "subject": t.subject,
                            "status": t.status,
                            "severity": t.severity,
                            "category": t.category,
                            "created_at": t.created_at.isoformat() if t.created_at else None,
                        }
                        for t in tickets
                    ]
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_ticket_history failed for %s", customer_id)
        return ToolResult(ok=False, error=str(exc))


async def search_docs(
    query: str,
    category: str | None = None,
    top_k: int = 5,
    mode: str = "hybrid",
) -> ToolResult:
    """Search the knowledge base and return cited evidence.

    Args:
        query: The search query string.
        category: Optional ticket category to prefer matching articles.
        top_k: Maximum number of evidence items to return (default 5).
        mode: Retrieval mode — 'hybrid' (default), 'semantic', or 'keyword'.
    """
    try:
        from rag.ingest import get_retriever

        retriever = get_retriever()
        results = await retriever.retrieve(
            query=query,
            top_k=min(top_k, 10),
            mode=mode,
            category=category,
        )
        return ToolResult(
            ok=True,
            data={
                "evidence": [
                    {
                        "id": e.id,
                        "title": e.title,
                        "source": e.source,
                        "snippet": e.snippet,
                        "score": round(e.score, 4),
                        "url": e.url,
                        "article_id": e.article_id,
                    }
                    for e in results
                ]
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("search_docs failed for query=%r", query)
        return ToolResult(ok=False, error=str(exc))


async def check_service_status(service: str | None = None) -> ToolResult:
    """Return current incident and service-health information.

    Args:
        service: Optional service name to filter incidents (e.g. 'sso', 'api').
                 Pass None to return all active incidents.
    """
    try:
        async with get_session() as session:
            stmt = select(Incident).where(Incident.status != "resolved")
            result = await session.execute(stmt)
            incidents = result.scalars().all()

            if service:
                svc_lower = service.lower()
                incidents = [
                    inc for inc in incidents
                    if svc_lower in (inc.title or "").lower()
                    or any(
                        svc_lower in str(s).lower()
                        for s in (inc.affected_services or [])
                    )
                ]

            return ToolResult(
                ok=True,
                data={
                    "active_incidents": [
                        {
                            "id": inc.id,
                            "title": inc.title,
                            "description": inc.description,
                            "status": inc.status,
                            "severity": inc.severity,
                            "affected_services": inc.affected_services,
                            "started_at": inc.started_at.isoformat() if inc.started_at else None,
                        }
                        for inc in incidents
                    ],
                    "service_healthy": len(incidents) == 0,
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("check_service_status failed")
        return ToolResult(ok=False, error=str(exc))


def register_support_tools(registry: "ToolRegistry") -> None:
    """Register all read-only tools into *registry*."""
    registry.register_many(
        {
            "get_customer": get_customer,
            "get_subscription": get_subscription,
            "get_ticket_history": get_ticket_history,
            "search_docs": search_docs,
            "check_service_status": check_service_status,
        }
    )
