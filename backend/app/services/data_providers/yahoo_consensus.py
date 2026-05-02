"""Analyst consensus data provider — Yahoo Finance via yahooquery.

Uses the yahooquery `Ticker` class (sync) wrapped in `run_in_executor` so
it doesn't block the event loop. No API key required.

Data pulled:
  - financial_data   → price targets + recommendation key/mean
  - recommendation_trend → rating distribution (most recent period)
  - earnings_trend   → forward EPS estimates

TTL: 24 h — consensus changes intraday but rarely in ways that flip a signal.
Historical mode: yahooquery has no point-in-time consensus endpoint. The
data_retrieval agent skips this provider when `as_of_date` is set, so
historical runs are never contaminated with current-day analyst views.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.models.agents.common import ConsensusData
from app.services.data_providers._cache import cached_fetch, make_cache_key

logger = logging.getLogger(__name__)

_TTL_SECONDS = 24 * 3600  # 24 hours


# ---------------------------------------------------------------------------
# Sync fetch (runs in a thread executor to avoid blocking the event loop)
# ---------------------------------------------------------------------------


def _sync_fetch(ticker: str) -> dict[str, Any]:
    """Call yahooquery synchronously and serialize results to a plain dict.

    DataFrames are converted to lists-of-dicts so the result is JSON-safe
    for the signal_cache Postgres JSONB column.
    """
    # Import inside the function so the module can be imported even if
    # yahooquery is not installed in a test environment (callers mock this out).
    from yahooquery import Ticker  # type: ignore[import-untyped]

    t = Ticker(ticker, asynchronous=False)

    # --- financial_data: price targets + recommendation ---
    fin_raw: Any = t.financial_data
    fin: dict[str, Any] = {}
    if isinstance(fin_raw, dict):
        fin = fin_raw.get(ticker, {}) or {}

    # --- recommendation_trend: rating distribution ---
    trend_raw: Any = t.recommendation_trend
    most_recent_period: dict[str, Any] = {}
    if isinstance(trend_raw, dict):
        df_or_err = trend_raw.get(ticker)
        if hasattr(df_or_err, "to_dict"):
            # It's a DataFrame; take the first row (most recent period)
            records = df_or_err.to_dict(orient="records")
            if records:
                most_recent_period = records[0]
    elif hasattr(trend_raw, "to_dict"):
        records = trend_raw.to_dict(orient="records")
        if records:
            most_recent_period = records[0]

    # --- earnings_trend: forward EPS estimates ---
    etf_raw: Any = t.earnings_trend
    eps_estimates: dict[str, float | None] = {
        "current_quarter": None,
        "current_year": None,
        "next_year": None,
    }
    if isinstance(etf_raw, dict):
        df_or_err = etf_raw.get(ticker)
        if hasattr(df_or_err, "to_dict"):
            records = df_or_err.to_dict(orient="records")
            # earnings_trend rows have a 'period' field: '0q'=current qtr,
            # '0y'=current year, '+1y'=next year
            period_map = {"0q": "current_quarter", "0y": "current_year", "+1y": "next_year"}
            for row in records:
                period = str(row.get("period", ""))
                key = period_map.get(period)
                if key:
                    val = row.get("earningsEstimate.avg")
                    if val is not None and not _is_nan(val):
                        eps_estimates[key] = float(val)
    elif hasattr(etf_raw, "to_dict"):
        records = etf_raw.to_dict(orient="records")
        period_map = {"0q": "current_quarter", "0y": "current_year", "+1y": "next_year"}
        for row in records:
            period = str(row.get("period", ""))
            key = period_map.get(period)
            if key:
                val = row.get("earningsEstimate.avg")
                if val is not None and not _is_nan(val):
                    eps_estimates[key] = float(val)

    return {
        "financial_data": fin,
        "recommendation_trend": most_recent_period,
        "eps_estimates": eps_estimates,
    }


def _is_nan(v: Any) -> bool:
    """Safe NaN check that works for int/str/None without importing math."""
    try:
        return v != v  # NaN is the only float where x != x
    except Exception:
        return False


def _safe_float(v: Any) -> float | None:
    if v is None or _is_nan(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None or _is_nan(v):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Cached async wrapper
# ---------------------------------------------------------------------------


@cached_fetch(
    key_fn=lambda ticker: make_cache_key("yahoo.consensus", ticker=ticker),
    ttl_seconds=_TTL_SECONDS,
)
async def _fetch_raw(ticker: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch, ticker)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def fetch_consensus(ticker: str) -> ConsensusData | None:
    """Fetch analyst consensus for a public ticker. Returns None on any failure.

    Never raises — callers (data_retrieval agent) treat None as 'unavailable'
    and signal_analysis flags it.
    """
    try:
        raw = await _fetch_raw(ticker)
    except Exception:
        logger.warning("yahoo_consensus: fetch failed for %s", ticker, exc_info=True)
        return None

    fin: dict[str, Any] = raw.get("financial_data", {})
    trend: dict[str, Any] = raw.get("recommendation_trend", {})
    eps: dict[str, Any] = raw.get("eps_estimates", {})

    current_price = _safe_float(fin.get("currentPrice"))
    target_mean = _safe_float(fin.get("targetMeanPrice"))

    # Compute implied upside deterministically so the LLM doesn't do arithmetic
    implied_upside_pct: float | None = None
    if current_price and target_mean and current_price > 0:
        implied_upside_pct = round((target_mean - current_price) / current_price * 100, 2)

    # recommendation_key is e.g. "buy", "hold", "sell"; normalise to lowercase
    rec_key_raw = fin.get("recommendationKey")
    recommendation_key = str(rec_key_raw).lower() if rec_key_raw else None

    return ConsensusData(
        current_price=current_price,
        target_low=_safe_float(fin.get("targetLowPrice")),
        target_high=_safe_float(fin.get("targetHighPrice")),
        target_mean=target_mean,
        target_median=_safe_float(fin.get("targetMedianPrice")),
        number_of_analyst_opinions=_safe_int(fin.get("numberOfAnalystOpinions")),
        recommendation_key=recommendation_key,
        recommendation_mean=_safe_float(fin.get("recommendationMean")),
        strong_buy=_safe_int(trend.get("strongBuy")),
        buy=_safe_int(trend.get("buy")),
        hold=_safe_int(trend.get("hold")),
        sell=_safe_int(trend.get("sell")),
        strong_sell=_safe_int(trend.get("strongSell")),
        eps_current_quarter=eps.get("current_quarter"),
        eps_current_year=eps.get("current_year"),
        eps_next_year=eps.get("next_year"),
        implied_upside_pct=implied_upside_pct,
    )
