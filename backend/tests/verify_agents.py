"""End-to-end smoke for stages 3.1-3.3 — real providers + real Anthropic.

Not part of the pytest suite (would cost $ and hit rate limits). Run by hand:

    docker compose exec backend uv run python tests/verify_agents.py

Prints one section per agent so you can eyeball schemas + LLM outputs before
we wire the LangGraph graphs in stage 3.4.
"""
from __future__ import annotations

import asyncio
import json
import sys
from decimal import Decimal

from app.models.agents import (
    DataRetrievalInput,
    DevilsAdvocateInput,
    HoldingSnapshot,
    MarketIntelInput,
    PortfolioConstructionInput,
    SignalAnalysisInput,
    SynthesisInput,
)
from app.models.db.enums import AssetClass, RiskProfile
from app.services.agents import (
    data_retrieval,
    devils_advocate,
    market_intel,
    portfolio_construction,
    signal_analysis,
    synthesis,
)


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _dump(label: str, obj) -> None:  # type: ignore[no-untyped-def]
    print(f"\n[{label}]")
    print(json.dumps(obj.model_dump(mode="json"), indent=2, default=str))


async def main(ticker: str) -> None:

    _banner("1. Data Retrieval (Haiku tier — procedural, no LLM)")
    retrieved = await data_retrieval.run(DataRetrievalInput(ticker=ticker, lookback_days=90))
    print(f"  insider_filings: {len(retrieved.insider_filings)}")
    print(f"  congress_trades: {len(retrieved.congress_trades)}")
    print(f"  price_summary.latest: {retrieved.price_summary.latest if retrieved.price_summary else None}")
    print(f"  volume_anomalies:  {len(retrieved.volume_anomalies)}")
    print(f"  risk_factors (first 200):\n    {retrieved.risk_factors.text[:200]!r}")

    _banner("2. Market Intelligence (Sonnet)")
    intel = await market_intel.run(MarketIntelInput(ticker=ticker, lookback_days=14))
    print(f"  news_items:       {len(intel.news_items)}")
    print(f"  analyst_changes:  {len(intel.analyst_changes)}")
    print(f"  narrative:\n    {intel.narrative_summary}")

    _banner("3. Signal Analysis (Opus)")
    sigs = await signal_analysis.run(
        SignalAnalysisInput(ticker=ticker, retrieved=retrieved, market_intel=intel)
    )
    print(f"  signals: {len(sigs.signals)}")
    for s in sigs.signals:
        print(f"    [{s.direction}/{s.strength:.2f}] {s.name}: {s.rationale[:120]}")
    if sigs.flags:
        print(f"  flags: {sigs.flags}")

    _banner("4. Devil's Advocate (Opus)")
    da = await devils_advocate.run(DevilsAdvocateInput(ticker=ticker, signal_analysis=sigs))
    for c in da.counterarguments:
        print(f"    [{c.severity}] {c.claim}")
    print(f"  worst case: {da.worst_case_scenario}")

    _banner("5. Synthesis (Opus) — VerdictCard surface")
    syn = await synthesis.run(
        SynthesisInput(
            ticker=ticker, signal_analysis=sigs, devils_advocate=da, market_intel=intel
        )
    )
    print(f"  signal:    {syn.signal}")
    print(f"  verdict:   {syn.layers.verdict}")
    print(f"  top 3:     {syn.layers.top_3_signals}")
    print(f"  uncertainty: {syn.layers.key_uncertainty}")
    print(f"  confidence:  {syn.layers.confidence:.2f}")
    print(f"  rec_pos_pct: {syn.recommended_position_pct}")

    _banner("6. Portfolio Construction (Sonnet)")
    pc = await portfolio_construction.run(
        PortfolioConstructionInput(
            portfolio_id="smoke-portfolio",
            holdings=[
                HoldingSnapshot(
                    ticker="MSFT",
                    shares=Decimal("50"),
                    avg_cost=Decimal("310.00"),
                    asset_class=AssetClass.ESTABLISHED,
                )
            ],
            cash_balance=Decimal("20000.00"),
            risk_profile=RiskProfile.MODERATE,
            candidates=[syn],
        )
    )
    print(f"  verdict:   {pc.layers.verdict}")
    print(f"  trades:    {len(pc.proposed_trades)}")
    for t in pc.proposed_trades:
        print(f"    {t.action} {t.ticker} -> {t.target_weight_pct:.2%}: {t.rationale[:120]}")
    print(f"  allocations: {pc.target_allocations}")


if __name__ == "__main__":
    ticker_arg = sys.argv[1].upper() if len(sys.argv) > 1 else "NVDA"
    print(f"Running smoke for ticker: {ticker_arg}\n")
    asyncio.run(main(ticker_arg))
