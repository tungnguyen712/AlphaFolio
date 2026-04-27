"""Pre-synthesis validation gate.

Deterministic Python — no LLM, no network. Checks for common data quality
issues before Synthesis runs. Returns a ValidationResult that Synthesis must
factor into its confidence calibration.
"""
from __future__ import annotations

from datetime import date

from app.models.agents.data_retrieval import DataRetrievalOutput
from app.models.agents.market_intel import MarketIntelOutput
from app.models.agents.signal_analysis import SignalAnalysisOutput
from app.models.agents.synthesis import ValidationResult


def validate_research_inputs(
    ticker: str,
    retrieved: DataRetrievalOutput,
    market_intel: MarketIntelOutput | None,
    signals: SignalAnalysisOutput,
) -> ValidationResult:
    """Run all data quality checks and return a ValidationResult.

    confidence_penalty is 5% per warning + 15% per error, capped at 50%.
    passed=False only when errors exist (warnings alone do not fail validation).
    """
    warnings: list[str] = []
    errors: list[str] = []

    # --- Price data ---
    if retrieved.price_summary is None:
        errors.append(
            f"{ticker}: No price data available — cannot compute price-based targets."
        )
    else:
        ps = retrieved.price_summary
        for field in ("market_cap", "forward_pe", "ev_revenue", "high_52w", "low_52w"):
            if getattr(ps, field, None) is None:
                warnings.append(f"PriceSummary.{field} unavailable for {ticker}.")

    # --- Insider data ---
    if not retrieved.insider_filings:
        warnings.append(f"{ticker}: No Form 4 insider transactions retrieved.")
    elif retrieved.insider_summary is not None:
        s = retrieved.insider_summary
        if s.num_distinct_filings > 0 and s.raw_transaction_count > 3 * s.num_distinct_filings:
            warnings.append(
                f"{ticker}: Insider row count ({s.raw_transaction_count}) is >3× distinct filings "
                f"({s.num_distinct_filings}) — possible row overcounting in signal analysis."
            )

    # --- Analyst / market intel ---
    if market_intel is not None:
        if market_intel.analyst_signal_source == "news_reported_analyst_signal":
            warnings.append(
                f"{ticker}: analyst_changes is empty — analyst data sourced from news snippets only. "
                "Do not present as structured consensus."
            )
        if market_intel.analyst_changes:
            stale = [
                a
                for a in market_intel.analyst_changes
                if a.published_at and (date.today() - a.published_at).days > 180
            ]
            if stale:
                warnings.append(
                    f"{ticker}: {len(stale)} analyst change(s) are older than 180 days — treat as stale."
                )
        if not market_intel.news_items:
            warnings.append(f"{ticker}: No news items survived post-retrieval filtering.")

    # --- Signal source integrity ---
    for sig in signals.signals:
        if not sig.sources:
            errors.append(f"Signal '{sig.name}' has no source citations.")

    penalty = round(min(0.05 * len(warnings) + 0.15 * len(errors), 0.50), 2)

    return ValidationResult(
        warnings=warnings,
        errors=errors,
        confidence_penalty=penalty,
        passed=len(errors) == 0,
    )
