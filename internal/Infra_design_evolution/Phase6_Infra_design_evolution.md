# Phase 6 — Infrastructure and Component Wiring

## Overview

Phase 6 introduces the **Tool Layer** inside the FastAPI backend process and a new top-level `integrations/` package that sits outside the backend but is imported by tool functions.  
No new network services or containers are added — this phase wires components **within** the existing backend process.

---

## Component map at the end of Phase 6

```mermaid
graph TD
    Browser["Browser :3000\n(Next.js frontend — Phase 12)"]
    FastAPI["FastAPI process :8000\nuvicorn"]

    subgraph FastAPI_internals["Inside FastAPI process"]
        Routers["Routers\napi/auth · api/tickets\napi/customers · api/knowledge\napi/dashboard · api/escalations"]
        Middleware["Middleware stack\nCORS → RequestId → RateLimit → Audit"]
        Services["Services\nticket_service · customer_service\nseed_service"]
        Tools["Tool Layer (Phase 6)\nToolRegistry · ToolPolicy\nsupport_tools · write_tools"]
        Integrations["Integrations (Phase 6)\nfactory → mock adapters\nEmail · Refund · Notify · Storage"]
        RAG["RAG Pipeline (Phase 5)\nretriever · vector_store\nBM25 + embeddings"]
    end

    DB[("SQLite / Postgres\n:5432 in production")]
    Redis[("Redis / fakeredis\n:6379 in production")]
    VectorStore[("In-memory\n/ Qdrant :6333")]
    KB["Knowledge Base\nsample_data/knowledge_base/"]

    Browser -->|HTTPS REST Bearer JWT| FastAPI
    FastAPI --> Middleware
    Middleware --> Routers
    Routers --> Services
    Routers -.->|future wiring Phase 9| Tools
    Services --> DB
    Services --> Redis
    Tools --> DB
    Tools --> RAG
    Tools --> Integrations
    RAG --> VectorStore
    RAG --> KB
    Integrations -.->|DEMO_MODE=true: logs only| MockLog["Application log"]
```

---

## P6-1: Tool Registry and Policy wiring

The `ToolRegistry` is a module-level singleton created on first import.  
On creation it auto-registers all tools by calling `register_support_tools` and `register_write_tools`.

```mermaid
sequenceDiagram
    participant Caller as Agent / Test
    participant Reg as ToolRegistry (singleton)
    participant Policy as ToolPolicy
    participant Fn as Tool Function

    Caller->>Reg: execute("create_refund_request", {amount:50}, approved=False)
    Reg->>Policy: requires_approval("create_refund_request", {amount:50})
    Policy-->>Reg: True
    Reg-->>Caller: ToolResult(ok=False, error="requires human approval")

    Note over Caller,Fn: Second call after human approves

    Caller->>Reg: execute("create_refund_request", {amount:50}, approved=True)
    Reg->>Policy: requires_approval(...)
    Policy-->>Reg: True
    Reg->>Fn: create_refund_request(ticket_id=..., amount=50, ...)
    Fn-->>Reg: ToolResult(ok=True, data={...})
    Reg-->>Caller: ToolResult(ok=True, data={...})
```

---

## P6-2: Read-only tools — DB access path

Each read-only tool opens its own short-lived `AsyncSession` via `get_session()`.  
No session is shared across tool calls.

```mermaid
graph LR
    Tool["Tool Function\ne.g. get_customer(customer_id)"]
    Session["AsyncSession\n(from get_session context manager)"]
    Engine["SQLAlchemy Async Engine\n(sqlite+aiosqlite or postgresql+asyncpg)"]
    DB[("Database")]

    Tool -->|async with get_session()| Session
    Session --> Engine
    Engine -->|SQL SELECT| DB
    DB -->|rows| Engine
    Engine -->|ORM objects| Session
    Session -->|commit / rollback| Engine
    Tool -->|returns ToolResult| Registry["ToolRegistry"]
```

The `search_docs` tool is different — it does not touch the database:

```mermaid
graph LR
    Tool["search_docs(query, category, top_k, mode)"]
    Retriever["RAG Retriever (Phase 5)\nhybrid / semantic / keyword"]
    VStore["Vector Store\nIn-memory / Qdrant"]
    BM25["BM25 Index\nin-memory"]
    Result["Evidence list\nid · title · snippet · score · url"]

    Tool -->|await get_retriever()| Retriever
    Retriever --> VStore
    Retriever --> BM25
    Retriever -->|RRF fusion + rerank| Result
    Result -->|ToolResult(ok=True, data={evidence:[...]})| Tool
```

---

## P6-3: Write tools — approval gate + DB write path

```mermaid
sequenceDiagram
    participant Registry as ToolRegistry
    participant Fn as create_refund_request(...)
    participant Session as AsyncSession
    participant DB as Database

    Registry->>Fn: create_refund_request(ticket_id, customer_id, amount, ...)
    Fn->>Session: async with get_session()
    Fn->>DB: INSERT INTO resolution_actions (action_type='create_refund_request', ...)
    DB-->>Fn: row saved
    Fn->>Session: await session.flush()
    Fn-->>Registry: ToolResult(ok=True, data={action_id, amount, status})
```

`reset_demo_setting` additionally updates the `workspaces.settings` JSON column:

```mermaid
graph LR
    Tool["reset_demo_setting(workspace_id, setting_key, setting_value)"]
    Session["AsyncSession"]
    DB[("workspaces table\nsettings JSON column")]
    Action["resolution_actions table\naudit record"]

    Tool -->|GET workspace| Session
    Session --> DB
    Tool -->|PATCH settings JSON| DB
    Tool -->|INSERT audit record| Action
    Tool -->|ToolResult(ok=True)| Registry["ToolRegistry"]
```

---

## P6-4: Mock Integrations — component wiring

The integration layer sits in the top-level `integrations/` package, **outside** `backend/`.  
Tool functions import from `integrations.factory`, never from `integrations.mock.services` directly.

```mermaid
graph TD
    WriteTool["Write Tool\ne.g. create_refund_request"]
    Factory["integrations/factory.py\nget_refund_service()"]
    Config["app.core.config.get_settings()\nDEMO_MODE"]
    MockRefund["MockRefundService\nlogs to stdout"]
    RealRefund["RealRefundService\n(future — not yet built)"]
    Protocol["RefundService Protocol\nrequest_refund()\nget_refund_status()"]

    WriteTool -->|future integration call| Factory
    Factory -->|read| Config
    Config -->|demo_mode=true| MockRefund
    Config -->|demo_mode=false| RealRefund
    MockRefund & RealRefund -.->|satisfies| Protocol
```

---

## Timeout and error containment

Every tool call is wrapped in `asyncio.wait_for` with `TOOL_TIMEOUT_SECONDS` (default 30 s).

```mermaid
graph LR
    Registry["ToolRegistry.execute()"]
    Timeout["asyncio.wait_for(fn(**args), timeout=30)"]
    Fn["Tool Function"]

    Registry --> Timeout
    Timeout -->|completes in time| Fn
    Timeout -->|TimeoutError| ErrTimeout["ToolResult(ok=False, 'timed out')"]
    Fn -->|raises Exception| ErrException["ToolResult(ok=False, str(exc))"]
    Fn -->|returns| OkResult["ToolResult(ok=True, data={...})"]
```

**The workflow graph above the registry never sees an exception.** It only ever sees `ToolResult`.

---

## Directory layout after Phase 6

```text
CloudDesk/
├── backend/
│   └── app/
│       └── tools/
│           ├── __init__.py        ← re-exports ToolPolicy, ToolResult, ToolRegistry
│           ├── policy.py          ← ToolPolicy rulebook + ToolResult dataclass
│           ├── registry.py        ← ToolRegistry enforcer + singleton get_registry()
│           ├── support_tools.py   ← 5 read-only tool functions
│           └── write_tools.py     ← 4 write tool functions
│
├── integrations/
│   ├── __init__.py
│   ├── protocols.py               ← EmailService, RefundService, NotificationService, StorageService
│   ├── factory.py                 ← get_email_service() etc. — selects mock vs. real
│   └── mock/
│       ├── __init__.py
│       └── services.py            ← Mock*Service classes (offline-safe)
│
└── tests/
    └── unit/
        └── test_tool_policy.py    ← 27 unit tests (all passing offline)
```

---

## Runtime environment variables relevant to Phase 6

| Variable | Default | Effect |
|---|---|---|
| `TOOL_TIMEOUT_SECONDS` | `30` | Maximum seconds a single tool call may run |
| `APPROVAL_REQUIRED_FOR_REFUNDS` | `true` | Whether `create_refund_request` always needs approval |
| `MAX_REFUND_WITHOUT_APPROVAL` | `0` | Dollar threshold below which refunds auto-approve |
| `DEMO_MODE` | `true` | Selects mock integration adapters |

---

## What is NOT wired yet

| Component | Phase |
|---|---|
| Agents calling ToolRegistry | Phase 9 (specialist agents) |
| Approval interrupt in the graph | Phase 10 |
| Approval UI for agents | Phase 12 |
| Real email / billing adapters | Phase 13 / production |
