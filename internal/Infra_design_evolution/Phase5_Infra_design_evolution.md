# Phase 5 — Infrastructure & Component Wiring: Knowledge Pipeline

---

## Infrastructure baseline from Phase 4

Before Phase 5, the runtime components were:

```mermaid
graph TD
    Browser["Browser\n(localhost:3000)"]
    NextJS["Next.js container\n:3000"]
    FastAPI["FastAPI container\n:8000"]
    SQLite["SQLite file\ndata/support.db"]
    FakeRedis["fakeredis\n(in-process)"]

    Browser -->|HTTPS| NextJS
    NextJS -->|REST /api/v1 + Bearer JWT| FastAPI
    FastAPI -->|aiosqlite| SQLite
    FastAPI -->|fakeredis| FakeRedis
```

Phase 5 adds two new in-process components (**vector store** and **BM25 index**) and one optional
external service (**Qdrant**), plus the ingest pipeline that feeds them.

---

## New components introduced in Phase 5

### Component map

```mermaid
graph TD
    subgraph "FastAPI process (:8000)"
        App["FastAPI app\n(lifespan)"]
        KnowledgeAPI["knowledge router\n/api/v1/knowledge"]
        KnowledgeRepo["KnowledgeRepository\n(DB reads/writes)"]

        subgraph RAG["RAG subsystem (rag/)"]
            Ingest["ingest.py\norchestrator\nglobal _retriever"]
            Chunking["chunking.py\nArticle → ArticleChunk[]"]
            VStore["vector_store.py\nInMemoryVectorStore\n(cosine similarity)"]
            BM25["retriever.py::BM25Index\n(keyword scoring)"]
            Retriever["retriever.py::Retriever\n(hybrid search + RRF)"]
        end
    end

    KB["sample_data/knowledge_base/*.md\n(15 Markdown files)"]
    DB["SQLite data/support.db\n(support_articles table)"]
    FakeRedis["fakeredis\n(RAG cache, TTL=300s)"]

    App -->|lifespan startup| Ingest
    KB -->|load_article_files| Ingest
    Ingest -->|chunk_article| Chunking
    Chunking -->|prefixed_text vectors| VStore
    Chunking -->|token lists| BM25
    VStore -->|stored in RAM| Retriever
    BM25 -->|stored in RAM| Retriever
    KnowledgeAPI --> Retriever
    KnowledgeAPI --> KnowledgeRepo
    KnowledgeRepo --> DB
    Retriever -->|cache.get/set| FakeRedis
```

---

## Startup sequence (lifespan)

When FastAPI starts (or when TestClient enters its context), the lifespan runs:

```mermaid
sequenceDiagram
    participant OS as OS / uvicorn
    participant App as FastAPI lifespan
    participant DB as SQLite
    participant FS as File system (KB)
    participant VS as InMemoryVectorStore
    participant BM as BM25Index
    participant Seed as seed_service

    OS->>App: start lifespan
    App->>DB: create_tables() — create support_articles + other tables
    App->>Seed: bootstrap_demo_data() (DEMO_MODE=true)
    Seed->>DB: INSERT 15 articles into support_articles
    App->>FS: load_article_files("sample_data/knowledge_base")
    FS-->>App: 15 Article objects
    App->>App: chunk each article → ~100-200 ArticleChunks
    App->>VS: add_documents(chunks) — embed + store vectors in RAM
    App->>BM: BM25Index(chunks) — build TF-IDF keyword index in RAM
    App-->>OS: lifespan complete, server ready
```

---

## Request flow: knowledge search

```mermaid
sequenceDiagram
    participant UI as Support agent UI
    participant GW as FastAPI /api/v1/knowledge/search
    participant Auth as JWT middleware
    participant Redis as fakeredis (cache)
    participant Ret as Retriever
    participant VS as InMemoryVectorStore
    participant BM as BM25Index

    UI->>GW: POST /api/v1/knowledge/search\n{query: "MFA locked out", top_k: 5}
    GW->>Auth: verify Bearer token (role ≥ viewer)
    Auth-->>GW: OK, user = {role: agent}
    GW->>Ret: retrieve(query, top_k=5, mode="hybrid")
    Ret->>Redis: GET rag:hybrid::5:MFA locked out
    Redis-->>Ret: cache miss

    Ret->>VS: search("MFA locked out", top_k=10)
    VS->>VS: embed(query) → 384-dim vector
    VS->>VS: cosine_similarity(query_vec, all_vecs)
    VS-->>Ret: top 10 semantic hits

    Ret->>BM: search("MFA locked out", top_k=10)
    BM->>BM: tokenise + BM25 scores
    BM-->>Ret: top 10 keyword hits

    Ret->>Ret: RRF(semantic_hits, keyword_hits, k=60)
    Ret->>Ret: heuristic rerank (category + title overlap)
    Ret->>Ret: deduplicate by article_id

    Ret->>Redis: SET rag:hybrid::5:MFA locked out\n(TTL=300s)
    Ret-->>GW: Evidence[] (top 5 results)
    GW-->>UI: 200 OK — [{id, title, source, snippet, score, url}]
```

---

## Request flow: article list / detail

```mermaid
sequenceDiagram
    participant UI as Support agent UI
    participant GW as FastAPI /api/v1/knowledge
    participant Auth as JWT middleware
    participant Repo as KnowledgeRepository
    participant DB as SQLite support_articles

    UI->>GW: GET /api/v1/knowledge/articles
    GW->>Auth: verify Bearer token (role ≥ viewer)
    Auth-->>GW: OK
    GW->>Repo: list_articles(page=1, page_size=20)
    Repo->>DB: SELECT * FROM support_articles LIMIT 20
    DB-->>Repo: 15 rows
    Repo-->>GW: ArticleListResponse {items: [...], total: 15}
    GW-->>UI: 200 OK
```

---

## Docker Compose wiring (Phase 5 additions)

Phase 5 adds no new containers. The vector store and BM25 index are **in-process** RAM structures
inside the FastAPI container. The optional Qdrant service was already defined in `docker-compose.yml`
and is only activated in production.

```mermaid
graph LR
    subgraph compose["docker-compose.yml"]
        FE["frontend\n:3000\n(Next.js)"]
        BE["backend\n:8000\n(FastAPI + RAG in RAM)"]
        Redis["redis\n:6379"]
        Qdrant["qdrant\n:6333\n(optional production VS)"]
        Vol1[("vol: sqlite-data")]
        Vol2[("vol: qdrant-data")]
    end

    FE -->|depends_on healthy| BE
    BE -->|depends_on healthy| Redis
    BE -->|VECTOR_STORE=qdrant| Qdrant
    BE --> Vol1
    Qdrant --> Vol2
```

Environment variable that controls which vector store is used:

| `VECTOR_STORE` | Used in | Vector store |
|---|---|---|
| `memory` (default) | Tests, demo | InMemoryVectorStore (RAM) |
| `qdrant` | Production | QdrantVectorStore (Qdrant container) |

---

## Environment variables added in Phase 5

| Variable | Default | Purpose |
|---|---|---|
| `VECTOR_STORE` | `memory` | Switch between in-memory and Qdrant |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant service address |
| `QDRANT_API_KEY` | *(empty)* | Qdrant API key (production) |
| `QDRANT_COLLECTION` | `clouddesk_knowledge` | Collection name in Qdrant |
| `EMBEDDING_PROVIDER` | `fake` | Embedding model provider |
| `EMBEDDING_MODEL` | `fake` | Model name |
| `EMBEDDING_DIMENSIONS` | `384` | Vector dimensions (must match model) |
| `SAMPLE_DATA_DIR` | `sample_data` | Root dir for KB articles |

---

## Health and observability

The `/health/ready` endpoint already checks the vector store:

```mermaid
flowchart LR
    Probe["GET /health/ready"]
    DB["database ✓"]
    Redis["redis ✓"]
    VS["vector_store ✓\n(always ok for 'memory')"]
    LLM["llm ✓\n(fake provider = ok)"]
    Probe --> DB
    Probe --> Redis
    Probe --> VS
    Probe --> LLM
```

The ingest pipeline logs the number of chunks indexed at startup, visible in JSON logs:
```json
{"event": "ingest_complete", "chunks": 143, "articles": 15, "elapsed_ms": 240}
```

---

## Reindex flow (admin operation)

```mermaid
sequenceDiagram
    participant Admin as Admin user
    participant GW as POST /api/v1/knowledge/reindex
    participant Auth as JWT (role=admin)
    participant Ingest as run_ingest(force=True)
    participant VS as VectorStore
    participant BM as BM25Index
    participant DB as SQLite

    Admin->>GW: POST /api/v1/knowledge/reindex
    GW->>Auth: verify role = admin
    Auth-->>GW: OK
    GW->>Ingest: run_ingest(settings, force=True)
    Ingest->>VS: delete all documents
    Ingest->>VS: add_documents(new chunks)
    Ingest->>BM: rebuild BM25Index
    Ingest->>DB: upsert articles into support_articles
    Ingest-->>GW: chunk_count = 143
    GW-->>Admin: 200 {chunks_indexed: 143, articles_indexed: 15}
```
