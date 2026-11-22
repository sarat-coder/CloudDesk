# Phase 4 — System Design Evolution: Support API

> This document traces how the system design grew during Phase 4, from "a database with no doors" to "a fully routable REST API for tickets and customers."

---

## Starting point (end of Phase 3)

After Phase 3 the system could authenticate users, enforce role-based access, rate-limit requests, and write audit logs. But it had no domain routes — no endpoints for tickets, customers, or anything a support agent would actually use.

```mermaid
graph TD
    Browser["Browser / API Client"]
    MW["Middleware Stack<br/>(CORS → RequestId → RateLimit → Audit)"]
    Auth["POST /auth/login<br/>GET /auth/me"]
    Health["GET /health/*"]
    DB[("SQLite / PostgreSQL<br/>(13 tickets, 8 customers seeded)")]

    Browser -->|"Bearer JWT"| MW
    MW --> Auth
    MW --> Health
    Auth -->|"verify / issue token"| DB
```

**Gap:** The database had all the data (from Phase 2 seed), but nothing exposed it over HTTP.

---

## Step 1 — API Contract first (P4-1)

Before writing a single route, the team wrote the contract. This is a deliberate design choice: by defining request/response shapes in `docs/API_CONTRACT.md` and `frontend/lib/types.ts` *before* the implementation, the backend and frontend stay in sync from day one.

```mermaid
graph LR
    A["docs/API_CONTRACT.md<br/>(source of truth)"]
    B["backend/app/schemas/*.py<br/>(Pydantic models)"]
    C["frontend/lib/types.ts<br/>(TypeScript interfaces)"]

    A -->|"defines"| B
    A -->|"defines"| C
    B <-->|"must stay in sync"| C
```

**Key insight:** The contract is not generated from code — the code is generated from the contract. Any change to a route *must* update `API_CONTRACT.md` first.

---

## Step 2 — Layered architecture for the Ticket API (P4-2)

The ticket functionality was split across three layers, each with a single job:

```mermaid
graph TD
    HTTP["HTTP Request<br/>POST /api/v1/tickets"]
    Router["tickets.py router<br/>• parse & validate body<br/>• check auth (require_role)<br/>• return HTTP response"]
    Service["ticket_service.py<br/>• check customer exists<br/>• generate ticket number<br/>• create Ticket + first TicketMessage"]
    Repo["TicketRepository<br/>TicketMessageRepository<br/>• SQL via SQLAlchemy"]
    DB[("Database")]

    HTTP --> Router --> Service --> Repo --> DB
```

**Why this matters:** Each layer only talks to the layer directly below it. The router never writes SQL. The service never knows about HTTP status codes. The repository never applies business rules. This is the **layering rule** from CLAUDE.md §4.2.

---

## Step 3 — The full ticket detail response (P4-2 continued)

A `GET /tickets/{id}` call traverses multiple tables and assembles a rich response:

```mermaid
graph TD
    Request["GET /tickets/{id}"]
    TS["ticket_service<br/>get_ticket_detail()"]

    T["tickets table<br/>(core fields)"]
    TM["ticket_messages table<br/>(conversation thread)"]
    C["customers table<br/>(customer name, company, plan)"]
    S["subscriptions table<br/>(seats, renewal, amount)"]
    W["workspaces table<br/>(storage, region)"]
    ESC["escalations table<br/>(if escalated)"]
    H["tickets table (again)<br/>(previous tickets for this customer)"]

    Request --> TS
    TS --> T
    TS --> TM
    TS --> C
    TS --> S
    TS --> W
    TS --> ESC
    TS --> H

    TS -->|"assembles into"| Response["TicketDetailResponse<br/>(one JSON object)"]
```

---

## Step 4 — Customer API (P4-3)

The customer layer mirrors the ticket layer in structure:

```mermaid
graph TD
    HTTP2["GET /api/v1/customers/{id}"]
    Router2["customers.py router"]
    Service2["customer_service.py<br/>get_customer_detail()"]
    DB2[("Database")]

    HTTP2 --> Router2 --> Service2 --> DB2

    Service2 -->|"returns"| CD["CustomerDetailResponse<br/>+ subscription<br/>+ workspace<br/>+ ticket history<br/>+ memory notes (empty until Phase 11)"]
```

---

## Complete system design at end of Phase 4

```mermaid
graph TD
    Client["Browser / API Client / Tests"]

    subgraph Middleware ["Middleware (outermost→innermost)"]
        CORS["CORS"]
        RID["RequestId"]
        RL["RateLimit"]
        AUD["Audit"]
    end

    subgraph API ["API Layer /api/v1/"]
        AuthR["auth router<br/>(Phase 3)"]
        TickR["tickets router<br/>(Phase 4) ✅"]
        CustR["customers router<br/>(Phase 4) ✅"]
        DashR["dashboard router<br/>(Phase 4 stub) ✅"]
        EscR["escalations router<br/>(Phase 4 stub) ✅"]
        SetR["settings router<br/>(Phase 4) ✅"]
        HealthR["health routes<br/>(Phase 1)"]
    end

    subgraph Services ["Services Layer"]
        TickS["ticket_service"]
        CustS["customer_service"]
        SeedS["seed_service (Phase 2)"]
    end

    subgraph Repos ["Repository Layer"]
        TickRepo["TicketRepository<br/>TicketMessageRepository"]
        CustRepo["CustomerRepository<br/>SubscriptionRepository<br/>WorkspaceRepository"]
        AuditRepo["AuditRepository"]
    end

    subgraph DB ["Data Stores"]
        SQLite[("SQLite / PostgreSQL")]
        Redis[("Redis / fakeredis<br/>(rate limit)")]
    end

    Client --> CORS --> RID --> RL --> AUD
    AUD --> AuthR
    AUD --> TickR
    AUD --> CustR
    AUD --> DashR
    AUD --> EscR
    AUD --> SetR
    AUD --> HealthR

    TickR --> TickS --> TickRepo --> SQLite
    CustR --> CustS --> CustRepo --> SQLite
    RL --> Redis
    AuditRepo --> SQLite
```

---

## Design decisions made in Phase 4

### 1. The `get_db` dependency pattern

FastAPI's dependency injection requires async generator functions (using `yield`). The existing `get_session()` helper used `@asynccontextmanager` which is not compatible. A new `get_db()` async generator was added to `core/database.py` as the standard FastAPI dependency.

```mermaid
sequenceDiagram
    participant FastAPI
    participant get_db
    participant AsyncSession

    FastAPI->>get_db: call dependency
    get_db->>AsyncSession: open session
    get_db-->>FastAPI: yield session
    FastAPI->>RouteHandler: inject session
    RouteHandler->>AsyncSession: execute queries
    FastAPI->>get_db: request complete
    get_db->>AsyncSession: commit() or rollback()
    get_db->>AsyncSession: close
```

### 2. Ticket number generation

Ticket numbers follow the `CD-NNNN` format used in the demo scenario. The service counts existing tickets and continues from where the seed data ends (CD-1013). A collision-prevention loop handles edge cases.

### 3. Stub endpoints for phase-forward compatibility

The `/tickets/{id}/run`, `/tickets/{id}/workflow`, `/tickets/{id}/events` routes exist and return valid responses even though the workflow engine is not built yet. This keeps the frontend (Phase 12) from hitting 404s during parallel development.

---

## What the design does NOT yet include

| Feature | Phase |
|---------|-------|
| Run AI workflow (`POST /tickets/{id}/run` → 202) | 10 |
| Workflow state polling | 9 |
| Human approval flow | 10 |
| Escalation records | 10 |
| Memory notes in customer context | 11 |
| Full dashboard metrics | 9 |
| Frontend pages | 12 |
