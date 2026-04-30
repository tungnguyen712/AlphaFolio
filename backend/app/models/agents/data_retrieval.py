"""Data Retrieval agent I/O (Haiku).

Rigid extraction: calls the data-provider layer, normalizes dicts into typed
Pydantic objects, drops nothing silently. No reasoning — that's Signal
Analysis's job.

`mode` selects between public (ticker-backed: Form 4 + 10-K + Polygon +
Quiver + Tavily) and pre_ipo (S-1-backed: Risk Factors + Business Overview +
Tavily, no Form 4 / 10-K since the company isn't filing yet). In pre_ipo
mode the `ticker` field carries the company name string — downstream agents
read `mode` to know how to interpret it.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from app.models.agents.common import (
    AgentModel,
    CongressTrade,
    FinancialFacts,
    FormDFiling,
    InsiderSummary,
    InsiderTransaction,
    MaterialEvent,
    PriceSummary,
    VolumeAnomaly,
)

RetrievalMode = Literal["public", "pre_ipo"]


class DataRetrievalInput(AgentModel):
    ticker: str
    mode: RetrievalMode = "public"
    lookback_days: int = 90
    as_of_date: date | None = None


class RiskFactorsExcerpt(AgentModel):
    """Flow-agnostic risk-factors block. Source is 10-K Item 1A in public mode,
    S-1 Risk Factors section in pre_ipo mode."""

    text: str
    filing_url: str | None = None
    filed_at: str | None = None


class BusinessOverviewExcerpt(AgentModel):
    """Prospectus summary / business overview from the S-1. Populated in
    pre_ipo mode only — public mode has segment data from other sources."""

    text: str
    filing_url: str | None = None
    filed_at: str | None = None


class DataRetrievalOutput(AgentModel):
    ticker: str
    mode: RetrievalMode = "public"
    lookback_days: int
    insider_filings: list[InsiderTransaction]
    congress_trades: list[CongressTrade]
    price_summary: PriceSummary | None
    volume_anomalies: list[VolumeAnomaly]
    risk_factors: RiskFactorsExcerpt
    business_overview: BusinessOverviewExcerpt | None = None
    form_d_filings: list[FormDFiling] = []
    insider_summary: InsiderSummary | None = None
    material_events: list[MaterialEvent] = []
    financial_facts: FinancialFacts | None = None
