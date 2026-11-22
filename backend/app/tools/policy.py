"""Tool policy — which tools need human approval before execution.

Rules (§7.4 of CLAUDE.md):
  - Read-only tools: no approval required.
  - update_ticket: write but no approval.
  - reset_demo_setting: workspace admin write, APPROVAL REQUIRED.
  - create_refund_request: billing write, APPROVAL REQUIRED by policy
    (controlled by APPROVAL_REQUIRED_FOR_REFUNDS / MAX_REFUND_WITHOUT_APPROVAL).
  - create_escalation: no approval — it is the safe escalation path.
  - Unknown tools: always require approval.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Returned by every tool execution — success or failure."""

    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class ToolPolicy:
    """Encodes which tools require human approval."""

    # Tools that always require approval regardless of args.
    _ALWAYS_REQUIRE: frozenset[str] = frozenset({"reset_demo_setting"})

    # Tools that explicitly never require approval.
    _NEVER_REQUIRE: frozenset[str] = frozenset(
        {
            "get_customer",
            "get_subscription",
            "get_ticket_history",
            "search_docs",
            "check_service_status",
            "update_ticket",
            "create_escalation",
        }
    )

    def requires_approval(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        *,
        approval_required_for_refunds: bool = True,
        max_refund_without_approval: float = 0.0,
    ) -> bool:
        """Return True when this tool call must wait for human approval."""
        if tool_name in self._ALWAYS_REQUIRE:
            return True
        if tool_name in self._NEVER_REQUIRE:
            return False
        if tool_name == "create_refund_request":
            if not approval_required_for_refunds:
                return False
            amount = float((args or {}).get("amount", 0))
            return amount > max_refund_without_approval
        # Unknown tools always require approval (safe default).
        return True


TOOL_POLICY = ToolPolicy()
