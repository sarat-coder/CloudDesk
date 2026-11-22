from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.models.entities import Customer, Incident, Product, Subscription, Ticket, Workspace
from app.repositories.ticket_repository import TicketRepository
from app.repositories.customer_repository import CustomerRepository

logger = logging.getLogger(__name__)


def _load(filename: str) -> list[dict]:
    settings = get_settings()
    path = Path(settings.sample_data_dir) / filename
    if not path.exists():
        logger.warning("Sample data file not found: %s", path)
        return []
    return json.loads(path.read_text(encoding="utf-8"))


async def _ensure_uuid(raw_id: str) -> str:
    try:
        uuid.UUID(raw_id)
        return raw_id
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_id))


async def _seed_customers(session: AsyncSession) -> None:
    repo = CustomerRepository(session)
    records = _load("customers.json")
    for rec in records:
        if await repo.exists_by_external_id(rec["external_id"]):
            continue
        await repo.create(
            Customer(
                id=await _ensure_uuid(rec["id"]),
                external_id=rec["external_id"],
                name=rec["name"],
                email=rec["email"],
                company=rec.get("company"),
                plan=rec.get("plan", "free"),
                status=rec.get("status", "active"),
            )
        )
    logger.info("Customers seeded (%d records)", len(records))


async def _seed_subscriptions(session: AsyncSession) -> None:
    records = _load("subscriptions.json")
    for rec in records:
        existing = await session.get(Subscription, await _ensure_uuid(rec["id"]))
        if existing:
            continue
        session.add(
            Subscription(
                id=await _ensure_uuid(rec["id"]),
                customer_id=await _ensure_uuid(rec["customer_id"]),
                plan=rec["plan"],
                seats=rec.get("seats", 1),
                seats_used=rec.get("seats_used", 0),
                status=rec.get("status", "active"),
                billing_cycle=rec.get("billing_cycle", "monthly"),
                amount=float(rec.get("amount", 0)),
                currency=rec.get("currency", "USD"),
                renewal_date=rec.get("renewal_date"),
            )
        )
    await session.flush()
    logger.info("Subscriptions seeded (%d records)", len(records))


async def _seed_workspaces(session: AsyncSession) -> None:
    records = _load("workspaces.json")
    for rec in records:
        existing = await session.get(Workspace, await _ensure_uuid(rec["id"]))
        if existing:
            continue
        session.add(
            Workspace(
                id=await _ensure_uuid(rec["id"]),
                customer_id=await _ensure_uuid(rec["customer_id"]),
                name=rec["name"],
                slug=rec["slug"],
                region=rec.get("region", "us-east-1"),
                storage_used_gb=float(rec.get("storage_used_gb", 0)),
                storage_limit_gb=float(rec.get("storage_limit_gb", 5)),
                member_count=int(rec.get("member_count", 1)),
                settings=rec.get("settings", {}),
            )
        )
    await session.flush()
    logger.info("Workspaces seeded (%d records)", len(records))


async def _seed_products(session: AsyncSession) -> None:
    records = _load("products.json")
    for rec in records:
        existing = await session.get(Product, await _ensure_uuid(rec["id"]))
        if existing:
            continue
        session.add(
            Product(
                id=await _ensure_uuid(rec["id"]),
                name=rec["name"],
                slug=rec["slug"],
                description=rec.get("description"),
                plan_limits=rec.get("plan_limits", {}),
            )
        )
    await session.flush()
    logger.info("Products seeded (%d records)", len(records))


async def _seed_incidents(session: AsyncSession) -> None:
    records = _load("incidents.json")
    for rec in records:
        existing = await session.get(Incident, await _ensure_uuid(rec["id"]))
        if existing:
            continue
        session.add(
            Incident(
                id=await _ensure_uuid(rec["id"]),
                title=rec["title"],
                description=rec["description"],
                affected_services=rec.get("affected_services", []),
                status=rec.get("status", "investigating"),
                severity=rec.get("severity", "medium"),
            )
        )
    await session.flush()
    logger.info("Incidents seeded (%d records)", len(records))


async def _seed_tickets(session: AsyncSession) -> None:
    repo = TicketRepository(session)
    records = _load("tickets.json")
    for rec in records:
        if await repo.exists_by_number(rec["ticket_number"]):
            continue
        await repo.create(
            Ticket(
                id=await _ensure_uuid(rec["id"]),
                ticket_number=rec["ticket_number"],
                customer_id=await _ensure_uuid(rec["customer_id"]),
                subject=rec["subject"],
                body=rec["body"],
                channel=rec.get("channel", "web"),
                status=rec.get("status", "new"),
                severity=rec.get("severity"),
                category=rec.get("category"),
                category_summary=rec.get("category_summary"),
            )
        )
    logger.info("Tickets seeded (%d records)", len(records))


async def bootstrap_demo_data() -> None:
    settings = get_settings()
    if not settings.demo_mode:
        return

    async with get_session() as session:
        await _seed_customers(session)
        await _seed_subscriptions(session)
        await _seed_workspaces(session)
        await _seed_products(session)
        await _seed_incidents(session)
        await _seed_tickets(session)

    logger.info("Demo data bootstrap complete")
