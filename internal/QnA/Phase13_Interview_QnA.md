# Phase 13 — Ticket Workflow Screen: Interview Q&A

**Audience:** Technical and non-technical interviewers. Answers explain both the "what" and the "why."

---

## System Design Questions

**Q1. The ticket detail screen polls the backend every 2 seconds. Why not use WebSockets or Server-Sent Events for real-time updates instead?**

Polling was the right choice for v1 for three reasons:
1. **Simplicity** — Polling requires no persistent connection, no special server configuration, and no reconnect logic. A GET request every 2 seconds is as simple as HTTP gets.
2. **Self-terminating** — Once the workflow reaches a terminal state (completed, failed, escalated), polling stops automatically. There is no open connection to clean up.
3. **Compatible** — The FastAPI backend and Next.js frontend work correctly behind load balancers and CDNs with no sticky-session requirement. WebSockets would require the same browser and server to stay connected, complicating horizontal scaling.

WebSockets or SSE would be the natural upgrade if the product needs sub-second updates (e.g., a live chat feature), but for an AI workflow that takes 5–30 seconds, 2-second polling provides an excellent user experience with minimal infrastructure complexity.

---

**Q2. Why is `deriveSteps` a pure function separate from the React component?**

`deriveSteps` takes a `WorkflowState` object and returns a `WorkflowStep[]` array. It has no side effects, no network calls, no DOM references, and no React hooks. This means:

1. **Testability** — Any JavaScript test runner can call `deriveSteps(mockState)` and check the result. No browser, no DOM, no React rendering needed.
2. **Reliability** — Pure functions have no hidden state. The same input always produces the same output. This eliminates a whole class of "it worked yesterday" bugs.
3. **Separation of concerns** — The React component is responsible for rendering. The pure function is responsible for data transformation. Each can change independently.

If the workflow gained a 13th step tomorrow, only `deriveSteps` would need to change — not the rendering code.

---

**Q3. The page shows Approve and Reject buttons only when `approval_status === "pending"`. What happens if the agent refreshes the page after approving?**

After approving, the backend updates the approval record's status to "approved" and resumes the workflow. The next time the browser fetches the workflow state (immediately after the approval call and also via the next polling tick), `approval_status` will be "approved", not "pending". The `shouldShowApproveReject` function returns `false` for "approved", so the buttons disappear.

There is no special "refresh" logic. The UI always reflects whatever the server says. This is called **server-driven UI state** — the browser is a view, not a source of truth.

---

**Q4. What is the three-column layout trying to solve, and what are the trade-offs?**

The problem: support agents need three types of context simultaneously — the conversation, the customer's profile, and the AI's findings. A single-column design forces scroll-switching. A tabbed design loses peripheral awareness (you can't see the AI's progress while reading the conversation).

The three-column CSS Grid solves this by putting all three contexts on screen at once. The trade-off is screen width — on a narrow screen (phone, small laptop) the layout breaks. The current implementation is designed for a support agent's desktop monitor, which is the realistic use case. A responsive mobile layout would be a Phase 14+ feature.

---

**Q5. How does the manual escalate action relate to the AI's automatic escalation?**

They are different paths that produce the same outcome (a formal escalation record) but are triggered differently:

| | Automatic (AI) | Manual (Agent) |
|---|---|---|
| Triggered by | Rules in `agents/rules.py` matching policy keywords | Agent clicking the Escalate button |
| When | During the `risk_check` or `escalation` node | After workflow completes or any time |
| Team assignment | Rules assign a named team (e.g., "security_team") | Agent provides a reason; backend assigns a default team |
| Scope | Specific to the ticket's content (security breach, GDPR, etc.) | Any reason the agent deems appropriate |

The manual escalation exists as a safety valve. Policy rules catch the known cases; agents catch the edge cases the rules don't anticipate.

---

## Security and Role Questions

**Q6. The UI hides the Approve button for viewers. Is that actually secure?**

The UI hiding is a **convenience gate**, not a security gate. It makes the product feel correct to use and prevents accidental clicks. The actual security is enforced at the backend:

- The `POST /approvals/{id}/approve` endpoint calls `require_role("agent")` before doing anything.
- If a viewer's JWT reaches that endpoint, the backend returns `403 Forbidden`.
- The viewer's JWT carries the role claim; the backend verifies it on every request.

If a viewer somehow bypassed the UI (opened the browser console, crafted a manual fetch), the backend would still reject them. The UI gate + backend gate together provide defence in depth.

---

**Q7. Why is the JWT stored in `localStorage` rather than a secure cookie?**

For the demo platform, `localStorage` was chosen for simplicity — it is easy to read, write, and clear from JavaScript without special server configuration.

The trade-off is XSS exposure: a cross-site scripting attack could read a `localStorage` token. A `HttpOnly` cookie cannot be read by JavaScript and is therefore safer. For a production deployment, the architecture would migrate to `HttpOnly` cookies set by the backend auth endpoint, which removes the token from JavaScript's reach entirely. This is noted as a production hardening item, not a demo concern.

---

**Q8. A viewer logs in and opens ticket CD-1002 (the refund approval). What exactly do they see and not see?**

What they see:
- The full message thread (the customer's original message and any replies)
- The customer panel (name, plan, subscription details, escalation status)
- The workflow panel with all 12 steps (progress, classification, diagnosis, evidence, resolution plan)
- The token usage and cost estimate

What they do NOT see:
- The reply text area and "Send reply" button (the entire composer is hidden when `canAct === false`)
- The "Run AI workflow" button
- The Approve / Reject buttons (the `shouldShowApproveReject` helper returns false when `canAct` is false)
- The Escalate button

The viewer has full observability but zero ability to act. This matches the role definition: viewers read tickets for oversight, not to resolve them.

---

## Testing Questions

**Q9. Why test `shouldShowApproveReject` and `shouldShowEscalate` as pure functions rather than rendering the whole TicketDetailPage?**

Rendering the full `TicketDetailPage` requires:
- Mocking the `useParams` hook (Next.js router)
- Mocking `localStorage` (auth state)
- Mocking every API call (`tickets.get`, `tickets.workflow`, etc.)
- Wrapping in the full Next.js app context

This is 50–100 lines of setup for every test, and it tests React rendering behaviour more than it tests business logic. By extracting the conditional logic into pure functions, the tests are:
- 3–5 lines each
- No mocking needed
- Run in under 1 millisecond
- Readable as documentation of the business rules

Both approaches are valid; the pure-function approach is simply faster to write and faster to run.

---

**Q10. The `WorkflowSteps.test.ts` file tests `deriveSteps`. What are the most important test cases and why?**

| Test case | Why it matters |
|---|---|
| `deriveSteps(null)` returns 12 steps all pending | The page renders before the workflow starts. Without this, the UI would crash on a fresh ticket. |
| Completed nodes are marked `done` | The core rendering logic. If this breaks, agents see wrong step states. |
| `current_node` is marked `running` | The pulsing animation. If this breaks, agents don't know which step is active. |
| All steps `done` when `status === "completed"` | The final state. If the last step shows pending after completion, agents think the workflow is still running. |

These four cases cover the full lifecycle: not started → in progress → done. Any regression in `deriveSteps` would immediately fail at least one of them.

---

## Architecture Questions

**Q11. The ticket detail page imports `shouldShowApproveReject` from `hooks.ts`. Why are these helpers in `hooks.ts` rather than a separate `utils.ts`?**

Pragmatism. The helpers are closely related to the other hook exports (`useAuth`, `useWorkflowPolling`, `deriveSteps`) — they are all part of the same "what does this page know about the current state?" concern. A separate `utils.ts` would add a file without meaningfully separating concerns at this scale.

If the codebase grew to 20+ shared utilities, extracting them would be worthwhile. For a focused domain module with 5 exports, one file is cleaner.

---

**Q12. What would break if someone removed the `shouldShowEscalate` check and always showed the Escalate button?**

Three things would break:
1. **Agents could try to escalate an already-escalated ticket** — the backend would likely throw a 409 or create a duplicate escalation record.
2. **Agents could escalate a closed ticket** — which should be a terminal state. This would require handling in the backend to reject it gracefully.
3. **The test suite would fail** — `shouldShowEscalate("escalated", true)` returns `false` by design. Any test asserting this behaviour would catch the regression.

The function is the single place that encodes the "you cannot escalate an already-escalated ticket" rule. Because it is tested, any change to that rule is immediately visible in the diff.

---

## Product and Process Questions

**Q13. Why does the escalate form ask for a reason before confirming?**

Intentional friction. Escalating a ticket moves it out of the agent's queue and into a specialist team's queue. That team has limited capacity. An accidental escalation wastes a specialist's time and potentially delays the resolution for other customers.

The reason form serves two purposes:
1. It makes escalation deliberate — the agent has to articulate why.
2. The reason is stored in the escalation record and visible to the specialist team receiving the ticket, giving them context before they open it.

---

**Q14. Phase 13 marks PLAN_PHASE.md Phase 12 (Agent console) as "validated locally." What does that mean exactly?**

The status progression in this project is:
1. `not started` — not yet built
2. `in progress` — being built
3. `implemented` — code exists, commits made
4. `validated locally` — the phase's tests pass on this machine

"Validated locally" means:
- The frontend unit tests pass with `npm run test`
- The frontend builds without TypeScript errors with `npm run build`
- The backend tests pass with `make test`
- The browser demo works end-to-end (run workflow on CD-1002, approve, send reply)

It explicitly does NOT mean:
- Deployed to a cloud environment
- Running in CI/CD
- Tested against a real Supabase database

The honest-status rule (CLAUDE.md §15.1) requires separating these levels. Claiming "deployed" before it is true is considered a project failure condition.
