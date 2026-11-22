# Phase 7 — Infrastructure and Component Wiring: Rules and Guardrails

## Overview

Phase 7 introduces no new network services, containers, or databases.  
Its contribution is entirely **in-process logic** — pure Python modules that sit
between the incoming request and the AI call. No new ports are opened, no new
volumes are mounted, and no external services are called.

This makes Phase 7 the lightest infrastructure phase of the entire build.

---

## Component wiring: where the new code lives

```mermaid
flowchart TD
    subgraph Container["backend container (:8000)"]
        subgraph FastAPI["FastAPI process"]
            MW["Middleware stack\n(CORS → RequestId → RateLimit → Audit)"]
            API["api/ routers"]
            SVC["services/"]
            subgraph NEW["Phase 7 — new in-process modules"]
                GRD["core/guardrails.py\nscan_for_injection\nvalidate_customer_output\nscrub"]
                RUL["agents/rules.py\nrule_category\nrule_severity\nESCALATION_RULES\nmatching_escalation_rules"]
                PRO["agents/prompts.py\nSECURITY_PREAMBLE\nwrap_untrusted"]
            end
            TOOLS["tools/ — Phase 6"]
            RAG["rag/ — Phase 5"]
        end
    end

    HTTP[HTTP request] --> MW --> API --> SVC
    SVC --> GRD
    SVC --> RUL
    SVC --> PRO
    SVC --> TOOLS
    SVC --> RAG
```

All three new modules are plain Python — they are imported directly by the service
layer. They have zero runtime dependencies (no HTTP calls, no database reads, no
external processes).

---

## Call-time flow: rules and guardrails in a ticket run

```mermaid
sequenceDiagram
    participant CLI as Client (browser or API)
    participant FW as FastAPI
    participant GRD as guardrails.py
    participant RUL as rules.py
    participant PRO as prompts.py
    participant AI as LLM (Phase 8+)
    participant TOOLS as ToolRegistry

    CLI->>FW: POST /tickets/{id}/run
    FW->>GRD: scan_for_injection(ticket.body)
    GRD-->>FW: injected=True/False + risk flag

    FW->>RUL: rule_category(text)
    RUL-->>FW: Category or None

    FW->>RUL: rule_severity(text, model_severity)
    RUL-->>FW: Final severity (never lower)

    FW->>RUL: matching_escalation_rules(text)
    RUL-->>FW: [] or [matched rules with team names]

    alt Policy escalation matched
        FW-->>CLI: escalate immediately — no AI call
    else Grey area
        FW->>PRO: wrap_untrusted(ticket.body)
        PRO-->>FW: <untrusted_content>...</untrusted_content>
        FW->>AI: SECURITY_PREAMBLE + prompt + wrapped text
        AI-->>FW: draft reply
        FW->>GRD: validate_customer_output(reply)
        GRD-->>FW: valid=True/False
        FW->>GRD: scrub(memory_note)
        GRD-->>FW: clean note
        FW-->>CLI: safe reply
    end
```

---

## Module dependency map

```mermaid
flowchart LR
    subgraph agents["agents/ package"]
        RUL["rules.py"] -->|imports| SCH["app.schemas.common\nCategory, Severity"]
        PRO["prompts.py"]
    end

    subgraph core["backend/app/core/"]
        GRD["guardrails.py"] -->|stdlib only| RE["re (stdlib)"]
    end

    agents -.->|used by Phase 8+| SPEC["agents/specialists/"]
    core -.->|used by Phase 8+| SPEC
```

Key observation: `guardrails.py` has zero application imports — it only uses Python's
built-in `re` module. `rules.py` imports only the `Category` and `Severity` enums
from `app.schemas.common`. Both modules are therefore testable with no database,
no Redis, no LLM — which is why the 58 Phase 7 tests run in under 0.5 seconds.

---

## No infrastructure changes

| Component | Phase 7 change |
|---|---|
| `backend` container | None — same image, same port |
| `frontend` container | None |
| `redis` | None |
| `qdrant` | None |
| `PostgreSQL / SQLite` | None |
| Docker Compose | None |
| `.env` / `.env.example` | None — no new env vars |

---

## Test isolation

Phase 7 tests run with the same offline harness as all prior phases:

```mermaid
flowchart LR
    subgraph conftest["tests/conftest.py"]
        ENV["os.environ:\nDEMO_MODE=true\nLLM_PROVIDER=fake\nVECTOR_STORE=memory\nUSE_FAKE_REDIS=true"]
    end

    ENV --> T1["test_rules.py\n(29 tests)"]
    ENV --> T2["test_guardrails.py\n(29 tests)"]

    T1 -->|imports| RUL["agents/rules.py"]
    T2 -->|imports| GRD["core/guardrails.py"]

    RUL -.->|no I/O| PASS
    GRD -.->|no I/O| PASS
```

No network, no file system, no database. The rules and guardrails are pure logic,
so they run identically in CI, in a Docker container, and on a developer laptop
with no credentials configured.

---

## Security posture added by Phase 7

```mermaid
flowchart TD
    TICKET[Incoming ticket text]

    TICKET --> L1["Layer 1: scan_for_injection\nDetect malicious patterns in text"]
    L1 -->|injected| FLAG["Flag ticket — risk=high\nwrap with untrusted tags"]
    L1 -->|clean| L2["Layer 2: rule_category + rule_severity\nClassify and triage without AI"]

    FLAG --> L2

    L2 --> L3["Layer 3: matching_escalation_rules\nPolicy decision before AI call"]
    L3 -->|matched| ESC["Escalate — no AI discretion"]
    L3 -->|no match| AI["Phase 8: AI agents with SECURITY_PREAMBLE"]

    AI --> L4["Layer 4: validate_customer_output\nBlock internal URLs and secrets from reply"]
    L4 -->|blocked| RISK["Raise risk to high — no reply sent"]
    L4 -->|valid| REPLY["Reply shown to customer"]

    REPLY --> L5["Layer 5: scrub\nRemove secrets before memory write"]
    L5 --> MEM["customer_memory — clean notes only"]
```

Five layers, all deterministic, all running before or after the AI — never relying on
the AI to enforce them.
