"use client";

import { useState, useEffect, useCallback } from "react";
import { knowledge } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { categoryLabel, formatRelative } from "@/lib/format";
import type { Article } from "@/lib/types";

export default function KnowledgePage() {
  const [items, setItems] = useState<Article[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await knowledge.list({ search });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--fg)]">Knowledge Base</h1>
        <span className="text-xs text-[var(--fg-muted)]">{total} articles</span>
      </div>

      <Input
        placeholder="Search articles…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-xs"
      />

      {loading ? (
        <div className="text-sm text-[var(--fg-muted)]">Loading…</div>
      ) : !items.length ? (
        <EmptyState title="No articles found" />
      ) : (
        <div className="grid gap-3">
          {items.map((a) => (
            <div
              key={a.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)] p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-sm font-medium text-[var(--fg)]">{a.title}</h3>
                  <p className="text-xs text-[var(--fg-muted)] mt-0.5">{a.summary}</p>
                </div>
                <span className="shrink-0 text-xs px-2 py-0.5 rounded bg-[var(--border)] text-[var(--fg-muted)]">
                  {categoryLabel(a.category)}
                </span>
              </div>
              <div className="flex gap-1 mt-2 flex-wrap">
                {a.tags.map((t) => (
                  <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-[var(--border)] text-[var(--fg-muted)]">
                    {t}
                  </span>
                ))}
              </div>
              <div className="text-xs text-[var(--fg-muted)] mt-2">
                Updated {formatRelative(a.updated_at)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
