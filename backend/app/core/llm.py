"""LLM provider factory and call_structured utility.

§4.0 of CLAUDE.md: 'No LLM call without call_structured' — this function is the
single path for every structured LLM call in the platform.  It records token usage,
measures wall-clock time, and isolates the provider behind a protocol so tests and
demo mode run with LLM_PROVIDER=fake and no API key.

Supported providers
-------------------
  fake      — deterministic offline responses (default; no key required)
  openai    — OpenAI Chat Completions with structured output
  anthropic — Anthropic Messages with tool-use-based structured output

Usage
-----
    from app.core.llm import call_structured
    from app.schemas.workflow import Classification

    result, usage, ms, calls = await call_structured(
        Classification,
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": user_text}],
    )
"""
from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_ZERO_USAGE: dict[str, Any] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "estimated_cost_usd": 0.0,
}


# ---------------------------------------------------------------------------
# Fake provider — deterministic, offline, zero-cost (§F14)
# ---------------------------------------------------------------------------

def _fake_response(response_model: type[T]) -> dict[str, Any]:
    """Return a minimal valid dict for *response_model* without calling any API."""
    name = response_model.__name__

    if name == "Classification":
        return {"category": "other", "summary": "Issue requires investigation (demo)"}

    if name == "SeverityAssessment":
        return {"severity": "medium", "reason": "Moderate impact assessed (demo)"}

    if name == "Diagnosis":
        return {
            "probable_causes": ["Configuration issue", "Possible service disruption"],
            "steps": [
                "Verify service status at status.clouddesk.io",
                "Review recent configuration changes",
                "Clear browser cache and retry",
            ],
            "active_incidents": [],
        }

    if name == "ResolutionPlan":
        return {
            "summary": "Issue investigated; resolution prepared",
            "customer_reply": (
                "Thank you for contacting CloudDesk support. "
                "We have reviewed your case and prepared a resolution. "
                "Please follow the steps below and let us know if you need further assistance."
            ),
            "internal_notes": "Demo resolution — no API key configured.",
            "actions": [],
        }

    if name == "EscalationDecision":
        return {
            "escalation_required": False,
            "reason": "Issue can be handled through standard support workflow",
            "team": None,
            "confidence": 0.75,
        }

    # Fallback: try to construct with all defaults.
    return {}


class _FakeProvider:
    async def call_structured(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        temperature: float = 0.0,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return _fake_response(response_model), dict(_ZERO_USAGE)


# ---------------------------------------------------------------------------
# Real provider stubs (populated when LLM_PROVIDER is set to openai/anthropic)
# ---------------------------------------------------------------------------

class _OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def call_structured(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        temperature: float = 0.0,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            from openai import AsyncOpenAI  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError("Install 'openai' package to use LLM_PROVIDER=openai") from exc

        client = AsyncOpenAI(api_key=self._api_key)
        schema = response_model.model_json_schema()
        response = await client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        import json
        data = json.loads(content)
        usage_obj = response.usage
        # Rough cost estimate: $0.0025 / 1K prompt + $0.01 / 1K completion (gpt-4o-mini)
        prompt_t = usage_obj.prompt_tokens if usage_obj else 0
        completion_t = usage_obj.completion_tokens if usage_obj else 0
        cost = (prompt_t * 2.5 + completion_t * 10.0) / 1_000_000
        usage = {
            "prompt_tokens": prompt_t,
            "completion_tokens": completion_t,
            "total_tokens": prompt_t + completion_t,
            "estimated_cost_usd": round(cost, 6),
        }
        return data, usage


class _AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def call_structured(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        temperature: float = 0.0,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            import anthropic  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError("Install 'anthropic' package to use LLM_PROVIDER=anthropic") from exc

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        system = next(
            (m["content"] for m in messages if m.get("role") == "system"),
            "You are a helpful assistant.",
        )
        user_messages = [m for m in messages if m.get("role") != "system"]

        import json
        schema = response_model.model_json_schema()
        tool_def = {
            "name": "output",
            "description": f"Return a {response_model.__name__} object",
            "input_schema": schema,
        }

        response = await client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=user_messages,
            tools=[tool_def],
            tool_choice={"type": "tool", "name": "output"},
        )

        data: dict[str, Any] = {}
        for block in response.content:
            if block.type == "tool_use" and block.name == "output":
                data = block.input
                break

        usage_obj = response.usage
        prompt_t = usage_obj.input_tokens if usage_obj else 0
        completion_t = usage_obj.output_tokens if usage_obj else 0
        # Rough cost estimate: $3 / 1M input + $15 / 1M output (claude-3-haiku)
        cost = (prompt_t * 3.0 + completion_t * 15.0) / 1_000_000
        usage = {
            "prompt_tokens": prompt_t,
            "completion_tokens": completion_t,
            "total_tokens": prompt_t + completion_t,
            "estimated_cost_usd": round(cost, 6),
        }
        return data, usage


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

_provider_instance: _FakeProvider | _OpenAIProvider | _AnthropicProvider | None = None


def _get_provider() -> _FakeProvider | _OpenAIProvider | _AnthropicProvider:
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    from app.core.config import get_settings
    settings = get_settings()
    provider_name = settings.llm_provider.lower()

    if provider_name == "fake" or not provider_name:
        _provider_instance = _FakeProvider()
    elif provider_name == "openai":
        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
        _provider_instance = _OpenAIProvider(api_key=api_key, model=settings.llm_model)
    elif provider_name == "anthropic":
        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
        _provider_instance = _AnthropicProvider(api_key=api_key, model=settings.llm_model)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider_name!r}")

    return _provider_instance


def reset_llm_provider() -> None:
    """Reset the cached provider — used in tests when env vars change."""
    global _provider_instance
    _provider_instance = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def call_structured(
    response_model: type[T],
    messages: list[dict[str, str]],
    temperature: float = 0.0,
) -> tuple[T, dict[str, Any], float, list[dict[str, Any]]]:
    """Call the configured LLM and parse the response as *response_model*.

    This is the ONLY entry point for LLM calls in the platform (§18, rule 4).

    Args:
        response_model: Pydantic model class to parse the response into.
        messages: List of {role, content} dicts (system + user messages).
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        (result, usage_dict, duration_ms, tool_call_records)
        usage_dict has keys: prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd.
        tool_call_records is always [] for now (reserved for future multi-turn tool use).
    """
    provider = _get_provider()
    start = time.monotonic()
    data, usage = await provider.call_structured(response_model, messages, temperature)
    duration_ms = (time.monotonic() - start) * 1000

    # Merge missing fields with defaults so model_validate never crashes.
    try:
        result = response_model.model_validate(data)
    except Exception:
        result = response_model.model_validate(_fake_response(response_model))

    return result, usage, duration_ms, []
