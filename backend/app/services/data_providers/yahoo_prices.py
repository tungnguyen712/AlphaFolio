"""Yahoo Finance fallback for portfolio prices and sector data.

No API key required. Used when POLYGON_API_KEY is not configured.
Endpoints are unofficial but stable and rate-limit-friendly for small batches.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://query2.finance.yahoo.com"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_TIMEOUT = 10.0


async def fetch_prev_close_batch(tickers: list[str]) -> dict[str, float | None]:
    """Return {ticker: prev_close} using Yahoo Finance chart endpoint."""
    if not tickers:
        return {}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        tasks = [_fetch_price(client, t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        t: (r if isinstance(r, float) else None)
        for t, r in zip(tickers, results)
    }


async def _fetch_price(client: httpx.AsyncClient, ticker: str) -> float | None:
    try:
        resp = await client.get(
            f"{_BASE}/v8/finance/chart/{ticker}",
            params={"interval": "1d", "range": "1d"},
        )
        if resp.status_code == 200:
            meta = resp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
            price = meta.get("regularMarketPrice") or meta.get("previousClose")
            return float(price) if price else None
    except Exception:
        logger.warning("yahoo_prices: price fetch failed for %s", ticker)
    return None


async def fetch_ticker_details_batch(tickers: list[str]) -> dict[str, str | None]:
    """Return {ticker: sector} using Yahoo Finance quoteSummary endpoint."""
    if not tickers:
        return {}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        tasks = [_fetch_sector(client, t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        t: (r if isinstance(r, str) else None)
        for t, r in zip(tickers, results)
    }


async def _fetch_sector(client: httpx.AsyncClient, ticker: str) -> str | None:
    try:
        resp = await client.get(
            f"{_BASE}/v10/finance/quoteSummary/{ticker}",
            params={"modules": "assetProfile"},
        )
        if resp.status_code == 200:
            profile = (
                resp.json()
                .get("quoteSummary", {})
                .get("result", [{}])[0]
                .get("assetProfile", {})
            )
            return profile.get("sector") or None
    except Exception:
        logger.warning("yahoo_prices: sector fetch failed for %s", ticker)
    return None
