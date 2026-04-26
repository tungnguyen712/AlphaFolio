"""Lightweight Polygon.io calls for portfolio dashboard prices and sector data.

Uses only free-tier endpoints:
  - /v2/snapshot/locale/us/markets/stocks/tickers  (batch prev-close)
  - /v2/aggs/ticker/{ticker}/prev                  (single fallback)
  - /v3/reference/tickers                          (sector / sic_description)
"""
from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.polygon.io"
_TIMEOUT = 10.0


async def fetch_prev_close_batch(
    tickers: list[str], api_key: str
) -> dict[str, float | None]:
    """Return {ticker: prev_close_price} for all tickers. Unknown = None."""
    if not tickers or not api_key:
        return {}

    result: dict[str, float | None] = {t: None for t in tickers}
    joined = ",".join(tickers)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(
                f"{_BASE}/v2/snapshot/locale/us/markets/stocks/tickers",
                params={"tickers": joined, "apiKey": api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                for snap in data.get("tickers") or []:
                    ticker = snap.get("ticker", "")
                    day = snap.get("day") or snap.get("prevDay") or {}
                    close = day.get("c")
                    if ticker and close is not None:
                        result[ticker] = float(close)
                # Fill gaps with individual prev calls
                missing = [t for t, v in result.items() if v is None]
                if missing:
                    tasks = [_fetch_single_prev(client, t, api_key) for t in missing]
                    singles = await asyncio.gather(*tasks, return_exceptions=True)
                    for t, price in zip(missing, singles):
                        if isinstance(price, float):
                            result[t] = price
            else:
                # Batch failed — fall back to individual calls
                tasks = [_fetch_single_prev(client, t, api_key) for t in tickers]
                singles = await asyncio.gather(*tasks, return_exceptions=True)
                for t, price in zip(tickers, singles):
                    if isinstance(price, float):
                        result[t] = price
        except Exception:
            logger.exception("polygon_prices: batch snapshot failed")

    return result


async def _fetch_single_prev(
    client: httpx.AsyncClient, ticker: str, api_key: str
) -> float | None:
    try:
        resp = await client.get(
            f"{_BASE}/v2/aggs/ticker/{ticker}/prev",
            params={"apiKey": api_key},
        )
        if resp.status_code == 200:
            results = resp.json().get("results") or []
            if results:
                return float(results[0].get("c", 0) or 0) or None
    except Exception:
        logger.warning("polygon_prices: single prev failed for %s", ticker)
    return None


async def fetch_ticker_details_batch(
    tickers: list[str], api_key: str
) -> dict[str, str | None]:
    """Return {ticker: sic_description} for sector labelling. Unknown = None."""
    if not tickers or not api_key:
        return {}

    result: dict[str, str | None] = {t: None for t in tickers}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        tasks = [_fetch_single_details(client, t, api_key) for t in tickers]
        details = await asyncio.gather(*tasks, return_exceptions=True)
        for ticker, detail in zip(tickers, details):
            if isinstance(detail, str):
                result[ticker] = detail

    return result


async def _fetch_single_details(
    client: httpx.AsyncClient, ticker: str, api_key: str
) -> str | None:
    try:
        resp = await client.get(
            f"{_BASE}/v3/reference/tickers/{ticker}",
            params={"apiKey": api_key},
        )
        if resp.status_code == 200:
            res = resp.json().get("results") or {}
            return res.get("sic_description") or None
    except Exception:
        logger.warning("polygon_prices: details failed for %s", ticker)
    return None
