"""Unit tests for ToolPolicy, ToolRegistry, and tool functions.

Covers:
  - read-only tools need no approval
  - update_ticket needs no approval
  - reset_demo_setting always needs approval
  - create_refund_request respects APPROVAL_REQUIRED_FOR_REFUNDS / MAX_REFUND_WITHOUT_APPROVAL
  - unknown tools always need approval
  - registry rejects unapproved consequential calls
  - tool exception returns ToolResult(ok=False), never raises
  - timeout returns ToolResult(ok=False)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.tools.policy import TOOL_POLICY, ToolPolicy, ToolResult
from app.tools.registry import ToolRegistry, reset_registry


# ---------------------------------------------------------------------------
# ToolPolicy tests
# ---------------------------------------------------------------------------


class TestToolPolicy:
    def setup_method(self) -> None:
        self.policy = ToolPolicy()

    # Read-only tools — no approval
    @pytest.mark.parametrize(
        "tool_name",
        [
            "get_customer",
            "get_subscription",
            "get_ticket_history",
            "search_docs",
            "check_service_status",
        ],
    )
    def test_read_only_tools_need_no_approval(self, tool_name: str) -> None:
        assert self.policy.requires_approval(tool_name) is False

    # update_ticket — write but no approval
    def test_update_ticket_needs_no_approval(self) -> None:
        assert self.policy.requires_approval("update_ticket") is False

    # create_escalation — no approval (safe path)
    def test_create_escalation_needs_no_approval(self) -> None:
        assert self.policy.requires_approval("create_escalation") is False

    # reset_demo_setting — always requires approval
    def test_reset_demo_setting_always_requires_approval(self) -> None:
        assert self.policy.requires_approval("reset_demo_setting") is True

    # create_refund_request — depends on settings
    def test_refund_requires_approval_when_flag_true_and_amount_above_zero(self) -> None:
        assert (
            self.policy.requires_approval(
                "create_refund_request",
                {"amount": 50.0},
                approval_required_for_refunds=True,
                max_refund_without_approval=0.0,
            )
            is True
        )

    def test_refund_no_approval_when_flag_false(self) -> None:
        assert (
            self.policy.requires_approval(
                "create_refund_request",
                {"amount": 500.0},
                approval_required_for_refunds=False,
                max_refund_without_approval=0.0,
            )
            is False
        )

    def test_refund_no_approval_when_amount_at_or_below_max(self) -> None:
        assert (
            self.policy.requires_approval(
                "create_refund_request",
                {"amount": 100.0},
                approval_required_for_refunds=True,
                max_refund_without_approval=100.0,
            )
            is False
        )

    def test_refund_requires_approval_when_amount_above_max(self) -> None:
        assert (
            self.policy.requires_approval(
                "create_refund_request",
                {"amount": 100.01},
                approval_required_for_refunds=True,
                max_refund_without_approval=100.0,
            )
            is True
        )

    # Unknown tools — always require approval
    def test_unknown_tool_always_requires_approval(self) -> None:
        assert self.policy.requires_approval("delete_all_data") is True
        assert self.policy.requires_approval("some_future_tool") is True

    # Module-level singleton is the same type
    def test_module_level_singleton_is_tool_policy(self) -> None:
        assert isinstance(TOOL_POLICY, ToolPolicy)


# ---------------------------------------------------------------------------
# ToolRegistry tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_registry():
    """Reset the module-level registry singleton between tests."""
    reset_registry()
    yield
    reset_registry()


class TestToolRegistry:
    def _make_registry(self) -> ToolRegistry:
        return ToolRegistry()

    # Unapproved consequential call is rejected
    @pytest.mark.asyncio
    async def test_registry_rejects_unapproved_reset_demo_setting(self) -> None:
        registry = self._make_registry()
        mock_fn = AsyncMock(return_value=ToolResult(ok=True))
        registry.register("reset_demo_setting", mock_fn)

        result = await registry.execute("reset_demo_setting", {}, approved=False)

        assert result.ok is False
        assert "approval" in result.error.lower()
        mock_fn.assert_not_called()

    # Approved call executes the function
    @pytest.mark.asyncio
    async def test_registry_executes_approved_reset_demo_setting(self) -> None:
        registry = self._make_registry()
        expected = ToolResult(ok=True, data={"done": True})
        mock_fn = AsyncMock(return_value=expected)
        registry.register("reset_demo_setting", mock_fn)

        result = await registry.execute(
            "reset_demo_setting",
            {"workspace_id": "w1", "setting_key": "k", "setting_value": True},
            approved=True,
        )

        assert result.ok is True
        mock_fn.assert_called_once()

    # Read-only tool executes without approved flag
    @pytest.mark.asyncio
    async def test_registry_executes_read_only_without_approval(self) -> None:
        registry = self._make_registry()
        expected = ToolResult(ok=True, data={"id": "c1"})
        mock_fn = AsyncMock(return_value=expected)
        registry.register("get_customer", mock_fn)

        result = await registry.execute("get_customer", {"customer_id": "c1"})

        assert result.ok is True
        mock_fn.assert_called_once_with(customer_id="c1")

    # Unknown tool registered but unapproved — rejected
    @pytest.mark.asyncio
    async def test_registry_rejects_unknown_tool_without_approval(self) -> None:
        registry = self._make_registry()
        mock_fn = AsyncMock(return_value=ToolResult(ok=True))
        registry.register("some_future_tool", mock_fn)

        result = await registry.execute("some_future_tool", {}, approved=False)

        assert result.ok is False
        mock_fn.assert_not_called()

    # Tool not registered at all returns ok=False
    @pytest.mark.asyncio
    async def test_registry_returns_error_for_unregistered_tool(self) -> None:
        registry = self._make_registry()
        result = await registry.execute("nonexistent_tool", {}, approved=True)
        assert result.ok is False
        assert "not registered" in result.error

    # Exception in tool function returns ToolResult(ok=False), never raises
    @pytest.mark.asyncio
    async def test_tool_exception_returns_error_result_not_raises(self) -> None:
        registry = self._make_registry()

        async def _boom(**_kwargs):
            raise RuntimeError("boom")

        registry.register("get_customer", _boom)
        result = await registry.execute("get_customer", {"customer_id": "x"})
        assert result.ok is False
        assert "boom" in result.error

    # Timeout returns ToolResult(ok=False)
    @pytest.mark.asyncio
    async def test_tool_timeout_returns_error_result(self) -> None:
        registry = self._make_registry()

        async def _slow(**_kwargs):
            await asyncio.sleep(999)
            return ToolResult(ok=True)

        registry.register("get_customer", _slow)

        with patch("app.tools.registry.get_settings") as mock_settings:
            mock_settings.return_value.tool_timeout_seconds = 0.01
            mock_settings.return_value.approval_required_for_refunds = True
            mock_settings.return_value.max_refund_without_approval = 0.0
            result = await registry.execute("get_customer", {"customer_id": "x"})

        assert result.ok is False
        assert "timed out" in result.error.lower()

    # registered_tools returns sorted list
    def test_registered_tools_sorted(self) -> None:
        registry = self._make_registry()
        registry.register("zzz", AsyncMock())
        registry.register("aaa", AsyncMock())
        assert registry.registered_tools() == ["aaa", "zzz"]


# ---------------------------------------------------------------------------
# Integration test: mock integrations satisfy protocols
# ---------------------------------------------------------------------------


class TestMockIntegrations:
    @pytest.mark.asyncio
    async def test_mock_email_service_ok(self) -> None:
        from integrations.mock.services import MockEmailService

        svc = MockEmailService()
        result = await svc.send(to="user@example.com", subject="Hello", body="World")
        assert result["ok"] is True
        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_mock_refund_service_ok(self) -> None:
        from integrations.mock.services import MockRefundService

        svc = MockRefundService()
        result = await svc.request_refund(
            customer_id="c1",
            amount=50.0,
            currency="USD",
            reason="overcharged",
            reference_id="ticket-001",
        )
        assert result["ok"] is True
        assert "refund_id" in result

    @pytest.mark.asyncio
    async def test_mock_notification_service_ok(self) -> None:
        from integrations.mock.services import MockNotificationService

        svc = MockNotificationService()
        result = await svc.notify(channel="#support", message="Ticket escalated")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_factory_returns_mock_in_demo_mode(self) -> None:
        from integrations.factory import (
            get_email_service,
            get_notification_service,
            get_refund_service,
        )
        from integrations.mock.services import (
            MockEmailService,
            MockNotificationService,
            MockRefundService,
        )

        assert isinstance(get_email_service(), MockEmailService)
        assert isinstance(get_refund_service(), MockRefundService)
        assert isinstance(get_notification_service(), MockNotificationService)

    def test_mock_services_satisfy_protocols(self) -> None:
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

        assert isinstance(MockEmailService(), EmailService)
        assert isinstance(MockRefundService(), RefundService)
        assert isinstance(MockNotificationService(), NotificationService)
        assert isinstance(MockStorageService(), StorageService)
