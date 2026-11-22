"use client";

import { useState, useEffect, useCallback } from "react";
import { audit } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate } from "@/lib/format";
import type { AuditLog } from "@/lib/types";

export default function AuditPage() {
  const [items, setItems] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await audit.list({ page, page_size: 25 });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--fg)]">Audit Log</h1>
        <span className="text-xs text-[var(--fg-muted)]">{total} entries</span>
      </div>

      {loading ? (
        <div className="text-sm text-[var(--fg-muted)]">Loading…</div>
      ) : !items.length ? (
        <EmptyState title="No audit entries" />
      ) : (
        <>
          <div className="rounded-lg border border-[var(--border)] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">When</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Actor</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Action</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Resource</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Request ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {items.map((e) => (
                  <tr key={e.id} className="hover:bg-[var(--bg-subtle)]">
                    <td className="px-4 py-2 text-xs text-[var(--fg-muted)] whitespace-nowrap">{formatDate(e.created_at)}</td>
                    <td className="px-4 py-2 text-xs text-[var(--fg)]">{e.actor}</td>
                    <td className="px-4 py-2 text-xs font-mono text-[var(--brand)]">{e.action}</td>
                    <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">{e.resource_type}/{e.resource_id.slice(0, 8)}</td>
                    <td className="px-4 py-2 text-xs font-mono text-[var(--fg-muted)]">{e.request_id.slice(0, 12)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-3 text-xs text-[var(--fg-muted)]">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-2 py-1 border border-[var(--border)] rounded disabled:opacity-40">Prev</button>
            <span>Page {page}</span>
            <button onClick={() => setPage((p) => p + 1)} disabled={items.length < 25} className="px-2 py-1 border border-[var(--border)] rounded disabled:opacity-40">Next</button>
          </div>
        </>
      )}
    </div>
  );
}
