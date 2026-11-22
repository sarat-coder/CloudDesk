# Phase 12 — Agent Console: Plain-English Explanation

**Audience:** Interview board, including non-technical members.

---

## What Did We Build in Phase 12?

By the end of Phase 11, the CloudDesk platform had a fully working AI brain. It could investigate tickets, classify them, search a knowledge base, produce a resolution plan, pause for human approval, and escalate sensitive cases to specialist teams — all proved by automated tests running on a laptop with no internet connection.

But there was no **window into that brain**. Support agents had to interact with it through a command line or raw API calls. That is not a product.

**Phase 12 builds the agent console** — the web application that sits in front of everything we have built so far. It is the screen an actual support agent opens in their browser every morning.

Think of it this way:
- Phases 1–11 built the engine room of a ship.
- Phase 12 builds the bridge — the place where human crew members look at instruments, give commands, and steer.

---

## What Was Built — Four Tasks

### Task P12-1 — Next.js App Shell and Navigation

**Files created:**
- `frontend/package.json` — the list of software libraries the frontend needs
- `frontend/next.config.ts` — configuration for the Next.js framework
- `frontend/tsconfig.json` — TypeScript settings (TypeScript is a stricter, safer version of JavaScript)
- `frontend/tailwind.config.ts` — the design system (a utility-first CSS framework)
- `frontend/app/layout.tsx` — the outermost HTML wrapper every page shares
- `frontend/app/globals.css` — colour tokens for light and dark themes
- `frontend/components/layout/nav.ts` — the single source of truth for navigation items
- `frontend/components/layout/Sidebar.tsx` — the left-hand navigation bar

**What was decided:**

The navigation is **declared once** in `nav.ts` as a list of objects (`label`, `href`, `icon`). Every page picks up navigation from that list. If a nav item needs to be renamed or reordered, there is exactly one file to change — not eight pages.

The sidebar shows fewer items to viewers (no Settings) using an `adminOnly` flag. The role check happens at render time by reading the role the backend returned at login.

The colour scheme is built from **CSS variables** (`--bg`, `--fg`, `--brand`, etc.) defined on `:root`. Changing the brand colour across every page and component requires changing one value in one file.

---

### Task P12-2 — Typed API Client

**Files created:**
- `frontend/lib/api.ts` — the single place that talks to the backend
- `frontend/lib/hooks.ts` — React "hooks" for polling and auth state
- `frontend/lib/format.ts` — display formatting (dates, labels, currency)
- `frontend/lib/cn.ts` — a tiny utility for combining CSS class names

**What was decided:**

The backend is reached **only** through `lib/api.ts`. No page imports `fetch` directly. This means:

1. If the backend URL changes, one file changes, not dozens.
2. The 401 "session expired" redirect happens in one place and cannot be forgotten on a new page.
3. If the network is unavailable, the client waits one second and retries once automatically — defined once, applied everywhere.

The file exports grouped objects (`auth`, `tickets`, `customers`, `knowledge`, etc.) that mirror the backend API sections. Each function is typed end-to-end: TypeScript knows the exact shape of the response before you write a single line of UI code.

**`usePolling`** is a reusable hook that calls any async function on a timer and returns `{ data, error, loading }`. The ticket detail page uses a specialised version — `useWorkflowPolling` — that stops polling automatically once the workflow reaches a terminal state (completed, failed, or escalated), so the browser is not making unnecessary calls.

**`deriveSteps`** turns a `WorkflowState` object into a 12-item list of `{ id, label, status }` values that the workflow panel renders. Its logic is: if the node id is in `completed_nodes` → "done"; if it matches `current_node` → "running"; otherwise → "pending". This logic is pure JavaScript with no DOM, so it is easy to unit-test.

---

### Task P12-3 — Login and Role-Aware Layout

**Files created:**
- `frontend/app/login/page.tsx` — the demo login screen
- `frontend/middleware.ts` — the Next.js middleware that blocks unauthenticated navigation
- `frontend/app/(dashboard)/layout.tsx` — the shell that wraps all protected pages

**What was decided:**

**Login:**
The login page shows three buttons — one for each demo user (admin, agent, viewer). Clicking one calls the backend's `/auth/demo-login` endpoint, which returns a JWT (a digitally signed session token). The token is stored in `localStorage` (the browser's key-value store) and a short-lived cookie is set so the middleware can gate server-side route navigation.

There is no password entry. This is by design for the demo platform. In production, this page would be replaced by a real identity provider (SSO, Supabase Auth, etc.).

**Role-aware layout:**
The `(dashboard)/layout.tsx` file wraps every dashboard page. When it loads it checks for a token. If there is none, it redirects to `/login`. It reads the role from localStorage and passes it to the Sidebar component.

The role determines what the agent can do. A viewer cannot click "Run AI workflow", "Send reply", "Approve", or "Reject" — those buttons are either hidden or disabled with the `canAct` flag (`canAct = role === "agent" || role === "admin"`).

This is a **UI-layer gate** — a convenience, not a security boundary. The real security gate is the backend, which returns 403 Forbidden on those same actions if the caller's JWT carries the wrong role. The UI gate just makes the product feel correct to use.

---

### Task P12-4 — Read-Only List Pages

**Files created:**
- `frontend/app/(dashboard)/dashboard/page.tsx` — headline stats + recent tickets
- `frontend/app/(dashboard)/tickets/page.tsx` — paginated, filterable ticket list
- `frontend/app/(dashboard)/tickets/[id]/page.tsx` — three-column ticket detail screen
- `frontend/app/(dashboard)/customers/page.tsx` — customer list with search
- `frontend/app/(dashboard)/customers/[id]/page.tsx` — customer detail with ticket history and memory notes
- `frontend/app/(dashboard)/knowledge/page.tsx` — knowledge base article browser
- `frontend/app/(dashboard)/escalations/page.tsx` — escalation queue
- `frontend/app/(dashboard)/agents/page.tsx` — workflow node reference
- `frontend/app/(dashboard)/audit/page.tsx` — paginated audit log
- `frontend/app/(dashboard)/settings/page.tsx` — admin-only configuration

**UI kit components:**
- `StatusPill` — coloured badge for ticket status (new / in progress / escalated / resolved…)
- `SeverityPill` — coloured badge for severity (low / medium / high / critical)
- `EmptyState` — a consistent "nothing here yet" placeholder with optional action
- `Button` — a styled button with four variants (primary, secondary, ghost, danger)
- `Input` — a styled text input with an optional label
- `Card` — a bordered container with an optional title

**The ticket detail screen (the most important page):**

This is the page described in requirement F12. It is a **three-column grid**:

| Left column | Centre column | Right column |
|---|---|---|
| Message thread + reply composer | Customer info panel | AI workflow panel |

The workflow panel shows:
1. A 12-step progress tracker (each step is "pending", "running" with a pulse animation, or "done" with a green tick)
2. Classification result (category, summary, confidence)
3. Diagnosis (problem statement + troubleshooting steps)
4. Evidence (top 3 knowledge articles cited)
5. Resolution plan (summary + planned actions, with ⚠ on approval-required actions)
6. Token usage and estimated cost

The Approve and Reject buttons render **only** when `workflow.approval_status === "pending"` and the user's role is `agent` or `admin`. A viewer sees neither button.

The workflow panel polls the backend every 2 seconds while the workflow is running and stops automatically when it finishes.

---

## What Was Tested

| Test file | What it proves |
|---|---|
| `__tests__/StatusPill.test.tsx` | Each status value renders the correct human-readable label |
| `__tests__/EmptyState.test.tsx` | Title, description, and action render correctly |
| `__tests__/WorkflowSteps.test.ts` | `deriveSteps` correctly labels nodes as done/running/pending |
| `__tests__/api.test.ts` | `NetworkError` carries status and detail; 401 response throws `NetworkError` |

All tests run with Vitest (a fast, in-browser-compatible test runner) and do not require a running backend.

---

## The Viewer-Cannot-Act Rule Illustrated

If a viewer logs in and opens ticket CD-1002:
- They see the message thread and the customer panel.
- The workflow panel shows all 12 steps and the resolution plan.
- The Approve / Reject buttons **do not render** (`approval_status === "pending"` is true, but `canAct` is false for a viewer).
- The reply box and "Send reply" button are **not shown** (the `canAct` check gates the whole composer).
- If a viewer somehow crafts an API request to approve an action, the backend returns 403 Forbidden regardless.

---

## In One Sentence

> Phase 12 adds the full web console that support agents use: a Next.js 15 application with a typed API client, role-aware login, eight dashboard pages, a hand-written component kit, a three-column ticket screen with live workflow polling and conditional approve/reject controls, and a unit-tested `deriveSteps` function that maps the AI's progress to a visual 12-step tracker.
