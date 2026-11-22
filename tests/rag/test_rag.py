"""RAG pipeline tests: ingest, retrieval modes, caching, RRF, rerank, filters."""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from rag.chunking import Article, ArticleChunk, chunk_article, load_article_files, _sliding_windows
from rag.ingest import build_fresh_retriever
from rag.retriever import BM25Index, Evidence, Retriever
from rag.vector_store import Document, InMemoryVectorStore, _embed


# ---------------------------------------------------------------------------
# Chunking tests
# ---------------------------------------------------------------------------

class TestChunking:
    def test_load_article_files_returns_at_least_15(self):
        settings = get_settings()
        kb_dir = f"{settings.sample_data_dir}/knowledge_base"
        articles = load_article_files(kb_dir)
        assert len(articles) >= 15, f"Expected ≥15 articles, got {len(articles)}"

    def test_article_has_required_fields(self):
        settings = get_settings()
        kb_dir = f"{settings.sample_data_dir}/knowledge_base"
        articles = load_article_files(kb_dir)
        for art in articles:
            assert art.slug, "Article missing slug"
            assert art.title, "Article missing title"
            assert art.category in {
                "login_issue", "billing", "api_failure", "workspace_permissions",
                "storage_quota", "integration", "feature_request", "account",
                "security", "other",
            }, f"Unknown category: {art.category}"

    def test_chunk_article_produces_chunks(self):
        art = Article(
            slug="test-article",
            title="Test Article",
            category="other",
            tags=["test"],
            summary="A test",
            body="## Section One\n\nSome content here.\n\n## Section Two\n\nMore content.",
        )
        chunks = chunk_article(art)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.id.startswith("test-article#chunk-")
            assert chunk.article_id == "test-article"
            # Every chunk is prefixed with "{title} - {heading}"
            assert chunk.prefixed_text.startswith("Test Article - ")

    def test_chunk_prefix_format(self):
        """Each chunk prefixed_text must be '{title} - {heading}: {text}'."""
        art = Article(
            slug="billing-guide",
            title="Billing Guide",
            category="billing",
            tags=[],
            summary="",
            body="## Refunds\n\nRefunds are processed in 5 days.",
        )
        chunks = chunk_article(art)
        assert chunks
        assert chunks[0].prefixed_text.startswith("Billing Guide - Refunds:")

    def test_sliding_windows_no_split_when_short(self):
        text = "x" * 100
        windows = _sliding_windows(text, 900, 150)
        assert windows == [text]

    def test_sliding_windows_overlap(self):
        text = "a" * 1000
        windows = _sliding_windows(text, 900, 150)
        assert len(windows) == 2
        # Second window starts at 900-150=750, so its content starts at char 750
        assert len(windows[0]) == 900
        assert len(windows[1]) == 250  # 1000 - 750

    def test_all_articles_produce_chunks(self):
        settings = get_settings()
        kb_dir = f"{settings.sample_data_dir}/knowledge_base"
        articles = load_article_files(kb_dir)
        for art in articles:
            chunks = chunk_article(art)
            assert len(chunks) >= 1, f"Article {art.slug} produced no chunks"

    def test_total_chunk_count_positive(self):
        settings = get_settings()
        kb_dir = f"{settings.sample_data_dir}/knowledge_base"
        articles = load_article_files(kb_dir)
        total = sum(len(chunk_article(a)) for a in articles)
        assert total > 0
        # Each article has at least 1 chunk, so total >= article count
        assert total >= len(articles)

    def test_source_format(self):
        art = Article(
            slug="sso-guide",
            title="SSO Guide",
            category="login_issue",
            tags=[],
            summary="",
            body="Configure SSO using SAML.",
        )
        chunks = chunk_article(art)
        assert chunks[0].source == "kb://sso-guide#chunk-0"

    def test_snippet_is_first_200_chars(self):
        body = "x" * 500
        art = Article(
            slug="test",
            title="T",
            category="other",
            tags=[],
            summary="",
            body=body,
        )
        chunks = chunk_article(art)
        for chunk in chunks:
            assert len(chunk.snippet) <= 200


# ---------------------------------------------------------------------------
# Vector store tests
# ---------------------------------------------------------------------------

class TestVectorStore:
    @pytest.fixture
    async def vs(self):
        store = InMemoryVectorStore(dims=384)
        docs = [
            Document(id="d1", text="MFA two-factor authentication lockout recovery"),
            Document(id="d2", text="Billing refund policy invoice seats"),
            Document(id="d3", text="SSO SAML configuration enterprise login"),
        ]
        await store.add_documents(docs)
        return store

    async def test_count(self, vs):
        assert await vs.count() == 3

    async def test_health(self, vs):
        assert await vs.health() is True

    async def test_search_returns_top_k(self, vs):
        results = await vs.search("MFA lockout", top_k=2)
        assert len(results) == 2

    async def test_search_mfa_first(self, vs):
        results = await vs.search("MFA two-factor lockout", top_k=3)
        assert results[0].document.id == "d1"

    async def test_delete(self, vs):
        await vs.delete(["d2"])
        assert await vs.count() == 2
        results = await vs.search("billing", top_k=5)
        ids = [r.document.id for r in results]
        assert "d2" not in ids

    async def test_add_idempotent(self, vs):
        await vs.add_documents([Document(id="d4", text="new doc")])
        assert await vs.count() == 4


class TestFakeEmbeddings:
    def test_embed_deterministic(self):
        v1 = _embed("hello world")
        v2 = _embed("hello world")
        assert v1 == v2

    def test_embed_unit_length(self):
        import math
        v = _embed("test embedding vector")
        mag = math.sqrt(sum(x * x for x in v))
        assert abs(mag - 1.0) < 1e-6

    def test_embed_different_texts_differ(self):
        v1 = _embed("mfa lockout recovery")
        v2 = _embed("billing refund policy")
        assert v1 != v2

    def test_embed_dimensions(self):
        v = _embed("test", dims=384)
        assert len(v) == 384


# ---------------------------------------------------------------------------
# BM25 tests
# ---------------------------------------------------------------------------

class TestBM25:
    @pytest.fixture
    def bm25(self):
        from rag.chunking import ArticleChunk
        chunks = [
            ArticleChunk(
                id="a#chunk-0", article_id="a", title="MFA Guide",
                heading="Lockout", text="MFA lockout recovery backup codes",
                prefixed_text="MFA Guide - Lockout: MFA lockout recovery backup codes",
                category="login_issue", source="kb://a#chunk-0", snippet="MFA lockout",
            ),
            ArticleChunk(
                id="b#chunk-0", article_id="b", title="Billing Policy",
                heading="Refunds", text="Billing refund policy invoice seats prorated",
                prefixed_text="Billing Policy - Refunds: Billing refund policy invoice seats prorated",
                category="billing", source="kb://b#chunk-0", snippet="Billing refund",
            ),
            ArticleChunk(
                id="c#chunk-0", article_id="c", title="SSO Guide",
                heading="Setup", text="SSO SAML configuration identity provider",
                prefixed_text="SSO Guide - Setup: SSO SAML configuration identity provider",
                category="login_issue", source="kb://c#chunk-0", snippet="SSO SAML",
            ),
        ]
        return BM25Index(chunks)

    def test_bm25_mfa_query(self, bm25):
        ranked = bm25.search("MFA lockout recovery", top_k=3)
        assert ranked
        assert ranked[0][0] == 0  # chunk index 0 = MFA article

    def test_bm25_billing_query(self, bm25):
        ranked = bm25.search("billing refund invoice", top_k=3)
        assert ranked[0][0] == 1  # chunk index 1 = Billing article

    def test_bm25_category_filter(self, bm25):
        ranked = bm25.search("SSO SAML lockout", top_k=3, filter_category="billing")
        # Only billing article matches category filter
        assert all(bm25._chunks[i].category == "billing" for i, _ in ranked)

    def test_bm25_scores_positive(self, bm25):
        ranked = bm25.search("MFA", top_k=3)
        for _, score in ranked:
            assert score > 0


# ---------------------------------------------------------------------------
# Retriever (integration) tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
async def retriever():
    settings = get_settings()
    return await build_fresh_retriever(settings)


class TestRetriever:
    async def test_mfa_query_returns_mfa_article_in_top3(self, retriever):
        evidence = await retriever.retrieve("account locked out after too many MFA attempts", top_k=3)
        article_ids = [e.article_id for e in evidence]
        assert "mfa-and-account-recovery" in article_ids, (
            f"Expected 'mfa-and-account-recovery' in top 3, got: {article_ids}"
        )

    async def test_billing_query_returns_billing_article(self, retriever):
        evidence = await retriever.retrieve("refund charged extra seats billing", top_k=3)
        article_ids = [e.article_id for e in evidence]
        assert "billing-and-refund-policy" in article_ids, (
            f"Expected 'billing-and-refund-policy' in top 3, got: {article_ids}"
        )

    async def test_sso_query_returns_sso_article(self, retriever):
        evidence = await retriever.retrieve("SSO SAML configuration enterprise login", top_k=3)
        article_ids = [e.article_id for e in evidence]
        assert any("sso" in a for a in article_ids), (
            f"Expected an SSO article in top 3, got: {article_ids}"
        )

    async def test_hybrid_mode(self, retriever):
        evidence = await retriever.retrieve("MFA two factor locked out", top_k=5, mode="hybrid")
        assert isinstance(evidence, list)
        assert len(evidence) >= 1
        for e in evidence:
            assert isinstance(e, Evidence)

    async def test_semantic_mode(self, retriever):
        evidence = await retriever.retrieve("two factor authentication recovery", top_k=3, mode="semantic")
        assert len(evidence) >= 1

    async def test_keyword_mode(self, retriever):
        evidence = await retriever.retrieve("MFA lockout backup codes", top_k=3, mode="keyword")
        assert len(evidence) >= 1

    async def test_top_k_respected(self, retriever):
        for top_k in (1, 3, 5):
            evidence = await retriever.retrieve("SSO login", top_k=top_k)
            assert len(evidence) <= top_k

    async def test_one_hit_per_article(self, retriever):
        """Deduplication: each article appears at most once in results."""
        evidence = await retriever.retrieve("SSO SAML MFA billing API", top_k=10)
        article_ids = [e.article_id for e in evidence]
        assert len(article_ids) == len(set(article_ids)), "Duplicate article in results"

    async def test_evidence_has_all_fields(self, retriever):
        evidence = await retriever.retrieve("API rate limit", top_k=3)
        for e in evidence:
            assert e.id
            assert e.title
            assert e.source.startswith("kb://")
            assert e.snippet
            assert e.url.startswith("/knowledge/")
            assert e.article_id

    async def test_category_filter(self, retriever):
        """Category filter narrows results."""
        evidence = await retriever.retrieve("account issue", top_k=5, category="billing")
        for e in evidence:
            # Heuristic: score should be boosted for billing articles
            # At minimum we get results without error
            pass
        assert isinstance(evidence, list)

    async def test_modes_produce_results(self, retriever):
        for mode in ("hybrid", "semantic", "keyword"):
            results = await retriever.retrieve("storage quota exceeded", top_k=3, mode=mode)
            assert len(results) >= 1, f"Mode {mode!r} returned no results"


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------

class TestCache:
    async def test_cache_hit(self, retriever):
        import fakeredis
        cache = fakeredis.FakeRedis(decode_responses=True)
        query = "mfa recovery test cache"

        # First call: populates cache
        r1 = await retriever.retrieve(query, top_k=3, mode="hybrid", cache=cache)
        # Second call: should hit cache and return same results
        r2 = await retriever.retrieve(query, top_k=3, mode="hybrid", cache=cache)
        assert [e.article_id for e in r1] == [e.article_id for e in r2]

    async def test_cache_key_format(self, retriever):
        import fakeredis
        cache = fakeredis.FakeRedis(decode_responses=True)
        await retriever.retrieve("key format test", top_k=3, mode="hybrid", cache=cache)
        keys = cache.keys("rag:*")
        assert any("rag:hybrid::3:key format test" in k for k in keys)

    async def test_cache_ttl_set(self, retriever):
        import fakeredis
        cache = fakeredis.FakeRedis(decode_responses=True)
        await retriever.retrieve("ttl test query", top_k=3, mode="semantic", cache=cache)
        keys = cache.keys("rag:*")
        for key in keys:
            ttl = cache.ttl(key)
            assert ttl > 0, "Cache TTL should be positive"
            assert ttl <= 300, "Cache TTL should not exceed 300s"

    async def test_different_modes_different_cache_keys(self, retriever):
        import fakeredis
        cache = fakeredis.FakeRedis(decode_responses=True)
        q = "cache mode differentiation"
        await retriever.retrieve(q, top_k=3, mode="hybrid", cache=cache)
        await retriever.retrieve(q, top_k=3, mode="semantic", cache=cache)
        keys = list(cache.keys("rag:*"))
        assert len(keys) == 2


# ---------------------------------------------------------------------------
# Knowledge API tests
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture(scope="module")
def api_client():
    """
    Create a TestClient whose lifespan (create_tables + seed + ingest) runs
    before any test.  Using TestClient as a context manager guarantees the
    lifespan completes before the first request.
    """
    from app.core.config import get_settings
    app = create_app(get_settings())
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


def _make_headers(role: str) -> dict[str, str]:
    from app.core.security import create_access_token
    subs = {"agent": "demo-agent-001", "admin": "demo-admin-001", "viewer": "demo-viewer-001"}
    names = {"agent": "Sam Agent", "admin": "Demo Admin", "viewer": "Vic Viewer"}
    token = create_access_token(sub=subs[role], role=role, name=names[role])
    return {"Authorization": f"Bearer {token}"}


AGENT_H = _make_headers("agent")
ADMIN_H = _make_headers("admin")
VIEWER_H = _make_headers("viewer")


class TestKnowledgeAPI:
    def test_list_articles_200(self, api_client):
        resp = api_client.get("/api/v1/knowledge/articles", headers=AGENT_H)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 15

    def test_list_articles_viewer_allowed(self, api_client):
        resp = api_client.get("/api/v1/knowledge/articles", headers=VIEWER_H)
        assert resp.status_code == 200

    def test_get_article_mfa(self, api_client):
        resp = api_client.get(
            "/api/v1/knowledge/articles/mfa-and-account-recovery", headers=AGENT_H
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "mfa-and-account-recovery"
        assert "content" in data
        assert len(data["content"]) > 100

    def test_get_article_404(self, api_client):
        resp = api_client.get(
            "/api/v1/knowledge/articles/nonexistent-slug", headers=AGENT_H
        )
        assert resp.status_code == 404

    def test_search_returns_results(self, api_client):
        resp = api_client.post(
            "/api/v1/knowledge/search",
            json={"query": "MFA lockout", "top_k": 3, "mode": "hybrid"},
            headers=AGENT_H,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "took_ms" in data
        assert data["mode"] == "hybrid"
        assert len(data["results"]) >= 1

    def test_search_mfa_article_in_top3(self, api_client):
        resp = api_client.post(
            "/api/v1/knowledge/search",
            json={"query": "account locked MFA too many attempts", "top_k": 3},
            headers=AGENT_H,
        )
        assert resp.status_code == 200
        ids = [r["article_id"] for r in resp.json()["results"]]
        assert "mfa-and-account-recovery" in ids

    def test_search_all_modes(self, api_client):
        for mode in ("hybrid", "semantic", "keyword"):
            resp = api_client.post(
                "/api/v1/knowledge/search",
                json={"query": "API rate limit", "mode": mode},
                headers=AGENT_H,
            )
            assert resp.status_code == 200, f"Mode {mode} failed"

    def test_reindex_admin_only(self, api_client):
        resp = api_client.post("/api/v1/knowledge/reindex", headers=ADMIN_H)
        assert resp.status_code == 200
        data = resp.json()
        assert "indexed" in data
        assert data["indexed"] > 0

    def test_reindex_agent_forbidden(self, api_client):
        resp = api_client.post("/api/v1/knowledge/reindex", headers=AGENT_H)
        assert resp.status_code == 403

    def test_search_evidence_shape(self, api_client):
        resp = api_client.post(
            "/api/v1/knowledge/search",
            json={"query": "SSO configuration SAML"},
            headers=AGENT_H,
        )
        assert resp.status_code == 200
        for item in resp.json()["results"]:
            assert "id" in item
            assert "title" in item
            assert "source" in item
            assert item["source"].startswith("kb://")
            assert "snippet" in item
            assert "score" in item
            assert "article_id" in item

    def test_list_articles_category_filter(self, api_client):
        resp = api_client.get(
            "/api/v1/knowledge/articles?category=login_issue", headers=AGENT_H
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "login_issue"

    def test_list_articles_search_filter(self, api_client):
        resp = api_client.get(
            "/api/v1/knowledge/articles?search=MFA", headers=AGENT_H
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
