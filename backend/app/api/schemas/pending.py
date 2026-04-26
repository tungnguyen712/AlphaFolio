"""Request/response schemas for pending position endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.db.enums import AssetClass, PendingPositionStatus


class PendingPositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    ticker: str
    target_pct: Decimal
    source_report_id: UUID | None
    status: PendingPositionStatus
    created_at: datetime
    updated_at: datetime


class CreatePendingBody(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    target_pct: Decimal = Field(gt=0, le=1)
    source_report_id: UUID | None = None


class AcceptPendingBody(BaseModel):
    shares: Decimal = Field(gt=0)
    avg_cost: Decimal = Field(ge=0)
    asset_class: AssetClass = AssetClass.ESTABLISHED
