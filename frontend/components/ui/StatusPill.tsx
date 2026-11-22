import type { TicketStatus, Severity, ApprovalStatus } from "@/lib/types";
import { statusLabel, severityLabel, approvalLabel } from "@/lib/format";
import { cn } from "@/lib/cn";

const STATUS_COLORS: Record<TicketStatus, string> = {
  new: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-700",
  waiting_on_customer: "bg-purple-100 text-purple-700",
  waiting_on_approval: "bg-orange-100 text-orange-700",
  escalated: "bg-red-100 text-red-700",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-500",
};

const SEVERITY_COLORS: Record<Severity, string> = {
  low: "bg-gray-100 text-gray-600",
  medium: "bg-yellow-100 text-yellow-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

const APPROVAL_COLORS: Record<ApprovalStatus, string> = {
  not_required: "bg-gray-100 text-gray-400",
  pending: "bg-orange-100 text-orange-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

interface StatusProps {
  status: TicketStatus;
}

interface SeverityProps {
  severity: Severity | null;
}

interface ApprovalProps {
  approval: ApprovalStatus;
}

export function StatusPill({ status }: StatusProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
        STATUS_COLORS[status]
      )}
    >
      {statusLabel(status)}
    </span>
  );
}

export function SeverityPill({ severity }: SeverityProps) {
  if (!severity) return <span className="text-xs text-[var(--fg-muted)]">—</span>;
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
        SEVERITY_COLORS[severity]
      )}
    >
      {severityLabel(severity)}
    </span>
  );
}

export function ApprovalPill({ approval }: ApprovalProps) {
  if (approval === "not_required") return null;
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
        APPROVAL_COLORS[approval]
      )}
    >
      {approvalLabel(approval)}
    </span>
  );
}
