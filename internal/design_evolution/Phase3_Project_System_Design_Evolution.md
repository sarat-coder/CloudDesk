# Phase 3 — System Design Evolution: Identity and Request Guards

> This document traces how the system design evolved through Phase 3, from the starting point (after Phase 2) to the final state with a full security layer.

---

## Starting point: Phase 2 system (what we had before Phase 3)

At the end of Phase 2, the system had a FastAPI backend with health routes, database persistence, and demo data loading. But there was **no identity layer** — any HTTP call worked regardless of who sent it.

```mermaid
graph LR
    Browser["Browser / Client"] -->|"Any HTTP request"| Middleware["CORS + RequestId\nMiddleware"]
    Middleware --> FastAPI["FastAPI App\n(Health routes only)"]
    FastAPI --> DB["SQLite / PostgreSQL\n(16 tables, 13 tickets)"]
```

**Problem:** No authentication. No authorisation. No rate limiting. No audit trail.

---

## Step 1: Adding JWT authentication (P3-1)

The first design decision: **how should identity work?**

We chose **stateless JWT authentication** (not session-based). The server signs a token when the user logs in. That token travels with every request. The server verifies the signature — no database lookup per request.

```mermaid
sequenceDiagram
    participant Browser
    participant Server
    participant DB

    Browser->>Server: POST /api/v1/auth/login {"email": "sam.agent@clouddesk.demo"}
    Server->>Server: Look up demo user → role=agent
    Server->>Server: Create JWT: {sub, role, exp=+8h}, sign with JWT_SECRET
    Server-->>Browser: {"access_token": "eyJ...", "role": "agent"}

    Browser->>Server: POST /api/v1/tickets (Authorization: Bearer eyJ...)
    Server->>Server: Verify JWT signature → extract {sub, role}
    Server->>Server: require_role("agent") → rank 2 ≥ 2 → allow
    Server->>DB: write ticket
    Server-->>Browser: 201 Created
```

**Key design:** The JWT claim `role` determines what the user can do. The numeric rank (viewer=1, agent=2, admin=3) means admin can do anything agent can do, and agent can do anything viewer can do — a clean hierarchy.

---

## Step 2: Adding role-based access control (P3-1 continued)

The `require_role` function acts as a **permission gate** on any route. The route declares what it needs; FastAPI enforces it via the dependency injection system.

```mermaid
graph TD
    Request["HTTP Request\n(Bearer token)"] --> GetUser["get_current_user()\n- extract Bearer token\n- verify JWT signature\n- return payload"]
    GetUser -->|401 if missing/invalid| Error401["401 Unauthorized"]
    GetUser --> RequireRole["require_role('agent')\n- check user.role rank\n- rank >= required?"]
    RequireRole -->|403 if rank too low| Error403["403 Forbidden"]
    RequireRole -->|pass| RouteHandler["Route Handler\n(business logic)"]
```

**Example — viewer trying to approve a refund:**

```mermaid
graph LR
    Vic["vic.viewer\n(rank 1)"] -->|POST /approvals/123/approve| Check["require_role('agent')\nrequired rank = 2"]
    Check -->|"1 < 2"| Reject["403 Forbidden\n'Role viewer cannot perform\nthis action'"]
```

---

## Step 3: Adding rate limiting (P3-2)

Rate limiting uses Redis as a shared counter. Each IP gets a fixed-window counter.

```mermaid
graph TD
    Request["Incoming Request\n(IP: 203.0.113.42)"] --> RateCheck["RateLimitMiddleware\nkey = 'rate:203.0.113.42'"]
    RateCheck -->|"redis.incr(key)\ncount = 45"| CountCheck{"count > 120?"}
    CountCheck -->|No| Continue["Pass to next middleware"]
    CountCheck -->|Yes| Block["429 Too Many Requests\n'Rate limit exceeded'"]
    Continue --> App["FastAPI App"]
```

**Redis data model:**

```
Key:   rate:203.0.113.42
Value: 45          (integer counter)
TTL:   60 seconds  (auto-expires, window resets)
```

For tests: `fakeredis` replaces Redis entirely — same interface, runs in memory.

---

## Step 4: Adding audit logging (P3-3)

The audit middleware wraps the entire request-response lifecycle and writes a log entry *after* the response is sent — so the audit write cannot delay or fail the user's response.

```mermaid
sequenceDiagram
    participant Client
    participant AuditMiddleware
    participant App

    Client->>AuditMiddleware: POST /api/v1/tickets
    AuditMiddleware->>App: forward request (captures response_status[])
    App-->>AuditMiddleware: response (status=201)
    AuditMiddleware-->>Client: response forwarded immediately
    AuditMiddleware->>DB: INSERT INTO audit_logs (actor, action, path, status=201, request_id)
    Note over AuditMiddleware,DB: Failure here is swallowed — user already got their response
```

**Audit log columns:**

| Column | Value example |
|---|---|
| actor_id | "demo-agent-001" (from JWT sub claim) |
| actor_role | "agent" |
| action | "POST" |
| resource_type | "tickets" (extracted from path) |
| request_id | "req-abc-123" (from X-Request-ID header) |
| ip_address | "203.0.113.42" |
| extra | {"path": "/api/v1/tickets", "status_code": 201} |

---

## Step 5: Final middleware stack (P3-4)

The four middleware layers are assembled in a specific order. This is the final architecture for Phase 3:

```mermaid
graph TD
    Internet["Internet / Client"] --> Audit["AuditMiddleware\n(outermost)\n- POST after response"]
    Audit --> RateLimit["RateLimitMiddleware\n- 429 if > 120 req/min\n- uses Redis/fakeredis"]
    RateLimit --> RequestId["RequestIdMiddleware\n- assigns X-Request-ID\n- stamps all logs"]
    RequestId --> CORS["CORSMiddleware\n- checks Origin header\n- adds CORS response headers"]
    CORS --> FastAPI["FastAPI App\n- auth router (/api/v1/auth/login)\n- health routes\n- protected routes (Depends)"]
    FastAPI --> Security["security.py\nget_current_user + require_role"]
    FastAPI --> DB["SQLite / PostgreSQL\n(16 tables + audit_logs)"]
    FastAPI --> Redis["Redis / fakeredis\n(rate limit counters)"]
```

---

## Complete Phase 3 system: before vs. after

### Before Phase 3

```mermaid
graph LR
    Anyone["Anyone\n(no credentials needed)"] -->|"Any request"| App["FastAPI\n(health + DB)"]
    App --> DB["Database"]
```

### After Phase 3

```mermaid
graph TD
    User["Authenticated User\n(Bearer JWT)"] -->|"Request"| Audit["Audit\n(log all mutations)"]
    Audit --> RL["Rate Limit\n(≤120 req/min)"]
    RL --> RID["Request ID\n(tracing)"]
    RID --> CORS["CORS\n(browser security)"]
    CORS --> Auth{"JWT Valid?\nRole rank OK?"}
    Auth -->|No| Reject["401 / 403"]
    Auth -->|Yes| App["Route Handler\n(business logic)"]
    App --> DB["Database"]

    Bot["Bot / Attacker\n(no token or too many requests)"] -->|"Flood or no token"| RL
    RL -->|">120 req/min"| Block429["429 Too Many Requests"]
```

---

## New files added in Phase 3

| File | Purpose |
|---|---|
| `backend/app/core/security.py` | JWT create/decode, `get_current_user`, `require_role`, demo_login |
| `backend/app/core/redis.py` | Redis or fakeredis client factory |
| `backend/app/api/__init__.py` | API package init |
| `backend/app/api/auth.py` | `POST /api/v1/auth/login` route |
| `backend/app/middleware/rate_limit.py` | Fixed-window rate limiter |
| `backend/app/middleware/audit.py` | Post-request audit log writer |
| `backend/app/repositories/profile_repository.py` | Profile DB queries |
| `backend/app/repositories/audit_repository.py` | Audit log DB queries |
| `tests/api/test_auth.py` | 11 auth tests (401, 403, demo login, audit log) |

---

## In one sentence

> Phase 3 transformed the application from an open system into a secured one by adding JWT-based identity, a three-tier role hierarchy, Redis-backed rate limiting, post-request audit logging, and a carefully ordered four-layer middleware stack that processes every request before the business logic runs.
