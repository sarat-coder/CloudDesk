# Phase 5 — System Design Evolution: Knowledge Pipeline

---

## Starting point: What we had after Phase 4

After Phase 4, the system had a working support API — tickets could be created, listed, updated,
and assigned. But the AI workflow had no knowledge retrieval capability. The design was:

```mermaid
flowchart LR
    Browser -->|HTTPS| NextJS["Next.js :3000"]
    NextJS -->|REST /api/v1| FastAPI["FastAPI :8000"]
    FastAPI --> DB["SQLite / PostgreSQL\n(tickets, customers,\n subscriptions)"]
    FastAPI --> Redis["Redis / fakeredis\n(rate limit, cache)"]
    FastAPI -->|No LLM yet| LLM["LLM Provider\n(fake/openai)"]
```

**Gap:** No knowledge base. No way to retrieve relevant help articles. No citations.

---

## Task 5.1 — Article loading and chunking

The first step was to ingest the 15 Markdown articles in `sample_data/knowledge_base/`.

### Design — article loader

```mermaid
flowchart TD
    subgraph Input
        MD["*.md files\n(YAML front-matter\n+ Markdown body)"]
    end

    subgraph chunking.py
        Load["load_article_files(kb_dir)\n→ list[Article]"]
        Split["_split_sections(article)\n→ [(heading, text)]"]
        Window["_sliding_windows(text, 900, 150)\n→ list[str]"]
        Prefix["ArticleChunk\nid = '{slug}#chunk-{n}'\nprefixed_text = '{title} - {heading}: {text}'"]
    end

    MD --> Load --> Split --> Window --> Prefix
```

Each `Article` holds: `slug`, `title`, `category`, `tags`, `summary`, `body`.

Each `ArticleChunk` holds everything needed to embed and return as a search result:
- `id`, `article_id`, `title`, `heading`, `text`
- `prefixed_text` — what actually gets embedded (richer context)
- `source` = `"kb://{slug}#{chunk-id}"`, `snippet` = first 120 chars

### Design after Task 5.1

```mermaid
flowchart LR
    KB["sample_data/\nknowledge_base/*.md"]
    ChunkPY["rag/chunking.py\nArticle + ArticleChunk"]
    KB --> ChunkPY
    style ChunkPY fill:#d4edda
```

---

## Task 5.2 — Embeddings and Vector Store

### Design — vector store protocol

A `Protocol` interface means the app can swap providers without touching the rest of the code.

```mermaid
classDiagram
    class VectorStoreService {
        <<Protocol>>
        +add_documents(docs) None
        +search(query, top_k, filter_category) SearchResult[]
        +delete(ids) None
        +count() int
        +health() bool
    }
    class InMemoryVectorStore {
        -_docs: list[Document]
        +add_documents()
        +search() SearchResult[]
    }
    class QdrantVectorStore {
        -_client: QdrantClient
        +add_documents()
        +search() SearchResult[]
    }
    VectorStoreService <|.. InMemoryVectorStore
    VectorStoreService <|.. QdrantVectorStore
```

**FakeEmbeddings** — deterministic 384-dim hashed bag-of-words, normalised to unit length. Works
fully offline, no API key required.

### Design after Task 5.2

```mermaid
flowchart LR
    ChunkPY["rag/chunking.py"]
    VStore["rag/vector_store.py\nInMemoryVectorStore\n(or QdrantVectorStore)"]
    Embed["_embed(text) → 384-dim vector\n(FakeEmbeddings in demo)"]

    ChunkPY -->|prefixed_text| Embed --> VStore
    style VStore fill:#d4edda
    style Embed fill:#d4edda
```

---

## Task 5.3 — Retriever with hybrid search

This is the core intelligence of the pipeline.

### Design — retrieval flow

```mermaid
flowchart TD
    Query["User query string"]

    subgraph Semantic["Semantic search"]
        EmbedQ["embed(query)"]
        CosSim["cosine similarity\nvs all chunk vectors"]
        TopSem["top-k semantic hits"]
    end

    subgraph Keyword["Keyword search  (BM25)"]
        Tokenise["tokenise query"]
        BM25Score["BM25 score\n(k1=1.5, b=0.75)"]
        TopKW["top-k keyword hits"]
    end

    subgraph Fusion["Reciprocal Rank Fusion (k=60)"]
        RRF["score = 1/(k + rank_sem) + 1/(k + rank_kw)"]
        Rerank["Heuristic rerank:\n• category match +0.1\n• title word overlap"]
        Dedup["One hit per article_id"]
    end

    Query --> EmbedQ --> CosSim --> TopSem --> RRF
    Query --> Tokenise --> BM25Score --> TopKW --> RRF
    RRF --> Rerank --> Dedup --> Evidence["Evidence[]"]
```

### Cache layer

```mermaid
flowchart LR
    Call["retrieve(query, top_k, mode, category)"]
    Key["cache_key =\n'rag:{mode}:{category}:{top_k}:{query}'"]
    Redis["Redis / fakeredis\nTTL = 300 s"]
    Result["Evidence[]"]

    Call --> Key
    Key -->|hit| Redis -->|deserialise| Result
    Key -->|miss| Retrieve["run search"] --> Redis
    Retrieve --> Result
```

---

## Task 5.4 — Ingest orchestrator

```mermaid
flowchart TD
    Start["run_ingest(settings, force=False)"]
    Check{Already\nindexed?}
    Load["load_article_files(kb_dir)\n→ Article[]"]
    Chunk["chunk_article(article)\n→ ArticleChunk[]"]
    Embed["embed each chunk\n(FakeEmbeddings or real)"]
    Store["vector_store.add_documents()\nBM25Index(chunks)"]
    Global["_retriever = Retriever(store, bm25)\n_chunks = chunks"]

    Start --> Check
    Check -->|yes and not force| Skip["return 0"]
    Check -->|no or force| Load --> Chunk --> Embed --> Store --> Global
    Global --> Return["return len(chunks)"]
```

---

## Task 5.5 — Knowledge API

```mermaid
flowchart LR
    Agent["Support agent\nor AI workflow"]

    subgraph API["FastAPI /api/v1/knowledge"]
        List["GET /articles → ArticleListResponse"]
        Detail["GET /articles/{slug} → ArticleDetailResponse"]
        Search["POST /search → KnowledgeSearchResponse"]
        Reindex["POST /reindex → ReindexResponse (admin only)"]
    end

    subgraph Services
        Repo["KnowledgeRepository\n(DB reads/writes)"]
        Retriever["Retriever\n(vector + BM25 search)"]
    end

    Agent --> List --> Repo
    Agent --> Detail --> Repo
    Agent --> Search --> Retriever
    Agent --> Reindex
    Reindex -->|force=True| IngestPipeline["run_ingest(force=True)"]
    Reindex --> Repo
```

---

## Final design after Phase 5

```mermaid
flowchart TD
    Browser -->|HTTPS| NextJS["Next.js :3000"]
    NextJS -->|REST /api/v1| FastAPI["FastAPI :8000"]

    FastAPI --> DB["SQLite / PostgreSQL\n(tickets, customers, support_articles, …)"]
    FastAPI --> Redis["Redis / fakeredis\n(rate limit, RAG cache 300 s)"]
    FastAPI --> LLM["LLM Provider\n(fake / openai / anthropic)"]

    subgraph RAG["RAG Pipeline (new in Phase 5)"]
        Chunking["rag/chunking.py\nload + chunk articles"]
        VectorStore["rag/vector_store.py\nInMemory / Qdrant"]
        BM25["BM25 keyword index"]
        Retriever["rag/retriever.py\nHybrid → RRF → rerank"]
        Ingest["rag/ingest.py\norchestrator"]
    end

    KB["sample_data/\nknowledge_base/*.md"] --> Ingest
    Ingest --> Chunking --> VectorStore
    Ingest --> Chunking --> BM25
    Retriever --> VectorStore
    Retriever --> BM25
    FastAPI -->|knowledge API| Retriever
    FastAPI -->|article DB| DB

    style RAG fill:#e8f4f8
```

---

## Design decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| Protocol for VectorStoreService | Swap in-memory ↔ Qdrant without touching retriever code | Slightly more boilerplate |
| FakeEmbeddings (hashed bag-of-words) | Fully offline, deterministic, testable with no API key | Lower quality than real embeddings; must reindex when switching |
| Sliding windows (900 / 150 overlap) | Short chunks stay retrievable; overlap prevents boundary cuts | More chunks = more storage and slower ingest |
| Reciprocal Rank Fusion (not score fusion) | Scores from semantic and BM25 are on different scales; ranks are comparable | Does not exploit score magnitude |
| One result per article | Prevents one verbose article from dominating results | May miss two distinct sections from the same article |
| Cache keyed on mode + category + top_k + query | Different parameters need different cached results | Cache size grows with parameter combinations |
