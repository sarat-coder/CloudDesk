"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import type { UserRole } from "@/lib/types";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [role, setRole] = useState<UserRole | null>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        router.replace("/login");
        return;
      }
      setRole((localStorage.getItem("role") as UserRole) ?? "viewer");
      setEmail(localStorage.getItem("email") ?? "");
      setName(localStorage.getItem("name") ?? "");
    } catch {}
    setReady(true);
  }, [router]);

  if (!ready || !role) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)]">
        <span className="text-sm text-[var(--fg-muted)]">Loading…</span>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar role={role} userEmail={email} userName={name} />
      <main className="flex-1 overflow-auto bg-[var(--bg)]">{children}</main>
    </div>
  );
}
