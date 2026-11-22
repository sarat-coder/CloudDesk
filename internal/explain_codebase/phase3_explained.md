# Phase 3 — Identity and Request Guards: Plain-English Explanation

> **Audience:** Anyone — including non-technical interviewers — who wants to understand what was built in Phase 3 and *why* it matters.

---

## Quick recap: Where we left off

At the end of Phase 2, the application had a working database, 16 tables, and 13 realistic demo tickets loaded automatically at startup. Any request to any endpoint would succeed — there was **no concept of "who are you?" or "are you allowed to do that?"**

**Phase 3 gives the application its security layer.** After Phase 3, only authenticated users can access protected parts of the system, and not every authenticated user can do everything — a viewer cannot approve a refund, only an agent or admin can.

---

## Why do we need identity and request guards?

Imagine you built a support platform but left the front door open. Anyone who knew the web address could:
- Read all your customers' ticket history
- Approve refunds without being a support agent
- Delete accounts without authorisation

That would be a serious security failure. Phase 3 closes that door. It adds four layers of protection, like security guards stationed at different checkpoints:

```
Internet
    │
    ▼
[Guard 1: Audit]           → Records WHAT happened (write to log)
    │
    ▼
[Guard 2: Rate Limiter]    → Stops floods of requests (spam / bots)
    │
    ▼
[Guard 3: Request ID]      → Tags every request with a unique tracking number
    │
    ▼
[Guard 4: CORS]            → Only allows browsers from approved websites
    │
    ▼
[FastAPI App]              → Routes protected by JWT + Role checks
```

---

## What was actually built? (Four tasks)

### Task P3-1 — JWT Authentication (`backend/app/core/security.py`)

**The problem it solves:** The server needs to verify "who are you?" for every request, without storing a session in memory or making a database call each time.

**What we built:**

The industry standard solution is called **JWT (JSON Web Token)**. Here is how it works in simple terms:

1. **Login:** The user sends their email (e.g. `sam.agent@clouddesk.demo`). The server creates a small signed "ticket" — a JWT — that says *"This is Sam. Sam is an agent. This ticket is valid for 8 hours."* The server signs this ticket with a secret key (like a wax seal on an envelope).

2. **Every subsequent request:** The user's browser sends the JWT along with every request (in the `Authorization: Bearer <token>` header). The server verifies the signature — if nobody tampered with it, the server trusts the claims inside. No database lookup needed.

3. **Expiry:** After 8 hours the token is invalid. The user must log in again.

**Key functions in `security.py`:**

| Function | What it does |
|---|---|
| `create_access_token(sub, role, name)` | Creates a signed JWT with the user's ID, role, and an 8-hour expiry |
| `decode_token(token)` | Verifies the signature and reads the claims. Raises 401 if invalid or expired. |
| `get_current_user(request)` | A FastAPI **dependency** — any route can declare `user = Depends(get_current_user)` and automatically get the logged-in user, or a 401 error if not logged in |
| `require_role("agent")` | A stricter version — only allows users whose role rank is ≥ the required level. Returns 403 Forbidden for viewers trying to do agent actions. |

**Role ranking (the numeric ladder):**

| Role | Rank | Can do |
|---|---|---|
| `viewer` | 1 | Read tickets, customers, knowledge, audit logs |
| `agent` | 2 | Everything viewer can + run workflows, approve/reject, escalate, reply |
| `admin` | 3 | Everything agent can + reindex knowledge, change settings |

A role check passes if `user's rank ≥ required rank`. So an admin can always do what an agent can do, and an agent can always do what a viewer can do.

**Demo login (`POST /api/v1/auth/login`):**

For the demo, three pre-made users exist:
- `admin@clouddesk.demo` → gets an admin token
- `sam.agent@clouddesk.demo` → gets an agent token
- `vic.viewer@clouddesk.demo` → gets a viewer token

No real passwords are involved — this is a demo system. In production, you would swap the login route for Supabase authentication.

---

### Task P3-2 — Rate Limiting (`backend/app/middleware/rate_limit.py`)

**The problem it solves:** Without rate limiting, a bot could send 10,000 requests per second and crash the server or rack up enormous AI costs.

**What we built:**

A "fixed window" rate limiter that counts how many requests each client (identified by IP address) has sent in the last 60 seconds. If they exceed the limit (`RATE_LIMIT_PER_MINUTE`, default 120), the server returns a **429 Too Many Requests** error and the request never reaches the app.

**How it uses Redis:**

Redis is an ultra-fast in-memory database. For each IP address:
1. First request: create a counter set to 1, with a 60-second expiry timer.
2. Each subsequent request: increment the counter.
3. If the counter exceeds the limit → return 429.
4. After 60 seconds: Redis automatically deletes the counter, and the window resets.

For tests, **fakeredis** is used — a fully in-memory fake version of Redis. No real Redis server is needed.

---

### Task P3-3 — Audit Logging (`backend/app/middleware/audit.py`)

**The problem it solves:** For compliance and debugging, every state-changing action must be recorded — who did what, when, to which resource, and with what result.

**What we built:**

An audit middleware that runs around every **non-GET** request (GET requests are read-only and do not need to be audited). After the request completes, it writes a row to the `audit_logs` database table containing:
- Who made the request (`actor_id`, `actor_role`)
- What they did (`action` = POST/PUT/DELETE)
- Which resource was affected (`resource_type` = extracted from the URL path)
- The request's tracking ID (`request_id`)
- The client's IP address
- The HTTP status code of the response

This is a **post-processing** step — the audit log is written *after* the response is sent to the user, so it cannot slow down or break the response. Even if the audit write fails (e.g. a database issue), the middleware catches the exception silently so the user's request still succeeds.

---

### Task P3-4 — Middleware Order (`backend/app/main.py`)

**The problem it solves:** The four middleware layers must wrap each other in the right order so that security guarantees are maintained.

**The documented order (outermost last: CORS → RequestId → RateLimit → Audit):**

```
Request enters:   Audit → RateLimit → RequestId → CORS → App
Response exits:   App → CORS → RequestId → RateLimit → Audit
```

Why this order?

| Layer | Runs before | Why first/last matters |
|---|---|---|
| Audit (outermost) | Everything | Sees the full response status code after all processing is done |
| RateLimit | RequestId, CORS, App | Stops flooded requests before wasting work assigning IDs |
| RequestId | CORS, App | Assigns the tracking ID before the app routes run, so all logs share the same ID |
| CORS (innermost) | App | Closest to the app, handles cross-origin headers for browsers |

---

## How these pieces connect

```
Browser sends POST /api/v1/tickets
            │
            ▼
        Audit middleware wraps everything
            │
            ▼
        RateLimit: IP has 45/120 requests this minute → allow
            │
            ▼
        RequestId: assigns "req-abc-123" to this request
            │
            ▼
        CORS: Origin is allowed
            │
            ▼
        FastAPI routes:
            └── Depends(require_role("agent"))
                    └── get_current_user: decodes JWT → user = {sub: "...", role: "agent"}
                    └── role check: agent rank 2 >= required rank 2 → ALLOW
            └── Route handler runs
            │
            ▼
        Response 200 sent back
            │
            ▼
        Audit middleware: writes to audit_logs (actor, action, path, status 200)
```

If `vic.viewer@clouddesk.demo` tries to approve a refund:

```
JWT decoded → role = "viewer" (rank 1)
require_role("agent") → required rank 2
1 < 2 → 403 Forbidden
```

The viewer never reaches the approval logic.

---

## The "no service-role key to the client" rule

The auth login endpoint returns exactly three fields:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "role": "agent"
}
```

The Supabase service-role key (which bypasses all database security) is **never** returned to the browser. It stays server-side only. This is enforced in code and verified by a test.

---

## What Phase 3 does NOT include

- A real Supabase/Google/email login flow (that would use Supabase Auth in production)
- IP blocking or geographic rate limiting
- API key authentication (for integrations — that comes with Phase 6)
- Frontend login page (that comes with Phase 12)

---

## In one sentence

> Phase 3 gives the application its security skeleton: JWT token authentication, role-based access control (viewer/agent/admin), a Redis-backed rate limiter, an audit log of every state-changing request, and the correct four-layer middleware order — so no unauthenticated or unauthorised action can reach the business logic.
