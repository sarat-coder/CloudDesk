from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Ticket, TicketMessage
from app.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    model = Ticket

    async def get_by_number(self, ticket_number: str) -> Ticket | None:
        result = await self.session.execute(
            select(Ticket).where(Ticket.ticket_number == ticket_number)
        )
        return result.scalar_one_or_none()

    async def exists_by_number(self, ticket_number: str) -> bool:
        result = await self.session.execute(
            select(Ticket.id).where(Ticket.ticket_number == ticket_number)
        )
        return result.scalar_one_or_none() is not None

    async def list_by_customer(
        self, customer_id: str, limit: int = 20
    ) -> list[Ticket]:
        result = await self.session.execute(
            select(Ticket)
            .where(Ticket.customer_id == customer_id)
            .order_by(desc(Ticket.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_recent(self, limit: int = 50) -> list[Ticket]:
        result = await self.session.execute(
            select(Ticket).order_by(desc(Ticket.created_at)).limit(limit)
        )
        return list(result.scalars().all())


class TicketMessageRepository(BaseRepository[TicketMessage]):
    model = TicketMessage

    async def list_by_ticket(self, ticket_id: str) -> list[TicketMessage]:
        result = await self.session.execute(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at)
        )
        return list(result.scalars().all())
