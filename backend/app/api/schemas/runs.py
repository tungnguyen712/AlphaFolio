"""Request/response schemas for the run-kickoff and run-status endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.db.enums import AgentRunFlow, AgentRunStatus


class _APISchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Kickoff requests
# ---------------------------------------------------------------------------


class ResearchRunRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=200)
    mode: Literal["public", "pre_ipo"] = "public"
    lookback_days: int = Field(default=90, ge=1, le=365)
    portfolio_id: UUID | None = None
    as_of_date: date | None = None


class PortfolioRunRequest(BaseModel):
    candidate_report_ids: list[UUID] = Field(default_factory=list)
    objective: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Kickoff responses
# ---------------------------------------------------------------------------


class RunAccepted(BaseModel):
    """Returned 202 from POST /research/runs and POST /portfolios/{id}/runs.

    Client polls `GET /runs/{run_id}` until status flips to complete or failed.
    """

    run_id: UUID
    flow: AgentRunFlow
    status: AgentRunStatus


# ---------------------------------------------------------------------------
# Status responses
# ---------------------------------------------------------------------------


class RunStepOut(_APISchema):
    id: UUID
    agent_name: str
    output: dict[str, Any] | None = None
    error: str | None = None
    completed_at: datetime | None = None


class RunStatusOut(_APISchema):
    id: UUID
    flow: AgentRunFlow
    status: AgentRunStatus
    ticker: str | None
    started_at: datetime | None
    completed_at: datetime | None
    # Populated when status == COMPLETE.
    report: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    as_of_date: date | None = None
    # Populated when status == FAILED.
    error: str | None = None


# ---------------------------------------------------------------------------
# SSE streaming events (GET /runs/{id}/stream)
# ---------------------------------------------------------------------------


class RunEventOut(BaseModel):
    """One SSE event emitted on GET /runs/{id}/stream.

    `type` discriminates the event kind:
      - "status"  : run transitioned to "running"
      - "step"    : one agent node completed
      - "done"    : terminal event; client should close the stream
    """

    type: Literal["status", "step", "done"]
    status: str | None = None
    agent_name: str | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    completed_at: str | None = None
