"""Market Intelligence agent I/O (Sonnet).

Wraps Tavily news + Polygon macro context, summarizes into a structured
narrative the Synthesis agent can quote from.
"""
from __future__ import annotations

from app.models.agents.common import AgentModel, AnalystChange, MacroContext, NewsItem


class MarketIntelInput(AgentModel):
    ticker: str
    lookback_days: int = 90


class MarketIntelOutput(AgentModel):
    ticker: str
    news_items: list[NewsItem]
    analyst_changes: list[AnalystChange]
    macro_context: MacroContext
    narrative_summary: str
