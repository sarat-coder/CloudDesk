# Phase 6 — Tools and Policy: Plain-English Explanation

## What is Phase 6 about?

In Phase 5 we built a knowledge library — the system could look up articles.  
Phase 6 is about **actions** — the things the AI is allowed to *do* on behalf of a customer.  
More importantly, Phase 6 sets up the safety rules that decide **who must check before the AI acts**.

Think of it like this: a junior bank teller can answer your balance question on their own,  
but to issue a refund they need a manager's signature. Phase 6 builds exactly that system.

---

## The big idea: every action goes through one gate

Before Phase 6, there was nothing stopping code from doing anything — writing to the database,  
issuing refunds, changing settings — all without any check.

After Phase 6:

> **Every single thing the AI wants to do must pass through the ToolRegistry.**
> The ToolRegistry asks: "Does this action need a human to approve it first?"
> If yes and no approval has been given, the action is blocked. Period.

No shortcut exists. No tool can skip the registry. That is the guarantee.

---

## The three building blocks

### 1. ToolPolicy — the rulebook

`backend/app/tools/policy.py`

This is a simple rulebook — a list of which actions need approval and which do not.

| Action | Needs Approval? | Why |
|---|---|---|
| Look up customer info | No | Reading is safe |
| Search the knowledge base | No | Reading is safe |
| Check for active incidents | No | Reading is safe |
| Update a ticket's status | No | Low-risk bookkeeping |
| Record an escalation | No | Escalating is itself the safety path |
| Reset a workspace setting | **YES — always** | Affects the customer's admin configuration |
| Issue a refund | **YES — by default** | Real money involved |

The refund rule is smart: you can configure a threshold. For example, "auto-approve refunds under $10 but require a human for anything larger."

A key rule: **any unknown future tool also requires approval by default.** New tools start safe.

---

### 2. ToolRegistry — the enforcer

`backend/app/tools/registry.py`

This is where the rulebook becomes action.  

When an agent wants to run a tool, it calls:  
`registry.execute("create_refund_request", {amount: 50}, approved=False)`

The registry then:
1. Looks up the policy for that tool.
2. If approval is required but not given → returns an error (never crashes, just says "not allowed").
3. If the tool does not exist → returns an error.
4. If everything is OK → runs the tool, with a time limit (e.g. 30 seconds).
5. If the tool throws an exception → catches it and returns a safe error message.

The agent (AI) never sees an exception. It always gets back a clear result: success or failure with a reason.

---

### 3. The Tools themselves

There are nine tools total, split into two files:

**Read-only tools** (`support_tools.py`) — no approval needed:
- `get_customer` — load the customer's profile, subscription, and workspace in one call
- `get_subscription` — billing plan details
- `get_ticket_history` — past tickets for the customer
- `search_docs` — search the knowledge base (from Phase 5)
- `check_service_status` — are there any active incidents affecting the customer?

**Write tools** (`write_tools.py`):
- `update_ticket` — change ticket status, severity, category (no approval needed)
- `create_escalation` — hand the ticket to a specialist team (no approval needed)
- `reset_demo_setting` — change a workspace admin toggle (**approval required**)
- `create_refund_request` — log a refund in the billing system (**approval required**)

---

## Mock Integrations — faking the outside world

`integrations/protocols.py`, `integrations/mock/services.py`, `integrations/factory.py`

CloudDesk needs to talk to external systems: an email service, a billing/refund provider, a notification system, a storage provider.

In a real company those are paid third-party services.  
For demos and tests we do not want to call them — so we built **mock (fake) versions**.

The mock email service writes "I would have sent this email" to the log.  
The mock refund service returns a fake refund ID without touching any payment system.

The **factory** decides which version to use:
- `DEMO_MODE=true` → use mocks (safe, offline, free)
- Real credentials provided → switch to real adapters (not built yet — the hooks are there)

This pattern is called **dependency injection via protocols**: the rest of the system only knows "give me something that can send email" — it never cares whether that is SendGrid or a log message.

---

## A concrete example: CD-1002 (the refund ticket)

A customer says "I was charged for 8 seats but only use 5."

1. The AI looks up the customer — `get_customer` runs fine, no approval needed.
2. It searches the knowledge base — `search_docs` runs fine, no approval needed.
3. It decides to issue a partial refund and calls `create_refund_request` with `amount=150`.
4. The registry checks the policy: **refunds always need approval (amount > $0)**.
5. The registry blocks the action and returns: *"requires human approval"*.
6. The workflow pauses and asks the support agent to review.
7. The agent clicks Approve.
8. The same `create_refund_request` call runs again, now with `approved=True`.
9. The refund is recorded — and the mock refund service logs what it would do in production.

**No money ever moves without a human seeing it first.** That is the Phase 6 guarantee.

---

## What this phase did NOT build (intentionally)

- The workflow graph that calls these tools — that is Phase 9.
- The approval UI for the agent — that is Phase 10 and 12.
- Real email/refund providers — those need production credentials.

Phase 6 builds the foundation so that when the AI and the human interface arrive,  
the safety rails are already in place and tested.

---

## Files created in Phase 6

| File | Purpose |
|---|---|
| `backend/app/tools/__init__.py` | Package entry point |
| `backend/app/tools/policy.py` | ToolPolicy rulebook + ToolResult type |
| `backend/app/tools/registry.py` | ToolRegistry enforcer + singleton |
| `backend/app/tools/support_tools.py` | 5 read-only tool functions |
| `backend/app/tools/write_tools.py` | 4 write tool functions |
| `integrations/__init__.py` | Package entry point |
| `integrations/protocols.py` | Protocol interfaces (Email, Refund, Notification, Storage) |
| `integrations/mock/__init__.py` | Package entry point |
| `integrations/mock/services.py` | 4 offline mock adapters |
| `integrations/factory.py` | Selects mock vs. real at startup |
| `tests/unit/test_tool_policy.py` | 27 offline unit tests — all passing |

---

## One-sentence summary for non-technical readers

> Phase 6 built the safety gate: every action the AI can take is registered and checked — if it involves money or settings, a human must approve it first; if anything goes wrong, the system catches the error silently and reports it cleanly.
