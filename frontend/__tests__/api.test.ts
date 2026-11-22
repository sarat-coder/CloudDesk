import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NetworkError } from "@/lib/api";

describe("NetworkError", () => {
  it("carries status and detail", () => {
    const e = new NetworkError(401, "Session expired");
    expect(e.status).toBe(401);
    expect(e.detail).toBe("Session expired");
    expect(e.name).toBe("NetworkError");
    expect(e.message).toBe("Session expired");
  });

  it("is an instance of Error", () => {
    const e = new NetworkError(403, "Forbidden");
    expect(e instanceof Error).toBe(true);
    expect(e instanceof NetworkError).toBe(true);
  });
});

describe("401 redirect", () => {
  let originalFetch: typeof global.fetch;
  let assignMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    originalFetch = global.fetch;
    // Provide a minimal localStorage shim
    const store: Record<string, string> = {};
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => { store[k] = v; },
      removeItem: (k: string) => { delete store[k]; },
    });
    assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { href: "/dashboard" },
      writable: true,
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  it("throws NetworkError on 401", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Session expired" }),
    } as Response);

    const { auth } = await import("@/lib/api");
    await expect(auth.me()).rejects.toThrow(NetworkError);
  });
});
