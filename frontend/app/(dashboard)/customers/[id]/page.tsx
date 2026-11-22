"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { customers } from "@/lib/api";
import { StatusPill } from "@/components/ui/StatusPill";
import { Card } from "@/components/ui/Card";
import { formatDate, formatRelative } from "@/lib/format";
import type { CustomerDetail } from "@/lib/types";

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<CustomerDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    customers.get(id).then(setData).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;
  if (!data) return <div className="p-6 text-sm text-[var(--fg-muted)]">Loading…</div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold text-[var(--fg)]">{data.name}</h1>
          <p className="text-xs text-[var(--fg-muted)]">{data.email} · {data.company}</p>
        </div>
        <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--border)] text-[var(--fg-muted)] capitalize">
          {data.plan}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Subscription">
          {data.subscription ? (
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-[var(--fg-muted)]">Plan</dt><dd>{data.subscription.plan}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--fg-muted)]">Seats</dt><dd>{data.subscription.seats_used} / {data.subscription.seats}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--fg-muted)]">Status</dt><dd>{data.subscription.status}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--fg-muted)]">Renews</dt><dd>{data.subscription.renewal_date ? formatDate(data.subscription.renewal_date) : "—"}</dd></div>
            </dl>
          ) : (
            <p className="text-xs text-[var(--fg-muted)]">No subscription</p>
          )}
        </Card>

        <Card title="Memory notes">
          {data.memory.length === 0 ? (
            <p className="text-xs text-[var(--fg-muted)]">No notes yet.</p>
          ) : (
            <ul className="space-y-1 text-xs text-[var(--fg)]">
              {data.memory.slice(0, 5).map((m) => (
                <li key={m.id} className="border-b border-[var(--border)] pb-1">
                  <span className="text-[var(--fg-muted)]">[{m.memory_type}]</span> {m.content}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div>
        <h2 className="text-sm font-medium text-[var(--fg)] mb-3">Ticket history</h2>
        {!data.tickets.length ? (
          <p className="text-xs text-[var(--fg-muted)]">No tickets.</p>
        ) : (
          <div className="rounded-lg border border-[var(--border)] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">#</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Subject</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Status</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-[var(--fg-muted)]">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.tickets.map((t) => (
                  <tr key={t.id} className="hover:bg-[var(--bg-subtle)]">
                    <td className="px-4 py-2">
                      <Link href={`/tickets/${t.id}`} className="text-[var(--brand)] hover:underline font-mono text-xs">{t.ticket_number}</Link>
                    </td>
                    <td className="px-4 py-2 text-[var(--fg)] max-w-xs truncate">{t.subject}</td>
                    <td className="px-4 py-2"><StatusPill status={t.status} /></td>
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
