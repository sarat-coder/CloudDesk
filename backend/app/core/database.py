from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.models.entities import Base


def _make_engine():
    settings = get_settings()
    connect_args: dict = {}
    if "sqlite" in settings.database_url:
        connect_args["check_same_thread"] = False
    return create_async_engine(
        settings.database_url,
        echo=False,
        connect_args=connect_args,
    )


def _make_session_factory(engine=None):
    if engine is None:
        engine = _make_engine()
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables() -> None:
    engine = _make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    factory = _make_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
