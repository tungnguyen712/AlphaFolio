"""Wikidata SPARQL client for corporate relationship data.

Queries the public Wikidata SPARQL endpoint for structural company
relationships: subsidiaries (P355), parent organizations (P749).

No API key required. Wikidata allows reasonable query volume with a
descriptive User-Agent per Wikimedia bot policy. We set one derived
from the existing SEC EDGAR user agent setting.

Data quality: excellent for well-known public companies (NVDA, AAPL, TSMC),
sparse for mid-cap and small-cap. Customer/supplier relationships are
rarely in Wikidata — those come from 10-K extraction. This source
is primarily useful for corporate structure (subsidiaries, parent org).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.services.data_providers._cache import (
    cached_fetch,
    make_cache_key,
)

_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

_QID_TTL = 30 * 24 * 60 * 60        # 30 days — QIDs are stable identifiers
_RELATIONS_TTL = 30 * 24 * 60 * 60  # 30 days — corporate structure changes rarely

# Wikidata SPARQL is free; no rate limiter needed for low-volume lookups.
# Wikimedia asks for a descriptive User-Agent and reasonable cadence.

_COMPANY_HINTS = frozenset((
    "company", "corporation", "technology", "semiconductor",
    "manufacturer", "enterprise", "inc", "ltd", "corp", "american",
    "multinational", "conglomerate",
))


def _ua() -> str:
    settings = get_settings()
    email = settings.sec_edgar_user_agent.split()[-1]
    return f"AlphaFolio/1.0 ({email})"


def _sparql_headers() -> dict[str, str]:
    return {
        "User-Agent": _ua(),
        "Accept": "application/sparql-results+json",
    }


# --------------------------------------------------------------------------
# QID resolution: company name → Wikidata entity ID
# --------------------------------------------------------------------------


def _qid_key(company_name: str) -> str:
    return make_cache_key("wikidata.qid", name=company_name.strip().upper())


@cached_fetch(key_fn=_qid_key, ttl_seconds=_QID_TTL)
async def _resolve_qid(company_name: str) -> dict[str, Any]:
    """Return {'qid': 'Q182477', 'label': 'Nvidia'} or raise LookupError."""
    params = {
        "action": "wbsearchentities",
        "search": company_name,
        "language": "en",
        "format": "json",
        "type": "item",
        "limit": "5",
    }
    async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": _ua()}) as client:
        resp = await client.get(_WIKIDATA_API, params=params)
        resp.raise_for_status()
        data = resp.json()

    hits = data.get("search", [])
    if not hits:
        raise LookupError(f"No Wikidata entity found for {company_name!r}")

    # Prefer hits whose description mentions business/company context to avoid
    # resolving "Apple" → fruit rather than Apple Inc.
    for hit in hits:
        desc = (hit.get("description") or "").lower()
        if any(h in desc for h in _COMPANY_HINTS):
            return {"qid": hit["id"], "label": hit.get("label", company_name)}

    return {"qid": hits[0]["id"], "label": hits[0].get("label", company_name)}


# --------------------------------------------------------------------------
# SPARQL relationship query
# --------------------------------------------------------------------------


def _relations_key(company_name: str) -> str:
    return make_cache_key("wikidata.relations.v2", name=company_name.strip().upper())


@cached_fetch(key_fn=_relations_key, ttl_seconds=_RELATIONS_TTL)
async def fetch_wikidata_relationships(company_name: str) -> dict[str, Any]:
    """Return {'entities': [{'name', 'qid', 'ticker', 'relationship'}]}.

    Queries for:
    - Direct subsidiaries: target wdt:P355 ?sub
    - Reverse subsidiaries: ?sub wdt:P749 target  (entities whose parent is target)
    - Parent organization: target wdt:P749 ?parent

    Returns {'entities': []} on any error — supply chain data still works
    via 10-K + Tavily if Wikidata is unavailable.
    """
    try:
        qid_data = await _resolve_qid(company_name)
    except (LookupError, httpx.HTTPError):
        return {"entities": []}

    qid = qid_data["qid"]

    sparql = f"""
SELECT DISTINCT ?rel ?relLabel ?relTicker ?relType WHERE {{
  {{
    wd:{qid} wdt:P355 ?rel .
    BIND("subsidiary" AS ?relType)
  }} UNION {{
    wd:{qid} wdt:P749 ?rel .
    BIND("parent" AS ?relType)
  }} UNION {{
    ?rel wdt:P749 wd:{qid} .
    FILTER(?rel != wd:{qid})
    BIND("subsidiary" AS ?relType)
  }} UNION {{
    wd:{qid} wdt:P176 ?rel .
    BIND("manufacturer" AS ?relType)
  }}
  OPTIONAL {{ ?rel wdt:P249 ?relTicker }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 50
"""

    try:
        async with httpx.AsyncClient(timeout=25.0, headers=_sparql_headers()) as client:
            resp = await client.get(
                _WIKIDATA_SPARQL,
                params={"query": sparql.strip(), "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"entities": []}

    bindings = data.get("results", {}).get("bindings", [])
    entities: list[dict[str, Any]] = []
    seen_qids: set[str] = set()

    for b in bindings:
        rel_uri = b.get("rel", {}).get("value", "")
        rel_qid = rel_uri.rsplit("/", 1)[-1] if rel_uri else ""
        if not rel_qid or rel_qid in seen_qids:
            continue
        seen_qids.add(rel_qid)

        name = b.get("relLabel", {}).get("value", "")
        if not name or name == rel_qid:
            continue

        ticker = b.get("relTicker", {}).get("value") or None
        rel_type = b.get("relType", {}).get("value", "subsidiary")

        entities.append({
            "name": name,
            "qid": rel_qid,
            "ticker": ticker,
            "relationship": rel_type,
        })

    return {"entities": entities}
