# Phase 3 — Interview Q&A: Identity and Request Guards

> All possible interview questions from Phase 3, with clear answers suitable for technical and non-technical panels.

---

## Section 1: Authentication Fundamentals

**Q1. What is JWT and why did you choose it over session-based authentication?**

**A:** JWT stands for JSON Web Token. It is a small signed package of data — typically containing a user's ID, role, and expiry time — that the server gives to the client on login. The client then includes this token in every subsequent request.

We chose JWT over session-based auth because:
- **Stateless:** The server does not need to store session data. It just verifies the signature. This makes the API easy to scale horizontally (multiple server instances, no shared session store).
- **Self-contained:** The token includes the user's role, so authorisation decisions can be made without a database lookup on every request.
- **Standard:** JWT (RFC 7519) is widely understood and supported by tools like Supabase, Auth0, and frontend libraries.

The trade-off: if you need to revoke a token before it expires (e.g. a user is banned), you need extra infrastructure (a blocklist). We accepted this trade-off for v1 since the 8-hour expiry is short enough.

---

**Q2. What algorithm does the JWT use and why?**

**A:** We use **HS256** (HMAC with SHA-256). This is a symmetric algorithm — the same secret key is used to both sign and verify the token. It is simpler than RS256 (asymmetric), appropriate for a system where only one service both issues and verifies tokens. RS256 is better when multiple services need to verify tokens issued by a central auth service (they only need the public key). For our single-backend architecture, HS256 is the right choice.

---

**Q3. Where is the JWT secret stored and how is it protected?**

**A:** The secret is stored in the `.env` file, which is in `.gitignore` and is **never committed to the repository**. The `.env.example` file lists the variable with an empty value as a placeholder.

In code, the secret is read as a `SecretStr` from Pydantic Settings. When you print the settings object, the secret value appears as `**********` — it is never accidentally logged. The effective secret is only accessed via `settings.effective_jwt_secret` immediately before it is needed.

The Supabase service-role key (which bypasses all database security) is treated similarly — it is never returned to the browser.

---

**Q4. What is the difference between `get_current_user` and `require_role`?**

**A:**
- `get_current_user` answers **"who are you?"** — it decodes the JWT and returns the payload. If the token is missing or invalid, it raises HTTP 401 Unauthorized.
- `require_role("agent")` answers **"are you allowed?"** — it calls `get_current_user` first, then checks whether the user's role rank meets the minimum. If not, it raises HTTP 403 Forbidden.

A route that only needs to know who is logged in uses `Depends(get_current_user)`. A route that also enforces a minimum role uses `Depends(require_role("agent"))`.

---

**Q5. What are the three demo users and why do they exist?**

**A:** The three demo users cover all three role tiers:
- `admin@clouddesk.demo` — admin role (can do everything)
- `sam.agent@clouddesk.demo` — agent role (can run workflows, approve)
- `vic.viewer@clouddesk.demo` — viewer role (read-only)

They exist so a developer can immediately log in and test role-based behaviour without creating real users or configuring an identity provider. They are issued real 8-hour JWTs by the demo login endpoint. The test suite uses these same users (via `conftest.py` fixtures) to verify that a viewer genuinely cannot approve a refund.

---

## Section 2: Role-Based Access Control (RBAC)

**Q6. What is the role hierarchy and how is it enforced?**

**A:** There are three roles with a numeric rank:

| Role | Rank | Access |
|---|---|---|
| viewer | 1 | Read-only: tickets, customers, knowledge, audit |
| agent | 2 | Everything viewer + run workflows, approve/reject, escalate, reply |
| admin | 3 | Everything agent + reindex knowledge, settings |

Enforcement uses `_ROLE_RANK[user["role"]] >= _ROLE_RANK[minimum_role]`. An admin (rank 3) passes any check that requires agent (rank 2) or viewer (rank 1). The check is a single integer comparison — no complex permission tables.

---

**Q7. What happens if a viewer tries to approve a refund?**

**A:** The request is rejected at the dependency level before it reaches the route handler:
1. JWT is decoded → `role = "viewer"`, `rank = 1`
2. `require_role("agent")` → `required_rank = 2`
3. `1 < 2` → raise HTTP 403 Forbidden: *"Role 'viewer' cannot perform this action (requires 'agent')"*

The refund logic is never executed. This is tested in `test_viewer_receives_403_on_agent_route`.

---

**Q8. Why is 403 a different error from 401?**

**A:**
- **401 Unauthorized** means: *"I don't know who you are."* The request has no token, or the token is invalid/expired. The user needs to log in.
- **403 Forbidden** means: *"I know who you are, but you are not allowed to do this."* The token is valid, but the role is insufficient.

Sending 401 for a valid-but-insufficient token would be confusing — the user would think they need to log in again, when actually they just lack the permission. The correct code (403) tells the client to show an "access denied" message rather than a login redirect.

---

## Section 3: Rate Limiting

**Q9. How does the rate limiter work?**

**A:** We use a **fixed window** algorithm:

1. For each incoming request, extract the client's IP address from the ASGI scope.
2. Look up (or create) a Redis key `rate:<IP>` with a 60-second TTL.
3. Increment the counter using `redis.incr(key)`.
4. If the counter exceeds `RATE_LIMIT_PER_MINUTE` (default 120), return 429.
5. If the first request (counter was 1), set the TTL to 60 seconds with `redis.expire(key, 60)`.
6. After 60 seconds Redis automatically deletes the key, and the window resets.

**Limitation:** The fixed window has a "boundary burst" problem — a user could send 120 requests at the end of one window and 120 at the start of the next, effectively sending 240 in two seconds. For v1 this is acceptable; a sliding window or token bucket would solve it in a future phase.

---

**Q10. What is fakeredis and why is it used in tests?**

**A:** `fakeredis` is a Python library that provides the same interface as a real Redis client, but stores data entirely in memory within the Python process. No Redis server is needed.

It is used in tests because:
- Tests must run offline (no external services per CLAUDE.md §18 rule 7).
- It is configured via `USE_FAKE_REDIS=true` in `conftest.py`.
- The `get_redis_client()` factory in `core/redis.py` checks this setting and returns a `FakeRedis` instance instead of a real Redis connection.

The same code path runs in production with a real Redis server — just a different instance of the same interface. This is the "ports and adapters" pattern applied to the cache layer.

---

**Q11. What happens if Redis is unavailable?**

**A:** The rate limit middleware wraps the Redis call in a `try/except`. If Redis is unavailable or returns an error, the exception is swallowed silently and the request is **allowed through**. This is a deliberate "fail open" design — we prefer the app to work without rate limiting rather than taking the entire API down because Redis is unreachable. The trade-off: during a Redis outage, a flood attack could get through. For production, this should be monitored and a circuit breaker added.

---

## Section 4: Audit Logging

**Q12. What does the audit middleware log?**

**A:** For every **non-GET request** (POST, PUT, PATCH, DELETE), the middleware writes one row to `audit_logs` with:
- `actor_id`: the user's sub (from the JWT), or null if unauthenticated
- `actor_role`: the user's role (from the JWT)
- `action`: the HTTP method (POST, DELETE, etc.)
- `resource_type`: extracted from the URL path (e.g. `tickets` from `/api/v1/tickets/123`)
- `request_id`: the X-Request-ID header value (from RequestIdMiddleware)
- `ip_address`: the client's IP address
- `extra`: JSON blob with the full path and HTTP status code

GET requests are excluded because they are read-only and do not change state.

---

**Q13. Why does the audit middleware run after the response is sent?**

**A:** The audit middleware captures the response's status code (200, 201, 403, 500, etc.) and writes that into the log. This requires waiting until the response is complete. More importantly, the audit write happens asynchronously in a `finally`-equivalent block after `await self.app(scope, receive, send_capture)` completes — meaning the user has already received their response. This guarantees:

1. The audit write cannot slow down the user's response.
2. Even if the audit write fails (e.g. database is temporarily unavailable), the user's request still succeeds.

Telemetry and audit trails must never be in the critical path of user operations.

---

**Q14. What if the audit write fails?**

**A:** The exception is caught and logged at DEBUG level, then discarded. This is an intentional design decision: audit failures are non-fatal. The same philosophy applies to the workflow event tracer in Phase 9 — "telemetry must not break a run." In production, you would add a monitoring alert for sustained audit failures (e.g. if the database is full or the audit_logs table is locked), but individual failures should never crash the application.

---

## Section 5: Middleware Architecture

**Q15. What is middleware and why is the order important?**

**A:** Middleware is code that runs around every HTTP request and response, like layers of an onion. Each layer can inspect, modify, or short-circuit the request before passing it to the next layer.

The order matters because:
- **Audit must be outermost** to capture the final response status code (all inner layers have run).
- **Rate limit should run early** to reject floods before wasting work on request ID generation or CORS processing.
- **Request ID must run before the app** so that all application logs (and the audit log) share the same ID for the same request.
- **CORS must run closest to the app** to correctly add cross-origin headers to both normal and error responses.

Placing them in the wrong order would mean, for example, that audit logs have no request ID (if audit runs before RequestId), or that rate-limited responses don't get CORS headers (if CORS runs outside the rate limiter).

---

**Q16. How is the middleware order implemented in the code?**

**A:** Each middleware wraps the next by holding a reference to it:

```python
cors_app       = CORSMiddleware(app=api, ...)
request_id_app = RequestIdMiddleware(cors_app)
rate_limit_app = RateLimitMiddleware(request_id_app)
audit_app      = AuditMiddleware(rate_limit_app)
return audit_app
```

When the ASGI server calls `audit_app(scope, receive, send)`, the audit middleware calls `rate_limit_app(scope, receive, send)`, which calls `request_id_app`, and so on. This is the "chain of responsibility" design pattern.

---

## Section 6: Security Design

**Q17. What are the security rules your CLAUDE.md calls "§18.1 things that must never happen" related to Phase 3?**

**A:** The relevant prohibitions are:
1. **A viewer able to approve, reply, or run a workflow must return 403.** — Enforced by `require_role("agent")` on those routes, tested in `test_viewer_receives_403_on_agent_route`.
2. **No service-role secret returned to the client.** — The auth login response contains only `access_token`, `token_type`, and `role`. The Supabase service-role key is never sent to the browser.

---

**Q18. What is defence-in-depth and how does Phase 3 contribute to it?**

**A:** Defence-in-depth means layering multiple independent security controls so that no single failure exposes the system. Phase 3 adds three independent layers:

1. **JWT at the route level** — a request without a valid token never reaches business logic.
2. **Role checks at the dependency level** — a valid token with insufficient role is rejected before the handler runs.
3. **Rate limiting at the middleware level** — a flood of requests is blocked before even being parsed as a JWT.

Additionally, the Postgres RLS policies (from Phase 2) add a fourth layer at the database level — even if all three application layers are bypassed (e.g. by a bug), the database itself will reject unauthorised reads and writes.

---

**Q19. If someone captures a JWT token, can they impersonate the user forever?**

**A:** No, for two reasons:
1. **Expiry:** Tokens expire after 8 hours. After that, the signature is still valid but the `exp` claim check fails and `decode_token` raises 401.
2. **Secret rotation:** If the `JWT_SECRET` environment variable is changed and the server is restarted, all previously issued tokens become invalid immediately (the signature can no longer be verified).

For v1 this is sufficient. Production hardening would add a token blocklist (revocation list) for immediate invalidation on logout or account compromise.

---

**Q20. How do the tests verify that the security works?**

**A:** The test file `tests/api/test_auth.py` contains 11 tests covering:

| Test | What it proves |
|---|---|
| `test_missing_token_returns_401` | No token → 401 |
| `test_malformed_token_returns_401` | Garbage token → 401 |
| `test_agent_token_is_accepted` | Valid agent JWT → 200 |
| `test_viewer_receives_403_on_agent_route` | Viewer JWT on agent-only route → 403 |
| `test_admin_token_passes_agent_route` | Admin JWT on agent-only route → 200 (rank ≥ rank) |
| `test_demo_login_issues_token_for_known_user` | Login as agent → token + role returned |
| `test_demo_login_issues_token_for_admin` | Login as admin → role=admin |
| `test_demo_login_issues_token_for_viewer` | Login as viewer → role=viewer |
| `test_demo_login_rejects_unknown_user` | Unknown email → 401 |
| `test_non_get_request_writes_audit_log` | POST request → audit_logs row written |
| `test_service_role_key_not_in_login_response` | Login response has no service-role fields |

All 11 tests run offline (no network, no real Redis, no real DB server).

---

## Section 7: Architecture and Trade-offs

**Q21. Why is the rate limiter in middleware rather than in the route handlers?**

**A:** Rate limiting in middleware means the check happens once, transparently, for every route — including routes added in future phases. If it were in each route handler, every new route would need a copy of the rate-limiting code, and it would be easy to forget. Middleware is the correct layer for cross-cutting concerns (security, logging, rate limiting) that apply to all routes uniformly.

---

**Q22. Why are JWT tokens not stored in the database?**

**A:** Storing tokens in a database would reintroduce state to what is otherwise a stateless system, adding a DB lookup on every request. JWT's core advantage is that the server can verify identity using only the token and the secret — no I/O required. We only involve the database if we need to:
- Look up additional user profile data (which we do lazily, only when needed)
- Revoke tokens (which we have not implemented in v1)

---

**Q23. How does `effective_jwt_secret` work and why does it exist?**

**A:** `effective_jwt_secret` is a property on the `Settings` class that returns the first non-empty value from: `SUPABASE_JWT_SECRET` → `JWT_SECRET`. 

This exists because in Supabase production deployments, Supabase issues JWTs signed with its own secret (`SUPABASE_JWT_SECRET`). By checking Supabase's secret first, the application can verify both Supabase-issued tokens (production) and our own demo tokens (`JWT_SECRET`) with one code path. Switching from demo to Supabase production requires only setting one environment variable — no code changes.

---

**Q24. What would need to change to replace the demo login with real authentication?**

**A:** The demo login route (`POST /api/v1/auth/login`) would be replaced or supplemented with Supabase Auth. The rest of the security layer would not change:
- `decode_token` already uses `effective_jwt_secret`, which checks `SUPABASE_JWT_SECRET` first.
- `get_current_user` and `require_role` are independent of how the token was issued — they only care that the JWT has a valid signature and a `role` claim.
- The frontend would call Supabase's login endpoint instead of our `/auth/login`, then send the resulting Supabase JWT in the same `Authorization: Bearer` header.

This is the "open/closed principle" in practice — the security layer is open for extension (new auth providers) but closed for modification (existing route protection is unchanged).
