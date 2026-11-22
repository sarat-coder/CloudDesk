from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Customer, Subscription, Workspace
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    async def get_by_email(self, email: str) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(Customer.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(Customer.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def exists_by_external_id(self, external_id: str) -> bool:
        result = await self.session.execute(
            select(Customer.id).where(Customer.external_id == external_id)
        )
        return result.scalar_one_or_none() is not None


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get_by_customer(self, customer_id: str) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.customer_id == customer_id)
        )
        return list(result.scalars().all())

    async def exists_for_customer(self, customer_id: str) -> bool:
        result = await self.session.execute(
            select(Subscription.id).where(Subscription.customer_id == customer_id)
        )
        return result.scalar_one_or_none() is not None


class WorkspaceRepository(BaseRepository[Workspace]):
    model = Workspace

    async def get_by_customer(self, customer_id: str) -> list[Workspace]:
        result = await self.session.execute(
            select(Workspace).where(Workspace.customer_id == customer_id)
        )
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace).where(Workspace.slug == slug)
        )
        return result.scalar_one_or_none()
