# Phase 12 — Agent Console: Interview Questions and Answers

**Audience:** Technical and non-technical interviewers. Covers system design, frontend architecture, security, testing, and product thinking.

---

## Section 1 — What was built and why

**Q1. What is the agent console and who uses it?**

The agent console is the web application that human support agents open in their browser to handle customer tickets. It connects to the AI backend built in Phases 1–11. Before Phase 12 there was no UI — agents had to use API tools or a command-line script. The console makes the AI-powered workflow accessible to non-technical support staff.

---

**Q2. Why Next.js 15 specifically? What does "App Router" mean?**

Next.js is a React framework built on top of Node.js. The App Router (introduced in Next.js 13 and the default in 15) organises pages by filesystem: a file at `app/(dashboard)/tickets/page.tsx` becomes the route `/tickets`. It supports server components (components that render on the server), client components (the `"use client"` directive), and layouts that wrap groups of pages without re-rendering the shared shell.

The App Router was chosen because it enables the `output: "standalone"` mode needed for Docker images, and because its file-based routing avoids manual route configuration.

---

**Q3. Why is there a separate frontend process? Why not serve the UI from FastAPI?**

Three reasons:
1. **Separation of concerns** — FastAPI is Python; the UI is TypeScript/React. Keeping them separate means each can be built, tested, and deployed independently.
2. **Developer experience** — Next.js provides fast hot-reloading during development. If the UI were bundled into FastAPI, every frontend change would require restarting a Python server.
3. **Production architecture** — In a real deployment, the Next.js container can be CDN-cached or served by a static host, while the FastAPI container handles only API traffic. This is a common and scalable pattern.

---

## Section 2 — Architecture decisions

**Q4. Why is the backend only reachable through `lib/api.ts`? Why not call `fetch` directly in each page?**

Having a single API client layer gives you three things you cannot easily add later:

1. **A universal 401 handler** — When a session expires, every API call automatically redirects to `/login?reason=expired`. If `fetch` were called directly in 20 pages, this logic would need to be duplicated 20 times.
2. **A universal retry** — Network blips cause the client to wait one second and retry once. Again, this is in one place.
3. **Type safety** — The client functions return typed responses. TypeScript knows the exact shape of a `TicketDetail` object before you write a single render statement.

---

**Q5. What is `NEXT_PUBLIC_API_URL` and why does it matter for Docker?**

It is an environment variable that tells the browser-side code where the backend API lives (e.g. `http://localhost:8000`). In Next.js, variables prefixed with `NEXT_PUBLIC_` are **baked into the JavaScript bundle at build time**. This means:

- In development: `http://localhost:8000`
- In Docker Compose: `http://backend:8000` (the container service name)
- In production: `https://api.yourdomain.com`

Because the value is baked in at build time, the Docker image must be rebuilt for each environment. You cannot change it at runtime by injecting an environment variable — the value is already compiled into the JavaScript files.

---

**Q6. Why are there two session storage mechanisms (localStorage and a cookie)?**

`localStorage` is only accessible in the browser (client-side code). The JWT token is stored there because it is read by the `lib/api.ts` client, which runs in the browser.

The Next.js middleware runs on the **server** (or at the CDN edge) before the page is rendered. It cannot read `localStorage`. Cookies are sent on every HTTP request automatically, so the middleware can read a cookie to decide whether to redirect to `/login`.

The `cd_session` cookie contains only a boolean flag — not the JWT itself. The real authentication check is performed by the FastAPI backend on every API call. The cookie is just a UX mechanism to avoid unnecessary server renders of protected pages.

---

**Q7. How does the `deriveSteps` function work?**

It takes a `WorkflowState` object (or null) and returns a list of 12 step objects, each with `{ id, label, status }`. The status logic is:

1. If the node's `id` is in `workflow.completed_nodes` → `"done"`
2. Else if `workflow.current_node === id` → `"running"`
3. Otherwise → `"pending"`

This is pure JavaScript with no DOM interaction, which makes it trivial to unit-test without a browser. The 12 step IDs are ordered to match the actual graph execution order, so the visual progress tracker always moves top-to-bottom.

---

## Section 3 — Security and roles

**Q8. How does the role-aware UI work? What prevents a viewer from approving a ticket?**

There are two layers of protection:

**Layer 1 — Frontend (UX convenience):**
After login, the backend returns the user's role alongside the JWT. The role is stored in `localStorage`. The `useAuth()` hook reads it and computes `canAct = role === "agent" || role === "admin"`. Components that perform consequential actions (Approve, Reject, Send reply, Run AI workflow) are gated on `canAct`. When `canAct` is false, those elements are disabled or not rendered at all.

**Layer 2 — Backend (real security boundary):**
Every mutating API endpoint (`/run`, `/reply`, `/approvals/{id}/approve`, etc.) has `require_role("agent")` on the route handler. If a viewer's JWT is used to call one of these endpoints — even if they bypass the UI using curl — the backend returns 403 Forbidden. The frontend check is for a good user experience; the backend check is what actually enforces the policy.

---

**Q9. The service-role key is mentioned in CLAUDE.md as something that must never reach the frontend. Where is this enforced?**

Structurally. The Next.js application does not connect to the database, Redis, or the vector store. It only calls the FastAPI REST API. The service-role key (the database admin credential) lives only in the backend's `.env` file and is used only by SQLAlchemy and the seed service. There is no code path in the frontend that imports or references it. Even if the Next.js container were compromised, it could not expose the service-role key because it has never been given it.

---

**Q10. What is the `cd_session` cookie's `SameSite=Lax` setting and why does it matter?**

`SameSite=Lax` means the cookie is sent on same-site requests and on top-level cross-site navigations (e.g., clicking a link from another website), but not on cross-site sub-requests (e.g., images, iframes, fetch calls from another origin). This protects against CSRF (Cross-Site Request Forgery) attacks, where a malicious website tricks the user's browser into making requests to CloudDesk with their credentials. Because the cookie is `Lax` and not `None`, it cannot be sent in a cross-site fetch, so a CSRF attack using the cookie alone would fail.

---

## Section 4 — Testing

**Q11. How are the frontend tests structured? What do they test?**

There are four test files:

| File | What it tests |
|---|---|
| `StatusPill.test.tsx` | Renders each status value and checks the human-readable label appears |
| `EmptyState.test.tsx` | Title, description, and optional action node all render correctly |
| `WorkflowSteps.test.ts` | `deriveSteps` correctly labels nodes as done/running/pending for various workflow states |
| `api.test.ts` | `NetworkError` carries the right status and detail; a 401 HTTP response throws `NetworkError` |

The tests use **Vitest** (a fast test runner compatible with Jest's API) and **Testing Library** (a library for rendering React components and querying the DOM by accessible attributes like text content and role). They run in jsdom — a simulated browser environment — so no real browser or backend is needed.

---

**Q12. Why test `deriveSteps` as a pure function rather than testing the React component that renders the steps?**

Because `deriveSteps` contains the interesting logic (the state-to-status mapping), while the React component is just a loop that renders what `deriveSteps` returns. Testing the pure function:

- Is faster (no DOM setup required)
- Is easier to read (inputs and outputs are plain JavaScript)
- Gives clearer error messages when it fails

If the pure function tests pass, the component is correct by construction. This pattern — push logic into pure functions, keep components dumb — is a core principle of React architecture.

---

**Q13. What does the `api.test.ts` test actually verify?**

It verifies two things:

1. The `NetworkError` class is correctly structured — it stores the HTTP status code and the error detail string, extends `Error`, and has the right `.name`.
2. When the backend returns a 401 response, the `auth.me()` function throws a `NetworkError` (not silently swallowing the error or returning null).

The second test uses `vi.fn()` to mock the global `fetch` function, returning a fake 401 response. This isolates the test from the network — no backend needs to be running.

---

## Section 5 — Product and UX thinking

**Q14. The ticket detail page has three columns. What is in each one and why that layout?**

| Column | Contents | Why |
|---|---|---|
| Left | Message thread + reply composer | This is the core of a support ticket — the conversation. It needs the most horizontal space. |
| Centre | Customer panel (name, subscription, escalation if any) | Context the agent needs to understand the customer without leaving the screen. Narrow because the data is concise. |
| Right | AI workflow panel (12-step tracker, evidence, diagnosis, resolution plan) | The AI's work product. The agent reads it to decide whether to approve, edit, or reject the AI's proposal. Narrow-ish to stay out of the way if the agent is composing a reply. |

---

**Q15. Why does polling stop automatically instead of running forever?**

The `useWorkflowPolling` hook checks the `workflow.status` field after each poll. If it is `"completed"`, `"failed"`, or `"escalated"`, it cancels the interval and stops making requests. This:

- Reduces backend load (no more requests after the workflow is done)
- Avoids the React warning about state updates on unmounted components
- Gives the browser a break from network activity once the work is done

---

**Q16. Why is the reply composer pre-filled with the AI's suggested customer response?**

The resolution plan returned by the AI includes a `customer_response` field — a draft reply that cites the evidence and applies the troubleshooting steps. This becomes the `placeholder` text in the reply textarea. The agent can:

- Use it as-is by typing nothing (the placeholder shows what will be sent)
- Edit it by typing in the box
- Discard it and write something completely different

The AI suggestion reduces the agent's effort. The human always sends the reply — the AI never sends it directly. This satisfies requirement F9 (consequential actions need human approval) as it applies to customer communication.

---

## Section 6 — Difficult questions

**Q17. The Next.js middleware uses a plain cookie with no token value. Couldn't someone just set that cookie manually and bypass the login?**

Yes — the middleware is not a security gate. It is a UX gate that prevents an unauthenticated page load from briefly rendering before the client-side redirect fires. Someone who sets the cookie manually would reach the dashboard page, which would then try to fetch data from the backend with no JWT. The backend would return 401, and the `lib/api.ts` client would redirect them to `/login?reason=expired`. So the cookie bypass gains nothing.

The real authentication is JWT-based on the backend. Every API request is independently authenticated. There is no session on the server side that the cookie represents.

---

**Q18. What is `output: "standalone"` in next.config.ts and why is it needed for Docker?**

`output: "standalone"` tells the Next.js build to produce a self-contained directory that includes only the files needed to run the production server, with no reference to `node_modules` in the project root. This makes the Docker image significantly smaller because it only copies the standalone output, not the entire `node_modules` tree (which can be hundreds of megabytes). The standalone output includes the minimal Node.js server and all required dependencies in a single directory.

---

**Q19. What happens to localStorage in a private/incognito window?**

`localStorage` in a private window is isolated from regular windows and cleared when the private window is closed. The `lib/api.ts` client wraps every `localStorage` access in a try/catch because `localStorage` can throw in certain environments (some privacy-hardened browsers, some embedded contexts). If the read throws, the function returns `null`, and the API call proceeds without an auth header, which the backend treats as unauthenticated (401 → redirect to login).

---

**Q20. The phase builds a "read-only list pages" task. But the ticket detail page has Approve, Reject, and Send Reply buttons. Is it really read-only?**

No — the naming in the TASKS.md task title refers to the data being read-only for viewers, and to the fact that the list pages (tickets, customers, knowledge, etc.) themselves perform no mutations. The ticket detail page is an action page. The "read-only" in the task title was scoping the list pages (dashboard, /tickets, /customers, /knowledge, /escalations, /agents, /audit, /settings) as displaying-only, while the ticket detail page was the action screen developed alongside them as part of the same phase.
