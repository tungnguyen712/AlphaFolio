"""Market Intelligence agent (Sonnet tier).

Hits Tavily for news + Polygon stub for analyst changes/macro context, then
asks Sonnet to distill everything into a 2-3 sentence narrative the Synthesis
agent can quote.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.models.agents import (
    AnalystChange,
    MacroContext,
    MarketIntelInput,
    MarketIntelOutput,
    NewsItem,
)
from app.config import get_settings
from app.services.data_providers import finnhub, polygon_stub, tavily
from app.services.data_providers.news_filter import filter_news
from app.services.data_providers.polygon_stub import PolygonFixtureMissingError
from app.services.data_providers.sec_edgar import _resolve_cik
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


async def _company_name_for_filter(ticker: str) -> str | None:
    """Resolve the human-readable company name for news relevance filtering.

    Finnhub articles say 'Nvidia' not 'NVDA' — passing the clean company name
    lets filter_news match on the full name, not just the ticker symbol.
    Result is cached by _resolve_cik (24h TTL) so overhead is one fast DB read
    after the first call.
    """
    try:
        data = await _resolve_cik(ticker)
        title = data.get("title", "")
        # Strip legal suffixes so "NVIDIA CORP" → "Nvidia" matches article text
        for suffix in (
            " CORP", " INC", " CO", " LTD", " LLC", " LP", " NV", " SA",
            " PLC", " GROUP", " HOLDINGS", " PLATFORMS", " TECHNOLOGIES",
        ):
            if title.upper().endswith(suffix):
                title = title[: -len(suffix)].strip()
                break
        return title.title() or None
    except Exception:
        return None


async def run(inputs: MarketIntelInput) -> MarketIntelOutput:
    ticker = inputs.ticker
    as_of = inputs.as_of_date

    if as_of is not None:
        # Historical mode: use Finnhub date-range news instead of Tavily live search.
        settings = get_settings()
        start_date = as_of - timedelta(days=inputs.lookback_days)
        raw_news = await finnhub.fetch_historical_news(
            ticker, start_date=start_date, end_date=as_of, api_key=settings.finnhub_api_key
        )
        # Resolve full company name so filter_news can match "Nvidia" headlines for NVDA, etc.
        company_name = await _company_name_for_filter(ticker)
    else:
        news_bundle = await tavily.fetch_news(
            ticker, lookback_days=inputs.lookback_days, mode=inputs.mode
        )
        raw_news = [NewsItem.model_validate(n) for n in news_bundle.get("news_items", [])]
        company_name = None

    # Historical mode: skip the Polygon stub entirely — it is fixture-based and
    # always returns current-dated analyst changes and macro context, which would
    # inject look-ahead data into a historical run and produce timestamp collisions
    # that the LLM correctly flags as inconsistencies, tanking confidence.
    if as_of is not None:
        polygon_bundle: dict[str, Any] = {}
    else:
        polygon_bundle = await _safe_polygon(ticker)

    analyst_changes = [
        AnalystChange.model_validate(a) for a in polygon_bundle.get("analyst_changes", [])
    ]
    macro = MacroContext.model_validate(polygon_bundle.get("macro_context") or {})

    # Post-retrieval filtering: relevance + deduplication
    news_items, dropped = filter_news(
        ticker=ticker,
        items=raw_news,
        lookback_days=inputs.lookback_days,
        as_of_date=as_of,
        company_name=company_name,
    )
    reason_counts = Counter(d.reason for d in dropped)
    news_filter_summary = (
        f"Kept {len(news_items)}/{len(raw_news)} articles. "
        f"Dropped: {dict(reason_counts)}" if dropped else f"Kept all {len(news_items)} articles."
    )

    # Analyst source discipline
    analyst_signal_source = "structured" if analyst_changes else "news_reported_analyst_signal"

    user_prompt = _build_user_prompt(ticker, news_items, analyst_changes, macro)
    narrative = await call_structured(
        tier=AgentTier.SONNET,
        agent_name="market_intel",
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
        filtered_out_news=dropped,
        analyst_signal_source=analyst_signal_source,
        news_filter_summary=news_filter_summary,
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
