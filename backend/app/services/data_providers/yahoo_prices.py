"""Yahoo Finance fallback for portfolio prices, sector data, and historical OHLCV.

No API key required. The fetch_prev_close_batch / fetch_ticker_details_batch
functions use the unofficial Yahoo Finance chart/quoteSummary endpoints (stable
for small batches). The historical functions use the yfinance library which
wraps the same API with smarter pagination and retry logic.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

from app.models.agents.common import OHLCVBar, PriceSummary

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


# ---------------------------------------------------------------------------
# Historical OHLCV (yfinance-backed)
# ---------------------------------------------------------------------------


async def fetch_historical_ohlcv(
    ticker: str,
    start_date: date,
    end_date: date,
) -> list[OHLCVBar]:
    """Return daily OHLCV bars for ticker between start_date and end_date (inclusive).

    Runs yfinance in a thread pool since it's a synchronous library. Raises
    ValueError if no data is available for the requested range.
    """
    loop = asyncio.get_event_loop()
    bars = await loop.run_in_executor(
        None, _yf_history, ticker, start_date, end_date
    )
    if not bars:
        raise ValueError(f"No price data for {ticker} from {start_date} to {end_date}")
    return bars


async def fetch_price_as_of(ticker: str, as_of_date: date) -> PriceSummary:
    """Return a PriceSummary computed from historical data as of as_of_date.

    Fetches ~400 days of history to cover 52-week high/low and pct_90d.
    Raises ValueError if no data is available.
    """
    loop = asyncio.get_event_loop()
    summary = await loop.run_in_executor(
        None, _yf_price_summary, ticker, as_of_date
    )
    return summary


def _yf_history(ticker: str, start: date, end: date) -> list[OHLCVBar]:
    import yfinance as yf  # imported here so the module loads without yfinance in test envs

    t = yf.Ticker(ticker)
    # yfinance end date is exclusive — add one day to include end_date
    hist = t.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=True)
    if hist.empty:
        return []
    bars: list[OHLCVBar] = []
    for ts, row in hist.iterrows():
        bars.append(
            OHLCVBar(
                date=ts.date() if hasattr(ts, "date") else ts,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row.get("Volume", 0) or 0),
            )
        )
    return bars


def _yf_price_summary(ticker: str, as_of: date) -> PriceSummary:
    import yfinance as yf

    start = as_of - timedelta(days=400)
    # end is exclusive — use as_of + 1 to include the as_of date itself
    end = as_of + timedelta(days=1)

    t = yf.Ticker(ticker)
    hist = t.history(start=str(start), end=str(end), auto_adjust=True)

    if hist.empty:
        raise ValueError(f"No price data for {ticker} as of {as_of}")

    # Normalize index to plain date objects
    hist.index = [ts.date() if hasattr(ts, "date") else ts for ts in hist.index]
    closes = hist["Close"]

    latest_price = float(closes.iloc[-1])
    latest_date = hist.index[-1]

    def _pct_return(days: int) -> float | None:
        ref = as_of - timedelta(days=days)
        past = [c for d, c in zip(hist.index, closes) if d <= ref]
        if not past:
            return None
        return round((latest_price / float(past[-1]) - 1) * 100, 2)

    high_52w = float(hist["High"].max()) if "High" in hist.columns else None
    low_52w = float(hist["Low"].min()) if "Low" in hist.columns else None
    volume = int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else None

    missing = [f for f in ("market_cap", "forward_pe", "ev_revenue") if True]

    return PriceSummary(
        latest=latest_price,
        pct_30d=_pct_return(30),
        pct_90d=_pct_return(90),
        high_52w=high_52w,
        low_52w=low_52w,
        volume=volume,
        retrieved_at=latest_date,
        missing_fields=missing,
    )


def _fetch_ohlcv_sync_batch(
    tickers: list[str],
    start_date: date,
    end_date: date,
) -> dict[str, list[Any]]:
    """Fetch OHLCV for multiple tickers in one yfinance download call.

    Returns {ticker: [{date, close}]} — minimal shape for simulation engine.
    Internal use only; callers use fetch_historical_ohlcv per ticker.
    """
    import yfinance as yf

    end = end_date + timedelta(days=1)
    data = yf.download(
        tickers,
        start=str(start_date),
        end=str(end),
        auto_adjust=True,
        progress=False,
        group_by="ticker",
    )
    result: dict[str, list[Any]] = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                closes = data["Close"]
            else:
                closes = data[ticker]["Close"]
            series = []
            for ts, price in closes.items():
                if price and not (price != price):  # skip NaN
                    series.append({
                        "date": ts.date() if hasattr(ts, "date") else ts,
                        "close": float(price),
                    })
            result[ticker] = series
        except (KeyError, Exception):
            result[ticker] = []
    return result
