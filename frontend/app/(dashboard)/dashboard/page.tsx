"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { dashboard } from "@/lib/api";
import { StatusPill, SeverityPill } from "@/components/ui/StatusPill";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatRelative } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)] p-4">
      <div className="text-2xl font-semibold text-[var(--fg)]">{value}</div>
      <div className="text-xs font-medium text-[var(--fg-muted)] mt-0.5">{label}</div>
      {sub && <div className="text-xs text-[var(--fg-muted)]">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dashboard.summary().then(setSummary).catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="p-6">
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-3">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-[var(--fg)]">Dashboard</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Open tickets" value={summary?.open_tickets ?? "—"} />
        <StatCard label="Resolved today" value={summary?.resolved_today ?? "—"} />
        <StatCard label="Pending approvals" value={summary?.pending_approvals ?? "—"} />
        <StatCard
          label="Avg resolution"
          value={
            summary?.avg_resolution_minutes != null
              ? `${Math.round(summary.avg_resolution_minutes)}m`
              : "—"
          }
        />
      </div>

      <div>
        <h2 className="text-sm font-medium text-[var(--fg)] mb-3">Recent tickets</h2>
        {!summary?.recent_tickets?.length ? (
          <EmptyState title="No recent tickets" />
        ) : (
          <div className="rounded-lg border border-[var(--border)] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">#</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Subject</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Status</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Severity</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {summary.recent_tickets.map((t) => (
                  <tr key={t.id} className="hover:bg-[var(--bg-subtle)]">
                    <td className="px-4 py-2">
                      <Link href={`/tickets/${t.id}`} className="text-[var(--brand)] hover:underline font-mono text-xs">
                        {t.ticket_number}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-[var(--fg)] max-w-xs truncate">{t.subject}</td>
                    <td className="px-4 py-2"><StatusPill status={t.status} /></td>
                    <td className="px-4 py-2"><SeverityPill severity={t.severity} /></td>
                    <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">{formatRelative(t.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
