# Phase 2 — Persistence and Demo Data: Plain-English Explanation

> **Audience:** Anyone — including non-technical interviewers — who wants to understand what was built in Phase 2 and *why* it matters.

---

## Quick recap: Where we left off

At the end of Phase 1, we had a web server that could start, answer health checks, and log in a structured way. But it had no memory. Every time it restarted, it forgot everything. There was no database, no customers, no support tickets — nothing stored anywhere.

**Phase 2 gives the application its memory.** After Phase 2, the app knows about customers, tickets, billing subscriptions, and workspaces. It loads a realistic set of demo data when it starts for the first time, so developers and stakeholders can see a fully populated system without any manual setup.

---

## What is "persistence"?

Persistence means that data survives after the program stops. Without a database, every variable in memory disappears when the server restarts. With a database, that same data is written to disk and is still there when the server comes back.

Think of it this way:
- **Without persistence:** A notebook that disappears every time you close the cover.
- **With persistence:** A notebook that stays on your desk and remembers every page, even after you go home.

---

## What was actually built? (Four tasks)

### Task P2-1 — SQLAlchemy Models and Enums

**The problem it solves:** The application needs a consistent, typed way to represent data — a "blueprint" for each kind of record.

**What we built:**

- **`backend/app/schemas/common.py`** — A set of carefully controlled "enums" (fixed lists of allowed values). Think of these as the official vocabulary the system speaks:
  - **Category** (10 values): *login_issue, billing, api_failure, workspace_permissions, storage_quota, integration, feature_request, account, security, other* — the only 10 things a support ticket can be about.
  - **TicketStatus** (7 values): *new → in_progress → waiting_on_customer → waiting_on_approval → escalated → resolved → closed* — the journey a ticket takes.
  - **Severity** (4 levels): *low, medium, high, critical* — how urgent a ticket is.
  - **Channel** (4 values): *email, chat, web, api* — how the customer contacted us.

  Why does this matter? By restricting values to these fixed lists, it is **impossible** for the system to store a ticket with status "complete" or category "other-billing" — typos and inconsistencies are caught at the code level before they reach the database.

- **`backend/app/models/entities.py`** — 16 database table definitions written as Python classes using SQLAlchemy. Each class is a blueprint for one type of record. Here is a simplified view of the key tables:

| Table | What it stores |
|---|---|
| `customers` | Customer name, email, company, plan (free/pro/business/enterprise) |
| `tickets` | Support ticket text, channel, status, severity, category |
| `subscriptions` | Billing plan, seat count, renewal date |
| `workspaces` | Storage usage, member count, workspace settings |
| `workflow_runs` | The AI workflow's execution state for each ticket |
| `approval_requests` | Pending human approvals (refunds, deletions, etc.) |
| `customer_memory` | Things the AI has learned about this customer over time |
| `audit_logs` | An immutable record of every important action |

  **Why SQLAlchemy?** SQLAlchemy is a trusted Python library that translates between Python objects and database rows. We write Python; SQLAlchemy writes the SQL. This means the same code works on SQLite (a simple file database, perfect for development) and PostgreSQL (the cloud-grade database used in production).

  **A key design choice:** All IDs are stored as short text strings (`String(36)`) rather than native UUID types. This sounds like a minor detail, but it means the same code works on SQLite (which does not have a native UUID type) and PostgreSQL (which does). "Write once, run anywhere."

- **`backend/app/core/database.py`** — The database engine factory. This file manages:
  1. Creating the database connection based on the `DATABASE_URL` setting.
  2. The `create_tables()` function — called once at startup to create all 16 tables if they do not already exist.
  3. The `get_session()` context manager — a safe way for the rest of the code to get a database connection, use it, and release it cleanly (even if an error occurs).

---

### Task P2-2 — Postgres Schema, RLS, and Migrations

**The problem it solves:** We need a SQL definition of the database that cloud/Supabase teams can apply directly, plus security rules that restrict data access in the cloud.

**What we built:**

- **`database/schema.sql`** — The authoritative Postgres DDL (Data Definition Language). This is the SQL file that creates all 16 tables, indexes, and triggers in a Postgres/Supabase database. If the SQLAlchemy models and this file disagree, this file wins (it is the source of truth for column types, constraints, and indexes).

  Notable contents:
  - An `updated_at` trigger on every table: whenever a row is changed, Postgres automatically updates its `updated_at` timestamp.
  - Indexes on the most-queried columns (customer ID, ticket status, date created) so queries stay fast even with millions of rows.
  - `CHECK` constraints enforcing the enums (e.g., `status IN ('new', 'in_progress', ...)`).

- **`database/rls_policies.sql`** — Row Level Security (RLS) policies. In Supabase (the cloud database layer), every table has RLS enabled, meaning the database itself enforces who can see what:
  - A `viewer` can read tickets but not approve or change anything.
  - Only `agent` and `admin` roles can update ticket records.
  - `audit_logs` can only be read by an `admin`.
  
  This is a defence-in-depth measure: even if a bug in the API layer exposed a database connection to the wrong user, they still cannot read or write data they are not authorised for.

- **`database/migrations/0001_initial.sql`** — The first migration file. When the schema needs to change in the future, a new numbered file is added (`0002_add_index.sql`, etc.) without touching the original. This ensures we have a complete, ordered history of every change to the database structure.

---

### Task P2-3 — Repository Layer

**The problem it solves:** The rest of the application needs a clean, consistent way to read and write database records — without each part of the code writing raw SQL queries.

**What we built:**

Three files, each representing a layer of abstraction:

- **`BaseRepository`** — A generic base class that every table's repository inherits from. It provides standard operations for free:
  - `get(id)` — look up one record by ID
  - `list(limit, offset)` — get a page of records
  - `create(instance)` — save a new record
  - `update(instance, **kwargs)` — change fields on an existing record
  - `count()` — how many records exist

- **`CustomerRepository`** — Specialised customer queries:
  - `get_by_email(email)` — look up a customer by email address
  - `get_by_external_id(external_id)` — look up by the customer's reference number (e.g., "CUST-0001")
  - `exists_by_external_id(external_id)` — fast check used during seeding to avoid creating duplicates

- **`TicketRepository`** — Specialised ticket queries:
  - `get_by_number(ticket_number)` — look up "CD-1002" directly
  - `list_by_customer(customer_id)` — all tickets for a specific customer
  - `list_recent(limit)` — the most recently created tickets

**Why does the repository pattern matter?**

Imagine the AI agent needs to look up a customer's subscription. Without the repository pattern, the agent code might contain raw SQL like `SELECT * FROM subscriptions WHERE customer_id = ?`. Now imagine you change the column name from `customer_id` to `cust_id`. You would need to find and update every SQL query across the entire codebase.

With the repository pattern, the query lives in exactly one place (`SubscriptionRepository.get_by_customer`). Change it once, and the whole application is fixed. The agents, the API routes, and the seed service all call the same method.

---

### Task P2-4 — Sample Data and Demo Bootstrap

**The problem it solves:** Developers and stakeholders need realistic data to work with immediately, without manually creating records.

**What we built:**

- **`sample_data/` JSON files** — Seven JSON files representing the demo scenario:
  - 8 customers across all four plan tiers (free, pro, business, enterprise)
  - 8 subscriptions (annual and monthly billing, different seat counts)
  - 9 workspaces (some customers have more than one)
  - 4 products (the plan definitions)
  - 2 incidents (one active SSO outage, one resolved API issue)
  - 13 tickets (described below)
  - 3 previously resolved cases (for the AI to learn from)

- **13 demo tickets** — Each ticket exercises a different part of the system:

| Ticket | What it exercises |
|---|---|
| CD-1001 | SSO failure for an enterprise customer |
| CD-1002 | Billing refund — triggers the **human approval gate** |
| CD-1003 | API rate-limiting issue |
| CD-1004 | Storage quota exceeded |
| CD-1005 | Security breach — triggers **auto-escalation** |
| CD-1006 | Data loss — triggers **auto-escalation** |
| CD-1007 | Workspace permissions (external sharing) |
| CD-1008 | Slack integration broken |
| CD-1009 | GDPR data deletion request — triggers **escalation** |
| CD-1010 | Dark mode feature request (should be low severity) |
| CD-1011 | Payment dispute — triggers **escalation** |
| CD-1012 | MFA lockout (tests the MFA recovery article retrieval) |
| CD-1013 | Contains a **prompt injection attempt** that the AI must ignore |

- **15 knowledge base articles** (`sample_data/knowledge_base/*.md`) — Markdown articles the AI will search when investigating tickets. Each has YAML front-matter (title, category, tags, summary) so it can be classified and searched efficiently.

- **`backend/app/services/seed_service.py`** — The bootstrap service that loads all the JSON files into the database. Key features:
  - **Idempotent**: If you run it twice, records are only created once — no duplicates. Each function checks whether a record already exists before creating it.
  - **Runs automatically**: Called from `main.py` at startup when `DEMO_MODE=true` and the database is empty.
  - **`make seed`**: Developers can also run it manually from the command line.

---

## How these pieces connect

```
Server starts
     │
     ▼
 create_tables()          ← SQLAlchemy creates the 16 tables from entities.py
     │
     ▼
 bootstrap_demo_data()    ← seed_service loads sample_data/*.json into the DB
     │
     ├── _seed_customers()       reads customers.json  → CustomerRepository.create()
     ├── _seed_subscriptions()   reads subscriptions.json → Subscription rows
     ├── _seed_workspaces()      reads workspaces.json → Workspace rows
     ├── _seed_products()        reads products.json   → Product rows
     ├── _seed_incidents()       reads incidents.json  → Incident rows
     └── _seed_tickets()         reads tickets.json    → TicketRepository.create()
     │
     ▼
  API routes can now serve real data
  AI agents can now load customer context, search articles, etc.
```

---

## The two-database strategy

One of the smartest design decisions in Phase 2 is running two database systems simultaneously, without changing any application code:

| Setting | Database | Used for |
|---|---|---|
| Development / Demo | SQLite (a file: `data/support.db`) | Local development, `make backend`, demos |
| Production (Supabase) | PostgreSQL | Cloud deployment |
| Tests | SQLite (in a temp folder) | Offline pytest, deleted after each test run |

The application code never mentions "SQLite" or "PostgreSQL" directly. It only calls `get_session()`. Which database it gets is determined by the `DATABASE_URL` environment variable. This is the same "ports and adapters" principle from Phase 1 — the core logic is decoupled from the specific infrastructure choice.

---

## What Phase 2 does NOT include

- User authentication / login (Phase 3)
- HTTP API routes for tickets and customers (Phase 4)
- AI agents (Phase 9–11)
- Any frontend (Phase 12–13)

---

## In one sentence

> Phase 2 gives the application its data model and memory: 16 database tables, two-database portability, a repository layer for clean data access, 13 realistic demo tickets, 8 demo customers, and an idempotent auto-bootstrap that loads all sample data on first startup.
