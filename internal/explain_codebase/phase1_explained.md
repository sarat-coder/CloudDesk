# Phase 1 — Runtime Skeleton: Plain-English Explanation

> **Audience:** Anyone — including non-technical interviewers — who wants to understand what was built in Phase 1 and *why* it matters before anything else was written.

---

## What is CloudDesk?

CloudDesk is an AI-powered **customer support platform** for a fictional SaaS company. When a customer sends a support ticket (e.g. "I was charged too much" or "I can't log in"), the platform automatically investigates, drafts a resolution, and presents it to a support agent for final approval. Think of it as a smart assistant for your support team — not a replacement for human judgment, just a very capable first responder.

---

## Why do we need a "Runtime Skeleton" before anything else?

Imagine you are building a skyscraper. Before you lay bricks, you need:

1. A solid foundation.
2. Scaffolding so workers can safely build floors above.
3. A way to check that the building is still standing (health check).
4. A site logbook so everyone knows what happened and when.

**Phase 1 is exactly that for our software.** It does not yet support tickets, customers, or AI agents. What it *does* do is put every foundational piece in place so that every future feature has a safe, consistent place to live.

---

## What was actually built? (Four tasks)

### Task P1-1 — Settings and JSON Logging

**The problem it solves:** A web application needs to know its own configuration — which database to use, whether it is running in demo mode, which AI provider to call, and dozens of other options. It also needs to record what it is doing in a machine-readable way so errors can be found and fixed fast.

**What we built:**

- **`backend/app/core/config.py`** — A single Python class called `Settings`. Think of it as a smart configuration form. Every setting the app needs (database address, AI provider, rate limits, feature flags) lives here. Settings are read from a `.env` file on startup, so a developer can change them without editing any code.
  - Secrets (passwords, API keys) are stored safely — if you accidentally print the settings object, the secret values show up as `**********` instead of the real value.
  - The settings object is **cached**: the app reads the file once and keeps the result in memory, so it is fast.

- **`backend/app/core/logging.py`** — A logging system that writes every log line as a single JSON object (a structured dictionary) instead of plain text. Each log line automatically includes:
  - The exact timestamp
  - The severity level (INFO, ERROR, etc.)
  - The log message
  - The **Request ID** of the HTTP request that caused it (explained next)
  - The **Workflow ID** if an AI workflow is running

  Why JSON? Because monitoring systems (like AWS CloudWatch or Datadog) can query JSON logs. Plain text logs are hard to search programmatically.

---

### Task P1-2 — Health Routes and Request-ID Middleware

**The problem it solves:** Operations teams and load balancers need a way to ask "is this server alive and ready to receive traffic?" without triggering any real work. They also need to trace a single user's request through thousands of log lines.

**What we built:**

- **Three health check endpoints** in `backend/app/main.py`:

  | Endpoint | What it does | Used by |
  |---|---|---|
  | `GET /health` | Returns the app name and version | Manual checks, dashboards |
  | `GET /health/live` | Returns "alive" — no I/O, never fails | Kubernetes liveness probe (restarts the pod if this fails) |
  | `GET /health/ready` | Checks database, Redis, vector store, and LLM config | Kubernetes readiness probe (stops sending traffic if not ready) |

  The readiness check is clever: it does **not** make real network calls to the database. Instead, it reads the configuration and decides whether the connections *would* work. This means it is instant and cannot hang.

- **`backend/app/middleware/request_id.py`** — A piece of software that sits between the user's browser and every route. For every incoming HTTP request it:
  1. Reads the `X-Request-ID` header if the client sent one.
  2. If none was provided, generates a random UUID (a unique identifier).
  3. Injects that ID into every log line produced during that request.
  4. Echoes the ID back to the client in the response header.

  **Why does this matter?** When a user reports a problem ("my ticket didn't save at 3pm"), a developer can search all logs for that request ID and see the exact sequence of events — even across multiple servers.

---

### Task P1-3 — Offline Pytest Harness

**The problem it solves:** Developers need to run tests quickly without needing a real database, a real Redis server, or a real AI API key. If tests required all of those, they would be slow, expensive, and impossible to run in a CI/CD pipeline with no credentials.

**What we built:**

- **`tests/conftest.py`** — A "setup file" that runs before any test. It sets environment variables to safe fake values:
  - `LLM_PROVIDER=fake` → no real AI calls
  - `VECTOR_STORE=memory` → no Qdrant (vector database)
  - `USE_FAKE_REDIS=true` → an in-memory fake Redis
  - A temporary SQLite database that is deleted after the test run

- **Role fixtures:** Three pre-made HTTP headers (`agent_headers`, `admin_headers`, `viewer_headers`) that simulate logged-in users of each role. Future tests use these to prove that a viewer cannot approve a refund.

- **Test files:**
  - `tests/unit/test_config.py` → proves settings load correctly, secrets are redacted, and the cache works
  - `tests/unit/test_logging.py` → proves JSON logs are well-formed
  - `tests/api/test_health.py` → proves all three health endpoints respond correctly
  - `tests/unit/test_env_example.py` → proves the `.env.example` file lists every variable the app uses
  - `tests/unit/test_offline_harness.py` → proves the test suite itself runs fully offline

---

### Task P1-4 — Makefile and `.env.example`

**The problem it solves:** New developers joining the project need a simple, documented way to get everything running. Without this, every developer figures it out by trial and error.

**What we built:**

- **`.env.example`** — A template for the `.env` file with every configuration variable listed and explained, but with **placeholder values only** (never real secrets). This file is committed to Git so everyone can see what variables exist. The real `.env` file (with actual secrets) is in `.gitignore` and never committed.

- **`Makefile`** — Four one-word commands:
  - `make setup` → installs Python dependencies and creates a `.env` from the example
  - `make backend` → starts the FastAPI server on port 8000
  - `make test` → runs all tests offline (takes ~6 seconds)
  - `make lint` → checks code style with Ruff

---

## How these pieces connect

```
Developer types "make backend"
        │
        ▼
  Python reads .env file
        │
        ▼
  Settings object is built (config.py)
        │
        ▼
  FastAPI app starts (main.py)
        │
        ├── JSON logging configured (logging.py)
        │
        ├── CORS middleware added (allows browser requests)
        │
        └── Request-ID middleware added (request_id.py)
                │
                ▼
         Every HTTP request gets a unique ID
         Every log line includes that ID
         Health endpoints answer immediately
```

---

## The "offline first" principle

One of the strongest design decisions made in Phase 1: **the entire test suite runs with zero external dependencies.** No database, no Redis, no AI provider, no internet. This means:

- Tests are fast (seconds, not minutes).
- Tests work on any developer's laptop and in any CI pipeline.
- A broken external service cannot stop developers from working.

Every future phase must maintain this property. If a new feature requires a network call, a fake/mock version of that call must be provided for tests.

---

## What Phase 1 does NOT include

Phase 1 is intentionally minimal. It does **not** include:

- A database schema or any data
- User authentication or login
- Any AI agents or ticket processing
- A frontend (UI)
- Any business logic

All of those come in later phases, built on top of this solid foundation.

---

## In one sentence

> Phase 1 gives the application its foundation: a safe configuration system, structured logging, health check endpoints, a request-tracing mechanism, and a fully offline test harness — so every future feature is built on a consistent, well-tested base.
