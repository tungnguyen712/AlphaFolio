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
import logging
from datetime import date
from typing import Any

from app.config import get_settings
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
from app.services.data_providers import polygon_prices, polygon_stub, quiver_stub, sec_edgar, yahoo_prices
from app.services.data_providers import yahoo_consensus
from app.services.data_providers.polygon_stub import PolygonFixtureMissingError
from app.services.data_providers.sec_edgar import (
    aggregate_insider_transactions,
    fetch_10k_excerpts_as_of,
    fetch_8k_events,
    fetch_financial_facts,
)
from app.models.agents.common import ConsensusData, FinancialFacts, MaterialEvent, QuarterlySnapshot

logger = logging.getLogger(__name__)


async def run(inputs: DataRetrievalInput) -> DataRetrievalOutput:
    if inputs.mode == "pre_ipo":
        return await _run_pre_ipo(inputs)
    return await _run_public(inputs)


async def _empty_congress() -> list:
    return []


async def _safe_8k_events(
    ticker: str, lookback: int, as_of: date | None
) -> dict[str, Any]:
    try:
        return await fetch_8k_events(ticker, lookback_days=lookback, as_of_date=as_of)
    except Exception:
        logger.warning("data_retrieval: 8-K event fetch failed for %s", ticker)
        return {"events": []}


async def _safe_financial_facts(ticker: str, as_of: date | None) -> dict[str, Any]:
    try:
        return await fetch_financial_facts(ticker, as_of_date=as_of)
    except Exception:
        logger.exception("data_retrieval: XBRL facts fetch failed for %s", ticker)
        return {"entity_name": ticker, "quarters": [], "source": "sec_edgar_xbrl"}


async def _safe_form4(ticker: str, lookback: int) -> dict[str, Any]:
    try:
        return await sec_edgar.fetch_form4_transactions(ticker, lookback_days=lookback)
    except LookupError:
        return {"insider_filings": []}


async def _safe_10k(ticker: str, as_of: date | None = None) -> dict[str, Any]:
    """Fetch 10-K excerpts, returning empty on any ticker-resolution failure.

    When as_of is set, uses fetch_10k_excerpts_as_of to avoid look-ahead bias
    (only returns filings available on or before that date).
    """
    try:
        if as_of is not None:
            return await fetch_10k_excerpts_as_of(ticker, as_of)
        return await sec_edgar.fetch_10k_excerpts(ticker)
    except LookupError:
        return {"risk_factors_excerpt": "", "filing_url": "", "filed_at": ""}


async def _safe_consensus(ticker: str, as_of: date | None) -> ConsensusData | None:
    """Fetch analyst consensus. Always returns None in historical mode because
    yahooquery has no point-in-time endpoint — surfacing today's consensus
    for a past research date would introduce look-ahead bias."""
    if as_of is not None:
        logger.debug("data_retrieval: skipping consensus for historical run (%s as_of %s)", ticker, as_of)
        return None
    return await yahoo_consensus.fetch_consensus(ticker)


# ---------------------------------------------------------------------------
# Public branch
# ---------------------------------------------------------------------------


async def _run_public(inputs: DataRetrievalInput) -> DataRetrievalOutput:
    ticker = inputs.ticker
    lookback = inputs.lookback_days
    as_of = inputs.as_of_date

    form4_task = _safe_form4(ticker, lookback)
    tenk_task = _safe_10k(ticker, as_of)
    events_task = _safe_8k_events(ticker, lookback, as_of)
    facts_task = _safe_financial_facts(ticker, as_of)
    consensus_task = asyncio.create_task(_safe_consensus(ticker, as_of))
    # Quiver stub is fixture-based (not date-aware) — skip in historical mode to
    # avoid injecting future congressional trades into a point-in-time analysis.
    congress_task = (
        _empty_congress() if as_of is not None else quiver_stub.fetch_congress_trades(ticker)
    )

    if as_of is not None:
        # Historical mode: fetch price data as of the specified date via yfinance.
        # Skip Polygon stub/live since it only returns current prices.
        price_task = _safe_price_as_of(ticker, as_of)
        form4, tenk, events_raw, facts_raw, congress, price_summary, consensus = await asyncio.gather(
            form4_task, tenk_task, events_task, facts_task, congress_task, price_task, consensus_task
        )
        polygon: dict[str, Any] = {}
    else:
        polygon_task = _safe_polygon(ticker)
        form4, tenk, events_raw, facts_raw, congress, polygon, consensus = await asyncio.gather(
            form4_task, tenk_task, events_task, facts_task, congress_task, polygon_task, consensus_task
        )
        price_summary = _price_summary(polygon)
        # Supplement with valuation fields from yfinance (market_cap, forward_pe, ev_revenue, 52w range)
        if price_summary is not None:
            price_summary = await _supplement_price_summary(ticker, price_summary)

    volume_anomalies = [
        VolumeAnomaly.model_validate(v) for v in polygon.get("volume_anomalies", [])
    ]

    # Historical mode: filter insider filings to those filed on or before as_of_date.
    raw_filings = [InsiderTransaction.model_validate(t) for t in form4["insider_filings"]]
    if as_of is not None:
        insider_filings = [f for f in raw_filings if f.filed_at <= as_of]
    else:
        insider_filings = raw_filings
    insider_summary = aggregate_insider_transactions(insider_filings)

    material_events = [
        MaterialEvent.model_validate(e) for e in events_raw.get("events", [])
    ]

    financial_facts: FinancialFacts | None = None
    raw_quarters = facts_raw.get("quarters", [])
    if raw_quarters:
        financial_facts = FinancialFacts(
            entity_name=facts_raw.get("entity_name", ticker),
            quarters=[QuarterlySnapshot.model_validate(q) for q in raw_quarters],
            source=facts_raw.get("source", "sec_edgar_xbrl"),
        )

    return DataRetrievalOutput(
        ticker=ticker,
        mode="public",
        lookback_days=lookback,
        insider_filings=insider_filings,
        congress_trades=[CongressTrade.model_validate(t) for t in congress],
        price_summary=price_summary,
        volume_anomalies=volume_anomalies,
        risk_factors=RiskFactorsExcerpt(
            text=tenk.get("risk_factors_excerpt", ""),
            filing_url=tenk.get("filing_url") or None,
            filed_at=tenk.get("filed_at") or None,
        ),
        business_overview=None,
        insider_summary=insider_summary,
        material_events=material_events,
        financial_facts=financial_facts,
        consensus=consensus,
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


async def _safe_price_as_of(ticker: str, as_of: date) -> PriceSummary | None:
    """Fetch historical PriceSummary as of a specific date via yfinance."""
    try:
        return await yahoo_prices.fetch_price_as_of(ticker, as_of)
    except Exception:
        logger.warning("data_retrieval: historical price fetch failed for %s as of %s", ticker, as_of)
        return None


async def _safe_polygon(ticker: str) -> dict[str, Any]:
    """Try fixture first; fall back to live Polygon then Yahoo when no fixture exists."""
    try:
        return await polygon_stub.fetch_market_intel(ticker)
    except PolygonFixtureMissingError:
        pass

    # No fixture — fetch live prev-close so price_summary.latest is populated.
    settings = get_settings()
    price: float | None = None

    if settings.polygon_api_key:
        prices = await polygon_prices.fetch_prev_close_batch([ticker], settings.polygon_api_key)
        price = prices.get(ticker)

    if price is None:
        prices = await yahoo_prices.fetch_prev_close_batch([ticker])
        price = prices.get(ticker)

    if price is not None:
        return {"price_series": {"latest": price}}
    return {}


def _price_summary(polygon: dict[str, Any]) -> PriceSummary | None:
    raw = polygon.get("price_series")
    if not raw:
        return None
    ps = PriceSummary.model_validate(raw)
    missing = [
        f for f in ("high_52w", "low_52w", "market_cap", "forward_pe", "ev_revenue")
        if getattr(ps, f, None) is None
    ]
    return ps.model_copy(update={"missing_fields": missing, "retrieved_at": date.today()})


async def _supplement_price_summary(ticker: str, ps: PriceSummary) -> PriceSummary:
    """Fetch missing valuation and 52w fields from yfinance and merge into ps.

    This is best-effort: if yfinance fails, returns the original ps unchanged.
    """
    loop = asyncio.get_event_loop()
    try:
        enriched = await loop.run_in_executor(None, _yf_enrich_price_summary, ticker, ps)
        return enriched
    except Exception:
        logger.debug("data_retrieval: yfinance enrichment failed for %s", ticker)
        return ps


def _yf_enrich_price_summary(ticker: str, ps: PriceSummary) -> PriceSummary:
    """Sync worker: fetches yfinance .info + 400-day history and merges into ps."""
    import yfinance as yf
    from datetime import timedelta

    t = yf.Ticker(ticker)

    # Valuation fields
    market_cap = ps.market_cap
    forward_pe = ps.forward_pe
    ev_revenue = ps.ev_revenue
    try:
        info = t.info or {}
        if market_cap is None:
            v = info.get("marketCap")
            market_cap = float(v) if v is not None else None
        if forward_pe is None:
            v = info.get("forwardPE")
            forward_pe = float(v) if v is not None else None
        if ev_revenue is None:
            v = info.get("enterpriseToRevenue")
            ev_revenue = float(v) if v is not None else None
    except Exception:
        pass

    # 52-week high/low from 400-day history
    high_52w = ps.high_52w
    low_52w = ps.low_52w
    volume = ps.volume
    if high_52w is None or low_52w is None:
        try:
            today = date.today()
            hist = t.history(
                start=str(today - timedelta(days=400)),
                end=str(today + timedelta(days=1)),
                auto_adjust=True,
            )
            if not hist.empty:
                if high_52w is None and "High" in hist.columns:
                    high_52w = float(hist["High"].max())
                if low_52w is None and "Low" in hist.columns:
                    low_52w = float(hist["Low"].min())
                if volume is None and "Volume" in hist.columns:
                    volume = int(hist["Volume"].iloc[-1])
        except Exception:
            pass

    missing = [
        f for f, v in [
            ("market_cap", market_cap),
            ("forward_pe", forward_pe),
            ("ev_revenue", ev_revenue),
            ("high_52w", high_52w),
            ("low_52w", low_52w),
        ] if v is None
    ]

    return ps.model_copy(update={
        "market_cap": market_cap,
        "forward_pe": forward_pe,
        "ev_revenue": ev_revenue,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "volume": volume,
        "missing_fields": missing,
    })
