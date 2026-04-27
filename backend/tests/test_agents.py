"""Agent-node unit tests.

All LLM calls mocked — tests here are fast, deterministic, and run offline.
Each test pins the *tier* the node uses (so accidentally pointing the Signal
Analysis agent at Sonnet gets caught immediately) and the output-model type
it requests.

The end-to-end variant with real providers + real Anthropic lives in
`tests/verify_agents.py` and is a manual smoke, not part of the suite.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.agents import (
    Counterargument,
    DataRetrievalInput,
    DevilsAdvocateInput,
    DevilsAdvocateOutput,
    HoldingSnapshot,
    MarketIntelInput,
    MarketIntelOutput,
    PortfolioConstructionInput,
    PortfolioConstructionOutput,
    ProposedTrade,
    Signal,
    SignalAnalysisInput,
    SignalAnalysisOutput,
    SourceRef,
    SynthesisInput,
    SynthesisOutput,
    VerdictLayer,
)
from app.models.db.enums import AssetClass, ResearchSignal, RiskProfile
from app.services.agents import (
    data_retrieval,
    devils_advocate,
    market_intel,
    portfolio_construction,
    signal_analysis,
    synthesis,
)
from app.services.llm.anthropic_client import AgentTier

# ---------------------------------------------------------------------------
# Helpers — fake provider payloads so data_retrieval doesn't touch the network.
# ---------------------------------------------------------------------------


def _fake_form4() -> dict:
    return {
        "insider_filings": [
            {
                "filer": "Huang, Jensen",
                "role": "CEO",
                "transaction": "sell",
                "shares": 240000,
                "price": 905.12,
                "value_usd": 217228800.0,
                "filed_at": "2026-03-10",
                "form": "Form 4",
                "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000010/form4.xml",
            }
        ]
    }


def _fake_tenk() -> dict:
    return {
        "risk_factors_excerpt": "Risks include supply concentration and geopolitical export controls...",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000030/nvda-20250128.htm",
        "filed_at": "2025-02-21",
    }


def _fake_polygon() -> dict:
    return {
        "price_series": {"latest": 932.10, "pct_90d": 0.084, "pct_30d": -0.021, "iv_30d": 0.42},
        "volume_anomalies": [{"date": "2026-04-14", "z_score": 2.8, "note": "post-earnings spike"}],
        "analyst_changes": [
            {
                "firm": "Morgan Stanley",
                "action": "upgrade",
                "from": "overweight",
                "to": "overweight+top-pick",
                "pt_from": 950,
                "pt_to": 1050,
                "date": "2026-04-08",
            }
        ],
        "macro_context": {
            "fed_funds": 4.25,
            "ten_yr_yield": 4.07,
            "dxy": 103.2,
            "semis_index_90d_pct": 0.11,
        },
    }


def _fake_quiver() -> list[dict]:
    return [
        {
            "member": "Pelosi, N.",
            "party": "D",
            "transaction": "buy",
            "amount_range_usd": [1000000, 5000000],
            "filed_at": "2026-02-14",
            "source": "quiver",
        }
    ]


def _fake_tavily() -> dict:
    return {
        "news_items": [
            {
                "headline": "NVDA smashes Q1 earnings expectations",
                "source": "reuters",
                "url": "https://reuters.com/a",
                "published": "2026-04-18",
                "score": 0.91,
                "snippet": "NVDA data-center revenue beat consensus by 12%.",
            }
        ]
    }


# ---------------------------------------------------------------------------
# Data Retrieval — procedural, no LLM.
# ---------------------------------------------------------------------------


async def test_data_retrieval_normalizes_provider_payloads() -> None:
    with (
        patch(
            "app.services.agents.data_retrieval.sec_edgar.fetch_form4_transactions",
            AsyncMock(return_value=_fake_form4()),
        ),
        patch(
            "app.services.agents.data_retrieval.sec_edgar.fetch_10k_excerpts",
            AsyncMock(return_value=_fake_tenk()),
        ),
        patch(
            "app.services.agents.data_retrieval.quiver_stub.fetch_congress_trades",
            AsyncMock(return_value=_fake_quiver()),
        ),
        patch(
            "app.services.agents.data_retrieval.polygon_stub.fetch_market_intel",
            AsyncMock(return_value=_fake_polygon()),
        ),
    ):
        out = await data_retrieval.run(DataRetrievalInput(ticker="NVDA", lookback_days=90))

    assert out.ticker == "NVDA"
    assert out.insider_filings[0].transaction == "sell"
    assert out.congress_trades[0].member == "Pelosi, N."
    assert out.price_summary is not None
    assert out.price_summary.latest == 932.10
    assert out.volume_anomalies[0].z_score == 2.8
    assert "supply concentration" in out.risk_factors.text
    # Form 4 aggregation
    assert out.insider_summary is not None
    assert out.insider_summary.raw_transaction_count == 1
    assert out.insider_summary.unique_sellers == 1


async def test_data_retrieval_survives_missing_polygon_fixture() -> None:
    from app.services.data_providers.polygon_stub import PolygonFixtureMissingError

    with (
        patch(
            "app.services.agents.data_retrieval.sec_edgar.fetch_form4_transactions",
            AsyncMock(return_value={"insider_filings": []}),
        ),
        patch(
            "app.services.agents.data_retrieval.sec_edgar.fetch_10k_excerpts",
            AsyncMock(return_value={"risk_factors_excerpt": "", "filing_url": "", "filed_at": ""}),
        ),
        patch(
            "app.services.agents.data_retrieval.quiver_stub.fetch_congress_trades",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.agents.data_retrieval.polygon_stub.fetch_market_intel",
            AsyncMock(side_effect=PolygonFixtureMissingError("no fixture")),
        ),
        # Mock live fallback providers so the test is deterministic
        patch(
            "app.services.agents.data_retrieval.polygon_prices.fetch_prev_close_batch",
            AsyncMock(return_value={}),
        ),
        patch(
            "app.services.agents.data_retrieval.yahoo_prices.fetch_prev_close_batch",
            AsyncMock(return_value={}),
        ),
    ):
        out = await data_retrieval.run(DataRetrievalInput(ticker="ZZZZ", lookback_days=30))

    assert out.price_summary is None
    assert out.volume_anomalies == []


# ---------------------------------------------------------------------------
# Market Intel — Sonnet + providers.
# ---------------------------------------------------------------------------


async def test_market_intel_uses_sonnet_and_wraps_provider_data() -> None:
    captured: dict = {}

    async def fake_call_structured(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return kwargs["output_model"](narrative_summary="Strong quarter, supply still tight.")

    with (
        patch(
            "app.services.agents.market_intel.tavily.fetch_news",
            AsyncMock(return_value=_fake_tavily()),
        ),
        patch(
            "app.services.agents.market_intel.polygon_stub.fetch_market_intel",
            AsyncMock(return_value=_fake_polygon()),
        ),
        patch(
            "app.services.agents.market_intel.call_structured",
            side_effect=fake_call_structured,
        ),
    ):
        out = await market_intel.run(MarketIntelInput(ticker="NVDA", lookback_days=14))

    assert isinstance(out, MarketIntelOutput)
    assert out.ticker == "NVDA"
    assert out.news_items[0].headline == "NVDA smashes Q1 earnings expectations"
    assert out.analyst_changes[0].to_rating == "overweight+top-pick"
    assert out.macro_context.fed_funds == 4.25
    assert captured["tier"] == AgentTier.SONNET
    # New fields
    assert out.analyst_signal_source == "structured"
    assert isinstance(out.filtered_out_news, list)


# ---------------------------------------------------------------------------
# Signal Analysis — Opus.
# ---------------------------------------------------------------------------


def _sample_retrieved_output():  # type: ignore[no-untyped-def]
    from app.models.agents import DataRetrievalOutput, RiskFactorsExcerpt
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


def _sample_signal() -> Signal:
    return Signal(
        name="insider_cluster_buy",
        direction="bullish",
        strength=0.7,
        rationale="Three insiders bought in the last 30 days.",
        sources=[SourceRef(kind="sec_filing", label="NVDA Form 4 2026-03-10")],
    )


async def test_signal_analysis_uses_opus_and_returns_signal_output() -> None:
    captured: dict = {}

    async def fake_call_structured(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return SignalAnalysisOutput(ticker="NVDA", signals=[_sample_signal()], flags=[])

    with patch(
        "app.services.agents.signal_analysis.call_structured",
        side_effect=fake_call_structured,
    ):
        out = await signal_analysis.run(
            SignalAnalysisInput(ticker="NVDA", retrieved=_sample_retrieved_output())
        )

    assert isinstance(out, SignalAnalysisOutput)
    assert captured["tier"] == AgentTier.OPUS
    assert captured["output_model"] is SignalAnalysisOutput


# ---------------------------------------------------------------------------
# Devil's Advocate — Opus.
# ---------------------------------------------------------------------------


async def test_devils_advocate_uses_opus() -> None:
    captured: dict = {}

    async def fake_call_structured(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return DevilsAdvocateOutput(
            ticker="NVDA",
            counterarguments=[
                Counterargument(
                    claim="China revenue cliff if export controls widen",
                    severity="high",
                    evidence="10-K risk factors call this out explicitly",
                    sources=[],
                )
            ],
            worst_case_scenario="Export-controls tighten, DC revenue -25% in 2 quarters.",
        )

    with patch(
        "app.services.agents.devils_advocate.call_structured",
        side_effect=fake_call_structured,
    ):
        out = await devils_advocate.run(
            DevilsAdvocateInput(
                ticker="NVDA",
                signal_analysis=SignalAnalysisOutput(
                    ticker="NVDA", signals=[_sample_signal()], flags=[]
                ),
            )
        )

    assert captured["tier"] == AgentTier.OPUS
    assert out.counterarguments[0].severity == "high"


# ---------------------------------------------------------------------------
# Synthesis — Opus, carries the VerdictLayer.
# ---------------------------------------------------------------------------


async def test_synthesis_uses_opus_and_returns_verdict_layer() -> None:
    captured: dict = {}

    async def fake_call_structured(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return SynthesisOutput(
            ticker="NVDA",
            signal=ResearchSignal.BUY,
            layers=VerdictLayer(
                verdict="BUY, cap at 3% of portfolio",
                top_3_signals=[
                    "Insider cluster buy",
                    "Analyst upgrade w/ higher PT",
                    "Datacenter demand holding",
                ],
                key_uncertainty="Export-control rule change",
                confidence=0.68,
            ),
            rationale="Bullish thesis holds; DA case is mostly macro.",
            recommended_position_pct=0.03,
            sources=[SourceRef(kind="sec_filing", label="NVDA 10-K 2026-02")],
            valuation_bridge=None,
            confidence_breakdown=None,
            validation_result=None,
            insider_summary=None,
        )

    with patch(
        "app.services.agents.synthesis.call_structured",
        side_effect=fake_call_structured,
    ):
        out = await synthesis.run(
            SynthesisInput(
                ticker="NVDA",
                signal_analysis=SignalAnalysisOutput(
                    ticker="NVDA", signals=[_sample_signal()], flags=[]
                ),
                devils_advocate=DevilsAdvocateOutput(
                    ticker="NVDA", counterarguments=[], worst_case_scenario="-"
                ),
            )
        )

    assert captured["tier"] == AgentTier.OPUS
    assert out.layers.verdict.startswith("BUY")
    assert len(out.layers.top_3_signals) == 3
    assert out.signal == ResearchSignal.BUY


# ---------------------------------------------------------------------------
# Portfolio Construction — Sonnet.
# ---------------------------------------------------------------------------


async def test_portfolio_construction_uses_sonnet() -> None:
    captured: dict = {}

    async def fake_call_structured(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return PortfolioConstructionOutput(
            portfolio_id="pf-123",
            layers=VerdictLayer(
                verdict="Rebalance: trim MSFT, add NVDA 2%",
                top_3_signals=["NVDA conviction", "MSFT overweight", "Cash buffer OK"],
                key_uncertainty="NVDA earnings next week",
                confidence=0.6,
            ),
            proposed_trades=[
                ProposedTrade(
                    ticker="NVDA",
                    action="buy",
                    target_weight_pct=0.02,
                    rationale="Adopt latest research BUY",
                    links_to_report_ticker="NVDA",
                ),
            ],
            target_allocations={"NVDA": 0.02, "MSFT": 0.08},
            rationale="-",
        )

    with patch(
        "app.services.agents.portfolio_construction.call_structured",
        side_effect=fake_call_structured,
    ):
        out = await portfolio_construction.run(
            PortfolioConstructionInput(
                portfolio_id="pf-123",
                holdings=[
                    HoldingSnapshot(
                        ticker="MSFT",
                        shares=Decimal("100"),
                        avg_cost=Decimal("310"),
                        asset_class=AssetClass.ESTABLISHED,
                    )
                ],
                cash_balance=Decimal("25000"),
                risk_profile=RiskProfile.MODERATE,
                candidates=[],
            )
        )

    assert captured["tier"] == AgentTier.SONNET
    assert out.proposed_trades[0].ticker == "NVDA"


# ---------------------------------------------------------------------------
# Quick belt-and-suspenders: verify each agent file really does pick the
# tier it's supposed to (reading the source is fine, but asserting it via
# the mock above is what we actually trust).
# ---------------------------------------------------------------------------


def test_all_agent_modules_importable() -> None:
    # Pure import check — catches circular-import bugs added between stages.
    assert data_retrieval.run
    assert market_intel.run
    assert signal_analysis.run
    assert devils_advocate.run
    assert synthesis.run
    assert portfolio_construction.run


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
