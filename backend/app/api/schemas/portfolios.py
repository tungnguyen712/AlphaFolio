"""Request/response schemas for portfolio + holdings endpoints.

Distinct from the DB ORM types (in app.models.db) and from the agent I/O
types (in app.models.agents). Decimals serialize as strings to avoid float
precision surprises in JSON.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.db.enums import AssetClass, RiskProfile


class _APISchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Portfolios
# ---------------------------------------------------------------------------


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    cash_balance: Decimal = Field(ge=0)
    risk_profile: RiskProfile


class PortfolioUpdate(BaseModel):
    """All fields optional — PATCH semantics. Send only what you want changed."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    risk_profile: RiskProfile | None = None
    cash_balance: Decimal | None = Field(default=None, ge=0)


class PortfolioOut(_APISchema):
    id: UUID
    name: str
    cash_balance: Decimal
    risk_profile: RiskProfile
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------


class HoldingCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    shares: Decimal = Field(gt=0)
    avg_cost: Decimal = Field(ge=0)
    asset_class: AssetClass


class HoldingUpdate(BaseModel):
    """All fields optional — PATCH semantics. Send only what you want changed."""

    shares: Decimal | None = Field(default=None, gt=0)
    avg_cost: Decimal | None = Field(default=None, ge=0)
    asset_class: AssetClass | None = None


class HoldingOut(_APISchema):
    id: UUID
    portfolio_id: UUID
    ticker: str
    shares: Decimal
    avg_cost: Decimal
    asset_class: AssetClass
    created_at: datetime
    updated_at: datetime


class PortfolioWithHoldingsOut(PortfolioOut):
    holdings: list[HoldingOut] = []


# ---------------------------------------------------------------------------
# Market data (prices endpoint)
# ---------------------------------------------------------------------------


class TickerMarketData(BaseModel):
    prev_close: float | None = None
    sector: str | None = None


class PortfolioPricesOut(BaseModel):
    prices: dict[str, TickerMarketData]
