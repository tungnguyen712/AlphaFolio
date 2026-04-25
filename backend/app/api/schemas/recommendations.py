"""Response schemas for portfolio recommendation endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PortfolioRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID | None
    portfolio_id: UUID
    recommendation: dict[str, Any]
    created_at: datetime
