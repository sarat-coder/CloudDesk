# Phase 10 — Infra & Component Wiring: Workflow Graph and Approval

**Audience:** Interview board including non-technical members.

---

## Overview

Phase 10 wires together the AI workflow engine (LangGraph), the web API (FastAPI), the database (SQLite/PostgreSQL), and the in-process checkpoint store. The result is a system where:
- A single HTTP request starts a long-running AI pipeline
- The pipeline runs in the background while the browser polls for progress
- The pipeline can pause mid-way and wait for a human to click "Approve"
- Every step is recorded so it can be inspected later

---

## Component Architecture at End of Phase 10

```mermaid
graph TB
    Browser["🌐 Browser\n(React frontend)"]
    API["🚀 FastAPI :8000\n(API Layer)"]
    BG["⚙️ BackgroundTasks\n(In-process)"]
    Graph["🤖 LangGraph\n(Workflow Engine)"]
    DB["🗄️ SQLite / PostgreSQL\n(workflow_runs, events\napproval_requests)"]
    CP["💾 Checkpointer\n(InMemorySaver / AsyncSqliteSaver)"]
    Redis["⚡ Redis / FakeRedis\n(Rate limiting, cache)"]
    VectorStore["🔍 Vector Store\n(KB articles)"]
    LLM["🧠 LLM Provider\n(fake / OpenAI / Anthropic)"]

    Browser -->|"POST /tickets/{id}/run\nGET /tickets/{id}/workflow (poll every 2s)\nPOST /approvals/{id}/approve"| API
    API -->|"202 + workflow_id\ncreates workflow_runs row"| Browser
    API -->|"add_task(start_workflow)"| BG
    BG -->|"graph.astream(state)"| Graph
    Graph -->|"write events, runs state\napproval_requests"| DB
    Graph -->|"checkpoint state\nafter every node"| CP
    API -->|"read workflow_runs\nworkflow_events"| DB
    Graph -->|"search articles\ncheck service status"| VectorStore
    Graph -->|"call_structured\nclassify, diagnose, plan"| LLM
    API -->|"rate limit\nsession cache"| Redis

    style Browser fill:#4A90D9,color:#fff
    style API fill:#2E8B57,color:#fff
    style BG fill:#8B6914,color:#fff
    style Graph fill:#9B4DCA,color:#fff
    style DB fill:#C0392B,color:#fff
    style CP fill:#16A085,color:#fff
```

---

## How FastAPI BackgroundTasks Work

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as FastAPI
    participant DB as Database
    participant BG as BackgroundTasks
    participant G as LangGraph

    UI->>API: POST /tickets/{id}/run
    API->>DB: INSERT workflow_runs (status=running)
    API-->>UI: 202 {workflow_id}
    Note over API: Returns immediately — no waiting
    API->>BG: add_task(start_workflow, workflow_id)
    BG->>G: graph.astream(initial_state)
    loop Every node completion
        G->>DB: UPDATE workflow_runs.state
        G->>DB: INSERT workflow_events
    end
    UI->>API: GET /workflow (poll every 2s)
    API->>DB: SELECT workflow_runs WHERE ticket_id=...
    API-->>UI: {status, completed_nodes, ...}
```

**Why BackgroundTasks, not Celery?**
- v1 is designed to run offline with zero infrastructure dependencies
- BackgroundTasks runs in the same process as the API — no message queue, no worker, no broker needed
- For production scale, the same `start_workflow` function can be called from a Celery/RQ worker with one line change

---

## LangGraph Checkpoint Infrastructure

```mermaid
graph LR
    Test["🧪 Tests\n(CHECKPOINT_DB_PATH=:memory:)"]
    Dev["💻 Development\n(./data/checkpoints.db)"]
    Prod["☁️ Production\n(PostgreSQL or S3)"]

    Test -->|"InMemorySaver\n(no disk I/O)"| MemCP["Memory\nCheckpointer"]
    Dev -->|"AsyncSqliteSaver\n(local file)"| SQLiteCP["SQLite\nCheckpointer"]
    Prod -->|"PostgresSaver or\ncustom store"| PGsCP["Postgres\nCheckpointer"]

    MemCP --> State["Serialized\nSupportState"]
    SQLiteCP --> State
    PGsCP --> State
```

**What gets checkpointed?**
Every time a node completes, LangGraph automatically serializes the entire `SupportState` (all 20+ fields) and writes it to the checkpointer. This means:
- If the server restarts, the graph can resume from exactly where it left off
- The human_approval interrupt stores the state before pausing
- On resume, the graph reloads state and continues from the interrupt point

**The interrupt/resume mechanism:**

```mermaid
sequenceDiagram
    participant G as LangGraph Graph
    participant CP as Checkpointer (SQLite)
    participant DB as Database
    participant API as FastAPI

    G->>G: resolve all actions need approval
    G->>DB: INSERT approval_requests (status=pending)
    G->>DB: UPDATE ticket.status = waiting_on_approval
    G->>CP: CHECKPOINT full state at human_approval node
    Note over G: interrupt() suspends execution
    G-->>API: graph pauses (astream yields nothing more)

    Note over API,DB: Time passes... seconds or hours

    API->>DB: SELECT approval_requests WHERE id=...
    API->>DB: UPDATE approval_requests.status = approved
    API->>G: Command(resume={approved: true, decided_by: "agent-id"})
    G->>CP: LOAD state from checkpoint
    G->>G: Continue from after interrupt()
    G->>DB: INSERT resolution_actions (executed)
    G->>DB: UPDATE ticket.status = in_progress
```

---

## Database Tables Used in Phase 10

```mermaid
erDiagram
    tickets {
        string id PK
        string status "new|in_progress|waiting_on_approval|escalated|resolved"
        string ticket_number
    }
    workflow_runs {
        string id PK
        string ticket_id FK
        string status "running|completed|failed|waiting_on_approval|escalated"
        json state "Full SupportState snapshot"
        datetime started_at
        datetime completed_at
    }
    workflow_events {
        string id PK
        string run_id FK
        string event_type "node_started|node_completed|llm_called|tool_called|approval_requested|workflow_completed"
        string node
        json data "duration_ms, tokens, tool_name, etc."
        datetime created_at
    }
    approval_requests {
        string id PK
        string run_id FK
        string ticket_id FK
        string status "pending|approved|rejected"
        string reason
        string decided_by
        datetime decided_at
    }
    resolution_actions {
        string id PK
        string run_id FK
        string ticket_id FK
        string action_type "update_ticket|create_refund_request|reset_demo_setting"
        json args
        string status "pending|completed|failed"
        json result
    }

    tickets ||--o{ workflow_runs : "has many"
    workflow_runs ||--o{ workflow_events : "has many"
    workflow_runs ||--o{ approval_requests : "has at most one"
    workflow_runs ||--o{ resolution_actions : "has many"
```

---

## WorkflowTracer — Observability Layer

The `WorkflowTracer` writes `workflow_events` rows. It is designed to **never raise an exception** — a tracing bug must never kill a workflow run.

```mermaid
graph TD
    Node["Graph Node Execution"]
    Tracer["WorkflowTracer._emit()"]
    DB["workflow_events table"]
    Log["Python logger (debug only)"]

    Node -->|"node_started / node_completed\nllm_called / tool_called\napproval_requested"| Tracer
    Tracer -->|"try: INSERT row"| DB
    Tracer -->|"except: log debug\n(never raises)"| Log

    style Tracer fill:#9B4DCA,color:#fff
    style DB fill:#C0392B,color:#fff
```

**Events never stored (privacy rules §16):**
- Raw prompts sent to the LLM
- Chain-of-thought / hidden reasoning
- Other customers' data
- Secrets (API keys, passwords)

**Events always stored:**
- Node timing (duration_ms)
- LLM token counts and estimated cost
- Tool names and success/failure
- Approval request IDs and decisions

---

## Test Infrastructure

```mermaid
graph LR
    Test["pytest tests/workflow/"]
    FakeLLM["Fake LLM\n(LLM_PROVIDER=fake\nno API key needed)"]
    MemDB["In-Memory SQLite\n(temporary file per session)"]
    MemCP["InMemorySaver\n(CHECKPOINT_DB_PATH=:memory:)"]
    FakeRedis["FakeRedis\n(USE_FAKE_REDIS=true)"]
    MemVS["In-Memory VectorStore\n(VECTOR_STORE=memory)"]

    Test --> FakeLLM
    Test --> MemDB
    Test --> MemCP
    Test --> FakeRedis
    Test --> MemVS

    style Test fill:#2E8B57,color:#fff
```

All tests run offline in ~14 seconds with zero infrastructure dependencies. The same test suite validates the entire 319-test project.

---

## Network/Routing Summary

| Request | Route | Handler | Background? |
|---|---|---|---|
| Start workflow | `POST /api/v1/tickets/{id}/run` | `run_workflow()` | Yes — BackgroundTasks |
| Poll progress | `GET /api/v1/tickets/{id}/workflow` | `get_workflow()` | No — sync DB read |
| Get events | `GET /api/v1/tickets/{id}/events` | `get_events()` | No — sync DB read |
| Approve action | `POST /api/v1/approvals/{id}/approve` | `approve()` | No — inline resume |
| Reject action | `POST /api/v1/approvals/{id}/reject` | `reject()` | No — inline resume |

---

## Key Infrastructure Decisions

| Decision | Choice | Reason |
|---|---|---|
| Background execution | In-process BackgroundTasks | Zero dependencies for v1; easy to migrate to Celery/RQ |
| State persistence | SQLite (dev) / PostgreSQL (prod) | Same SQLAlchemy models work for both |
| Checkpoint store | In-memory (tests) / SQLite file (dev) | Tests need no disk; dev needs persistence across restarts |
| Event storage | Relational DB rows | Queryable, auditable, never in LLM prompts |
| Approval mechanism | LangGraph interrupt() + Command(resume=...) | Built-in, composable, state-safe |
