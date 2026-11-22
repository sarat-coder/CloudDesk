/**
 * CloudDesk frontend type definitions.
 * Mirrors docs/API_CONTRACT.md — keep in sync when routes change.
 */

// ---------------------------------------------------------------------------
// Enumerations
// ---------------------------------------------------------------------------

export type TicketStatus =
  | "new"
  | "in_progress"
  | "waiting_on_customer"
  | "waiting_on_approval"
  | "escalated"
  | "resolved"
  | "closed";

export type Severity = "low" | "medium" | "high" | "critical";

export type Category =
  | "login_issue"
  | "billing"
  | "api_failure"
  | "workspace_permissions"
  | "storage_quota"
  | "integration"
  | "feature_request"
  | "account"
  | "security"
  | "other";

export type Channel = "email" | "chat" | "web" | "api";

export type UserRole = "viewer" | "agent" | "admin";

export type ApprovalStatus = "not_required" | "pending" | "approved" | "rejected";

export type MemoryType = "preference" | "past_issue" | "troubleshooting" | "note";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  avatar_url?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  role: UserRole;
}

// ---------------------------------------------------------------------------
// Tickets
// ---------------------------------------------------------------------------

export interface TicketSummary {
  id: string;
  ticket_number: string;
  subject: string;
  status: TicketStatus;
  severity: Severity | null;
  category: Category | null;
  customer_id: string;
  customer_name: string | null;
  channel: Channel;
  created_at: string;
  updated_at: string;
  escalation_required: boolean;
  approval_status: ApprovalStatus;
}

export interface Ticket extends TicketSummary {
  body: string;
  assigned_to: string | null;
  resolved_at: string | null;
  tags: string[];
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  role: "customer" | "agent" | "system" | "ai";
  author_name: string | null;
  body: string;
  internal: boolean;
  attachments: { name: string; url: string; size: number }[];
  created_at: string;
}

export interface TicketDetail extends Ticket {
  messages: TicketMessage[];
  customer: Customer | null;
  subscription: Subscription | null;
  history: TicketSummary[];
  workflow: WorkflowState | null;
  resolution_actions: ResolutionAction[];
  escalation: Escalation | null;
}

export interface TicketListResponse {
  items: TicketSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface TicketCreate {
  customer_id: string;
  subject: string;
  body: string;
  channel?: Channel;
}

export interface TicketUpdate {
  status?: TicketStatus;
  severity?: Severity;
  assigned_to?: string;
}

// ---------------------------------------------------------------------------
// Customers
// ---------------------------------------------------------------------------

export interface Customer {
  id: string;
  external_id: string;
  name: string;
  email: string;
  company: string | null;
  plan: string;
  status: "active" | "trial" | "past_due" | "churned";
  created_at: string;
  updated_at: string;
}

export interface Subscription {
  id: string;
  customer_id: string;
  plan: "free" | "pro" | "business" | "enterprise";
  seats: number;
  seats_used: number;
  status: string;
  billing_cycle: string;
  amount: number;
  currency: string;
  renewal_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface Workspace {
  id: string;
  customer_id: string;
  name: string;
  slug: string;
  region: string;
  storage_used_gb: number;
  storage_limit_gb: number;
  member_count: number;
  settings: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerMemory {
  id: string;
  customer_id: string;
  memory_type: MemoryType;
  content: string;
  source_ticket_id: string | null;
  created_at: string;
}

export interface CustomerDetail extends Customer {
  subscription: Subscription | null;
  workspace: Workspace | null;
  tickets: TicketSummary[];
  memory: CustomerMemory[];
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Workflow state (right-hand panel)
// ---------------------------------------------------------------------------

export interface Evidence {
  id: string;
  title: string;
  source: string;
  snippet: string;
  score: number;
  url?: string;
  article_id?: string;
}

export interface PlannedAction {
  tool: string;
  arguments: Record<string, unknown>;
  requires_approval: boolean;
  description: string;
}

export interface ResolutionAction {
  id: string;
  ticket_id: string;
  tool: string;
  arguments: Record<string, unknown>;
  status:
    | "planned"
    | "pending_approval"
    | "approved"
    | "executed"
    | "rejected"
    | "failed";
  result: Record<string, unknown> | null;
  requires_approval: boolean;
  created_at: string;
  executed_at: string | null;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

export interface WorkflowState {
  workflow_id: string;
  ticket_id: string;
  status:
    | "running"
    | "waiting_for_approval"
    | "completed"
    | "failed"
    | "escalated";
  current_node: string | null;
  completed_nodes: string[];
  classification: {
    category: Category;
    intent: string;
    summary: string;
    confidence: number;
  } | null;
  severity: Severity | null;
  severity_reason: string | null;
  customer_context: {
    customer: Customer;
    subscription: Subscription | null;
    workspace: Workspace | null;
    previous_tickets: TicketSummary[];
    memory_notes: string[];
  } | null;
  retrieved_docs: Evidence[];
  previous_cases: {
    ticket_number: string;
    subject: string;
    resolution_summary: string;
    similarity: number;
  }[];
  diagnosis: {
    problem: string;
    probable_causes: string[];
    troubleshooting_steps: string[];
    confidence: number;
  } | null;
  resolution_plan: {
    summary: string;
    customer_response: string;
    internal_notes: string;
    actions: PlannedAction[];
  } | null;
  actions: ResolutionAction[];
  risk: { level: "low" | "medium" | "high"; reasons: string[] } | null;
  escalation_required: boolean;
  escalation_reason: string | null;
  approval_status: ApprovalStatus;
  approval_request_id: string | null;
  final_response: string | null;
  ticket_summary: string | null;
  errors: string[];
  started_at: string;
  finished_at?: string;
  duration_ms?: number;
  token_usage: TokenUsage;
}

export interface WorkflowEvent {
  id: string;
  workflow_id: string;
  ticket_id: string;
  event_type:
    | "node_started"
    | "node_completed"
    | "tool_called"
    | "llm_called"
    | "approval_requested"
    | "approval_resolved"
    | "error"
    | "workflow_completed";
  node: string | null;
  tool: string | null;
  message: string;
  duration_ms: number | null;
  payload: Record<string, unknown>;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

export interface ApprovalRequest {
  id: string;
  ticket_id: string;
  ticket_number: string;
  workflow_id: string;
  action: PlannedAction;
  risk_level: string;
  reason: string;
  requested_by: "ai";
  status: "pending" | "approved" | "rejected";
  decided_by?: string;
  decision_note?: string;
  created_at: string;
  decided_at?: string;
}

// ---------------------------------------------------------------------------
// Escalations
// ---------------------------------------------------------------------------

export interface Escalation {
  id: string;
  ticket_id: string;
  ticket_number: string;
  reason: string;
  priority: string;
  status: "open" | "acknowledged" | "resolved";
  created_by: "ai" | "human";
  assigned_team: string;
  created_at: string;
  resolved_at?: string;
}

// ---------------------------------------------------------------------------
// Knowledge base
// ---------------------------------------------------------------------------

export interface Article {
  id: string;
  slug: string;
  title: string;
  category: Category;
  tags: string[];
  summary: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export interface DashboardSummary {
  open_tickets: number;
  resolved_today: number;
  pending_approvals: number;
  escalations_open: number;
  avg_resolution_minutes: number | null;
  by_severity: Record<Severity, number>;
  by_category: Partial<Record<Category, number>>;
  recent_tickets: TicketSummary[];
  agent_activity: WorkflowEvent[];
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export interface AuditLog {
  id: string;
  actor: string;
  actor_type: "user" | "agent" | "system";
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, unknown>;
  request_id: string;
  created_at: string;
}
