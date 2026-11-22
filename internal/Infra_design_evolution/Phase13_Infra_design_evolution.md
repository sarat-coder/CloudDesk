# Phase 13 — Ticket Workflow Screen: Infrastructure and Component Wiring

## Overview

Phase 13 adds no new backend infrastructure. It wires the already-running services together through the browser's ticket detail screen. The infrastructure story for this phase is entirely about **how the browser communicates with the API** to drive the live workflow panel.

---

## Component Map at the Start of Phase 13

```mermaid
graph TB
    subgraph "User's Browser"
        LOGIN["/login page"]
        DASH["/dashboard pages (list views)"]
        TICKET_STUB["/tickets/[id] (stub)\nshowed messages only"]
    end

    subgraph "Next.js Server (:3000)"
        MIDDLEWARE["middleware.ts\nauth guard"]
        PAGES["App Router pages"]
    end

    subgraph "FastAPI (:8000)"
        AUTH_RT["/api/v1/auth"]
        TICKET_RT["/api/v1/tickets"]
        WORKFLOW_RT["/api/v1/tickets/{id}/workflow"]
        APPROVAL_RT["/api/v1/approvals"]
    end

    subgraph "Data Stores"
        SQLITE["SQLite (support.db)\ntickets, customers, workflow_runs"]
        CHECKDB["checkpoints.db\nLangGraph state"]
        FAKEREDIS["fakeredis\nshort-term memory, rate limit"]
        INMEM["In-memory vector store\nknowledge chunks"]
    end

    LOGIN --> AUTH_RT
    DASH --> TICKET_RT
    TICKET_STUB -.->|not yet wired to workflow| WORKFLOW_RT
    MIDDLEWARE --> PAGES
    TICKET_RT --> SQLITE
    WORKFLOW_RT --> SQLITE
    WORKFLOW_RT --> CHECKDB
```

The `TICKET_STUB` → `WORKFLOW_RT` connection was not yet made. Phase 13 completes it.

---

## What Phase 13 Adds to the Wiring

```mermaid
graph TB
    subgraph "User's Browser"
        TICKET_PAGE["/tickets/[id]\n(fully wired)"]
        POLL["useWorkflowPolling\nGET /workflow every 2s"]
        ACTIONS["Action handlers\nrun · reply · approve · reject · escalate"]
    end

    subgraph "Next.js Server (:3000)"
        MIDDLEWARE["middleware.ts"]
    end

    subgraph "FastAPI (:8000)"
        RT_RUN["POST /tickets/{id}/run\n→ starts workflow in background"]
        RT_WF["GET /tickets/{id}/workflow\n→ returns current WorkflowState"]
        RT_REPLY["POST /tickets/{id}/reply\n→ adds message to thread"]
        RT_APR_A["POST /approvals/{id}/approve\n→ resumes paused graph"]
        RT_APR_R["POST /approvals/{id}/reject\n→ routes to escalation"]
        RT_ESC["POST /tickets/{id}/escalate\n→ creates escalation record"]
    end

    TICKET_PAGE --> POLL
    POLL -->|every 2 seconds| RT_WF
    TICKET_PAGE --> ACTIONS
    ACTIONS --> RT_RUN
    ACTIONS --> RT_REPLY
    ACTIONS --> RT_APR_A
    ACTIONS --> RT_APR_R
    ACTIONS --> RT_ESC
```

---

## The Polling Loop in Detail

The browser does not receive push notifications. It uses a timed polling loop to stay up to date with the AI workflow's progress.

```mermaid
sequenceDiagram
    participant B as Browser Tab
    participant MW as Next.js Middleware
    participant API as FastAPI :8000
    participant WS as Workflow Service
    participant DB as SQLite

    B->>API: POST /tickets/{id}/run
    Note over API,WS: BackgroundTasks starts workflow
    API-->>B: 202 { workflow_id }

    loop Poll every 2 s until terminal state
        B->>API: GET /tickets/{id}/workflow
        API->>WS: get_workflow_state(ticket_id)
        WS->>DB: SELECT workflow_runs WHERE ticket_id=?
        DB-->>WS: row with state JSON
        WS-->>API: WorkflowState
        API-->>B: WorkflowState JSON
        B->>B: deriveSteps(state) → re-render 12 steps

        alt state.status in [completed, failed, escalated]
            B->>B: Stop polling timer
        end
    end
```

**Key networking details:**
- All requests carry `Authorization: Bearer <JWT>` from localStorage
- The API validates the JWT on every request (Phase 3 middleware)
- If the fetch throws (network down), the hook retries after 5 seconds instead of 2 seconds
- If the server returns 401, the browser is redirected to `/login?reason=expired`

---

## The Approval Interrupt Flow

When the AI hits a step that requires human approval (e.g. a refund), the LangGraph workflow **pauses itself** and stores its full state in `checkpoints.db`. The browser detects this via the `approval_status === "pending"` field on `WorkflowState` and shows the Approve/Reject buttons.

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as FastAPI
    participant WS as Workflow Service
    participant CK as checkpoints.db
    participant TOOL as ToolRegistry

    Note over API,CK: AI workflow paused — approval_status = "pending"
    B->>B: Polling detects approval_status === "pending"
    B->>B: Render Approve + Reject buttons

    B->>API: POST /approvals/{id}/approve { note }
    API->>WS: approval_service.decide(id, approved=True)
    WS->>CK: resume_workflow(Command(resume=True))
    CK-->>WS: Resumed graph continues from interrupt point
    WS->>TOOL: ToolRegistry.execute("create_refund_request", args, approved=True)
    TOOL-->>WS: ToolResult(ok=True)
    WS-->>API: Updated WorkflowState
    API-->>B: { approval, workflow }
    B->>B: Reload ticket + continue polling
```

---

## The Manual Escalate Flow

The agent can escalate a ticket manually when the AI did not auto-escalate it. This is a simple REST write — no graph resume involved.

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as FastAPI :8000
    participant SVC as EscalationService
    participant DB as SQLite

    B->>API: POST /tickets/{id}/escalate\n{ reason: "VIP customer", priority: "normal" }
    API->>API: require_role("agent")
    API->>SVC: create_escalation(ticket_id, reason, assigned_team, ...)
    SVC->>DB: INSERT escalations (id, ticket_id, reason, assigned_team)
    SVC->>DB: UPDATE tickets SET status="escalated"
    SVC->>DB: INSERT audit_logs (action="escalate")
    DB-->>SVC: ok
    SVC-->>API: Escalation record
    API-->>B: 200 Escalation JSON
    B->>B: Show "Ticket escalated" message
    B->>B: Reload ticket (status is now "escalated")
    B->>B: Escalate button disappears (shouldShowEscalate returns false)
```

---

## Network Topology for Phase 13

```mermaid
graph LR
    subgraph "Client Side"
        BROWSER["Browser\nlocalStorage: JWT, role, email"]
    end

    subgraph "Next.js Container (:3000)"
        NEXT_MW["Auth middleware\n(reads cookie)"]
        NEXT_PAGE["RSC + Client Components\n(React Server Components\nfor layout,\nClient Components for\npolling and actions)"]
    end

    subgraph "FastAPI Container (:8000)"
        CORS["CORSMiddleware\norigin: http://localhost:3000"]
        REQID["RequestIdMiddleware\nX-Request-ID header"]
        RATELIM["RateLimitMiddleware\n120 req/min per client"]
        AUDIT["AuditMiddleware\nlogs non-GET requests"]
        ROUTES["Ticket routes\nApproval routes\nEscalation routes"]
    end

    BROWSER -->|HTTPS :3000| NEXT_MW
    NEXT_MW --> NEXT_PAGE
    NEXT_PAGE -->|REST API calls\nBearer JWT| CORS
    CORS --> REQID
    REQID --> RATELIM
    RATELIM --> AUDIT
    AUDIT --> ROUTES
```

**Middleware order (outermost to innermost):**
1. CORS — allows requests from the Next.js origin
2. RequestId — stamps every request and response with `X-Request-ID`
3. RateLimit — 120 requests per minute per client IP, using Redis
4. Audit — writes `audit_logs` for every non-GET request
5. Routes — the actual handlers

---

## Data Flow Summary

```mermaid
flowchart TD
    BROWSER[Browser\nuseWorkflowPolling]
    -->|GET /tickets/id/workflow every 2s| FASTAPI[FastAPI\nworkflow_service.get_state]
    --> SQLITE[SQLite workflow_runs table\nstate JSON = WorkflowState]
    --> BROWSER

    BROWSER2[Browser\nApprove button]
    -->|POST /approvals/id/approve| FASTAPI2[FastAPI\napproval_service.decide]
    --> CHECKPOINT[checkpoints.db\nresumed LangGraph state]
    --> TOOL[ToolRegistry\ncreate_refund_request]
    --> SQLITE2[SQLite\nresolution_actions, audit_logs]
    --> BROWSER2

    BROWSER3[Browser\nEscalate button]
    -->|POST /tickets/id/escalate| FASTAPI3[FastAPI\nescalation_service.create]
    --> SQLITE3[SQLite\nescalations, ticket status update, audit_logs]
    --> BROWSER3
```

---

## What Changed vs Phase 12

| Aspect | Phase 12 | Phase 13 |
|---|---|---|
| Ticket detail page | Static — showed messages and customer info | Dynamic — polling, live 12-step tracker |
| Workflow connection | No connection to AI workflow state | Polls `/tickets/{id}/workflow` every 2 seconds |
| Action buttons | None wired | Run, Reply, Approve, Reject, Escalate all functional |
| Helper logic | Inline conditionals in page | Extracted to pure functions in `hooks.ts` |
| Test coverage | StatusPill, EmptyState, WorkflowSteps, API | Plus: TicketActions (approve/reject/escalate conditionals) |
