"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { tickets, approvals } from "@/lib/api";
import { StatusPill, SeverityPill } from "@/components/ui/StatusPill";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Card } from "@/components/ui/Card";
import { formatDate, categoryLabel, formatDuration } from "@/lib/format";
import { useAuth, useWorkflowPolling, deriveSteps, shouldShowApproveReject, shouldShowEscalate } from "@/lib/hooks";
import type { TicketDetail, WorkflowStep } from "@/lib/hooks";
import type { TicketDetail as TD } from "@/lib/types";

// ---------------------------------------------------------------------------
// WorkflowSteps – right panel progress tracker
// ---------------------------------------------------------------------------
function WorkflowSteps({ steps }: { steps: WorkflowStep[] }) {
  return (
    <ol className="space-y-1">
      {steps.map((s) => (
        <li key={s.id} className="flex items-center gap-2">
          <span
            className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium shrink-0 ${
              s.status === "done"
                ? "bg-green-500 text-white"
                : s.status === "running"
                ? "bg-[var(--brand)] text-white animate-pulse"
                : "bg-[var(--border)] text-[var(--fg-muted)]"
            }`}
          >
            {s.status === "done" ? "✓" : s.status === "running" ? "…" : ""}
          </span>
          <span
            className={`text-xs ${
              s.status === "done"
                ? "text-[var(--fg)]"
                : s.status === "running"
                ? "text-[var(--brand)] font-medium"
                : "text-[var(--fg-muted)]"
            }`}
          >
            {s.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { role, canAct } = useAuth();
  const [ticket, setTicket] = useState<TD | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [replyText, setReplyText] = useState("");
  const [runLoading, setRunLoading] = useState(false);
  const [replyLoading, setReplyLoading] = useState(false);
  const [approveLoading, setApproveLoading] = useState(false);
  const [escalateLoading, setEscalateLoading] = useState(false);
  const [escalateReason, setEscalateReason] = useState("");
  const [showEscalateForm, setShowEscalateForm] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const loadTicket = useCallback(() => {
    tickets.get(id).then(setTicket).catch((e) => setError(e.message));
  }, [id]);

  useEffect(() => { loadTicket(); }, [loadTicket]);

  const workflowEnabled = !!ticket;
  const { workflow, loading: wfLoading } = useWorkflowPolling(id, workflowEnabled);

  const steps = deriveSteps(workflow);

  async function runWorkflow() {
    setRunLoading(true);
    setActionMsg(null);
    try {
      await tickets.run(id);
      setActionMsg("Workflow started — watching progress…");
      loadTicket();
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Failed to start workflow");
    } finally {
      setRunLoading(false);
    }
  }

  async function sendReply() {
    if (!replyText.trim()) return;
    setReplyLoading(true);
    try {
      await tickets.reply(id, replyText);
      setReplyText("");
      loadTicket();
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Reply failed");
    } finally {
      setReplyLoading(false);
    }
  }

  async function handleApprove() {
    if (!workflow?.approval_request_id) return;
    setApproveLoading(true);
    try {
      await approvals.approve(workflow.approval_request_id);
      setActionMsg("Approved — workflow resuming…");
      loadTicket();
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Approval failed");
    } finally {
      setApproveLoading(false);
    }
  }

  async function handleReject() {
    if (!workflow?.approval_request_id) return;
    setApproveLoading(true);
    try {
      await approvals.reject(workflow.approval_request_id);
      setActionMsg("Rejected — escalating…");
      loadTicket();
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Rejection failed");
    } finally {
      setApproveLoading(false);
    }
  }

  async function handleEscalate() {
    if (!escalateReason.trim()) return;
    setEscalateLoading(true);
    try {
      await tickets.escalate(id, escalateReason.trim());
      setActionMsg("Ticket escalated to a specialist team.");
      setShowEscalateForm(false);
      setEscalateReason("");
      loadTicket();
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Escalation failed");
    } finally {
      setEscalateLoading(false);
    }
  }

  if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;
  if (!ticket) return <div className="p-6 text-sm text-[var(--fg-muted)]">Loading…</div>;

  const showApproveReject = shouldShowApproveReject(workflow?.approval_status, canAct);
  const showEscalateBtn = shouldShowEscalate(ticket?.status, canAct);

  return (
    <div className="h-full grid grid-cols-[1fr_280px_320px] gap-0 divide-x divide-[var(--border)]">
      {/* Left: messages + composer */}
      <div className="flex flex-col overflow-auto">
        <div className="px-5 py-4 border-b border-[var(--border)]">
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="font-mono text-xs text-[var(--fg-muted)]">{ticket.ticket_number}</span>
              <h1 className="text-base font-semibold text-[var(--fg)] mt-0.5">{ticket.subject}</h1>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <StatusPill status={ticket.status} />
              <SeverityPill severity={ticket.severity} />
            </div>
          </div>
          <div className="text-xs text-[var(--fg-muted)] mt-1">
            {ticket.channel} · {categoryLabel(ticket.category ?? "other")} · {formatDate(ticket.created_at)}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-auto px-5 py-4 space-y-4">
          {ticket.messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "customer" ? "justify-start" : "justify-end"}`}>
              <div
                className={`max-w-lg rounded-lg px-4 py-3 text-sm ${
                  m.role === "customer"
                    ? "bg-[var(--bg-subtle)] border border-[var(--border)] text-[var(--fg)]"
                    : m.role === "ai"
                    ? "bg-[var(--brand)]/10 border border-[var(--brand)]/30 text-[var(--fg)]"
                    : "bg-[var(--brand)] text-white"
                }`}
              >
                <div className="text-xs font-medium mb-1 opacity-70">
                  {m.author_name ?? m.role} · {formatDate(m.created_at)}
                </div>
                <div className="whitespace-pre-wrap">{m.body}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Composer */}
        {canAct && (
          <div className="border-t border-[var(--border)] px-5 py-4 space-y-2">
            {actionMsg && (
              <div className="text-xs text-[var(--brand)] bg-[var(--brand)]/10 rounded px-3 py-2">
                {actionMsg}
              </div>
            )}
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder={workflow?.resolution_plan?.customer_response ?? "Write a reply…"}
              rows={4}
              className="w-full px-3 py-2 text-sm border border-[var(--border)] rounded-md bg-[var(--bg)] text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)] resize-none"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={sendReply} disabled={replyLoading || !replyText.trim()}>
                Send reply
              </Button>
              {!workflow && (
                <Button size="sm" variant="secondary" onClick={runWorkflow} disabled={runLoading}>
                  {runLoading ? "Starting…" : "Run AI workflow"}
                </Button>
              )}
              {showApproveReject && (
                <>
                  <Button size="sm" onClick={handleApprove} disabled={approveLoading}>Approve</Button>
                  <Button size="sm" variant="danger" onClick={handleReject} disabled={approveLoading}>Reject</Button>
                </>
              )}
              {showEscalateBtn && !showApproveReject && (
                <Button size="sm" variant="secondary" onClick={() => setShowEscalateForm((v) => !v)}>
                  Escalate
                </Button>
              )}
            </div>
            {showEscalateForm && (
              <div className="mt-2 flex gap-2 items-start">
                <textarea
                  value={escalateReason}
                  onChange={(e) => setEscalateReason(e.target.value)}
                  placeholder="Reason for escalation…"
                  rows={2}
                  className="flex-1 px-3 py-2 text-sm border border-[var(--border)] rounded-md bg-[var(--bg)] text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)] resize-none"
                />
                <Button size="sm" variant="danger" onClick={handleEscalate} disabled={escalateLoading || !escalateReason.trim()}>
                  {escalateLoading ? "Escalating…" : "Confirm escalate"}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Centre: customer panel */}
      <div className="overflow-auto px-4 py-4 space-y-4">
        <h2 className="text-xs font-semibold text-[var(--fg-muted)] uppercase tracking-wide">Customer</h2>
        {ticket.customer ? (
          <div className="space-y-1 text-sm">
            <div className="font-medium text-[var(--fg)]">{ticket.customer.name}</div>
            <div className="text-xs text-[var(--fg-muted)]">{ticket.customer.email}</div>
            <div className="text-xs text-[var(--fg-muted)] capitalize">{ticket.customer.plan} · {ticket.customer.status}</div>
          </div>
        ) : (
          <p className="text-xs text-[var(--fg-muted)]">—</p>
        )}

        {ticket.subscription && (
          <Card title="Subscription">
            <dl className="space-y-1 text-xs">
              <div className="flex justify-between"><dt className="text-[var(--fg-muted)]">Seats</dt><dd>{ticket.subscription.seats_used}/{ticket.subscription.seats}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--fg-muted)]">Status</dt><dd>{ticket.subscription.status}</dd></div>
            </dl>
          </Card>
        )}

        {ticket.escalation && (
          <Card title="Escalation">
            <div className="text-xs space-y-1">
              <div><span className="text-[var(--fg-muted)]">Team:</span> {ticket.escalation.assigned_team}</div>
              <div><span className="text-[var(--fg-muted)]">Priority:</span> {ticket.escalation.priority}</div>
              <div><span className="text-[var(--fg-muted)]">Reason:</span> {ticket.escalation.reason}</div>
            </div>
          </Card>
        )}
      </div>

      {/* Right: workflow panel */}
      <div className="overflow-auto px-4 py-4 space-y-4">
        <h2 className="text-xs font-semibold text-[var(--fg-muted)] uppercase tracking-wide">AI Workflow</h2>

        <WorkflowSteps steps={steps} />

        {workflow?.classification && (
          <Card title="Classification">
            <div className="text-xs space-y-1">
              <div><span className="text-[var(--fg-muted)]">Category:</span> {categoryLabel(workflow.classification.category)}</div>
              <div><span className="text-[var(--fg-muted)]">Summary:</span> {workflow.classification.summary}</div>
              <div><span className="text-[var(--fg-muted)]">Confidence:</span> {Math.round(workflow.classification.confidence * 100)}%</div>
            </div>
          </Card>
        )}

        {workflow?.diagnosis && (
          <Card title="Diagnosis">
            <div className="text-xs space-y-2">
              <p className="text-[var(--fg)]">{workflow.diagnosis.problem}</p>
              <ul className="list-disc list-inside space-y-0.5 text-[var(--fg-muted)]">
                {workflow.diagnosis.troubleshooting_steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          </Card>
        )}

        {workflow?.retrieved_docs?.length ? (
          <Card title="Evidence">
            <ul className="text-xs space-y-2">
              {workflow.retrieved_docs.slice(0, 3).map((d) => (
                <li key={d.id} className="border-b border-[var(--border)] pb-1">
                  <div className="font-medium text-[var(--fg)]">{d.title}</div>
                  <div className="text-[var(--fg-muted)]">{d.snippet.slice(0, 120)}…</div>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}

        {workflow?.resolution_plan && (
          <Card title="Resolution plan">
            <div className="text-xs space-y-2">
              <p className="text-[var(--fg)]">{workflow.resolution_plan.summary}</p>
              {workflow.resolution_plan.actions.length > 0 && (
                <div>
                  <div className="text-[var(--fg-muted)] font-medium mb-1">Actions</div>
                  <ul className="space-y-0.5">
                    {workflow.resolution_plan.actions.map((a, i) => (
                      <li key={i} className="flex items-center gap-1 text-[var(--fg-muted)]">
                        {a.requires_approval && (
                          <span className="text-orange-500">⚠</span>
                        )}
                        <code>{a.tool}</code>
                        {a.description && <span>— {a.description}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Card>
        )}

        {workflow?.token_usage && (
          <div className="text-xs text-[var(--fg-muted)]">
            Tokens: {workflow.token_usage.total_tokens} · Cost: ${workflow.token_usage.estimated_cost_usd.toFixed(4)}
            {workflow.duration_ms && ` · ${formatDuration(workflow.duration_ms)}`}
          </div>
        )}
      </div>
    </div>
  );
}
