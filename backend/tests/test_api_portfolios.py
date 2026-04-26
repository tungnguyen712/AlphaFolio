"""Portfolio + holdings + recommendations API tests.

Auth is overridden with a test-user dependency so we don't need a real
Clerk JWT. DB is the dev Postgres in the backend container.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.auth.clerk import get_current_user
from app.db.session import SessionLocal
from app.main import app
from app.models.db import (
    PendingPositionStatus,
    Portfolio,
    PortfolioHolding,
    PortfolioPositionPending,
    RebalanceTrigger,
    User,
)
from app.models.db.enums import AssetClass, RebalanceTriggerKind, RiskProfile


@pytest_asyncio.fixture
async def test_user() -> AsyncIterator[User]:
    """Create a one-off user for the test, override get_current_user to return
    it, clean up afterwards."""
    clerk_id = f"test_api_{uuid.uuid4()}"
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


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------


async def test_create_and_list_portfolio(client: AsyncClient, test_user: User):
    resp = await client.post(
        "/portfolios",
        json={
            "name": "Test PF",
            "cash_balance": "10000.00",
            "risk_profile": "moderate",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Test PF"
    assert body["risk_profile"] == "moderate"
    pid = body["id"]

    listing = await client.get("/portfolios")
    assert listing.status_code == 200
    assert any(p["id"] == pid for p in listing.json())


async def test_get_portfolio_with_holdings(client: AsyncClient, test_user: User):
    create = await client.post(
        "/portfolios",
        json={"name": "PF2", "cash_balance": "5000", "risk_profile": "conservative"},
    )
    pid = create.json()["id"]

    add_holding = await client.post(
        f"/portfolios/{pid}/holdings",
        json={
            "ticker": "msft",  # ensure server upper-cases
            "shares": "10",
            "avg_cost": "300.00",
            "asset_class": "established",
        },
    )
    assert add_holding.status_code == 201
    assert add_holding.json()["ticker"] == "MSFT"

    full = await client.get(f"/portfolios/{pid}")
    assert full.status_code == 200
    assert len(full.json()["holdings"]) == 1
    assert full.json()["holdings"][0]["asset_class"] == "established"


async def test_patch_holding_partial_update(client: AsyncClient, test_user: User):
    pf = (
        await client.post(
            "/portfolios",
            json={"name": "PF3", "cash_balance": "1000", "risk_profile": "aggressive"},
        )
    ).json()
    holding = (
        await client.post(
            f"/portfolios/{pf['id']}/holdings",
            json={
                "ticker": "AAPL",
                "shares": "5",
                "avg_cost": "150",
                "asset_class": "established",
            },
        )
    ).json()

    resp = await client.patch(
        f"/portfolios/{pf['id']}/holdings/{holding['id']}",
        json={"shares": "12.5"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["shares"]) == Decimal("12.5")
    assert Decimal(body["avg_cost"]) == Decimal("150")  # unchanged


async def test_cannot_access_other_users_portfolio(
    client: AsyncClient, test_user: User
):
    """Create a portfolio under a different user, then try to fetch it as
    test_user — should 404, not leak existence."""
    async with SessionLocal() as session:
        other = User(clerk_id=f"other_{uuid.uuid4()}", email="other@example.com")
        session.add(other)
        await session.commit()
        await session.refresh(other)

        from app.models.db import Portfolio
        from app.models.db.enums import RiskProfile

        pf = Portfolio(
            user_id=other.id,
            name="OtherPF",
            cash_balance=Decimal("0"),
            risk_profile=RiskProfile.MODERATE,
        )
        session.add(pf)
        await session.commit()
        await session.refresh(pf)
        other_pf_id = pf.id
        other_user_id = other.id

    try:
        resp = await client.get(f"/portfolios/{other_pf_id}")
        assert resp.status_code == 404
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == other_user_id))
            await session.commit()


async def test_validation_rejects_zero_shares(client: AsyncClient, test_user: User):
    pf = (
        await client.post(
            "/portfolios",
            json={"name": "PF4", "cash_balance": "0", "risk_profile": "moderate"},
        )
    ).json()
    resp = await client.post(
        f"/portfolios/{pf['id']}/holdings",
        json={
            "ticker": "NVDA",
            "shares": "0",
            "avg_cost": "100",
            "asset_class": "established",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Health check (sanity that app boots through lifespan)
# ---------------------------------------------------------------------------


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# Silence unused-fixture warnings — fixture is consumed via Depends override.
_ = pytest


# ---------------------------------------------------------------------------
# Pending positions
# ---------------------------------------------------------------------------


async def _seed_portfolio(user: User, name: str = "TestPF") -> Portfolio:
    async with SessionLocal() as session:
        pf = Portfolio(
            user_id=user.id,
            name=name,
            cash_balance=Decimal("10000"),
            risk_profile=RiskProfile.MODERATE,
        )
        session.add(pf)
        await session.commit()
        await session.refresh(pf)
        return pf


async def test_list_pending_positions_returns_only_pending_by_default(
    client: AsyncClient, test_user: User
):
    pf = await _seed_portfolio(test_user)

    async with SessionLocal() as session:
        session.add(
            PortfolioPositionPending(
                portfolio_id=pf.id,
                ticker="NVDA",
                target_pct=Decimal("0.05"),
                status=PendingPositionStatus.PENDING,
            )
        )
        session.add(
            PortfolioPositionPending(
                portfolio_id=pf.id,
                ticker="AAPL",
                target_pct=Decimal("0.03"),
                status=PendingPositionStatus.REJECTED,
            )
        )
        await session.commit()

    resp = await client.get(f"/portfolios/{pf.id}/pending")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["ticker"] == "NVDA"

    # include_resolved shows both
    resp_all = await client.get(
        f"/portfolios/{pf.id}/pending", params={"include_resolved": "true"}
    )
    assert len(resp_all.json()) == 2


async def test_accept_pending_position_creates_holding(
    client: AsyncClient, test_user: User
):
    pf = await _seed_portfolio(test_user)

    async with SessionLocal() as session:
        pending = PortfolioPositionPending(
            portfolio_id=pf.id,
            ticker="MSFT",
            target_pct=Decimal("0.10"),
            status=PendingPositionStatus.PENDING,
        )
        session.add(pending)
        await session.commit()
        await session.refresh(pending)
        pending_id = pending.id

    resp = await client.post(
        f"/portfolios/{pf.id}/pending/{pending_id}/accept",
        json={"shares": "15", "avg_cost": "420.00", "asset_class": "established"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["ticker"] == "MSFT"
    assert Decimal(body["shares"]) == Decimal("15")

    # Pending row should now be ACCEPTED
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(PortfolioPositionPending).where(
                    PortfolioPositionPending.id == pending_id
                )
            )
        ).scalar_one()
        assert row.status == PendingPositionStatus.ACCEPTED

    # Holding should be in the portfolio
    pf_resp = await client.get(f"/portfolios/{pf.id}")
    tickers = [h["ticker"] for h in pf_resp.json()["holdings"]]
    assert "MSFT" in tickers


async def test_reject_pending_position(client: AsyncClient, test_user: User):
    pf = await _seed_portfolio(test_user)

    async with SessionLocal() as session:
        pending = PortfolioPositionPending(
            portfolio_id=pf.id,
            ticker="GME",
            target_pct=Decimal("0.01"),
            status=PendingPositionStatus.PENDING,
        )
        session.add(pending)
        await session.commit()
        await session.refresh(pending)
        pending_id = pending.id

    resp = await client.post(f"/portfolios/{pf.id}/pending/{pending_id}/reject")
    assert resp.status_code == 204

    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(PortfolioPositionPending).where(
                    PortfolioPositionPending.id == pending_id
                )
            )
        ).scalar_one()
        assert row.status == PendingPositionStatus.REJECTED


async def test_double_resolve_returns_409(client: AsyncClient, test_user: User):
    pf = await _seed_portfolio(test_user)

    async with SessionLocal() as session:
        pending = PortfolioPositionPending(
            portfolio_id=pf.id,
            ticker="AMC",
            target_pct=Decimal("0.01"),
            status=PendingPositionStatus.PENDING,
        )
        session.add(pending)
        await session.commit()
        await session.refresh(pending)
        pending_id = pending.id

    # First accept
    await client.post(
        f"/portfolios/{pf.id}/pending/{pending_id}/accept",
        json={"shares": "5", "avg_cost": "10.00"},
    )
    # Second accept must 409
    resp = await client.post(
        f"/portfolios/{pf.id}/pending/{pending_id}/accept",
        json={"shares": "5", "avg_cost": "10.00"},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Rebalance triggers
# ---------------------------------------------------------------------------


async def test_trigger_create_list_deactivate(
    client: AsyncClient, test_user: User
):
    pf = await _seed_portfolio(test_user, "TrigPF")

    create_resp = await client.post(
        f"/portfolios/{pf.id}/triggers",
        json={
            "kind": "earnings_date",
            "condition_json": {"note": "Q2 earnings"},
            "fires_at": "2026-07-15T00:00:00Z",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()
    assert body["kind"] == "earnings_date"
    assert body["active"] is True
    trigger_id = body["id"]

    list_resp = await client.get(f"/portfolios/{pf.id}/triggers")
    assert list_resp.status_code == 200
    assert any(t["id"] == trigger_id for t in list_resp.json())

    del_resp = await client.delete(f"/portfolios/{pf.id}/triggers/{trigger_id}")
    assert del_resp.status_code == 204

    # Deactivated trigger absent from default list, present with include_inactive
    list_after = await client.get(f"/portfolios/{pf.id}/triggers")
    assert not any(t["id"] == trigger_id for t in list_after.json())

    list_inactive = await client.get(
        f"/portfolios/{pf.id}/triggers", params={"include_inactive": "true"}
    )
    match = next(t for t in list_inactive.json() if t["id"] == trigger_id)
    assert match["active"] is False
