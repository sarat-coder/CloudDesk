import { describe, it, expect } from "vitest";
import { deriveSteps } from "@/lib/hooks";
import type { WorkflowState } from "@/lib/types";

const BASE_WORKFLOW: WorkflowState = {
  workflow_id: "wf-1",
  ticket_id: "t-1",
  status: "running",
  current_node: "troubleshooting",
  completed_nodes: ["understand_ticket", "classify_severity", "customer_context", "knowledge_retrieval"],
  classification: null,
  severity: null,
  severity_reason: null,
  customer_context: null,
  retrieved_docs: [],
  previous_cases: [],
  diagnosis: null,
  resolution_plan: null,
  actions: [],
  risk: null,
  escalation_required: false,
  escalation_reason: null,
  approval_status: "not_required",
  approval_request_id: null,
  final_response: null,
  ticket_summary: null,
  errors: [],
  started_at: new Date().toISOString(),
  token_usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, estimated_cost_usd: 0 },
};

describe("deriveSteps", () => {
  it("returns 12 steps for null workflow", () => {
    const steps = deriveSteps(null);
    expect(steps).toHaveLength(12);
    expect(steps.every((s) => s.status === "pending")).toBe(true);
  });

  it("marks completed nodes as done", () => {
    const steps = deriveSteps(BASE_WORKFLOW);
    const done = steps.filter((s) => s.status === "done").map((s) => s.id);
    expect(done).toContain("understand_ticket");
    expect(done).toContain("classify_severity");
    expect(done).toContain("customer_context");
    expect(done).toContain("knowledge_retrieval");
  });

  it("marks current node as running", () => {
    const steps = deriveSteps(BASE_WORKFLOW);
    const running = steps.find((s) => s.status === "running");
    expect(running?.id).toBe("troubleshooting");
  });

  it("leaves future nodes as pending", () => {
    const steps = deriveSteps(BASE_WORKFLOW);
    const pending = steps.filter((s) => s.status === "pending").map((s) => s.id);
    expect(pending).toContain("resolution_planning");
    expect(pending).toContain("memory_update");
  });

  it("marks all as done when workflow is completed", () => {
    const all12 = [
      "understand_ticket", "classify_severity", "customer_context", "knowledge_retrieval",
      "troubleshooting", "resolution_planning", "risk_check", "escalation_check",
      "human_approval", "execute_resolution", "ticket_summary", "memory_update",
    ];
    const completed: WorkflowState = {
      ...BASE_WORKFLOW,
      status: "completed",
      current_node: null,
      completed_nodes: all12,
    };
    const steps = deriveSteps(completed);
    expect(steps.every((s) => s.status === "done")).toBe(true);
  });
});
