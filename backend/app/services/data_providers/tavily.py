"""Tavily news search client.

Real HTTP. Behind cache+rate-limit decorator; 15-min TTL is aggressive
enough that rerunning research on the same ticker during development
doesn't re-bill, but fresh enough that breaking news isn't stale.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.services.data_providers._cache import (
    AsyncRateLimiter,
    cached_fetch,
    make_cache_key,
)

_TAVILY_ENDPOINT = "https://api.tavily.com/search"
_TTL_SECONDS = 15 * 60

# Tavily's published limit is 60 req/min on the free tier; half-rate to be
# polite and leave headroom for parallel tool calls in the agent graph.
_rate_limiter = AsyncRateLimiter(rps=0.5)


def _key(ticker: str, lookback_days: int) -> str:
    return make_cache_key("tavily.news", ticker=ticker.upper(), lookback_days=lookback_days)


@cached_fetch(key_fn=_key, ttl_seconds=_TTL_SECONDS, rate_limiter=_rate_limiter)
async def fetch_news(ticker: str, lookback_days: int = 90) -> dict[str, Any]:
    """Return {'news_items': [...]} shaped for MarketIntelOutput.news_items."""
    settings = get_settings()
    payload = {
        "api_key": settings.tavily_api_key,
        "query": f"{ticker} stock earnings news",
        "search_depth": "basic",
        "topic": "news",
        "days": lookback_days,
        "max_results": 10,
        "include_answer": False,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(_TAVILY_ENDPOINT, json=payload)
        resp.raise_for_status()
        body = resp.json()

    news_items = [
        {
            "headline": r.get("title", ""),
            "source": _source_from_url(r.get("url", "")),
            "url": r.get("url", ""),
            "published": r.get("published_date"),
            "score": r.get("score"),
            "snippet": r.get("content", "")[:500],
        }
        for r in body.get("results", [])
    ]
    return {"news_items": news_items}


def _source_from_url(url: str) -> str:
    if not url:
        return "unknown"
    # naive: take the second-level domain as the source name
    try:
        host = url.split("//", 1)[1].split("/", 1)[0]
        parts = host.split(".")
        return parts[-2] if len(parts) >= 2 else host
    except IndexError:
        return "unknown"
