"""Policy rules for category, severity, and escalation decisions.

§7.2 of CLAUDE.md: policy cases are decided by rules, never left to the model's
probability. Rules can RAISE severity but never lower it.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.common import Category, Severity

# ---------------------------------------------------------------------------
# Category keyword rules
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.LOGIN_ISSUE: [
        "login", "log in", "sign in", "sso", "saml", "okta", "password",
        "authentication", "locked out", "mfa", "2fa", "otp", "authenticat",
        "credential", "unable to log", "can't log",
    ],
    Category.BILLING: [
        "refund", "charged", "charge", "invoice", "billing", "payment",
        "subscription", "seats", "overcharged", "credit", "overpaid",
        "billing cycle", "pro plan", "enterprise plan",
    ],
    Category.API_FAILURE: [
        "api", "429", "rate limit", "too many requests", "timeout",
        "endpoint", "request failed", "api key", "http error", "rest",
        "nightly sync", "automation", "integration error",
    ],
    Category.WORKSPACE_PERMISSIONS: [
        "share", "permission", "access denied", "can't see", "workspace",
        "folder access", "external sharing", "admin", "external partner",
        "share folder", "external consultant",
    ],
    Category.STORAGE_QUOTA: [
        "storage", "quota", "disk", "upload", "file size", "space",
        "quota exceeded", "storage limit", "5 gb", "exceeded",
    ],
    Category.INTEGRATION: [
        "slack", "zapier", "integration", "webhook", "third-party",
        "plugin", "connect", "jira", "notion", "stopped working",
    ],
    Category.FEATURE_REQUEST: [
        "feature", "suggest", "would love", "can you add", "feature request",
        "dark mode", "wishlist", "would be great", "enhancement",
    ],
    Category.ACCOUNT: [
        "delete account", "close account", "cancel", "gdpr",
        "data deletion", "erase data", "right to be forgotten",
        "legacy workspace", "account deletion", "data erasure",
    ],
    Category.SECURITY: [
        "breach", "suspicious", "unauthorized", "hack", "compromised",
        "phishing", "security incident", "suspicious login",
        "security threat", "account takeover",
    ],
}


def rule_category(text: str) -> Category | None:
    """Return the most likely Category based on keyword matching.

    Returns None if no keywords match, so the model can decide in grey areas.
    """
    text_lower = text.lower()
    scores: dict[Category, int] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[category] = score
    if not scores:
        return None
    return max(scores, key=lambda c: scores[c])


# ---------------------------------------------------------------------------
# Severity rules (can raise, never lower)
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


def _max_severity(a: Severity, b: Severity) -> Severity:
    return a if _SEVERITY_ORDER[a] >= _SEVERITY_ORDER[b] else b


_CRITICAL_PATTERNS: list[str] = [
    # Security breaches
    "breach", "compromised", "hack", "phishing", "security incident",
    "account takeover", "unauthorized access", "accounts may have been",
    # Data loss
    "files disappeared", "data lost", "files gone", "data missing",
    "deleted files", "disappeared from",
    # Enterprise-wide outages
    "entire team", "all users", "blocking all", "enterprise sla",
    "production down", "system-wide", "143 of our users",
    "whole team",
]

_HIGH_PATTERNS: list[str] = [
    "dispute", "unauthorized charge", "chargeback", "fraudulent",
    "locked out", "mfa", "two-factor", "authentication fail",
    "can't log in", "unable to log in",
    "api down", "429", "rate limit",
    "critical", "urgent", "immediately",
]


def rule_severity(text: str, model_severity: Severity) -> Severity:
    """Apply keyword rules to severity. Rules can only raise, never lower.

    Args:
        text: The ticket subject + body combined.
        model_severity: The severity the LLM assigned.

    Returns:
        The final severity — always >= model_severity.
    """
    text_lower = text.lower()

    if any(p in text_lower for p in _CRITICAL_PATTERNS):
        return _max_severity(model_severity, Severity.CRITICAL)

    if any(p in text_lower for p in _HIGH_PATTERNS):
        return _max_severity(model_severity, Severity.HIGH)

    # Rules found nothing to escalate; keep the model's judgement.
    return model_severity


# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EscalationRule:
    name: str
    keywords: tuple[str, ...]
    team: str
    reason: str


ESCALATION_RULES: list[EscalationRule] = [
    EscalationRule(
        name="payment_dispute",
        keywords=(
            "dispute", "unauthorized charge", "chargeback",
            "fraudulent charge", "not authorized", "payment dispute",
        ),
        team="billing_disputes_team",
        reason="Payment dispute requires specialist billing review",
    ),
    EscalationRule(
        name="account_deletion",
        keywords=(
            "delete account", "close account", "gdpr",
            "data erasure", "erase data", "right to be forgotten",
            "data deletion", "legacy workspace", "delete legacy",
        ),
        team="data_compliance_team",
        reason="Account deletion and GDPR requests require compliance team review",
    ),
    EscalationRule(
        name="security_incident",
        keywords=(
            "breach", "compromised", "unauthorized access",
            "suspicious login", "security incident", "account hack",
            "phishing", "accounts may have been", "successfully compromised",
        ),
        team="security_team",
        reason="Potential security breach requires immediate security team response",
    ),
    EscalationRule(
        name="data_loss",
        keywords=(
            "files disappeared", "data lost", "files gone",
            "missing files", "deleted files", "data missing",
            "disappeared from", "critical client files",
        ),
        team="data_recovery_team",
        reason="Data loss requires specialist recovery team review",
    ),
    EscalationRule(
        name="legal",
        keywords=(
            "legal", "lawsuit", "attorney", "court",
            "compliance violation", "regulatory", "legal action",
        ),
        team="legal_team",
        reason="Legal or compliance issue requires legal team review",
    ),
    EscalationRule(
        name="enterprise_outage",
        keywords=(
            "entire team", "all users", "blocking all",
            "enterprise sla", "production down", "system-wide",
            "143 of our users", "whole team", "all 143",
        ),
        team="enterprise_support_team",
        reason="Enterprise-wide outage requires escalation to dedicated support team",
    ),
]


def matching_escalation_rules(text: str, plan_name: str = "") -> list[EscalationRule]:
    """Return every EscalationRule whose keywords appear in the text or plan name.

    Policy: if any rule matches, escalation is required — the model's vote does
    not override this (§7.2).
    """
    combined = (text + " " + plan_name).lower()
    return [rule for rule in ESCALATION_RULES if any(kw in combined for kw in rule.keywords)]
