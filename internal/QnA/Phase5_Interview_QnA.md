# Phase 5 — Interview Q&A: Knowledge Pipeline

---

## Fundamentals

**Q: What is RAG and why do you use it here?**

RAG stands for Retrieval-Augmented Generation. Instead of asking the LLM to answer purely from
its training data, we first retrieve relevant passages from our own knowledge base and include them
in the prompt. This means the AI's answers are grounded in up-to-date, company-specific information
rather than general knowledge, and every claim can be cited back to a specific help article.

---

**Q: Why chunk articles instead of passing the whole document to the LLM?**

Two reasons: (1) LLMs have context limits — a 15-article knowledge base would exceed them, and
even if it didn't, attention quality degrades with long contexts. (2) Smaller chunks produce better
embeddings. A 900-character passage about "MFA lockout recovery" embeds more precisely than a 3,000-
word article that covers many topics. The overlap (150 chars) prevents sentences from being split
across chunk boundaries.

---

**Q: What is a vector embedding?**

An embedding is a list of numbers (a vector) that represents the *meaning* of a piece of text.
Similar meanings produce similar vectors. We measure similarity using cosine similarity — the angle
between two vectors. The key property: "account locked out" and "can't log in" produce similar
vectors even though they share no words.

---

**Q: What are FakeEmbeddings and when do you use them?**

FakeEmbeddings is a deterministic, offline embedding function we wrote in-house. It converts each
word into a hash-based index in a 384-dimension vector, then normalises the vector to unit length.
It produces no semantic meaning — just a consistent fingerprint per word combination — but it's
sufficient for integration tests, demos, and CI because it needs no API key and runs in milliseconds.
We switch to real embeddings (OpenAI `text-embedding-3-small` or similar) in production by changing
`EMBEDDING_PROVIDER`.

---

**Q: What is BM25 and why keep it alongside vector search?**

BM25 is a classic keyword-scoring algorithm (Best Match 25) that scores documents by term frequency
adjusted for document length. It excels at exact-term matching — "HTTP 429", "SAML assertion", API
endpoint names — where semantic search may fail because those terms appear infrequently in training
data. Hybrid search (combining both) outperforms either alone.

---

## Architecture

**Q: Why use a Protocol for VectorStoreService instead of a base class?**

Python Protocols are structural subtypes — a class satisfies the Protocol if it has the right
methods, regardless of inheritance. This means `InMemoryVectorStore` and `QdrantVectorStore` can
be developed and tested independently. The app selects the implementation at startup via
`get_vector_store(settings)` based on the `VECTOR_STORE` env var. The rest of the codebase only
ever sees the Protocol, so swapping implementations requires zero changes to callers.

---

**Q: Explain Reciprocal Rank Fusion (RRF). Why not just average the scores?**

Semantic similarity scores (0.0–1.0 cosine distance) and BM25 scores (unbounded positive numbers)
live on completely different scales. Averaging them directly would let one dominate. RRF converts
each ranked list into a score based on position: `1 / (k + rank)`, where k=60 is a smoothing
constant. A chunk that ranks #1 in both lists scores approximately `1/61 + 1/61 ≈ 0.033`. A chunk
that ranks #1 in one and #10 in the other scores `1/61 + 1/70 ≈ 0.030`. This is scale-invariant,
empirically robust, and requires no tuning per domain.

---

**Q: What is the cache key format and why does it include `mode` and `category`?**

```
rag:{mode}:{category}:{top_k}:{query}
```

- `mode` — hybrid, semantic, and keyword searches return different results even for the same query.
- `category` — a filtered search (e.g., billing articles only) returns different results than an
  unfiltered one.
- `top_k` — requesting 3 vs 10 results are different operations.
- `query` — the actual query text.

Using all four ensures we never serve a cached response that doesn't match the caller's parameters.
TTL is 300 seconds (5 minutes) — long enough to handle multiple agents asking similar questions in
a burst, short enough to pick up reindexed content quickly.

---

**Q: Why is the ingest pipeline idempotent? What does `force=False` do?**

On server startup we don't want to re-embed and re-index 150 chunks every time the server restarts
(which would be slow and wasteful in production). `run_ingest` checks whether `_retriever` is already
populated. If it is and `force=False`, it returns immediately. The `POST /knowledge/reindex` endpoint
passes `force=True` to rebuild the index — used after adding new articles or changing the embedding
model.

---

**Q: Why is `SupportArticle` stored in SQL if the full article text is also loaded from files?**

Two reasons: (1) The API endpoints (`GET /knowledge/articles`) need to list and paginate articles —
SQL is better for that than scanning 15 files on every request. (2) Future phases may allow agents
to flag articles for review or add notes, which requires a durable record. The SQLite row is the
canonical store; the file system is the source of truth for content, and the seed service syncs them
at startup.

---

## Testing

**Q: How do you test the RAG pipeline with no API key and no network?**

Three strategies: (1) FakeEmbeddings for deterministic vectors. (2) `InMemoryVectorStore` instead
of Qdrant. (3) `USE_FAKE_REDIS=true` for the cache. All test environment variables are set in
`tests/conftest.py` before any app code is imported. The full test suite runs in ~10 seconds with
no external dependencies.

---

**Q: Why use `pytest-asyncio` with `scope="session"` for the event loop?**

The retriever's `retrieve()` method is async. If each test created its own event loop, async
fixtures like the `Retriever` instance would be torn down and recreated for every test, which is
slow. Session scope means one event loop and one `Retriever` instance for the entire test run. The
trade-off is that tests in the same session share state — we isolate this by using
`build_fresh_retriever()` which does not touch the global `_retriever`.

---

**Q: The TestKnowledgeAPI tests use a sync TestClient inside a pytest-asyncio session. Why use a
context manager for the TestClient?**

`TestClient` starts the ASGI lifespan (which calls `create_tables()`) when it enters its context
manager (`__enter__`). Without `with TestClient(...) as client:`, the lifespan may start lazily on
the first request and, in an environment where pytest-asyncio already manages an event loop,
the internal `anyio.from_thread.start_blocking_portal()` call may not complete the lifespan
synchronously before the first test runs. Using `with TestClient(app) as client: yield client`
guarantees the lifespan is fully started (tables created, seed loaded, ingest complete) before any
assertion runs.

---

**Q: What would break if someone deleted `tests/rag/__init__.py` by accident — wait, there IS no
`__init__.py`. Why?**

This is intentional. With `--import-mode=importlib` (set in `pyproject.toml`), pytest imports test
files as top-level modules rather than as subpackages. If `tests/rag/__init__.py` existed, pytest
would try to import `tests/rag/conftest.py` as the `rag` package — conflicting with the actual
`rag/` package at the project root. The absence of `__init__.py` in `tests/rag/` is the fix.

---

## Production and operations

**Q: How would you switch from the in-memory vector store to Qdrant in production?**

Set `VECTOR_STORE=qdrant`, `QDRANT_URL=http://qdrant:6333`, and `QDRANT_API_KEY=<key>` in the
production `.env` file. The `get_vector_store(settings)` factory returns a `QdrantVectorStore`
instead of `InMemoryVectorStore`. Then call `POST /api/v1/knowledge/reindex` once after deployment
to populate the Qdrant collection. No code changes needed.

---

**Q: What happens if the knowledge base ingest fails at startup?**

The lifespan wraps `run_ingest()` in a `try/except`. On failure it logs a warning and continues
server startup. The knowledge search endpoints will return empty results (the retriever global is
not set) but all other endpoints remain operational. This is intentional — a missing KB should not
take down the entire support platform.

---

**Q: If you change the embedding model, do you need to do anything special?**

Yes — you must call `POST /api/v1/knowledge/reindex` (admin role required) after changing the model.
The old vectors in the store were computed by the old model and are incompatible with the new one.
Calling reindex with `force=True` deletes all old vectors, re-embeds every chunk with the new model,
and rebuilds the BM25 index. CLAUDE.md explicitly states: "Changing the embedding model requires
`POST /knowledge/reindex` — it recreates the collection."

---

**Q: What security considerations apply to the knowledge API?**

- All endpoints require authentication (JWT Bearer token, role ≥ `viewer`).
- `POST /reindex` requires `admin` role (can disrupt service if abused).
- Article content comes from internal Markdown files, not user input, so injection is not a concern
  here. However, the search query (`KnowledgeSearchRequest.query`) is user-supplied and is not
  executed as SQL — it is passed to the vector store's embed function and to BM25, neither of which
  is vulnerable to injection.
- Evidence snippets returned by search are article content, not user data, so there is no risk of
  leaking one customer's data to another.
