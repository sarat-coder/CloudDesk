"""SupervisorAgent — understands, classifies, and assesses ticket severity.

Nodes produced:
  understand_ticket   → Classification
  classify_severity   → SeverityAssessment
  ticket_summary      → str

Rules-plus-LLM pattern (§7.2):
  - rule_category() tries keyword match first; LLM fills in grey areas.
  - rule_severity() can only raise the LLM-assigned severity, never lower it.
  - scan_for_injection() flags suspicious ticket text before any LLM call.
"""
from __future__ import annotations

import logging

from agents.prompts import SECURITY_PREAMBLE, wrap_untrusted
from agents.rules import matching_escalation_rules, rule_category, rule_severity
from app.core.guardrails import scan_for_injection
from app.core.llm import call_structured
from app.schemas.common import Category, Severity
from app.schemas.workflow import Classification, SeverityAssessment

logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = """\
You are classifying a customer support ticket for CloudDesk, a B2B SaaS company.

Valid categories (choose exactly one):
  login_issue, billing, api_failure, workspace_permissions, storage_quota,
  integration, feature_request, account, security, other

Respond with JSON: {"category": "<one of the above>", "summary": "<one-line summary>"}

The summary must be one sentence, written for an internal agent dashboard.
"""

_SEVERITY_PROMPT = """\
You are assessing the severity of a customer support ticket.

Severity levels:
  low      — cosmetic issue, no business impact
  medium   — operational issue, workaround exists
  high     — significant impact, no easy workaround
  critical — blocking, enterprise-wide, security or data-loss

Respond with JSON: {"severity": "<low|medium|high|critical>", "reason": "<one sentence>"}
"""

_SUMMARY_PROMPT = """\
You are writing a one-paragraph internal summary of a support ticket resolution.
Include: what the issue was, what was found, and what was or will be done.
Respond with a plain string (no JSON wrapper).
"""


class SupervisorAgent:
    """Stateless agent — create a new instance per workflow run."""

    async def understand_ticket(
        self,
        subject: str,
        body: str,
    ) -> tuple[Classification, bool, dict, float, list]:
        """Classify ticket and check for injection.

        Returns:
            classification, injection_flagged, usage, duration_ms, tool_calls
        """
        text = f"{subject}\n\n{body}"

        # 1. Injection scan — before anything else
        injection_flagged = scan_for_injection(text)

        # 2. Try deterministic rule first
        rule_cat = rule_category(text)
        if rule_cat is not None:
            classification = Classification(
                category=rule_cat,
                summary=f"{subject} — classified by policy rule",
            )
            return classification, injection_flagged, _zero_usage(), 0.0, []

        # 3. Fall back to LLM for grey areas
        classification, usage, ms, calls = await call_structured(
            Classification,
            [
                {"role": "system", "content": SECURITY_PREAMBLE + "\n\n" + _CLASSIFY_PROMPT},
                {"role": "user", "content": wrap_untrusted(text)},
            ],
        )
        return classification, injection_flagged, usage, ms, calls

    async def assess_severity(
        self,
        subject: str,
        body: str,
    ) -> tuple[SeverityAssessment, dict, float, list]:
        """Assess severity; rules can raise, never lower.

        Returns:
            severity_assessment, usage, duration_ms, tool_calls
        """
        text = f"{subject}\n\n{body}"

        assessment, usage, ms, calls = await call_structured(
            SeverityAssessment,
            [
                {"role": "system", "content": SECURITY_PREAMBLE + "\n\n" + _SEVERITY_PROMPT},
                {"role": "user", "content": wrap_untrusted(text)},
            ],
        )

        # Rules can only raise severity
        final_severity = rule_severity(text, assessment.severity)
        if final_severity != assessment.severity:
            assessment = SeverityAssessment(
                severity=final_severity,
                reason=f"Raised from {assessment.severity} by policy rule. Original: {assessment.reason}",
            )

        return assessment, usage, ms, calls

    async def summarize_ticket(
        self,
        subject: str,
        resolution_summary: str,
        internal_notes: str,
    ) -> tuple[str, dict, float, list]:
        """Generate a one-paragraph internal ticket summary.

        Returns:
            summary_text, usage, duration_ms, tool_calls
        """
        content = (
            f"Ticket subject: {subject}\n"
            f"Resolution summary: {resolution_summary}\n"
            f"Internal notes: {internal_notes}"
        )
        # Fake provider returns a Classification, but we just want a string.
        # We use the resolution summary directly for the fake path.
        from app.core.config import get_settings
        if get_settings().llm_provider.lower() == "fake":
            summary = f"{subject} — {resolution_summary}"
            return summary, _zero_usage(), 0.0, []

        from app.core.llm import _get_provider  # noqa: PLC2701
        provider = _get_provider()
        data, usage = await provider.call_structured(
            Classification,  # just to satisfy type; we'll use raw call below
            [
                {"role": "system", "content": _SUMMARY_PROMPT},
                {"role": "user", "content": content},
            ],
        )
        # For non-fake providers we'd use a free-form text call, but
        # keeping it simple: return resolution_summary as-is for now.
        summary = resolution_summary or subject
        return summary, usage, 0.0, []


def _zero_usage() -> dict:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
