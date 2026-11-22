# Phase 4 — Interview Questions & Answers

> Covers the Support API phase: REST design, FastAPI, Pydantic, layered architecture, session management, and testing.

---

## REST & API Design

**Q1: Why is `docs/API_CONTRACT.md` written before the implementation?**

**A:** The contract is the shared agreement between the backend and frontend teams. Writing it first prevents the common problem where the backend ships a field named `ticket_id` and the frontend expects `ticketId` — small mismatches that cause silent bugs. It also forces you to think about the response shape from the consumer's perspective, not the database's perspective, before you're locked in. In this project, the TypeScript types in `frontend/lib/types.ts` are derived from the same contract, so both sides are guaranteed to match.

---

**Q2: Why are tickets created with status `"new"` even when the agent creates them through the API?**

**A:** The status lifecycle — `new → in_progress → resolved` — is a business concept, not a technical one. Any ticket that hasn't been investigated yet is "new" regardless of how it arrived. Setting `"new"` at creation makes the workflow's starting state predictable: the AI agents in Phase 9 will always pick up tickets in `"new"` status and move them forward.

---

**Q3: Why does `POST /tickets` automatically create the first `TicketMessage` row?**

**A:** A ticket without at least one message is incomplete — the AI agents need the original customer text to investigate. By creating the message atomically with the ticket (in the same database transaction), we guarantee that every ticket has at least one message. This prevents a class of bugs where a ticket exists but has no body to analyze.

---

**Q4: How does pagination work in `GET /tickets`?**

**A:** The endpoint accepts `page` (default 1) and `page_size` (default 20, max 100). The service layer runs two queries: a `COUNT(*)` to get the total, and a `SELECT` with `OFFSET` and `LIMIT` to get the page. Both queries apply the same filters (status, severity, search) so the total is always consistent with the page content. The response always includes `total`, `page`, and `page_size` so the frontend can render pagination controls.

---

**Q5: A `viewer` user calls `POST /tickets`. What happens?**

**A:** FastAPI evaluates the `require_role("agent")` dependency before the route handler runs. The dependency checks that the token's role rank (viewer=1) is less than the minimum rank (agent=2) and raises HTTP 403 Forbidden. The route handler never executes, the database is never touched, and the audit log records a 403.

---

## FastAPI & Pydantic

**Q6: What is the difference between a Pydantic `BaseModel` and a SQLAlchemy model?**

**A:** A SQLAlchemy model (in `entities.py`) describes a database table — it has columns, relationships, and is managed by an ORM session. A Pydantic model (in `schemas/`) describes the shape of data in transit — over HTTP or between functions. Pydantic validates input and serialises output. The service layer converts SQLAlchemy models into Pydantic models before returning them to the router. This separation means the database schema and the API contract can evolve independently.

---

**Q7: What does `model_config = {"from_attributes": True}` do in the Pydantic schema?**

**A:** It tells Pydantic to accept SQLAlchemy ORM objects (which expose data as Python attributes) in addition to plain dicts. Without it, `CustomerResponse.model_validate(customer_orm_object)` would fail because Pydantic would look for dict keys, not object attributes. With it, `model_validate` reads `customer.name`, `customer.email`, etc. directly from the ORM instance.

---

**Q8: Why are there separate `TicketSummaryResponse`, `TicketResponse`, and `TicketDetailResponse` schemas?**

**A:** Each represents a different level of detail for different use cases:
- `TicketSummaryResponse` — the list view. Enough fields for a row in a table (no body text, no messages).
- `TicketResponse` — the creation/update response. Adds `body` and `tags`.
- `TicketDetailResponse` — the full view. Adds messages, customer context, workflow state, and history.

Returning only what is needed for each endpoint improves performance and prevents leaking data the caller doesn't need. This is the **principle of minimal surface area**.

---

**Q9: Why does `TicketCreate` validate `subject` with `min_length=1, max_length=512`?**

**A:** These are system boundary validations (CLAUDE.md §18 rule: validate at system boundaries). We can't trust the caller to send sensible data. An empty subject would create a confusing ticket. A 10 MB subject would bloat the database and break display components. Pydantic's field validation rejects bad input before it reaches the service layer, and FastAPI automatically returns HTTP 422 Unprocessable Entity with a helpful error message.

---

## Session Management & Database

**Q10: Why was `get_db()` added when `get_session()` already existed?**

**A:** `get_session()` uses `@asynccontextmanager`, which returns a context manager object. FastAPI's dependency injection system expects either a plain async function or an **async generator** (a function with `yield`). Passing a context manager to `Depends()` doesn't work — FastAPI doesn't know to call `__aenter__`/`__aexit__` automatically. `get_db()` is an async generator that explicitly yields the session, which is the pattern FastAPI understands. Both ultimately use the same session factory and have the same commit/rollback behaviour.

---

**Q11: When exactly does the database session commit?**

**A:** The `get_db()` dependency yields the session before the route handler runs. When the route handler returns normally, Python resumes the generator after the `yield`, which runs `await session.commit()`. If the route handler raises an exception, Python resumes with `throw()`, which runs `await session.rollback()`. This means every successful HTTP request commits its work, and every failed request is rolled back — with no explicit commit/rollback calls in the route handlers themselves.

---

**Q12: What happens if two simultaneous requests try to create a ticket and both compute `ticket_number = "CD-1014"`?**

**A:** The `ticket_number` column has a `UNIQUE` constraint in the database (see `entities.py`). If two transactions try to insert the same ticket number, one will get a `UniqueViolationError` from the database. The collision-prevention loop in `ticket_service.create_ticket` increments the counter and retries — but in practice, the unique constraint is the final safety net. For a single-process demo app this is fine; a production system would use a database sequence or UUID-based ticket numbers.

---

## Layered Architecture

**Q13: Why can't the router (tickets.py) write SQL directly?**

**A:** CLAUDE.md §4.2 defines strict layering rules: the API layer handles HTTP concerns only (validation, auth, response codes); the service layer handles business rules; the repository layer handles SQL. If the router wrote SQL, any change to the database schema would require changing the HTTP handler — tightly coupling two concerns that should be independent. It also makes testing harder: you'd need a database to test HTTP input validation.

---

**Q14: Why does `customer_service.py` have a `_ticket_summary()` helper that duplicates logic from `ticket_service.py`?**

**A:** This is a deliberate trade-off for Phase 4. The customer detail view needs to list tickets in a summary format, but importing `ticket_service` from `customer_service` would create a dependency cycle (or at least tight coupling). The helper is small and the duplication is minimal. In a larger codebase, a `TicketSummaryMapper` utility might be extracted to a shared location. At this stage, three similar lines are better than a premature abstraction (CLAUDE.md §18).

---

## Testing

**Q15: How do the ticket tests use the demo seed data without resetting the database between tests?**

**A:** The test module uses `scope="module"` for the client fixture, which means one test database is shared across all tests in the module. The seed data (13 tickets, 8 customers) is loaded once during app startup. Tests read from seed data by querying the API (e.g., searching for ticket CD-1001 by number). Tests that write data (creating new tickets) work on top of the seed data without deleting it. This is fast but means tests must not depend on a fixed total count — they check `>= 13`, not `== 13`.

---

**Q16: Why is the channel in `test_create_ticket_all_channels` parameterised?**

**A:** F1 (CLAUDE.md functional requirement 1) explicitly says tickets must be accepted from `email`, `chat`, `web`, and `API` channels. A single parameterised test verifies all four channels with minimal code duplication, and pytest automatically names each test run, making failures easy to identify (e.g., `test_create_ticket_all_channels[api]`).

---

**Q17: How does `test_run_409_when_waiting_on_approval` work without an actual workflow?**

**A:** The test first patches a ticket's status to `"waiting_on_approval"` via `PATCH /tickets/{id}`, then immediately calls `POST /tickets/{id}/run`. The router checks the ticket's status *before* starting the workflow and returns 409 if it is `"waiting_on_approval"`. The workflow engine doesn't need to exist for this check — the status is just a string in the database. This is the Phase 4 version of the 409 contract specified in CLAUDE.md §10.

---

## TypeScript Contract

**Q18: Why are TypeScript types stored in the backend repository if the frontend doesn't exist yet?**

**A:** The types are documentation as much as code. Having them in the repository ensures they evolve with the backend: when a new field is added to `TicketDetailResponse` in Python, the developer knows to add it to `frontend/lib/types.ts` as well. The same CLAUDE.md rule (§12) says: "if an endpoint changes, update `API_CONTRACT.md`, `backend/app/schemas/`, and `frontend/lib/types.ts` in the same change." All three are in the same repo so the constraint is enforceable in code review.

---

## Open / Extended Questions

**Q19: How would you add pagination to the customer tickets list inside `GET /customers/{id}`?**

**A:** The current `get_customer_detail` returns all tickets for a customer. For customers with hundreds of tickets this could be slow. The fix would be to accept optional `ticket_page` and `ticket_page_size` query parameters, pass them to the service, and add `LIMIT`/`OFFSET` to the ticket query. The response would include pagination metadata for the nested tickets. This is deferred because the demo scenario has at most a few tickets per customer.

---

**Q20: What would change if you switched from SQLite to PostgreSQL?**

**A:** Almost nothing. The `DATABASE_URL` environment variable changes from `sqlite+aiosqlite:///./data/support.db` to `postgresql+asyncpg://user:pass@host/db`. The SQLAlchemy models use `String(36)` and `JSON` (not `JSONB`) specifically to remain portable across both databases. The only differences are:
- PostgreSQL enforces unique constraints with more concurrency safety.
- PostgreSQL supports `JSONB` for faster JSON queries (a future optimization).
- Migrations are needed for PostgreSQL; SQLite auto-creates tables at startup.
