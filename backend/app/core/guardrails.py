"""Guardrails: injection detection, output validation, and secret scrubbing.

§9 of CLAUDE.md:
  - scan_for_injection (N4): flags suspicious ticket text before it enters any prompt.
  - validate_customer_output (N5): rejects internal URLs, secrets, and other customers'
    data before a reply is shown. Failure defines risk as "high".
  - scrub (N7): removes card numbers, API keys, and passwords before memory writes.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Secret / PII patterns — used by both validate_customer_output and scrub
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    # Payment card numbers
    re.compile(r"\b4[0-9]{12}(?:[0-9]{3})?\b"),          # Visa
    re.compile(r"\b5[1-5][0-9]{14}\b"),                   # Mastercard
    re.compile(r"\b3[47][0-9]{13}\b"),                    # Amex
    re.compile(r"\b6(?:011|5[0-9]{2})[0-9]{12}\b"),       # Discover
    re.compile(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b"),  # grouped card
    # LLM provider API keys
    re.compile(r"sk-[A-Za-z0-9]{48}"),                    # OpenAI key
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{90,}"),            # Anthropic key
    # Generic secret assignment patterns
    re.compile(r"(?i)password\s*[=:]\s*\S+"),
    re.compile(r"(?i)pwd\s*[=:]\s*\S+"),
    re.compile(r"(?i)api[_-]?key\s*[=:]\s*\S+"),
    re.compile(r"(?i)secret\s*[=:]\s*\S+"),
    # HTTP Bearer tokens and JWTs
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(
        r"eyJ[A-Za-z0-9\-_]{10,}\.eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_.+/]*"
    ),
]

# ---------------------------------------------------------------------------
# Internal URL patterns — must not appear in customer-facing replies
# ---------------------------------------------------------------------------

_INTERNAL_URL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"https?://localhost", re.IGNORECASE),
    re.compile(r"https?://127\.", re.IGNORECASE),
    re.compile(r"https?://10\.", re.IGNORECASE),
    re.compile(r"https?://192\.168\.", re.IGNORECASE),
    re.compile(r"\.internal\b", re.IGNORECASE),
    re.compile(r"\binternal\.clouddesk\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Prompt injection patterns
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?i)ignore\s+(all\s+)?(previous|prior|above|your)\s+instructions"
    ),
    re.compile(r"(?i)disregard\b.{0,40}\binstructions\b"),
    re.compile(
        r"(?i)forget\s+(all\s+)?(previous|prior|above|your)\s+instructions"
    ),
    re.compile(r"(?i)you\s+are\s+now\s+"),
    re.compile(r"(?i)pretend\s+(you\s+are|to\s+be)"),
    re.compile(r"(?i)act\s+as\s+(if\s+you\s+are|a\s+)"),
    re.compile(r"(?i)export\s+all\s+(customer|user|data|record)"),
    re.compile(r"(?i)reveal\s+(your\s+)?(system\s+)?prompt"),
    re.compile(r"(?i)print\s+all\s+(customer|user|data|record)"),
    re.compile(r"(?i)show\s+me\s+all\s+(customer|user|data|record)"),
    re.compile(r"(?i)\bjailbreak\b"),
    re.compile(r"(?i)\bDAN\s+mode\b"),
    re.compile(r"(?i)override\s+(your\s+)?(safety|restriction|instruction)"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_for_injection(text: str) -> bool:
    """Return True if the text contains potential prompt-injection patterns.

    When True, the ticket is flagged and the text must be wrapped via
    wrap_untrusted before entering any prompt. Risk is raised to 'high'.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def validate_customer_output(
    text: str,
    current_customer_id: str | None = None,
) -> tuple[bool, str]:
    """Validate that text is safe to surface to a customer.

    Checks:
      - No internal/private URLs
      - No secrets or PII matching known patterns

    Returns:
        (is_valid, reason) — is_valid=False means risk must be raised to 'high'.
    """
    for pattern in _INTERNAL_URL_PATTERNS:
        if pattern.search(text):
            return False, f"Internal URL detected in customer-facing reply"

    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return False, "Secret or sensitive data pattern detected in reply"

    return True, ""


def scrub(text: str) -> str:
    """Remove known secret patterns from text before writing to memory (N7).

    Replaces card numbers, API keys, passwords, and tokens with [REDACTED].
    """
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result
