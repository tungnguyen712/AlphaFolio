"""Pre-synthesis validation gate.

Deterministic Python — no LLM, no network. Checks for common data quality
issues before Synthesis runs. Returns a ValidationResult that Synthesis must
factor into its confidence calibration.

Penalty tiers:
  - INFRA_PENALTY (0.02): Missing valuation fields that are structural data-stack
    limitations (Polygon doesn't archive historical market_cap/PE/EV). These are
    not business signals — penalizing them at 0.05 makes every historical run
    artificially uncertain.
  - SIGNAL_PENALTY (0.05): Genuine intelligence gaps — no insider data, no news,
    no analyst coverage. These reflect real uncertainty about the business.
  - HISTORICAL_GAP_PENALTY (0.01): In historical mode, missing news and analyst
    data is expected (Finnhub free tier, Polygon stub skipped). Treat as minimal.
  - ERROR_PENALTY (0.15): Hard errors (no price data at all).
  - Cap: 0.40 (reduced from 0.50 — historical runs should not be penalized into
    paralysis when structural data is unavailable by design).
"""
from __future__ import annotations

from datetime import date

from app.models.agents.data_retrieval import DataRetrievalOutput
from app.models.agents.market_intel import MarketIntelOutput
from app.models.agents.signal_analysis import SignalAnalysisOutput
from app.models.agents.synthesis import ValidationResult

_INFRA_PENALTY = 0.02   # data-stack limitation, not a business signal
_SIGNAL_PENALTY = 0.05  # genuine intelligence gap
_HIST_GAP_PENALTY = 0.01  # expected gap in historical mode
_ERROR_PENALTY = 0.15
_CAP = 0.40


def validate_research_inputs(
    ticker: str,
    retrieved: DataRetrievalOutput,
    market_intel: MarketIntelOutput | None,
    signals: SignalAnalysisOutput,
    as_of_date: date | None = None,
) -> ValidationResult:
    warnings: list[str] = []
    errors: list[str] = []
    penalty: float = 0.0
    is_historical = as_of_date is not None

    # --- Price data ---
    if retrieved.price_summary is None:
        errors.append(
            f"{ticker}: No price data available — cannot compute price-based targets."
        )
        penalty += _ERROR_PENALTY
    else:
        ps = retrieved.price_summary
        # Valuation multiples: infrastructure gap (Polygon doesn't archive these)
        for field in ("market_cap", "forward_pe", "ev_revenue"):
            if getattr(ps, field, None) is None:
                warnings.append(f"PriceSummary.{field} unavailable for {ticker}.")
                penalty += _INFRA_PENALTY
        # 52-week range: signal gap (matters for momentum / mean-reversion)
        for field in ("high_52w", "low_52w"):
            if getattr(ps, field, None) is None:
                warnings.append(f"PriceSummary.{field} unavailable for {ticker}.")
                penalty += _SIGNAL_PENALTY

    # --- Insider data ---
    if not retrieved.insider_filings:
        warnings.append(f"{ticker}: No Form 4 insider transactions retrieved.")
        penalty += _SIGNAL_PENALTY
    elif retrieved.insider_summary is not None:
        s = retrieved.insider_summary
        if s.num_distinct_filings > 0 and s.raw_transaction_count > 3 * s.num_distinct_filings:
            warnings.append(
                f"{ticker}: Insider row count ({s.raw_transaction_count}) is >3× distinct filings "
                f"({s.num_distinct_filings}) — possible row overcounting in signal analysis."
            )
            penalty += _SIGNAL_PENALTY

    # --- Analyst / market intel ---
    if market_intel is not None:
        # In historical mode, empty analyst and news are expected gaps (Polygon skipped,
        # Finnhub free tier limited) — apply minimal penalty rather than full signal gap.
        empty_news_penalty = _HIST_GAP_PENALTY if is_historical else _SIGNAL_PENALTY
        empty_analyst_penalty = _HIST_GAP_PENALTY if is_historical else _SIGNAL_PENALTY

        if market_intel.analyst_signal_source == "news_reported_analyst_signal":
            warnings.append(
                f"{ticker}: analyst_changes is empty — analyst data sourced from news snippets only. "
                "Do not present as structured consensus."
            )
            penalty += empty_analyst_penalty

        if market_intel.analyst_changes:
            stale = [
                a for a in market_intel.analyst_changes
                if a.published_at and (date.today() - a.published_at).days > 180
            ]
            if stale:
                warnings.append(
                    f"{ticker}: {len(stale)} analyst change(s) are older than 180 days — treat as stale."
                )
                penalty += _SIGNAL_PENALTY

        if not market_intel.news_items:
            warnings.append(f"{ticker}: No news items survived post-retrieval filtering.")
            penalty += empty_news_penalty

    # --- Signal source integrity ---
    for sig in signals.signals:
        if not sig.sources:
            errors.append(f"Signal '{sig.name}' has no source citations.")
            penalty += _ERROR_PENALTY

    penalty = round(min(penalty, _CAP), 2)

    return ValidationResult(
        warnings=warnings,
        errors=errors,
        confidence_penalty=penalty,
        passed=len(errors) == 0,
    )
