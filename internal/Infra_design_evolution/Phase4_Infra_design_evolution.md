# Phase 4 — Infrastructure Design Evolution: Support API

> This document explains the component wiring, routing, and data flow introduced in Phase 4 from an infrastructure perspective.

---

## What changed at the infrastructure level in Phase 4

Phase 4 is primarily a **software routing** phase rather than an infrastructure phase — no new services or containers were added. What changed is how HTTP requests flow *through* the existing application to reach new business logic.

The key infrastructure additions:
1. **New URL routes** mounted in the FastAPI application.
2. **A new database session dependency** (`get_db`) wired into those routes.
3. **TypeScript types** placed in the frontend directory (even though the Next.js frontend doesn't exist yet).

---

## Component wiring at the end of Phase 4

```mermaid
graph TD
    subgraph External ["External (Phase 4 scope: local dev + tests)"]
        curl["curl / pytest TestClient / Postman"]
    end

    subgraph App ["FastAPI process (port 8000)"]
        subgraph MW ["Middleware Chain (Phase 3)"]
            CORS["CORSMiddleware<br/>allow_origins=http://localhost:3000<br/>expose_headers=X-Request-ID"]
            RID["RequestIdMiddleware<br/>reads/generates X-Request-ID"]
            RL["RateLimitMiddleware<br/>120 req/min per client (fakeredis in tests)"]
            AUD["AuditMiddleware<br/>writes audit_logs on non-GET"]
        end

        subgraph Routes ["Routes (Phase 4 adds these)"]
            T["/api/v1/tickets/*"]
            C["/api/v1/customers/*"]
            D["/api/v1/dashboard/summary"]
            E["/api/v1/escalations"]
            S["/api/v1/settings"]
        end

        subgraph Deps ["FastAPI Dependencies"]
            GDB["get_db()<br/>async generator<br/>yields AsyncSession<br/>commits/rollbacks on exit"]
            GCU["get_current_user()<br/>decodes JWT Bearer token"]
            RR["require_role('agent')<br/>checks role rank ≥ 2"]
        end

        subgraph Services ["Service Layer"]
            TS["ticket_service.py"]
            CS["customer_service.py"]
        end

        subgraph Repos ["Repository Layer"]
            TR["TicketRepository"]
            TMR["TicketMessageRepository"]
            CR["CustomerRepository"]
            SR["SubscriptionRepository"]
            WR["WorkspaceRepository"]
        end
    end

    subgraph DataStores ["Data Stores"]
        DB[("SQLite<br/>(dev + tests)<br/>or PostgreSQL<br/>(prod)")]
        Redis[("fakeredis<br/>(tests + demo)<br/>or Redis<br/>(prod)")]
    end

    curl -->|"HTTP + Bearer JWT"| CORS
    CORS --> RID --> RL --> AUD
    AUD --> T
    AUD --> C
    AUD --> D
    AUD --> E
    AUD --> S

    T -->|"Depends"| GDB
    T -->|"Depends"| GCU
    T -->|"Depends"| RR
    C -->|"Depends"| GDB
    C -->|"Depends"| GCU
    D -->|"Depends"| GDB
    E -->|"Depends"| GDB
    S -->|"no DB needed"| GCU

    T --> TS
    C --> CS
    TS --> TR
    TS --> TMR
    CS --> CR
    CS --> SR
    CS --> WR

    TR --> DB
    TMR --> DB
    CR --> DB
    SR --> DB
    WR --> DB
    RL --> Redis
    AUD --> DB
```

---

## Request lifecycle diagram — creating a ticket

```mermaid
sequenceDiagram
    participant Client as Client (curl/browser)
    participant MW as Middleware Stack
    participant Router as tickets.py router
    participant DB_Dep as get_db dependency
    participant Auth as require_role("agent")
    participant Svc as ticket_service
    participant Repo as TicketRepository
    participant DB as SQLite/PostgreSQL

    Client->>MW: POST /api/v1/tickets {customer_id, subject, body, channel}
    MW->>MW: CORS check (origin allowed?)
    MW->>MW: RequestId — read or generate X-Request-ID
    MW->>MW: RateLimit — check Redis counter
    MW->>MW: Audit — will log this POST on exit

    MW->>Auth: check JWT Bearer token
    Auth->>Auth: decode_token() → role = "agent"
    Auth-->>Router: user dict {sub, role, name}

    MW->>DB_Dep: open AsyncSession
    DB_Dep->>DB: begin transaction
    DB_Dep-->>Router: session injected

    Router->>Svc: create_ticket(session, customer_id, ...)
    Svc->>Repo: get(customer_id) — does customer exist?
    Repo->>DB: SELECT * FROM customers WHERE id=?
    DB-->>Repo: Customer row
    Repo-->>Svc: Customer object

    Svc->>DB: SELECT COUNT(*) FROM tickets
    DB-->>Svc: 13 (seed count)
    Svc->>Repo: create(Ticket{ticket_number="CD-1014", ...})
    Repo->>DB: INSERT INTO tickets ...
    Svc->>Repo: create(TicketMessage{role="customer", ...})
    Repo->>DB: INSERT INTO ticket_messages ...

    Svc-->>Router: Ticket object
    Router-->>DB_Dep: return (no exception)
    DB_Dep->>DB: COMMIT
    DB_Dep->>DB: close session

    MW->>DB: INSERT INTO audit_logs (action=POST, ...)
    Router-->>Client: 201 Created {ticket_number, status, ...}
```

---

## Request lifecycle diagram — getting ticket detail

```mermaid
sequenceDiagram
    participant Client
    participant Router as tickets.py router
    participant DB_Dep as get_db
    participant Svc as ticket_service
    participant DB as Database

    Client->>Router: GET /api/v1/tickets/{id}
    Note right of Router: get_current_user validates JWT (viewer OK)
    Router->>DB_Dep: open session
    Router->>Svc: get_ticket_detail(session, ticket_id)

    Svc->>DB: SELECT * FROM tickets WHERE id=?
    Svc->>DB: SELECT * FROM ticket_messages WHERE ticket_id=?
    Svc->>DB: SELECT * FROM customers WHERE id=?
    Svc->>DB: SELECT * FROM subscriptions WHERE customer_id=?
    Svc->>DB: SELECT * FROM workspaces WHERE customer_id=?
    Svc->>DB: SELECT * FROM tickets WHERE customer_id=? (history)
    Svc->>DB: SELECT * FROM escalations WHERE ticket_id=?

    Svc-->>Router: TicketDetailResponse
    Router-->>Client: 200 OK {id, ticket_number, messages[], customer{...}, ...}
```

---

## The `get_db` dependency — plumbing detail

```mermaid
flowchart LR
    subgraph database.py
        GS["get_session()<br/>@asynccontextmanager<br/>used in tests & seed service"]
        GD["get_db()<br/>async generator<br/>used in FastAPI Depends"]
    end

    subgraph How they differ
        A["get_session() returns a context manager<br/>caller writes: async with get_session() as s:"]
        B["get_db() yields a session<br/>FastAPI manages enter/exit automatically"]
    end

    GS --> A
    GD --> B
```

Both functions open the same underlying `AsyncSession`, commit on success, and roll back on failure. They are two entry points to the same session factory — one for code that explicitly manages the context, and one for FastAPI's dependency injection system.

---

## File layout added in Phase 4

```
backend/
└── app/
    ├── api/
    │   ├── tickets.py        ← NEW: ticket CRUD routes
    │   ├── customers.py      ← NEW: customer read routes
    │   ├── dashboard.py      ← NEW: summary stub
    │   ├── escalations.py    ← NEW: escalations stub
    │   └── settings.py       ← NEW: config introspection
    ├── schemas/
    │   ├── tickets.py        ← NEW: Pydantic request/response models
    │   ├── customers.py      ← NEW: Pydantic customer models
    │   └── workflow.py       ← NEW: stub workflow state schema
    ├── services/
    │   ├── ticket_service.py ← NEW: ticket business logic
    │   └── customer_service.py ← NEW: customer business logic
    └── core/
        └── database.py       ← UPDATED: added get_db() async generator

frontend/
└── lib/
    └── types.ts              ← NEW: TypeScript type definitions (Phase 12 will use these)

docs/
└── API_CONTRACT.md           ← VERIFIED: routes and types authoritative here

tests/
└── api/
    ├── test_tickets.py       ← NEW: ticket API tests
    └── test_customers.py     ← NEW: customer API tests
```

---

## Network topology at end of Phase 4

```mermaid
graph LR
    subgraph Dev Machine
        FE["Next.js :3000<br/>(not yet built — Phase 12)"]
        BE["FastAPI :8000<br/>(running)"]
        DB[("SQLite file<br/>data/support.db")]
        RD[("fakeredis<br/>in-memory)")]
    end

    FE -->|"REST /api/v1<br/>Bearer JWT"| BE
    BE --> DB
    BE --> RD
```

**Note:** In Phase 4 development, the frontend does not exist. All API testing is done via pytest (TestClient) or curl. The frontend will be built in Phase 12 and will use `frontend/lib/types.ts` created here.

---

## What infrastructure is NOT yet present

| Component | Needed for | Phase |
|-----------|-----------|-------|
| Qdrant vector store | Knowledge retrieval | 5 |
| LangGraph executor | AI workflow | 9 |
| Checkpoint database | Resume on restart | 9 |
| Redis (real, not fake) | Rate limit in prod | Prod deploy |
| Docker containers | Deployment | 14 |
| Next.js frontend | UI | 12 |
