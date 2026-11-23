"""Sentry setup shared by the API and the Celery worker.

The API (uvicorn) and the worker (celery) are separate processes, so each one
calls `init_sentry()` exactly once from its own entry point:
  - API:    app/main.py, before `create_app()`
  - Worker: the `celeryd_init` signal handler in app/workers/celery_app.py

Do NOT call this at import time of celery_app.py: the API imports that module
too (through app.workers.tasks), which would init Sentry twice in the API.
"""
from __future__ import annotations

import sentry_sdk
from sentry_sdk.integrations.anthropic import AnthropicIntegration
from sentry_sdk.integrations.langgraph import LanggraphIntegration

from app.config import get_settings


def init_sentry() -> None:
    """Initialise Sentry. No-op when SENTRY_DSN is empty or Sentry is already up."""
    settings = get_settings()
    if not settings.sentry_dsn:
        return
    if sentry_sdk.is_initialized():
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # Prompts and tool inputs carry user portfolio data. Keep all of it off:
        # no request bodies, cookies, user IPs or LLM inputs/outputs.
        send_default_pii=False,
        # FastAPI, Celery and the logging integrations auto-enable when their
        # packages are installed. The two below are listed explicitly only to pin
        # include_prompts=False; the SDK's default for it varies by version.
        integrations=[
            AnthropicIntegration(include_prompts=False),
            LanggraphIntegration(include_prompts=False),
        ],
    )
