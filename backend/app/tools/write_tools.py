"""Approval-gated (and ticket-write) tools.

Tools:
  update_ticket          — update ticket status/severity/assignment (no approval)
  reset_demo_setting     — reset workspace admin demo setting  (APPROVAL REQUIRED)
  create_refund_request  — create a billing refund record      (APPROVAL REQUIRED)
  create_escalation      — record an escalation               (no approval — safe path)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.database import get_session
from app.models.entities import ApprovalRequest, Escalation, ResolutionAction, Ticket, Workspace
from app.tools.policy import ToolResult

if TYPE_CHECKING:
    from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


async def update_ticket(
    ticket_id: str,
    status: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    category_summary: str | None = None,
    assigned_to: str | None = None,
) -> ToolResult:
    """Update ticket metadata.  Does not require approval.

    Args:
        ticket_id: The internal UUID of the ticket.
        status: New status (new/in_progress/waiting_on_customer/resolved/closed).
        severity: New severity (low/medium/high/critical).
        category: New category from the 10 defined categories.
        category_summary: One-line summary of the issue.
        assigned_to: Profile UUID to assign the ticket to.
    """
    try:
        async with get_session() as session:
            ticket: Ticket | None = await session.get(Ticket, ticket_id)
            if ticket is None:
                return ToolResult(ok=False, error=f"Ticket '{ticket_id}' not found.")

            changed: dict[str, Any] = {}
            if status is not None:
                ticket.status = status
                changed["status"] = status
            if severity is not None:
                ticket.severity = severity
                changed["severity"] = severity
            if category is not None:
                ticket.category = category
                changed["category"] = category
            if category_summary is not None:
                ticket.category_summary = category_summary
                changed["category_summary"] = category_summary
            if assigned_to is not None:
                ticket.assigned_to = assigned_to
                changed["assigned_to"] = assigned_to

            ticket.updated_at = datetime.now(timezone.utc)
            await session.flush()
            return ToolResult(ok=True, data={"updated": changed, "ticket_id": ticket_id})
    except Exception as exc:  # noqa: BLE001
        logger.exception("update_ticket failed for %s", ticket_id)
        return ToolResult(ok=False, error=str(exc))


async def reset_demo_setting(
    workspace_id: str,
    setting_key: str,
    setting_value: Any,
    run_id: str | None = None,
) -> ToolResult:
    """Reset a workspace demo/admin setting.  Requires human approval.

    Args:
        workspace_id: The internal UUID of the workspace.
        setting_key: The settings key to update (e.g. 'external_sharing_enabled').
        setting_value: The value to set.
        run_id: Workflow run UUID (for audit trail).
    """
    try:
        async with get_session() as session:
            workspace: Workspace | None = await session.get(Workspace, workspace_id)
            if workspace is None:
                return ToolResult(ok=False, error=f"Workspace '{workspace_id}' not found.")

            settings = dict(workspace.settings or {})
            old_value = settings.get(setting_key)
            settings[setting_key] = setting_value
            workspace.settings = settings
            workspace.updated_at = datetime.now(timezone.utc)

            if run_id:
                session.add(
                    ResolutionAction(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        ticket_id="",  # caller may patch
                        action_type="reset_demo_setting",
                        args={
                            "workspace_id": workspace_id,
                            "setting_key": setting_key,
                            "setting_value": setting_value,
                        },
                        status="executed",
                        executed_at=datetime.now(timezone.utc),
                    )
                )

            await session.flush()
            return ToolResult(
                ok=True,
                data={
                    "workspace_id": workspace_id,
                    "setting_key": setting_key,
                    "old_value": old_value,
                    "new_value": setting_value,
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("reset_demo_setting failed for workspace %s", workspace_id)
        return ToolResult(ok=False, error=str(exc))


async def create_refund_request(
    ticket_id: str,
    customer_id: str,
    amount: float,
    currency: str = "USD",
    reason: str = "",
    run_id: str | None = None,
) -> ToolResult:
    """Create a refund request record in the resolution actions table.  Requires approval.

    Args:
        ticket_id: UUID of the ticket this refund is for.
        customer_id: UUID of the customer receiving the refund.
        amount: Refund amount in the specified currency.
        currency: Currency code (default 'USD').
        reason: Reason for the refund.
        run_id: Workflow run UUID.
    """
    try:
        async with get_session() as session:
            action_id = str(uuid.uuid4())
            action = ResolutionAction(
                id=action_id,
                run_id=run_id or str(uuid.uuid4()),
                ticket_id=ticket_id,
                action_type="create_refund_request",
                args={
                    "customer_id": customer_id,
                    "amount": amount,
                    "currency": currency,
                    "reason": reason,
                },
                status="executed",
                result={"status": "refund_requested", "amount": amount, "currency": currency},
                executed_at=datetime.now(timezone.utc),
            )
            session.add(action)
            await session.flush()
            return ToolResult(
                ok=True,
                data={
                    "action_id": action_id,
                    "ticket_id": ticket_id,
                    "customer_id": customer_id,
                    "amount": amount,
                    "currency": currency,
                    "reason": reason,
                    "status": "refund_requested",
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_refund_request failed for ticket %s", ticket_id)
        return ToolResult(ok=False, error=str(exc))


async def create_escalation(
    ticket_id: str,
    team: str,
    reason: str,
    priority: str = "medium",
    run_id: str | None = None,
    created_by: str | None = None,
) -> ToolResult:
    """Create an escalation record for the ticket.  Does not require approval.

    This is the safe escalation path — it never runs unattended money operations.

    Args:
        ticket_id: UUID of the ticket being escalated.
        team: Name of the team to escalate to (e.g. 'billing-team', 'security-team').
        reason: Human-readable reason for escalation.
        priority: Escalation priority (low/medium/high/critical).
        run_id: Workflow run UUID.
        created_by: Profile UUID or display name of the initiator.
    """
    try:
        async with get_session() as session:
            escalation_id = str(uuid.uuid4())
            escalation = Escalation(
                id=escalation_id,
                ticket_id=ticket_id,
                run_id=run_id,
                team=team,
                reason=reason,
                priority=priority,
                status="open",
                created_by=created_by,
            )
            session.add(escalation)

            # Reflect escalation on the ticket status.
            ticket: Ticket | None = await session.get(Ticket, ticket_id)
            if ticket is not None:
                ticket.status = "escalated"
                ticket.updated_at = datetime.now(timezone.utc)

            await session.flush()
            return ToolResult(
                ok=True,
                data={
                    "escalation_id": escalation_id,
                    "ticket_id": ticket_id,
                    "team": team,
                    "reason": reason,
                    "priority": priority,
                    "status": "open",
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_escalation failed for ticket %s", ticket_id)
        return ToolResult(ok=False, error=str(exc))


def register_write_tools(registry: "ToolRegistry") -> None:
    """Register all write tools (approved + unapproved) into *registry*."""
    registry.register_many(
        {
            "update_ticket": update_ticket,
            "reset_demo_setting": reset_demo_setting,
            "create_refund_request": create_refund_request,
            "create_escalation": create_escalation,
        }
    )
