from __future__ import annotations

from sqlalchemy import select

from app.models.entities import Profile
from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    model = Profile

    async def get_by_email(self, email: str) -> Profile | None:
        result = await self.session.execute(
            select(Profile).where(Profile.email == email)
        )
        return result.scalar_one_or_none()
