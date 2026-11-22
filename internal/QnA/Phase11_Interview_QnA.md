# Phase 11 — Interview Q&A: Approval & Escalation

**Audience:** Interview board (technical and non-technical members).

---

## Architecture Questions

### Q: What is the "human approval gate" and why is it necessary?

**A:** The human approval gate is a mechanism that completely pauses the AI workflow when it detects that the resolution plan contains an action that could cost money or change an account — specifically refunds, security setting resets, or account deletions. It is necessary because:

1. **Financial risk** — an AI issuing refunds without oversight is a financial control failure.
2. **Compliance** — payment processors and audit requirements often mandate human review for refunds above a threshold.
3. **Trust** — agents on the platform need to feel in control; they should never discover a refund happened without their knowledge.

The gate does not slow down low-risk tickets — only tickets with approval-required actions are paused.

---

### Q: How does LangGraph's `interrupt()` work?

**A:** `interrupt()` is a function provided by LangGraph. When called inside a node:

1. The entire workflow state (all outputs from all previous nodes) is serialised and written to the checkpointer database.
2. The current function call returns immediately — the graph stops executing.
3. Control returns to the calling code (our workflow service), which records the "waiting on approval" status.
4. When a human later calls the approve or reject API, the system calls `graph.astream(Command(resume=...))` with the same thread ID.
5. LangGraph loads the saved state from the checkpointer and re-enters the `human_approval` node from the point just after `interrupt()`.

The key insight: **the workflow does not hold any memory, CPU, or network resources while waiting**. It is completely dormant between pause and resume, like a saved game.

---

### Q: What is "idempotency" and why does it matter at the interrupt point?

**A:** Idempotency means that running the same operation twice produces the same result as running it once. It matters at the interrupt point because LangGraph's design guarantees that code **before** `interrupt()` may run more than once — for example if the server restarts between the interrupt being called and the state being saved.

In our `human_approval` node, the code before `interrupt()` checks: "does an `approval_requests` row already exist for this run?" If yes, it reuses the existing one. If no, it creates a new one. This prevents creating duplicate approval requests if the node re-executes.

Without this check, a server restart during the pause could create two approval records, leaving the system in an inconsistent state.

---

### Q: What is the three-way routing decision after `risk_check`?

**A:** The `_route_after_risk()` function in `graph.py` makes a deterministic three-way choice:

1. **Escalation path** — if `escalation_decision.escalation_required == True` (a policy rule fired)
2. **Approval path** — if any planned action has `requires_approval == True`
3. **Auto-resolution path** — if neither of the above is true

This function reads from the workflow state and makes no AI calls. The routing logic is transparent, testable, and auditable — a developer can read exactly why a ticket went to one path and not another.

---

### Q: What is the difference between `escalation_check` and the `escalation` node?

**A:** These are two separate nodes with different responsibilities:

- **`escalation_check`** is an **AI-aware decision node** — it runs the EscalationAgent, which applies policy rules first and then optionally asks the LLM whether escalation is warranted in grey areas. It **decides** whether to escalate.
- **`escalation`** is a **write node** — it creates the `Escalation` database record, routes to the named team, and updates the ticket status to `escalated`. It **executes** the escalation decision.

Keeping them separate means: (1) the escalation write can be triggered from two paths (policy escalation and human rejection), (2) the AI check can be skipped in tests, and (3) each node has a single, clear responsibility.

---

### Q: Why can the `escalation` node be reached from two different paths?

**A:** The escalation node can be reached from:
1. `risk_check` — when a policy rule (security breach, GDPR, data loss, etc.) fires and `escalation_required = True`.
2. `human_approval` — when an agent reviews the plan and clicks "Reject."

Both paths are legitimate escalation scenarios. The node's code does not care which path triggered it — it creates an `Escalation` record either way. This avoids duplicating the write logic.

---

## Security and RBAC Questions

### Q: How does RBAC prevent a viewer from approving?

**A:** The approve and reject endpoints use `require_role("agent")` as a FastAPI dependency. This is a function that:

1. Reads the `Authorization: Bearer <token>` header.
2. Decodes the JWT and extracts the user's role.
3. If the role is below "agent" (i.e., "viewer"), raises `HTTPException(403, "Insufficient permissions")`.
4. The FastAPI framework returns the 403 response without ever calling the service layer.

A viewer cannot approve even if they know the approval ID. This is enforced server-side — the client cannot bypass it by modifying the request.

---

### Q: What prevents two agents from approving the same request simultaneously?

**A:** The `approval_service.decide()` function reads the approval status from the database and checks whether it is still `"pending"`. If the status is anything other than `"pending"`, it raises a `ValueError("already approved/rejected")`, which the API layer translates to an HTTP 409 Conflict.

This works because:
- The status check and the status update are in the same database transaction.
- SQLite and PostgreSQL both guarantee that only one transaction can hold a write lock at a time.

The practical result: the first agent's click succeeds; the second agent's click returns a 409 error with a clear message.

---

### Q: Why does `execute_resolution` treat approved and auto-approved actions identically?

**A:** Because `ToolRegistry.execute(name, args, approved=…)` is the single enforcement point for whether a tool call is allowed. Whether `approved=True` came from a human clicking "Approve" or from the auto-path (action did not require approval), the registry applies the same logic:

- If `approved=False` and the tool requires approval → return `ToolResult(ok=False, error="not approved")`
- Otherwise → execute the tool

There is no "fast lane" that skips policy enforcement for pre-approved actions. This means: a bug in the routing logic cannot accidentally execute a gated action without a record — the registry would catch it.

---

## Workflow and State Questions

### Q: What happens if the server restarts while a workflow is waiting for approval?

**A:** Nothing is lost. The state was checkpointed before the interrupt. When the agent clicks "Approve":

1. The API reads the `run_id` from the `approval_requests` table (which was written before the interrupt).
2. It calls `resume_workflow(run_id, approved=True, decided_by=...)`.
3. LangGraph loads the full `SupportState` from `data/checkpoints.db`.
4. The graph continues from the interrupt point with the full state restored.

The only requirement is that the checkpointer database persists across restarts. In production, `CHECKPOINT_DB_PATH` points to a persistent file or a database, not `:memory:`.

---

### Q: How does the approve API know which workflow to resume?

**A:** The `approval_requests` table has a `run_id` column that links the approval to the `workflow_runs` row. The LangGraph checkpointer uses `run_id` as the `thread_id` — the key that identifies which saved state to load. So the resume chain is:

```
POST /approvals/{approval_id}/approve
  → read approval_requests WHERE id=approval_id → get run_id
  → update approval status
  → resume_workflow(run_id=...)
      → graph.astream(Command(resume=...), config={"configurable": {"thread_id": run_id}})
          → LangGraph loads state from checkpointer WHERE thread_id=run_id
          → continues from interrupt point
```

---

### Q: What does the `_approval_decision` key in the state mean?

**A:** `_approval_decision` is a state key set by the `human_approval` node after the interrupt resumes. It holds the boolean value from the agent's decision (`True` for approved, `False` for rejected). The `_route_after_human_approval()` function reads this key to decide whether to go to `execute_resolution` or `escalation`.

The leading underscore is a naming convention meaning "this key is an internal signal, not a business output" — it is not shown to the user and not included in the resolution plan.

---

### Q: What is `ResolutionAction` and why does it exist?

**A:** `ResolutionAction` is a database table that records every tool call made by the `execute_resolution` node. Each row captures:
- Which tool was called (e.g., `create_refund_request`)
- What arguments were passed (e.g., `{amount: 50, ticket_id: "CD-1002"}`)
- Whether it succeeded or failed
- The timestamp

This table serves as the **audit trail for consequential actions**. If a manager later asks "did a refund go out for ticket CD-1002?", the answer is in `resolution_actions`, not in a log file. It is queryable, structured, and permanent.

---

## Demo and Testing Questions

### Q: What does `make demo` demonstrate?

**A:** The demo script (`scripts/demo.py`) runs two scenarios:

1. **CD-1002 (Refund ticket):** Starts the workflow, polls until it reaches `waiting_on_approval`, prompts the user to press Enter (simulating the agent approving), resumes the workflow, and prints the final resolution including the refund action result.

2. **CD-1005 (Security breach ticket):** Starts the workflow, polls until it reaches `escalated`, and prints the escalation details (team = "Security Team", no approval gate was ever reached).

The script uses the HTTP API — it calls `/run`, polls `/workflow`, reads `/approvals/{id}`, and calls `/approve`. This means it tests the entire stack end-to-end, not just individual functions.

---

### Q: How are Phase 11 features tested without a real database or real AI?

**A:** The test suite (`tests/conftest.py`) sets up:
- A temporary SQLite database (deleted after tests)
- `InMemorySaver` as the LangGraph checkpointer (`:memory:`)
- `LLM_PROVIDER=fake` — the EscalationAgent uses a deterministic fake LLM
- `USE_FAKE_REDIS=true` — in-memory Redis replacement

This means all tests run in under 10 seconds on a laptop with no network connection. Key tests:
- **Interrupt test** — asserts that after a run with an approval-required action, the workflow status is `waiting_on_approval` and an `approval_requests` row exists.
- **Resume test** — asserts that calling the approve endpoint causes the run to reach `completed`.
- **Rejection test** — asserts that calling reject causes the run to reach `escalated` and an `escalations` row exists.
- **Policy test** — asserts that CD-1005 never reaches `human_approval`; it goes directly to `escalated`.

---

### Q: What would happen if the LLM said "escalate this ticket" for a simple billing question?

**A:** The system distrusts vague model escalations. In `EscalationAgent.run()`, even if the LLM returns `escalation_required=True`, the system overrides it if:

1. No policy rule matched (the ticket is not a security breach, GDPR request, etc.)
2. AND the ticket severity is not `high` or `critical`
3. AND the model's confidence is below 70%

In that case, `escalation_required` is set to `False` and the ticket continues to the approval or auto-resolution path. This prevents "alarm fatigue" — where the system escalates everything and specialist teams stop trusting the platform.

---

## Non-Technical Questions

### Q: Can you explain the approval gate without technical terms?

**A:** Imagine a junior bank teller. They can help customers with most things — checking balances, transferring between accounts, printing statements. But if a customer asks for a large cash withdrawal, the teller cannot authorise it alone. They write up the request, hand it to their manager, and wait. The manager reviews it and either stamps "Approved" or "Denied." Only after that stamp does the teller carry out the transaction.

The AI platform works exactly the same way. For most tickets, it handles everything automatically. For refunds or account changes, it stops, writes up the request, and waits for the support agent (the manager) to decide. The agent sees the full plan, decides yes or no, and the system executes accordingly.

---

### Q: What is an escalation and why does it bypass the approval gate?

**A:** An escalation is when a support case is handed off to a specialist team because the platform determines it is too sensitive, too complex, or too risky for the standard workflow. Examples: a security breach, a GDPR erasure request, a payment dispute.

Escalation **bypasses** the approval gate because escalation is itself the safe choice — it means "we're not resolving this automatically, we're routing it to humans with the right expertise." There is nothing to approve; the whole point is that the platform is declining to act and deferring to specialists. Requiring a manager to "approve an escalation" would be counterproductive — it would create a bottleneck on the safest possible outcome.

---

### Q: What is a 409 Conflict error and when does it occur?

**A:** HTTP 409 Conflict means "I cannot process your request because it conflicts with the current state of the resource." In our system, it occurs in two places:

1. **Duplicate run:** An agent tries to start the AI workflow on a ticket that is already `waiting_on_approval`. The system refuses and says: "you cannot start a new workflow while another is paused waiting for your decision."

2. **Duplicate approval:** Two agents try to approve the same request at the same time. The first one succeeds. The second one gets 409 because the approval record is no longer `pending` — it was already decided.

Both cases protect against double-processing.
