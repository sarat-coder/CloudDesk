"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { UserRole } from "./types";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<UserRole | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [name, setName] = useState<string | null>(null);

  useEffect(() => {
    try {
      setToken(localStorage.getItem("token"));
      setRole(localStorage.getItem("role") as UserRole | null);
      setEmail(localStorage.getItem("email"));
      setName(localStorage.getItem("name"));
    } catch {}
  }, []);

  const canAct = role === "agent" || role === "admin";

  return { token, role, email, name, canAct };
}

// ---------------------------------------------------------------------------
// Generic polling hook
// ---------------------------------------------------------------------------

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs = 2000,
  enabled = true
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    run();
    const id = setInterval(run, intervalMs);
    return () => clearInterval(id);
  }, [run, intervalMs, enabled]);

  return { data, error, loading, refresh: run };
}

// ---------------------------------------------------------------------------
// Workflow polling (stops when terminal state reached)
// ---------------------------------------------------------------------------

export function useWorkflowPolling(ticketId: string, enabled = true) {
  const [workflow, setWorkflow] = useState<import("./types").WorkflowState | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!enabled) return;

    let active = true;

    const poll = async () => {
      try {
        const { tickets } = await import("./api");
        const state = await tickets.workflow(ticketId);
        if (!active) return;
        setWorkflow(state);
        setLoading(false);

        const terminal = ["completed", "failed", "escalated"];
        if (!terminal.includes(state.status)) {
          setTimeout(poll, 2000);
        }
      } catch {
        if (!active) return;
        setLoading(false);
        setTimeout(poll, 5000);
      }
    };

    poll();
    return () => {
      active = false;
    };
  }, [ticketId, enabled]);

  return { workflow, loading };
}

// ---------------------------------------------------------------------------
// Derive workflow steps for the right-hand panel
// ---------------------------------------------------------------------------

const STEP_IDS = [
  "understand_ticket",
  "classify_severity",
  "customer_context",
  "knowledge_retrieval",
  "troubleshooting",
  "resolution_planning",
  "risk_check",
  "escalation_check",
  "human_approval",
  "execute_resolution",
  "ticket_summary",
  "memory_update",
];

export type StepStatus = "pending" | "running" | "done" | "skipped";

export interface WorkflowStep {
  id: string;
  label: string;
  status: StepStatus;
}

const STEP_LABELS: Record<string, string> = {
  understand_ticket: "Understand ticket",
  classify_severity: "Classify severity",
  customer_context: "Load customer",
  knowledge_retrieval: "Search knowledge",
  troubleshooting: "Diagnose",
  resolution_planning: "Plan resolution",
  risk_check: "Risk check",
  escalation_check: "Escalation check",
  human_approval: "Human approval",
  execute_resolution: "Execute",
  ticket_summary: "Summarise",
  memory_update: "Update memory",
};

export function deriveSteps(
  workflow: import("./types").WorkflowState | null
): WorkflowStep[] {
  if (!workflow) {
    return STEP_IDS.map((id) => ({
      id,
      label: STEP_LABELS[id] ?? id,
      status: "pending",
    }));
  }

  const completed = new Set(workflow.completed_nodes);
  const current = workflow.current_node;

  return STEP_IDS.map((id) => {
    let status: StepStatus = "pending";
    if (completed.has(id)) status = "done";
    else if (current === id) status = "running";
    return { id, label: STEP_LABELS[id] ?? id, status };
  });
}
