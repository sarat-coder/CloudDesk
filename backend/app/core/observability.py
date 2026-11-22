"""WorkflowTracer — records workflow events to the database.

Every node, tool call, and LLM call writes a WorkflowEvent row.
Telemetry failures NEVER raise — they are logged and swallowed so a tracing
bug never kills a workflow run (§16 of CLAUDE.md).

Raw prompts are never stored (§16 "Never exposed: raw prompts").
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowTracer:
    """Records events for one workflow run."""

    def __init__(self, run_id: str, ticket_id: str) -> None:
        self.run_id = run_id
        self.ticket_id = ticket_id

    # ------------------------------------------------------------------
    # Context manager for a node
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def node(self, node_name: str):
        """Emit node_started / node_completed around the enclosed block."""
        import time
        start = time.monotonic()
        await self._emit("node_started", node=node_name, data={})
        try:
            yield
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._emit(
                "node_completed",
                node=node_name,
                data={"duration_ms": duration_ms},
            )

    # ------------------------------------------------------------------
    # Individual event emitters
    # ------------------------------------------------------------------

    async def tool_called(
        self,
        node: str,
        tool_name: str,
        ok: bool,
        result_summary: str = "",
    ) -> None:
        await self._emit(
            "tool_called",
            node=node,
            data={"tool": tool_name, "ok": ok, "result": result_summary[:500]},
        )

    async def llm_called(
        self,
        node: str,
        usage: dict[str, Any],
        duration_ms: float,
        purpose: str = "",
    ) -> None:
        await self._emit(
            "llm_called",
            node=node,
            data={
                "purpose": purpose,
                "duration_ms": int(duration_ms),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "estimated_cost_usd": usage.get("estimated_cost_usd", 0.0),
            },
        )

    async def approval_requested(self, node: str, approval_id: str, reason: str) -> None:
        await self._emit(
            "approval_requested",
            node=node,
            data={"approval_id": approval_id, "reason": reason},
        )

    async def approval_resolved(
        self, node: str, approval_id: str, decision: str, decided_by: str
    ) -> None:
        await self._emit(
            "approval_resolved",
            node=node,
            data={
                "approval_id": approval_id,
                "decision": decision,
                "decided_by": decided_by,
            },
        )

    async def error(self, node: str, message: str) -> None:
        await self._emit("error", node=node, data={"message": message[:1000]})

    async def workflow_completed(self, status: str, duration_ms: int) -> None:
        await self._emit(
            "workflow_completed",
            node=None,
            data={"status": status, "duration_ms": duration_ms},
        )

    # ------------------------------------------------------------------
    # Internal emit
    # ------------------------------------------------------------------

    async def _emit(
        self,
        event_type: str,
        node: str | None,
        data: dict[str, Any],
    ) -> None:
        try:
            from app.core.database import get_session
            from app.models.entities import WorkflowEvent

            async with get_session() as session:
                event = WorkflowEvent(
                    id=str(uuid.uuid4()),
                    run_id=self.run_id,
                    event_type=event_type,
                    node=node,
                    data=data,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(event)
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.debug(
                "WorkflowTracer._emit failed silently for event_type=%s run_id=%s",
                event_type,
                self.run_id,
            )


def tracer_for(state: dict[str, Any]) -> WorkflowTracer:
    """Convenience factory — extracts run / ticket IDs from graph state."""
    return WorkflowTracer(
        run_id=state.get("workflow_id", "unknown"),
        ticket_id=state.get("ticket_id", "unknown"),
    )


async def record_tool_calls(
    tracer: WorkflowTracer,
    node: str,
    tool_calls: list[dict[str, Any]],
) -> None:
    """Record a list of tool-call records emitted by an agent."""
    for call in tool_calls:
        await tracer.tool_called(
            node=node,
            tool_name=call.get("tool", "unknown"),
            ok=call.get("ok", True),
        )


async def record_llm(
    tracer: WorkflowTracer,
    node: str,
    usage: dict[str, Any],
    duration_ms: float,
    purpose: str,
) -> None:
    await tracer.llm_called(node=node, usage=usage, duration_ms=duration_ms, purpose=purpose)
