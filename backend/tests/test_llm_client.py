"""Tests for app.services.llm.anthropic_client.

No real API calls. We patch messages.create to return a faked tool_use block
and verify the client parses it into the Pydantic output type, handles bad
payloads, and maps tiers to the configured model IDs.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, Field

from app.services.llm.anthropic_client import (
    AgentTier,
    StructuredOutputError,
    call_structured,
    model_for,
)


class _Dummy(BaseModel):
    verdict: str
    confidence: float = Field(ge=0.0, le=1.0)


def _fake_message(payload: dict | None, *, stop_reason: str = "tool_use") -> SimpleNamespace:
    if payload is None:
        content = [SimpleNamespace(type="text", text="I refuse")]
    else:
        content = [
            SimpleNamespace(type="tool_use", name="record_output", input=payload),
        ]
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def test_model_for_resolves_each_tier() -> None:
    # Reads from get_settings(); default values in config.py are non-empty.
    assert model_for(AgentTier.OPUS)
    assert model_for(AgentTier.SONNET)
    assert model_for(AgentTier.HAIKU)


async def test_call_structured_parses_tool_input() -> None:
    fake = AsyncMock(return_value=_fake_message({"verdict": "BUY", "confidence": 0.72}))
    with patch(
        "app.services.llm.anthropic_client.get_client",
        return_value=SimpleNamespace(messages=SimpleNamespace(create=fake)),
    ):
        result = await call_structured(
            tier=AgentTier.SONNET,
            system="sys",
            user="usr",
            output_model=_Dummy,
        )

    assert isinstance(result, _Dummy)
    assert result.verdict == "BUY"
    assert result.confidence == 0.72

    # Confirm the call used tool-choice = record_output and cached system.
    call_kwargs = fake.await_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "record_output"}
    assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call_kwargs["tools"][0]["name"] == "record_output"


async def test_call_structured_raises_when_no_tool_use_block() -> None:
    fake = AsyncMock(return_value=_fake_message(None, stop_reason="end_turn"))
    with patch(
        "app.services.llm.anthropic_client.get_client",
        return_value=SimpleNamespace(messages=SimpleNamespace(create=fake)),
    ):
        with pytest.raises(StructuredOutputError, match="no forced tool call"):
            await call_structured(
                tier=AgentTier.HAIKU,
                system="sys",
                user="usr",
                output_model=_Dummy,
            )


async def test_call_structured_unwraps_opus_parameter_wrapper() -> None:
    """Opus sometimes returns `{"parameter": {<real payload>}}`; we unwrap once."""
    fake = AsyncMock(
        return_value=_fake_message({"parameter": {"verdict": "BUY", "confidence": 0.66}})
    )
    with patch(
        "app.services.llm.anthropic_client.get_client",
        return_value=SimpleNamespace(messages=SimpleNamespace(create=fake)),
    ):
        result = await call_structured(
            tier=AgentTier.OPUS,
            system="sys",
            user="usr",
            output_model=_Dummy,
        )

    assert result.verdict == "BUY"
    assert result.confidence == 0.66


async def test_call_structured_raises_on_bad_tool_input() -> None:
    fake = AsyncMock(return_value=_fake_message({"verdict": "BUY", "confidence": 5.0}))
    with patch(
        "app.services.llm.anthropic_client.get_client",
        return_value=SimpleNamespace(messages=SimpleNamespace(create=fake)),
    ):
        with pytest.raises(StructuredOutputError, match="validation failed"):
            await call_structured(
                tier=AgentTier.OPUS,
                system="sys",
                user="usr",
                output_model=_Dummy,
            )
