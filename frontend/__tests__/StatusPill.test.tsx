import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusPill, SeverityPill } from "@/components/ui/StatusPill";

describe("StatusPill", () => {
  it("renders New for new status", () => {
    render(<StatusPill status="new" />);
    expect(screen.getByText("New")).toBeTruthy();
  });

  it("renders In Progress for in_progress", () => {
    render(<StatusPill status="in_progress" />);
    expect(screen.getByText("In Progress")).toBeTruthy();
  });

  it("renders Waiting Approval chip for waiting_on_approval", () => {
    render(<StatusPill status="waiting_on_approval" />);
    expect(screen.getByText("Approval")).toBeTruthy();
  });

  it("renders Escalated for escalated", () => {
    render(<StatusPill status="escalated" />);
    expect(screen.getByText("Escalated")).toBeTruthy();
  });

  it("renders Resolved for resolved", () => {
    render(<StatusPill status="resolved" />);
    expect(screen.getByText("Resolved")).toBeTruthy();
  });
});

describe("SeverityPill", () => {
  it("renders a dash for null severity", () => {
    render(<SeverityPill severity={null} />);
    expect(screen.getByText("—")).toBeTruthy();
  });

  it("renders Critical for critical severity", () => {
    render(<SeverityPill severity="critical" />);
    expect(screen.getByText("Critical")).toBeTruthy();
  });
});
