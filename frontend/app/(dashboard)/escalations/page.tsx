"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { escalations } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatRelative } from "@/lib/format";
import type { Escalation } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-red-100 text-red-700",
  acknowledged: "bg-yellow-100 text-yellow-700",
  resolved: "bg-green-100 text-green-700",
};

export default function EscalationsPage() {
  const [items, setItems] = useState<Escalation[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await escalations.list({ status: status || undefined });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--fg)]">Escalations</h1>
        <span className="text-xs text-[var(--fg-muted)]">{total} total</span>
      </div>

      <select
        value={status}
        onChange={(e) => setStatus(e.target.value)}
        className="px-3 py-2 rounded-md border border-[var(--border)] bg-[var(--bg)] text-sm text-[var(--fg)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
      >
        <option value="">All statuses</option>
        <option value="open">Open</option>
        <option value="acknowledged">Acknowledged</option>
        <option value="resolved">Resolved</option>
      </select>

      {loading ? (
        <div className="text-sm text-[var(--fg-muted)]">Loading…</div>
      ) : !items.length ? (
        <EmptyState title="No escalations" description="All clear." />
      ) : (
        <div className="rounded-lg border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border)]">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Ticket</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Team</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Priority</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Reason</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {items.map((e) => (
                <tr key={e.id} className="hover:bg-[var(--bg-subtle)]">
                  <td className="px-4 py-2">
                    <Link href={`/tickets/${e.ticket_id}`} className="text-[var(--brand)] hover:underline font-mono text-xs">
                      {e.ticket_number}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-xs text-[var(--fg)]">{e.assigned_team}</td>
                  <td className="px-4 py-2 text-xs text-[var(--fg-muted)] capitalize">{e.priority}</td>
                  <td className="px-4 py-2">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[e.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {e.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-[var(--fg-muted)] max-w-xs truncate">{e.reason}</td>
                  <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">{formatRelative(e.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
