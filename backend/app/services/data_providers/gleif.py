"""GLEIF (Global Legal Entity Identifier Foundation) client for corporate structure.

Uses the public GLEIF REST API (no auth, free). Returns parent and subsidiary
relationships derived from the LEI hierarchy.

LEI = Legal Entity Identifier — a 20-character alphanumeric code assigned to every
financial entity globally by regulation.  The parent/child hierarchy is submitted
by each entity and validated by local operating units (LOUs), making it the most
reliable source for corporate structure data — especially for non-US companies
(TSMC, ASML) that have sparse Wikidata entries.

Coverage: all publicly regulated entities worldwide.  Excellent for large-caps.
Cache TTL: 30 days — LEI hierarchy changes only on M&A events.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from app.config import get_settings
from app.services.data_providers._cache import (
    AsyncRateLimiter,
    cached_fetch,
    make_cache_key,
)

_GLEIF_BASE = "https://api.gleif.org/api/v1"
_TTL = 30 * 24 * 60 * 60  # 30 days
_MAX_CHILDREN = 20

# Common legal suffixes to strip when comparing names for match quality.
_LEGAL_SUFFIXES = frozenset(
    "inc corp ltd llc plc nv sa ag co the and limited company holding "
    "group international holdings corporation".split()
)

# Regex for stripping trailing legal suffixes from the search query so that
# GLEIF's fulltext index ranks the canonical holding company first.
# e.g. "ASML HOLDING NV" → "ASML HOLDING" → returns "ASML Holding N.V." at rank 1
_QUERY_SUFFIX_RE = re.compile(
    r"\s+(?:INC|CORP|LTD|LLC|CO|NV|PLC|AG|SA|BV|KK|COMPANY|GROUP|"
    r"HOLDINGS?|INTERNATIONAL|CORPORATION|INCORPORATED|LIMITED)\.?\s*$",
    re.IGNORECASE,
)

# GLEIF has no hard rate limit but polite behaviour is required.
# 0.5 rps gives plenty of headroom for low-volume lookups.
_rate_limiter = AsyncRateLimiter(rps=0.5)


def _ua() -> str:
    settings = get_settings()
    email = settings.sec_edgar_user_agent.split()[-1]
    return f"AlphaFolio/1.0 ({email})"


def _gleif_key(company_name: str) -> str:
    return make_cache_key("gleif.relations.v3", name=company_name.strip().upper())


def _strip_query(company_name: str) -> str:
    """Strip ONE trailing legal suffix to improve GLEIF fulltext ranking.

    Only one pass so we don't over-strip: "ASML HOLDING NV" → "ASML HOLDING"
    (not all the way to "ASML").  GLEIF's index then surfaces "ASML Holding N.V."
    at rank 1 instead of an ADR instrument or subsidiary.
    """
    name = company_name.strip()
    reduced = _QUERY_SUFFIX_RE.sub("", name).strip()
    return reduced if reduced else name


def _tokenize(name: str) -> set[str]:
    """Normalize name to lowercase alphanum tokens, strip legal suffixes."""
    tokens = set(re.sub(r"[^a-z0-9 ]", "", name.lower()).split())
    return tokens - _LEGAL_SUFFIXES


def _is_good_match(query: str, legal_name: str, threshold: float = 0.4) -> bool:
    """Jaccard similarity of core tokens must meet threshold.

    Prevents false positives like "TSMC" → "TSMC PRODUCTION & MAINTENANCE
    CONSULTANTS ApS" (Jaccard 1/4 = 0.25, rejected).
    """
    q_tokens = _tokenize(query)
    n_tokens = _tokenize(legal_name)
    if not q_tokens or not n_tokens:
        return False
    overlap = len(q_tokens & n_tokens)
    union = len(q_tokens | n_tokens)
    return overlap / union >= threshold


async def _search_lei(company_name: str, client: httpx.AsyncClient) -> str | None:
    """Return the best-matching ACTIVE LEI for company_name, or None.

    Strips legal suffixes from the query so GLEIF's fulltext index ranks the
    canonical holding entity first (e.g. "ASML HOLDING NV" → "ASML HOLDING").
    Then validates the top-5 results with Jaccard similarity against the
    original name to reject unrelated entities that happen to share an acronym.
    """
    query = _strip_query(company_name)
    resp = await client.get(
        f"{_GLEIF_BASE}/lei-records",
        params={
            "filter[fulltext]": query,
            "filter[entity.status]": "ACTIVE",
            "page[size]": "5",
        },
    )
    resp.raise_for_status()
    hits = resp.json().get("data", [])
    for hit in hits:
        legal_name = (
            hit.get("attributes", {})
            .get("entity", {})
            .get("legalName", {})
            .get("name", "")
        )
        if _is_good_match(company_name, legal_name):
            return hit["id"]
    return None


async def _fetch_children(lei: str, client: httpx.AsyncClient) -> list[dict[str, str]]:
    """Return list of {"name", "lei"} for direct subsidiaries."""
    resp = await client.get(
        f"{_GLEIF_BASE}/lei-records/{lei}/direct-children",
        params={"page[size]": str(_MAX_CHILDREN)},
    )
    resp.raise_for_status()
    children: list[dict[str, str]] = []
    for item in resp.json().get("data", []):
        name = (
            item.get("attributes", {})
            .get("entity", {})
            .get("legalName", {})
            .get("name")
        )
        child_lei = item.get("id")
        if name and child_lei:
            children.append({"name": name, "lei": child_lei})
    return children


async def _fetch_parent(
    lei: str, client: httpx.AsyncClient
) -> dict[str, str] | None:
    """Return {"name", "lei"} for the direct parent, or None if top-level entity."""
    try:
        resp = await client.get(f"{_GLEIF_BASE}/lei-records/{lei}/direct-parent")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json().get("data")
        if not data:
            return None
        name = (
            data.get("attributes", {})
            .get("entity", {})
            .get("legalName", {})
            .get("name")
        )
        parent_lei = data.get("id")
        if name and parent_lei:
            return {"name": name, "lei": parent_lei}
        return None
    except httpx.HTTPStatusError:
        return None


@cached_fetch(key_fn=_gleif_key, ttl_seconds=_TTL, rate_limiter=_rate_limiter)
async def fetch_gleif_relationships(company_name: str) -> dict[str, Any]:
    """Return {"entities": [{"name", "lei", "relationship"}]}.

    Fetches direct parent + direct children for the best GLEIF match of
    company_name.  Returns {"entities": []} on any lookup or network error.
    """
    headers = {
        "User-Agent": _ua(),
        "Accept": "application/vnd.api+json",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            lei = await _search_lei(company_name, client)
            if not lei:
                return {"entities": []}
            children, parent = await asyncio.gather(
                _fetch_children(lei, client),
                _fetch_parent(lei, client),
            )
    except (httpx.HTTPError, ValueError):
        return {"entities": []}

    entities: list[dict[str, str]] = []
    for child in children:
        entities.append({**child, "relationship": "subsidiary"})
    if parent:
        entities.append({**parent, "relationship": "parent"})

    return {"entities": entities}
