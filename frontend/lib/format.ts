import type { TicketStatus, Severity, Category, ApprovalStatus } from "./types";

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(amount);
}

export function statusLabel(s: TicketStatus): string {
  const labels: Record<TicketStatus, string> = {
    new: "New",
    in_progress: "In Progress",
    waiting_on_customer: "Waiting",
    waiting_on_approval: "Approval",
    escalated: "Escalated",
    resolved: "Resolved",
    closed: "Closed",
  };
  return labels[s] ?? s;
}

export function severityLabel(s: Severity): string {
  const labels: Record<Severity, string> = {
    low: "Low",
    medium: "Medium",
    high: "High",
    critical: "Critical",
  };
  return labels[s] ?? s;
}

export function categoryLabel(c: Category): string {
  const labels: Record<Category, string> = {
    login_issue: "Login Issue",
    billing: "Billing",
    api_failure: "API Failure",
    workspace_permissions: "Permissions",
    storage_quota: "Storage",
    integration: "Integration",
    feature_request: "Feature Request",
    account: "Account",
    security: "Security",
    other: "Other",
  };
  return labels[c] ?? c;
}

export function approvalLabel(s: ApprovalStatus): string {
  const labels: Record<ApprovalStatus, string> = {
    not_required: "—",
    pending: "Pending",
    approved: "Approved",
    rejected: "Rejected",
  };
  return labels[s] ?? s;
}
