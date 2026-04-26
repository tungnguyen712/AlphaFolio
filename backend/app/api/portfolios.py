"""Portfolio + holdings + recommendations + pending positions + triggers endpoints.

All resources scoped to the authenticated user; cross-user reads return 404
to avoid leaking existence.
"""
from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DBSessionDep
from app.config import get_settings
from app.services.data_providers import polygon_prices, yahoo_prices
from app.api.schemas.pending import AcceptPendingBody, CreatePendingBody, PendingPositionOut
from app.api.schemas.portfolios import (
    HoldingCreate,
    HoldingOut,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioOut,
    PortfolioPricesOut,
    PortfolioUpdate,
    PortfolioWithHoldingsOut,
    TickerMarketData,
)
from app.api.schemas.recommendations import PortfolioRecommendationOut
from app.api.schemas.triggers import TriggerCreate, TriggerOut
from app.models.db import (
    PendingPositionStatus,
    Portfolio,
    PortfolioHolding,
    PortfolioPositionPending,
    PortfolioRecommendation,
    RebalanceTrigger,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


# ---------------------------------------------------------------------------
# Portfolios
# ---------------------------------------------------------------------------


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    body: PortfolioCreate,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> Portfolio:
    portfolio = Portfolio(
        user_id=user.id,
        name=body.name,
        cash_balance=body.cash_balance,
        risk_profile=body.risk_profile,
    )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.get("", response_model=list[PortfolioOut])
async def list_portfolios(user: CurrentUserDep, db: DBSessionDep) -> list[Portfolio]:
    result = await db.execute(
        select(Portfolio)
        .where(Portfolio.user_id == user.id)
        .order_by(Portfolio.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{portfolio_id}", response_model=PortfolioWithHoldingsOut)
async def get_portfolio(
    portfolio_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> PortfolioWithHoldingsOut:
    portfolio = await _load_owned_portfolio(db, portfolio_id, user.id)
    holdings_rows = (
        await db.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio.id)
            .order_by(PortfolioHolding.created_at.desc())
        )
    ).scalars().all()
    return PortfolioWithHoldingsOut(
        id=portfolio.id,
        name=portfolio.name,
        cash_balance=portfolio.cash_balance,
        risk_profile=portfolio.risk_profile,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        holdings=[HoldingOut.model_validate(h) for h in holdings_rows],
    )


@router.patch("/{portfolio_id}", response_model=PortfolioOut)
async def update_portfolio(
    portfolio_id: UUID,
    body: PortfolioUpdate,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> Portfolio:
    portfolio = await _load_owned_portfolio(db, portfolio_id, user.id)

    if body.name is not None:
        portfolio.name = body.name
    if body.risk_profile is not None:
        portfolio.risk_profile = body.risk_profile
    if body.cash_balance is not None:
        portfolio.cash_balance = body.cash_balance

    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> None:
    portfolio = await _load_owned_portfolio(db, portfolio_id, user.id)
    await db.delete(portfolio)
    await db.commit()


# ---------------------------------------------------------------------------
# Market data (prices + sector for dashboard)
# ---------------------------------------------------------------------------


@router.get("/{portfolio_id}/prices", response_model=PortfolioPricesOut)
async def get_portfolio_prices(
    portfolio_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> PortfolioPricesOut:
    portfolio = await _load_owned_portfolio(db, portfolio_id, user.id)
    holdings_rows = (
        await db.execute(
            select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio.id)
        )
    ).scalars().all()

    tickers = [h.ticker for h in holdings_rows]
    if not tickers:
        return PortfolioPricesOut(prices={})

    api_key = get_settings().polygon_api_key
    if api_key:
        prices, sectors = await asyncio.gather(
            polygon_prices.fetch_prev_close_batch(tickers, api_key),
            polygon_prices.fetch_ticker_details_batch(tickers, api_key),
        )
    else:
        prices, sectors = await asyncio.gather(
            yahoo_prices.fetch_prev_close_batch(tickers),
            yahoo_prices.fetch_ticker_details_batch(tickers),
        )

    return PortfolioPricesOut(
        prices={
            t: TickerMarketData(
                prev_close=prices.get(t),
                sector=sectors.get(t),
            )
            for t in tickers
        }
    )


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------


@router.post(
    "/{portfolio_id}/holdings",
    response_model=HoldingOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_holding(
    portfolio_id: UUID,
    body: HoldingCreate,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> PortfolioHolding:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    holding = PortfolioHolding(
        portfolio_id=portfolio_id,
        ticker=body.ticker.upper(),
        shares=body.shares,
        avg_cost=body.avg_cost,
        asset_class=body.asset_class,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


@router.patch("/{portfolio_id}/holdings/{holding_id}", response_model=HoldingOut)
async def update_holding(
    portfolio_id: UUID,
    holding_id: UUID,
    body: HoldingUpdate,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> PortfolioHolding:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    holding = await _load_holding(db, holding_id, portfolio_id)

    if body.shares is not None:
        holding.shares = body.shares
    if body.avg_cost is not None:
        holding.avg_cost = body.avg_cost
    if body.asset_class is not None:
        holding.asset_class = body.asset_class

    await db.commit()
    await db.refresh(holding)
    return holding


@router.delete(
    "/{portfolio_id}/holdings/{holding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_holding(
    portfolio_id: UUID,
    holding_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> None:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    holding = await _load_holding(db, holding_id, portfolio_id)
    await db.delete(holding)
    await db.commit()


# ---------------------------------------------------------------------------
# Portfolio recommendations (read-only — generated via /portfolios/{id}/runs)
# ---------------------------------------------------------------------------


@router.get(
    "/{portfolio_id}/recommendations",
    response_model=list[PortfolioRecommendationOut],
)
async def list_recommendations(
    portfolio_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
    limit: int = 20,
    offset: int = 0,
) -> list[PortfolioRecommendationOut]:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    result = await db.execute(
        select(PortfolioRecommendation)
        .where(PortfolioRecommendation.portfolio_id == portfolio_id)
        .order_by(PortfolioRecommendation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list(result.scalars().all())
    # Map ORM `recommendation_json` -> response field `recommendation`.
    return [
        PortfolioRecommendationOut(
            id=r.id,
            run_id=r.run_id,
            portfolio_id=r.portfolio_id,
            recommendation=r.recommendation_json,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Pending positions (Research → Portfolio handoff)
# ---------------------------------------------------------------------------


@router.get("/{portfolio_id}/pending", response_model=list[PendingPositionOut])
async def list_pending_positions(
    portfolio_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
    include_resolved: bool = False,
) -> list[PortfolioPositionPending]:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    stmt = select(PortfolioPositionPending).where(
        PortfolioPositionPending.portfolio_id == portfolio_id
    )
    if not include_resolved:
        stmt = stmt.where(
            PortfolioPositionPending.status == PendingPositionStatus.PENDING
        )
    stmt = stmt.order_by(PortfolioPositionPending.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.post(
    "/{portfolio_id}/pending",
    response_model=PendingPositionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_pending_position(
    portfolio_id: UUID,
    body: CreatePendingBody,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> PortfolioPositionPending:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    pending = PortfolioPositionPending(
        portfolio_id=portfolio_id,
        ticker=body.ticker.upper(),
        target_pct=body.target_pct,
        source_report_id=body.source_report_id,
        status=PendingPositionStatus.PENDING,
    )
    db.add(pending)
    await db.commit()
    await db.refresh(pending)
    return pending


@router.post(
    "/{portfolio_id}/pending/{pending_id}/accept",
    response_model=HoldingOut,
    status_code=status.HTTP_201_CREATED,
)
async def accept_pending_position(
    portfolio_id: UUID,
    pending_id: UUID,
    body: AcceptPendingBody,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> PortfolioHolding:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    pending = await _load_pending(db, pending_id, portfolio_id)
    if pending.status != PendingPositionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="position already resolved"
        )
    holding = PortfolioHolding(
        portfolio_id=portfolio_id,
        ticker=pending.ticker,
        shares=body.shares,
        avg_cost=body.avg_cost,
        asset_class=body.asset_class,
    )
    db.add(holding)
    pending.status = PendingPositionStatus.ACCEPTED
    await db.commit()
    await db.refresh(holding)
    return holding


@router.post(
    "/{portfolio_id}/pending/{pending_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reject_pending_position(
    portfolio_id: UUID,
    pending_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> None:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    pending = await _load_pending(db, pending_id, portfolio_id)
    if pending.status != PendingPositionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="position already resolved"
        )
    pending.status = PendingPositionStatus.REJECTED
    await db.commit()


# ---------------------------------------------------------------------------
# Rebalance triggers
# ---------------------------------------------------------------------------


@router.post(
    "/{portfolio_id}/triggers",
    response_model=TriggerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_trigger(
    portfolio_id: UUID,
    body: TriggerCreate,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> RebalanceTrigger:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    trigger = RebalanceTrigger(
        portfolio_id=portfolio_id,
        kind=body.kind,
        condition_json=body.condition_json,
        fires_at=body.fires_at,
        active=True,
    )
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)
    return trigger


@router.get("/{portfolio_id}/triggers", response_model=list[TriggerOut])
async def list_triggers(
    portfolio_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
    include_inactive: bool = False,
) -> list[RebalanceTrigger]:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    stmt = select(RebalanceTrigger).where(
        RebalanceTrigger.portfolio_id == portfolio_id
    )
    if not include_inactive:
        stmt = stmt.where(RebalanceTrigger.active.is_(True))
    stmt = stmt.order_by(RebalanceTrigger.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.delete(
    "/{portfolio_id}/triggers/{trigger_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_trigger(
    portfolio_id: UUID,
    trigger_id: UUID,
    user: CurrentUserDep,
    db: DBSessionDep,
) -> None:
    await _load_owned_portfolio(db, portfolio_id, user.id)
    trigger = await _load_trigger(db, trigger_id, portfolio_id)
    trigger.active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Helpers (also used by app/api/runs.py; not private to this module)
# ---------------------------------------------------------------------------


async def _load_owned_portfolio(
    db, portfolio_id: UUID, user_id: UUID
) -> Portfolio:
    portfolio = (
        await db.execute(
            select(Portfolio).where(
                Portfolio.id == portfolio_id, Portfolio.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="portfolio not found"
        )
    return portfolio


async def _load_holding(
    db, holding_id: UUID, portfolio_id: UUID
) -> PortfolioHolding:
    holding = (
        await db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.id == holding_id,
                PortfolioHolding.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()
    if holding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="holding not found"
        )
    return holding


async def _load_pending(
    db, pending_id: UUID, portfolio_id: UUID
) -> PortfolioPositionPending:
    pending = (
        await db.execute(
            select(PortfolioPositionPending).where(
                PortfolioPositionPending.id == pending_id,
                PortfolioPositionPending.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="pending position not found"
        )
    return pending


async def _load_trigger(
    db, trigger_id: UUID, portfolio_id: UUID
) -> RebalanceTrigger:
    trigger = (
        await db.execute(
            select(RebalanceTrigger).where(
                RebalanceTrigger.id == trigger_id,
                RebalanceTrigger.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()
    if trigger is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="trigger not found"
        )
    return trigger


