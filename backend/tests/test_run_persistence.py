"""Persistence-wrapper tests.

The LangGraph graphs are swapped for fakes that yield canned `updates`, so
we're testing the DB side only. Runs against the dev Postgres inside the
backend container — same pattern as `test_providers.py`'s cache test.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
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
from app.models.db import (
    AgentRun,
    AgentRunFlow,
    AgentRunStatus,
    AgentRunStep,
    AssetClass,
    Portfolio,
    PortfolioRecommendation,
    ResearchReport,
    RiskProfile,
    User,
)
from app.services.runs.persistence import run_portfolio, run_research


# ---------------------------------------------------------------------------
# Fixtures — test-only user (and portfolio) rows, cleaned up after.
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_id():
    clerk_id = f"test_{uuid.uuid4()}"
    async with SessionLocal() as session:
        user = User(clerk_id=clerk_id, email=f"{clerk_id}@example.com")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        yield user.id

    # Cascade-delete via user → runs/reports.
    async with SessionLocal() as session:
        await session.execute(delete(User).where(User.clerk_id == clerk_id))
        await session.commit()


@pytest.fixture
async def portfolio_id(user_id):
    async with SessionLocal() as session:
        pf = Portfolio(
            user_id=user_id,
            name="test-portfolio",
            cash_balance=Decimal("10000"),
            risk_profile=RiskProfile.MODERATE,
        )
        session.add(pf)
        await session.commit()
        await session.refresh(pf)
        yield pf.id
    # User fixture teardown cascades to portfolio.


# ---------------------------------------------------------------------------
# Canned agent outputs (matches the graph's shape).
# ---------------------------------------------------------------------------


def _synthesis_output(ticker: str = "NVDA") -> SynthesisOutput:
    return SynthesisOutput(
        ticker=ticker,
        signal="hold",
        layers=VerdictLayer(
            verdict="HOLD pending earnings.",
            top_3_signals=["Insider cluster", "Analyst upgrade", "Macro supportive"],
            key_uncertainty="Q2 Data Center guide",
            confidence=0.55,
        ),
        rationale="Balanced.",
        recommended_position_pct=None,
        sources=[SourceRef(kind="sec_filing", label="NVDA 10-K 2026-02")],
    )


def _research_updates(ticker: str = "NVDA"):
    """Yields the sequence of `updates` a real research_graph would emit."""

    retrieved = DataRetrievalOutput(
        ticker=ticker,
        lookback_days=90,
        insider_filings=[],
        congress_trades=[],
        price_summary=None,
        volume_anomalies=[],
        risk_factors=RiskFactorsExcerpt(text="", filing_url=None, filed_at=None),
    )
    intel = MarketIntelOutput(
        ticker=ticker,
        news_items=[],
        analyst_changes=[],
        macro_context=MacroContext(),
        narrative_summary="Neutral.",
    )
    sigs = SignalAnalysisOutput(
        ticker=ticker,
        signals=[
            Signal(
                name="x",
                direction="neutral",
                strength=0.3,
                rationale="r",
                sources=[SourceRef(kind="news", label="n")],
            )
        ],
        flags=[],
    )
    da = DevilsAdvocateOutput(
        ticker=ticker,
        counterarguments=[
            Counterargument(claim="c", severity="low", evidence="e", sources=[])
        ],
        worst_case_scenario="w",
    )
    syn = _synthesis_output(ticker)

    return [
        {"data_retrieval": {"retrieved": retrieved}},
        {"market_intel": {"market_intel": intel}},
        {"signal_analysis": {"signals": sigs}},
        {"devils_advocate": {"devils_advocate": da}},
        {"synthesis": {"synthesis": syn}},
    ]


def _portfolio_update(portfolio_id: str):
    return {
        "portfolio_construction": {
            "recommendation": PortfolioConstructionOutput(
                portfolio_id=portfolio_id,
                layers=VerdictLayer(
                    verdict="HOLD",
                    top_3_signals=["a", "b", "c"],
                    key_uncertainty="u",
                    confidence=0.6,
                ),
                proposed_trades=[
                    ProposedTrade(
                        ticker="NVDA",
                        action="buy",
                        target_weight_pct=0.02,
                        rationale="starter",
                        links_to_report_ticker="NVDA",
                    )
                ],
                target_allocations={"NVDA": 0.02, "CASH": 0.98},
                rationale="-",
            )
        }
    }


class _FakeGraph:
    """Quacks like a compiled StateGraph for our persistence wrapper — supports
    .astream(initial, stream_mode=...) returning an async generator over
    canned update dicts."""

    def __init__(self, updates):
        self._updates = updates

    def astream(self, initial, stream_mode="updates"):  # noqa: ARG002
        updates = self._updates

        async def _gen():
            for u in updates:
                yield u

        return _gen()


# ---------------------------------------------------------------------------
# Research persistence
# ---------------------------------------------------------------------------


async def test_run_research_persists_run_steps_and_report(user_id):
    fake = _FakeGraph(_research_updates("NVDA"))
    with patch("app.services.runs.persistence._research_graph", fake):
        run_id, synth = await run_research(user_id=user_id, ticker="NVDA")

    assert synth.ticker == "NVDA"

    async with SessionLocal() as session:
        run = (await session.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one()
        assert run.flow == AgentRunFlow.RESEARCH
        assert run.status == AgentRunStatus.COMPLETE
        assert run.ticker == "NVDA"
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.graph_state is not None
        # Final state dump should include every agent's output key.
        for key in ("retrieved", "market_intel", "signals", "devils_advocate", "synthesis"):
            assert key in run.graph_state

        steps = (
            await session.execute(
                select(AgentRunStep)
                .where(AgentRunStep.run_id == run_id)
                .order_by(AgentRunStep.completed_at)
            )
        ).scalars().all()
        assert [s.agent_name for s in steps] == [
            "data_retrieval",
            "market_intel",
            "signal_analysis",
            "devils_advocate",
            "synthesis",
        ]
        assert all(s.output is not None for s in steps)

        report = (
            await session.execute(select(ResearchReport).where(ResearchReport.run_id == run_id))
        ).scalar_one()
        assert report.ticker == "NVDA"
        assert report.confidence == 0.55
        assert report.report_json["layers"]["key_uncertainty"] == "Q2 Data Center guide"


async def test_run_research_marks_failed_on_exception(user_id):
    class _Explode:
        def astream(self, initial, stream_mode="updates"):  # noqa: ARG002
            async def _gen():
                yield {"data_retrieval": {"retrieved": "ok"}}
                raise RuntimeError("synthesis blew up")

            return _gen()

    with patch("app.services.runs.persistence._research_graph", _Explode()):
        with pytest.raises(RuntimeError, match="synthesis blew up"):
            await run_research(user_id=user_id, ticker="NVDA")

    async with SessionLocal() as session:
        runs = (
            await session.execute(
                select(AgentRun).where(AgentRun.user_id == user_id).order_by(AgentRun.started_at)
            )
        ).scalars().all()
        assert len(runs) == 1
        assert runs[0].status == AgentRunStatus.FAILED
        assert runs[0].completed_at is not None

        err_step = (
            await session.execute(
                select(AgentRunStep).where(
                    AgentRunStep.run_id == runs[0].id, AgentRunStep.agent_name == "_error"
                )
            )
        ).scalar_one()
        assert "synthesis blew up" in err_step.error

        # No research_report row for a failed run.
        reports = (
            await session.execute(
                select(ResearchReport).where(ResearchReport.run_id == runs[0].id)
            )
        ).scalars().all()
        assert reports == []


# ---------------------------------------------------------------------------
# Portfolio persistence
# ---------------------------------------------------------------------------


async def test_run_portfolio_persists_recommendation(user_id, portfolio_id):
    fake = _FakeGraph([_portfolio_update(str(portfolio_id))])
    with patch("app.services.runs.persistence._portfolio_graph", fake):
        run_id, rec = await run_portfolio(
            user_id=user_id,
            portfolio_id=portfolio_id,
            holdings=[
                HoldingSnapshot(
                    ticker="MSFT",
                    shares=Decimal("10"),
                    avg_cost=Decimal("310"),
                    asset_class=AssetClass.ESTABLISHED,
                )
            ],
            cash_balance=Decimal("5000"),
            risk_profile=RiskProfile.MODERATE,
            candidates=[_synthesis_output("NVDA")],
        )

    assert rec.portfolio_id == str(portfolio_id)

    async with SessionLocal() as session:
        run = (await session.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one()
        assert run.flow == AgentRunFlow.PORTFOLIO
        assert run.status == AgentRunStatus.COMPLETE
        assert run.ticker is None  # portfolio runs aren't ticker-scoped

        steps = (
            await session.execute(select(AgentRunStep).where(AgentRunStep.run_id == run_id))
        ).scalars().all()
        assert [s.agent_name for s in steps] == ["portfolio_construction"]

        pr = (
            await session.execute(
                select(PortfolioRecommendation).where(PortfolioRecommendation.run_id == run_id)
            )
        ).scalar_one()
        assert pr.portfolio_id == portfolio_id
        assert pr.recommendation_json["proposed_trades"][0]["ticker"] == "NVDA"
