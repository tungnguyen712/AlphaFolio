"""Read-side research API tests — list/get reports.

Pre-creates ResearchReport rows directly in the DB; doesn't run the agent
graph. Auth dependency is overridden to a test user.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.auth.clerk import get_current_user
from app.db.session import SessionLocal
from app.main import app
from app.models.db import ResearchReport, User
from app.models.db.enums import ResearchSignal


@pytest_asyncio.fixture
async def test_user() -> AsyncIterator[User]:
    clerk_id = f"test_research_{uuid.uuid4()}"
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


def _fake_report_json(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "signal": "hold",
        "layers": {
            "verdict": "HOLD",
            "top_3_signals": ["a", "b", "c"],
            "key_uncertainty": "earnings",
            "confidence": 0.55,
        },
        "rationale": "...",
        "recommended_position_pct": None,
        "sources": [],
    }


async def _seed_report(user: User, ticker: str = "NVDA") -> ResearchReport:
    async with SessionLocal() as session:
        rep = ResearchReport(
            user_id=user.id,
            ticker=ticker,
            signal=ResearchSignal.HOLD,
            confidence=0.55,
            report_json=_fake_report_json(ticker),
        )
        session.add(rep)
        await session.commit()
        await session.refresh(rep)
        return rep


async def test_list_reports_filters_by_ticker(
    client: AsyncClient, test_user: User
):
    await _seed_report(test_user, "NVDA")
    await _seed_report(test_user, "AAPL")

    resp = await client.get("/research/reports", params={"ticker": "NVDA"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["ticker"] == "NVDA"


async def test_get_report_returns_full_payload(
    client: AsyncClient, test_user: User
):
    rep = await _seed_report(test_user, "MSFT")
    resp = await client.get(f"/research/reports/{rep.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "MSFT"
    assert body["report"]["layers"]["confidence"] == 0.55


async def test_get_other_users_report_returns_404(
    client: AsyncClient, test_user: User
):
    async with SessionLocal() as session:
        other = User(clerk_id=f"r_other_{uuid.uuid4()}", email="x@example.com")
        session.add(other)
        await session.commit()
        await session.refresh(other)

        rep = ResearchReport(
            user_id=other.id,
            ticker="ZZZZ",
            signal=ResearchSignal.SELL,
            confidence=0.4,
            report_json=_fake_report_json("ZZZZ"),
        )
        session.add(rep)
        await session.commit()
        await session.refresh(rep)
        other_rep_id = rep.id
        other_id = other.id

    try:
        resp = await client.get(f"/research/reports/{other_rep_id}")
        assert resp.status_code == 404
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == other_id))
            await session.commit()
