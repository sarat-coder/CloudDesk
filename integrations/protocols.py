"""Integration protocols — runtime-pluggable interfaces.

Each integration is typed as a Protocol so the rest of the app only
depends on the interface, never on a specific implementation (mock or real).
The factory (integrations/factory.py) selects the right adapter at startup.

Integrations defined here:
  EmailService      — send transactional email
  RefundService     — issue/query refunds from the billing provider
  NotificationService — send Slack / webhook / in-app notifications
  StorageService    — query storage usage for a workspace
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EmailService(Protocol):
    """Send transactional email to a support customer."""

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        """Return a dict with at least {'ok': bool, 'message_id': str | None}."""
        ...


@runtime_checkable
class RefundService(Protocol):
    """Issue and query refunds from the billing provider."""

    async def request_refund(
        self,
        customer_id: str,
        amount: float,
        currency: str,
        reason: str,
        reference_id: str,
    ) -> dict[str, Any]:
        """Return {'ok': bool, 'refund_id': str | None, 'status': str}."""
        ...

    async def get_refund_status(self, refund_id: str) -> dict[str, Any]:
        """Return {'ok': bool, 'refund_id': str, 'status': str}."""
        ...


@runtime_checkable
class NotificationService(Protocol):
    """Notify the support team or external channel."""

    async def notify(
        self,
        channel: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return {'ok': bool, 'delivery_id': str | None}."""
        ...


@runtime_checkable
class StorageService(Protocol):
    """Query or manage cloud storage for a workspace."""

    async def get_usage(self, workspace_id: str) -> dict[str, Any]:
        """Return {'ok': bool, 'used_gb': float, 'limit_gb': float}."""
        ...
