# Phase 9 — System Design Evolution: Specialist Agents

## Starting Point

At the beginning of Phase 9, we had a fully wired data layer (phases 1–8): a FastAPI backend, SQLite/Postgres persistence, Redis caching, a knowledge RAG pipeline, six tools with approval gating, deterministic rules and guardrails, and a short-term + long-term memory system. What we did **not** have was the agent layer — the components that reason over a ticket and produce a resolution.

---

## Step 1: Shared State and Schema Contract (P9-1)

Before writing any agent, we established the data contract they all share.

### Schemas (`backend/app/schemas/workflow.py`)

```mermaid
classDiagram
    class Classification {
        +Category category
        +str summary
    }
    class SeverityAssessment {
        +Severity severity
        +str reason
    }
    class CustomerContext {
        +str customer_id
        +str name
        +str plan
        +dict subscription
        +dict workspace
        +list ticket_history
        +list memory_notes
    }
    class Evidence {
        +str id
        +str title
        +str source
        +str snippet
        +float score
        +str url
    }
    class Diagnosis {
        +list probable_causes
        +list steps
        +list active_incidents
    }
    class PlannedAction {
        +str tool
        +dict args
        +str description
        +bool requires_approval
    }
    class ResolutionPlan {
        +str summary
        +str customer_reply
        +str internal_notes
        +list actions
    }
    class EscalationDecision {
        +bool escalation_required
        +str reason
        +str team
        +float confidence
    }
```

### State (`agents/state.py`)

```mermaid
graph TD
    A[SupportState TypedDict] --> B[ticket metadata\nticket_id, subject, body]
    A --> C[agent outputs\nclassification, diagnosis\nresolution_plan, ...]
    A --> D[reducers — append only\nerrors, completed_nodes]
    A --> E[token_usage\nmerge_usage sums across nodes]
    A --> F[flags\ninjection_flagged, risk_level]
```

The state uses Python `Annotated` reducers so `errors` and `completed_nodes` only ever grow — no node can erase another node's contributions.

---

## Step 2: Fake LLM Provider (P9-1 continued)

```mermaid
graph LR
    A[call_structured] --> B{LLM_PROVIDER env var}
    B -->|fake| C[_FakeProvider\nreturns deterministic\nvalid Pydantic models]
    B -->|openai| D[OpenAI API]
    B -->|anthropic| E[Anthropic API]
    C --> F[always returns\nusage=0, cost=0.0]
    D --> G[real tokens, real cost]
    E --> G
```

The fake provider dispatches on the response model class name and returns hardcoded but structurally valid objects. This is what makes all tests run offline.

---

## Step 3: Supervisor Agent — Classification and Severity (P9-2)

```mermaid
flowchart TD
    INPUT[ticket subject + body] --> SCAN[scan_for_injection\ncheck for prompt injection]
    SCAN -->|flagged| FLAG[injection_flagged = True\nwrap_untrusted applied]
    SCAN -->|clean| RULE_CAT[rule_category\ndeterministic keyword rules]
    FLAG --> RULE_CAT
    RULE_CAT -->|matched| RETURN_CLASS[return deterministic\nClassification]
    RULE_CAT -->|no match| LLM_CLASS[call_structured\nClassification]
    LLM_CLASS --> RETURN_CLASS
    RETURN_CLASS --> RULE_SEV[rule_severity\ncan only raise severity\nnever lower it]
    RULE_SEV --> FINAL[SeverityAssessment]
```

**Key design decision:** Rules run before the LLM for classification, and rules always win for severity. If the LLM says "medium" but the rules detect "enterprise + outage", severity becomes "critical".

---

## Step 4: Customer Agent — Pure Data Retrieval (P9-3)

```mermaid
flowchart LR
    INPUT[customer_id + ticket_id] --> TOOL1[ToolRegistry.execute\nget_customer]
    INPUT --> TOOL2[ToolRegistry.execute\nget_ticket_history]
    INPUT --> MEM[recall_customer\nmemory_service]
    TOOL1 --> CTX[CustomerContext]
    TOOL2 --> CTX
    MEM --> CTX
    CTX --> NOTE[load_errors list\npartial data OK\nnever crashes]
```

No LLM call. The agent is a pure data assembler. If the customer is not in the database, it returns a `CustomerContext` with an empty `load_errors` entry rather than crashing.

---

## Step 5: Knowledge Agent — RAG + Jaccard (P9-4)

```mermaid
flowchart TD
    INPUT[subject + body + category + ticket_history] --> SEARCH[ToolRegistry.execute\nsearch_docs\nhybrid semantic+keyword]
    SEARCH -->|ok| EVIDENCE[list of Evidence\ncited articles]
    SEARCH -->|failed| EMPTY_EV[empty evidence list]
    INPUT --> JACCARD[_similar_cases\nJaccard similarity\nthreshold 0.10]
    ticket_history --> JACCARD
    JACCARD --> CASES[list of PreviousCase]
    EVIDENCE --> OUTPUT[return evidence + cases]
    CASES --> OUTPUT
```

Jaccard similarity compares word-token sets. A score ≥ 0.10 is considered "similar". Tokenization strips punctuation and splits on underscores so "login_issue" contributes both "login" and "issue".

---

## Step 6: Troubleshooting Agent — Playbooks + AI (P9-5)

```mermaid
flowchart TD
    INPUT[subject + body + category + evidence] --> STATUS[ToolRegistry.execute\ncheck_service_status]
    INPUT --> PLAYBOOK[category-specific playbook\ne.g. login_issue → check SSO, MFA, browser]
    STATUS --> INCIDENTS[active_incidents list]
    PLAYBOOK --> PROMPT[enriched prompt\nplaybook hints + evidence snippets + incidents]
    INCIDENTS --> PROMPT
    PROMPT --> LLM[call_structured Diagnosis]
    LLM --> DIAGNOSIS[probable_causes + steps + active_incidents]
```

Playbooks are static lists of hints per category. They guide the LLM without constraining it — the LLM can still produce causes the playbook doesn't list, but it always starts from the right domain.

---

## Step 7: Resolution Agent — Deterministic Actions + LLM Prose (P9-6)

```mermaid
flowchart TD
    INPUT[all context] --> LLM[call_structured ResolutionPlan\nAI writes summary + customer_reply + notes]
    LLM --> VALIDATE[validate_customer_output\nblocks internal URLs, secrets, other customer data]
    VALIDATE -->|invalid| SAFE_REPLY[replace with generic safe reply]
    VALIDATE -->|valid| GROUND[_ground_response\ncheck reply cites at least 1 KB article]
    SAFE_REPLY --> ACTIONS
    GROUND --> ACTIONS[plan_actions — deterministic\nbased on category + customer context]
    ACTIONS --> OUTPUT[ResolutionPlan + list of PlannedAction]
```

**Most important design decision in Phase 9:** `plan_actions()` is a pure Python function with no LLM involvement. The LLM writes the words; policy decides the deeds.

---

## Step 8: Escalation Agent — Policy Rules Win (P9-7)

```mermaid
flowchart TD
    INPUT[subject + body + severity + plan] --> RULES[matching_escalation_rules\ndeterministic policy check]
    RULES -->|matched| POLICY[return policy EscalationDecision\nms=0, no LLM call]
    RULES -->|no match| LLM[call_structured EscalationDecision\nAI judgement]
    LLM --> DISTRUST{low confidence +\nnot high severity?}
    DISTRUST -->|yes| OVERRIDE[set escalation_required = False]
    DISTRUST -->|no| KEEP[keep AI decision]
    POLICY --> RISK[assess_risk\nhigh / medium / low]
    OVERRIDE --> RISK
    KEEP --> RISK
```

`assess_risk()` is a pure function: no LLM, no randomness. It returns "high" if any of these are true: injection flagged, output validation failed, escalation required, critical severity, or approval-required actions present.

---

## End State of Phase 9

```mermaid
graph TB
    subgraph agents/specialists/
        SUP[supervisor.py\nClassification + Severity]
        CUST[customer.py\nCustomerContext]
        KNOW[knowledge.py\nEvidence + PreviousCase]
        TROUBLE[troubleshooting.py\nDiagnosis]
        RES[resolution.py\nResolutionPlan + PlannedAction]
        ESC[escalation.py\nEscalationDecision + risk_level]
    end
    subgraph agents/
        STATE[state.py\nSupportState TypedDict]
    end
    subgraph backend/app/schemas/
        SCHEMAS[workflow.py\nall Pydantic models]
    end
    subgraph backend/app/core/
        LLM[llm.py\ncall_structured + FakeProvider]
    end

    SCHEMAS --> SUP
    SCHEMAS --> CUST
    SCHEMAS --> KNOW
    SCHEMAS --> TROUBLE
    SCHEMAS --> RES
    SCHEMAS --> ESC
    LLM --> SUP
    LLM --> TROUBLE
    LLM --> RES
    LLM --> ESC
    STATE --> SCHEMAS
```

**Next phase (Phase 10)** will wire these six agents into a LangGraph workflow graph. The agents themselves will not change; we will write node functions that call them and pipe state through the graph.
