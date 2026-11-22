"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { auth, NetworkError } from "@/lib/api";

const DEMO_USERS = [
  { email: "admin@clouddesk.demo", role: "admin", label: "Admin" },
  { email: "sam.agent@clouddesk.demo", role: "agent", label: "Support Agent" },
  { email: "vic.viewer@clouddesk.demo", role: "viewer", label: "Viewer" },
];

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const reason = params.get("reason");
  const next = params.get("next") ?? "/dashboard";

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (reason === "expired") setError("Your session has expired. Please sign in again.");
  }, [reason]);

  async function loginAs(email: string, role: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await auth.demoLogin(email, role);
      try {
        localStorage.setItem("token", res.access_token);
        localStorage.setItem("role", res.user.role);
        localStorage.setItem("email", res.user.email);
        localStorage.setItem("name", res.user.full_name);
      } catch {}
      // Set a session cookie so the middleware can gate SSR routes.
      document.cookie = `cd_session=1; path=/; max-age=${8 * 3600}; SameSite=Lax`;
      router.push(next);
    } catch (e) {
      setError(e instanceof NetworkError ? e.detail : "Login failed. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-[var(--bg)] px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-[var(--brand)]">CloudDesk</h1>
          <p className="text-sm text-[var(--fg-muted)] mt-1">Support Console — Demo Login</p>
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-md bg-red-50 border border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-3">
          {DEMO_USERS.map((u) => (
            <button
              key={u.email}
              onClick={() => loginAs(u.email, u.role)}
              disabled={loading}
              className="w-full flex items-center justify-between px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)] hover:border-[var(--brand)] hover:bg-[var(--brand)]/5 transition-colors disabled:opacity-50"
            >
              <div className="text-left">
                <div className="text-sm font-medium text-[var(--fg)]">{u.label}</div>
                <div className="text-xs text-[var(--fg-muted)]">{u.email}</div>
              </div>
              <span className="text-xs px-2 py-0.5 rounded bg-[var(--border)] text-[var(--fg-muted)]">
                {u.role}
              </span>
            </button>
          ))}
        </div>

        {loading && (
          <p className="text-center text-xs text-[var(--fg-muted)] mt-4">Signing in…</p>
        )}

        <p className="text-center text-xs text-[var(--fg-muted)] mt-6">
          Demo mode — no real credentials required
        </p>
      </div>
    </main>
  );
}
