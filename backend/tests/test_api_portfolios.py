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
from sqlalchemy import delete

from app.auth.clerk import get_current_user
from app.db.session import SessionLocal
from app.main import app
from app.models.db import User


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
