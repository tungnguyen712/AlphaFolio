"""Request/response schemas for rebalance trigger endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.db.enums import RebalanceTriggerKind


class TriggerCreate(BaseModel):
    kind: RebalanceTriggerKind
    condition_json: dict[str, Any] = {}
    fires_at: datetime | None = None


class TriggerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID | None
    kind: RebalanceTriggerKind
    condition_json: dict[str, Any]
    fires_at: datetime | None
    last_evaluated_at: datetime | None
    active: bool
    created_at: datetime
    updated_at: datetime
