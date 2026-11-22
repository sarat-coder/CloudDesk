"use client";

import { useEffect, useState } from "react";
import { settings } from "@/lib/api";
import { useAuth } from "@/lib/hooks";
import { Card } from "@/components/ui/Card";

export default function SettingsPage() {
  const { role } = useAuth();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (role !== "admin") return;
    settings.get().then(setData).catch((e) => setError(e.message));
  }, [role]);

  if (role && role !== "admin") {
    return (
      <div className="p-6">
        <div className="text-sm text-[var(--fg-muted)]">Settings are only available to admins.</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-[var(--fg)]">Settings</h1>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <Card title="Platform configuration">
        {data ? (
          <pre className="text-xs text-[var(--fg)] overflow-auto max-h-96">
            {JSON.stringify(data, null, 2)}
          </pre>
        ) : (
          <p className="text-xs text-[var(--fg-muted)]">Loading…</p>
        )}
      </Card>

      <Card title="Demo accounts">
        <ul className="text-xs space-y-1 text-[var(--fg)]">
          <li><strong>Admin:</strong> admin@clouddesk.demo</li>
          <li><strong>Agent:</strong> sam.agent@clouddesk.demo</li>
          <li><strong>Viewer:</strong> vic.viewer@clouddesk.demo</li>
        </ul>
      </Card>
    </div>
  );
}
