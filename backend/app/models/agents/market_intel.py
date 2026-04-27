"""Market Intelligence agent I/O (Sonnet).

Wraps Tavily news + Polygon macro context, summarizes into a structured
narrative the Synthesis agent can quote from.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.agents.common import (
    AgentModel,
    AnalystChange,
    FilteredNewsItem,
    MacroContext,
    NewsItem,
)
from app.models.agents.data_retrieval import RetrievalMode


class MarketIntelInput(AgentModel):
    ticker: str
    mode: RetrievalMode = "public"
    lookback_days: int = 90


class MarketIntelOutput(AgentModel):
    ticker: str
    news_items: list[NewsItem]
    analyst_changes: list[AnalystChange]
    macro_context: MacroContext
    narrative_summary: str
    filtered_out_news: list[FilteredNewsItem] = Field(default_factory=list)
    analyst_signal_source: Literal["structured", "news_reported_analyst_signal"] = "structured"
    news_filter_summary: str | None = None
