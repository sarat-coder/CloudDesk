# Phase 11 — Infra & Component Wiring: Approval & Escalation

**Audience:** Interview board including non-technical members.

---

## Overview

Phase 11 extends the Phase 10 component wiring with two new flows:

1. **The approval flow** — a request that pauses mid-workflow and waits for a human click to resume.
2. **The escalation flow** — a request that bypasses the approval gate and routes straight to a specialist team record.

Both flows share the same infrastructure components (FastAPI, LangGraph, SQLite/PostgreSQL, the checkpointer). What changes is the **path** those requests take through those components and the new tables that are written along the way.

---

## Component Architecture at End of Phase 11

```mermaid
graph TB
    Browser["🌐 Browser\n(React frontend)"]
    API["🚀 FastAPI :8000\n• /tickets/{id}/run\n• /tickets/{id}/workflow\n• /approvals/{id}/approve\n• /approvals/{id}/reject\n• /api/v1/agents"]
    BG["⚙️ BackgroundTasks\n(In-process worker)"]
    Graph["🤖 LangGraph StateGraph\n13 nodes + 3-way router"]
    CP["💾 Checkpointer\nInMemorySaver (tests)\nAsyncSqliteSaver (prod)\ndata/checkpoints.db"]
    DB["🗄️ SQLite / PostgreSQL\ntickets\nworkflow_runs\nworkflow_events\napproval_requests ✦NEW\nresolution_actions ✦NEW\nescalations ✦NEW"]
    Redis["⚡ Redis / FakeRedis\nRate limit • Session cache"]
    LLM["🧠 LLM Provider\nfake / OpenAI / Anthropic"]
    Tools["🔧 ToolRegistry\nget_customer\nupdate_ticket\ncreate_refund_request ✦gated\nreset_demo_setting ✦gated\ncreate_escalation"]

    Browser -->|"POST /run → 202 + workflow_id\nGET /workflow (poll 2s)\nPOST /approve or /reject"| API
    API -->|"Background: start_workflow()"| BG
    BG -->|"graph.astream(state)"| Graph
    Graph <-->|"checkpoint after every node\nload on resume"| CP
    Graph -->|"write approval_requests\nresolution_actions\nescalations\nworkflow_events"| DB
    API -->|"read approval_requests\nworkflow_runs"| DB
    Graph -->|"registry.execute(tool, args)"| Tools
    Graph -->|"call_structured\n(EscalationAgent)"| LLM
    API -->|"rate limit\nsession token"| Redis

    style Browser fill:#4A90D9,color:#fff
    style API fill:#2E8B57,color:#fff
    style BG fill:#8B6914,color:#fff
    style Graph fill:#9B4DCA,color:#fff
    style CP fill:#16A085,color:#fff
    style DB fill:#C0392B,color:#fff
    style Tools fill:#1A5276,color:#fff
```

---

## Flow 1: The Approval Path (CD-1002 — Refund Ticket)

This flow shows what happens when the resolution plan contains a `create_refund_request` action.

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as FastAPI :8000
    participant BG as BackgroundTasks
    participant Graph as LangGraph Graph
    participant CP as Checkpointer (SQLite)
    participant DB as Database (SQLite)
    participant Tools as ToolRegistry

    UI->>API: POST /api/v1/tickets/CD-1002/run
    API->>DB: INSERT workflow_runs (status=running)
    API-->>UI: 202 { workflow_id }
    API->>BG: add_task(start_workflow)

    Note over BG,Graph: Nodes 1-6 run (understand→resolution_planning)
    BG->>Graph: graph.astream(initial_state)
    Graph->>DB: write workflow_events (8 node events)

    Note over Graph: resolution_planning finds create_refund_request → requires_approval=True
    Note over Graph: escalation_check → no policy rule matches
    Note over Graph: risk_check → routes to human_approval

    Graph->>DB: INSERT approval_requests (status=pending)
    Graph->>DB: UPDATE tickets SET status='waiting_on_approval'
    Graph->>CP: SAVE full SupportState (all 8 nodes' output)
    Graph-->>BG: graph paused (interrupt returns)
    BG->>DB: UPDATE workflow_runs SET status='waiting_on_approval'

    UI->>API: GET /api/v1/tickets/CD-1002/workflow (poll)
    API->>DB: SELECT workflow_runs WHERE id=...
    API-->>UI: { status: "waiting_on_approval", completed_nodes: [...8 nodes] }

    Note over UI: Agent reviews the plan, clicks Approve
    UI->>API: POST /api/v1/approvals/{id}/approve
    API->>DB: UPDATE approval_requests SET status='approved', decided_by='sam.agent'
    API->>Graph: Command(resume={approved:true, decided_by:'sam.agent'})
    Graph->>CP: LOAD saved SupportState
    Graph->>Tools: registry.execute('create_refund_request', {amount: 50}, approved=True)
    Graph->>DB: INSERT resolution_actions (status=completed)
    Graph->>DB: UPDATE workflow_runs SET status='completed'
    Graph->>DB: UPDATE tickets SET status='resolved'
    API-->>UI: { decision: "approved", run_id: "..." }
```

---

## Flow 2: The Auto-Escalation Path (CD-1005 — Security Breach)

This flow shows what happens when a policy rule fires before human_approval is ever reached.

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as FastAPI :8000
    participant BG as BackgroundTasks
    participant Graph as LangGraph Graph
    participant DB as Database (SQLite)

    UI->>API: POST /api/v1/tickets/CD-1005/run
    API->>DB: INSERT workflow_runs (status=running)
    API-->>UI: 202 { workflow_id }
    API->>BG: add_task(start_workflow)

    Note over BG,Graph: Nodes 1-6 run (understand→resolution_planning)
    BG->>Graph: graph.astream(initial_state)

    Note over Graph: escalation_check detects "suspicious logins" keyword
    Note over Graph: Policy rule fires → team='Security Team', escalation_required=True
    Note over Graph: risk_check → routes to escalation (NOT human_approval)

    Graph->>DB: INSERT escalations (team='Security Team', priority='high')
    Graph->>DB: UPDATE tickets SET status='escalated'
    Graph->>DB: INSERT workflow_events (escalation created)
    Graph->>DB: UPDATE workflow_runs SET status='escalated'
    UI->>API: GET /api/v1/tickets/CD-1005/workflow (poll)
    API-->>UI: { status: "escalated", escalation_team: "Security Team" }

    Note over UI: No approval prompt ever shown. Human_approval node never reached.
```

---

## Flow 3: The Reject-to-Escalation Path

This flow shows what happens when an agent reviews and rejects an approval request.

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as FastAPI :8000
    participant Graph as LangGraph Graph
    participant CP as Checkpointer
    participant DB as Database

    Note over UI,DB: Graph is paused at human_approval (same as Flow 1)

    UI->>API: POST /api/v1/approvals/{id}/reject
    API->>DB: UPDATE approval_requests SET status='rejected', decided_by='sam.agent'
    API->>Graph: Command(resume={approved:false, decided_by:'sam.agent'})
    Graph->>CP: LOAD saved SupportState
    Note over Graph: _route_after_human_approval sees approved=False → escalation
    Graph->>DB: INSERT escalations (reason='Agent rejected approval')
    Graph->>DB: UPDATE tickets SET status='escalated'
    Graph->>DB: UPDATE workflow_runs SET status='escalated'
    API-->>UI: { decision: "rejected", run_id: "..." }
```

---

## The Checkpointer: What It Stores and Why

```mermaid
graph TB
    subgraph "Before interrupt()"
        N1["understand_ticket output:\nclassification, injection_flagged"]
        N2["classify_severity output:\nseverity = high"]
        N3["customer_context output:\ncustomer profile, history"]
        N4["knowledge_retrieval output:\nevidence[], similar_cases[]"]
        N5["resolution_planning output:\nresolution_plan, planned_actions"]
    end

    CP["💾 Checkpointer\n(data/checkpoints.db)\nKeyed by thread_id = run_id\n\nStores the entire SupportState\nas a serialised JSON blob"]

    N1 --> CP
    N2 --> CP
    N3 --> CP
    N4 --> CP
    N5 --> CP

    CP -->|"On resume:\nrestore full state,\ncontinue from interrupt()"| Execute["execute_resolution\nreceives ALL prior output\nas if the graph never stopped"]

    style CP fill:#16A085,color:#fff
    style Execute fill:#27AE60,color:#fff
```

**Why is this important?** The execute_resolution node needs access to outputs from every earlier node — the customer's subscription plan, the evidence from the knowledge base, the planned actions, the ticket ID. Without the checkpointer, all of that would be lost when the graph pauses. The checkpointer makes the pause completely transparent to the executing nodes.

---

## Approval API Routing

```mermaid
graph LR
    subgraph "FastAPI Routers (mounted at /api/v1)"
        R_Approvals["approvals.py router\n/approvals/{id}"]
    end

    subgraph "RBAC layer (require_role)"
        GET["GET /approvals/{id}\nAny authenticated user"]
        POST_A["POST /approvals/{id}/approve\nAgent role required"]
        POST_R["POST /approvals/{id}/reject\nAgent role required"]
    end

    subgraph "approval_service.py"
        S_Get["get_pending_approval(db, id)"]
        S_Decide["decide(db, id, approved, decided_by)"]
        S_Resume["resume_workflow(run_id, approved, decided_by)"]
    end

    R_Approvals --> GET
    R_Approvals --> POST_A
    R_Approvals --> POST_R

    GET --> S_Get
    POST_A --> S_Decide
    POST_R --> S_Decide
    S_Decide --> S_Resume
```

**RBAC enforcement note:** `require_role("agent")` is a FastAPI dependency injected on the approve and reject endpoints. If a viewer token is presented, the dependency raises `HTTPException(403)` before the service layer is even called. The viewer cannot approve even if they guess the approval ID.

---

## Race Condition Protection

```mermaid
flowchart TD
    Agent1["Agent 1 clicks Approve"] -->|"POST /approvals/{id}/approve"| Check1
    Agent2["Agent 2 also clicks Approve\n(race condition)"] -->|"POST /approvals/{id}/approve"| Check2

    Check1["approval_service.decide()\nLoads approval from DB\napproval.status == 'pending' ✓"] -->|"UPDATE status='approved'"| Commit["DB commit\n(atomic)"]
    Check2["approval_service.decide()\nLoads approval from DB\napproval.status == 'approved' ✗"] -->|"status != 'pending'"| Error["raise ValueError('already approved')\n→ HTTP 409 Conflict"]

    Commit --> Resume["resume_workflow()\nGraph continues once"]
    Error --> UI2["Agent 2 sees:\n409 Conflict — already decided"]
```

The database `UPDATE` is atomic. Only one transaction succeeds; the other sees the already-updated status and returns 409.

---

## Demo Script Component Wiring

```mermaid
graph TD
    CLI["Terminal: make demo\nor make demo TICKET=CD-1005"]
    Script["scripts/demo.py\n(Python CLI)"]
    DB_Init["Bootstrap DB\n(seed sample data if empty)"]
    Ingest["Index knowledge base\n(if not already indexed)"]
    API_Run["POST /tickets/{id}/run\nGet workflow_id"]
    Poll["GET /tickets/{id}/workflow\nevery 2 seconds"]
    Branch{Status?}
    Approve["User presses Enter\n→ POST /approvals/{id}/approve"]
    Done["Print final resolution plan\nPrint escalation team (if escalated)"]

    CLI --> Script
    Script --> DB_Init
    DB_Init --> Ingest
    Ingest --> API_Run
    API_Run --> Poll
    Poll --> Branch
    Branch -->|"waiting_on_approval\n(CD-1002 path)"| Approve
    Branch -->|"escalated\n(CD-1005 path)"| Done
    Branch -->|"completed"| Done
    Branch -->|"running"| Poll
    Approve --> Poll
```

The demo script is a **self-contained end-to-end test in a terminal**. It wires through the full HTTP API (not direct function calls), which means it exercises the same RBAC, rate limiting, audit logging, and serialisation paths that the real frontend would use.

---

## Network Ports and Process Boundaries (Phase 11)

```mermaid
graph LR
    subgraph "Single Python Process"
        FastAPI["FastAPI\n:8000"]
        BG["BackgroundTasks\n(in-process)"]
        Graph["LangGraph\n(in-memory)"]
        CP_Mem["Checkpointer\n(AsyncSqliteSaver\ndata/checkpoints.db)"]
    end

    subgraph "File System"
        DB_File["data/support.db\n(SQLite)"]
        CP_File["data/checkpoints.db\n(SQLite)"]
    end

    subgraph "In-Memory (tests)"
        FakeRedis["FakeRedis"]
        MemCP["InMemorySaver"]
        TmpDB["Temp SQLite\n(deleted after tests)"]
    end

    FastAPI <--> BG
    BG <--> Graph
    Graph <--> CP_Mem
    CP_Mem <--> CP_File
    FastAPI <--> DB_File
    Graph <--> DB_File
```

**Production note:** In this phase everything runs in one process. The checkpointer and the main database are separate SQLite files intentionally — the checkpointer only LangGraph reads/writes; the application DB is owned by the FastAPI layer. When migrating to Postgres, only `DATABASE_URL` and `CHECKPOINT_DB_PATH` change — the code is the same.

---

## Summary: What Phase 11 Added to the Infrastructure

| Component | Before Phase 11 | After Phase 11 |
|---|---|---|
| `human_approval` node | Did not exist | Calls `interrupt()`, writes `approval_requests`, pauses graph |
| `execute_resolution` node | Stub | Calls ToolRegistry for every planned action, writes `resolution_actions` |
| `escalation` node | Did not exist as a wired node | Writes `escalations`, updates ticket status |
| Approvals API | Did not exist | 3 endpoints: GET / approve / reject with RBAC |
| Approval service | Did not exist | Decides, records decision, resumes paused graph |
| New DB tables | — | `approval_requests`, `resolution_actions`, `escalations` |
| Demo script | Did not exist | CD-1002 (approve path) and CD-1005 (escalation path) |
