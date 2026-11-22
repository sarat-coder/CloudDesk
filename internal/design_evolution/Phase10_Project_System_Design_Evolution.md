# Phase 10 — Project System Design Evolution

## Overview

Phase 10 integrates all specialist agents into a single orchestrated workflow. The design evolved from "six separate agents that can be called individually" (Phase 9) to "one graph that orchestrates them all in sequence with conditional routing, an approval gate, and escalation paths."

---

## Stage 1: Starting Point (End of Phase 9)

At the end of Phase 9, we had six specialist agents that could each be called independently. There was no orchestration, no shared state, no routing logic, and no way to run a ticket end-to-end. The workflow endpoint was a stub returning `"not_implemented_until_phase_10"`.

```mermaid
graph TD
    A[Ticket arrives] --> B[Manual: call each agent]
    B --> C[SupervisorAgent]
    B --> D[CustomerAgent]
    B --> E[KnowledgeAgent]
    B --> F[TroubleshootingAgent]
    B --> G[ResolutionAgent]
    B --> H[EscalationAgent]
    C --> I[Results unconnected]
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
```

**Problem**: No shared state. No routing. No execution of actions. No approval gate. No observability.

---

## Stage 2: LangGraph StateGraph — Linear Pipeline

The first step was to wire the agents into a linear sequence using LangGraph's `StateGraph`. Every node reads from and writes to a single shared `SupportState` object — a TypedDict that accumulates findings as the ticket moves through the graph.

```mermaid
flowchart LR
    START --> understand_ticket
    understand_ticket --> classify_severity
    classify_severity --> customer_context
    customer_context --> knowledge_retrieval
    knowledge_retrieval --> troubleshooting
    troubleshooting --> resolution_planning
    resolution_planning --> escalation_check
    escalation_check --> risk_check
    risk_check --> execute_resolution
    execute_resolution --> ticket_summary
    ticket_summary --> memory_update
    memory_update --> END
```

**Key design decisions at this stage:**
- Each node returns a **partial dict** — it only sets the keys it owns
- Two reducer fields (`errors`, `completed_nodes`) use `operator.add` — they append rather than overwrite
- `token_usage` uses a custom `merge_usage` reducer that sums token counts across nodes
- A node never sees the full state of the graph — only what previous nodes wrote

---

## Stage 3: Conditional Routing — Branching After risk_check

The linear graph was extended with conditional edges after `risk_check`. The routing function `_route_after_risk()` reads the state and returns a string that tells LangGraph which node to visit next.

```mermaid
flowchart TD
    START([START]) --> understand_ticket
    understand_ticket --> classify_severity
    classify_severity --> customer_context
    customer_context --> knowledge_retrieval
    knowledge_retrieval --> troubleshooting
    troubleshooting --> resolution_planning
    resolution_planning --> escalation_check
    escalation_check --> risk_check

    risk_check -->|escalation_required = true| escalation
    risk_check -->|approval-required actions| human_approval
    risk_check -->|low / medium risk| execute_resolution

    human_approval -->|approved = true| execute_resolution
    human_approval -->|approved = false| escalation

    execute_resolution --> ticket_summary
    escalation --> ticket_summary
    ticket_summary --> memory_update
    memory_update --> END([END])

    style human_approval fill:#f9c,stroke:#c33
    style escalation fill:#fca,stroke:#c63
    style execute_resolution fill:#cfc,stroke:#363
```

**Three routing outcomes after `risk_check`:**

| Condition | Route To |
|---|---|
| `escalation_decision.escalation_required == True` | `escalation` node |
| Any `planned_action.requires_approval == True` | `human_approval` node |
| Neither | `execute_resolution` node |

**After `human_approval`:**

| Decision | Route To |
|---|---|
| `approved == True` | `execute_resolution` |
| `approved == False` | `escalation` |

---

## Stage 4: The Approval Gate — LangGraph interrupt()

The most architecturally significant addition in Phase 10 is the human approval gate, implemented using LangGraph's `interrupt()` primitive.

```mermaid
sequenceDiagram
    participant UI as Support Agent (UI)
    participant API as FastAPI
    participant BG as BackgroundTask
    participant Graph as LangGraph Graph
    participant DB as Database
    participant CP as Checkpointer (SQLite)

    UI->>API: POST /tickets/{id}/run
    API->>DB: INSERT workflow_runs (status=running)
    API-->>UI: 202 {workflow_id}
    API->>BG: start_workflow() in background

    BG->>Graph: graph.astream(initial_state)
    Graph->>Graph: ...runs nodes 1–8...
    Graph->>DB: INSERT approval_requests (status=pending)
    Graph->>DB: UPDATE tickets (status=waiting_on_approval)
    Graph->>CP: checkpoint state at human_approval
    Graph-->>BG: interrupt() — graph suspends

    loop Poll every 2 seconds
        UI->>API: GET /tickets/{id}/workflow
        API->>DB: SELECT workflow_runs
        API-->>UI: {status: "waiting_on_approval", ...}
    end

    UI->>API: POST /approvals/{id}/approve
    API->>DB: UPDATE approval_requests (status=approved)
    API->>Graph: graph.astream(Command(resume={approved:true}))
    Graph->>CP: restore state from checkpoint
    Graph->>Graph: ...continues from human_approval...
    Graph->>Graph: execute_resolution → ticket_summary → memory_update
    Graph-->>API: completed
    API->>DB: UPDATE workflow_runs (status=completed)
```

**What "interrupt" means:** The graph's execution suspends at the `human_approval` node. The entire state (all outputs from nodes 1–8) is saved to a SQLite database by the checkpointer. When the agent approves, the graph is resumed with `Command(resume={approved: True, decided_by: "agent-id"})`. The graph restores from the checkpoint and continues as if it never stopped.

---

## Stage 5: Observability Layer

Every node emits events to `workflow_events` via `WorkflowTracer`.

```mermaid
graph TD
    subgraph "Each Graph Node"
        N1[Node starts] --> E1[emit: node_started]
        N2[Node runs] --> E2[emit: llm_called with tokens/cost]
        N2 --> E3[emit: tool_called with ok/fail]
        N3[Node ends] --> E4[emit: node_completed with duration_ms]
    end

    subgraph "Special Events"
        AP[human_approval node] --> E5[emit: approval_requested]
        AR[after resume] --> E6[emit: approval_resolved]
        ERR[any exception] --> E7[emit: error]
        END[graph finishes] --> E8[emit: workflow_completed]
    end

    E1 --> DB[(workflow_events table)]
    E2 --> DB
    E3 --> DB
    E4 --> DB
    E5 --> DB
    E6 --> DB
    E7 --> DB
    E8 --> DB
```

**WorkflowTracer design rule:** Every `_emit()` call is wrapped in a try/except that swallows failures. Telemetry errors are logged at DEBUG level and never propagate to the workflow.

---

## Stage 6: Full System Architecture at End of Phase 10

```mermaid
graph TB
    subgraph "Browser"
        UI[Next.js UI]
    end

    subgraph "FastAPI :8000"
        AR[/tickets/id/run/]
        AW[/tickets/id/workflow/]
        AE[/tickets/id/events/]
        AA[/approvals/id/approve/]
        AJ[/approvals/id/reject/]
    end

    subgraph "Services Layer"
        WS[workflow_service]
        AS[approval_service]
    end

    subgraph "LangGraph Workflow"
        GR[graph.py — StateGraph]
        subgraph "Nodes"
            N1[understand_ticket]
            N2[classify_severity]
            N3[customer_context]
            N4[knowledge_retrieval]
            N5[troubleshooting]
            N6[resolution_planning]
            N7[escalation_check]
            N8[risk_check]
            N9A[escalation]
            N9B[human_approval]
            N9C[execute_resolution]
            N10[ticket_summary]
            N11[memory_update]
        end
        CP[Checkpointer]
        OB[WorkflowTracer]
    end

    subgraph "Data Stores"
        SQLDB[(SQLite / PostgreSQL)]
        REDIS[(Redis / fakeredis)]
        QDRANT[(Vector Store)]
    end

    subgraph "Specialist Agents"
        SA[SupervisorAgent]
        CA[CustomerAgent]
        KA[KnowledgeAgent]
        TA[TroubleshootingAgent]
        RA[ResolutionAgent]
        EA[EscalationAgent]
    end

    UI -->|POST /run| AR
    UI -->|GET /workflow poll| AW
    UI -->|POST /approve| AA

    AR --> WS
    AA --> AS
    AW --> WS

    WS -->|BackgroundTask| GR
    AS -->|Command resume| GR

    GR --> N1 --> N2 --> N3 --> N4 --> N5 --> N6 --> N7 --> N8
    N8 -->|conditional| N9A
    N8 -->|conditional| N9B
    N8 -->|conditional| N9C
    N9B -->|interrupt/resume| CP
    N9A --> N10
    N9C --> N10
    N10 --> N11

    N1 --- SA
    N2 --- SA
    N3 --- CA
    N4 --- KA
    N5 --- TA
    N6 --- RA
    N7 --- EA

    GR --> OB
    OB --> SQLDB
    WS --> SQLDB
    AS --> SQLDB
    CA --> REDIS
    KA --> QDRANT
```

---

## Key Design Decisions Summary

| Decision | Why |
|---|---|
| LangGraph StateGraph | Built-in checkpointing, interrupt/resume, conditional edges — exactly what approval gates need |
| TypedDict with Annotated reducers | Partial state updates from each node without overwriting; type safety |
| `interrupt_before=["human_approval"]` | Graph pauses before the node runs on first entry; resumes inside it |
| Idempotent pre-interrupt code | The code before `interrupt()` can run twice on resume; it checks for existing DB rows first |
| WorkflowTracer never raises | Telemetry failures must not break a live support case |
| `_route_after_risk` reads escalation_decision AND planned_actions | Two separate high-risk paths need separate routing keys |
| BackgroundTasks (in-process) for v1 | No external queue needed; acceptable for demo load; production moves to a worker |
| `_serialise_state` before DB write | Pydantic models are not JSON-serialisable; must be `.model_dump()`'d before storing in JSON column |
