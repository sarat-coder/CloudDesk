# Phase 13 — Ticket Workflow Screen: Plain-English Explanation

**Audience:** Interview board, including non-technical members.

---

## What Did We Build in Phase 13?

By the end of Phase 12 we had a complete web console — login, navigation, a list of tickets, customer profiles, a knowledge base browser, an escalations queue, and an audit log.

But the centrepiece of the whole product — the screen where a support agent actually *works a ticket* — was still a placeholder. The agent could see tickets in a list, but clicking one showed only basic details with no live connection to the AI workflow running in the background.

**Phase 13 completes the ticket workflow screen.** It is the bridge between the human agent in the browser and the AI pipeline running on the server.

Think of it this way:
- The AI engine (Phases 1–11) is the surgeon.
- The ticket workflow screen (Phase 13) is the operating-theatre display that lets the surgical team see exactly what the surgeon is doing, step by step, and make decisions in real time.

---

## What Was Built — Four Tasks

### Task P13-1 — Ticket Detail Layout

**What it is:**
The ticket detail screen is split into three columns side by side:

| Left column | Centre column | Right column |
|---|---|---|
| The conversation — all messages between the customer and the support team, plus a text box to write a reply | The customer's profile — their name, plan, subscription seats, and any active escalation | The AI's live work panel — progress steps, findings, and the reply it drafted |

This three-column design means an agent can read the customer's messages, see who the customer is, and watch the AI work, all without scrolling or switching tabs. It is designed for a wide monitor and uses a technique called CSS Grid to divide the screen proportionally.

**Why three columns:**
Decisions in support work require three types of information at the same time — what the customer said, who they are, and what the system found. Putting all three in one view eliminates the mental overhead of switching between screens.

---

### Task P13-2 — Workflow Steps and Polling

**The 12-step progress tracker:**

The right column shows a vertical list of 12 steps — one for each node in the AI pipeline:

```
1. Understand ticket       ✓ done (green)
2. Classify severity       ✓ done
3. Load customer           ✓ done
4. Search knowledge        ✓ done
5. Diagnose                … running (pulsing blue)
6. Plan resolution         ○ pending (grey)
7. Risk check              ○ pending
8. Escalation check        ○ pending
9. Human approval          ○ pending
10. Execute                ○ pending
11. Summarise              ○ pending
12. Update memory          ○ pending
```

**How it works (the `deriveSteps` function):**

There is a pure logic function called `deriveSteps`. It takes the AI's current status object and produces this list of twelve items, each tagged as `done`, `running`, or `pending`. The rules are:

- If the step's name appears in `completed_nodes` → it is `done` (green tick)
- If the step's name matches `current_node` → it is `running` (pulsing animation)
- Everything else is `pending` (grey circle)

This function contains no UI code — it is pure logic that takes data in and produces data out. Because of this, it can be tested without a browser.

**How the page stays live (polling):**

The browser cannot receive a notification from the server when the AI finishes a step. Instead, the ticket screen asks the server "has anything changed?" every two seconds. This is called polling. A specialist hook called `useWorkflowPolling` manages this automatically and stops polling the moment the workflow reaches a terminal state (completed, failed, or escalated), so the browser is not making unnecessary calls after the AI finishes.

---

### Task P13-3 — Approve, Reject, Reply, and Escalate Actions

The left column of the ticket screen is not just for reading — it is where agents take action.

**Four actions are available to agents and admins (viewers see none of them):**

#### 1. Send reply
The agent types a message and clicks "Send reply". The backend records it as an agent message and adds it to the ticket thread. The AI can pre-fill the text box with its suggested reply, but the agent can edit it freely before sending.

#### 2. Run AI workflow
If no workflow has run yet, a "Run AI workflow" button appears next to the reply controls. Clicking it asks the backend to start the AI pipeline for this ticket. The button disappears once the workflow is running, replaced by the live 12-step tracker.

#### 3. Approve / Reject (conditional)
When the AI has requested human approval (for example, to issue a refund), two buttons appear: **Approve** and **Reject**.

A critical rule enforced in both the UI and the backend:
- **Approve / Reject only appear when `approval_status === "pending"`** — not before, not after.
- **Viewers never see these buttons**, regardless of the approval status.

Approving tells the backend to resume the AI workflow and execute the planned action. Rejecting routes the ticket to an escalation team instead.

#### 4. Escalate
When the ticket is not already escalated or closed, and the user is an agent or admin, an **Escalate** button appears. Clicking it expands a small text area asking for the reason. The agent writes the reason and confirms. The backend records a formal escalation record and updates the ticket status to "escalated".

This manual escalate path exists for cases where the agent sees something the AI did not catch — an unusual edge case, a VIP customer, or additional context that arrived after the workflow ran.

**The two pure helper functions behind these rules:**

```
shouldShowApproveReject(approvalStatus, canAct)
  → true only when approvalStatus === "pending" AND the user is agent/admin

shouldShowEscalate(ticketStatus, canAct)
  → true only when the ticket is not escalated/closed AND user is agent/admin
```

These functions contain no UI code and are tested independently.

---

### Task P13-4 — Frontend Unit Tests

Phase 13 adds two new test files:

| Test file | What it proves |
|---|---|
| `__tests__/TicketActions.test.ts` | Approve/Reject only show for agents when approval is pending; Escalate hides for escalated/closed tickets and for viewers |

**Tests for `shouldShowApproveReject`:**
- Returns `true` when status is "pending" AND user can act ✓
- Returns `false` when user is a viewer (canAct = false) ✓
- Returns `false` when status is "not_required", "approved", or "rejected" ✓
- Returns `false` when status is null or undefined ✓

**Tests for `shouldShowEscalate`:**
- Returns `true` for active tickets (new, in_progress) when user can act ✓
- Returns `false` when ticket is already "escalated" ✓
- Returns `false` when ticket is "closed" ✓
- Returns `false` for viewers (canAct = false) ✓
- Returns `false` for null status ✓

All tests run with Vitest (a fast test runner) and do not need a running backend or browser.

---

## The Role-Aware Security Principle — Illustrated

Here is what happens when different users open ticket CD-1002 (the refund approval ticket):

| User | Sees the message thread | Sees approve/reject | Sees escalate | Can send reply |
|---|---|---|---|---|
| `vic.viewer` | Yes | **No** — canAct is false | **No** — canAct is false | **No** — composer is hidden |
| `sam.agent` | Yes | **Yes** — when approval_status is "pending" | **Yes** — ticket is not escalated | **Yes** |
| `admin@clouddesk.demo` | Yes | **Yes** | **Yes** | **Yes** |

If a viewer manually crafts a POST request to approve the action, the backend returns **403 Forbidden** regardless. The UI gate is a convenience; the backend gate is the real security.

---

## In One Sentence

> Phase 13 completes the agent console by wiring the ticket detail screen into the live AI workflow: a three-column layout with real-time 12-step polling, an AI-drafted reply the agent can edit, role-gated approve/reject buttons that appear only when an approval is genuinely pending, and a manual escalate action with a reason form — all backed by pure logic functions that are independently unit-tested.
