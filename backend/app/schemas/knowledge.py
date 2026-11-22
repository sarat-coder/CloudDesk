from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ArticleResponse(BaseModel):
    id: str
    slug: str
    title: str
    category: str
    tags: list[str]
    summary: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArticleDetailResponse(ArticleResponse):
    content: str


class ArticleListResponse(BaseModel):
    items: list[ArticleResponse]
    total: int


class EvidenceItem(BaseModel):
    id: str
    title: str
    source: str
    snippet: str
    score: float
    url: str | None = None
    article_id: str


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: str = Field(default="hybrid", pattern="^(hybrid|semantic|keyword)$")


class KnowledgeSearchResponse(BaseModel):
    results: list[EvidenceItem]
    mode: str
    took_ms: int


class ReindexResponse(BaseModel):
    indexed: int
