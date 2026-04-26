"""Data Retrieval agent (Haiku tier).

Currently procedural: fans out provider calls in parallel and normalizes the
dicts into typed Pydantic objects. Parsing already happens in the providers
(SEC XML, Polygon JSON); there's no text extraction step left that needs an
LLM.

Two branches:
  - `mode="public"`: ticker-backed — Form 4 + 10-K + Quiver + Polygon.
  - `mode="pre_ipo"`: company-name-backed — S-1 Risk Factors + Prospectus
    Summary. No Form 4 / 10-K / Quiver / Polygon since the company isn't
    public yet; those list fields come back empty and agents flag them.

Haiku tier is reserved for when we add semi-structured extraction here —
e.g. pulling management-commentary bullet points out of a 10-K's MD&A
section. Until then, no Anthropic call is made.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.models.agents import (
    BusinessOverviewExcerpt,
    CongressTrade,
    DataRetrievalInput,
    DataRetrievalOutput,
    FormDFiling,
    InsiderTransaction,
    PriceSummary,
    RiskFactorsExcerpt,
    VolumeAnomaly,
)
from app.services.data_providers import polygon_stub, quiver_stub, sec_edgar
from app.services.data_providers.polygon_stub import PolygonFixtureMissingError


async def run(inputs: DataRetrievalInput) -> DataRetrievalOutput:
    if inputs.mode == "pre_ipo":
        return await _run_pre_ipo(inputs)
    return await _run_public(inputs)


async def _safe_form4(ticker: str, lookback: int) -> dict[str, Any]:
    try:
        return await sec_edgar.fetch_form4_transactions(ticker, lookback_days=lookback)
    except LookupError:
        return {"insider_filings": []}


async def _safe_10k(ticker: str) -> dict[str, Any]:
    """Fetch 10-K excerpts, returning empty on any ticker-resolution failure.

    Falls back to an empty dict rather than crashing the whole run when the
    ticker is delisted, OTC-only, or not yet in SEC's master list.
    """
    try:
        return await sec_edgar.fetch_10k_excerpts(ticker)
    except LookupError:
        return {"risk_factors_excerpt": "", "filing_url": "", "filed_at": ""}


# ---------------------------------------------------------------------------
# Public branch
# ---------------------------------------------------------------------------


async def _run_public(inputs: DataRetrievalInput) -> DataRetrievalOutput:
    ticker = inputs.ticker
    lookback = inputs.lookback_days

    form4_task = _safe_form4(ticker, lookback)
    tenk_task = _safe_10k(ticker)
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
        mode="public",
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
        business_overview=None,
    )


# ---------------------------------------------------------------------------
# Pre-IPO branch
# ---------------------------------------------------------------------------


async def _run_pre_ipo(inputs: DataRetrievalInput) -> DataRetrievalOutput:
    """In pre_ipo mode, `inputs.ticker` carries the company name string.

    Tolerant of "no S-1 on file" (e.g. OpenAI as of 2026-04): produces a
    valid-but-empty output instead of raising. Downstream agents will flag
    the absence and Market Intel still delivers Tavily news, so research
    on a truly private company degrades to news-only rather than erroring.

    Form D filings are pulled in parallel — they're public for any company
    that's done a private securities offering (which is essentially all
    venture-backed pre-IPOs), and give the most concrete dollar-denominated
    funding-round data available for private names.
    """
    company_name = inputs.ticker
    lookback = inputs.lookback_days

    s1_task = _safe_s1(company_name)
    form_d_task = _safe_form_d(company_name)
    s1, form_d = await asyncio.gather(s1_task, form_d_task)

    risk_factors = RiskFactorsExcerpt(
        text=s1.get("risk_factors_excerpt", ""),
        filing_url=s1.get("filing_url") or None,
        filed_at=s1.get("filed_at") or None,
    )
    overview_text = s1.get("business_overview_excerpt", "")
    business_overview = (
        BusinessOverviewExcerpt(
            text=overview_text,
            filing_url=s1.get("filing_url") or None,
            filed_at=s1.get("filed_at") or None,
        )
        if overview_text
        else None
    )

    return DataRetrievalOutput(
        ticker=company_name,
        mode="pre_ipo",
        lookback_days=lookback,
        insider_filings=[],
        congress_trades=[],
        price_summary=None,
        volume_anomalies=[],
        risk_factors=risk_factors,
        business_overview=business_overview,
        form_d_filings=[FormDFiling.model_validate(f) for f in form_d],
    )


async def _safe_s1(company_name: str) -> dict[str, Any]:
    try:
        return await sec_edgar.fetch_s1_excerpts(company_name)
    except LookupError:
        return {
            "risk_factors_excerpt": "",
            "business_overview_excerpt": "",
            "filing_url": "",
            "filed_at": "",
            "form": "",
        }


async def _safe_form_d(company_name: str) -> list[dict[str, Any]]:
    """Form D is supplementary — never raise from missing-data on it."""
    try:
        result = await sec_edgar.fetch_form_d_filings(company_name)
        return list(result.get("filings", []))
    except (LookupError, Exception):  # noqa: BLE001 — supplementary path
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
