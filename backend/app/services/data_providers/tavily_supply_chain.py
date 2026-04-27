"""Tavily supply chain search — targeted queries for supplier/customer context.

Separate from the earnings/analyst/regulatory queries in tavily.py.
Uses the same Tavily API key but a dedicated rate limiter instance so
concurrent market_intel + supply_chain calls don't share the same
token bucket and starve each other.

TTL is 24h vs 15min for earnings news — supply chain relationships
are reported infrequently; stale data here is low-risk.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import get_settings
from app.services.data_providers._cache import (
    AsyncRateLimiter,
    cached_fetch,
    make_cache_key,
)

_TAVILY_ENDPOINT = "https://api.tavily.com/search"
_TTL_SECONDS = 24 * 60 * 60  # 24 hours
_PER_QUERY_RESULTS = 8
_FINAL_RESULT_CAP = 15

# Independent limiter — doesn't share budget with market_intel's Tavily calls.
# Tavily free tier: 60 req/min; 0.5 rps gives comfortable headroom.
_rate_limiter = AsyncRateLimiter(rps=0.5)


def _key(ticker: str) -> str:
    return make_cache_key("tavily.supply_chain.v2", ticker=ticker.upper())


def _queries_for(ticker: str) -> list[str]:
    return [
        f"{ticker} key business partners suppliers infrastructure",
        f"{ticker} largest customers enterprise clients revenue deals",
        f"{ticker} acquisitions subsidiaries owned companies",
    ]


@cached_fetch(key_fn=_key, ttl_seconds=_TTL_SECONDS, rate_limiter=_rate_limiter)
async def fetch_supply_chain_data(ticker: str) -> dict[str, Any]:
    """Return {'snippets': [...]} — supply-chain-focused Tavily results.

    Issues 3 angled queries targeting suppliers, customers, and manufacturers.
    Returns raw snippets for entity extraction in the pipeline layer (currently
    fetched and cached but entity parsing deferred to v1.1).
    """
    settings = get_settings()
    queries = _queries_for(ticker)

    results = await asyncio.gather(
        *[_one_query(settings.tavily_api_key, q) for q in queries],
        return_exceptions=True,
    )

    by_url: dict[str, dict[str, Any]] = {}
    for result in results:
        if isinstance(result, BaseException):
            continue
        for item in result:
            url = item.get("url", "")
            if not url:
                continue
            existing = by_url.get(url)
            if existing is None or (item.get("score") or 0) > (existing.get("score") or 0):
                by_url[url] = item

    merged = sorted(
        by_url.values(), key=lambda r: r.get("score") or 0, reverse=True
    )[:_FINAL_RESULT_CAP]

    snippets = [
        {
            "headline": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:800],
            "score": r.get("score"),
        }
        for r in merged
    ]
    return {"snippets": snippets}


async def _one_query(api_key: str, query: str) -> list[dict[str, Any]]:
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "topic": "general",
        "max_results": _PER_QUERY_RESULTS,
        "include_answer": False,
    }
    await _rate_limiter.acquire()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(_TAVILY_ENDPOINT, json=payload)
        resp.raise_for_status()
        body = resp.json()
    return body.get("results", [])
