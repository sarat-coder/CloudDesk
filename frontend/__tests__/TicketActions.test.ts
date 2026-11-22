import { describe, it, expect } from "vitest";
import { shouldShowApproveReject, shouldShowEscalate } from "@/lib/hooks";

describe("shouldShowApproveReject", () => {
  it("returns true when approval is pending and user can act", () => {
    expect(shouldShowApproveReject("pending", true)).toBe(true);
  });

  it("returns false when approval is pending but viewer cannot act", () => {
    expect(shouldShowApproveReject("pending", false)).toBe(false);
  });

  it("returns false when approval is not_required even for an agent", () => {
    expect(shouldShowApproveReject("not_required", true)).toBe(false);
  });

  it("returns false when approval is approved (already decided)", () => {
    expect(shouldShowApproveReject("approved", true)).toBe(false);
  });

  it("returns false when approval is rejected", () => {
    expect(shouldShowApproveReject("rejected", true)).toBe(false);
  });

  it("returns false when approval status is null", () => {
    expect(shouldShowApproveReject(null, true)).toBe(false);
  });

  it("returns false when approval status is undefined", () => {
    expect(shouldShowApproveReject(undefined, true)).toBe(false);
  });
});

describe("shouldShowEscalate", () => {
  it("returns true for an active ticket when user can act", () => {
    expect(shouldShowEscalate("new", true)).toBe(true);
  });

  it("returns true for in_progress ticket when user can act", () => {
    expect(shouldShowEscalate("in_progress", true)).toBe(true);
  });

  it("returns false when ticket is already escalated", () => {
    expect(shouldShowEscalate("escalated", true)).toBe(false);
  });

  it("returns false when ticket is closed", () => {
    expect(shouldShowEscalate("closed", true)).toBe(false);
  });

  it("returns false when user cannot act (viewer)", () => {
    expect(shouldShowEscalate("new", false)).toBe(false);
  });

  it("returns false for null status", () => {
    expect(shouldShowEscalate(null, true)).toBe(false);
  });
});
