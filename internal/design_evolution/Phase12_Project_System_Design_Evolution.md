# Phase 12 — System Design Evolution: Agent Console

This document traces how the system design grew during Phase 12, from "AI backend with no UI" to "fully navigable web console."

---

## Starting point: What existed before Phase 12

After Phase 11, the system looked like this:

```mermaid
graph LR
    Dev[Developer / cURL] -->|REST| Backend[FastAPI :8000]
    Backend --> DB[(SQLite)]
    Backend --> Redis[(fakeredis)]
    Backend --> VS[(In-memory vector store)]
    Backend --> LangGraph[LangGraph workflow]
```

There was no browser-facing layer. Only developers or the demo script could trigger workflows.

---

## Step 1 — Adding a Next.js skeleton (P12-1)

The first step was to create an empty Next.js project and wire it to the backend through an environment variable.

```mermaid
graph LR
    Browser[Browser :3000] -->|Next.js App Router| Pages[Pages]
    Pages -->|NEXT_PUBLIC_API_URL| Backend[FastAPI :8000]
    Backend --> DB[(SQLite)]
    Backend --> LangGraph[LangGraph workflow]
```

**Key design decision:** Next.js 15 with the App Router was chosen because it supports server components, file-based routing, and the `standalone` output mode needed for the Docker image. The frontend communicates with the backend over REST — it does not connect directly to the database, Redis, or the vector store. The backend is the only entry point.

---

## Step 2 — Typed API client layer (P12-2)

Before writing any pages, a typed client layer was introduced. This is the layer that every page talks to — no page imports `fetch` directly.

```mermaid
graph TD
    Page[React Page Component]
    Page --> ApiClient["lib/api.ts (typed client)"]
    ApiClient -->|Bearer JWT| Backend[FastAPI :8000]
    ApiClient -->|401 response| Redirect[Redirect to /login]
    ApiClient -->|Network error| Retry[Auto-retry once]

    subgraph Utilities
        Hooks["lib/hooks.ts (usePolling, useAuth, deriveSteps)"]
        Format["lib/format.ts (statusLabel, formatDate, etc.)"]
        Cn["lib/cn.ts (className combiner)"]
    end

    Page --> Hooks
    Page --> Format
```

**Key design decision:** The API client is grouped by domain (`auth`, `tickets`, `customers`, etc.) matching the backend router groups. This means adding a new backend endpoint requires editing one object in `api.ts` and one TypeScript interface in `types.ts` — both files are in the same `lib/` folder. The contract stays in sync.

The `usePolling` hook encapsulates the interval/cleanup pattern. The specialised `useWorkflowPolling` stops polling automatically on terminal states, avoiding wasted network calls after the workflow finishes.

---

## Step 3 — Authentication and role-aware layout (P12-3)

A login page and a Next.js middleware were added to gate all dashboard routes.

```mermaid
graph TD
    Browser -->|GET /dashboard| Middleware[middleware.ts]
    Middleware -->|No cd_session cookie| LoginPage[/login]
    Middleware -->|Cookie present| DashboardLayout["(dashboard)/layout.tsx"]
    DashboardLayout -->|Reads localStorage role| Sidebar[Sidebar component]
    DashboardLayout --> PageContent[Page content]

    LoginPage -->|POST /auth/demo-login| Backend[FastAPI :8000]
    Backend -->|{access_token, user}| LoginPage
    LoginPage -->|Writes localStorage| Browser
    LoginPage -->|Sets cd_session cookie| Browser
```

**Key design decision:** The session is stored in two places — a JWT in `localStorage` for API calls, and a plain cookie (`cd_session`) for the Next.js middleware. This is because `localStorage` is inaccessible to server-side code (the middleware runs on the server), while cookies are sent on every request automatically.

The role is derived client-side from `localStorage.role`. The `canAct` flag (`role === "agent" || role === "admin"`) is computed once in `useAuth()` and used by every action button to decide whether to render as enabled or disabled (or not at all).

---

## Step 4 — Read-only list pages and the ticket detail screen (P12-4)

This step added all eight dashboard pages and the UI kit.

```mermaid
graph TD
    subgraph Dashboard Pages
        DP[/dashboard]
        TP[/tickets]
        TD["/tickets/[id]"]
        CP[/customers]
        CD["/customers/[id]"]
        KP[/knowledge]
        EP[/escalations]
        AP[/agents]
        AuP[/audit]
        SP[/settings]
    end

    subgraph UI Kit
        StatusPill
        SeverityPill
        EmptyState
        Button
        Input
        Card
    end

    TD -->|polls every 2s| WorkflowState[WorkflowState API]
    TD -->|deriveSteps| WorkflowPanel[12-step tracker]
    TD -->|canAct=true| ApproveReject[Approve / Reject buttons]
    TD -->|canAct=false| ViewOnly[Buttons hidden / disabled]
```

---

## Final system design after Phase 12

```mermaid
graph TB
    Browser["Browser (agent/viewer)"]

    subgraph Frontend["Frontend — Next.js :3000"]
        Middleware["middleware.ts (auth gate)"]
        LoginPage["/login page"]
        DashLayout["(dashboard)/layout.tsx"]

        subgraph Pages
            Dashboard["/dashboard"]
            Tickets["/tickets"]
            TicketDetail["/tickets/[id] — three-column screen"]
            Customers["/customers[/id]"]
            Knowledge["/knowledge"]
            Escalations["/escalations"]
            Agents["/agents"]
            Audit["/audit"]
            Settings["/settings (admin only)"]
        end

        subgraph UIKit["UI Kit (components/ui/)"]
            StatusPill
            SeverityPill
            EmptyState
            Button
            Input
            Card
        end

        subgraph Lib["Lib (lib/)"]
            ApiClient["api.ts — typed REST client"]
            Hooks["hooks.ts — usePolling, useAuth, deriveSteps"]
            Format["format.ts — labels, dates, currency"]
            Types["types.ts — TypeScript types"]
        end
    end

    subgraph Backend["Backend — FastAPI :8000"]
        Auth["/auth"]
        TicketsAPI["/tickets"]
        CustomersAPI["/customers"]
        KnowledgeAPI["/knowledge"]
        EscalationsAPI["/escalations"]
        ApprovalsAPI["/approvals"]
        AgentsAPI["/agents"]
        AuditAPI["/audit"]
        LangGraph["LangGraph workflow"]
    end

    DB[(SQLite / Postgres)]
    Redis[(Redis / fakeredis)]
    VectorStore[(In-memory / Qdrant)]

    Browser --> Middleware
    Middleware --> LoginPage
    Middleware --> DashLayout
    DashLayout --> Pages
    Pages --> ApiClient
    ApiClient -->|Bearer JWT| Backend
    Backend --> DB
    Backend --> Redis
    Backend --> VectorStore
    Backend --> LangGraph
```

---

## Design principles applied in Phase 12

| Principle | How it appears |
|---|---|
| **Single source of truth** | Navigation declared once in `nav.ts`; API types defined once in `types.ts` |
| **Backend is the security boundary** | Frontend gates are UX convenience; 403s from the backend are the real gate |
| **No gradients, no UI library** | All components are hand-written; `tailwind.config.ts` holds the design tokens |
| **Build-time vs run-time config** | `NEXT_PUBLIC_*` values are baked in at build time; `localStorage` is per-session |
| **Offline testing** | Tests use Vitest + jsdom; no browser launch, no backend needed |
| **Stop polling on terminal state** | `useWorkflowPolling` stops when status is completed/failed/escalated |

---

## Component responsibility map

```mermaid
graph LR
    App["App Router (Next.js)"]
    App --> MW[middleware.ts — gate unauthenticated requests]
    App --> Layout["(dashboard)/layout.tsx — read role, show sidebar"]
    App --> Pages[Pages — fetch data, render UI]
    Pages --> UIKit[UI Kit — StatusPill, Button, EmptyState, Card…]
    Pages --> LibApi["lib/api.ts — single fetch gateway"]
    Pages --> LibHooks["lib/hooks.ts — polling, auth, deriveSteps"]
    LibApi -->|JWT| FastAPI[FastAPI :8000]
```
