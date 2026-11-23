"""init_sentry() must stay a no-op without a DSN and must keep prompts/PII off."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import sentry_sdk

from app import observability


def _settings(dsn: str) -> SimpleNamespace:
    return SimpleNamespace(
        sentry_dsn=dsn,
        sentry_traces_sample_rate=0.25,
        app_env="staging",
    )


@pytest.fixture
def init_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(sentry_sdk, "is_initialized", lambda: False)
    return calls


def test_noop_when_dsn_empty(monkeypatch: pytest.MonkeyPatch, init_calls: list[dict]) -> None:
    monkeypatch.setattr(observability, "get_settings", lambda: _settings(""))
    observability.init_sentry()
    assert init_calls == []


def test_noop_when_already_initialized(
    monkeypatch: pytest.MonkeyPatch, init_calls: list[dict]
) -> None:
    monkeypatch.setattr(observability, "get_settings", lambda: _settings("https://k@o0.ingest.sentry.io/1"))
    monkeypatch.setattr(sentry_sdk, "is_initialized", lambda: True)
    observability.init_sentry()
    assert init_calls == []


def test_init_keeps_pii_and_prompts_off(
    monkeypatch: pytest.MonkeyPatch, init_calls: list[dict]
) -> None:
    monkeypatch.setattr(observability, "get_settings", lambda: _settings("https://k@o0.ingest.sentry.io/1"))
    observability.init_sentry()

    assert len(init_calls) == 1
    kwargs = init_calls[0]
    assert kwargs["send_default_pii"] is False
    assert kwargs["environment"] == "staging"
    assert kwargs["traces_sample_rate"] == 0.25

    by_name = {type(i).__name__: i for i in kwargs["integrations"]}
    assert by_name["AnthropicIntegration"].include_prompts is False
    assert by_name["LanggraphIntegration"].include_prompts is False
