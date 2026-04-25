"""Run-kickoff + status endpoint tests.

Strategy: patch `run_*_task.delay` so we control when the "worker" picks up
the task. After the POST returns, we manually invoke a stub that flips the
AgentRun row to COMPLETE — same effect as a real Celery worker but
synchronous and predictable.

We don't use Celery's eager mode because eager-executing a task that calls
`asyncio.run(...)` inside pytest-asyncio's already-running loop blows up
with a "cannot be called from a running event loop" error.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.auth.clerk import get_current_user
from app.db.session import SessionLocal
from app.main import app
from app.models.db import (
    AgentRun,
    AgentRunStatus,
    Portfolio,
    PortfolioHolding,
    User,
)
from app.models.db.enums import AssetClass, RiskProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_user() -> AsyncIterator[User]:
    clerk_id = f"test_runs_{uuid.uuid4()}"
    async with SessionLocal() as session:
        user = User(clerk_id=clerk_id, email=f"{clerk_id}@example.com")
        session.add(user)
        await session.commit()
        await session.refresh(user)

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.clerk_id == clerk_id))
            await session.commit()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Stub that mimics what `execute_research_run` does on a happy path: flip
# status to COMPLETE. Doesn't run the agent graph or the LLM.
async def _stub_complete(run_id: UUID) -> None:
    async with SessionLocal() as session:
        run = (
            await session.execute(select(AgentRun).where(AgentRun.id == run_id))
        ).scalar_one()
        run.status = AgentRunStatus.COMPLETE
        run.started_at = datetime.now(UTC)
        run.completed_at = datetime.now(UTC)
        await session.commit()


# ---------------------------------------------------------------------------
# Research run kickoff
# ---------------------------------------------------------------------------


async def test_research_run_returns_202_and_dispatches_celery(
    client: AsyncClient, test_user: User
):
    with patch("app.api.runs.run_research_task.delay") as mock_delay:
        resp = await client.post("/research/runs", json={"ticker": "NVDA"})
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["flow"] == "research"
    assert body["status"] == "queued"
    run_id = UUID(body["run_id"])
    mock_delay.assert_called_once_with(str(run_id))

    # Status before worker picks up: still queued.
    pre_resp = await client.get(f"/runs/{run_id}")
    assert pre_resp.status_code == 200
    assert pre_resp.json()["status"] == "queued"

    # Simulate worker pickup.
    await _stub_complete(run_id)

    post_resp = await client.get(f"/runs/{run_id}")
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "complete"
    assert post_resp.json()["ticker"] == "NVDA"


async def test_research_run_validates_portfolio_ownership(
    client: AsyncClient, test_user: User
):
    """Passing a portfolio_id you don't own must 404 before enqueueing."""
    bogus_pid = uuid.uuid4()
    resp = await client.post(
        "/research/runs",
        json={"ticker": "NVDA", "portfolio_id": str(bogus_pid)},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Portfolio run kickoff
# ---------------------------------------------------------------------------


async def test_portfolio_run_serializes_holdings_and_dispatches(
    client: AsyncClient, test_user: User
):
    """Kickoff should pull holdings from the portfolio and serialize them
    into the queued AgentRun's graph_state under _queued_inputs."""
    async with SessionLocal() as session:
        pf = Portfolio(
            user_id=test_user.id,
            name="run-test",
            cash_balance=Decimal("25000"),
            risk_profile=RiskProfile.MODERATE,
        )
        session.add(pf)
        await session.commit()
        await session.refresh(pf)

        h = PortfolioHolding(
            portfolio_id=pf.id,
            ticker="MSFT",
            shares=Decimal("50"),
            avg_cost=Decimal("310"),
            asset_class=AssetClass.ESTABLISHED,
        )
        session.add(h)
        await session.commit()
        pf_id = pf.id

    with patch("app.api.runs.run_portfolio_task.delay") as mock_delay:
        resp = await client.post(f"/portfolios/{pf_id}/runs", json={})
    assert resp.status_code == 202, resp.text
    run_id = UUID(resp.json()["run_id"])
    mock_delay.assert_called_once_with(str(run_id))

    # Confirm queued state captured the holding.
    async with SessionLocal() as session:
        run = (
            await session.execute(select(AgentRun).where(AgentRun.id == run_id))
        ).scalar_one()
        assert run.status == AgentRunStatus.QUEUED
        gs = run.graph_state or {}
        assert "_queued_inputs" in gs
        tickers = [h["ticker"] for h in gs["_queued_inputs"]["holdings"]]
        assert "MSFT" in tickers


async def test_portfolio_run_rejects_unknown_candidate_ids(
    client: AsyncClient, test_user: User
):
    async with SessionLocal() as session:
        pf = Portfolio(
            user_id=test_user.id,
            name="cand-test",
            cash_balance=Decimal("10000"),
            risk_profile=RiskProfile.MODERATE,
        )
        session.add(pf)
        await session.commit()
        await session.refresh(pf)
        pf_id = pf.id

    bogus = str(uuid.uuid4())
    resp = await client.post(
        f"/portfolios/{pf_id}/runs",
        json={"candidate_report_ids": [bogus]},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /runs listing + ownership
# ---------------------------------------------------------------------------


async def test_list_runs_filters_by_flow(client: AsyncClient, test_user: User):
    with patch("app.api.runs.run_research_task.delay"):
        await client.post("/research/runs", json={"ticker": "AAPL"})
        await client.post("/research/runs", json={"ticker": "AMD"})

    resp = await client.get("/runs", params={"flow": "research"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 2
    assert all(r["flow"] == "research" for r in rows)


async def test_get_other_users_run_returns_404(
    client: AsyncClient, test_user: User
):
    """A run owned by another user must 404 when fetched by this user."""
    async with SessionLocal() as session:
        other = User(clerk_id=f"runs_other_{uuid.uuid4()}", email="x@example.com")
        session.add(other)
        await session.commit()
        await session.refresh(other)

        from app.models.db import AgentRunFlow

        run = AgentRun(
            user_id=other.id,
            flow=AgentRunFlow.RESEARCH,
            ticker="NVDA",
            status=AgentRunStatus.COMPLETE,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        other_run_id = run.id
        other_user_id = other.id

    try:
        resp = await client.get(f"/runs/{other_run_id}")
        assert resp.status_code == 404
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == other_user_id))
            await session.commit()
