# Phase 4 — Support API: Plain-English Explanation

> **Audience:** Anyone — including non-technical interviewers — who wants to understand what was built in Phase 4 and *why* it matters before the AI agents are switched on.

---

## What changed between Phase 3 and Phase 4?

After Phase 3 we had a locked door — the system could check your ID badge (JWT auth), limit how many times you could knock per minute (rate limiting), and write down everything you did (audit log). But the door had nothing interesting behind it. There were no tickets, no customers, no support data.

**Phase 4 opens the door and fills the room with real data.** Support agents can now create tickets, search them, look up customers, and see the full history of a customer's interactions — all through a proper HTTP API, with every permission rule still enforced.

---

## Why does an API layer matter?

Think of the system like a library:

- **The database (Phase 2)** is the stacks of shelves — every book is there but hidden in the back room.
- **The repository layer (Phase 2)** is the librarians who know where every book lives — you tell them what you need and they go get it.
- **The API layer (Phase 4)** is the front desk — the place where any visitor (a human at a browser, an AI agent, a mobile app) can walk up and ask for something in a standard way.

Without the front desk, every part of the system would have to know the internal shelf numbering scheme. With it, everyone speaks the same language: HTTP requests and JSON responses.

---

## What was actually built? (Three tasks)

### Task P4-1 — API Contract Document

**The problem it solves:** When a frontend developer is building the ticket screen, they need to know *exactly* what data to expect — what fields, what types, what error codes. Without a written agreement, the backend and frontend drift apart and break each other's code.

**What was done:**
- `docs/API_CONTRACT.md` was verified and completed. It is the single source of truth for every route and type.
- `frontend/lib/types.ts` was written from the contract. These TypeScript type definitions ensure the browser-side code and the server-side code describe the same shapes.

**Simple analogy:** This is like writing the menu before opening a restaurant. The kitchen (backend) and the waitstaff (frontend) both read the same menu. Nobody improvises.

---

### Task P4-2 — Ticket API

**The problem it solves:** Support agents need a way to create tickets (from email, chat, web, or API calls) and retrieve them. The AI agents in later phases will also query this API to understand what problem they are solving.

**What was done:**

| Route | What it does |
|-------|-------------|
| `POST /api/v1/tickets` | Create a new ticket; also saves the customer's first message automatically |
| `GET /api/v1/tickets` | List tickets; filterable by status, severity, or free-text search; paginated |
| `GET /api/v1/tickets/{id}` | Get one ticket in full detail — messages, customer info, subscription, history, workflow state |
| `PATCH /api/v1/tickets/{id}` | Update a ticket's status, severity, or assignee |
| `POST /api/v1/tickets/{id}/reply` | Add an agent's reply message |
| `POST /api/v1/tickets/{id}/request-info` | Ask the customer a question; sets ticket to "waiting on customer" |
| `POST /api/v1/tickets/{id}/run` | Placeholder that returns 409 if already waiting on approval (workflow starts in Phase 10) |

**Permission rules enforced:**
- Any logged-in user (viewer, agent, admin) can **read** tickets.
- Only agents and admins can **write** (create, update, reply). A viewer gets HTTP 403.

**How a ticket number is generated:**
The system counts existing tickets and generates `CD-1001`, `CD-1002`, etc. — matching the demo scenario perfectly. The seed data already has CD-1001 through CD-1013, so new tickets continue at CD-1014 and beyond.

**Three-layer flow for creating a ticket:**
```
POST /api/v1/tickets
     ↓
tickets.py router  ← validates input, checks auth
     ↓
ticket_service.py  ← checks customer exists, generates ticket number, creates ticket + first message
     ↓
TicketRepository   ← writes to database
```

---

### Task P4-3 — Customer API

**The problem it solves:** When an agent opens a ticket, they need to see who the customer is — their name, company, subscription plan, workspace details, and all their previous tickets. This context is essential before diagnosing a problem.

**What was done:**

| Route | What it does |
|-------|-------------|
| `GET /api/v1/customers` | List customers with optional name/email search; paginated |
| `GET /api/v1/customers/{id}` | Get one customer's full profile — subscription, workspace, ticket history, memory notes |

**What is in a "customer detail"?**
- **Basic info:** name, email, company, plan (free/pro/business/enterprise), account status
- **Subscription:** how many seats, billing cycle, renewal date, amount
- **Workspace:** storage usage, region, member count
- **Ticket history:** all past tickets for this customer
- **Memory notes:** notes the AI wrote in previous runs (this will be populated in Phase 11)

**Simple analogy:** Imagine a doctor's office. When a patient walks in, the doctor does not start from zero — they open the patient's file: past visits, prescriptions, allergies. The customer detail endpoint is that patient file for a support agent.

---

## What else was added?

### Stub endpoints for future phases

Three additional minimal routes were added so the system does not return 404 when the frontend calls them:

- `GET /api/v1/dashboard/summary` — returns ticket counts (Phase 9 will add full metrics).
- `GET /api/v1/escalations` — returns an empty list (Phase 10 will fill it).
- `GET /api/v1/settings` — returns the current app configuration (useful for the settings page).

### A new session dependency

Under the hood, all API routes now use a FastAPI-compatible database session helper (`get_db`). This is a small but important plumbing change: it ensures each HTTP request gets its own database connection that is automatically committed when the request succeeds and rolled back if anything goes wrong — with no extra code in the route handlers.

---

## How does the system look now?

Here is a simplified map of what an HTTP request goes through:

```
Browser / Test
    │
    ▼
FastAPI (main.py)
    │   CORS → RequestId → RateLimit → Audit middleware
    ├─── /api/v1/auth/...        ← Phase 3
    ├─── /api/v1/tickets/...     ← Phase 4 (NEW)
    ├─── /api/v1/customers/...   ← Phase 4 (NEW)
    ├─── /api/v1/dashboard/...   ← Phase 4 stub (NEW)
    ├─── /api/v1/escalations/... ← Phase 4 stub (NEW)
    ├─── /api/v1/settings/...    ← Phase 4 (NEW)
    ├─── /health/...             ← Phase 1
    │
    ▼
Services layer   (ticket_service.py, customer_service.py)
    │
    ▼
Repository layer (TicketRepository, CustomerRepository, …)
    │
    ▼
SQLite / PostgreSQL database
```

---

## What does "validated locally" mean?

It means 74 automated tests ran on a laptop with no internet connection and no AI API key, and all 74 passed. No paid cloud services. No deployment. The tests cover:

- Creating tickets via all four channels (email, chat, web, API).
- Getting CD-1001 through CD-1013 from the seeded database.
- Verifying that a viewer gets 403 when trying to create a ticket.
- Verifying that a 404 is returned for a nonexistent ticket or customer.
- Verifying that a 409 is returned when you try to run the AI workflow on a ticket already waiting for human approval.
- Fetching a customer's detail including subscription, workspace, and ticket history.

---

## What is NOT done yet?

- The AI workflow does not run yet (Phase 9–10).
- The human approval flow does not exist yet (Phase 10).
- The frontend pages are not built yet (Phase 12).
- Memory notes in customer details are always empty (Phase 11).
- Escalation records are not yet written (Phase 10).

The system is a fully functional CRUD API for tickets and customers. The intelligence comes later.
