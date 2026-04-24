"""End-to-end smoke for stage 3.4 — real agents + real Anthropic, routed
through the compiled LangGraph graphs (not the stage-3.3 direct-call harness).

Not part of pytest. Run by hand:

    docker compose exec backend uv run python tests/verify_graphs.py NVDA

Confirms:
  - research_graph composes the 5 agents, parallelizes the data-gathering
    pair, and lands in a terminal state with a populated Synthesis output.
  - portfolio_graph consumes the Synthesis as a candidate and lands in a
    terminal state with a populated PortfolioConstruction output.
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal

from app.graphs.portfolio import build_portfolio_graph, new_portfolio_state
from app.graphs.research import build_research_graph, new_research_state
from app.models.agents import HoldingSnapshot
from app.models.db.enums import AssetClass, RiskProfile


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


async def main(ticker: str) -> None:
    _banner(f"research_graph for {ticker}")
    research = build_research_graph()
    r_state = await research.ainvoke(new_research_state(ticker=ticker, lookback_days=90))

    syn = r_state["synthesis"]
    print(f"  retrieved:        insider_filings={len(r_state['retrieved'].insider_filings)}")
    print(f"  market_intel:     news_items={len(r_state['market_intel'].news_items)}")
    print(f"  signals:          {len(r_state['signals'].signals)} signals, "
          f"{len(r_state['signals'].flags)} flags")
    print(f"  devils_advocate:  {len(r_state['devils_advocate'].counterarguments)} counterarguments")
    print(f"  synthesis.signal: {syn.signal}")
    print(f"  synthesis.verdict: {syn.layers.verdict}")
    print(f"  synthesis.top_3:   {syn.layers.top_3_signals}")
    print(f"  synthesis.confidence: {syn.layers.confidence:.2f}")

    _banner(f"portfolio_graph with {ticker} synthesis as candidate")
    portfolio = build_portfolio_graph()
    p_state = await portfolio.ainvoke(
        new_portfolio_state(
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

    rec = p_state["recommendation"]
    print(f"  verdict: {rec.layers.verdict}")
    print(f"  trades:  {len(rec.proposed_trades)}")
    for t in rec.proposed_trades:
        print(f"    {t.action} {t.ticker} -> {t.target_weight_pct:.2%}: {t.rationale}")
    print(f"  allocations: {rec.target_allocations}")


if __name__ == "__main__":
    ticker_arg = sys.argv[1].upper() if len(sys.argv) > 1 else "NVDA"
    print(f"Running graph smoke for ticker: {ticker_arg}\n")
    asyncio.run(main(ticker_arg))
