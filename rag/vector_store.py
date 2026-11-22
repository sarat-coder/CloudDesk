from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Document:
    id: str
    text: str      # prefixed text — what gets embedded
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    document: Document
    score: float


@runtime_checkable
class VectorStoreService(Protocol):
    async def add_documents(self, documents: list[Document]) -> None: ...
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_category: str | None = None,
    ) -> list[SearchResult]: ...
    async def delete(self, ids: list[str]) -> None: ...
    async def count(self) -> int: ...
    async def health(self) -> bool: ...


def _embed(text: str, dims: int = 384) -> list[float]:
    """Deterministic hashed bag-of-words embedding (fake, offline)."""
    tokens = re.findall(r"\w+", text.lower())
    vec = [0.0] * dims
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16) % dims
        vec[h] += 1.0
    mag = math.sqrt(sum(x * x for x in vec))
    if mag == 0:
        return vec
    return [x / mag for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    """Dot product of two pre-normalised vectors equals cosine similarity."""
    return sum(x * y for x, y in zip(a, b))


class InMemoryVectorStore:
    def __init__(self, dims: int = 384) -> None:
        self._dims = dims
        self._docs: list[Document] = []
        self._embeddings: list[list[float]] = []

    async def add_documents(self, documents: list[Document]) -> None:
        for doc in documents:
            emb = _embed(doc.text, self._dims)
            self._docs.append(doc)
            self._embeddings.append(emb)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_category: str | None = None,
    ) -> list[SearchResult]:
        q_emb = _embed(query, self._dims)
        results: list[SearchResult] = []
        for doc, emb in zip(self._docs, self._embeddings):
            if filter_category and doc.metadata.get("category") != filter_category:
                continue
            score = _cosine(q_emb, emb)
            results.append(SearchResult(document=doc, score=score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def delete(self, ids: list[str]) -> None:
        id_set = set(ids)
        pairs = [
            (d, e)
            for d, e in zip(self._docs, self._embeddings)
            if d.id not in id_set
        ]
        self._docs = [p[0] for p in pairs]
        self._embeddings = [p[1] for p in pairs]

    async def count(self) -> int:
        return len(self._docs)

    async def health(self) -> bool:
        return True


class QdrantVectorStore:
    """Qdrant-backed vector store (requires QDRANT_URL and qdrant-client)."""

    def __init__(self, settings) -> None:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams

        self._collection = settings.qdrant_collection
        self._dims = settings.embedding_dimensions
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value()
            if settings.qdrant_api_key
            else None,
        )

    async def add_documents(self, documents: list[Document]) -> None:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=abs(hash(doc.id)) % (2**63),
                vector=_embed(doc.text, self._dims),
                payload={"doc_id": doc.id, "text": doc.text, **doc.metadata},
            )
            for doc in documents
        ]
        await self._client.upsert(collection_name=self._collection, points=points)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_category: str | None = None,
    ) -> list[SearchResult]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        q_emb = _embed(query, self._dims)
        query_filter = None
        if filter_category:
            query_filter = Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=filter_category))]
            )
        hits = await self._client.search(
            collection_name=self._collection,
            query_vector=q_emb,
            limit=top_k,
            query_filter=query_filter,
        )
        results = []
        for hit in hits:
            payload = hit.payload or {}
            doc = Document(
                id=payload.get("doc_id", str(hit.id)),
                text=payload.get("text", ""),
                metadata={k: v for k, v in payload.items() if k not in ("doc_id", "text")},
            )
            results.append(SearchResult(document=doc, score=float(hit.score)))
        return results

    async def delete(self, ids: list[str]) -> None:
        from qdrant_client.models import PointIdsList

        point_ids = [abs(hash(i)) % (2**63) for i in ids]
        await self._client.delete(
            collection_name=self._collection,
            points_selector=PointIdsList(points=point_ids),
        )

    async def count(self) -> int:
        info = await self._client.get_collection(self._collection)
        return info.vectors_count or 0

    async def health(self) -> bool:
        try:
            await self._client.get_collections()
            return True
        except Exception:
            return False


def get_vector_store(settings) -> VectorStoreService:
    if settings.vector_store == "qdrant":
        return QdrantVectorStore(settings)
    return InMemoryVectorStore(dims=settings.embedding_dimensions)
