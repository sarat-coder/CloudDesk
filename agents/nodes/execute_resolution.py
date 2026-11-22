"""Node: execute_resolution — run the planned actions through ToolRegistry."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

NODE = "execute_resolution"


async def execute_resolution(state: dict) -> dict:
    from app.core.database import get_session
    from app.core.observability import record_tool_calls, tracer_for
    from app.models.entities import ResolutionAction
    from app.tools.registry import get_registry

    tracer = tracer_for(state)
    errors: list[str] = []
    tool_records: list[dict] = []

    async with tracer.node(NODE):
        planned_actions = state.get("planned_actions", [])
        # State key set by human_approval node on resume; absent on auto path
        approved = state.get("_approval_decision", True)
        run_id = state.get("workflow_id", "")
        ticket_id = state.get("ticket_id", "")

        registry = get_registry()

        for action in planned_actions:
            is_approved = approved if action.requires_approval else True
            result = await registry.execute(
                name=action.tool,
                args=action.args,
                approved=is_approved,
            )
            tool_records.append({"tool": action.tool, "ok": result.ok})

            # Persist the resolution action
            try:
                async with get_session() as session:
                    action_row = ResolutionAction(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        ticket_id=ticket_id,
                        action_type=action.tool,
                        args=action.args,
                        status="completed" if result.ok else "failed",
                        result={"ok": result.ok, "data": result.data, "error": result.error},
                        executed_at=datetime.now(timezone.utc),
                    )
                    session.add(action_row)
                    await session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("execute_resolution: failed to persist action %s: %s", action.tool, exc)

            if not result.ok:
                errors.append(f"Tool '{action.tool}' failed: {result.error}")

        await record_tool_calls(tracer, NODE, tool_records)

    return {
        "completed_nodes": [NODE],
        "current_node": NODE,
        "errors": errors,
    }
