"""TroubleshootingAgent — diagnoses the root cause and proposes numbered steps.

Node produced: troubleshooting → Diagnosis

Playbook enrichment: adds category-specific steps before the LLM call so
the model always has a concrete starting point (§7.1).
"""
from __future__ import annotations

import logging
from typing import Any

from agents.prompts import SECURITY_PREAMBLE, wrap_untrusted
from app.core.llm import call_structured
from app.schemas.workflow import Diagnosis, Evidence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category-specific playbook hints
# ---------------------------------------------------------------------------

_PLAYBOOKS: dict[str, list[str]] = {
    "login_issue": [
        "Check whether SSO/SAML configuration is correct in the IdP.",
        "Verify MFA device or backup codes are available.",
        "Confirm the user account is not locked or suspended.",
    ],
    "billing": [
        "Compare invoice line items against active seat count.",
        "Verify billing cycle dates and proration rules.",
        "Check for pending plan changes or failed payment retries.",
    ],
    "api_failure": [
        "Check current rate-limit quota and usage dashboard.",
        "Verify API key is valid and has not been rotated.",
        "Review request payload for malformed JSON or missing fields.",
    ],
    "workspace_permissions": [
        "Confirm external sharing is enabled in workspace admin settings.",
        "Check folder-level permission overrides.",
        "Verify user role is not set to 'viewer' unintentionally.",
    ],
    "storage_quota": [
        "Compare storage_used_gb against storage_limit_gb in workspace settings.",
        "Identify large files or folders that can be archived or deleted.",
        "Verify whether a plan upgrade includes additional storage.",
    ],
    "integration": [
        "Re-authenticate the integration via the connected apps page.",
        "Check webhook endpoint URL and verify it returns HTTP 200.",
        "Review recent changes to the third-party app's API credentials.",
    ],
    "security": [
        "Force-sign-out all active sessions immediately.",
        "Rotate API keys and service account credentials.",
        "Enable login notifications and review recent access logs.",
    ],
}

_DIAGNOSE_PROMPT = """\
You are diagnosing a customer support ticket for CloudDesk, a B2B SaaS platform.

Based on the ticket text, service status information, and playbook hints provided,
identify the most likely root causes and write clear numbered troubleshooting steps.

Respond with JSON matching this schema:
{
  "probable_causes": ["<string>", ...],
  "steps": ["<numbered step>", ...],
  "active_incidents": []
}

Keep steps actionable and specific.  Steps should come from the playbook hints and
the evidence provided, not from general knowledge.
"""


class TroubleshootingAgent:
    """Stateless agent — produces a Diagnosis for a support ticket."""

    async def run(
        self,
        subject: str,
        body: str,
        category: str,
        evidence: list[Evidence] | None = None,
        customer_context_summary: str = "",
    ) -> tuple[Diagnosis, dict, float, list]:
        """Diagnose the ticket and return probable causes + numbered steps.

        Returns:
            diagnosis, usage, duration_ms, tool_calls
        """
        from app.tools.registry import get_registry

        tool_calls: list[dict] = []
        registry = get_registry()

        # 1. Check for active incidents
        r_status = await registry.execute("check_service_status")
        tool_calls.append({"tool": "check_service_status", "ok": r_status.ok})
        active_incidents: list[dict] = []
        if r_status.ok and r_status.data:
            active_incidents = r_status.data.get("active_incidents", [])

        # 2. Build enriched prompt context
        playbook_steps = _PLAYBOOKS.get(category, [])
        playbook_text = (
            "\n".join(f"  - {s}" for s in playbook_steps)
            if playbook_steps
            else "  (no specific playbook for this category)"
        )

        evidence_text = ""
        if evidence:
            snippets = [f"  [{e.title}]: {e.snippet[:200]}" for e in evidence[:3]]
            evidence_text = "Knowledge base evidence:\n" + "\n".join(snippets)

        incidents_text = ""
        if active_incidents:
            inc_lines = [
                f"  [{i.get('severity','?').upper()}] {i.get('title','')}: {i.get('description','')[:100]}"
                for i in active_incidents[:3]
            ]
            incidents_text = "Active service incidents:\n" + "\n".join(inc_lines)

        user_content = (
            f"Ticket subject: {subject}\n\n"
            f"Category: {category}\n\n"
            f"Playbook hints:\n{playbook_text}\n\n"
            + (evidence_text + "\n\n" if evidence_text else "")
            + (incidents_text + "\n\n" if incidents_text else "")
            + f"Customer context: {customer_context_summary}\n\n"
            f"Ticket body:\n"
        ) + wrap_untrusted(body)

        # 3. Call LLM for diagnosis
        diagnosis, usage, ms, llm_calls = await call_structured(
            Diagnosis,
            [
                {"role": "system", "content": SECURITY_PREAMBLE + "\n\n" + _DIAGNOSE_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        tool_calls.extend(llm_calls)

        # Merge active incidents from live check into result
        if active_incidents and not diagnosis.active_incidents:
            diagnosis = Diagnosis(
                probable_causes=diagnosis.probable_causes,
                steps=diagnosis.steps,
                active_incidents=active_incidents[:3],
            )

        return diagnosis, usage, ms, tool_calls
