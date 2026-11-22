from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import SupportArticle
from app.repositories.base import BaseRepository


class KnowledgeRepository(BaseRepository[SupportArticle]):
    model = SupportArticle

    async def get_by_slug(self, slug: str) -> SupportArticle | None:
        result = await self.session.execute(
            select(SupportArticle).where(SupportArticle.slug == slug)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        query: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SupportArticle], int]:
        stmt = select(SupportArticle)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    SupportArticle.title.ilike(like),
                    SupportArticle.summary.ilike(like),
                )
            )
        if category:
            stmt = stmt.where(SupportArticle.category == category)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = stmt.order_by(SupportArticle.title).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def upsert_from_file(
        self,
        slug: str,
        title: str,
        category: str,
        tags: list[str],
        summary: str,
        body: str,
        article_id: str,
    ) -> SupportArticle:
        existing = await self.get_by_slug(slug)
        if existing:
            existing.title = title
            existing.category = category
            existing.tags = tags
            existing.summary = summary
            existing.body = body
            await self.session.flush()
            return existing
        article = SupportArticle(
            id=article_id,
            slug=slug,
            title=title,
            category=category,
            tags=tags,
            summary=summary,
            body=body,
        )
        self.session.add(article)
        await self.session.flush()
        await self.session.refresh(article)
        return article
