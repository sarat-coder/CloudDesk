# Phase 6 — Interview Questions and Answers

## Tools, Policy, Registry, and Mock Integrations

---

### Section 1: Concept and Motivation

**Q1. Why did you build a ToolRegistry instead of letting agents call functions directly?**

A: Calling functions directly means there is no single place to enforce rules. Any agent could call any function at any time, bypass a timeout, or silently swallow exceptions. The registry is a single chokepoint — every tool call, without exception, passes through it. That lets us enforce approval checks, timeouts, and exception containment in one place, so the rest of the system (agents, graph, tests) never has to worry about those concerns individually.

---

**Q2. What is the ToolPolicy? Why is it separate from the registry?**

A: The ToolPolicy is a pure rulebook — it only answers "does this tool name and argument set require approval?" It has no I/O, no database calls, no side effects. That makes it trivially unit-testable: you just call `policy.requires_approval(name, args)` and assert True or False. Keeping it separate from the registry means the safety rules can be read, reviewed, and tested in complete isolation from execution mechanics.

---

**Q3. Why does an unknown tool require approval by default?**

A: If you default to "no approval needed" for unknown tools, adding a new consequential tool accidentally creates a security gap — it runs without review until someone notices. By defaulting to "approval required," new tools start safe. You explicitly opt out of approval for the ones that do not need it, not the other way around. This is a fail-safe (safe-by-default) design.

---

**Q4. Why does `create_escalation` not require approval?**

A: Escalating is itself the conservative, safe action — it hands the ticket to a human specialist team. If you required approval before escalating, you create a catch-22: a critical ticket needs a human, but you need a human to approve the escalation first. The escalation path must always be open, so it has no approval gate.

---

### Section 2: Technical Implementation

**Q5. How does the registry handle a tool that takes too long?**

A: Every tool call is wrapped in `asyncio.wait_for(fn(**args), timeout=settings.tool_timeout_seconds)`. If the tool does not complete in time, Python raises `asyncio.TimeoutError`. The registry catches that exception, logs a warning, and returns `ToolResult(ok=False, error="timed out")`. The workflow graph receives a clean error result — it never sees the exception.

---

**Q6. What happens if a tool raises an unexpected exception?**

A: The registry has a broad `except Exception` around the tool call. It logs the full traceback for debugging, then returns `ToolResult(ok=False, error=str(exc))`. The calling agent gets a structured failure response and can decide what to do — usually escalate. This is the "telemetry must not break a run" principle from CLAUDE.md applied to tool execution.

---

**Q7. Walk me through what happens when `create_refund_request` is called without approval.**

A:
1. `registry.execute("create_refund_request", {amount: 50}, approved=False)` is called.
2. The registry calls `policy.requires_approval("create_refund_request", {amount:50}, approval_required_for_refunds=True, max_refund_without_approval=0)`.
3. The policy checks: flag is True, amount (50) > threshold (0) → returns True.
4. `approved=False` and `requires_approval=True`, so the registry short-circuits.
5. The tool function is **never called**.
6. Registry returns `ToolResult(ok=False, error="requires human approval")`.
7. The workflow pauses and creates an approval request for the human agent.

---

**Q8. How does the refund threshold work? Give an example.**

A: There are two settings: `APPROVAL_REQUIRED_FOR_REFUNDS` (a boolean flag) and `MAX_REFUND_WITHOUT_APPROVAL` (a dollar amount).

- If the flag is `false`, refunds never need approval regardless of amount.
- If the flag is `true` and the amount is **at or below** the threshold, it auto-approves.
- If the flag is `true` and the amount **exceeds** the threshold, approval is required.

Example: `MAX_REFUND_WITHOUT_APPROVAL=100`. A $50 refund auto-approves. A $150 refund pauses for human review. This lets companies auto-approve small courtesy refunds while protecting against large ones.

---

**Q9. How is the ToolRegistry singleton initialized? What happens in tests?**

A: `get_registry()` uses a module-level `_registry` variable. On first call it creates a new `ToolRegistry`, calls `register_support_tools` and `register_write_tools`, and stores it. Subsequent calls return the same object. For tests, `reset_registry()` sets `_registry = None` so the next `get_registry()` starts fresh. This prevents test pollution — one test's mock functions do not leak into the next test.

---

**Q10. Why are tool functions plain `async def` instead of using the LangChain `@tool` decorator?**

A: The `@tool` decorator is planned for Phase 9 when agents use LangChain tool-calling. In Phase 6 the tools are built as plain async functions registered by name in the ToolRegistry. This keeps Phase 6 independent — it has no LangChain dependency and tests run much faster. When Phase 9 wraps them with `@tool`, the underlying functions do not change.

---

### Section 3: Integration Design

**Q11. What is the purpose of `integrations/protocols.py`?**

A: It defines Python `Protocol` classes — interfaces that describe what an integration must be able to do, without specifying how. For example, `EmailService` defines a `send(to, subject, body)` method. Any class that has that method satisfies the protocol, whether it is `MockEmailService` or `RealSendGridService`. The rest of the application (factory, tools) only imports the protocol. This is called **duck typing with structure** — you get interface safety without forced inheritance.

---

**Q12. Why are the mock services in a separate `integrations/mock/` package rather than inline?**

A: Separation of concerns. The mock adapters will be replaced by real ones in production. By keeping them in `integrations/mock/`, the real adapters can go in `integrations/real/` and the factory just changes which one it imports. The tool functions and agent code never change. If you put mock logic inline in the tools, every tool file needs changing when you add real integrations.

---

**Q13. How does the factory decide which adapter to return?**

A: It reads `settings.demo_mode`. In demo mode it returns a mock. In non-demo mode it would return a real adapter (not yet built). This means every environment — developer laptop, staging, production — automatically gets the right adapters based on a single environment variable, with no code change required.

---

**Q14. `MockStorageService.get_usage` actually reads the database. Why is that not a problem?**

A: The mock does not make a network call to a real storage API, which is the point. It reads the `workspaces.storage_used_gb` and `storage_limit_gb` columns that are already in the demo database (seeded in Phase 2). This gives realistic responses without any external service. It is still fully offline — just reading local SQLite.

---

### Section 4: Testing Strategy

**Q15. How did you test the approval gate without a running database?**

A: The ToolPolicy tests are pure unit tests — they instantiate `ToolPolicy()` and call `requires_approval()`. No database, no HTTP, no async. For the registry tests, tools are replaced with `AsyncMock` objects from `unittest.mock`. This lets us test the registry's control flow (block unapproved call, execute approved call, catch exceptions, enforce timeout) without any real tool logic.

---

**Q16. How do you test that a tool exception does not crash the system?**

A: We register a tool function that immediately raises `RuntimeError("boom")`, then call `registry.execute(...)` and assert that the result is `ToolResult(ok=False)` with "boom" in the error message, and that no exception propagates to the test. The test simply asserting `result.ok is False` proves the exception was contained.

---

**Q17. How do you test the timeout without actually waiting 30 seconds?**

A: We register a tool that calls `await asyncio.sleep(999)`, then patch `get_settings()` to return `tool_timeout_seconds=0.01` (10 milliseconds). The tool times out almost instantly, the registry catches `asyncio.TimeoutError`, and the test completes in well under a second.

---

**Q18. How many tests does Phase 6 add, and what do they cover?**

A: 27 new tests in `tests/unit/test_tool_policy.py`. They cover:
- 5 read-only tools need no approval (parametrized)
- `update_ticket` and `create_escalation` need no approval
- `reset_demo_setting` always needs approval
- 4 refund threshold combinations (flag off, flag on with amount below/at/above threshold)
- Unknown tools always need approval
- Registry blocks unapproved consequential calls
- Registry executes approved calls
- Registry returns error for unregistered tools
- Tool exceptions return `ToolResult(ok=False)`, not raise
- Tool timeout returns `ToolResult(ok=False)`
- Mock services return success results
- Mock services satisfy their Protocol interfaces
- Factory returns correct mock types in demo mode

---

### Section 5: Architecture and Design Decisions

**Q19. Why is `ToolResult` a dataclass rather than a Pydantic model or a dict?**

A: Dataclasses are lighter weight, have no validation overhead, and are simpler to construct (`ToolResult(ok=False, error="...")` is cleaner than a Pydantic model). Since `ToolResult` is an internal return type never serialized directly to HTTP or the database, Pydantic's features are not needed. When results flow into workflow state they get converted there.

---

**Q20. The spec says "the same execute path runs for auto-resolved and human-approved actions." What does that mean, and why does it matter?**

A: Whether a tool runs automatically (low-risk path) or after a human approved it in the UI, it calls `registry.execute(name, args, approved=True)` in both cases. This guarantees the same logic runs in both scenarios — no separate code path that might behave differently. For audits, every execution is treated the same. For testing, you only need to test one code path.

---

**Q21. How does Phase 6 relate to the overall pipeline described in CLAUDE.md?**

A: The pipeline is: Understand → Classify → Investigate → Retrieve → Troubleshoot → **Decide → Resolve → Act → Escalate** → Remember. Phase 6 builds the **Act** and **Escalate** mechanics. The agents (Phase 8) will decide what to do, and the graph (Phase 9) orchestrates the flow, but the actual execution of actions — including the approval gate — is entirely in the Tool Layer built here.

---

**Q22. What would you change if you needed to support multiple approval levels (e.g. team-lead vs. director)?**

A: The `ToolPolicy.requires_approval` method could return a string like `"team_lead"` or `"director"` instead of a boolean. The `ToolRegistry.execute` would then accept an `approver_role` argument and compare it against the required level. The `approval_requests` table in the database already has a `decided_by` column that could store the approver's role. The change is localized to `policy.py` and `registry.py` — no tool functions need changing.
