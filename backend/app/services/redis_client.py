"""Async Redis client singleton for SSE run-event pub/sub.

Never raises to callers — Redis unavailability must not fail agent runs.
All errors are logged and swallowed in publish helpers.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
        )
    return _redis


def run_event_channel(run_id: UUID) -> str:
    return f"run:{run_id}:events"


async def publish_run_event(run_id: UUID, payload: dict[str, Any]) -> None:
    """Publish a run event. Errors are logged and swallowed."""
    try:
        r = get_redis()
        await r.publish(run_event_channel(run_id), json.dumps(payload))
    except Exception:
        logger.warning("Redis publish failed for run %s", run_id, exc_info=True)
