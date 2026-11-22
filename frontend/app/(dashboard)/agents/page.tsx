"use client";

import { useEffect, useState } from "react";
import { agents } from "@/lib/api";

const NODE_DESCRIPTIONS: Record<string, string> = {
  understand_ticket: "Reads the ticket and identifies the core issue.",
  classify_severity: "Assigns a severity level (low / medium / high / critical) with a reason.",
  customer_context: "Loads the customer record, subscription, workspace, and prior tickets.",
  knowledge_retrieval: "Searches the knowledge base and finds similar resolved cases.",
  troubleshooting: "Produces a diagnosis with probable causes and numbered steps.",
  resolution_planning: "Builds a resolution plan — customer reply, internal notes, and actions.",
  risk_check: "Decides the risk level and whether approval or escalation is required.",
  escalation_check: "Applies policy rules to determine if the ticket must escalate.",
  human_approval: "Pauses the workflow and waits for a human agent to approve or reject.",
  execute_resolution: "Runs the planned actions through the tool registry.",
  ticket_summary: "Writes a one-paragraph ticket summary and updates the ticket record.",
  memory_update: "Writes scrubbed, de-duplicated notes to long-term customer memory.",
};

export default function AgentsPage() {
  const [graph, setGraph] = useState<{ nodes: { id: string; label: string }[]; edges: { from: string; to: string }[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    agents.graph().then(setGraph).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-[var(--fg)]">Agent Nodes</h1>
      <p className="text-xs text-[var(--fg-muted)]">
        Every ticket passes through these 12 nodes in the LangGraph workflow. Each node is a specialist that performs one job.
      </p>

      <div className="grid gap-3 md:grid-cols-2">
        {(graph?.nodes ?? []).map((node, i) => (
          <div key={node.id} className="rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)] p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono text-[var(--fg-muted)]">{i + 1}</span>
              <span className="text-sm font-medium text-[var(--fg)]">{node.label}</span>
            </div>
            <p className="text-xs text-[var(--fg-muted)]">
              {NODE_DESCRIPTIONS[node.id] ?? "Specialist node."}
            </p>
            <code className="text-xs text-[var(--brand)] mt-1 block">{node.id}</code>
          </div>
        ))}
      </div>

      {graph?.edges && (
        <div>
          <h2 className="text-sm font-medium text-[var(--fg)] mb-2">Transitions</h2>
          <div className="flex flex-wrap gap-1">
            {graph.edges.map((e, i) => (
              <span key={i} className="text-xs font-mono px-2 py-0.5 rounded border border-[var(--border)] text-[var(--fg-muted)]">
                {e.from} → {e.to}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
