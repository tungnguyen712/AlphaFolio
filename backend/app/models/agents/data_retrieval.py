"""Data Retrieval agent I/O (Haiku).

Rigid extraction: calls the data-provider layer, normalizes dicts into typed
Pydantic objects, drops nothing silently. No reasoning — that's Signal
Analysis's job.
"""
from __future__ import annotations

from app.models.agents.common import (
    AgentModel,
    CongressTrade,
    InsiderTransaction,
    PriceSummary,
    VolumeAnomaly,
)


class DataRetrievalInput(AgentModel):
    ticker: str
    lookback_days: int = 90


class RiskFactorsExcerpt(AgentModel):
    text: str
    filing_url: str | None = None
    filed_at: str | None = None


class DataRetrievalOutput(AgentModel):
    ticker: str
    lookback_days: int
    insider_filings: list[InsiderTransaction]
    congress_trades: list[CongressTrade]
    price_summary: PriceSummary | None
    volume_anomalies: list[VolumeAnomaly]
    risk_factors: RiskFactorsExcerpt
