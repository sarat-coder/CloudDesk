# Phase 9 — Infrastructure & Component Wiring: Specialist Agents

## Overview

Phase 9 adds the agent layer — six specialist Python classes — that sit **between** the FastAPI API layer and the tool/RAG/memory layers built in earlier phases. No new infrastructure services were added. The agents run inside the same FastAPI process as background tasks.

---

## Component Map After Phase 9

```mermaid
graph TB
    subgraph Browser
        UI[Next.js Frontend\n:3000]
    end
    subgraph FastAPI Process :8000
        API[API Layer\napi/tickets.py]
        AGENTS[Specialist Agents\nagents/specialists/]
        TOOLS[Tool Registry\napp/tools/registry.py]
        RULES[Rules + Guardrails\nagents/rules.py\napp/core/guardrails.py]
        LLM_FACTORY[LLM Factory\napp/core/llm.py]
        MEMORY[Memory Service\nmemory/memory_service.py]
        RAG[RAG Retriever\nrag/retriever.py]
    end
    subgraph Data Stores
        DB[(SQLite / Postgres)]
        REDIS[(Redis / fakeredis)]
        VECTOR[(In-memory / Qdrant)]
    end
    subgraph External
        LLM_API[LLM API\nOpenAI / Anthropic\nor Fake in demo mode]
    end

    UI -->|REST + Bearer JWT| API
    API --> AGENTS
    AGENTS --> TOOLS
    AGENTS --> RULES
    AGENTS --> LLM_FACTORY
    AGENTS --> MEMORY
    TOOLS --> RAG
    RAG --> VECTOR
    MEMORY --> REDIS
    MEMORY --> DB
    TOOLS --> DB
    LLM_FACTORY -->|only when LLM_PROVIDER != fake| LLM_API
```

---

## How an Agent Call Flows Through the System

```mermaid
sequenceDiagram
    participant API as FastAPI Route
    participant SUP as SupervisorAgent
    participant RULES as rules.py + guardrails.py
    participant LLM as call_structured\n(llm.py)
    participant FAKE as FakeProvider\n(offline)

    API->>SUP: understand_ticket(subject, body)
    SUP->>RULES: scan_for_injection(text)
    RULES-->>SUP: injection_flagged=False
    SUP->>RULES: rule_category(text)
    RULES-->>SUP: no match
    SUP->>LLM: call_structured(Classification, messages)
    LLM->>FAKE: _fake_response(Classification)
    FAKE-->>LLM: Classification(category=OTHER, summary="")
    LLM-->>SUP: (result, usage, ms, calls)
    SUP->>RULES: rule_severity(text, model_severity)
    RULES-->>SUP: severity (can only raise)
    SUP-->>API: (Classification, injection_flagged, usage, ms, calls)
```

---

## Agent Internal Architecture

Each specialist agent follows the same pattern:

```mermaid
classDiagram
    class SpecialistAgent {
        +async run(...) tuple
        -_build_prompt(...) list[dict]
        -_call_tools(...) list[ToolResult]
    }
    class ToolRegistry {
        +async execute(name, args, approved) ToolResult
    }
    class call_structured {
        +async call(ResponseModel, messages) tuple
    }
    class Rules {
        +deterministic_check(...) result
    }

    SpecialistAgent --> ToolRegistry : tool calls
    SpecialistAgent --> call_structured : LLM calls
    SpecialistAgent --> Rules : policy checks
```

The key constraint: **every tool call goes through ToolRegistry** — agents cannot call tools directly. ToolRegistry enforces approval gates, timeouts, and audit logging.

---

## LLM Factory: Provider Abstraction

```mermaid
graph LR
    A[call_structured\napp/core/llm.py] -->|reads env| B{LLM_PROVIDER}
    B -->|fake| C[_FakeProvider\nno network calls\nreturns deterministic Pydantic models\ncost = 0.0]
    B -->|openai| D[OpenAI Chat Completions\nstructured output mode]
    B -->|anthropic| E[Anthropic Messages API\nJSON tool-use mode]
    C --> F[tuple: result, usage_dict, duration_ms, tool_calls]
    D --> F
    E --> F
```

All agents call `call_structured()` and receive the same 4-tuple regardless of which LLM provider is configured. The agents have zero provider-specific code.

---

## Rules and Guardrails Layer

```mermaid
graph TD
    subgraph agents/rules.py
        RC[rule_category\nkeyword match → Category]
        RS[rule_severity\nrules can only raise, never lower]
        RE[matching_escalation_rules\npolicy dict: text match → team]
    end
    subgraph app/core/guardrails.py
        SI[scan_for_injection\npattern-based flag]
        WU[wrap_untrusted\nwraps in XML-like delimiters]
        VC[validate_customer_output\nblocks secrets, internal URLs, other-customer data]
        SC[scrub\nstrips PII patterns before memory write]
    end

    SupervisorAgent --> RC
    SupervisorAgent --> RS
    SupervisorAgent --> SI
    SupervisorAgent --> WU
    EscalationAgent --> RE
    ResolutionAgent --> VC
    MemoryService --> SC
```

The rules and guardrails layer is **always deterministic** — no LLM calls, no randomness. It can be unit-tested in isolation with simple string inputs.

---

## Memory Integration in Phase 9

```mermaid
sequenceDiagram
    participant CUST as CustomerAgent
    participant MEM as memory_service.py
    participant REDIS as Redis (short-term)
    participant DB as PostgreSQL/SQLite (long-term)

    CUST->>MEM: recall_customer(customer_id, session)
    MEM->>DB: SELECT customer_memory WHERE customer_id = ?
    DB-->>MEM: list of CustomerMemory rows (max 10)
    MEM-->>CUST: list of dicts {type, content}
    Note over CUST: memory_notes attached to CustomerContext
```

CustomerAgent reads memory; it does **not** write. Writing happens in the `memory_update` node that runs at the very end of the workflow (Phase 10).

---

## RAG Integration in Phase 9

```mermaid
sequenceDiagram
    participant KNOW as KnowledgeAgent
    participant REG as ToolRegistry
    participant TOOL as search_docs\napp/tools/support_tools.py
    participant RET as rag/retriever.py
    participant VS as VectorStore\n(memory or Qdrant)

    KNOW->>REG: execute("search_docs", {query, category, top_k, mode})
    REG->>TOOL: search_docs(query, category, top_k, mode)
    TOOL->>RET: get_retriever() → retrieve(query, ...)
    RET->>VS: semantic search + BM25 keyword search
    VS-->>RET: candidate chunks
    RET->>RET: reciprocal rank fusion + rerank
    RET-->>TOOL: list of evidence dicts
    TOOL-->>REG: ToolResult(ok=True, data={evidence: [...]})
    REG-->>KNOW: ToolResult
```

In tests, the retriever is not initialised, so `search_docs` returns `ToolResult(ok=False)`. KnowledgeAgent handles this gracefully by returning an empty evidence list.

---

## Docker / Deployment Impact

Phase 9 adds no new containers or environment variables. The agents are Python classes instantiated at request time — stateless, no persistent resources, no additional ports.

```mermaid
graph LR
    subgraph docker-compose.yml unchanged
        FE[frontend\n:3000]
        BE[backend\n:8000\nFastAPI + Agents]
        REDIS[redis\n:6379]
        QDRANT[qdrant\n:6333]
    end
    FE --> BE
    BE --> REDIS
    BE --> QDRANT
```

The only file-level impact is in `backend/` and `agents/` — no Dockerfile changes, no compose changes, no new environment variables required. `LLM_PROVIDER=fake` (the default) means the backend starts and processes tickets with no API key configured.
