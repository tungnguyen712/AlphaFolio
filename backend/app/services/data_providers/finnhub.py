"""Finnhub news provider for historical date-range news retrieval.

Used in the historical research mode (as_of_date set) as a replacement for
Tavily, which can only search the current live web. Finnhub's company-news
endpoint supports explicit from/to date filtering.

Free tier: 60 req/min, no cost. Sign up at finnhub.io for an API key.
Cache TTL: 7 days (historical news doesn't change).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import httpx

from app.models.agents.common import NewsItem
from app.services.data_providers._cache import AsyncRateLimiter, cached_fetch, make_cache_key

logger = logging.getLogger(__name__)

_BASE = "https://finnhub.io/api/v1"
_TIMEOUT = 15.0
_TTL_SECONDS = 7 * 24 * 3600  # 7 days — historical news doesn't change
_MAX_ITEMS = 50

_rate_limiter = AsyncRateLimiter(rps=1.0)  # conservative; free tier allows 60/min


@cached_fetch(
    key_fn=lambda ticker, start_date, end_date, api_key=None: make_cache_key(
        "finnhub.news", ticker=ticker, start=str(start_date), end=str(end_date)
    ),
    ttl_seconds=_TTL_SECONDS,
    rate_limiter=_rate_limiter,
)
async def _fetch_raw(
    ticker: str,
    start_date: date,
    end_date: date,
    api_key: str = "",
) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{_BASE}/company-news",
            params={
                "symbol": ticker,
                "from": str(start_date),
                "to": str(end_date),
                "token": api_key,
            },
        )
        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list):
            return {"items": []}
        return {"items": items[:_MAX_ITEMS]}


async def fetch_historical_news(
    ticker: str,
    start_date: date,
    end_date: date,
    api_key: str = "",
) -> list[NewsItem]:
    """Return news articles for ticker between start_date and end_date.

    Falls back to empty list if the API key is missing or the request fails,
    so callers degrade gracefully when Finnhub isn't configured.
    """
    if not api_key:
        logger.warning("finnhub: no api_key configured — returning empty news for %s", ticker)
        return []

    try:
        raw = await _fetch_raw(ticker, start_date, end_date, api_key)
    except Exception:
        logger.warning("finnhub: fetch failed for %s (%s → %s)", ticker, start_date, end_date)
        return []

    items: list[NewsItem] = []
    for article in raw.get("items", []):
        try:
            pub_date = _parse_ts(article.get("datetime"))
            url = article.get("url", "")
            if not url:
                continue
            items.append(
                NewsItem(
                    headline=article.get("headline", ""),
                    source=article.get("source", "finnhub"),
                    url=url,
                    published=pub_date,
                    score=None,
                    snippet=article.get("summary", "")[:1000],
                )
            )
        except Exception:
            continue
    return items


def _parse_ts(ts: int | str | None) -> date | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts)).date()
    except (TypeError, ValueError, OSError):
        return None
