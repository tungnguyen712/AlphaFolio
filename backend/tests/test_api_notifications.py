"""Notification API + trigger evaluation tests.

`_evaluate_triggers` is called directly (awaited) rather than via
`evaluate_triggers_task.delay()` to keep the test synchronous and avoid
needing a live Celery worker.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.auth.clerk import get_current_user
from app.db.session import SessionLocal
from app.main import app
from app.models.db import (
    Notification,
    NotificationKind,
    Portfolio,
    RebalanceTrigger,
    User,
)
from app.models.db.enums import RebalanceTriggerKind, RiskProfile
from app.workers.tasks import _evaluate_triggers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_user() -> AsyncIterator[User]:
    clerk_id = f"test_notif_{uuid.uuid4()}"
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
# Trigger evaluation beat task
# ---------------------------------------------------------------------------


async def test_evaluate_triggers_fires_due_trigger_and_creates_notification(
    test_user: User,
):
    """A trigger with fires_at in the past should be fired: active → False,
    one Notification row created for the portfolio owner."""
    async with SessionLocal() as session:
        pf = Portfolio(
            user_id=test_user.id,
            name="eval-test",
            cash_balance=Decimal("5000"),
            risk_profile=RiskProfile.MODERATE,
        )
        session.add(pf)
        await session.commit()
        await session.refresh(pf)

        trigger = RebalanceTrigger(
            portfolio_id=pf.id,
            kind=RebalanceTriggerKind.EARNINGS_DATE,
            condition_json={"note": "Q1"},
            fires_at=datetime.now(UTC) - timedelta(minutes=1),
            active=True,
        )
        session.add(trigger)
        await session.commit()
        await session.refresh(trigger)
        trigger_id = trigger.id

    count = await _evaluate_triggers()
    assert count >= 1

    async with SessionLocal() as session:
        # Trigger deactivated
        t = (
            await session.execute(
                select(RebalanceTrigger).where(RebalanceTrigger.id == trigger_id)
            )
        ).scalar_one()
        assert t.active is False
        assert t.last_evaluated_at is not None

        # Notification created for this user
        notif = (
            await session.execute(
                select(Notification).where(
                    Notification.user_id == test_user.id,
                    Notification.kind == NotificationKind.REBALANCE_TRIGGER,
                )
            )
        ).scalar_one_or_none()
        assert notif is not None
        assert notif.payload["trigger_id"] == str(trigger_id)


async def test_evaluate_triggers_skips_future_trigger(test_user: User):
    """A trigger whose fires_at is in the future must not fire."""
    async with SessionLocal() as session:
        pf = Portfolio(
            user_id=test_user.id,
            name="future-test",
            cash_balance=Decimal("1000"),
            risk_profile=RiskProfile.MODERATE,
        )
        session.add(pf)
        await session.commit()
        await session.refresh(pf)

        trigger = RebalanceTrigger(
            portfolio_id=pf.id,
            kind=RebalanceTriggerKind.CUSTOM,
            condition_json={},
            fires_at=datetime.now(UTC) + timedelta(days=30),
            active=True,
        )
        session.add(trigger)
        await session.commit()
        await session.refresh(trigger)
        trigger_id = trigger.id

    await _evaluate_triggers()

    async with SessionLocal() as session:
        t = (
            await session.execute(
                select(RebalanceTrigger).where(RebalanceTrigger.id == trigger_id)
            )
        ).scalar_one()
        assert t.active is True  # untouched


# ---------------------------------------------------------------------------
# Notifications API
# ---------------------------------------------------------------------------


async def _seed_notification(
    user: User,
    kind: NotificationKind = NotificationKind.OTHER,
    read: bool = False,
) -> Notification:
    async with SessionLocal() as session:
        n = Notification(
            user_id=user.id,
            kind=kind,
            payload={"msg": "test"},
            read_at=datetime.now(UTC) if read else None,
        )
        session.add(n)
        await session.commit()
        await session.refresh(n)
        return n


async def test_list_notifications_default_returns_all(
    client: AsyncClient, test_user: User
):
    await _seed_notification(test_user, read=False)
    await _seed_notification(test_user, read=True)

    resp = await client.get("/notifications")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_list_notifications_unread_only(
    client: AsyncClient, test_user: User
):
    await _seed_notification(test_user, read=False)
    await _seed_notification(test_user, read=True)

    resp = await client.get("/notifications", params={"unread_only": "true"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    assert all(r["read_at"] is None for r in rows)


async def test_mark_notification_read(client: AsyncClient, test_user: User):
    notif = await _seed_notification(test_user, read=False)

    resp = await client.post(f"/notifications/{notif.id}/read")
    assert resp.status_code == 200
    body = resp.json()
    assert body["read_at"] is not None

    # Idempotent: second call returns 200 with read_at still set
    resp2 = await client.post(f"/notifications/{notif.id}/read")
    assert resp2.status_code == 200
    assert resp2.json()["read_at"] is not None


async def test_mark_other_users_notification_returns_404(
    client: AsyncClient, test_user: User
):
    async with SessionLocal() as session:
        other = User(
            clerk_id=f"notif_other_{uuid.uuid4()}", email="other@example.com"
        )
        session.add(other)
        await session.commit()
        await session.refresh(other)

        n = Notification(
            user_id=other.id,
            kind=NotificationKind.OTHER,
            payload={},
        )
        session.add(n)
        await session.commit()
        await session.refresh(n)
        notif_id = n.id
        other_id = other.id

    try:
        resp = await client.post(f"/notifications/{notif_id}/read")
        assert resp.status_code == 404
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(User).where(User.id == other_id))
            await session.commit()
