"""Tavily news search client.

Real HTTP. Behind cache+rate-limit decorator; 15-min TTL is aggressive
enough that rerunning research on the same ticker during development
doesn't re-bill, but fresh enough that breaking news isn't stale.

Each `fetch_news()` call issues *multiple* angled queries instead of one.
A single equity-style query (e.g. "Discord stock earnings news") returns
junk on private names because Tavily ranks for "stock earnings" relevance,
and a single query also misses orthogonal angles on public names (analyst
moves, regulatory action, business momentum). Issuing 3 angled queries and
deduping by URL gives a much wider, more useful coverage at ~3× search-API
cost (still cents per run).
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
_TTL_SECONDS = 15 * 60
_PER_QUERY_RESULTS = 8  # 3 queries × 8 = up to 24 raw, dedup -> ~12-15 final
_FINAL_RESULT_CAP = 15

# Tavily's published limit is 60 req/min on the free tier; half-rate to be
# polite and leave headroom for parallel tool calls in the agent graph.
_rate_limiter = AsyncRateLimiter(rps=0.5)


def _key(ticker: str, lookback_days: int, mode: str) -> str:
    return make_cache_key(
        "tavily.news", ticker=ticker.upper(), lookback_days=lookback_days, mode=mode
    )


def _queries_for(name: str, mode: str) -> list[str]:
    """Three angled queries per mode. Each angle pulls a distinct slice of
    coverage; merging + deduping by URL gives the widest signal surface.

    Pre-IPO angles are designed to surface what's actually written about
    private companies: IPO process / S-1 chatter, primary funding rounds and
    secondary-market marks (Forge, EquityZen, Nasdaq Private Market), and
    operational news (revenue, MAU, layoffs).

    Public angles cover earnings, analyst posture, and regulatory / legal
    risk — three different reader cohorts that Tavily's relevance ranker
    wouldn't combine on its own.
    """
    if mode == "pre_ipo":
        return [
            f"{name} IPO filing S-1 valuation",
            f"{name} funding round Series secondary market valuation",
            f"{name} revenue users growth layoffs",
        ]
    return [
        f"{name} earnings revenue guidance",
        f"{name} analyst rating upgrade downgrade price target",
        f"{name} regulation lawsuit antitrust risk",
    ]


@cached_fetch(key_fn=_key, ttl_seconds=_TTL_SECONDS, rate_limiter=_rate_limiter)
async def fetch_news(
    ticker: str, lookback_days: int = 90, mode: str = "public"
) -> dict[str, Any]:
    """Return {'news_items': [...]} shaped for MarketIntelOutput.news_items.

    Issues 3 angled queries in parallel, merges results, dedupes by URL, and
    returns the top `_FINAL_RESULT_CAP` by score. A single failed query
    doesn't fail the call — we just lose that angle's contribution.
    """
    settings = get_settings()
    queries = _queries_for(ticker, mode)

    results = await asyncio.gather(
        *[_one_query(settings.tavily_api_key, q, lookback_days) for q in queries],
        return_exceptions=True,
    )

    by_url: dict[str, dict[str, Any]] = {}
    for q, result in zip(queries, results, strict=True):
        if isinstance(result, BaseException):
            # Drop the failure but keep the other angles. Logged via repr so
            # we don't lose the diagnostic in case all three fail.
            continue
        for item in result:
            url = item.get("url", "")
            if not url:
                continue
            existing = by_url.get(url)
            # If the same URL came back from multiple queries, keep the one
            # with the highest score — different angles may rank it differently.
            if existing is None or (item.get("score") or 0) > (existing.get("score") or 0):
                item = dict(item)
                item["query_origin"] = q
                by_url[url] = item

    merged = sorted(by_url.values(), key=lambda r: r.get("score") or 0, reverse=True)[
        :_FINAL_RESULT_CAP
    ]

    news_items = [
        {
            "headline": r.get("title", ""),
            "source": _source_from_url(r.get("url", "")),
            "url": r.get("url", ""),
            "published": r.get("published_date"),
            "score": r.get("score"),
            "snippet": r.get("content", "")[:500],
        }
        for r in merged
    ]
    return {"news_items": news_items}


async def _one_query(api_key: str, query: str, lookback_days: int) -> list[dict[str, Any]]:
    """Single Tavily search. Caller is responsible for catching exceptions."""
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "topic": "news",
        "days": lookback_days,
        "max_results": _PER_QUERY_RESULTS,
        "include_answer": False,
    }
    await _rate_limiter.acquire()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(_TAVILY_ENDPOINT, json=payload)
        resp.raise_for_status()
        body = resp.json()
    return body.get("results", [])


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
