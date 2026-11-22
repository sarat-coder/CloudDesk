# Phase 2 — Infrastructure Design Evolution

> This document explains how the infrastructure, storage, and component wiring of CloudDesk evolves through Phase 2. Each section covers what exists at a given point, how data flows between components, and why the choices were made.

---

## What "infrastructure" means in Phase 2

Phase 2 introduces the first **persistent storage layer**. Before Phase 2, the app had no databases — everything lived in process memory and disappeared on restart. After Phase 2:

- A SQLite file (`data/support.db`) stores all application data locally.
- An async SQLAlchemy engine manages connections.
- The seed service writes demo data into the database on first startup.

Docker and cloud databases are still future phases (Phase 14 and production deployment). But the **wiring patterns** established here are exactly what the Docker stack will follow later.

---

## Stage 1 — After P2-1: Database Engine Added to the Runtime

The first infrastructure addition is the database engine and session management.

### Component wiring

```mermaid
graph TD
    subgraph "File System"
        envfile[".env\nDATABASE_URL=sqlite+aiosqlite:///./data/support.db"]
        dbfile["data/support.db\n(SQLite file, git-ignored)"]
    end

    subgraph "Python Process (:8000)"
        config["Settings\n(get_settings)"]
        engine["AsyncEngine\n(create_async_engine)"]
        factory["async_sessionmaker"]
        metadata["Base.metadata\n(16 table definitions)"]
        tables["create_tables()\ncreates schema on startup"]
    end

    envfile -->|"DATABASE_URL"| config
    config -->|"database_url"| engine
    engine --> factory
    metadata -->|"create_all(conn)"| engine
    engine --> dbfile
    tables --> engine
```

### Key wiring rules established here

1. **`DATABASE_URL` controls everything.** Change one environment variable to switch from SQLite to PostgreSQL. The application code never imports a specific database driver.
2. **`create_tables()` is idempotent.** It uses `create_all(checkfirst=True)`, meaning it only creates tables that do not already exist. Running it twice is safe.
3. **`AsyncEngine` with `aiosqlite`.** Python's `asyncio` allows the web server to handle thousands of concurrent requests while some are waiting for database I/O. The async engine is essential for performance.

---

## Stage 2 — After P2-2: Postgres Schema (Cloud-Ready Wiring)

This stage establishes what the infrastructure looks like when deployed to the cloud. No new Python runtime code — this is about the Supabase/Postgres picture.

### Local vs. cloud infrastructure

```mermaid
graph TD
    subgraph "Local Development (Phase 2 today)"
        dev_app["FastAPI Process\n:8000"]
        dev_db["SQLite File\ndata/support.db\n(local disk)"]
        dev_app -->|"aiosqlite driver"| dev_db
    end

    subgraph "Cloud / Production (Phase 14+)"
        cloud_app["FastAPI Container\n(ECS / Cloud Run)"]
        supabase["Supabase / PostgreSQL\n(managed, external)"]
        cloud_app -->|"asyncpg driver\nTLS encrypted"| supabase
    end

    envfile[".env\nDATABASE_URL=..."] -->|"dev config"| dev_app
    envcloud["Environment Secrets\n(AWS Secrets Manager / Azure Key Vault)"] -->|"cloud config"| cloud_app
```

### Database security in Supabase (RLS wiring)

```mermaid
graph TD
    browser["Browser\n(uses anon key)"]
    backend["FastAPI Backend\n(uses service-role key)"]
    rls["Supabase RLS Engine\n(database-level policy enforcement)"]
    tables["Data Tables"]

    backend -->|"service-role key\nbypasses RLS\n(trusted path)"| rls
    browser -->|"anon key\nsubject to RLS policies"| rls
    rls -->|"viewer: read-only\nagent: read+write\nadmin: full"| tables

    note["Defence in depth:\nEven if the API has a bug,\nthe DB still enforces access rules"]
```

### `updated_at` trigger wiring

```mermaid
sequenceDiagram
    participant App as FastAPI (Python)
    participant PG as PostgreSQL

    App->>PG: UPDATE tickets SET status='resolved' WHERE id='...'
    PG->>PG: BEFORE UPDATE trigger fires
    PG->>PG: SET updated_at = now()
    PG-->>App: Row updated (with fresh updated_at)
```

The trigger runs at the database level — the application code never needs to manually set `updated_at`. This prevents the common bug where code forgets to update the timestamp.

---

## Stage 3 — After P2-3: Repository Layer Wiring

The repository layer sits between the application logic and the raw database session. It is the "connector" that every part of the app uses to talk to the database.

### Session lifecycle per request

```mermaid
sequenceDiagram
    participant Caller as "API route / Agent / Seed"
    participant Ctx as "get_session() context manager"
    participant Session as "AsyncSession"
    participant DB as "SQLite / PostgreSQL"

    Caller->>Ctx: async with get_session() as session:
    Ctx->>Session: BEGIN transaction
    Caller->>Session: repo.create(Customer(...))
    Session->>DB: INSERT INTO customers ...
    DB-->>Session: row created
    Caller->>Session: repo.get_by_email("x@y.com")
    Session->>DB: SELECT * FROM customers WHERE email=?
    DB-->>Session: row returned
    Caller->>Ctx: (block exits normally)
    Ctx->>Session: COMMIT
    Session->>DB: COMMIT
    Session-->>Ctx: released

    Note over Caller,DB: If an exception is raised anywhere in the block, ROLLBACK is called instead of COMMIT
```

### Repository call chain

```mermaid
graph TD
    subgraph "Callers"
        api["API routes\n(Phase 4)"]
        agent["AI Agents\n(Phase 9)"]
        seed["seed_service.py"]
    end

    subgraph "Repository Layer"
        base["BaseRepository\nget, list, create, update, count"]
        cr["CustomerRepository\nget_by_email\nget_by_external_id\nexists_by_external_id"]
        tr["TicketRepository\nget_by_number\nlist_by_customer\nlist_recent"]
    end

    subgraph "Session Layer"
        sess["AsyncSession\n(one per request)"]
    end

    subgraph "Database"
        sqlite["SQLite (dev)"]
        postgres["PostgreSQL (prod)"]
    end

    api --> cr
    api --> tr
    agent --> cr
    agent --> tr
    seed --> cr
    seed --> tr

    cr --> base --> sess
    tr --> base --> sess
    sess -->|"DATABASE_URL determines which"| sqlite
    sess --> postgres
```

---

## Stage 4 — After P2-4: Startup Sequence and Data Flow

The final stage adds the demo data bootstrap to the startup sequence.

### Full startup sequence

```mermaid
sequenceDiagram
    participant UV as "uvicorn"
    participant Main as "main.py lifespan"
    participant Log as "setup_logging()"
    participant DB as "create_tables()"
    participant Seed as "bootstrap_demo_data()"
    participant Files as "sample_data/*.json"
    participant SQLite as "data/support.db"

    UV->>Main: startup
    Main->>Log: configure JSON logging
    Main->>DB: create_tables()
    DB->>SQLite: CREATE TABLE IF NOT EXISTS (×16)
    SQLite-->>DB: tables ready
    Main->>Seed: bootstrap_demo_data() (only if DEMO_MODE=true)
    Seed->>Files: read customers.json, tickets.json, ...
    Files-->>Seed: 8 customers, 13 tickets, ...
    Seed->>SQLite: INSERT (skip if already exists)
    SQLite-->>Seed: rows written
    Seed-->>Main: done (8 customers, 13 tickets loaded)
    Main->>UV: yield (server ready to accept requests)
```

### Complete Phase 2 infrastructure diagram

```mermaid
graph TD
    subgraph "Git Repository"
        envex[".env.example\n(template, committed)"]
        source["backend/ source\nmodels, schemas, repos, services"]
        sampledata["sample_data/\n*.json + knowledge_base/*.md"]
        sqlschema["database/schema.sql\n(Postgres DDL)"]
        makefile["Makefile\nsetup | backend | seed | test | lint"]
    end

    subgraph "Local Machine (after make setup)"
        env[".env\n(git-ignored, real values)"]
        venv[".venv\n(Python packages incl. sqlalchemy, aiosqlite)"]

        subgraph "Runtime Process (:8000)"
            cors["CORSMiddleware"]
            rid["RequestIdMiddleware"]
            fastapi["FastAPI"]
            config["Settings (singleton)"]
            engine["AsyncEngine"]
            session["AsyncSession\n(per request)"]
            repos["Repositories\nCustomerRepo | TicketRepo | ..."]
        end

        subgraph "Data"
            sqlite["data/support.db\n(SQLite, git-ignored)"]
        end

        subgraph "Test Process (no sockets)"
            conftest["conftest.py\nFake env + fixtures"]
            testclient["TestClient (in-process)"]
            tempdb["Temp SQLite\n(deleted after tests)"]
        end
    end

    envex -.->|"make setup copies"| env
    env --> config
    config --> engine
    engine --> sqlite
    engine --> session
    session --> repos

    cors --> rid --> fastapi
    fastapi --> repos

    sampledata -->|"seed_service reads\nat startup"| sqlite

    conftest --> testclient
    conftest --> tempdb
    testclient --> fastapi
```

---

## Infrastructure that does NOT exist yet in Phase 2

| Component | Added in |
|---|---|
| JWT authentication | Phase 3 |
| Redis rate limiting | Phase 3 |
| HTTP API routes | Phase 4 |
| Vector store (Qdrant / in-memory) | Phase 5 |
| Docker containers | Phase 14 |
| Docker Compose networking | Phase 14 |
| Cloud deployment (AWS/Azure/GCP) | Phase 14 |

---

## Two-database portability

A critical property established in Phase 2 is that the same Python code runs on two different databases depending on a single environment variable:

```mermaid
graph LR
    env["DATABASE_URL env var"]

    env -->|"sqlite+aiosqlite:///./data/support.db"| sqlite["SQLite\n(local dev, tests)"]
    env -->|"postgresql+asyncpg://..."| postgres["PostgreSQL\n(Supabase, production)"]

    sqlite --> samecode["Same Python code\nSame SQLAlchemy models\nSame repositories"]
    postgres --> samecode
```

The only differences between environments are:
1. The `DATABASE_URL` value
2. For Postgres: `JSON` column type becomes `JSONB`, UUID handling is native
3. For Postgres: RLS policies are enforced; for SQLite: they are not (but the app-level RBAC will cover this in Phase 3)

---

## Security posture after Phase 2

```mermaid
graph TD
    subgraph "Security Decisions in Phase 2"
        s1["data/ is git-ignored\n(no SQLite files committed)"]
        s2["sample_data/ contains\nFICTIONAL data only\n(no real credentials)"]
        s3["Secrets never in models\nor JSON files"]
        s4["RLS on all tables\n(Postgres/Supabase)"]
        s5["CHECK constraints\nenforce enums at DB level"]
        s6["Migrations are additive only\n(no DROP TABLE, no data loss)"]
    end
```

---

## Summary

Phase 2 adds the data storage layer to the infrastructure:

1. **Storage engine:** `AsyncEngine` connects to SQLite (dev) or Postgres (prod) via a single env var.
2. **Schema management:** `create_tables()` runs at startup; Postgres has authoritative DDL in `schema.sql`.
3. **Session management:** `get_session()` context manager guarantees commits and rollbacks.
4. **Repository layer:** All database access goes through typed repositories — no raw SQL in business logic.
5. **Demo bootstrap:** `bootstrap_demo_data()` runs at startup in demo mode and is idempotent.
6. **Cloud-ready:** RLS policies and the Postgres DDL are production-grade from day one.
