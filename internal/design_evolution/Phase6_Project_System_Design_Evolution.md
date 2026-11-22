# Phase 6 — System Design Evolution: Tools and Policy

## Where we started (end of Phase 5)

After Phase 5 we had a full knowledge retrieval pipeline, but the system still had no concept of **actions**.  
The AI could read tickets and search articles but could not change anything.  
There was no safety mechanism to control what the AI was permitted to do.

### Phase 5 ending state

```mermaid
graph TD
    Browser["Browser / API client"]
    FastAPI["FastAPI backend :8000"]
    DB[("SQLite / Postgres\ntables: tickets, customers, …")]
    RAG["RAG Pipeline\nchunking · vector store · retriever"]
    KB["Knowledge Base\n15 articles · BM25 + Semantic"]

    Browser -->|REST / JWT| FastAPI
    FastAPI -->|SQL| DB
    FastAPI -->|search| RAG
    RAG -->|indexed chunks| KB
```

The system could answer questions but could not take action.

---

## Step 1: Defining what "actions" look like

The first design decision was to model every action as a **named, typed function** with a clear contract.

```mermaid
graph LR
    Agent["AI Agent"]
    Tool["Tool Function\nasync def get_customer(customer_id)"]
    DB[("Database")]

    Agent -->|calls directly| Tool
    Tool -->|SQL| DB
```

**Problem with this design:** nothing stops the agent from calling any function at any time, with no safety checks and no timeout. A refund could be issued without anyone knowing.

---

## Step 2: Adding a Policy layer

The fix is to never call tools directly. Every call goes through a **policy check** first.

```mermaid
graph LR
    Agent["AI Agent"]
    Policy["ToolPolicy\n'does this need approval?'"]
    Tool["Tool Function"]
    DB[("Database")]

    Agent -->|"execute(name, args, approved?)"| Policy
    Policy -->|approved or no-approval-needed| Tool
    Policy -->|needs approval, not approved| Error["ToolResult(ok=False)\n'requires approval'"]
    Tool -->|SQL| DB
```

The policy rulebook answers one question for each tool: **does this need a human to approve it?**

---

## Step 3: Wrapping policy + execution in a Registry

The registry is the single enforcement point:

```mermaid
graph TD
    Agent["AI Agent (future phases)"]
    Registry["ToolRegistry\n1. check policy\n2. lookup fn\n3. execute with timeout\n4. catch exceptions"]
    PolicyRulebook["ToolPolicy\nrulebook"]
    FnMap["fn map\nname → async function"]
    Tool["Tool Function"]
    DB[("Database")]
    Result["ToolResult\nok=True / ok=False"]

    Agent -->|execute(name, args, approved)| Registry
    Registry -->|requires_approval?| PolicyRulebook
    Registry -->|lookup| FnMap
    FnMap --> Tool
    Tool -->|SQL| DB
    Registry -->|always returns| Result
```

Key properties guaranteed by the registry:
- **Tool exceptions never crash** the graph — they become `ToolResult(ok=False)`.
- **Timeouts** are enforced — no tool can block forever.
- **Unknown tools** are automatically approval-required (safe default).

---

## Step 4: The nine tools

Tools are divided into read-only (no approval needed) and write tools (some need approval).

```mermaid
graph TD
    subgraph "Read-only tools (no approval)"
        T1["get_customer\nprofile + subscription + workspace"]
        T2["get_subscription\nbilling details"]
        T3["get_ticket_history\nrecent tickets"]
        T4["search_docs\nRAG knowledge retrieval"]
        T5["check_service_status\nactive incidents"]
    end

    subgraph "Write tools"
        T6["update_ticket\nstatus · severity · category\n(no approval)"]
        T7["create_escalation\nhand to specialist team\n(no approval — it IS the safe path)"]
        T8["reset_demo_setting\nworkspace admin toggle\n⚠ ALWAYS needs approval"]
        T9["create_refund_request\nbilling refund record\n⚠ needs approval when amount > threshold"]
    end

    DB[("Database")]
    RAG["RAG Retriever"]

    T1 & T2 & T3 & T5 & T6 & T7 & T8 & T9 --> DB
    T4 --> RAG
```

---

## Step 5: Mock Integrations

The write tools interact with external systems (email, billing, notifications, storage).  
In demo/test mode, mock adapters handle these calls safely offline.

```mermaid
graph TD
    FactoryFn["Factory function\nget_email_service()\nget_refund_service()\n…"]
    DEMO{"DEMO_MODE?"}
    Mock["Mock Adapters\n• MockEmailService → logs\n• MockRefundService → fake ID\n• MockNotificationService → logs\n• MockStorageService → reads DB"]
    Real["Real Adapters\n(future: SendGrid, Stripe, …)"]
    Protocol["Integration Protocol\ninterface only"]

    FactoryFn --> DEMO
    DEMO -->|true| Mock
    DEMO -->|false| Real
    Mock & Real -.->|satisfies| Protocol
```

The rest of the application only imports the Protocol interface. It never imports `MockEmailService` directly — that is the factory's responsibility.

---

## Final state at end of Phase 6

```mermaid
graph TD
    Browser["Browser / API client"]
    FastAPI["FastAPI backend :8000\nRouters: auth · tickets · customers\nknowledge · dashboard · escalations"]
    Auth["JWT + RBAC\nPhase 3"]
    DB[("SQLite / Postgres")]
    RAG["RAG Pipeline\nPhase 5"]
    KB["Knowledge Base\n15 articles"]
    
    subgraph ToolLayer["Tool Layer (Phase 6)"]
        Registry["ToolRegistry\nsingle execution gate"]
        Policy["ToolPolicy\nrulebook"]
        ReadTools["Read-only Tools\n5 functions"]
        WriteTools["Write Tools\n4 functions\n(2 approval-gated)"]
        Integrations["Integrations\nEmail · Refund · Notify · Storage\n(mock adapters)"]
    end

    Browser -->|REST / Bearer JWT| FastAPI
    FastAPI -->|auth check| Auth
    FastAPI -->|SQL| DB
    FastAPI -->|future: will call| Registry
    Registry -->|policy check| Policy
    Registry --> ReadTools & WriteTools
    ReadTools -->|SQL| DB
    ReadTools -->|search| RAG
    RAG --> KB
    WriteTools -->|SQL| DB
    WriteTools -->|via factory| Integrations
```

The Tool Layer is fully implemented and tested.  
It is not yet wired into the workflow graph (that happens in Phase 9).  
The approval UI does not exist yet (Phase 10 and 12).

---

## Design decisions made in Phase 6

| Decision | Reason |
|---|---|
| Single ToolRegistry singleton | Agents in Phase 9 can import one object; tests can reset it |
| Policy is a plain class, not config | Easy to unit test without touching the DB or settings |
| Unknown tools require approval | New tools start safe; opt-out of approval rather than opt-in |
| Exceptions → ToolResult(ok=False) | The workflow graph must never crash because a tool failed |
| Mock adapters satisfy protocols | Tests and demos work offline; swapping to real adapters needs zero code change in callers |
| create_escalation needs no approval | Escalating is always the safe, conservative choice |
