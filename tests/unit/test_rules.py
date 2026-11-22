"""Unit tests for agents/rules.py.

Covers:
  - rule_category: keyword-based classification
  - rule_severity: rules can raise but never lower the model's severity
  - ESCALATION_RULES / matching_escalation_rules: policy cases return named teams
  - Demo tickets CD-1005, CD-1006, CD-1009, CD-1011 each trigger escalation
    without any model call.
"""
from __future__ import annotations

import pytest

from agents.rules import (
    ESCALATION_RULES,
    matching_escalation_rules,
    rule_category,
    rule_severity,
)
from app.schemas.common import Category, Severity


# ---------------------------------------------------------------------------
# rule_category
# ---------------------------------------------------------------------------


class TestRuleCategory:
    def test_login_sso_text(self) -> None:
        text = "Our entire team has been unable to log in via SSO since 8am. SAML with Okta."
        assert rule_category(text) == Category.LOGIN_ISSUE

    def test_billing_refund_text(self) -> None:
        text = "I noticed our invoice shows charges for 8 seats but we only have 5 active users."
        assert rule_category(text) == Category.BILLING

    def test_api_failure_429(self) -> None:
        text = "API returning 429 errors on our nightly sync job."
        assert rule_category(text) == Category.API_FAILURE

    def test_storage_quota(self) -> None:
        text = "Cannot upload any files — storage quota exceeded."
        assert rule_category(text) == Category.STORAGE_QUOTA

    def test_security_suspicious_login(self) -> None:
        text = "Multiple suspicious login attempts, some accounts may have been compromised."
        assert rule_category(text) == Category.SECURITY

    def test_workspace_permissions(self) -> None:
        text = "Cannot share folder with external partners. External sharing is not enabled."
        assert rule_category(text) == Category.WORKSPACE_PERMISSIONS

    def test_feature_request_dark_mode(self) -> None:
        text = "Would love to have a dark mode feature in the app."
        assert rule_category(text) == Category.FEATURE_REQUEST

    def test_account_deletion(self) -> None:
        text = "Please delete account and erase all data under GDPR."
        assert rule_category(text) == Category.ACCOUNT

    def test_integration_slack(self) -> None:
        text = "Slack integration has stopped working since yesterday."
        assert rule_category(text) == Category.INTEGRATION

    def test_no_match_returns_none(self) -> None:
        text = "blah blah completely generic text with zero matching keywords"
        assert rule_category(text) is None

    def test_returns_highest_score_category(self) -> None:
        # More billing keywords than login keywords
        text = "refund charged invoice billing payment subscription seats credit"
        assert rule_category(text) == Category.BILLING


# ---------------------------------------------------------------------------
# rule_severity
# ---------------------------------------------------------------------------


class TestRuleSeverity:
    def test_security_breach_raises_to_critical(self) -> None:
        text = "Accounts may have been compromised in a security breach."
        assert rule_severity(text, Severity.MEDIUM) == Severity.CRITICAL

    def test_data_loss_raises_to_critical(self) -> None:
        text = "Critical client files have disappeared from our shared folder."
        assert rule_severity(text, Severity.LOW) == Severity.CRITICAL

    def test_enterprise_outage_raises_to_critical(self) -> None:
        text = "Entire team of 143 users cannot log in. This is blocking all of them."
        assert rule_severity(text, Severity.HIGH) == Severity.CRITICAL

    def test_dispute_raises_to_at_least_high(self) -> None:
        result = rule_severity("Unauthorized charge on our account.", Severity.LOW)
        assert result in (Severity.HIGH, Severity.CRITICAL)

    def test_severity_never_lowered(self) -> None:
        # Dark mode feature request — rules have nothing to escalate,
        # but they must not lower a model-assigned CRITICAL.
        text = "Please add dark mode to the app."
        assert rule_severity(text, Severity.CRITICAL) == Severity.CRITICAL

    def test_severity_never_lowered_from_high(self) -> None:
        text = "Please add dark mode to the app."
        assert rule_severity(text, Severity.HIGH) == Severity.HIGH

    def test_no_trigger_keeps_model_medium(self) -> None:
        text = "Cannot share folder with external consultant."
        assert rule_severity(text, Severity.MEDIUM) == Severity.MEDIUM

    def test_suspicious_login_critical(self) -> None:
        text = (
            "We have detected suspicious login attempts. "
            "Two accounts may have been successfully compromised."
        )
        assert rule_severity(text, Severity.LOW) == Severity.CRITICAL


# ---------------------------------------------------------------------------
# ESCALATION_RULES table
# ---------------------------------------------------------------------------


class TestEscalationRulesTable:
    def test_all_policy_cases_covered(self) -> None:
        names = {r.name for r in ESCALATION_RULES}
        required = {
            "payment_dispute",
            "account_deletion",
            "security_incident",
            "data_loss",
            "legal",
            "enterprise_outage",
        }
        assert required.issubset(names)

    def test_each_rule_has_named_team(self) -> None:
        for rule in ESCALATION_RULES:
            assert rule.team, f"Rule '{rule.name}' has no team"
            assert rule.reason, f"Rule '{rule.name}' has no reason"


# ---------------------------------------------------------------------------
# matching_escalation_rules — demo tickets
# ---------------------------------------------------------------------------


class TestMatchingEscalationRules:
    def _teams(self, text: str) -> set[str]:
        return {r.team for r in matching_escalation_rules(text)}

    def test_cd_1005_suspicious_logins_security(self) -> None:
        text = (
            "We have detected suspicious login attempts on our account. "
            "Two accounts may have been successfully compromised. "
            "Please treat this as a security incident."
        )
        assert "security_team" in self._teams(text)

    def test_cd_1006_files_disappeared_data_recovery(self) -> None:
        text = (
            "Critical client files have disappeared from our shared folder. "
            "The files were there yesterday evening but are now gone."
        )
        assert "data_recovery_team" in self._teams(text)

    def test_cd_1009_delete_workspace_gdpr(self) -> None:
        text = (
            "Please delete legacy workspace and erase all data. "
            "We are exercising our GDPR right to erasure."
        )
        assert "data_compliance_team" in self._teams(text)

    def test_cd_1011_unauthorized_charge_dispute(self) -> None:
        text = "Unauthorized charge on our account — this is a payment dispute."
        assert "billing_disputes_team" in self._teams(text)

    def test_feature_request_no_escalation(self) -> None:
        text = "I would love to see a dark mode feature added to CloudDesk."
        assert len(matching_escalation_rules(text)) == 0

    def test_cd_1001_enterprise_outage(self) -> None:
        text = (
            "Our entire team of 143 users cannot log in. "
            "We are on the Enterprise plan with an active SLA. "
            "This is blocking all of them."
        )
        assert "enterprise_support_team" in self._teams(text)

    def test_plan_name_checked_too(self) -> None:
        # Text is benign but plan_name triggers legal rule
        text = "Some normal issue."
        teams = self._teams("")
        assert "legal_team" not in teams
        teams_with_plan = {
            r.team for r in matching_escalation_rules("Some normal issue.", "legal review required")
        }
        assert "legal_team" in teams_with_plan

    def test_no_false_positive_for_billing_ticket(self) -> None:
        # CD-1002: refund ticket should NOT trigger escalation rules
        text = (
            "Our invoice shows charges for 8 seats but we only have 5 active users. "
            "I would like a refund for the 3 unused seats."
        )
        # No escalation rule should match plain refund requests
        matched = matching_escalation_rules(text)
        teams = {r.team for r in matched}
        assert "security_team" not in teams
        assert "data_recovery_team" not in teams
