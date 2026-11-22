# Phase 2 — System Design Evolution

> This document traces how the system design grew during Phase 2, from "a web server with no memory" to "a web server with a full data model and seeded demo data." Each stage shows what was added, why, and how the design changed.

---

## Starting point: End of Phase 1

At the end of Phase 1, the system looked like this:

```mermaid
graph TD
    browser["Browser / Load Balancer"]
    cors["CORSMiddleware"]
    rid["RequestIdMiddleware"]
    fastapi["FastAPI"]
    health["Health Routes\n/health /health/live /health/ready"]
    config["Settings\n(lru_cached)"]
    jsonlog["JsonFormatter → stdout"]

    browser --> cors --> rid --> fastapi
    fastapi --> health
    health --> config
    rid -.-> jsonlog
```

**What was missing:** No database, no data model, no way to store or retrieve anything.

---

## Stage 1 — After P2-1: Enums and SQLAlchemy Models

The first step of Phase 2 defines **what the data looks like** — the vocabulary and blueprints.

### What was added
- `backend/app/schemas/common.py` — Category, TicketStatus, Severity, Channel enums
- `backend/app/models/entities.py` — 16 SQLAlchemy model classes
- `backend/app/core/database.py` — Engine factory, `create_tables()`, `get_session()`

### Schema (data vocabulary)

The enums define the fixed vocabulary for the entire system. Nothing can be stored outside these values:

```mermaid
graph LR
    subgraph "Fixed Vocabularies (schemas/common.py)"
        cat["Category\n10 values\nlogin_issue | billing\napi_failure | security\n..."]
        status["TicketStatus\n7 values\nnew → in_progress\n→ resolved → closed\n..."]
        sev["Severity\n4 levels\nlow | medium\nhigh | critical"]
        chan["Channel\n4 values\nemail | chat\nweb | api"]
    end
```

### Data model (16 tables)

```mermaid
erDiagram
    customers ||--o{ subscriptions : "has"
    customers ||--o{ workspaces : "owns"
    customers ||--o{ tickets : "submits"
    customers ||--o{ customer_memory : "remembered in"

    tickets ||--o{ ticket_messages : "has"
    tickets ||--o{ workflow_runs : "processed by"
    tickets ||--o{ approval_requests : "pauses for"
    tickets ||--o{ escalations : "routed to"

    workflow_runs ||--o{ workflow_events : "emits"
    workflow_runs ||--o{ resolution_actions : "plans"
    workflow_runs ||--o{ approval_requests : "generates"

    profiles ||--o{ tickets : "assigned to"
    support_articles }o--o{ tickets : "cited in resolution"

    products }|--|| subscriptions : "defines limits for"
    incidents }|--o| tickets : "context for"
```

### SQLAlchemy engine setup

```mermaid
graph TD
    env["DATABASE_URL env var"]
    engine["AsyncEngine\n(create_async_engine)"]
    session["async_sessionmaker\n(session factory)"]
    metadata["Base.metadata\n(all 16 tables)"]

    env --> engine
    engine --> session
    metadata -->|"create_all(conn)"| engine

    subgraph "Per-request lifecycle"
        ctx["get_session()\nasync context manager"]
        begin["BEGIN transaction"]
        commit["COMMIT on success"]
        rollback["ROLLBACK on exception"]
    end

    session --> ctx
    ctx --> begin --> commit
    ctx --> rollback
```

### Key design decisions at this stage

| Decision | Why |
|---|---|
| `String(36)` for UUIDs (not native UUID type) | SQLite has no UUID type; String works on both SQLite and Postgres |
| `JSON` not `JSONB` for column type | SQLite uses JSON; Postgres uses JSONB. The SQLAlchemy `JSON` type maps to whichever is native |
| `Base.metadata.create_all()` at startup | Zero-config for new developers — the database is ready after `make backend` |
| `get_session()` as async context manager | Guarantees connection release even if an exception occurs mid-request |

---

## Stage 2 — After P2-2: Postgres Schema and RLS

The authoritative SQL definition and the cloud-database security layer are added. No new Python runtime code — this stage is about the cloud/production picture.

### What was added
- `database/schema.sql` — Postgres DDL with triggers, indexes, CHECK constraints
- `database/rls_policies.sql` — Row Level Security policies
- `database/migrations/0001_initial.sql` — First migration file

### Two-layer security model

```mermaid
graph TD
    subgraph "Application Layer (Python)"
        api["FastAPI routes"]
        rbac["require_role()\n(Phase 3 — not yet)"]
    end

    subgraph "Database Layer (Supabase/Postgres)"
        rls["Row Level Security\nPolicies"]
        trigger["updated_at trigger\n(every table)"]
        checks["CHECK constraints\n(enums enforced at DB level)"]
    end

    api -->|"service-role key\nbypasses RLS"| rls
    browser["Browser (anon key)"] -->|"subject to RLS"| rls
    rls --> data["Data Tables"]
    data --> trigger
    data --> checks
```

**Why two layers?** Defence in depth. If the application layer has a bug (e.g., a missing permission check), the database's RLS policies still prevent unauthorised reads and writes. This is a standard security pattern for Supabase applications.

### Migration strategy

```mermaid
graph LR
    v0["Empty DB"] -->|"0001_initial.sql"| v1["Schema v1\n(16 tables)"]
    v1 -->|"0002_*.sql\n(future)"| v2["Schema v2"]
    v2 -->|"0003_*.sql\n(future)"| v3["Schema v3"]

    note["Rule: Never edit\nan applied migration.\nOnly add new files."]
```

---

## Stage 3 — After P2-3: Repository Layer

The repository layer adds a clean separation between "how to access data" and "what to do with data."

### What was added
- `backend/app/repositories/base.py` — `BaseRepository` with generic CRUD
- `backend/app/repositories/customer_repository.py` — customer-specific queries
- `backend/app/repositories/ticket_repository.py` — ticket-specific queries

### Repository architecture

```mermaid
graph TD
    subgraph "Callers (future phases)"
        api["API routes\n(Phase 4)"]
        agents["AI Agents\n(Phase 9)"]
        seed["seed_service.py"]
    end

    subgraph "Repository Layer"
        base["BaseRepository[T]\nget | list | create | update | count"]
        cust["CustomerRepository\n+ get_by_email\n+ get_by_external_id"]
        tick["TicketRepository\n+ get_by_number\n+ list_by_customer\n+ list_recent"]
        sub["SubscriptionRepository\n+ get_by_customer"]
        ws["WorkspaceRepository\n+ get_by_customer\n+ get_by_slug"]
    end

    subgraph "Data Layer"
        session["AsyncSession\n(SQLAlchemy)"]
        db["SQLite / PostgreSQL"]
    end

    api --> cust
    api --> tick
    agents --> cust
    agents --> tick
    seed --> cust
    seed --> tick

    cust --> base --> session --> db
    tick --> base --> session --> db
    sub --> base
    ws --> base
```

### Why the repository pattern matters

```mermaid
graph LR
    subgraph "Without repository (bad)"
        a1["Agent code"] -->|"SELECT * FROM tickets WHERE..."| db1["Database"]
        a2["API code"] -->|"SELECT * FROM tickets WHERE..."| db1
        a3["Seed code"] -->|"SELECT * FROM tickets WHERE..."| db1
        note1["Change: ticket_number → number\n→ update 3+ places"]
    end

    subgraph "With repository (good)"
        b1["Agent code"] --> repo["TicketRepository\n.get_by_number()"]
        b2["API code"] --> repo
        b3["Seed code"] --> repo
        repo -->|"query lives here\nChange once, fixed everywhere"| db2["Database"]
    end
```

---

## Stage 4 — After P2-4: Sample Data and Demo Bootstrap (Final Phase 2 State)

The system now starts up and loads itself with realistic demo data automatically.

### What was added
- `sample_data/*.json` — 7 JSON files (customers, subscriptions, workspaces, products, incidents, tickets, previous_resolutions)
- `sample_data/knowledge_base/*.md` — 15 knowledge articles
- `backend/app/services/seed_service.py` — idempotent bootstrap service
- `main.py` lifespan updated to call `create_tables()` and `bootstrap_demo_data()`

### Complete Phase 2 system design

```mermaid
graph TD
    subgraph "Startup sequence (main.py lifespan)"
        step1["1. setup_logging()"]
        step2["2. create_tables()\n(16 tables in SQLite/Postgres)"]
        step3["3. bootstrap_demo_data()\n(only if DEMO_MODE=true and DB is empty)"]
    end

    subgraph "sample_data/"
        cj["customers.json\n8 customers"]
        sj["subscriptions.json\n8 subscriptions"]
        wj["workspaces.json\n9 workspaces"]
        pj["products.json\n4 products"]
        ij["incidents.json\n2 incidents"]
        tj["tickets.json\n13 tickets"]
        kb["knowledge_base/\n15 Markdown articles"]
    end

    subgraph "seed_service.py"
        sc["_seed_customers()"]
        ss["_seed_subscriptions()"]
        sw["_seed_workspaces()"]
        sp["_seed_products()"]
        si["_seed_incidents()"]
        st["_seed_tickets()"]
    end

    subgraph "Repository Layer"
        cr["CustomerRepository"]
        tr["TicketRepository"]
    end

    subgraph "Database (SQLite in dev)"
        db["16 tables\n(Base.metadata)"]
    end

    step1 --> step2 --> step3
    step3 --> sc --> cr --> db
    step3 --> ss --> db
    step3 --> sw --> db
    step3 --> sp --> db
    step3 --> si --> db
    step3 --> st --> tr --> db

    cj --> sc
    sj --> ss
    wj --> sw
    pj --> sp
    ij --> si
    tj --> st
```

### Idempotency guarantee

```mermaid
sequenceDiagram
    participant Boot as Startup
    participant Seed as seed_service
    participant Repo as Repository
    participant DB as Database

    Boot->>Seed: bootstrap_demo_data()
    Seed->>Repo: exists_by_external_id("CUST-0001")?
    Repo->>DB: SELECT id WHERE external_id="CUST-0001"
    DB-->>Repo: row found
    Repo-->>Seed: True (exists)
    Seed->>Seed: skip (no INSERT)

    Note over Boot,DB: Second startup — no duplicates created
```

---

## Summary: What changed and why across Phase 2

| Stage | Files | What it enabled |
|---|---|---|
| P2-1 | `schemas/common.py`, `models/entities.py`, `core/database.py` | Data vocabulary; 16-table schema; engine and session management |
| P2-2 | `database/schema.sql`, `rls_policies.sql`, `migrations/` | Cloud-ready Postgres DDL; two-layer security; migration history |
| P2-3 | `repositories/base.py`, `customer_repository.py`, `ticket_repository.py` | Clean data access layer; callers never write raw SQL |
| P2-4 | `sample_data/`, `services/seed_service.py`, `main.py` updated | Realistic demo data loaded at startup; `make seed` command |

After Phase 2, the system:
- Has a complete, portable data model (SQLite for development, Postgres for production)
- Loads 13 demo tickets, 8 customers, and 15 knowledge articles automatically
- Provides a clean repository layer all future phases will use
- Has 34 passing tests that run offline in ~5 seconds

The next phases build on this foundation: Phase 3 adds authentication, Phase 4 adds the HTTP API routes that expose this data to the frontend.
