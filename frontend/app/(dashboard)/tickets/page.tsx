"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { tickets } from "@/lib/api";
import { StatusPill, SeverityPill } from "@/components/ui/StatusPill";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { formatRelative, categoryLabel } from "@/lib/format";
import { useAuth } from "@/lib/hooks";
import type { TicketSummary } from "@/lib/types";

export default function TicketsPage() {
  const { canAct } = useAuth();
  const [items, setItems] = useState<TicketSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await tickets.list({ search, status: status || undefined, page, page_size: 20 });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tickets");
    } finally {
      setLoading(false);
    }
  }, [search, status, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--fg)]">Tickets</h1>
        <span className="text-xs text-[var(--fg-muted)]">{total} total</span>
      </div>

      <div className="flex gap-3">
        <Input
          placeholder="Search tickets…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="max-w-xs"
        />
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-md border border-[var(--border)] bg-[var(--bg)] text-sm text-[var(--fg)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
        >
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="in_progress">In Progress</option>
          <option value="waiting_on_approval">Waiting Approval</option>
          <option value="escalated">Escalated</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      {loading ? (
        <div className="text-sm text-[var(--fg-muted)]">Loading…</div>
      ) : !items.length ? (
        <EmptyState title="No tickets found" description="Try adjusting the filters." />
      ) : (
        <>
          <div className="rounded-lg border border-[var(--border)] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">#</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Subject</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Customer</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Status</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Severity</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Category</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {items.map((t) => (
                  <tr key={t.id} className="hover:bg-[var(--bg-subtle)]">
                    <td className="px-4 py-2">
                      <Link href={`/tickets/${t.id}`} className="text-[var(--brand)] hover:underline font-mono text-xs">
                        {t.ticket_number}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-[var(--fg)] max-w-xs truncate">{t.subject}</td>
                    <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">{t.customer_name ?? "—"}</td>
                    <td className="px-4 py-2"><StatusPill status={t.status} /></td>
                    <td className="px-4 py-2"><SeverityPill severity={t.severity} /></td>
                    <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">
                      {t.category ? categoryLabel(t.category) : "—"}
                    </td>
                    <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">{formatRelative(t.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-3 text-xs text-[var(--fg-muted)]">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2 py-1 border border-[var(--border)] rounded disabled:opacity-40"
            >
              Prev
            </button>
            <span>Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={items.length < 20}
              className="px-2 py-1 border border-[var(--border)] rounded disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
