"""Portfolio simulation engine.

Pure Python + yfinance — no LLM calls. Given a list of weighted tickers and a
date range, fetches historical daily closes and computes:

  - Per-ticker normalized cumulative % return from start (for the chart)
  - Per-ticker metrics: total_return, CAGR, Sharpe ratio, max_drawdown
  - Blended portfolio series (weighted sum) and its metrics

All returns are in percent (e.g. 12.5 means +12.5%). The chart series always
starts at 0.0 on the start_date.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class SimPosition:
    ticker: str
    weight: float


@dataclass
class DailyPoint:
    date: str          # ISO-format string for JSON serialization
    cumulative_pct: float


@dataclass
class TickerMetrics:
    ticker: str
    total_return: float
    cagr: float
    sharpe: float
    max_drawdown: float
    start_price: float
    end_price: float


@dataclass
class SimResult:
    positions: list[SimPosition]
    benchmark: str
    start_date: date
    end_date: date
    series: dict[str, list[DailyPoint]]
    metrics: dict[str, TickerMetrics]
    portfolio_series: list[DailyPoint]
    portfolio_metrics: TickerMetrics


async def run_simulation(
    positions: list[SimPosition],
    start_date: date,
    end_date: date,
    benchmark: str = "VOO",
) -> SimResult:
    """Fetch historical closes and compute simulation metrics.

    The benchmark ticker is treated as an additional series; callers render it
    distinctly in the chart. Weights apply only to the portfolio blended line,
    not to the per-ticker individual lines.
    """
    all_tickers = list({p.ticker for p in positions} | {benchmark})

    loop = asyncio.get_event_loop()
    raw_data: dict[str, list[dict[str, Any]]] = await loop.run_in_executor(
        None, _download_batch, all_tickers, start_date, end_date
    )

    # Build a common date index (intersection of all trading days present)
    date_sets = [
        {row["date"] for row in rows}
        for rows in raw_data.values()
        if rows
    ]
    if not date_sets:
        raise ValueError("No price data available for any of the requested tickers.")

    common_dates = sorted(date_sets[0].intersection(*date_sets[1:]))
    if len(common_dates) < 2:
        raise ValueError(
            f"Insufficient overlapping trading days between {start_date} and {end_date}."
        )

    # Per-ticker close series aligned to common_dates
    aligned: dict[str, list[float]] = {}
    for ticker, rows in raw_data.items():
        by_date = {row["date"]: row["close"] for row in rows}
        aligned[ticker] = [by_date[d] for d in common_dates if d in by_date]

    # Cumulative normalized % return from start (index 0 = 0.0%)
    series: dict[str, list[DailyPoint]] = {}
    metrics: dict[str, TickerMetrics] = {}
    for ticker, closes in aligned.items():
        if not closes:
            continue
        start_price = closes[0]
        cum_pct = [(c / start_price - 1.0) * 100.0 for c in closes]
        series[ticker] = [
            DailyPoint(date=d.isoformat() if hasattr(d, "isoformat") else str(d), cumulative_pct=round(pct, 4))
            for d, pct in zip(common_dates, cum_pct)
        ]
        metrics[ticker] = _compute_metrics(ticker, closes, common_dates)

    # Blended portfolio series (weighted by position weights)
    weight_map = {p.ticker: p.weight for p in positions}
    portfolio_closes = _blend_portfolio(aligned, common_dates, positions, weight_map)
    portfolio_series = [
        DailyPoint(
            date=d.isoformat() if hasattr(d, "isoformat") else str(d),
            cumulative_pct=round((c / portfolio_closes[0] - 1.0) * 100.0, 4),
        )
        for d, c in zip(common_dates, portfolio_closes)
    ]
    portfolio_metrics = _compute_metrics("portfolio", portfolio_closes, common_dates)

    return SimResult(
        positions=positions,
        benchmark=benchmark,
        start_date=start_date,
        end_date=end_date,
        series=series,
        metrics=metrics,
        portfolio_series=portfolio_series,
        portfolio_metrics=portfolio_metrics,
    )


def _blend_portfolio(
    aligned: dict[str, list[float]],
    common_dates: list[date],
    positions: list[SimPosition],
    weight_map: dict[str, float],
) -> list[float]:
    """Return a synthetic price series representing the weighted portfolio.

    Each day: portfolio_value = sum(weight_i * (close_i / start_i))
    Normalized to start at 1.0 so metrics compute correctly.
    """
    n = len(common_dates)
    blended = [0.0] * n
    for pos in positions:
        closes = aligned.get(pos.ticker)
        if not closes or len(closes) != n:
            continue
        start = closes[0]
        if start == 0:
            continue
        for i, c in enumerate(closes):
            blended[i] += pos.weight * (c / start)
    # Normalize so it starts at 1.0 for metric computation
    if blended[0] != 0:
        factor = 1.0 / blended[0]
        blended = [v * factor for v in blended]
    return blended


def _compute_metrics(
    ticker: str,
    closes: list[float],
    dates: list[date],
) -> TickerMetrics:
    n = len(closes)
    start_price = closes[0]
    end_price = closes[-1]
    total_return = (end_price / start_price - 1.0) * 100.0

    # CAGR
    years = (dates[-1] - dates[0]).days / 365.25
    cagr = ((end_price / start_price) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0

    # Sharpe (annualized, risk-free rate assumed 0 for simplicity)
    daily_returns = [(closes[i] / closes[i - 1] - 1.0) for i in range(1, n)]
    if len(daily_returns) >= 2:
        mean_r = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        std_r = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    # Max drawdown
    peak = closes[0]
    max_dd = 0.0
    for c in closes:
        if c > peak:
            peak = c
        dd = (c - peak) / peak * 100.0
        if dd < max_dd:
            max_dd = dd

    return TickerMetrics(
        ticker=ticker,
        total_return=round(total_return, 2),
        cagr=round(cagr, 2),
        sharpe=round(sharpe, 3),
        max_drawdown=round(max_dd, 2),
        start_price=round(start_price, 4),
        end_price=round(end_price, 4),
    )


def _download_batch(
    tickers: list[str],
    start_date: date,
    end_date: date,
) -> dict[str, list[dict[str, Any]]]:
    """Download historical closes for multiple tickers in one yfinance call.

    Returns {ticker: [{date: date, close: float}]}.
    """
    import yfinance as yf

    end = end_date + timedelta(days=1)  # yfinance end is exclusive
    data = yf.download(
        tickers,
        start=str(start_date),
        end=str(end),
        auto_adjust=True,
        progress=False,
        group_by="ticker" if len(tickers) > 1 else None,
    )

    result: dict[str, list[dict[str, Any]]] = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                closes = data["Close"]
            else:
                closes = data[ticker]["Close"]
            rows = []
            for ts, price in closes.items():
                if price and not (price != price):  # skip NaN
                    rows.append({
                        "date": ts.date() if hasattr(ts, "date") else ts,
                        "close": float(price),
                    })
            result[ticker] = rows
        except (KeyError, Exception):
            result[ticker] = []
    return result
