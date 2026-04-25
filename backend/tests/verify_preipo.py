"""End-to-end smoke for the pre-IPO branch — real SEC + Tavily + Anthropic.

Default company is "Reddit" because they filed S-1 in early 2024, so the
filing is indexed in EDGAR's full-text search and we fetch real excerpts.

Companies WITHOUT an S-1 on file (e.g. OpenAI, Stripe, Databricks as of
2026-04) still work — the branch degrades to *news-only* via Tavily. The
agent flags the missing filing and Synthesis confidence drops accordingly.

Not part of the pytest suite — costs real API money.

    docker compose exec backend uv run python tests/verify_preipo.py           # Reddit (has S-1)
    docker compose exec backend uv run python tests/verify_preipo.py Klarna    # has S-1
    docker compose exec backend uv run python tests/verify_preipo.py OpenAI    # no S-1 — news only
"""
from __future__ import annotations

import asyncio
import sys

from app.graphs.research import build_research_graph, new_research_state


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


async def main(company_name: str) -> None:
    _banner(f"pre-IPO research graph for {company_name}")
    graph = build_research_graph()
    state = await graph.ainvoke(
        new_research_state(ticker=company_name, mode="pre_ipo", lookback_days=90)
    )

    retrieved = state["retrieved"]
    _banner("1. Data Retrieval (pre-IPO branch)")
    print(f"  mode:              {retrieved.mode}")
    print(f"  display name:      {retrieved.ticker}")
    print(f"  insider_filings:   {len(retrieved.insider_filings)}  (expected 0 — not public)")
    print(f"  congress_trades:   {len(retrieved.congress_trades)}  (expected 0)")
    print(f"  price_summary:     {retrieved.price_summary}  (expected None)")
    print(
        f"  risk_factors:      {len(retrieved.risk_factors.text)} chars from {retrieved.risk_factors.filing_url}"
    )
    print(f"  risk_factors filed_at: {retrieved.risk_factors.filed_at}")
    if retrieved.business_overview:
        print(f"  business_overview: {len(retrieved.business_overview.text)} chars")
        print(f"    first 200: {retrieved.business_overview.text[:200]!r}")
    else:
        print("  business_overview: (none extracted)")

    _banner("2. Market Intelligence")
    intel = state["market_intel"]
    print(f"  news_items:     {len(intel.news_items)}")
    print(f"  analyst_changes:{len(intel.analyst_changes)}  (expected 0 pre-IPO)")
    print(f"  narrative:\n    {intel.narrative_summary}")

    _banner("3. Signal Analysis")
    sigs = state["signals"]
    print(f"  signals: {len(sigs.signals)}")
    for s in sigs.signals:
        print(f"    [{s.direction}/{s.strength:.2f}] {s.name}: {s.rationale[:160]}")
    if sigs.flags:
        print("  flags:")
        for f in sigs.flags:
            print(f"    - {f}")

    _banner("4. Devil's Advocate")
    da = state["devils_advocate"]
    for c in da.counterarguments:
        print(f"    [{c.severity}] {c.claim[:200]}")
    print(f"\n  worst case: {da.worst_case_scenario[:400]}...")

    _banner("5. Synthesis — VerdictCard")
    syn = state["synthesis"]
    print(f"  signal:    {syn.signal}")
    print(f"  verdict:   {syn.layers.verdict}")
    print("  top 3:")
    for t in syn.layers.top_3_signals:
        print(f"    - {t}")
    print(f"  uncertainty: {syn.layers.key_uncertainty}")
    print(f"  confidence:  {syn.layers.confidence:.2f}")


if __name__ == "__main__":
    name = " ".join(sys.argv[1:]).strip() or "Reddit"
    print(f"Running pre-IPO smoke for: {name}\n")
    asyncio.run(main(name))
