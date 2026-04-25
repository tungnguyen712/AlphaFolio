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


async def main(ticker: str, mode: str = "public") -> None:

    _banner(f"1. Data Retrieval (Haiku tier — procedural, no LLM) [mode={mode}]")
    retrieved = await data_retrieval.run(
        DataRetrievalInput(ticker=ticker, mode=mode, lookback_days=90)
    )
    print(f"  insider_filings: {len(retrieved.insider_filings)}")
    print(f"  congress_trades: {len(retrieved.congress_trades)}")
    print(f"  price_summary.latest: {retrieved.price_summary.latest if retrieved.price_summary else None}")
    print(f"  volume_anomalies:  {len(retrieved.volume_anomalies)}")
    print(f"  risk_factors (first 200):\n    {retrieved.risk_factors.text[:200]!r}")
    if retrieved.business_overview:
        print(f"  business_overview: {len(retrieved.business_overview.text)} chars")
    print(f"  form_d_filings:    {len(retrieved.form_d_filings)}")
    for fd in retrieved.form_d_filings[:5]:
        amt = (
            f"${fd.total_offering_amount_usd:,.0f}"
            if fd.total_offering_amount_usd is not None
            else "n/a"
        )
        sold = (
            f"${fd.total_amount_sold_usd:,.0f}"
            if fd.total_amount_sold_usd is not None
            else "n/a"
        )
        print(
            f"    {fd.filed_at} {fd.issuer_name}: offered {amt}, sold {sold}, "
            f"first sale {fd.date_of_first_sale}"
        )

    _banner("2. Market Intelligence (Sonnet)")
    intel = await market_intel.run(
        MarketIntelInput(ticker=ticker, mode=mode, lookback_days=14)
    )
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


async def _resolve_identifier(raw: str) -> tuple[str, str]:
    """Resolve any user-typed identifier into (mode, identifier) for the agents.

      - Clean ticker tokens ('NVDA') pass through as public.
      - Company names ('Nvidia') resolve via SEC's master list to a ticker.
      - Names that AREN'T in the public master list (private companies like
        'Stripe', 'OpenAI') fall back to pre_ipo mode, where the data_retrieval
        agent looks for an S-1 and degrades to news-only if none exists.
    """
    cleaned = raw.strip()
    if len(cleaned) <= 5 and cleaned.isalnum() and cleaned.upper() == cleaned:
        return ("public", cleaned.upper())

    from app.services.data_providers.sec_edgar import resolve_ticker_from_name

    try:
        resolved = await resolve_ticker_from_name(cleaned)
        print(f"(resolved {raw!r} -> {resolved['ticker']} / {resolved['title']}, public mode)\n")
        return ("public", resolved["ticker"])
    except LookupError:
        print(
            f"(no public ticker for {raw!r} — falling back to pre_ipo mode; "
            "data_retrieval will look for an S-1 and otherwise run news-only)\n"
        )
        return ("pre_ipo", cleaned)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    raw = args[0] if args else "NVDA"
    force_pre_ipo = "--pre-ipo" in flags

    async def _run() -> None:
        if force_pre_ipo:
            # Skip the public-ticker resolver — useful for testing the S-1
            # path on companies that have a public S-1 on EDGAR but have
            # since IPO'd (Reddit, Rubrik, Klarna, etc.). The resolver would
            # otherwise route those to public mode via their ticker.
            mode, identifier = "pre_ipo", raw.strip()
            print(f"(--pre-ipo flag set; forcing pre_ipo mode for {raw!r})\n")
        else:
            mode, identifier = await _resolve_identifier(raw)
        print(f"Running smoke for {identifier} (mode={mode})\n")
        await main(identifier, mode=mode)

    asyncio.run(_run())
