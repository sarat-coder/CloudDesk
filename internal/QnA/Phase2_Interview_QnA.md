# Phase 2 — Interview Q&A

> All possible interview questions from Phase 2 (Persistence and Demo Data) with thorough answers. Questions range from conceptual/non-technical to deep technical.

---

## Section 1 — What Was Built and Why

**Q1: What is the goal of Phase 2?**

Phase 2 gives the application its data model and persistent storage. After Phase 1, the server could boot and answer health checks, but had no memory — every restart wiped everything. Phase 2 adds:
- A formal definition of every data entity (customers, tickets, subscriptions, etc.)
- A database engine that saves those entities to disk
- A repository layer so the rest of the code has a clean way to read and write data
- A set of realistic demo data loaded automatically at startup

---

**Q2: Why does the system need 16 database tables?**

Each table stores a distinct type of information with its own fields and relationships. The 16 tables map directly to the product's features:

- **Core support**: `tickets`, `ticket_messages` (the actual problem and conversation)
- **Customer identity**: `customers`, `profiles`, `subscriptions`, `workspaces`, `products` (who is raising the ticket and what plan are they on)
- **AI workflow**: `workflow_runs`, `workflow_events`, `resolution_actions`, `approval_requests` (the AI's work is data too)
- **Escalation and safety**: `escalations`, `customer_memory`, `audit_logs`
- **Knowledge**: `support_articles` (the articles the AI retrieves)
- **Operational**: `incidents` (active outages the AI might reference)

---

**Q3: Why SQLAlchemy instead of writing raw SQL?**

SQLAlchemy provides several advantages:
1. **Type safety**: Column types are defined in Python. A mistake (storing an integer where a string is expected) is caught at the Python level.
2. **Portability**: The same model works on SQLite and PostgreSQL. SQLAlchemy translates to the right SQL dialect.
3. **Relationship mapping**: `customer.tickets` returns a Python list — no manual JOIN needed.
4. **Async support**: SQLAlchemy 2's async engine works with Python's `asyncio`, which is essential for a high-concurrency FastAPI application.
5. **Migrations via code**: Models document the schema. `create_all()` handles DDL at startup.

---

## Section 2 — The Data Model

**Q4: What is the purpose of the Category enum with exactly 10 values?**

The 10 categories represent every type of support ticket the system handles. By restricting values to exactly these 10, the system gains:
- **Consistency**: Every ticket is categorised the same way, regardless of which AI model classifies it.
- **Routing logic**: Escalation rules, knowledge retrieval, and troubleshooting playbooks all branch on category.
- **Reporting**: Dashboard metrics are reliable because there are no "other-billing" or "LOGIN_ISSUE" variants — only "billing" or "login_issue."

Adding a new category is a deliberate act: it requires updating `schemas/common.py`, the Postgres DDL, the AI prompts, the routing rules, and the test suite.

---

**Q5: Why are UUIDs stored as `String(36)` instead of a native UUID column type?**

SQLite does not have a native UUID column type. If the models used `UUID` (Postgres-only), the same code would not work on SQLite. By using `String(36)` (a 36-character string, the standard UUID text representation), the same model runs on:
- SQLite (local development and tests)
- PostgreSQL/Supabase (production)

The trade-off is a slightly larger storage footprint compared to a 16-byte binary UUID. For this application's scale, that trade-off is entirely acceptable.

---

**Q6: What is the difference between `JSON` and `JSONB` and why does the code use `JSON`?**

- **`JSON`** (Postgres) stores JSON as text, re-parses on each read. Supported by both Postgres and SQLite.
- **`JSONB`** (Postgres-only) stores JSON in a binary format with indexing support. Faster queries, but only on Postgres.

SQLAlchemy's `JSON` column type maps to `JSON` on Postgres and to a text column on SQLite. Using `JSONB` in the model would break SQLite compatibility. The `database/schema.sql` file uses `jsonb` for Postgres-specific production use, while the Python models use `JSON` for portability.

---

**Q7: What is `updated_at` and why is it on every table?**

`updated_at` is a timestamp that records when a row was last modified. It is used for:
- **Debugging**: "This ticket status changed from new to in_progress at 14:32:17" — visible in the audit trail.
- **Caching**: The frontend can compare `updated_at` to decide whether to re-fetch.
- **Conflict detection**: If two users modify the same record, `updated_at` lets you detect the conflict.

In SQLite (via Python's `onupdate=_now`), the timestamp is updated by SQLAlchemy before each UPDATE. In Postgres (via the `set_updated_at()` trigger), the database itself updates it — no application code needed. This prevents the common bug where code forgets to update the timestamp.

---

## Section 3 — The Database Layer

**Q8: What is `create_tables()` and when is it called?**

`create_tables()` calls SQLAlchemy's `Base.metadata.create_all()`, which issues `CREATE TABLE IF NOT EXISTS` statements for all 16 tables. It is called once at server startup (in the FastAPI lifespan handler). Key properties:
- **Idempotent**: `IF NOT EXISTS` means running it twice is safe — it will not recreate tables or delete data.
- **Automatic**: New developers do not need to run SQL scripts manually. `make backend` creates the database.
- **SQLite and Postgres**: The same function works on both because SQLAlchemy generates the appropriate DDL.

---

**Q9: What is the `get_session()` context manager and why is it structured that way?**

```python
@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    factory = _make_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

This structure guarantees:
1. **A session is always released**: Even if the calling code raises an exception, the `async with factory()` block ensures the session is returned to the pool.
2. **Transactions are committed on success**: If the code inside `async with get_session() as session:` completes without an exception, all changes are committed.
3. **Rollback on failure**: If any exception occurs, all changes in the transaction are rolled back. The database is never left in a partial state.
4. **Caller simplicity**: Code that uses data just calls `async with get_session() as session:` — no manual commit/rollback.

---

**Q10: What is the difference between `AsyncEngine` and `AsyncSession` in SQLAlchemy?**

- **`AsyncEngine`**: A single object (singleton) that manages the connection pool to the database. It knows the database URL and driver. Created once at startup.
- **`AsyncSession`**: A short-lived object (created per request) that represents one database transaction. It tracks pending changes and communicates with the engine.

Analogy:
- The engine is a **taxi company** — it manages a fleet of vehicles.
- A session is a **single taxi ride** — it starts, takes you somewhere, and ends.

---

## Section 4 — The Repository Layer

**Q11: What is the repository pattern and why use it?**

The repository pattern places all database query logic in one dedicated class per entity type. All other code calls methods like `TicketRepository.get_by_number("CD-1002")` instead of writing `SELECT * FROM tickets WHERE ticket_number = 'CD-1002'`.

Benefits:
1. **Single point of change**: Rename a column → update one method in one file.
2. **Testability**: Mock the repository to test business logic without a real database.
3. **Readability**: Business logic reads like natural language (`await repo.list_by_customer(customer.id)`) not raw SQL.
4. **Layering compliance**: The CLAUDE.md spec requires agents to never write SQL directly. The repository is the only place SQL lives.

---

**Q12: Why does `BaseRepository` use generics (`Generic[ModelT]`)?**

Generics let the base class know the type of model it is working with:

```python
class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

class TicketRepository(BaseRepository[Ticket]):
    model = Ticket
```

This means:
- `TicketRepository.get(id)` returns `Ticket | None` — not just `Any`.
- Type checkers (like mypy) can catch bugs at development time: "you are using this `Customer` object as if it were a `Ticket`."
- Code completion in IDEs works correctly: typing `ticket.` shows Ticket's fields, not generic ones.

---

**Q13: What does `exists_by_external_id` in `CustomerRepository` do and why does it exist?**

```python
async def exists_by_external_id(self, external_id: str) -> bool:
    result = await self.session.execute(
        select(Customer.id).where(Customer.external_id == external_id)
    )
    return result.scalar_one_or_none() is not None
```

It performs a lightweight check that selects only the `id` column instead of fetching the full row. It is used by `seed_service.py` to check whether a customer already exists before inserting — this is what makes the seed idempotent.

The key optimisation: selecting only `Customer.id` (a `String(36)`) is much cheaper than selecting all columns and constructing a full Python object. For 8 customers this is negligible, but it is a good pattern that scales.

---

## Section 5 — Sample Data and the Bootstrap Service

**Q14: Why are there exactly 13 demo tickets?**

Each ticket exercises a specific feature of the platform:

| Ticket | Feature exercised |
|---|---|
| CD-1001 | Enterprise SSO failure (critical severity, active incident) |
| CD-1002 | Billing refund (triggers the **human approval gate**) |
| CD-1003 | API rate-limiting with quota confusion |
| CD-1004 | Storage quota with delay-in-meter behaviour |
| CD-1005 | Security incident (**auto-escalates** to Security Response Team) |
| CD-1006 | Data loss (**auto-escalates** to Data Recovery team) |
| CD-1007 | Workspace permissions (external sharing toggle) |
| CD-1008 | Integration failure (Slack webhook) |
| CD-1009 | GDPR erasure request (**auto-escalates** to Legal/Compliance) |
| CD-1010 | Feature request (should be classified low severity by policy) |
| CD-1011 | Payment dispute (**auto-escalates** to Billing) |
| CD-1012 | MFA lockout (retrieves the MFA recovery article) |
| CD-1013 | Contains a **prompt injection attempt** the AI must refuse |

This set covers every code path in the AI workflow: normal resolution, approval gate, four different escalation triggers, and an adversarial input.

---

**Q15: What is an "idempotent" bootstrap and why does it matter?**

Idempotent means "running the operation multiple times produces the same result as running it once."

In the seed service, before inserting any record, the code checks whether that record already exists:

```python
if await repo.exists_by_external_id(rec["external_id"]):
    continue  # skip — already in the database
```

**Why it matters:**
1. If a developer restarts the server, the demo data is not duplicated.
2. CI tests that call `bootstrap_demo_data()` in the test fixture do not accidentally double-seed.
3. If the server crashes mid-seed, the next restart safely continues from where it left off.

Without idempotency, a simple server restart would result in 26 tickets (13 × 2) instead of 13.

---

**Q16: Why are sample data files in JSON instead of SQL INSERT statements?**

1. **Portability**: JSON is format-agnostic. The same `customers.json` loads into SQLite (via Python), PostgreSQL (via Python), and could be loaded into a test double without any SQL at all.
2. **Readability**: JSON is easier for a human to read and edit than SQL INSERT statements.
3. **Testability**: Tests can read `customers.json` directly (without a database) to verify the data format.
4. **Separation of concerns**: The data is separated from the loading logic. If you want to change the data, you only touch the JSON file — not the Python code.

The `seed.sql` file exists separately for the Postgres/Supabase SQL editor workflow.

---

**Q17: What is YAML front-matter in the knowledge base articles and why is it there?**

Each knowledge base article is a Markdown file with a YAML block at the top:

```yaml
---
title: "SSO Configuration Guide"
category: "login_issue"
tags: ["sso", "saml", "okta"]
summary: "How to set up and troubleshoot SAML-based SSO..."
---
```

This metadata serves the RAG (Retrieval-Augmented Generation) pipeline in Phase 5:
- **`category`**: Narrows which articles are considered for a given ticket category. If the ticket is about billing, the retriever can skip SSO articles.
- **`tags`**: Enables keyword search alongside semantic (embedding-based) search.
- **`summary`**: Can be used as a short snippet in the AI's response without quoting the full article.

Storing metadata in the file (rather than in a separate database) keeps articles self-contained and easy to edit.

---

## Section 6 — Architecture and Design Principles

**Q18: Why does the same code work on SQLite and PostgreSQL?**

Three design decisions make this possible:

1. **`String(36)` UUIDs**: No PostgreSQL-only UUID type.
2. **SQLAlchemy `JSON`**: Maps to text in SQLite, json/jsonb in Postgres.
3. **`DATABASE_URL` as the only configuration point**: The engine is created from the URL; the rest of the code never mentions the specific database.

This is the "ports and adapters" principle: the application core is decoupled from the specific infrastructure. The database is just one implementation of "storage."

---

**Q19: What is Row Level Security (RLS) and why is it used?**

RLS is a PostgreSQL feature that lets you define policies inside the database itself — policies that restrict which rows each user can see or modify, based on their identity.

In CloudDesk's Supabase deployment:
- The **backend** uses the **service-role key** (which bypasses RLS) for full access.
- The **browser** uses the **anon key** (which is subject to RLS).

RLS provides **defence in depth**: even if a frontend bug accidentally used the wrong key, or if someone obtained the anon key, they still cannot read tickets they are not authorised to see. The database itself enforces the access control.

---

**Q20: Why is there a `database/schema.sql` file when SQLAlchemy already handles schema creation?**

SQLAlchemy's `create_all()` is for the Python/SQLite development workflow. The `schema.sql` file exists because:

1. **Supabase SQL editor**: Database administrators or DevOps engineers set up the Postgres schema by running SQL, not Python scripts.
2. **Source of truth**: `schema.sql` documents the production schema in a human-readable, database-native format. It includes Postgres-specific features (triggers, `CHECK` constraints, `jsonb`) that SQLAlchemy's `JSON` type does not fully express.
3. **Audit and review**: A SQL file can be reviewed in a pull request by DBAs who do not know Python.
4. **CLAUDE.md rule**: "§6 — `database/schema.sql` is the authority for table count." The Python models and the SQL file must agree. A test (`test_entities.py`) enforces this.

---

**Q21: What is the difference between `scope="module"` and `scope="session"` in the seed test fixture?**

In `tests/api/test_seed_bootstrap.py`:

```python
@pytest.fixture(scope="module")
async def seeded_db():
    await create_tables()
    await bootstrap_demo_data()
```

- **`scope="module"`**: The fixture runs once per test file (module). All tests in `test_seed_bootstrap.py` share the same seeded database state.
- **`scope="session"`**: Would run once for the entire test suite — useful for setup that is very expensive.

Using `module` scope here means: seed once, run all 7 seed tests, then the fixture is torn down. This is faster than seeding before every test, but isolated enough that seed tests don't contaminate unit tests in other files.

---

**Q22: What would happen if `create_tables()` was not idempotent?**

If `CREATE TABLE` (not `CREATE TABLE IF NOT EXISTS`) was used, the second `make backend` after the first run would fail with "table already exists" errors. The developer would need to manually delete the database file or run `DROP TABLE` before starting the server again.

By using `IF NOT EXISTS` (via SQLAlchemy's default `checkfirst=True`), the startup sequence is safe to run repeatedly. This is essential for the developer experience and for production restarts.

---

## Section 7 — Advanced Questions

**Q23: How would you extend the data model to support multi-tenancy?**

The current model supports one "tenant" per deployment (one CloudDesk instance serving multiple customers). True multi-tenancy (multiple tenants sharing one database) would require:
1. Adding a `tenant_id` column to every table that holds user data.
2. Extending RLS policies to filter by `tenant_id = current_tenant()`.
3. Ensuring all queries include the tenant filter.

The current model is well-structured for this extension — the layered architecture means you would only need to update the repositories, not the agents or API routes.

---

**Q24: Why does the seed service use `flush()` instead of `commit()` for some inserts?**

In the seed service, most seeding functions call `await session.flush()` while `get_session()` calls `commit()` after the entire block completes. The reason:

- `flush()` sends the pending SQL to the database but does not commit the transaction. This means subsequent queries in the same transaction can see the new rows (e.g., subscriptions can verify their `customer_id` FK constraint).
- The final `commit()` (from `get_session()`'s context manager) writes everything atomically. If anything fails mid-seed, the entire seed run is rolled back cleanly.

This "flush early, commit late" pattern is standard practice for multi-step transactional operations.

---

**Q25: Why are knowledge base articles stored as Markdown files rather than in the database?**

Three reasons:
1. **Version control**: Markdown files in Git have full edit history. If an article is changed, you can see exactly what changed and when.
2. **Knowledge base management**: Support writers edit Markdown files in a text editor or CMS, not in a database admin panel. This is a more natural workflow.
3. **RAG pipeline**: Phase 5 will read these files, chunk them, generate embeddings, and store those in a vector store. The articles are the source material — the vector store is the searchable index. Having the source in files and the index in a database is the correct separation.

The `support_articles` database table stores article metadata and body after they are ingested. The Markdown files are the source; the database is the processed, searchable output.
