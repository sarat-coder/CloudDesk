# Phase 1 — System Design Evolution

> This document traces how the system design grew during Phase 1, from an empty project to a working runtime skeleton. Each stage shows what was added and why, with a Mermaid diagram of the system at that point.

---

## Stage 0 — Empty Project (starting point)

Before Phase 1, there was nothing but a Git repository and the CLAUDE.md spec. The design existed only on paper.

```mermaid
graph LR
    spec[CLAUDE.md Spec]
    dev[Developer]
    dev -->|reads| spec
```

**What existed:** Repository skeleton, `pyproject.toml`, `TASKS.md`, `.gitignore`

---

## Stage 1 — After P1-1: Settings and JSON Logging

The first real code defines how the application configures itself and records what it is doing.

### What was added
- `backend/app/core/config.py` — `Settings` class using `pydantic-settings`
- `backend/app/core/logging.py` — `JsonFormatter`, `log_context`, `setup_logging`

### Design at this stage

```mermaid
graph TD
    subgraph "Backend (Python)"
        config["config.py\nSettings\n(reads .env)"]
        logging["logging.py\nJsonFormatter\nlog_context"]
    end

    env[".env file\n(local secrets)"]
    envex[".env.example\n(template, in Git)"]
    stdout["stdout\n(JSON log lines)"]

    env -->|"loaded at startup\n(lru_cache)"| config
    envex -.->|"template for"| env
    logging -->|"writes structured logs"| stdout
```

### Key design decisions at this stage

| Decision | Why |
|---|---|
| `pydantic-settings` with `SecretStr` | Secrets are never accidentally printed; validation happens at startup not at first use |
| `lru_cache` on `get_settings()` | Settings are read once; subsequent calls get the same object (fast, deterministic) |
| `ContextVar` for request/workflow IDs | Thread-safe context propagation without passing IDs through every function call |
| JSON logs | Machine-parseable; monitoring tools (CloudWatch, Datadog) can query them |

---

## Stage 2 — After P1-2: Health Routes and Request-ID Middleware

The application now starts and can receive HTTP requests. Health endpoints let infrastructure know the server is alive and ready.

### What was added
- `backend/app/main.py` — `create_app()`, three health endpoints, CORS and middleware setup
- `backend/app/middleware/request_id.py` — `RequestIdMiddleware`

### Design at this stage

```mermaid
graph TD
    browser["Browser / Load Balancer"]
    cors["CORSMiddleware\n(outermost)"]
    rid["RequestIdMiddleware\n(reads/generates X-Request-ID)"]
    fastapi["FastAPI Application"]

    subgraph "Health Endpoints"
        h1["GET /health\nservice metadata"]
        h2["GET /health/live\nalways 200"]
        h3["GET /health/ready\nchecks config"]
    end

    subgraph "Core"
        config["config.py\nSettings"]
        logging["logging.py\nlog_context"]
    end

    browser -->|"HTTP request"| cors
    cors --> rid
    rid -->|"injects request_id\ninto log context"| logging
    rid --> fastapi
    fastapi --> h1
    fastapi --> h2
    fastapi --> h3
    h3 -->|"reads"| config

    rid -->|"echoes X-Request-ID\nin response header"| browser
```

### Middleware order (outermost first)

```mermaid
graph LR
    req["Incoming Request"] --> cors["CORS\n(allow cross-origin)"]
    cors --> rid["Request-ID\n(trace every log)"]
    rid --> app["FastAPI Routes"]
    app --> rid
    rid --> cors
    cors --> res["Response + X-Request-ID header"]
```

> Note: Audit and Rate-Limit middleware are defined in CLAUDE.md but are added in Phase 3. The order shown above will grow: `CORS → RequestId → RateLimit → Audit`.

### Key design decisions at this stage

| Decision | Why |
|---|---|
| Three separate health endpoints | Liveness (is the process alive?) and readiness (is it safe to route traffic?) serve different purposes in Kubernetes |
| Readiness checks config only, no I/O | A healthy-check that calls the DB can itself fail or hang. Config-based checks are instant and reliable |
| `RequestIdMiddleware` at ASGI level | Works for all responses including 404 and 500, not just routes that return cleanly |
| `expose_headers: ["X-Request-ID"]` in CORS | Browsers block custom headers by default; this allows the frontend to read the ID |

---

## Stage 3 — After P1-3: Offline Pytest Harness

A test infrastructure layer is added. No production code changes — only test scaffolding.

### What was added
- `tests/conftest.py` — environment variable overrides, role fixtures
- `tests/unit/test_config.py`, `test_logging.py`, `test_offline_harness.py`, `test_env_example.py`
- `tests/api/test_health.py`

### Design at this stage

```mermaid
graph TD
    subgraph "Test Layer"
        conftest["conftest.py\nSets fake env vars\nbefore any import"]
        unit["unit/\ntest_config.py\ntest_logging.py"]
        api["api/\ntest_health.py"]
    end

    subgraph "Fakes / Stubs"
        fakedb["sqlite in temp dir\n(destroyed after tests)"]
        fakeredis["USE_FAKE_REDIS=true\n(in-memory)"]
        fakellm["LLM_PROVIDER=fake\n(no API calls)"]
    end

    subgraph "Backend"
        config["config.py"]
        logging["logging.py"]
        main["main.py"]
        rid["request_id.py"]
    end

    conftest -->|"os.environ.update()\nbefore any import"| config
    conftest --> fakedb
    conftest --> fakeredis
    conftest --> fakellm
    unit --> config
    unit --> logging
    api --> main
    api --> rid
```

### Key design decisions at this stage

| Decision | Why |
|---|---|
| `os.environ.update()` runs at module import time | Tests run before the app module loads, so settings see the overrides |
| `scope="session"` fixtures | The temp database directory is created once and cleaned up once per test run, not per test |
| Role fixtures (`agent_headers`, `admin_headers`, `viewer_headers`) | Shared across all future test files; any test can simulate a specific role in one line |
| `test_env_example.py` | Prevents drift: if a developer adds a setting without adding it to `.env.example`, the test fails |

---

## Stage 4 — After P1-4: Makefile and `.env.example` (Final Phase 1 State)

The developer experience layer is added. No new runtime components, but the project is now usable by any developer from a fresh checkout.

### What was added
- `Makefile` — `setup`, `backend`, `test`, `lint` targets
- `.env.example` — all variables with placeholder values

### Complete Phase 1 System Design

```mermaid
graph TD
    subgraph "Developer Workflow"
        make_setup["make setup\n(uv sync + copy .env.example)"]
        make_backend["make backend\n(uvicorn on :8000)"]
        make_test["make test\n(pytest, fully offline)"]
        make_lint["make lint\n(ruff check)"]
        envex[".env.example\n(committed)"]
        env[".env\n(git-ignored)"]
    end

    subgraph "Runtime (port 8000)"
        cors["CORSMiddleware"]
        rid["RequestIdMiddleware"]
        fastapi["FastAPI"]

        subgraph "Health Routes"
            live["GET /health/live"]
            ready["GET /health/ready"]
            health["GET /health"]
        end

        subgraph "Core"
            config["config.py\nSettings (lru_cached)"]
            logging["logging.py\nJsonFormatter\nContextVars"]
        end
    end

    subgraph "Test Suite (offline)"
        conftest["conftest.py\nFake env + fixtures"]
        unit_tests["unit/ tests"]
        api_tests["api/ tests"]
    end

    make_setup --> envex
    envex --> env
    env --> config
    make_backend --> cors
    cors --> rid --> fastapi
    fastapi --> live
    fastapi --> ready
    fastapi --> health
    ready --> config
    logging -.->|"JSON to stdout"| stdout["stdout logs"]
    rid -.->|"log_context(request_id=...)"| logging

    make_test --> conftest
    conftest --> unit_tests
    conftest --> api_tests
```

---

## Summary: What changed and why across Phase 1

| Stage | File(s) | What it enabled |
|---|---|---|
| 0 → 1 | `config.py`, `logging.py` | Safe configuration loading; structured logs with context IDs |
| 1 → 2 | `main.py`, `request_id.py` | HTTP server boots; health endpoints answer; every request is traceable |
| 2 → 3 | `conftest.py`, `tests/` | Entire test suite runs offline in ~6 s |
| 3 → 4 | `Makefile`, `.env.example` | Any developer can start the project in one command |

After Phase 1, the system cannot yet serve real tickets or call an AI. But it has:
- A working server that answers HTTP
- Structured, traceable logs
- Health checks for infrastructure
- A fully offline test suite
- A one-command developer setup

Every later phase builds directly on top of this.
