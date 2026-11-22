from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import require_role
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import (
    ArticleDetailResponse,
    ArticleListResponse,
    ArticleResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    EvidenceItem,
    ReindexResponse,
)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.get("/articles", response_model=ArticleListResponse)
async def list_articles(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: dict = Depends(require_role("viewer")),
):
    async with get_session() as session:
        repo = KnowledgeRepository(session)
        offset = (page - 1) * page_size
        articles, total = await repo.search(
            query=search, category=category, limit=page_size, offset=offset
        )
        return ArticleListResponse(
            items=[ArticleResponse.model_validate(a) for a in articles],
            total=total,
        )


@router.get("/articles/{slug}", response_model=ArticleDetailResponse)
async def get_article(
    slug: str,
    _user: dict = Depends(require_role("viewer")),
):
    async with get_session() as session:
        repo = KnowledgeRepository(session)
        article = await repo.get_by_slug(slug)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        return ArticleDetailResponse(
            id=article.id,
            slug=article.slug,
            title=article.title,
            category=article.category,
            tags=article.tags or [],
            summary=article.summary or "",
            updated_at=article.updated_at,
            content=article.body,
        )


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    body: KnowledgeSearchRequest,
    _user: dict = Depends(require_role("viewer")),
):
    from rag.ingest import get_retriever

    try:
        retriever = get_retriever()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Knowledge index not ready")

    start = time.monotonic()
    evidence_list = await retriever.retrieve(
        query=body.query,
        top_k=body.top_k,
        mode=body.mode,
    )
    took_ms = int((time.monotonic() - start) * 1000)

    return KnowledgeSearchResponse(
        results=[
            EvidenceItem(
                id=e.id,
                title=e.title,
                source=e.source,
                snippet=e.snippet,
                score=round(e.score, 4),
                url=e.url,
                article_id=e.article_id,
            )
            for e in evidence_list
        ],
        mode=body.mode,
        took_ms=took_ms,
    )


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_knowledge(
    _user: dict = Depends(require_role("admin")),
):
    from rag.ingest import run_ingest

    settings = get_settings()
    indexed = await run_ingest(settings, force=True)
    return ReindexResponse(indexed=indexed)
