from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag.chunking import ArticleChunk
    from rag.vector_store import VectorStoreService

_CACHE_TTL = 300  # seconds


@dataclass
class Evidence:
    id: str
    title: str
    source: str
    snippet: str
    score: float
    url: str
    article_id: str


class BM25Index:
    """In-memory BM25 index over ArticleChunk objects."""

    def __init__(
        self,
        chunks: list[ArticleChunk],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self._chunks = chunks
        self._k1 = k1
        self._b = b
        self._tf: list[dict[str, float]] = []
        self._df: dict[str, int] = {}
        self._dl: list[int] = []
        self._n = len(chunks)
        self._avgdl = 1.0
        if chunks:
            self._build()

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def _build(self) -> None:
        for chunk in self._chunks:
            tokens = self._tokenize(chunk.prefixed_text)
            self._dl.append(len(tokens))
            tf: dict[str, float] = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            self._tf.append(tf)
            for tok in set(tokens):
                self._df[tok] = self._df.get(tok, 0) + 1
        self._avgdl = sum(self._dl) / max(1, self._n)

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_category: str | None = None,
    ) -> list[tuple[int, float]]:
        """Return (chunk_index, bm25_score) pairs, best first."""
        q_tokens = self._tokenize(query)
        scores: dict[int, float] = {}
        for tok in set(q_tokens):
            df = self._df.get(tok, 0)
            if df == 0:
                continue
            idf = math.log((self._n - df + 0.5) / (df + 0.5) + 1)
            for i, (tf_map, dl) in enumerate(zip(self._tf, self._dl)):
                if filter_category and self._chunks[i].category != filter_category:
                    continue
                tf = tf_map.get(tok, 0.0)
                if tf == 0:
                    continue
                norm_dl = 1 - self._b + self._b * dl / self._avgdl
                contrib = idf * tf * (self._k1 + 1) / (tf + self._k1 * norm_dl)
                scores[i] = scores.get(i, 0.0) + contrib
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


class Retriever:
    def __init__(
        self,
        vector_store: VectorStoreService,
        chunks: list[ArticleChunk],
    ) -> None:
        self._vs = vector_store
        self._chunks = chunks
        self._bm25 = BM25Index(chunks) if chunks else None
        self._chunk_by_id = {c.id: c for c in chunks}

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",
        category: str | None = None,
        cache=None,
    ) -> list[Evidence]:
        cache_key = f"rag:{mode}:{category or ''}:{top_k}:{query}"
        if cache is not None:
            try:
                raw = cache.get(cache_key)
                if raw:
                    return [Evidence(**e) for e in json.loads(raw)]
            except Exception:
                pass

        if mode == "semantic":
            result = await self._semantic(query, top_k, category)
        elif mode == "keyword":
            result = self._keyword(query, top_k, category)
        else:
            result = await self._hybrid(query, top_k, category)

        if cache is not None:
            try:
                cache.set(cache_key, json.dumps([asdict(e) for e in result]), ex=_CACHE_TTL)
            except Exception:
                pass

        return result

    async def _semantic(
        self,
        query: str,
        top_k: int,
        category: str | None,
    ) -> list[Evidence]:
        raw = await self._vs.search(query, top_k=top_k * 4, filter_category=category)
        return self._results_to_evidence(
            [(r.document.id, r.score) for r in raw], top_k
        )

    def _keyword(
        self,
        query: str,
        top_k: int,
        category: str | None,
    ) -> list[Evidence]:
        if not self._bm25:
            return []
        ranked = self._bm25.search(query, top_k=top_k * 4, filter_category=category)
        max_score = ranked[0][1] if ranked else 1.0
        pairs = [
            (self._chunks[i].id, score / max(max_score, 1e-9))
            for i, score in ranked
        ]
        return self._results_to_evidence(pairs, top_k)

    async def _hybrid(
        self,
        query: str,
        top_k: int,
        category: str | None,
    ) -> list[Evidence]:
        K = 60  # RRF constant

        sem_results = await self._vs.search(
            query, top_k=top_k * 4, filter_category=category
        )
        kw_ranked = (
            self._bm25.search(query, top_k=top_k * 4, filter_category=category)
            if self._bm25
            else []
        )

        rrf: dict[str, float] = {}
        for rank, result in enumerate(sem_results):
            doc_id = result.document.id
            rrf[doc_id] = rrf.get(doc_id, 0.0) + 1.0 / (K + rank + 1)
        for rank, (idx, _) in enumerate(kw_ranked):
            doc_id = self._chunks[idx].id
            rrf[doc_id] = rrf.get(doc_id, 0.0) + 1.0 / (K + rank + 1)

        # heuristic rerank: category match + title/query overlap boost
        q_words = set(re.findall(r"\w+", query.lower()))
        reranked: list[tuple[str, float]] = []
        for doc_id, rrf_score in rrf.items():
            chunk = self._chunk_by_id.get(doc_id)
            if chunk is None:
                continue
            boost = 0.0
            if category and chunk.category == category:
                boost += 0.1
            t_words = set(re.findall(r"\w+", chunk.title.lower()))
            overlap = len(q_words & t_words) / max(len(q_words), 1)
            boost += overlap * 0.05
            reranked.append((doc_id, rrf_score + boost))

        reranked.sort(key=lambda x: x[1], reverse=True)
        return self._results_to_evidence(reranked, top_k)

    def _results_to_evidence(
        self,
        pairs: list[tuple[str, float]],
        top_k: int,
    ) -> list[Evidence]:
        seen_articles: set[str] = set()
        evidence: list[Evidence] = []
        for doc_id, score in pairs:
            chunk = self._chunk_by_id.get(doc_id)
            if chunk is None:
                continue
            if chunk.article_id not in seen_articles:
                seen_articles.add(chunk.article_id)
                evidence.append(
                    Evidence(
                        id=chunk.id,
                        title=chunk.title,
                        source=chunk.source,
                        snippet=chunk.snippet,
                        score=score,
                        url=f"/knowledge/{chunk.article_id}",
                        article_id=chunk.article_id,
                    )
                )
            if len(evidence) >= top_k:
                break
        return evidence
