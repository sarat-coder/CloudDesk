import type {
  TokenResponse,
  User,
  TicketListResponse,
  Ticket,
  TicketDetail,
  TicketCreate,
  TicketUpdate,
  TicketMessage,
  WorkflowState,
  WorkflowEvent,
  ApprovalRequest,
  CustomerListResponse,
  CustomerDetail,
  Escalation,
  Article,
  DashboardSummary,
  AuditLog,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class NetworkError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = "NetworkError";
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("token");
  } catch {
    return null;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retries = 1
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init.headers as Record<string, string>),
  };

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch (err) {
    if (retries > 0) {
      await new Promise((r) => setTimeout(r, 1000));
      return request<T>(path, init, retries - 1);
    }
    throw new NetworkError(0, "Network unavailable — retrying…");
  }

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      window.location.href = "/login?reason=expired";
    }
    throw new NetworkError(401, "Session expired");
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {}
    throw new NetworkError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const auth = {
  demoLogin: (email?: string, role?: string) =>
    request<TokenResponse & { user: User }>("/api/v1/auth/demo-login", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),

  me: () => request<User>("/api/v1/auth/me"),
};

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export const dashboard = {
  summary: () => request<DashboardSummary>("/api/v1/dashboard/summary"),
};

// ---------------------------------------------------------------------------
// Tickets
// ---------------------------------------------------------------------------

export const tickets = {
  list: (params?: {
    status?: string;
    severity?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.severity) q.set("severity", params.severity);
    if (params?.search) q.set("search", params.search);
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    return request<TicketListResponse>(`/api/v1/tickets?${q}`);
  },

  create: (body: TicketCreate) =>
    request<Ticket>("/api/v1/tickets", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  get: (id: string) => request<TicketDetail>(`/api/v1/tickets/${id}`),

  update: (id: string, body: TicketUpdate) =>
    request<Ticket>(`/api/v1/tickets/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  run: (id: string) =>
    request<{ workflow_id: string; status: string }>(`/api/v1/tickets/${id}/run`, {
      method: "POST",
    }),

  workflow: (id: string) =>
    request<WorkflowState>(`/api/v1/tickets/${id}/workflow`),

  events: (id: string) =>
    request<WorkflowEvent[]>(`/api/v1/tickets/${id}/events`),

  reply: (id: string, body: string, internal = false) =>
    request<TicketMessage>(`/api/v1/tickets/${id}/reply`, {
      method: "POST",
      body: JSON.stringify({ body, internal }),
    }),

  requestInfo: (id: string, questions: string[]) =>
    request<TicketMessage>(`/api/v1/tickets/${id}/request-info`, {
      method: "POST",
      body: JSON.stringify({ questions }),
    }),

  escalate: (id: string, reason: string, priority = "normal") =>
    request<Escalation>(`/api/v1/tickets/${id}/escalate`, {
      method: "POST",
      body: JSON.stringify({ reason, priority }),
    }),
};

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

export const approvals = {
  list: (status?: string) => {
    const q = status ? `?status=${status}` : "";
    return request<ApprovalRequest[]>(`/api/v1/approvals${q}`);
  },

  get: (id: string) => request<ApprovalRequest>(`/api/v1/approvals/${id}`),

  approve: (id: string, note?: string) =>
    request<{ approval: ApprovalRequest; workflow: WorkflowState }>(
      `/api/v1/approvals/${id}/approve`,
      { method: "POST", body: JSON.stringify({ note }) }
    ),

  reject: (id: string, note?: string) =>
    request<{ approval: ApprovalRequest; workflow: WorkflowState }>(
      `/api/v1/approvals/${id}/reject`,
      { method: "POST", body: JSON.stringify({ note }) }
    ),
};

// ---------------------------------------------------------------------------
// Customers
// ---------------------------------------------------------------------------

export const customers = {
  list: (params?: { search?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set("search", params.search);
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    return request<CustomerListResponse>(`/api/v1/customers?${q}`);
  },

  get: (id: string) => request<CustomerDetail>(`/api/v1/customers/${id}`),
};

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

export const knowledge = {
  list: (params?: { search?: string; category?: string }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set("search", params.search);
    if (params?.category) q.set("category", params.category);
    return request<{ items: Article[]; total: number }>(`/api/v1/knowledge?${q}`);
  },

  search: (query: string, top_k = 5) =>
    request<{ results: import("./types").Evidence[] }>("/api/v1/knowledge/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k }),
    }),

  reindex: () =>
    request<{ status: string }>("/api/v1/knowledge/reindex", { method: "POST" }),
};

// ---------------------------------------------------------------------------
// Escalations
// ---------------------------------------------------------------------------

export const escalations = {
  list: (params?: { status?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    return request<{ items: Escalation[]; total: number }>(`/api/v1/escalations?${q}`);
  },
};

// ---------------------------------------------------------------------------
// Agents (graph nodes)
// ---------------------------------------------------------------------------

export const agents = {
  graph: () =>
    request<{ nodes: { id: string; label: string }[]; edges: { from: string; to: string }[] }>(
      "/api/v1/agents"
    ),
};

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export const audit = {
  list: (params?: { page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    return request<{ items: AuditLog[]; total: number }>(`/api/v1/audit?${q}`);
  },
};

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export const settings = {
  get: () => request<Record<string, unknown>>("/api/v1/settings"),
  update: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/v1/settings", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};
