"""Tests for TroubleshootingAgent — offline, fake LLM."""
from __future__ import annotations

import pytest

from agents.specialists.troubleshooting import TroubleshootingAgent
from app.schemas.workflow import Diagnosis


class TestTroubleshootingAgent:
    async def test_returns_diagnosis(self) -> None:
        agent = TroubleshootingAgent()
        diagnosis, usage, ms, calls = await agent.run(
            subject="Cannot upload files",
            body="Upload fails with quota exceeded error.",
            category="storage_quota",
        )
        assert isinstance(diagnosis, Diagnosis)

    async def test_diagnosis_has_steps(self) -> None:
        agent = TroubleshootingAgent()
        diagnosis, _, _, _ = await agent.run(
            subject="API returning 429",
            body="Our nightly sync is hitting rate limits.",
            category="api_failure",
        )
        assert len(diagnosis.steps) > 0

    async def test_diagnosis_has_probable_causes(self) -> None:
        agent = TroubleshootingAgent()
        diagnosis, _, _, _ = await agent.run(
            subject="SSO failing",
            body="Invalid SAML assertion for all users.",
            category="login_issue",
        )
        assert len(diagnosis.probable_causes) > 0

    async def test_check_service_status_called(self) -> None:
        agent = TroubleshootingAgent()
        _, _, _, calls = await agent.run(
            subject="Integration broken",
            body="Slack integration stopped working.",
            category="integration",
        )
        tool_names = [c["tool"] for c in calls]
        assert "check_service_status" in tool_names

    async def test_active_incidents_list_in_result(self) -> None:
        agent = TroubleshootingAgent()
        diagnosis, _, _, _ = await agent.run(
            subject="Storage issues",
            body="Cannot save files.",
            category="storage_quota",
        )
        assert isinstance(diagnosis.active_incidents, list)

    async def test_playbook_steps_enriched_for_security(self) -> None:
        # Security category has playbook hints; steps should be non-empty
        agent = TroubleshootingAgent()
        diagnosis, _, _, _ = await agent.run(
            subject="Possible account breach",
            body="Suspicious logins from unknown IPs.",
            category="security",
        )
        assert len(diagnosis.steps) > 0

    async def test_unknown_category_does_not_crash(self) -> None:
        agent = TroubleshootingAgent()
        diagnosis, _, _, _ = await agent.run(
            subject="Unknown issue",
            body="Something weird happened.",
            category="other",
        )
        assert isinstance(diagnosis, Diagnosis)
