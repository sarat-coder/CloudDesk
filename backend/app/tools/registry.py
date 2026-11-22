"""ToolRegistry — the single execution path for every tool call.

All agent tool calls go through ToolRegistry.execute().  The registry:
  1. Checks whether approval is required (via ToolPolicy).
  2. Rejects unapproved consequential calls.
  3. Applies a per-call timeout (TOOL_TIMEOUT_SECONDS).
  4. Wraps any exception in ToolResult(ok=False) so the graph never crashes.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.config import get_settings
from app.tools.policy import TOOL_POLICY, ToolResult

logger = logging.getLogger(__name__)

# Type alias: every registered tool is an async callable.
_AsyncToolFn = Callable[..., Coroutine[Any, Any, ToolResult]]


class ToolRegistry:
    """Central registry for all agent-callable tools."""

    def __init__(self) -> None:
        self._tools: dict[str, _AsyncToolFn] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, fn: _AsyncToolFn) -> None:
        """Register an async tool function under *name*."""
        self._tools[name] = fn

    def register_many(self, tools: dict[str, _AsyncToolFn]) -> None:
        for name, fn in tools.items():
            self.register(name, fn)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        name: str,
        args: dict[str, Any] | None = None,
        *,
        approved: bool = False,
    ) -> ToolResult:
        """Execute *name* with *args*.

        Returns ToolResult(ok=False) on any error; never raises.
        """
        args = args or {}
        settings = get_settings()

        # 1. Approval gate
        needs_approval = TOOL_POLICY.requires_approval(
            name,
            args,
            approval_required_for_refunds=settings.approval_required_for_refunds,
            max_refund_without_approval=settings.max_refund_without_approval,
        )
        if needs_approval and not approved:
            return ToolResult(
                ok=False,
                error=f"Tool '{name}' requires human approval before execution.",
            )

        # 2. Tool lookup
        fn = self._tools.get(name)
        if fn is None:
            return ToolResult(ok=False, error=f"Tool '{name}' is not registered.")

        # 3. Execute with timeout
        try:
            result = await asyncio.wait_for(
                fn(**args),
                timeout=settings.tool_timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning("Tool '%s' timed out after %.1fs", name, settings.tool_timeout_seconds)
            return ToolResult(ok=False, error=f"Tool '{name}' timed out.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool '%s' raised an exception", name)
            return ToolResult(ok=False, error=str(exc))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def registered_tools(self) -> list[str]:
        return sorted(self._tools.keys())


# Module-level singleton — imported by agents and tests.
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Return (and lazily initialise) the shared tool registry."""
    global _registry
    if _registry is None:
        from app.tools.support_tools import register_support_tools
        from app.tools.write_tools import register_write_tools

        _registry = ToolRegistry()
        register_support_tools(_registry)
        register_write_tools(_registry)
    return _registry


def reset_registry() -> None:
    """Reset the singleton — used in tests."""
    global _registry
    _registry = None
