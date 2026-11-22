# Phase 1 — Infrastructure Design Evolution

> This document explains how the infrastructure, networking, and component wiring of CloudDesk evolves through Phase 1. Each section covers what exists at a given point, how components talk to each other, and why the choices were made.

---

## What "infrastructure" means in Phase 1

In Phase 1, there is **no Docker yet** (Docker and Compose come in Phase 14). The infrastructure is entirely local:

- A Python virtual environment (`.venv`)
- A single FastAPI process on port 8000
- No running database, Redis, or vector store (they are faked in tests)

Despite this simplicity, the *wiring patterns* are established here — the same patterns that the full Docker stack will follow later.

---

## Stage 1 — After P1-1: Config and Logging (No Network Yet)

The first infrastructure decision is **how the app reads its own configuration**.

### Component wiring

```mermaid
graph LR
    subgraph "File System"
        envex[".env.example\n(Git-tracked)"]
        env[".env\n(Git-ignored, local only)"]
    end

    subgraph "Python Process"
        settings["Settings\n(pydantic-settings)"]
        lcache["lru_cache\n(singleton)"]
        logging["JsonFormatter\n+ ContextVars"]
        stdout["stdout / stderr"]
    end

    envex -.->|"template for\n(make setup copies)"| env
    env -->|"read at first call\nof get_settings()"| settings
    settings -->|"cached by"| lcache
    logging -->|"writes JSON lines to"| stdout
```

### Key wiring rules established here

1. **`.env` is the single source of truth for runtime values.** No hardcoded values in Python files (except defaults).
2. **`get_settings()` is a singleton.** Every part of the app calls `get_settings()` and gets the same object. This means you cannot have two parts of the app with different configs.
3. **`ContextVar` for log enrichment.** Python's `ContextVar` lets a log record carry the current `request_id` without passing it as a function argument. This is "ambient context" — set it once, used everywhere in that coroutine.

---

## Stage 2 — After P1-2: HTTP Server and Middleware Stack

The FastAPI process now listens on a port and processes HTTP requests. This introduces the **middleware stack** — a chain of wrappers around every route.

### HTTP request flow

```mermaid
sequenceDiagram
    participant Client as Browser / Load Balancer
    participant CORS as CORSMiddleware
    participant RID as RequestIdMiddleware
    participant App as FastAPI Routes
    participant Config as Settings
    participant Log as JsonFormatter

    Client->>CORS: HTTP Request (may include X-Request-ID)
    CORS->>RID: Forward request
    RID->>RID: Read or generate request_id
    RID->>Log: log_context(request_id=...)
    RID->>App: Forward request
    App->>Config: _readiness_checks(settings)
    Config-->>App: checks dict
    App-->>RID: HTTP Response
    RID->>RID: Append X-Request-ID header
    RID-->>CORS: Response with X-Request-ID
    CORS-->>Client: Response + CORS headers
```

### Middleware stack (outermost to innermost)

```mermaid
graph TD
    request["Incoming HTTP Request"] --> layer1

    subgraph "Middleware Stack (outermost wraps innermost)"
        layer1["1. CORSMiddleware\n• Adds Access-Control-* headers\n• Handles preflight OPTIONS\n• Exposes X-Request-ID to browsers"]
        layer2["2. RequestIdMiddleware\n• Reads X-Request-ID header\n• Generates UUID if missing\n• Sets log_context(request_id)\n• Appends header to every response"]
        layer3["3. FastAPI Application\n• Routing\n• Validation (Pydantic)\n• Route handlers"]
    end

    layer1 --> layer2 --> layer3

    layer3 --> response["HTTP Response"]
    response --> layer2
    layer2 --> layer1
    layer1 --> client["Client receives response\nwith X-Request-ID header"]
```

> **Future middleware (added in Phase 3):** The order after Phase 3 will be:
> `CORS → RequestId → RateLimit → Audit`
> This order is intentional: rate limiting happens before audit logging so that rejected requests are not unnecessarily written to the audit log.

### Port and network binding

```mermaid
graph LR
    subgraph "Local Machine"
        uvicorn["uvicorn\n127.0.0.1:8000"]
        fastapi["FastAPI (ASGI app)"]
    end

    browser["Browser\n(localhost:3000 in dev)"]

    browser -->|"HTTP on port 8000"| uvicorn
    uvicorn --> fastapi
```

- Binds to `127.0.0.1` (loopback only) in development — not reachable from other machines.
- In production (Phase 14), this will be a Docker container behind a load balancer.
- CORS is configured to allow `http://localhost:3000` by default (the Next.js dev server).

### Health endpoint routing

```mermaid
graph TD
    request["GET /health/*"] --> rid["RequestIdMiddleware"]
    rid --> router["FastAPI router"]

    router --> live["GET /health/live\n→ {'status': 'alive'}\nNo I/O, always 200"]
    router --> ready["GET /health/ready\n→ checks dict\n200 if ready, 503 if degraded"]
    router --> health["GET /health\n→ service metadata\nalways 200"]

    ready --> config_check["_readiness_checks(settings)\nReads config only\nNo network calls"]
```

---

## Stage 3 — After P1-3: Test Infrastructure Wiring

The test harness introduces a **parallel, isolated infrastructure** that runs entirely in memory. No ports, no sockets.

### Test infrastructure wiring

```mermaid
graph TD
    subgraph "Test Process"
        conftest["conftest.py\nos.environ.update()\nRuns BEFORE any import"]

        subgraph "Fake Infrastructure"
            fakedb["SQLite\n(temp file, deleted after tests)"]
            fakeredis["fakeredis\n(in-memory, no Redis process)"]
            fakellm["LLM_PROVIDER=fake\n(returns canned responses)"]
            fakevec["VECTOR_STORE=memory\n(in-memory, no Qdrant)"]
        end

        subgraph "Test Client"
            testclient["FastAPI TestClient\n(httpx, no sockets)"]
        end

        subgraph "Tests"
            unit["unit/ tests\ntest_config.py\ntest_logging.py"]
            api["api/ tests\ntest_health.py"]
        end
    end

    conftest --> fakedb
    conftest --> fakeredis
    conftest --> fakellm
    conftest --> fakevec
    conftest --> testclient

    unit --> conftest
    api --> testclient
```

### Key isolation properties

| Property | How it works |
|---|---|
| No real database | `DATABASE_URL=sqlite+aiosqlite:///./tmp/.../support.db` — temp file, cleaned up |
| No real Redis | `USE_FAKE_REDIS=true` — `fakeredis` library replaces Redis in memory |
| No real LLM | `LLM_PROVIDER=fake` — deterministic canned responses, no API key needed |
| No real vector store | `VECTOR_STORE=memory` — Python dict, no Qdrant process |
| No real HTTP sockets | `TestClient` from `httpx` calls the ASGI app in-process, no TCP |

### Why this matters architecturally

The test suite proves an important design guarantee: **every external dependency can be replaced with a fake.** This is only possible because all dependencies are accessed through abstraction:
- Config: `get_settings()` — overridable by env vars
- Database: `DATABASE_URL` — SQLite for tests, Postgres for production
- Redis: `USE_FAKE_REDIS` flag — same code, different backend
- LLM: `LLM_PROVIDER` — same interface, different implementation

This pattern (sometimes called "ports and adapters") means the core business logic never depends directly on a specific infrastructure choice.

---

## Stage 4 — After P1-4: Full Phase 1 Infrastructure Picture

After adding `Makefile` and `.env.example`, the complete local infrastructure looks like this:

### Developer workflow

```mermaid
graph TD
    subgraph "One-time setup"
        checkout["git clone / checkout"]
        make_setup["make setup\n1. uv sync (install deps into .venv)\n2. Copy .env.example → .env"]
    end

    subgraph "Day-to-day"
        make_backend["make backend\nuvicorn app.main:app\n127.0.0.1:8000"]
        make_test["make test\npytest -q (offline, ~6s)"]
        make_lint["make lint\nruff check backend tests"]
    end

    checkout --> make_setup
    make_setup --> make_backend
    make_setup --> make_test
    make_setup --> make_lint
```

### Full Phase 1 infrastructure diagram

```mermaid
graph TD
    subgraph "Git Repository"
        envex[".env.example\n(all vars, placeholders)"]
        source["Python source\nbackend/ + tests/"]
        pyproject["pyproject.toml\n(deps + pytest config)"]
        makefile["Makefile\n(developer commands)"]
        gitignore[".gitignore\n(env, data, venv)"]
    end

    subgraph "Local Machine (after make setup)"
        venv[".venv\n(Python packages)"]
        env[".env\n(real values, not in Git)"]

        subgraph "Runtime Process (:8000)"
            cors["CORSMiddleware"]
            rid["RequestIdMiddleware"]
            fastapi["FastAPI"]
            config["Settings\n(singleton)"]
            jsonlog["JsonFormatter\n→ stdout"]
        end

        subgraph "Test Process (no sockets)"
            conftest["conftest.py"]
            testclient["TestClient (in-process)"]
            fakes["Fakes:\nSQLite + fakeredis\n+ fake LLM + memory store"]
        end
    end

    envex -.->|"make setup copies"| env
    source --> venv
    pyproject --> venv
    env --> config

    cors --> rid --> fastapi
    fastapi --> config
    fastapi --> jsonlog

    conftest --> testclient
    conftest --> fakes
    testclient --> fastapi
```

---

## Infrastructure that does NOT exist yet in Phase 1

| Component | Added in |
|---|---|
| PostgreSQL / SQLite (real) | Phase 2 |
| Redis (real, for rate limiting) | Phase 3 |
| JWT authentication | Phase 3 |
| Qdrant (vector store) | Phase 5 |
| Docker containers | Phase 14 |
| Docker Compose networking | Phase 14 |
| Kubernetes / cloud deploy | Phase 14 |

---

## Security posture after Phase 1

Even at this early stage, several security decisions are locked in:

```mermaid
graph TD
    subgraph "Security Decisions in Phase 1"
        s1["Secrets in .env only\n(.gitignore prevents commit)"]
        s2["SecretStr in Settings\n(secrets never printed)"]
        s3["X-Request-ID validated\n(regex, max 128 chars)\nprevents header injection"]
        s4[".env.example has placeholders\nnever real values"]
        s5["CORS whitelist\nnot wildcard *"]
    end
```

---

## Summary

Phase 1 establishes the **infrastructure skeleton** that every later phase builds on:

1. **Configuration layer:** `.env` → `Settings` singleton → every component that needs config
2. **Middleware stack:** `CORS → RequestId → FastAPI` (will grow in Phase 3)
3. **Request tracing:** `X-Request-ID` flows from client → middleware → logs → response
4. **Test isolation:** Every real infrastructure component has a fake equivalent; tests run in-process
5. **Developer ergonomics:** One-command setup and run via `Makefile`

The infrastructure does no real work yet — no tickets, no AI, no database writes — but every pattern that the full system will use is already in place.
