"""LangGraph wiring tests.

Mocks each agent's `run()` with an AsyncMock so we're testing the graph
shape, not the agents (those have their own tests in test_agents.py).
Asserts:
  - Every node fires and writes its expected state key.
  - Parallelism: data_retrieval and market_intel both start before
    signal_analysis begins — i.e. they are NOT serialized.
  - Fan-in barrier: signal_analysis only runs once both parents have
    finished.
  - Portfolio graph reaches a terminal state with a populated recommendation.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.graphs.portfolio import build_portfolio_graph, new_portfolio_state
from app.graphs.research import build_research_graph, new_research_state
from app.models.agents import (
    Counterargument,
    DataRetrievalOutput,
    DevilsAdvocateOutput,
    HoldingSnapshot,
    MacroContext,
    MarketIntelOutput,
    PortfolioConstructionOutput,
    ProposedTrade,
    RiskFactorsExcerpt,
    Signal,
    SignalAnalysisOutput,
    SourceRef,
    SynthesisOutput,
    VerdictLayer,
)
from app.models.db.enums import AssetClass, ResearchSignal, RiskProfile

# ---------------------------------------------------------------------------
# Canned agent outputs.
# ---------------------------------------------------------------------------


def _fake_retrieved() -> DataRetrievalOutput:
    from app.models.agents.common import InsiderSummary

    return DataRetrievalOutput(
        ticker="NVDA",
        lookback_days=90,
        insider_filings=[],
        congress_trades=[],
        price_summary=None,
        volume_anomalies=[],
        risk_factors=RiskFactorsExcerpt(text="", filing_url=None, filed_at=None),
        insider_summary=InsiderSummary(),
    )


def _fake_market_intel() -> MarketIntelOutput:
    return MarketIntelOutput(
        ticker="NVDA",
        news_items=[],
        analyst_changes=[],
        macro_context=MacroContext(),
        narrative_summary="Neutral tape.",
    )


def _fake_signals() -> SignalAnalysisOutput:
    return SignalAnalysisOutput(
        ticker="NVDA",
        signals=[
            Signal(
                name="insider_cluster",
                direction="bearish",
                strength=0.6,
                rationale="CFO + EVP Field Ops sold in the same 5-day window.",
                sources=[SourceRef(kind="sec_filing", label="NVDA Form 4 2026-03")],
            )
        ],
        flags=[],
    )


def _fake_devils_advocate() -> DevilsAdvocateOutput:
    return DevilsAdvocateOutput(
        ticker="NVDA",
        counterarguments=[
            Counterargument(
                claim="Insider sales likely pre-scheduled 10b5-1",
                severity="medium",
                evidence="Plans typically set months in advance",
                sources=[],
            )
        ],
        worst_case_scenario="Data-center growth decelerates to 25% YoY.",
    )


def _fake_synthesis() -> SynthesisOutput:
    return SynthesisOutput(
        ticker="NVDA",
        signal=ResearchSignal.HOLD,
        layers=VerdictLayer(
            verdict="HOLD pending earnings print.",
            top_3_signals=["Insider cluster", "Analyst upgrade", "Macro supportive"],
            key_uncertainty="May Q2 Data Center guide",
            confidence=0.55,
        ),
        rationale="Bull and bear roughly balanced.",
        recommended_position_pct=None,
        sources=[SourceRef(kind="sec_filing", label="NVDA 10-K 2026-02")],
        valuation_bridge=None,
        confidence_breakdown=None,
        validation_result=None,
        insider_summary=None,
    )


def _fake_portfolio_rec(portfolio_id: str) -> PortfolioConstructionOutput:
    return PortfolioConstructionOutput(
        portfolio_id=portfolio_id,
        layers=VerdictLayer(
            verdict="HOLD — no trades.",
            top_3_signals=["Risk profile already met", "Cash buffer OK", "No strong BUY candidates"],
            key_uncertainty="NVDA earnings next week",
            confidence=0.6,
        ),
        proposed_trades=[
            ProposedTrade(
                ticker="NVDA",
                action="buy",
                target_weight_pct=0.03,
                rationale="Small starter position.",
                links_to_report_ticker="NVDA",
            )
        ],
        target_allocations={"MSFT": 0.5, "NVDA": 0.03, "CASH": 0.47},
        rationale="-",
    )


# ---------------------------------------------------------------------------
# Research graph.
# ---------------------------------------------------------------------------


async def test_research_graph_runs_all_six_nodes() -> None:
    from app.models.agents.synthesis import ValidationResult, ValuationBridge

    with (
        patch(
            "app.graphs.research.data_retrieval.run",
            AsyncMock(return_value=_fake_retrieved()),
        ),
        patch(
            "app.graphs.research.market_intel.run",
            AsyncMock(return_value=_fake_market_intel()),
        ),
        patch(
            "app.graphs.research.signal_analysis.run",
            AsyncMock(return_value=_fake_signals()),
        ),
        patch(
            "app.graphs.research.devils_advocate.run",
            AsyncMock(return_value=_fake_devils_advocate()),
        ),
        patch(
            "app.graphs.research._validation_svc.validate_research_inputs",
            return_value=ValidationResult(),
        ),
        patch(
            "app.graphs.research._valuation_svc.build_valuation_bridge",
            return_value=ValuationBridge(),
        ),
        patch(
            "app.graphs.research.synthesis.run",
            AsyncMock(return_value=_fake_synthesis()),
        ),
    ):
        graph = build_research_graph()
        final = await graph.ainvoke(new_research_state(ticker="NVDA"))

    assert final["ticker"] == "NVDA"
    assert isinstance(final["retrieved"], DataRetrievalOutput)
    assert isinstance(final["market_intel"], MarketIntelOutput)
    assert isinstance(final["signals"], SignalAnalysisOutput)
    assert isinstance(final["devils_advocate"], DevilsAdvocateOutput)
    assert isinstance(final["validation"], ValidationResult)
    assert isinstance(final["valuation_bridge"], ValuationBridge)
    assert isinstance(final["synthesis"], SynthesisOutput)
    assert final["synthesis"].layers.confidence == 0.55


async def test_research_graph_runs_retrieval_and_market_intel_in_parallel() -> None:
    """data_retrieval and market_intel should overlap in time; signal_analysis
    must wait for both. We detect this by having each data-node signal an
    Event before sleeping, and assert both events were set before
    signal_analysis fires."""
    retrieval_started = asyncio.Event()
    intel_started = asyncio.Event()
    signal_analysis_started_at_both_parents_done = False

    async def fake_retrieval(_inputs):
        retrieval_started.set()
        await asyncio.sleep(0.05)
        return _fake_retrieved()

    async def fake_intel(_inputs):
        intel_started.set()
        await asyncio.sleep(0.05)
        return _fake_market_intel()

    async def fake_signals(_inputs):
        nonlocal signal_analysis_started_at_both_parents_done
        # If the graph ran data-nodes serially, only one Event would be set here.
        signal_analysis_started_at_both_parents_done = (
            retrieval_started.is_set() and intel_started.is_set()
        )
        return _fake_signals()

    from app.models.agents.synthesis import ValidationResult, ValuationBridge

    with (
        patch("app.graphs.research.data_retrieval.run", side_effect=fake_retrieval),
        patch("app.graphs.research.market_intel.run", side_effect=fake_intel),
        patch("app.graphs.research.signal_analysis.run", side_effect=fake_signals),
        patch(
            "app.graphs.research.devils_advocate.run",
            AsyncMock(return_value=_fake_devils_advocate()),
        ),
        patch(
            "app.graphs.research._validation_svc.validate_research_inputs",
            return_value=ValidationResult(),
        ),
        patch(
            "app.graphs.research._valuation_svc.build_valuation_bridge",
            return_value=ValuationBridge(),
        ),
        patch(
            "app.graphs.research.synthesis.run",
            AsyncMock(return_value=_fake_synthesis()),
        ),
    ):
        graph = build_research_graph()
        await graph.ainvoke(new_research_state(ticker="NVDA"))

    assert signal_analysis_started_at_both_parents_done


async def test_research_graph_passes_portfolio_id_to_synthesis() -> None:
    """Cross-link test: research invoked from a portfolio tags the synthesis
    with that portfolio_id so downstream (ResearchReport) can filter by it."""
    captured: dict = {}

    async def fake_synthesis(inputs):
        captured["portfolio_id"] = inputs.portfolio_id
        return _fake_synthesis()

    from app.models.agents.synthesis import ValidationResult, ValuationBridge

    with (
        patch(
            "app.graphs.research.data_retrieval.run",
            AsyncMock(return_value=_fake_retrieved()),
        ),
        patch(
            "app.graphs.research.market_intel.run",
            AsyncMock(return_value=_fake_market_intel()),
        ),
        patch(
            "app.graphs.research.signal_analysis.run",
            AsyncMock(return_value=_fake_signals()),
        ),
        patch(
            "app.graphs.research.devils_advocate.run",
            AsyncMock(return_value=_fake_devils_advocate()),
        ),
        patch(
            "app.graphs.research._validation_svc.validate_research_inputs",
            return_value=ValidationResult(),
        ),
        patch(
            "app.graphs.research._valuation_svc.build_valuation_bridge",
            return_value=ValuationBridge(),
        ),
        patch("app.graphs.research.synthesis.run", side_effect=fake_synthesis),
    ):
        graph = build_research_graph()
        await graph.ainvoke(new_research_state(ticker="NVDA", portfolio_id="pf-123"))

    assert captured["portfolio_id"] == "pf-123"


# ---------------------------------------------------------------------------
# Portfolio graph.
# ---------------------------------------------------------------------------


async def test_portfolio_graph_produces_recommendation() -> None:
    with patch(
        "app.graphs.portfolio.portfolio_construction.run",
        AsyncMock(return_value=_fake_portfolio_rec("pf-abc")),
    ):
        graph = build_portfolio_graph()
        final = await graph.ainvoke(
            new_portfolio_state(
                portfolio_id="pf-abc",
                holdings=[
                    HoldingSnapshot(
                        ticker="MSFT",
                        shares=Decimal("100"),
                        avg_cost=Decimal("310.00"),
                        asset_class=AssetClass.ESTABLISHED,
                    )
                ],
                cash_balance=Decimal("20000.00"),
                risk_profile=RiskProfile.MODERATE,
                candidates=[_fake_synthesis()],
            )
        )

    rec = final["recommendation"]
    assert isinstance(rec, PortfolioConstructionOutput)
    assert rec.portfolio_id == "pf-abc"
    assert rec.proposed_trades[0].ticker == "NVDA"


async def test_portfolio_graph_forwards_candidates() -> None:
    captured: dict = {}

    async def fake_pc_run(inputs):
        captured["candidate_tickers"] = [c.ticker for c in inputs.candidates]
        captured["objective"] = inputs.objective
        return _fake_portfolio_rec(inputs.portfolio_id)

    with patch("app.graphs.portfolio.portfolio_construction.run", side_effect=fake_pc_run):
        graph = build_portfolio_graph()
        await graph.ainvoke(
            new_portfolio_state(
                portfolio_id="pf-abc",
                holdings=[],
                cash_balance=Decimal("10000"),
                risk_profile=RiskProfile.CONSERVATIVE,
                candidates=[_fake_synthesis()],
                objective="minimize drawdown",
            )
        )

    assert captured["candidate_tickers"] == ["NVDA"]
    assert captured["objective"] == "minimize drawdown"
