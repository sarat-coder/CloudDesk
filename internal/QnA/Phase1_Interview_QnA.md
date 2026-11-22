# Phase 1 — Interview Q&A

> All possible interview questions from Phase 1 (Runtime Skeleton) with thorough answers. Questions range from conceptual/non-technical to deep technical.

---

## Section 1 — Project & Product Understanding

**Q1: What is CloudDesk and what problem does it solve?**

CloudDesk is an AI-powered customer support platform for a fictional SaaS company. When a customer submits a support ticket (billing issue, login failure, storage problem, etc.), the platform automatically investigates the issue, retrieves relevant knowledge articles, drafts a resolution plan, and presents it to a support agent for approval. The goal is to reduce the time an agent spends researching and drafting replies — not to replace the human, but to make them dramatically faster and more consistent.

---

**Q2: Why do you need a "runtime skeleton" before building features?**

A runtime skeleton is the foundation that every feature will be built on. Without it, each developer makes different decisions about how to read configuration, how to log, and how to run tests — leading to an inconsistent codebase. By establishing these patterns first, every later feature:
- Reads configuration the same way
- Logs structured JSON in the same format
- Runs tests with the same fake infrastructure
- Is started with the same developer commands

The skeleton also unblocks other phases immediately — once you can run and test the server, all other work can proceed in parallel.

---

**Q3: What is the target user of this system? Is it customer-facing?**

The platform is for **support agents**, not customers directly. Customers send tickets (via email, chat, web, or API), but they never interact with the AI platform. An agent sees the ticket, the AI's investigation results, and a proposed reply — and decides whether to send it, modify it, or escalate.

---

## Section 2 — Configuration and Settings

**Q4: How does the application manage its configuration?**

Configuration is managed through a `Settings` class built with `pydantic-settings`. On first call to `get_settings()`, the class reads environment variables and a `.env` file, validates them (types, ranges, formats), and returns a Settings object. That object is cached by `@lru_cache`, so subsequent calls return the same instance without re-reading the file. This means configuration is loaded exactly once and is consistent everywhere.

---

**Q5: Why use `pydantic-settings` instead of `os.getenv()`?**

`os.getenv()` returns raw strings with no type checking or validation. `pydantic-settings` gives:
1. **Type coercion:** `"true"` becomes `True` (bool), `"30"` becomes `30.0` (float) automatically.
2. **Validation:** `embedding_dimensions: int = Field(gt=0)` raises an error at startup if the value is 0 or negative — not hours later when it's actually used.
3. **Defaults:** Defaults are co-located with the field definitions, not scattered in `os.getenv("X", "default")` calls throughout the code.
4. **Secret handling:** `SecretStr` fields are never accidentally printed or logged.

---

**Q6: What is `SecretStr` and why is it used?**

`SecretStr` is a Pydantic type that wraps a string value and overrides `__repr__` and `__str__` to return `'**********'` instead of the actual value. This prevents secrets (API keys, JWT secrets, database passwords) from being accidentally written to logs or displayed in error messages. To get the real value, you must explicitly call `.get_secret_value()`, which is a deliberate action that makes code reviewers aware a secret is being exposed.

---

**Q7: What is `@lru_cache` and why is it applied to `get_settings()`?**

`@lru_cache` memoizes the return value of a function. The first call executes the function and stores the result. All subsequent calls return the stored result immediately. Applied to `get_settings()`, this means:
- The `.env` file is read exactly once at startup.
- All parts of the app share the exact same `Settings` instance.
- Configuration is effectively a singleton.

The cache can be cleared with `get_settings.cache_clear()`, which is used in tests to simulate reloading configuration with different environment variables.

---

**Q8: Why is `.env.example` committed to Git but `.env` is not?**

`.env.example` is a documentation file — it lists every environment variable the app needs, with placeholder values (never real secrets). Any developer cloning the repo can see what they need to configure. `.env` contains actual values (database passwords, API keys), which must never be committed because Git history is public (or at least accessible to everyone with repo access). The `.gitignore` file excludes `.env` and all `.env.*` files except `.env.example`.

---

**Q9: What happens if `effective_jwt_secret` has two possible values?**

The `effective_jwt_secret` property checks `supabase_jwt_secret` first, then `jwt_secret`. This allows the same code to work in two modes:
- **Demo mode / local:** Set `JWT_SECRET` only.
- **Production (Supabase):** Set `SUPABASE_JWT_SECRET` to the JWT secret from your Supabase project settings. The Supabase secret overrides `JWT_SECRET` so tokens issued by Supabase can be verified correctly.

---

## Section 3 — Logging

**Q10: Why use structured JSON logging instead of plain text?**

Plain text logs like `2024-01-01 10:00:00 ERROR Something went wrong` are readable by humans but very hard for machines to parse. JSON logs like `{"timestamp":"2024-01-01T10:00:00Z","level":"ERROR","message":"Something went wrong","request_id":"abc-123"}` can be:
- Queried with SQL-like filters in log management tools (AWS CloudWatch Insights, Splunk, Datadog)
- Correlated across multiple services using the `request_id` field
- Monitored with alerts on specific field values

---

**Q11: What is a `ContextVar` and how is it used here?**

A `ContextVar` is a Python 3.7+ primitive for storing values in "async context" — similar to thread-local storage, but safe for async code where multiple coroutines share a thread. In CloudDesk:
- `_request_id` stores the current request's ID.
- `_workflow_id` stores the current workflow's ID.
- When the middleware calls `log_context(request_id="abc-123")`, it sets the ContextVar.
- Every `logging.info()` call in that request's coroutine automatically picks up `request_id="abc-123"` from the ContextVar, without passing it as a function argument.
- When the request ends, the ContextVar is reset to its previous value.

---

**Q12: What is the `log_context` context manager?**

`log_context` is a Python context manager (used with `with`) that:
1. Saves the current value of `_request_id` and/or `_workflow_id`.
2. Sets new values.
3. Yields (lets the wrapped code run).
4. Restores the original values, even if an exception occurred.

This "save → set → restore" pattern is called a **token-based reset** and is the correct way to use `ContextVar` in nested async code.

---

## Section 4 — Health Endpoints

**Q13: Why are there three different health endpoints?**

Each endpoint serves a different purpose in infrastructure management:

| Endpoint | Purpose | Used by |
|---|---|---|
| `/health` | General status with version info | Dashboards, manual checks, API clients |
| `/health/live` | "Is the process alive?" | Kubernetes liveness probe — if this fails, Kubernetes restarts the pod |
| `/health/ready` | "Is the app safe to receive traffic?" | Kubernetes readiness probe — if this fails, Kubernetes stops routing traffic here |

Separating liveness from readiness is a Kubernetes best practice. A pod can be alive (process running) but not ready (database not connected), and you want to route traffic away from it without restarting it.

---

**Q14: Why does `/health/ready` check configuration instead of making real network calls?**

Making real network calls in a health check creates a circular dependency problem: if the database is slow, every health check is slow. If the health check is slow, the load balancer might mark the server unhealthy and restart it, causing more load, causing more slowness. A configuration-based check is:
- **Instant:** No I/O.
- **Reliable:** Cannot fail due to database latency.
- **Accurate enough:** If the database URL is configured correctly, the app can connect. If it is not configured, the app will fail when it tries.

For Phase 1 (no real database yet), this is the right trade-off. In Phase 2, the readiness check can be extended to include a real database ping.

---

**Q15: What does the readiness endpoint return when something is wrong?**

It returns HTTP 503 (Service Unavailable) with a JSON body like:
```json
{
  "status": "degraded",
  "checks": {
    "database": {"status": "error", "detail": "Database URL is missing or uses an unsupported driver"},
    "redis": {"status": "ok"},
    "vector_store": {"status": "ok"},
    "llm": {"status": "ok"}
  }
}
```
This tells the operator exactly which dependency is failing, without requiring them to check logs.

---

## Section 5 — Request-ID Middleware

**Q16: What is the Request-ID and why is it important?**

A Request-ID (also called a trace ID or correlation ID) is a unique identifier assigned to each HTTP request. It is included in every log line produced while handling that request. When a user reports a problem, support can find their request ID (from the browser's developer tools or the API response header) and search logs for all events that happened during that request — across the entire stack. This is essential for debugging in production systems that handle thousands of requests per second.

---

**Q17: How does the `RequestIdMiddleware` work at the ASGI level?**

ASGI (Asynchronous Server Gateway Interface) is the Python interface between a web server (uvicorn) and a web framework (FastAPI). An ASGI middleware is a class that wraps the entire application and intercepts every request and response:

1. The middleware reads the incoming request's headers.
2. It extracts or generates a request ID.
3. It modifies the `send` function (which sends the HTTP response) to add the `X-Request-ID` header.
4. It wraps the handler call in `log_context(request_id=...)` so all logs during this request carry the ID.
5. After the handler returns, the modified `send` is called, appending the header.

Working at the ASGI level means the middleware applies to **every** response — including 404s, 500s, and OPTIONS preflight requests — not just routes that return successfully.

---

**Q18: Why is the Request-ID validated with a regex?**

Without validation, a client could send:
```
X-Request-ID: evil\r\nSet-Cookie: session=stolen
```
This is an HTTP header injection attack. By validating with `[A-Za-z0-9._:-]{1,128}`, the middleware:
1. Only accepts safe characters.
2. Limits length to 128 characters.
3. Rejects any value with control characters (like `\r\n`).

If validation fails, a fresh UUID is generated instead of echoing the malicious value.

---

**Q19: Why is `X-Request-ID` listed in CORS `expose_headers`?**

By default, browsers running JavaScript can only read a standard set of response headers (like `Content-Type`). Custom headers like `X-Request-ID` are hidden by the browser's CORS policy unless the server explicitly allows them in `Access-Control-Expose-Headers`. Without this, the Next.js frontend could not read the request ID and display it to the user or include it in error reports.

---

## Section 6 — Testing and the Offline Harness

**Q20: What is `conftest.py` in pytest?**

`conftest.py` is a special pytest file that is automatically loaded before any test in the same directory (or subdirectories). It is used to:
1. Set up environment variables that must be in place before the app is imported.
2. Define shared fixtures available to all tests.

The key insight is that `os.environ.update()` runs at **module import time** — before `app.core.config` is imported. This means `Settings()` sees the test values, not values from a `.env` file on disk.

---

**Q21: Why do the tests not require a real database or Redis?**

The test harness sets environment variables that point to fake alternatives:
- `DATABASE_URL=sqlite+aiosqlite:///tmp/test.db` → a temporary file database, not PostgreSQL
- `USE_FAKE_REDIS=true` → the `fakeredis` library simulates Redis in memory
- `LLM_PROVIDER=fake` → returns deterministic fake responses
- `VECTOR_STORE=memory` → an in-process dict, not Qdrant

This design follows the "ports and adapters" principle: the core business logic never imports a specific database driver or Redis client directly. It goes through an abstraction layer (Settings → factory function → actual implementation), making substitution easy.

---

**Q22: What is the purpose of `test_env_example.py`?**

This test reads `.env.example` and the `Settings` class's field names, then checks that every field in `Settings` has a corresponding entry in `.env.example`. It prevents the common problem where a developer adds a new setting to the code but forgets to document it in `.env.example`. Without this test, the next person to clone the repo and try to configure the app would have no idea the setting exists.

---

**Q23: What is `scope="session"` in a pytest fixture?**

By default, pytest fixtures are recreated for each test function. `scope="session"` means the fixture is created once for the entire test session and shared across all tests. The temporary database directory fixture uses session scope because:
1. Creating and deleting directories is slow relative to test execution.
2. All tests share the same fake database URL, so they should share the same directory.
3. The directory is cleaned up once at the very end of the test run.

---

**Q24: What are the role fixtures and why are they defined in conftest.py?**

```python
@pytest.fixture
def agent_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-agent-token"}
```

These fixtures provide pre-made HTTP headers that simulate an authenticated user of a given role (agent, admin, viewer). They are defined in `conftest.py` so every test file in the project can use them without importing anything. In later phases, these will be used to prove that:
- A `viewer` gets a 403 when trying to approve a refund.
- An `agent` can run a workflow.
- An `admin` can reindex the knowledge base.

---

## Section 7 — Architecture and Design Principles

**Q25: What is the layering rule and why does it matter?**

The codebase is divided into layers, each with a strict responsibility:

| Layer | Can call | Cannot call |
|---|---|---|
| API | Services | Business rules directly |
| Services | Repositories, Workflow | HTTP |
| Repositories | Database | LLMs |
| Core | (nothing else in the app) | Agents |
| Agents | Tools, Repositories | SQL directly |

Keeping layers clean means you can change the database (SQLite → PostgreSQL) without touching any agent code, and you can change the AI provider without touching any HTTP routes. If a layer violates the rules, it creates tight coupling that makes the system fragile and hard to test.

---

**Q26: What does "offline first" mean and why is it a design principle?**

"Offline first" means that every piece of functionality can be tested without any external service (database, AI API, Redis, vector store). This is enforced by the test harness in Phase 1. The benefits are:
- **Fast tests:** No network latency.
- **Reliable tests:** No flaky failures due to external service availability.
- **Cost-free CI:** No API calls = no API costs during testing.
- **Developer independence:** Any developer can run all tests from a fresh checkout, with no credentials.

---

**Q27: What is the `DEMO_MODE` flag?**

`DEMO_MODE=true` activates several behaviors that make the app run without any real infrastructure:
- The SQLite database is used instead of PostgreSQL.
- Sample data is loaded automatically at startup.
- Fake embeddings and a fake LLM provider are acceptable defaults.
- Redis URL is not required (fakeredis is used).

This allows a developer to run `make setup && make backend` and immediately have a fully working system with realistic demo data, without needing any cloud accounts or running any external services.

---

**Q28: Why is there no frontend in Phase 1?**

The frontend (Next.js) depends on a working API, which depends on a working database (Phase 2), which depends on working authentication (Phase 3). Building the frontend before those are in place would mean either:
- Building against a contract that doesn't exist yet, leading to rewrites, or
- Blocking the entire team on backend work before any frontend work can start.

By separating concerns and building in dependency order, frontend work can begin in Phase 12 — in parallel with other backend phases — using the API contract document as the source of truth.

---

## Section 8 — Advanced / Architectural Questions

**Q29: What is ASGI and how is it different from WSGI?**

WSGI (Web Server Gateway Interface) is the original Python web standard. It is **synchronous**: each request blocks a thread until it completes. ASGI (Asynchronous Server Gateway Interface) is the modern successor. It is **asynchronous**: a single thread can handle many concurrent requests, with I/O operations (database queries, HTTP calls to AI APIs) running concurrently using Python's `asyncio`.

For CloudDesk, ASGI is essential because:
- The AI workflow makes multiple LLM calls (seconds each) per ticket.
- With WSGI, each in-flight workflow would block a thread.
- With ASGI, thousands of tickets can be in-flight concurrently on a few threads.

---

**Q30: Why is the `create_app()` factory function used instead of a module-level `app = FastAPI()`?**

The factory pattern (`def create_app(settings=None) -> ASGIApp`) allows:
1. **Testability:** Tests can call `create_app(Settings(_env_file=None, environment="test"))` to create an app with specific settings, without affecting the module-level singleton.
2. **Multiple configurations:** The same codebase can serve multiple app instances with different configs (e.g., different CORS origins for different test cases).
3. **Deferred initialization:** The lifespan handler (database setup, etc.) runs when the app starts, not when the module is imported.

The module-level `app = create_app()` at the bottom of `main.py` creates the production instance that uvicorn imports.

---

**Q31: How does the system handle the case where a developer accidentally commits a `.env` file with real secrets?**

Three layers of protection:
1. **`.gitignore`** excludes `.env` and `*.env.*` (except `.env.example`). `git add .` will not stage it.
2. **`gitleaks`** (added in Phase 14 CI) scans every commit for secret patterns and fails the build.
3. **`test_env_example.py`** ensures `.env.example` only has placeholder values (it fails if it finds a string that looks like a real API key).

If a secret is committed anyway, the response is to rotate the secret immediately (not just delete the commit — git history is permanent unless rewritten).

---

**Q32: What is the difference between `AsyncSqliteSaver` and `InMemorySaver` for the checkpoint database?**

These are checkpointers for LangGraph (the AI workflow engine, added in Phase 10):
- **`InMemorySaver`**: Stores workflow state in a Python dict. Fast, but state is lost when the process restarts. Used when `CHECKPOINT_DB_PATH=:memory:` (tests).
- **`AsyncSqliteSaver`**: Persists workflow state to a SQLite file. Survives restarts. Used in development and staging.

This distinction matters for the approval flow: if an agent approves a refund but the server restarts before the approval is processed, the workflow must be resumable from the checkpoint. In tests, this doesn't matter — each test starts fresh — so the in-memory saver is faster and simpler.
