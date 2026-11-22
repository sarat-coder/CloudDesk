"""Node: memory_update — write scrubbed, de-duplicated customer memory."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

NODE = "memory_update"


async def memory_update(state: dict) -> dict:
    from app.core.database import get_session
    from app.core.observability import tracer_for
    from memory.memory_service import record_resolution

    tracer = tracer_for(state)
    errors: list[str] = []

    async with tracer.node(NODE):
        customer_id = state.get("customer_id", "")
        ticket_id = state.get("ticket_id", "")
        subject = state.get("subject", "")
        diagnosis = state.get("diagnosis")
        resolution_plan = state.get("resolution_plan")

        if not customer_id:
            return {
                "completed_nodes": [NODE],
                "current_node": NODE,
                "errors": [],
            }

        steps: list[str] = []
        if diagnosis:
            steps = diagnosis.steps[:3]

        resolution_summary = ""
        if resolution_plan:
            resolution_summary = resolution_plan.summary

        try:
            async with get_session() as session:
                await record_resolution(
                    customer_id=customer_id,
                    ticket_id=ticket_id,
                    subject=subject,
                    troubleshooting_steps=steps,
                    resolution_summary=resolution_summary,
                    session=session,
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("memory_update: failed to write memory: %s", exc)
            errors.append(f"memory write failed: {exc}")

    return {
        "completed_nodes": [NODE],
        "current_node": NODE,
        "errors": errors,
    }
