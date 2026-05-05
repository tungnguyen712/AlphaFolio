"""Anthropic client wrapper with per-agent model tiering + structured output.

All agent → LLM calls go through `call_structured()`. It:

  1. Picks the model ID for the agent's tier from `settings.anthropic_model_{opus,sonnet,haiku}`.
  2. Forces a typed response by exposing a single tool whose `input_schema`
     is the target Pydantic model's JSON schema, then setting
     `tool_choice` to that tool. The model has no way to answer except by
     filling the tool's arguments — we parse those back into the Pydantic
     type before returning.
  3. Marks the system prompt as ephemeral-cacheable. Agent system prompts
     don't change between runs, so subsequent calls within ~5 min reuse
     the prefix instead of retokenizing it.
  4. Retries transient errors (rate-limit, 5xx, overload) with exponential
     backoff via tenacity.

Intentionally thin — no provider abstraction layer, no "llm" base class.
If we ever swap Anthropic, this file is the one edit.
"""
from __future__ import annotations

import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar

from anthropic import APIStatusError, AsyncAnthropic, RateLimitError
from anthropic.types import Message
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)

# Name is arbitrary but kept stable so prompt-cache keys stay warm.
_TOOL_NAME = "record_output"
_MILLION = 1_000_000
_PRICING_USD_PER_MILLION: dict[str, tuple[float, float]] = {
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}
_llm_call_records: ContextVar[list["LLMCallRecord"] | None] = ContextVar(
    "llm_call_records", default=None
)


class AgentTier(StrEnum):
    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"


def model_for(tier: AgentTier) -> str:
    settings = get_settings()
    match tier:
        case AgentTier.OPUS:
            return settings.anthropic_model_opus
        case AgentTier.SONNET:
            return settings.anthropic_model_sonnet
        case AgentTier.HAIKU:
            return settings.anthropic_model_haiku


class StructuredOutputError(RuntimeError):
    """Raised when the model returns text instead of the forced tool call, or the
    tool arguments fail Pydantic validation. Both mean a prompt/schema bug."""


@dataclass(slots=True)
class LLMCallRecord:
    agent_name: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float
    estimated_cost_usd: float | None


def start_llm_accounting() -> Token[list[LLMCallRecord] | None]:
    """Start collecting LLM usage records in the current async context."""
    return _llm_call_records.set([])


def reset_llm_accounting(token: Token[list[LLMCallRecord] | None]) -> None:
    _llm_call_records.reset(token)


def drain_llm_call_records(agent_name: str) -> list[LLMCallRecord]:
    records = _llm_call_records.get()
    if records is None:
        return []
    matched = [record for record in records if record.agent_name == agent_name]
    records[:] = [record for record in records if record.agent_name != agent_name]
    return matched


_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """Process-wide singleton. AsyncAnthropic manages its own httpx pool."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


@retry(
    retry=retry_if_exception_type((RateLimitError, APIStatusError)),
    wait=wait_exponential(multiplier=1, min=2, max=30) + wait_random(0, 1),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def call_structured(
    *,
    tier: AgentTier,
    agent_name: str | None = None,
    system: str,
    user: str,
    output_model: type[T],
    max_tokens: int = 4096,
    temperature: float | None = None,
) -> T:
    """Invoke Claude at the given tier and parse the reply into `output_model`.

    The system prompt is cacheable. Keep it stable across calls for the same
    agent — don't interpolate run-specific details into it (put those in the
    user message).

    `temperature` is opt-in: Opus 4.7 rejects it entirely, so we omit the
    kwarg unless a caller passes one explicitly.
    """
    client = get_client()
    tool_spec = _tool_spec_for(output_model)

    extra: dict[str, Any] = {}
    if temperature is not None:
        extra["temperature"] = temperature

    model = model_for(tier)
    started = time.perf_counter()
    response: Message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[tool_spec],
        tool_choice={"type": "tool", "name": _TOOL_NAME},
        messages=[{"role": "user", "content": user}],
        **extra,
    )
    if agent_name is not None:
        _record_llm_call(
            agent_name=agent_name,
            model=model,
            response=response,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    payload = _extract_tool_input(response)
    payload = _unwrap_if_wrapped(payload, output_model)
    payload = _coerce_stringified_collections(payload)
    try:
        return output_model.model_validate(payload)
    except ValidationError as exc:
        # Truncation is the most common cause of a partial tool_use payload.
        # Surface stop_reason so the caller bumps max_tokens instead of
        # chasing a phantom "prompt/schema" bug.
        hint = (
            "\n\nHINT: model hit max_tokens before finishing the tool call — "
            "raise max_tokens for this agent."
            if response.stop_reason == "max_tokens"
            else ""
        )
        raise StructuredOutputError(
            f"{output_model.__name__} validation failed "
            f"(stop_reason={response.stop_reason}):\n{exc}\n\nRaw payload: {payload!r}{hint}"
        ) from exc


def _tool_spec_for(output_model: type[BaseModel]) -> dict[str, Any]:
    schema = output_model.model_json_schema()
    return {
        "name": _TOOL_NAME,
        "description": (
            f"Record a structured {output_model.__name__}. Every field must be "
            "filled in accordance with the JSON schema — no free text responses. "
            "Fill the schema fields directly at the top level of the tool input; "
            "do NOT wrap them under a 'parameter' or 'arguments' key."
        ),
        "input_schema": schema,
    }


def _coerce_stringified_collections(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse any top-level values that the LLM accidentally serialised as JSON strings.

    e.g. `{"signals": "[{...}]"}` → `{"signals": [{...}]}`.
    Only acts on strings that parse as a list or dict — leaves plain strings alone.
    """
    import json as _json

    result: dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith(("[", "{")):
                try:
                    result[k] = _json.loads(stripped)
                    continue
                except _json.JSONDecodeError:
                    pass
        result[k] = v
    return result


def _unwrap_if_wrapped(
    payload: dict[str, Any], output_model: type[BaseModel]
) -> dict[str, Any]:
    """Defensive unwrap for the Opus tool-use wrapping quirk.

    When the output schema has deep $defs (nested Pydantic models), Opus
    occasionally emits the tool input as `{"parameter": {<real payload>}}`
    instead of filling top-level fields directly. We detect that shape —
    payload is a single-key dict whose value is a dict AND the key name is
    NOT a declared field on the target model — and unwrap once.
    """
    if len(payload) != 1:
        return payload
    (only_key,) = payload.keys()
    only_value = payload[only_key]
    if not isinstance(only_value, dict):
        return payload
    if only_key in output_model.model_fields:
        return payload
    return only_value


def _extract_tool_input(response: Message) -> dict[str, Any]:
    for block in response.content:
        # anthropic.types.ToolUseBlock — duck-type on attribute to avoid
        # version-brittle isinstance checks.
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == _TOOL_NAME:
            return dict(block.input)  # type: ignore[arg-type]
    raise StructuredOutputError(
        "Model response contained no forced tool call. "
        f"Stop reason: {response.stop_reason}. Content blocks: "
        f"{[getattr(b, 'type', type(b).__name__) for b in response.content]}"
    )


def _record_llm_call(
    *,
    agent_name: str,
    model: str,
    response: Message,
    latency_ms: float,
) -> None:
    records = _llm_call_records.get()
    if records is None:
        return
    usage = getattr(response, "usage", None)
    input_tokens = _int_or_none(getattr(usage, "input_tokens", None))
    output_tokens = _int_or_none(getattr(usage, "output_tokens", None))
    records.append(
        LLMCallRecord(
            agent_name=agent_name,
            model=_normalize_model(model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=_estimate_cost_usd(model, input_tokens, output_tokens),
        )
    )


def _normalize_model(model: str) -> str:
    return model.strip().lower()


def _estimate_cost_usd(
    model: str, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    normalized = _normalize_model(model)
    for family, (input_rate, output_rate) in _PRICING_USD_PER_MILLION.items():
        if family in normalized:
            cost = (
                (input_tokens or 0) * input_rate
                + (output_tokens or 0) * output_rate
            ) / _MILLION
            return round(cost, 6)
    return None


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None
