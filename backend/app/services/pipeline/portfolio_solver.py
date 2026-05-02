"""Mean-variance and risk-parity portfolio optimizer.

Uses scipy.optimize.minimize (SLSQP) to produce mathematically optimal weights
from 90-day historical returns. This replaces LLM guesswork for target_allocations
with numbers that are auditable and reproducible.

Method selection by risk profile:
  - conservative  → minimum variance (lowest volatility for given return)
  - moderate       → maximum Sharpe ratio (best risk-adjusted return)
  - aggressive     → maximum Sharpe ratio with looser concentration limits

Max single-position caps by profile:
  - conservative: 20%
  - moderate:     30%
  - aggressive:   45%

Exposed API:
    solve_async(tickers, risk_profile, lookback_days=90) -> SolverResult
    solve_sync(tickers, risk_profile, lookback_days=90)  -> SolverResult  (for thread pool)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from app.models.db.enums import RiskProfile

logger = logging.getLogger(__name__)

_TRADING_DAYS_PER_YEAR = 252
_RISK_FREE_RATE = 0.05  # annualized, used for Sharpe calculation

# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


class SolverResult(BaseModel):
    """Output of the portfolio optimizer; injected into PortfolioConstructionInput."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    method: Literal["min_variance", "max_sharpe", "risk_parity", "equal_weight"]
    weights: dict[str, float]
    """Ticker -> optimal portfolio weight (0..1). Sums to 1.0."""
    expected_annual_return_pct: float | None = None
    expected_annual_volatility_pct: float
    sharpe_ratio: float | None = None
    lookback_days: int
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Constraint helpers
# ---------------------------------------------------------------------------


def _max_weight(risk_profile: RiskProfile) -> float:
    return {
        RiskProfile.CONSERVATIVE: 0.20,
        RiskProfile.MODERATE: 0.30,
        RiskProfile.AGGRESSIVE: 0.45,
    }[risk_profile]


def _choose_method(risk_profile: RiskProfile) -> Literal["min_variance", "max_sharpe"]:
    return "min_variance" if risk_profile == RiskProfile.CONSERVATIVE else "max_sharpe"


# ---------------------------------------------------------------------------
# Solvers (all operate on pre-built returns matrices)
# ---------------------------------------------------------------------------


def _solve_min_variance(
    returns: np.ndarray,  # shape (T, N) — daily log returns
    tickers: list[str],
    risk_profile: RiskProfile,
) -> SolverResult:
    """Minimize portfolio variance subject to weight constraints."""
    from scipy.optimize import minimize as sp_minimize

    n = returns.shape[1]
    cov = np.cov(returns.T) * _TRADING_DAYS_PER_YEAR  # annualised covariance
    mean_ret = returns.mean(axis=0) * _TRADING_DAYS_PER_YEAR

    max_w = _max_weight(risk_profile)
    bounds = [(0.0, max_w)] * n
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
    w0 = np.ones(n) / n

    def portfolio_variance(w: np.ndarray) -> float:
        return float(w @ cov @ w)

    result = sp_minimize(
        portfolio_variance,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    warnings: list[str] = []
    w = result.x if result.success else w0
    if not result.success:
        warnings.append(f"Min-variance optimizer did not converge ({result.message}); weights may be suboptimal.")

    w = np.clip(w, 0.0, 1.0)
    w /= w.sum()

    vol = float(np.sqrt(w @ cov @ w)) * 100
    ret = float(w @ mean_ret) * 100

    return SolverResult(
        method="min_variance",
        weights={t: round(float(w_i), 4) for t, w_i in zip(tickers, w)},
        expected_annual_return_pct=round(ret, 2),
        expected_annual_volatility_pct=round(vol, 2),
        sharpe_ratio=round((ret - _RISK_FREE_RATE * 100) / vol, 3) if vol > 0 else None,
        lookback_days=returns.shape[0],
        warnings=warnings,
    )


def _solve_max_sharpe(
    returns: np.ndarray,  # shape (T, N)
    tickers: list[str],
    risk_profile: RiskProfile,
) -> SolverResult:
    """Maximize Sharpe ratio: (μ - r_f) / σ."""
    from scipy.optimize import minimize as sp_minimize

    n = returns.shape[1]
    cov = np.cov(returns.T) * _TRADING_DAYS_PER_YEAR
    mean_ret = returns.mean(axis=0) * _TRADING_DAYS_PER_YEAR

    max_w = _max_weight(risk_profile)
    # Min 1% per position so assets are never fully zeroed (keeps solver stable)
    bounds = [(0.01, max_w)] * n
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
    w0 = np.ones(n) / n

    def neg_sharpe(w: np.ndarray) -> float:
        ret = float(w @ mean_ret)
        vol = float(np.sqrt(w @ cov @ w))
        if vol < 1e-8:
            return 0.0
        return -(ret - _RISK_FREE_RATE) / vol

    result = sp_minimize(
        neg_sharpe,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    warnings: list[str] = []
    w = result.x if result.success else w0
    if not result.success:
        warnings.append(f"Max-Sharpe optimizer did not converge ({result.message}); weights may be suboptimal.")

    w = np.clip(w, 0.0, 1.0)
    w /= w.sum()

    vol = float(np.sqrt(w @ cov @ w)) * 100
    ret = float(w @ mean_ret) * 100

    return SolverResult(
        method="max_sharpe",
        weights={t: round(float(w_i), 4) for t, w_i in zip(tickers, w)},
        expected_annual_return_pct=round(ret, 2),
        expected_annual_volatility_pct=round(vol, 2),
        sharpe_ratio=round((ret - _RISK_FREE_RATE * 100) / vol, 3) if vol > 0 else None,
        lookback_days=returns.shape[0],
        warnings=warnings,
    )


def _equal_weight(tickers: list[str], reason: str) -> SolverResult:
    n = len(tickers) or 1
    w = round(1.0 / n, 4)
    return SolverResult(
        method="equal_weight",
        weights={t: w for t in tickers},
        expected_annual_volatility_pct=0.0,
        lookback_days=0,
        warnings=[reason],
    )


# ---------------------------------------------------------------------------
# Data fetching (sync, intended to run in thread pool)
# ---------------------------------------------------------------------------


def _fetch_returns_sync(tickers: list[str], lookback_days: int) -> dict[str, list[float]]:
    """Fetch daily log returns for each ticker. Sync — wrap in run_in_executor."""
    import yfinance as yf

    end = date.today()
    # Fetch extra calendar days to cover weekends and holidays
    start = end - timedelta(days=lookback_days + 45)

    data = yf.download(
        tickers,
        start=str(start),
        end=str(end),
        auto_adjust=True,
        progress=False,
        group_by="ticker",
    )

    if data.empty:
        return {}

    result: dict[str, list[float]] = {}
    for ticker in tickers:
        try:
            closes = data["Close"][ticker].dropna() if len(tickers) > 1 else data["Close"].dropna()
            if len(closes) < 20:
                logger.warning("portfolio_solver: only %d closes for %s — skipping", len(closes), ticker)
                continue
            # Take the most recent lookback_days closes
            prices = np.array(closes.values[-lookback_days - 1 :], dtype=float)
            log_returns = np.diff(np.log(prices))
            result[ticker] = log_returns.tolist()
        except Exception as exc:
            logger.warning("portfolio_solver: failed to get returns for %s: %s", ticker, exc)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def solve_sync(
    tickers: list[str],
    risk_profile: RiskProfile,
    lookback_days: int = 90,
) -> SolverResult:
    """CPU-bound entry point. Call via loop.run_in_executor from async code."""
    if len(tickers) < 2:
        return _equal_weight(
            tickers or ["CASH"],
            "Portfolio has fewer than 2 tickers — no diversification to optimize; using equal weight.",
        )

    returns_map = _fetch_returns_sync(tickers, lookback_days)

    # Drop tickers with insufficient history
    valid = {t: r for t, r in returns_map.items() if len(r) >= 20}
    dropped = sorted(set(tickers) - set(valid))

    if len(valid) < 2:
        msg = (
            f"Insufficient price history for optimization "
            f"({len(valid)}/{len(tickers)} tickers have ≥20 days of data); using equal weight."
        )
        if dropped:
            msg += f" Missing: {', '.join(dropped)}."
        return _equal_weight(tickers, msg)

    # Align all return series to the same length
    min_len = min(len(r) for r in valid.values())
    valid_tickers = sorted(valid.keys())
    returns_matrix = np.array(
        [valid[t][-min_len:] for t in valid_tickers],
        dtype=float,
    ).T  # (T, N)

    extra_warnings: list[str] = []
    if dropped:
        extra_warnings.append(
            f"Excluded from optimization (insufficient price history): {', '.join(dropped)}."
        )

    method = _choose_method(risk_profile)
    try:
        solver_fn = _solve_min_variance if method == "min_variance" else _solve_max_sharpe
        solver_result = solver_fn(returns_matrix, valid_tickers, risk_profile)
    except Exception:
        logger.exception("portfolio_solver: unexpected error, falling back to equal weight")
        solver_result = _equal_weight(tickers, "Optimization raised an unexpected error; using equal weight.")

    solver_result.warnings.extend(extra_warnings)
    return solver_result


async def solve_async(
    tickers: list[str],
    risk_profile: RiskProfile,
    lookback_days: int = 90,
) -> SolverResult:
    """Async wrapper — offloads CPU-bound scipy work to the default thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, solve_sync, tickers, risk_profile, lookback_days)
