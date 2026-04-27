"""Supply chain pipeline — orchestrates Wikidata + Wikipedia + 10-K + Tavily into SupplyChainReport.

No LangGraph: four parallel async fetches then merge. The result is fast
enough to serve synchronously (<10s cold, <200ms cached).
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

from app.models.agents.supply_chain import (
    ConfidenceLevel,
    RelatedCompany,
    SupplyChainEntities,
    SupplyChainReport,
)
from app.services.data_providers._cache import (
    cache_get,
    cache_set,
    make_cache_key,
)
from app.services.data_providers.sec_edgar import (
    _resolve_cik,
    fetch_10k_item1_business,
    resolve_ticker_from_name,
)
from app.services.data_providers.tavily_supply_chain import fetch_supply_chain_data
from app.services.data_providers.wikidata import fetch_wikidata_relationships
from app.services.data_providers.wikipedia import fetch_wikipedia_text
from app.services.supply_chain.haiku_extraction import (
    extract_supply_chain_from_10k,
    extract_supply_chain_from_tavily,
    extract_supply_chain_from_wikipedia,
)

_HAIKU_CACHE_TTL = 7 * 24 * 60 * 60   # 7 days — matches 10-K document TTL
_TAVILY_HAIKU_TTL = 24 * 60 * 60      # 24 hours — matches Tavily fetch TTL
_WIKI_HAIKU_TTL = 7 * 24 * 60 * 60    # 7 days — Wikipedia text changes slowly

_LEGAL_SUFFIX_RE = re.compile(
    r"\s+(?:inc|corp|ltd|llc|co|company|group|holdings?|international|"
    r"technologies?|systems?|solutions?|services?|semiconductor|manufacturing|"
    r"corporation|incorporated|limited)\.?\s*$",
    re.IGNORECASE,
)

_ALIASES: dict[str, str] = {
    "tsmc": "taiwan semiconductor",
    "taiwan semiconductor manufacturing": "taiwan semiconductor",
    "taiwan semiconductor manufacturing company": "taiwan semiconductor",
    "samsung": "samsung electronics",
    "globalfoundries": "global foundries",
    "gf": "global foundries",
    "arm": "arm holdings",
    "asml": "asml holding",
    "foxconn": "hon hai precision",
    "apple": "apple",
}


def _normalize_name(name: str) -> str:
    name = name.strip().lower()
    name = _LEGAL_SUFFIX_RE.sub("", name).strip()
    return _ALIASES.get(name, name)


# --------------------------------------------------------------------------
# Haiku extraction with per-ticker caching
# --------------------------------------------------------------------------


async def _cached_haiku_extract(ticker: str, text: str) -> SupplyChainEntities:
    key = make_cache_key("sc.10k.haiku.v7", ticker=ticker.upper())
    cached = await cache_get(key)
    if cached is not None:
        return SupplyChainEntities.model_validate(cached)
    result = await extract_supply_chain_from_10k(text, ticker)
    await cache_set(key, result.model_dump(mode="json"), _HAIKU_CACHE_TTL)
    return result


async def _cached_tavily_extract(ticker: str, snippets: list[dict]) -> SupplyChainEntities:
    key = make_cache_key("sc.tavily.haiku.v4", ticker=ticker.upper())
    cached = await cache_get(key)
    if cached is not None:
        return SupplyChainEntities.model_validate(cached)
    result = await extract_supply_chain_from_tavily(snippets, ticker)
    await cache_set(key, result.model_dump(mode="json"), _TAVILY_HAIKU_TTL)
    return result


async def _cached_wiki_extract(ticker: str, text: str) -> SupplyChainEntities:
    key = make_cache_key("sc.wiki.haiku.v1", ticker=ticker.upper())
    cached = await cache_get(key)
    if cached is not None:
        return SupplyChainEntities.model_validate(cached)
    result = await extract_supply_chain_from_wikipedia(text, ticker)
    await cache_set(key, result.model_dump(mode="json"), _WIKI_HAIKU_TTL)
    return result


# --------------------------------------------------------------------------
# Safe (non-raising) wrappers for each source
# --------------------------------------------------------------------------


async def _safe_wikidata(company_name: str) -> list[RelatedCompany]:
    try:
        data = await fetch_wikidata_relationships(company_name)
        rels: list[RelatedCompany] = []
        for e in data.get("entities", []):
            rel_type = e.get("relationship", "subsidiary")
            if rel_type not in ("supplier", "customer", "subsidiary", "parent", "manufacturer"):
                continue
            rels.append(
                RelatedCompany(
                    name=e["name"],
                    ticker=e.get("ticker") or None,
                    relationship=rel_type,
                    confidence="high",
                    sources=["wikidata"],
                )
            )
        return rels
    except Exception:
        return []


async def _safe_10k(ticker: str) -> tuple[list[RelatedCompany], str | None, str | None]:
    """Returns (relationships, filing_url, filed_at). Never raises."""
    try:
        raw = await fetch_10k_item1_business(ticker)
        text = raw.get("business_excerpt", "")
        filing_url = raw.get("filing_url") or None
        filed_at = raw.get("filed_at") or None
        if not text:
            logger.warning("10-K Item1 empty for %s filing_url=%s", ticker, filing_url)
            return [], filing_url, filed_at
        entities = await _cached_haiku_extract(ticker, text)
        rels: list[RelatedCompany] = []
        for e in entities.entities:
            confidence: ConfidenceLevel = "high" if e.is_significant else "medium"
            rels.append(
                RelatedCompany(
                    name=e.name,
                    relationship=e.relationship,
                    confidence=confidence,
                    sources=["10k"],
                    evidence_snippet=e.evidence_snippet[:200] if e.evidence_snippet else None,
                )
            )
        return rels, filing_url, filed_at
    except Exception as exc:
        logger.warning("10-K supply chain failed for %s: %s", ticker, exc, exc_info=True)
        return [], None, None


async def _safe_wikipedia(company_name: str, ticker: str) -> list[RelatedCompany]:
    """Fetch Wikipedia article and extract supply chain relationships via Haiku.

    Normalizes the SEC company name (strips "INC", "CORP") before searching
    so Wikipedia's search API finds the right article.
    """
    try:
        search_name = _normalize_name(company_name).title()  # "NETFLIX INC" → "Netflix"
        data = await fetch_wikipedia_text(search_name)
        text = data.get("wikipedia_text", "")
        if not text:
            logger.warning("Wikipedia: no article found for %s (%s)", ticker, search_name)
            return []
        entities = await _cached_wiki_extract(ticker, text)
        rels: list[RelatedCompany] = []
        for e in entities.entities:
            if e.relationship not in ("supplier", "customer", "manufacturer", "subsidiary", "parent"):
                continue
            rels.append(
                RelatedCompany(
                    name=e.name,
                    relationship=e.relationship,
                    confidence="medium",  # Wikipedia: accurate but not a primary source
                    sources=["wikipedia"],
                    evidence_snippet=e.evidence_snippet[:200] if e.evidence_snippet else None,
                )
            )
        return rels
    except Exception as exc:
        logger.warning("Wikipedia supply chain failed for %s: %s", ticker, exc, exc_info=True)
        return []


async def _safe_tavily(ticker: str) -> list[RelatedCompany]:
    """Fetch Tavily supply chain snippets and extract entities via Haiku."""
    try:
        data = await fetch_supply_chain_data(ticker)
        snippets = data.get("snippets", [])
        if not snippets:
            return []
        entities = await _cached_tavily_extract(ticker, snippets)
        rels: list[RelatedCompany] = []
        for e in entities.entities:
            if e.relationship not in ("supplier", "customer", "manufacturer"):
                continue
            rels.append(
                RelatedCompany(
                    name=e.name,
                    relationship=e.relationship,
                    confidence="low",  # news-reported, not primary source
                    sources=["tavily"],
                    evidence_snippet=e.evidence_snippet[:200] if e.evidence_snippet else None,
                )
            )
        return rels
    except Exception as exc:
        logger.warning("Tavily supply chain failed for %s: %s", ticker, exc, exc_info=True)
        return []


# --------------------------------------------------------------------------
# Merge and deduplicate
# --------------------------------------------------------------------------


def _merge_and_deduplicate(
    wikidata_rels: list[RelatedCompany],
    wiki_rels: list[RelatedCompany],
    tenk_rels: list[RelatedCompany],
    tavily_rels: list[RelatedCompany],
) -> list[RelatedCompany]:
    """Merge four sources with priority: wikidata > wikipedia > 10k > tavily.

    Dedup key: (normalized_name, relationship). On collision, keep the
    higher-priority entry's fields but merge the sources list.
    """
    seen: dict[tuple[str, str], tuple[int, RelatedCompany]] = {}

    for priority, rels in (
        (0, wikidata_rels),
        (1, wiki_rels),
        (2, tenk_rels),
        (3, tavily_rels),
    ):
        for rel in rels:
            key = (_normalize_name(rel.name), rel.relationship)
            existing_priority, existing_rel = seen.get(key, (999, None))  # type: ignore[assignment]
            if existing_rel is None:
                seen[key] = (priority, rel)
            elif priority < existing_priority:
                merged_sources = list(set(existing_rel.sources + rel.sources))
                seen[key] = (priority, rel.model_copy(update={"sources": merged_sources}))
            else:
                merged_sources = list(set(existing_rel.sources + rel.sources))
                seen[key] = (existing_priority, existing_rel.model_copy(update={"sources": merged_sources}))

    return [rel for _, rel in seen.values()]


# --------------------------------------------------------------------------
# Ticker resolution
# --------------------------------------------------------------------------


async def _try_resolve_ticker(name: str) -> str | None:
    try:
        result = await resolve_ticker_from_name(name)
        return result["ticker"]
    except Exception:
        return None


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------


async def run_supply_chain(ticker: str) -> SupplyChainReport:
    """Orchestrate Wikidata + Wikipedia + 10-K + Tavily → SupplyChainReport."""
    upper = ticker.upper()

    try:
        cik_data = await _resolve_cik(upper)
        company_name = cik_data.get("title", upper)
    except LookupError:
        company_name = upper

    tenk_result, wikidata_rels, wiki_rels, tavily_rels = await asyncio.gather(
        _safe_10k(upper),
        _safe_wikidata(company_name),
        _safe_wikipedia(company_name, upper),
        _safe_tavily(upper),
    )

    tenk_rels, filing_url, filed_at = tenk_result

    all_rels = _merge_and_deduplicate(wikidata_rels, wiki_rels, tenk_rels, tavily_rels)

    # Attempt ticker resolution for up to 5 high/medium confidence entries without tickers.
    unresolved = [r for r in all_rels if r.confidence in ("high", "medium") and not r.ticker][:5]
    if unresolved:
        resolved = await asyncio.gather(*[_try_resolve_ticker(r.name) for r in unresolved])
        name_to_ticker = {r.name: t for r, t in zip(unresolved, resolved) if t}
        all_rels = [
            r.model_copy(update={
                "ticker": name_to_ticker[r.name],
                "research_url": f"/research?ticker={name_to_ticker[r.name]}",
            }) if r.name in name_to_ticker else r
            for r in all_rels
        ]

    # Set research_url for entries that already had a ticker (from Wikidata).
    all_rels = [
        r.model_copy(update={"research_url": f"/research?ticker={r.ticker}"})
        if r.ticker and not r.research_url else r
        for r in all_rels
    ]

    data_sources: list[str] = []
    if wikidata_rels:
        data_sources.append("wikidata")
    if wiki_rels:
        data_sources.append("wikipedia")
    if tenk_rels:
        data_sources.append("10k")
    if tavily_rels:
        data_sources.append("tavily")

    return SupplyChainReport(
        ticker=upper,
        company_name=company_name,
        generated_at=datetime.now(UTC).isoformat(),
        relationships=all_rels[:50],
        filing_url=filing_url,
        filed_at=filed_at,
        data_sources_used=data_sources,
    )
