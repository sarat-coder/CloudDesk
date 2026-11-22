# Phase 8 — Interview Questions & Answers: Memory

---

## Conceptual / Design Questions

**Q1. Why does an AI support platform need memory at all? Can't the AI just re-read the ticket?**

The ticket contains the current problem, but not the customer's history. Without memory:
- The AI does not know what was tried last time.
- It does not know the customer's preferences.
- It cannot recognize a recurring problem.

Memory lets the AI personalise its response and skip solutions that have already failed.
It also reduces time-to-resolution because the agent does not ask questions that were already answered.

---

**Q2. Why two tiers — Redis and a database? Why not just use the database for everything?**

The two tiers serve different purposes:

| Tier | Speed | Persistence | Cost |
|---|---|---|---|
| Redis (short-term) | Microseconds | 24 h max | Very cheap |
| Database (long-term) | Milliseconds | Permanent | Moderate |

Short-term data (conversation history, workflow state, retrieval cache) changes constantly
during a session and expires naturally. Putting it in the database would create enormous
write churn and require manual cleanup.

Long-term data (customer notes) must survive server restarts and be queryable by customer ID.
Redis is not queryable in a relational way and is not durable by default.

---

**Q3. What is a retrieval cache and why does it use a 5-minute TTL?**

A retrieval cache stores the results of a knowledge-base search. If the same query is run
twice within 5 minutes, the second call returns the cached results without hitting the
vector store again.

5 minutes is chosen because knowledge-base articles rarely change that fast, and it covers
the typical duration of a single workflow run. A longer TTL risks serving stale results after
a reindex. A shorter TTL would not save much.

---

**Q4. What is de-duplication in this context, and why is it important?**

De-duplication means: if the exact same memory note (same customer + same type + same
content) is about to be written twice, the second write is silently skipped.

Without this, `record_resolution()` called twice on the same ticket would double-write
every note. Over time, the memory table would fill with hundreds of identical rows, making
it slow to query and confusing for the AI to read.

The check is an exact string match after scrubbing. This is intentionally strict — slightly
different wording creates a new note rather than merging, which keeps the logic simple and predictable.

---

**Q5. How does the scrub function protect the memory system?**

`scrub()` (from Phase 7) scans text for known secret patterns — credit card numbers, API keys,
passwords, JWT tokens — and replaces them with `[REDACTED]` before anything is written to
the database.

This is the last line of defence before a note is persisted. Even if a ticket body contained
a customer's password and somehow made it into the resolution summary, `scrub()` would remove
it before it ever reached the `customer_memory` table. This satisfies security requirement N7
in the spec.

---

**Q6. Why does `long_term.add_note()` receive a session parameter instead of creating its own?**

This is called "session injection" and it is the standard pattern in the codebase.

The caller controls the session lifecycle — it opens the session, passes it in, and commits or
rolls back. If `add_note()` created its own session, every note write would be a separate
database transaction. That would make it impossible to write multiple notes atomically in
`record_resolution()` — if the second note failed, the first would already be committed.

By accepting a shared session, all notes written by one `record_resolution()` call either all
succeed or all roll back together.

---

## Implementation Questions

**Q7. What is `fakeredis` and why is it used in tests?**

`fakeredis` is a Python library that implements the Redis protocol entirely in memory without
a network socket. In tests, `USE_FAKE_REDIS=true` causes `get_redis_client()` to return a
`fakeredis.FakeRedis()` instance instead of connecting to a real Redis server.

This means tests run offline — no Redis installation, no Docker, no network — and they still
exercise the exact same code path that production uses.

---

**Q8. Why is the Redis client cached at module level in `short_term.py`?**

```python
_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = get_redis_client()
    return _redis_client
```

Without this cache, every call to `save_conversation()` or `load_workflow_state()` would
call `get_redis_client()`, which calls `fakeredis.FakeRedis()` and creates a *brand new*
in-memory store. Data written in one call would be invisible to the next.

Caching the client at module level ensures all calls share one store — in tests with fakeredis
and in production with the real Redis connection pool.

---

**Q9. Why does `recall_customer()` return a list of dicts instead of `CustomerMemory` objects?**

Agents are defined in the `agents/` package and must not import `app.models.entities`. That
would violate the layering rules in the spec (agents must not write SQL directly, and the
memory service is the bridge).

Returning plain dicts decouples the agents from the SQLAlchemy model. The agents receive
simple data they can iterate over and format into a prompt, with no dependency on the ORM.

---

**Q10. The spec says "rules first, LLM second". How does memory fit into that principle?**

Memory is read-only context for the LLM — it does not decide anything. The pattern holds:

1. `recall_customer()` retrieves history → feeds it into the prompt as context (not rules).
2. The LLM uses that context to generate a response.
3. Rules still fire independently (e.g., "is this a billing dispute?" is decided by rules, not by what the customer's memory says).

Memory enriches the LLM's context. Rules constrain what the LLM is allowed to decide.
They operate at different layers and do not conflict.

---

## Architecture / Trade-off Questions

**Q11. What happens if Redis goes down? Does the whole platform stop?**

No. The short-term memory is best-effort context, not critical path.

- If Redis is unavailable, `load_conversation()` returns `[]` and `load_workflow_state()` returns `None`.
- The workflow still runs. It just starts without cached context.
- The long-term memory in the database is unaffected.

This is intentional. The spec says "telemetry must not break a run" (§16) — the same principle
applies here: auxiliary systems like cache should degrade gracefully.

---

**Q12. What would you change to make this production-grade?**

Three improvements:

1. **Async Redis.** The current implementation uses a synchronous Redis client. In production,
   `redis.asyncio.from_url()` should be used to avoid blocking the event loop during I/O.

2. **TTL tuning.** The 24-hour TTL for conversation state may be too long for high-volume
   systems. A shorter TTL (2–4 hours) would reduce Redis memory usage, with the trade-off
   that very long-running approvals could lose state.

3. **Memory note size limit.** Long tickets could produce very large `past_issue` notes.
   Adding a character limit (e.g., 500 chars) would keep notes prompt-friendly and prevent
   database bloat.

---

**Q13. How would you extend this system to support "forget me" / GDPR erasure?**

The `customer_memory` table stores all notes with a `customer_id` FK. A GDPR erasure
request would:

1. Delete all rows in `customer_memory` where `customer_id = {id}`.
2. Clear `conversation:{ticket_id}` keys in Redis for all tickets belonging to that customer.
3. Delete the customer record (cascade deletes subscriptions, tickets, etc.).

The existing `clear_ticket()` function in `short_term.py` already supports step 2 at the
ticket level. A new service function `purge_customer()` would loop over the customer's tickets
and call it. The database delete is a standard `DELETE FROM customer_memory WHERE customer_id = ?`.

Ticket CD-1009 (workspace deletion + GDPR) is exactly this scenario. It is handled by the
escalation rules in Phase 7 and would use this memory purge in a full implementation.

---

**Q14. Why is `record_resolution()` designed to write multiple note types instead of one combined note?**

Different note types serve different recall purposes:

- `past_issue` lets the system say "you've had this problem before."
- `troubleshooting` lets the system say "this step worked for you last time."
- `note` is a free-form summary for the agent to read.

Keeping them separate allows future filtering: an agent could ask for only `troubleshooting`
notes when diagnosing a new ticket, without reading irrelevant preference or billing history.
One combined note would make that filtering impossible without text parsing.

---

**Q15. How does the memory system prevent storing another customer's data?**

Three controls:

1. **Scoped writes.** `add_note()` takes `customer_id` as a parameter. The caller (memory service)
   always passes the customer ID of the ticket being processed — it never receives a foreign ID.

2. **No cross-customer reads.** `recall()` queries `WHERE customer_id = ?`. It is structurally
   impossible to retrieve another customer's notes with this query.

3. **Scrub.** Even if a ticket body mentioned another customer's card number, `scrub()` removes
   it before the note is written.

Requirement N7 ("memory notes must not contain data about other customers or secrets") is
satisfied by design, not by policy enforcement at runtime.
