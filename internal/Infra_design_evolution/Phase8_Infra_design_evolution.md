# Phase 8 — Infrastructure Design Evolution: Memory

## Overview

Phase 8 activates two storage systems that were declared in Phase 1 and 2 but not used:
**Redis** (already running in Docker) and the `customer_memory` table (already defined in
the SQLite/Postgres schema). This phase wires them into the application for the first time.

No new Docker containers are added. Everything runs on the existing infrastructure.

---

## Component map before Phase 8

```mermaid
flowchart TB
    Browser --> NextJS["Next.js :3000"]
    NextJS --> FastAPI["FastAPI :8000"]
    FastAPI --> SQLite[("SQLite\ntickets, customers,\nworkflow_runs, ...")]
    FastAPI --> Redis[("Redis :6379\n(running but unused)")]
    FastAPI --> Qdrant[("Qdrant :6333\nvector store")]

    style Redis fill:#ffa,stroke:#cc8
```

Redis was running but no application code read from or wrote to it.
The `customer_memory` table existed in the schema but had no access layer.

---

## Component map after Phase 8

```mermaid
flowchart TB
    Browser --> NextJS["Next.js :3000"]
    NextJS --> FastAPI["FastAPI :8000"]

    subgraph Memory ["Memory Layer (new in Phase 8)"]
        ST["short_term.py\n(Redis facade)"]
        LT["long_term.py\n(DB facade)"]
        MS["memory_service.py\n(orchestrator)"]
    end

    FastAPI --> MS
    MS --> ST
    MS --> LT

    ST --> Redis[("Redis :6379\nconversations\nworkflow state\nretrieval cache")]
    LT --> DB[("SQLite / Postgres\ncustomer_memory table")]
    FastAPI --> Qdrant[("Qdrant :6333\nvector store")]

    style Redis fill:#3c3,stroke:#0a0,color:#fff
    style DB fill:#3c3,stroke:#0a0,color:#fff
```

Green = now actively used.

---

## Redis connection and key design

### How the connection is made

```mermaid
flowchart LR
    subgraph short_term.py
        GET[_get_redis\ncached client]
    end
    subgraph app/core/redis.py
        GRC[get_redis_client]
    end

    GET --> GRC
    GRC -->|USE_FAKE_REDIS=true| FakeRedis["fakeredis.FakeRedis\n(tests / demo)"]
    GRC -->|REDIS_URL set| RealRedis["redis.from_url\n(production)"]
```

The same `get_redis_client()` function that was defined in Phase 1 is reused.
The short_term module caches the returned client so only one connection exists per process.

### Key namespace and TTL

```mermaid
flowchart TD
    subgraph Redis Keys
        K1["conversation:{ticket_id}\n→ JSON list of messages\nTTL: 86400 s (24 h)"]
        K2["workflow:{workflow_id}\n→ JSON dict (workflow state)\nTTL: 86400 s (24 h)"]
        K3["rag:{mode}:{category}:{top_k}:{query_hash}\n→ JSON list of search results\nTTL: 300 s (5 min)"]
    end
```

The `{query_hash}` is an MD5 of the query string (first 16 chars) to keep key lengths bounded.

---

## Database wiring for long-term memory

### Table already existed — now it has an access layer

```mermaid
flowchart LR
    MS[memory_service.py] --> LT[long_term.py]
    LT --> Session[AsyncSession\nSQLAlchemy]
    Session --> DB[(customer_memory\ntable)]
```

`long_term.py` receives an `AsyncSession` from the caller (always the memory service).
It never creates its own session — sessions are passed in and committed by the caller.
This is the same pattern used in all other repository layers.

### The safety pipeline inside every write

```mermaid
flowchart LR
    INPUT["add_note(customer_id, type, content, session)"]
    INPUT --> V{type valid?}
    V -->|no| ERR[raise ValueError]
    V -->|yes| SCRUB["scrub(content)\nfrom guardrails.py"]
    SCRUB --> BLANK{content blank\nafter scrub?}
    BLANK -->|yes| SKIP[return None]
    BLANK -->|no| DEDUP{exact duplicate\nin DB?}
    DEDUP -->|yes| SKIP2[return None]
    DEDUP -->|no| WRITE[(INSERT customer_memory)]
    WRITE --> RETURN[return CustomerMemory]
```

---

## Data flow: ticket resolved → memory written

```mermaid
sequenceDiagram
    participant Node as memory_update node
    participant Svc as memory_service.py
    participant LT as long_term.py
    participant Guard as guardrails.scrub
    participant DB as customer_memory table

    Node->>Svc: record_resolution(customer_id, ticket_id, subject, steps, summary)
    Svc->>LT: add_note(type="past_issue", content="…")
    LT->>Guard: scrub(content)
    Guard-->>LT: clean content
    LT->>DB: SELECT — duplicate check
    DB-->>LT: not found
    LT->>DB: INSERT
    Svc->>LT: add_note(type="troubleshooting", step 1)
    Note over Svc,LT: repeated for up to 3 steps
    Svc->>LT: add_note(type="note", content=summary)
    LT->>Guard: scrub(content)
    Guard-->>LT: clean content
    LT->>DB: INSERT
```

---

## Data flow: new ticket starts → memory read

```mermaid
sequenceDiagram
    participant Node as customer_context node
    participant Svc as memory_service.py
    participant LT as long_term.py
    participant DB as customer_memory table

    Node->>Svc: recall_customer(customer_id, session)
    Svc->>LT: recall(customer_id, limit=10)
    LT->>DB: SELECT … ORDER BY created_at DESC LIMIT 10
    DB-->>LT: list[CustomerMemory]
    LT-->>Svc: list[CustomerMemory]
    Svc-->>Node: list[dict] — ready for prompt injection
```

---

## Docker Compose: no changes

Phase 8 uses the Redis and SQLite/Postgres services already declared in `docker-compose.yml`.
No new services, volumes, or environment variables are needed.

```mermaid
flowchart TB
    subgraph Compose stack
        FE["frontend\n:3000"]
        BE["backend\n:8000"]
        RD["redis\n:6379"]
        QD["qdrant\n:6333"]
    end

    FE --> BE
    BE --> RD
    BE --> QD
    BE -->|volume mount| SQLiteFile[("./data/support.db")]
```

The `USE_FAKE_REDIS=true` env var in `.env` / `conftest.py` makes tests skip the real Redis
container entirely and use fakeredis in-process instead.

---

## Environment variables involved

| Variable | Default | Effect |
|---|---|---|
| `REDIS_URL` | `""` | Real Redis connection string (e.g. `redis://redis:6379/0`) |
| `USE_FAKE_REDIS` | `false` | `true` → use fakeredis in-process (tests, offline demo) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/support.db` | Where customer_memory rows are stored |

---

## Summary

Phase 8 turns two previously-declared but unused infrastructure components — Redis and the
`customer_memory` table — into a working two-tier memory system. All writes are
secret-scrubbed and de-duplicated before they reach storage. The Docker topology does not
change; only new application code is added.
