"""Node: risk_check — compute risk level and decide the routing path."""
from __future__ import annotations

from app.core.observability import tracer_for

NODE = "risk_check"


async def risk_check(state: dict) -> dict:
    from agents.specialists.escalation import assess_risk

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        planned_actions = state.get("planned_actions", [])
        escalation_decision = state.get("escalation_decision")
        severity = state.get("severity", "medium")
        injection_flagged = state.get("injection_flagged", False)

        # Output is considered invalid if error list mentions validation failure
        errors = state.get("errors", [])
        output_valid = not any("validation failed" in e.lower() for e in errors)

        risk_level = assess_risk(
            planned_actions=planned_actions,
            escalation_decision=escalation_decision,
            severity=severity,
            injection_flagged=injection_flagged,
            output_valid=output_valid,
        )

    return {
        "risk_level": risk_level,
        "completed_nodes": [NODE],
        "current_node": NODE,
    }
