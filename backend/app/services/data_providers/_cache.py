"""Cache + rate-limit decorator for data-provider calls.

Two concerns in one module because they always compose: every provider call
goes cache-first, then rate-limit-gated if we miss, then writes back.

Cache is read-through against the `signal_cache` Postgres table (already in
the initial migration). Rate limiting is per-host, single-process asyncio.

Singleflight: when multiple Celery workers miss the cache for the same key at
the same time (e.g. two concurrent research runs on AAPL), only the first
worker calls the external provider; the others wait and read from cache once
the winner writes it. Implemented via Redis SET NX so the lock works across
processes/replicas. Falls back gracefully when Redis is unavailable.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, TypeVar

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.models.db import SignalCache
from app.services.redis_client import get_redis

T = TypeVar("T")
JsonDict = dict[str, Any]
logger = logging.getLogger(__name__)
structured_logger = structlog.get_logger(__name__)


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


# ---------------------------------------------------------------------------
# Singleflight — distributed deduplication of concurrent cache misses
# ---------------------------------------------------------------------------

# How long to hold the Redis lock before it auto-expires (protects against
# worker crash while holding the lock). Should be >= the slowest provider call.
_SF_LOCK_TTL_MS: int = 30_000  # 30 seconds

# Backoff schedule for loser workers waiting for the winner to populate cache.
# Sum is ~15.5 s — well within _SF_LOCK_TTL_MS.
_SF_POLL_DELAYS: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0, 8.0)


async def _singleflight_fetch(
    cache_key: str,
    fetch_fn: Callable[[], Awaitable[JsonDict]],
    ttl_seconds: int,
) -> JsonDict:
    """Execute fetch_fn exactly once across concurrent workers for cache_key.

    Only the worker that wins the Redis NX lock calls the external provider.
    All other workers poll the cache with exponential backoff until the winner
    writes the result. If the winner fails or Redis is unavailable, each worker
    falls back to calling the provider itself (pre-existing behaviour).
    """
    lock_key = f"sf:{cache_key}"
    redis_ok = True
    acquired = False
    try:
        r = get_redis()
        acquired = bool(await r.set(lock_key, "1", px=_SF_LOCK_TTL_MS, nx=True))
    except Exception:
        logger.debug("singleflight: Redis unavailable, skipping lock for %s", cache_key)
        redis_ok = False
        acquired = True  # degrade: let this worker proceed without the lock

    if acquired:
        # Double-check cache: another worker may have written it in the gap
        # between our outer cache miss and winning the lock.
        double_check = await cache_get(cache_key)
        if double_check is not None:
            if redis_ok:
                try:
                    await get_redis().delete(lock_key)
                except Exception:
                    pass
            return double_check
        try:
            result = await fetch_fn()
            await cache_set(cache_key, result, ttl_seconds)
            return result
        finally:
            if redis_ok:
                try:
                    await get_redis().delete(lock_key)
                except Exception:
                    pass  # TTL will clean it up
    else:
        # Another worker holds the lock — wait for it to populate the cache.
        for delay in _SF_POLL_DELAYS:
            await asyncio.sleep(delay)
            hit = await cache_get(cache_key)
            if hit is not None:
                return hit
        # Winner timed out or failed — do the fetch ourselves without a lock.
        logger.debug(
            "singleflight: timed out waiting for cache on %s, fetching directly",
            cache_key,
        )
        result = await fetch_fn()
        await cache_set(cache_key, result, ttl_seconds)
        return result


# ---------------------------------------------------------------------------
# cached_fetch decorator
# ---------------------------------------------------------------------------


def cached_fetch(
    *,
    key_fn: Callable[..., str],
    ttl_seconds: int,
    rate_limiter: AsyncRateLimiter | None = None,
) -> Callable[[Callable[..., Awaitable[JsonDict]]], Callable[..., Awaitable[JsonDict]]]:
    """Decorate an async provider call with read-through cache + optional rate limit.

    The decorated fn must return a JSON-serializable dict (the thing we persist).
    Pydantic modelling happens at the agent layer, not here.

    Concurrent cache misses for the same key are deduplicated via
    `_singleflight_fetch` so only one worker hits the external provider.
    """

    def deco(fn: Callable[..., Awaitable[JsonDict]]) -> Callable[..., Awaitable[JsonDict]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> JsonDict:
            cache_key = key_fn(*args, **kwargs)
            provider_name = f"{fn.__module__}.{fn.__name__}"
            started = time.perf_counter()
            hit = await cache_get(cache_key)
            if hit is not None:
                structured_logger.info(
                    "provider_cache_hit",
                    provider=provider_name,
                    cache_key=cache_key,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                return hit

            # Bundle the rate-limiter acquire with the actual call so that only
            # the singleflight winner (not the polling losers) consumes a slot.
            async def _fetch() -> JsonDict:
                fetch_started = time.perf_counter()
                if rate_limiter is not None:
                    await rate_limiter.acquire()
                try:
                    result = await fn(*args, **kwargs)
                except Exception as exc:
                    structured_logger.warning(
                        "provider_fetch_failed",
                        provider=provider_name,
                        cache_key=cache_key,
                        latency_ms=round((time.perf_counter() - fetch_started) * 1000, 2),
                        error=str(exc),
                        exc_info=True,
                    )
                    raise
                structured_logger.info(
                    "provider_fetch_completed",
                    provider=provider_name,
                    cache_key=cache_key,
                    cache_hit=False,
                    latency_ms=round((time.perf_counter() - fetch_started) * 1000, 2),
                )
                return result

            result = await _singleflight_fetch(cache_key, _fetch, ttl_seconds)
            structured_logger.info(
                "provider_cache_miss_completed",
                provider=provider_name,
                cache_key=cache_key,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return result

        return wrapper

    return deco
