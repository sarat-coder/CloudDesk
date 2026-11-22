"""Integration factory — selects mock vs. real adapters at startup.

Usage:
    from integrations.factory import get_email_service, get_refund_service, ...

In DEMO_MODE (or when no real credentials are configured) the mock adapters
are returned.  Add real adapter classes and wire them here when real credentials
are available.
"""
from __future__ import annotations

from app.core.config import get_settings
from integrations.mock.services import (
    MockEmailService,
    MockNotificationService,
    MockRefundService,
    MockStorageService,
)
from integrations.protocols import (
    EmailService,
    NotificationService,
    RefundService,
    StorageService,
)


def get_email_service() -> EmailService:
    """Return the configured email adapter."""
    settings = get_settings()
    if settings.demo_mode:
        return MockEmailService()
    # Extend here: return RealEmailService() when real credentials exist.
    return MockEmailService()


def get_refund_service() -> RefundService:
    """Return the configured refund/billing adapter."""
    settings = get_settings()
    if settings.demo_mode:
        return MockRefundService()
    return MockRefundService()


def get_notification_service() -> NotificationService:
    """Return the configured notification adapter."""
    settings = get_settings()
    if settings.demo_mode:
        return MockNotificationService()
    return MockNotificationService()


def get_storage_service() -> StorageService:
    """Return the configured storage adapter."""
    settings = get_settings()
    if settings.demo_mode:
        return MockStorageService()
    return MockStorageService()
