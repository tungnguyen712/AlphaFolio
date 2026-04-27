"""Builds a ValuationBridge from structured data already in the pipeline.

Pure Python — no LLM, no network. Assembles current price, available
multiples, and simple scenario anchors. The Synthesis agent then uses this
as a structured foundation for its valuation commentary.
"""
from __future__ import annotations

from app.models.agents.data_retrieval import DataRetrievalOutput
from app.models.agents.market_intel import MarketIntelOutput
from app.models.agents.synthesis import ScenarioCase, ValuationBridge


def build_valuation_bridge(
    retrieved: DataRetrievalOutput,
    market_intel: MarketIntelOutput | None,
) -> ValuationBridge:
    """Construct a ValuationBridge from available structured data.

    Scenarios are anchored to current price with simple percentage multiples
    when fundamental data (forward PE, EV/Revenue) is unavailable. All missing
    fields are listed explicitly so Synthesis can disclose them.
    """
    ps = retrieved.price_summary
    current = ps.latest if ps else None
    missing: list[str] = []

    if current is None:
        missing.append("current_price")
    if not ps or ps.market_cap is None:
        missing.append("market_cap")
    if not ps or ps.forward_pe is None:
        missing.append("forward_pe")
    if not ps or ps.ev_revenue is None:
        missing.append("ev_revenue")

    scenarios: list[ScenarioCase] = []
    if current is not None:
        scenarios = [
            ScenarioCase(
                label="bull",
                price_target=round(current * 1.25, 2),
                implied_upside_pct=25.0,
                key_assumption="Multiple expansion + earnings beat above consensus.",
            ),
            ScenarioCase(
                label="base",
                price_target=round(current * 1.08, 2),
                implied_upside_pct=8.0,
                key_assumption="Steady-state growth in line with guidance.",
            ),
            ScenarioCase(
                label="bear",
                price_target=round(current * 0.82, 2),
                implied_upside_pct=-18.0,
                key_assumption="Margin compression or guidance cut.",
            ),
        ]

    return ValuationBridge(
        current_price=current,
        price_timestamp=ps.retrieved_at if ps else None,
        market_cap=ps.market_cap if ps else None,
        forward_pe=ps.forward_pe if ps else None,
        ev_revenue=ps.ev_revenue if ps else None,
        scenarios=scenarios,
        missing_fields=missing,
    )
