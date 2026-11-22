# Phase 11 — Approval & Escalation: Plain-English Explanation

**Audience:** Interview board, including non-technical members.

---

## What Did We Build in Phase 11?

Phase 10 gave the platform its workflow skeleton — a pipeline with 13 steps. But at the end of Phase 10, the pipeline had no ability to **pause and wait for a human**, no ability to **send cases to specialist teams**, and no ability to **actually carry out the resolution actions** (refunds, setting resets, etc.). Those three capabilities are the entire focus of Phase 11.

Think of the difference this way:
- **Phase 10** built the highway and all the on-ramps.
- **Phase 11** installed the traffic lights, the emergency exits, and the actual vehicles that deliver the packages.

---

## The Three Problems Phase 11 Solves

### Problem 1 — Money cannot move without a human "yes"

If the AI decides a customer deserves a £50 refund, can the system just issue it? No. That would be an unreviewed financial transaction. We need a mechanism to **stop the entire workflow**, present the plan to a human agent, and only continue once the agent explicitly says "yes" or "no."

### Problem 2 — Sensitive cases must reach specialist teams, not just be "resolved"

If a customer reports suspicious logins or demands account deletion under GDPR, the right answer is not an automated reply — it is an escalation to the Security Team or Data Compliance Team respectively. This routing must be **deterministic and policy-driven**, not an AI guess.

### Problem 3 — After approval, the actions must actually execute

A "plan" is useless if nothing ever runs it. We need a step that takes the planned actions and fires them through the same secure "tool registry" whether they were auto-approved (safe actions) or human-approved (money/accounts).

---

## What Was Built — Five Tasks

### Task P11-1 — Human Approval Interrupt

**File:** `agents/nodes/human_approval.py`

This node does something that looks impossible: it **pauses a running computer program and waits indefinitely**. Here is how:

LangGraph provides a function called `interrupt()`. When called, it:
1. Saves the **entire state of the workflow** to a database (the checkpointer).
2. Suspends the program — no CPU, no memory, no cost while waiting.
3. Returns control to the web server, which writes `status = "waiting_on_approval"` to the ticket.

Crucially, the code **before** the interrupt creates the approval request record in the database. If a server restarts, that code runs again on resume — which is why it checks "does an approval request already exist?" before creating a new one. This is called **idempotency** — running the same step twice produces the same result, not a duplicate record.

**What the agent sees on their dashboard:** The ticket status changes from "in progress" to "waiting on approval." They see the resolution plan and two buttons: Approve and Reject.

---

### Task P11-2 — Approval Decide and Resume API

**Files:** `backend/app/api/approvals.py`, `backend/app/services/approval_service.py`

Three new API endpoints were added:

| Endpoint | What It Does |
|---|---|
| `GET /api/v1/approvals/{id}` | Read the pending approval request |
| `POST /api/v1/approvals/{id}/approve` | Record "yes" and resume the paused workflow |
| `POST /api/v1/approvals/{id}/reject` | Record "no" and route to escalation |

Both approve and reject are **agent-only** — if a viewer tries to approve, they get a 403 Forbidden response. This is enforced by `require_role("agent")` on those routes.

**What happens when the agent clicks "Approve":**

1. The API updates the `approval_requests` row: `status = "approved"`, records who approved and when.
2. It calls `approval_service.decide()`.
3. That service function calls `resume_workflow()`.
4. `resume_workflow()` loads the saved graph state from the checkpointer and **continues from exactly the step it paused at**, passing the approval decision.
5. The workflow picks up at execute_resolution and completes normally.

**What happens if the agent clicks "Reject":**

The workflow resumes with `approved = False`. The routing function `_route_after_human_approval()` sends the ticket to the escalation node instead of execute_resolution. The plan is abandoned; a human specialist team takes over.

**Race condition protection:** If two agents try to approve the same request at the same time, the second one gets a 409 Conflict error — the system detects that the approval is "already approved" and refuses the duplicate.

---

### Task P11-3 — Escalation Routing

**Files:** `agents/nodes/escalation_check.py`, `agents/nodes/escalation.py`, `agents/graph.py`

Escalation has two parts:

**Part A — the check (escalation_check node):** Runs the EscalationAgent, which applies policy rules first. For six specific ticket types, the escalation decision is hardcoded:

| Ticket type | Routes to |
|---|---|
| Suspicious logins / possible breach | Security Team |
| Files disappeared / data loss | Data Recovery Team |
| Payment dispute / chargeback | Billing Disputes Team |
| GDPR erasure / account deletion | Data Compliance Team |
| Legal or regulatory mention | Legal Team |
| Enterprise-wide outage | Enterprise Support Team |

The AI is consulted only for tickets that do not match any of these patterns.

**Part B — the execution (escalation node):** Creates an `escalation` record in the database with the team name, reason, and priority. Updates the ticket status to `escalated`. This is a **safe path** — it does not require human approval because escalation is a conservative action that protects the customer, not one that risks their money.

**The routing logic in the graph** (`_route_after_risk` in `graph.py`):
1. If `escalation_decision.escalation_required` is True → go to `escalation`
2. Else if any planned action `requires_approval` → go to `human_approval`
3. Otherwise → go to `execute_resolution` directly

This three-way fork is the most important branching point in the entire workflow.

---

### Task P11-4 — Execute Resolution on the Shared Tool Path

**File:** `agents/nodes/execute_resolution.py`

This node carries out the actions planned by the Resolution Agent. The key design decision: **it uses the same ToolRegistry code path regardless of whether approval was given by a human or the action was auto-approved.**

For each planned action:
1. Check whether it `requires_approval`. If yes, use the `approved` flag set by the human_approval node. If no, treat it as approved automatically.
2. Call `registry.execute(name, args, approved=…)`.
3. Persist the outcome as a `ResolutionAction` row in the database.
4. If the tool call failed, add the error to the error list — but do not crash the workflow.

**Why the shared path matters:** A refund that a human approved should behave identically to an automatic update. Having one code path means there is nothing special to audit about approved actions — the same log format, the same database record, the same error handling applies in every case.

---

### Task P11-5 — Demo Script

**File:** `scripts/demo.py`

A terminal-based script that demonstrates two end-to-end scenarios:

- **CD-1002** (Refund request): Shows the full approve path — workflow runs, pauses for approval, the script prompts the user to press Enter (simulating the agent clicking Approve), the workflow resumes and completes.
- **CD-1005** (Suspicious logins): Shows the auto-escalation path — no pause, no approval needed; the security rule fires and the ticket is immediately escalated to the Security Team.

This script is the **live smoke test** that proves every part of the platform works together end-to-end, without a UI. Run it with `make demo` or `make demo TICKET=CD-1005`.

---

## The Interrupt-Resume Pattern: A Human Analogy

Imagine a bank cashier who needs supervisor approval for a large withdrawal:

1. The customer hands over the withdrawal slip (ticket arrives).
2. The cashier fills in the form, checks the account, verifies identity — all the standard steps (nodes 1–8).
3. The cashier sees the amount exceeds their limit. They **stop**, write "awaiting supervisor" on the form, put it in the pending tray, and go help the next customer.
4. The supervisor finds the form in the pending tray, reviews it, stamps "APPROVED."
5. The cashier picks up the form, sees the stamp, and continues from exactly step 9.

The **pending tray** in our system is the checkpointer database. The **stamp** is the `Command(resume={"approved": true, "decided_by": "sam.agent"})` passed through the API.

---

## What Was Tested

All tests pass offline (no real AI, no real database beyond SQLite):

| Test | What it proves |
|---|---|
| `test_pause_on_approval_required_action` | A ticket with a refund action pauses at human_approval |
| `test_approval_routes_to_execute_resolution` | Approving resumes and completes normally |
| `test_rejection_routes_to_escalation` | Rejecting routes to the escalation node |
| `test_security_auto_escalation` | CD-1005 triggers security rule; human_approval never called |
| `test_gdpr_policy_escalation` | CD-1009 triggers data compliance rule |
| `test_409_on_duplicate_run` | A second run attempt on a waiting ticket returns 409 |
| `test_viewer_cannot_approve` | Viewer gets 403 on approve/reject endpoints |
| `test_execute_resolution_runs_all_actions` | Each planned action produces a ResolutionAction row |
| `test_demo_cd1002_end_to_end` | Full approve path completes without errors |

---

## In One Sentence

> Phase 11 adds the three things that make the pipeline production-safe: a human approval gate that pauses the workflow for money-touching decisions, a rules-based escalation engine that routes sensitive cases to specialist teams, and an execution step that reliably carries out the resolution plan — all audited, all reversible, all tested offline.
