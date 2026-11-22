"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { customers } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { formatRelative } from "@/lib/format";
import type { Customer } from "@/lib/types";

const PLAN_COLORS: Record<string, string> = {
  free: "bg-gray-100 text-gray-600",
  pro: "bg-blue-100 text-blue-700",
  business: "bg-purple-100 text-purple-700",
  enterprise: "bg-orange-100 text-orange-700",
};

export default function CustomersPage() {
  const [items, setItems] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await customers.list({ search, page, page_size: 20 });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [search, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--fg)]">Customers</h1>
        <span className="text-xs text-[var(--fg-muted)]">{total} total</span>
      </div>

      <Input
        placeholder="Search by name or email…"
        value={search}
        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        className="max-w-xs"
      />

      {loading ? (
        <div className="text-sm text-[var(--fg-muted)]">Loading…</div>
      ) : !items.length ? (
        <EmptyState title="No customers found" />
      ) : (
        <div className="rounded-lg border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border)]">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Name</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Email</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Company</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Plan</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {items.map((c) => (
                <tr key={c.id} className="hover:bg-[var(--bg-subtle)]">
                  <td className="px-4 py-2">
                    <Link href={`/customers/${c.id}`} className="text-[var(--brand)] hover:underline text-sm font-medium">
                      {c.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">{c.email}</td>
                  <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">{c.company ?? "—"}</td>
                  <td className="px-4 py-2">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${PLAN_COLORS[c.plan] ?? "bg-gray-100 text-gray-600"}`}>
                      {c.plan}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-[var(--fg-muted)] capitalize">{c.status}</td>
                  <td className="px-4 py-2 text-xs text-[var(--fg-muted)]">{formatRelative(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
