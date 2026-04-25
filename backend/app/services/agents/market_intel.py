"""Market Intelligence agent (Sonnet tier).

Hits Tavily for news + Polygon stub for analyst changes/macro context, then
asks Sonnet to distill everything into a 2-3 sentence narrative the Synthesis
agent can quote.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.models.agents import (
    AnalystChange,
    MacroContext,
    MarketIntelInput,
    MarketIntelOutput,
    NewsItem,
)
from app.services.data_providers import polygon_stub, tavily
from app.services.data_providers.polygon_stub import PolygonFixtureMissingError
from app.services.llm.anthropic_client import AgentTier, call_structured

SYSTEM_PROMPT = """You are the Market Intelligence agent for a stock research system.

You will receive a bundle of recent news headlines, analyst rating changes, and
a macro context snapshot for a single ticker. Produce a tight 2-3 sentence
narrative that a portfolio manager could read in under 20 seconds. Focus on
what is *new* and what actually moves the thesis. Do not restate every
headline. Do not hedge with "may" / "could" when the data is concrete.

You must call the record_output tool with the required fields filled in."""


class _NarrativeOnly(BaseModel):
    """Internal LLM-output shape — we already have structured news/analyst/macro,
    and only ask the LLM for the narrative summary on top."""

    narrative_summary: str = Field(max_length=1200)


async def run(inputs: MarketIntelInput) -> MarketIntelOutput:
    ticker = inputs.ticker
    news_bundle = await tavily.fetch_news(
        ticker, lookback_days=inputs.lookback_days, mode=inputs.mode
    )
    polygon_bundle = await _safe_polygon(ticker)

    news_items = [NewsItem.model_validate(n) for n in news_bundle.get("news_items", [])]
    analyst_changes = [
        AnalystChange.model_validate(a) for a in polygon_bundle.get("analyst_changes", [])
    ]
    macro = MacroContext.model_validate(polygon_bundle.get("macro_context") or {})

    user_prompt = _build_user_prompt(ticker, news_items, analyst_changes, macro)
    narrative = await call_structured(
        tier=AgentTier.SONNET,
        system=SYSTEM_PROMPT,
        user=user_prompt,
        output_model=_NarrativeOnly,
        max_tokens=800,
    )

    return MarketIntelOutput(
        ticker=ticker,
        news_items=news_items,
        analyst_changes=analyst_changes,
        macro_context=macro,
        narrative_summary=narrative.narrative_summary,
    )


def _build_user_prompt(
    ticker: str,
    news: list[NewsItem],
    analyst: list[AnalystChange],
    macro: MacroContext,
) -> str:
    payload = {
        "ticker": ticker,
        "news_items": [n.model_dump(mode="json") for n in news],
        "analyst_changes": [a.model_dump(mode="json") for a in analyst],
        "macro_context": macro.model_dump(mode="json"),
    }
    return (
        "Summarize the current market picture for the ticker below. Call the "
        "record_output tool with a 2-3 sentence narrative_summary.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )


async def _safe_polygon(ticker: str) -> dict[str, Any]:
    try:
        return await polygon_stub.fetch_market_intel(ticker)
    except PolygonFixtureMissingError:
        return {}
