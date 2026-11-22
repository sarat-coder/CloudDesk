"""CustomerAgent — loads customer context from tools + long-term memory.

Node produced: customer_context → CustomerContext

No LLM call — this agent is entirely deterministic (§7.1).
All tool calls go through ToolRegistry (§7.4).
Memory is read via memory_service.recall_customer() (§7.5).
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.workflow import CustomerContext

logger = logging.getLogger(__name__)

_ZERO_USAGE: dict[str, Any] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "estimated_cost_usd": 0.0,
}


class CustomerAgent:
    """Stateless agent — no LLM call, pure tool + memory reads."""

    async def run(
        self,
        customer_id: str,
        ticket_id: str,
    ) -> tuple[CustomerContext, dict, float, list]:
        """Load customer profile, subscription, workspace, ticket history, and memory.

        Returns:
            customer_context, usage (always zero), duration_ms, tool_calls
        """
        import time

        from app.core.database import get_session
        from app.tools.registry import get_registry
        from memory.memory_service import recall_customer

        start = time.monotonic()
        registry = get_registry()
        tool_calls: list[dict] = []
        errors: list[str] = []

        # --- get_customer ---
        r_customer = await registry.execute("get_customer", {"customer_id": customer_id})
        tool_calls.append({"tool": "get_customer", "ok": r_customer.ok})
        customer_data: dict[str, Any] = r_customer.data or {}
        if not r_customer.ok:
            errors.append(f"get_customer: {r_customer.error}")

        # --- get_ticket_history ---
        r_history = await registry.execute(
            "get_ticket_history", {"customer_id": customer_id, "limit": 10}
        )
        tool_calls.append({"tool": "get_ticket_history", "ok": r_history.ok})
        ticket_history: list[dict] = []
        if r_history.ok and r_history.data:
            ticket_history = r_history.data.get("tickets", [])
            # Exclude current ticket from history
            ticket_history = [t for t in ticket_history if t.get("id") != ticket_id]
        elif not r_history.ok:
            errors.append(f"get_ticket_history: {r_history.error}")

        # --- recall_customer (long-term memory) ---
        memory_notes: list[dict] = []
        try:
            async with get_session() as session:
                memory_notes = await recall_customer(customer_id, session)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"recall_customer: {exc}")

        duration_ms = (time.monotonic() - start) * 1000

        context = CustomerContext(
            customer_id=customer_id,
            name=customer_data.get("name", ""),
            email=customer_data.get("email", ""),
            plan=customer_data.get("plan", ""),
            subscription=customer_data.get("subscription"),
            workspace=customer_data.get("workspace"),
            ticket_history=ticket_history,
            memory_notes=memory_notes,
            load_errors=errors,
        )
        return context, dict(_ZERO_USAGE), duration_ms, tool_calls
