"""Data Retrieval agent (Haiku tier).

Currently procedural: fans out provider calls in parallel and normalizes the
dicts into typed Pydantic objects. Parsing already happens in the providers
(SEC XML, Polygon JSON); there's no text extraction step left that needs an
LLM.

Haiku tier is reserved for when we add semi-structured extraction here — e.g.
pulling management-commentary bullet points out of a 10-K's MD&A section.
Until then, no Anthropic call is made.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.models.agents import (
    CongressTrade,
    DataRetrievalInput,
    DataRetrievalOutput,
    InsiderTransaction,
    PriceSummary,
    RiskFactorsExcerpt,
    VolumeAnomaly,
)
from app.services.data_providers import polygon_stub, quiver_stub, sec_edgar
from app.services.data_providers.polygon_stub import PolygonFixtureMissingError


async def run(inputs: DataRetrievalInput) -> DataRetrievalOutput:
    ticker = inputs.ticker
    lookback = inputs.lookback_days

    form4_task = sec_edgar.fetch_form4_transactions(ticker, lookback_days=lookback)
    tenk_task = sec_edgar.fetch_10k_excerpts(ticker)
    congress_task = quiver_stub.fetch_congress_trades(ticker)
    polygon_task = _safe_polygon(ticker)

    form4, tenk, congress, polygon = await asyncio.gather(
        form4_task, tenk_task, congress_task, polygon_task
    )

    price_summary = _price_summary(polygon)
    volume_anomalies = [
        VolumeAnomaly.model_validate(v) for v in polygon.get("volume_anomalies", [])
    ]

    return DataRetrievalOutput(
        ticker=ticker,
        lookback_days=lookback,
        insider_filings=[InsiderTransaction.model_validate(t) for t in form4["insider_filings"]],
        congress_trades=[CongressTrade.model_validate(t) for t in congress],
        price_summary=price_summary,
        volume_anomalies=volume_anomalies,
        risk_factors=RiskFactorsExcerpt(
            text=tenk.get("risk_factors_excerpt", ""),
            filing_url=tenk.get("filing_url") or None,
            filed_at=tenk.get("filed_at") or None,
        ),
    )


async def _safe_polygon(ticker: str) -> dict[str, Any]:
    """Missing Polygon fixture is legitimate during dev; return an empty shape instead of blowing up."""
    try:
        return await polygon_stub.fetch_market_intel(ticker)
    except PolygonFixtureMissingError:
        return {}


def _price_summary(polygon: dict[str, Any]) -> PriceSummary | None:
    raw = polygon.get("price_series")
    if not raw:
        return None
    return PriceSummary.model_validate(raw)
