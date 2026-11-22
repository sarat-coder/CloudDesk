# Phase 8 — Memory: Plain-English Explanation

## What is Phase 8 about?

In Phase 7 we built the safety rules — the system could now recognize a security breach
or a billing dispute without asking the AI.

Phase 8 is about **making the system remember**. Right now, every time a new ticket
arrives for the same customer, the system starts from zero — it has no idea who this
person is, what problems they had before, or what already worked.

After Phase 8:

> **The platform remembers customers across conversations. When a new ticket arrives,
> the AI walks in already knowing that customer's history, preferences, and past solutions.**

---

## Why memory matters — a simple analogy

Think about the difference between calling a support line where:

**Scenario A — no memory:**  
You explain your whole situation from scratch. The agent asks the same questions they asked
last month. They suggest the same fix that did not work before.

**Scenario B — with memory:**  
The agent says: "Hi again, I see last month we fixed your SSO issue by updating your IdP
settings. Is this related?" They skip five minutes of questions and go straight to relevant help.

CloudDesk builds Scenario B. The memory system is what makes it possible.

---

## Two kinds of memory — short-term and long-term

Just like humans, the system has two types of memory:

### Short-term memory (Redis)

**What it is:** A fast, temporary whiteboard that lives in Redis.

**Redis** is like a giant sticky-note board. You can write something on it and read it
back in milliseconds. Notes automatically disappear after a set time — there is no manual
cleanup needed.

**What we store here:**

| Thing stored | How long it lasts | Why |
|---|---|---|
| Conversation history for a ticket | 24 hours | So the AI can remember what was said earlier in the same session |
| Workflow state snapshot | 24 hours | So the agent dashboard can poll for progress without re-running the workflow |
| Retrieval cache (search results) | 5 minutes | So the same knowledge-base search is not repeated for the same question |

**Key naming convention:**  
Every key follows a clear pattern so they never clash:
- `conversation:{ticket_id}` → the chat history for ticket CD-1002
- `workflow:{workflow_id}` → the last-known state of a running workflow
- `rag:{mode}:{category}:{top_k}:{query_hash}` → cached knowledge-base results

**In tests:** We use `fakeredis` — it behaves exactly like a real Redis server but runs
completely in memory inside the test process. No Redis installation needed.

---

### Long-term memory (database)

**What it is:** A permanent record in the `customer_memory` database table.

This memory survives server restarts and is never automatically deleted.

**The four memory types:**

| Type | What it records | Example |
|---|---|---|
| `preference` | How the customer likes to work | "Prefers email updates, not chat" |
| `past_issue` | A problem they had before and how it was resolved | "SSO failed: fixed by updating IdP settings." |
| `troubleshooting` | A specific step that worked for this customer | "Clearing browser cache fixed the login loop." |
| `note` | A general agent observation | "Customer is on enterprise plan, sensitive to downtime." |

**Two safety rules always enforced:**

1. **Scrub before writing.** Before any note is saved, it passes through `scrub()` from
   Phase 7. Card numbers, API keys, and passwords are replaced with `[REDACTED]`
   automatically — secrets can never leak into memory.

2. **De-duplicate.** If the exact same note (same customer + same type + same content) is
   about to be written twice, the second write is silently skipped. The database stays clean
   — no bloated, repetitive notes.

---

## The memory service — the single door agents use

Agents never talk directly to Redis or the database. They always go through
`memory/memory_service.py`, which provides just two functions:

### `recall_customer(customer_id, session)`

Returns the last 10 notes for a customer as a plain list of dictionaries, ready to
paste into an AI prompt. The agents use this at the start of ticket processing so the
AI knows who it is talking to.

**Example output:**
```
[
  { "type": "past_issue", "content": "SSO failed: fixed by updating IdP settings.", ... },
  { "type": "preference", "content": "Prefers email updates only.", ... }
]
```

### `record_resolution(customer_id, ticket_id, subject, steps, summary, session)`

Called when a ticket is resolved. It writes up to 5 notes:

1. A `past_issue` note: **"{subject}: {summary}"** — what happened and how it was fixed.
2. Up to 3 `troubleshooting` notes: the first three steps from the diagnosis that worked.
3. A `note` with the resolution summary.

All writes are de-duplicated and scrubbed automatically.

---

## What this looks like in practice — ticket CD-1002

Customer Alex Jordan calls in with a billing issue: "Charged for 8 seats, only using 5."

**First time this customer has a ticket:**  
No memory. The system investigates from scratch.

**After the ticket is resolved:**  
`record_resolution` is called. The memory now contains:
- `past_issue`: "Charged 8 seats, using 5: Refund approved for 3 seats × 2 months."
- `troubleshooting`: "Verified seat count in workspace settings."
- `note`: "Refund approved for 3 seats × 2 months."

**Next time Alex Jordan opens a ticket about billing:**  
`recall_customer` returns those notes. The AI reads them before the conversation begins
and says: "I see you had a billing overage fixed last quarter — is this a similar issue?"

---

## Files created in Phase 8

| File | Purpose |
|---|---|
| `memory/__init__.py` | package entry point |
| `memory/short_term.py` | Redis facade: conversation, workflow state, retrieval cache |
| `memory/long_term.py` | DB facade: add_note (with scrub + dedup), recall |
| `memory/memory_service.py` | `recall_customer()` and `record_resolution()` — the agents' only entry point |
| `tests/unit/test_memory.py` | 24 offline tests covering all three layers |

---

## One-sentence summary for non-technical readers

> Phase 8 gave CloudDesk a two-tier memory system: a fast, temporary Redis cache for
> in-flight conversations and workflow state, and a permanent customer memory database
> that the AI reads before every ticket so it already knows the customer's history,
> preferences, and what has worked before — with secrets scrubbed out automatically
> and duplicate notes silently skipped.
