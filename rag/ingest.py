from __future__ import annotations

import logging

from rag.chunking import ArticleChunk, Article, chunk_article, load_article_files
from rag.retriever import Retriever
from rag.vector_store import Document, VectorStoreService, get_vector_store

logger = logging.getLogger(__name__)

_retriever: Retriever | None = None
_chunks: list[ArticleChunk] = []


async def run_ingest(settings, force: bool = False) -> int:
    """Load articles from markdown files, chunk and index them.

    Returns the number of chunks indexed.  Idempotent unless *force* is True.
    """
    global _retriever, _chunks

    if _retriever is not None and not force:
        return len(_chunks)

    kb_dir = f"{settings.sample_data_dir}/knowledge_base"
    articles = load_article_files(kb_dir)
    if not articles:
        logger.warning("No articles found in %s", kb_dir)

    all_chunks: list[ArticleChunk] = []
    for article in articles:
        all_chunks.extend(chunk_article(article))

    vs: VectorStoreService = get_vector_store(settings)
    # Clear existing docs so reindex starts fresh
    if hasattr(vs, "_docs"):
        vs._docs.clear()  # type: ignore[union-attr]
        vs._embeddings.clear()  # type: ignore[union-attr]

    docs = [
        Document(
            id=chunk.id,
            text=chunk.prefixed_text,
            metadata={
                "article_id": chunk.article_id,
                "title": chunk.title,
                "category": chunk.category,
                "source": chunk.source,
                "snippet": chunk.snippet,
                "tags": chunk.tags,
            },
        )
        for chunk in all_chunks
    ]

    await vs.add_documents(docs)

    _chunks = all_chunks
    _retriever = Retriever(vs, all_chunks)

    logger.info(
        "Knowledge ingest complete: %d articles → %d chunks",
        len(articles),
        len(all_chunks),
    )
    return len(all_chunks)


def get_retriever() -> Retriever:
    if _retriever is None:
        raise RuntimeError("Retriever not initialised; call run_ingest() first.")
    return _retriever


async def build_fresh_retriever(settings) -> Retriever:
    """Create and return a fresh Retriever without touching the global state.

    Used by tests to get a clean instance per test.
    """
    kb_dir = f"{settings.sample_data_dir}/knowledge_base"
    articles = load_article_files(kb_dir)
    all_chunks: list[ArticleChunk] = []
    for article in articles:
        all_chunks.extend(chunk_article(article))

    vs = get_vector_store(settings)
    docs = [
        Document(
            id=chunk.id,
            text=chunk.prefixed_text,
            metadata={
                "article_id": chunk.article_id,
                "title": chunk.title,
                "category": chunk.category,
                "source": chunk.source,
                "snippet": chunk.snippet,
                "tags": chunk.tags,
            },
        )
        for chunk in all_chunks
    ]
    await vs.add_documents(docs)
    return Retriever(vs, all_chunks)
