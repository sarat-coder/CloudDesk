"""Mock integration adapters.

These adapters satisfy all integration protocols and work fully offline.
They write to the application log so demos show what would happen in production.
No real email is sent, no real refund is issued, no real storage is queried.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class MockEmailService:
    """Logs the email instead of sending it."""

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        message_id = f"mock-email-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MockEmail] To=%s Subject=%r reply_to=%s id=%s",
            to,
            subject,
            reply_to,
            message_id,
        )
        return {"ok": True, "message_id": message_id}


class MockRefundService:
    """Returns a fake refund ID without touching any payment provider."""

    async def request_refund(
        self,
        customer_id: str,
        amount: float,
        currency: str,
        reason: str,
        reference_id: str,
    ) -> dict[str, Any]:
        refund_id = f"mock-refund-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MockRefund] customer=%s amount=%.2f %s reason=%r ref=%s refund_id=%s",
            customer_id,
            amount,
            currency,
            reason,
            reference_id,
            refund_id,
        )
        return {"ok": True, "refund_id": refund_id, "status": "pending"}

    async def get_refund_status(self, refund_id: str) -> dict[str, Any]:
        logger.info("[MockRefund] get_status refund_id=%s", refund_id)
        return {"ok": True, "refund_id": refund_id, "status": "pending"}


class MockNotificationService:
    """Logs the notification instead of delivering it."""

    async def notify(
        self,
        channel: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        delivery_id = f"mock-notif-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MockNotification] channel=%s message=%r meta=%s delivery_id=%s",
            channel,
            message[:80],
            metadata,
            delivery_id,
        )
        return {"ok": True, "delivery_id": delivery_id}


class MockStorageService:
    """Returns static storage figures from the workspace record."""

    async def get_usage(self, workspace_id: str) -> dict[str, Any]:
        from app.core.database import get_session
        from app.models.entities import Workspace

        try:
            async with get_session() as session:
                workspace: Workspace | None = await session.get(Workspace, workspace_id)
                if workspace is None:
                    return {"ok": False, "error": f"Workspace '{workspace_id}' not found."}
                return {
                    "ok": True,
                    "used_gb": workspace.storage_used_gb,
                    "limit_gb": workspace.storage_limit_gb,
                }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
