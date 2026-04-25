"""Response schemas for research-report endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.db.enums import ResearchSignal


class _APISchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ResearchReportSummary(_APISchema):
    """Light response — for list endpoints. Skip the full report_json blob."""

    id: UUID
    run_id: UUID | None
    portfolio_id: UUID | None
    ticker: str
    signal: ResearchSignal
    confidence: float
    created_at: datetime


class ResearchReportOut(ResearchReportSummary):
    """Full report. `report` is the persisted SynthesisOutput dict — frontend
    types it as the same shape as the agent's output schema."""

    report: dict[str, Any]
