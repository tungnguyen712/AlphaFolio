"""Cache + rate-limit decorator for data-provider calls.

Two concerns in one module because they always compose: every provider call
goes cache-first, then rate-limit-gated if we miss, then writes back.

Cache is read-through against the `signal_cache` Postgres table (already in
the initial migration). Rate limiting is per-host, single-process asyncio —
fine for MVP; swap to a Redis-backed limiter when we scale to multiple
workers hitting the same SEC/Tavily host.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.models.db import SignalCache

T = TypeVar("T")
JsonDict = dict[str, Any]


class AsyncRateLimiter:
    """Leaky-bucket-ish async limiter: enforces a minimum interval between acquires.

    Shared per-host instance across all calls — e.g. one for sec.gov, one for
    api.tavily.com.

    Celery workers call asyncio.run() per task, which creates a fresh event loop
    each time. asyncio.Lock objects are bound to the loop that created them and
    raise RuntimeError when used from a different loop. We fix this by tracking
    the current running loop and recreating the lock whenever it changes.
    """

    def __init__(self, rps: float) -> None:
        if rps <= 0:
            raise ValueError("rps must be > 0")
        self._interval = 1.0 / rps
        self._lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._next_allowed_at: float = 0.0

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        if loop is not self._loop:
            # New event loop (e.g. fresh Celery task) — create a fresh lock.
            self._lock = asyncio.Lock()
            self._loop = loop
            self._next_allowed_at = 0.0
        async with self._lock:  # type: ignore[arg-type]
            now = loop.time()
            wait = self._next_allowed_at - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = loop.time()
            self._next_allowed_at = now + self._interval


def make_cache_key(namespace: str, **parts: Any) -> str:
    """Deterministic cache key; long arg blobs hashed so we stay under the 512-char column."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    if len(raw) > 200:
        raw = hashlib.sha256(raw.encode()).hexdigest()
    return f"{namespace}:{raw}"


async def cache_get(cache_key: str) -> JsonDict | None:
    async with SessionLocal() as session:
        stmt = select(SignalCache).where(
            SignalCache.cache_key == cache_key,
            SignalCache.expires_at > datetime.now(UTC),
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        return row.payload if row else None


async def cache_set(cache_key: str, payload: JsonDict, ttl_seconds: int) -> None:
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    stmt = (
        pg_insert(SignalCache)
        .values(cache_key=cache_key, payload=payload, expires_at=expires_at)
        .on_conflict_do_update(
            index_elements=["cache_key"],
            set_={"payload": payload, "expires_at": expires_at},
        )
    )
    async with SessionLocal() as session:
        await session.execute(stmt)
        await session.commit()


def cached_fetch(
    *,
    key_fn: Callable[..., str],
    ttl_seconds: int,
    rate_limiter: AsyncRateLimiter | None = None,
) -> Callable[[Callable[..., Awaitable[JsonDict]]], Callable[..., Awaitable[JsonDict]]]:
    """Decorate an async provider call with read-through cache + optional rate limit.

    The decorated fn must return a JSON-serializable dict (the thing we persist).
    Pydantic modelling happens at the agent layer, not here.
    """

    def deco(fn: Callable[..., Awaitable[JsonDict]]) -> Callable[..., Awaitable[JsonDict]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> JsonDict:
            cache_key = key_fn(*args, **kwargs)
            hit = await cache_get(cache_key)
            if hit is not None:
                return hit
            if rate_limiter is not None:
                await rate_limiter.acquire()
            result = await fn(*args, **kwargs)
            await cache_set(cache_key, result, ttl_seconds)
            return result

        return wrapper

    return deco
