"""Wikipedia MediaWiki API client for company article text.

Two sequential API calls per company:
  1. Search → find the right page title (handles legal-suffix variants like "NETFLIX INC")
  2. Extract → fetch full plaintext article, capped at 8000 chars

No API key required. Wikimedia requires a descriptive User-Agent with a contact
email — reuses the same setting as wikidata.py and sec_edgar.py.

TTL: 7 days. No rate limiter needed for low-volume per-ticker lookups.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.services.data_providers._cache import cached_fetch, make_cache_key

_WIKI_API = "https://en.wikipedia.org/w/api.php"
_TTL = 7 * 24 * 60 * 60  # 7 days
_TEXT_CAP = 8000           # chars — intro + first sections have the densest relationship data

_COMPANY_HINTS = frozenset((
    "company", "corporation", "technology", "software", "internet",
    "streaming", "media", "semiconductor", "manufacturer", "enterprise",
    "american", "multinational", "conglomerate", "founded", "nasdaq",
    "nyse", "publicly traded", "business",
))


def _ua() -> str:
    settings = get_settings()
    email = settings.sec_edgar_user_agent.split()[-1]
    return f"AlphaFolio/1.0 ({email})"


def _wiki_key(company_name: str) -> str:
    return make_cache_key("wikipedia.extract.v1", name=company_name.strip().upper())


async def _search_page_title(company_name: str, client: httpx.AsyncClient) -> str | None:
    """Return the Wikipedia page title for `company_name`, or None if not found.

    Picks the first search hit whose snippet/title contains a company-context
    word to avoid resolving "Apple" → apple (fruit) or "Alphabet" → the letter set.
    Falls back to the first result if no hint matches.
    """
    params = {
        "action": "query",
        "list": "search",
        "srsearch": company_name,
        "format": "json",
        "srlimit": "3",
        "utf8": "1",
    }
    resp = await client.get(_WIKI_API, params=params)
    resp.raise_for_status()
    hits = resp.json().get("query", {}).get("search", [])
    if not hits:
        return None

    for hit in hits:
        text = ((hit.get("snippet") or "") + " " + (hit.get("title") or "")).lower()
        if any(h in text for h in _COMPANY_HINTS):
            return hit["title"]

    return hits[0]["title"]


async def _fetch_article_text(page_title: str, client: httpx.AsyncClient) -> str:
    """Return plaintext extract for `page_title`, capped at _TEXT_CAP chars."""
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "true",
        "exsectionformat": "plain",
        "titles": page_title,
        "format": "json",
        "utf8": "1",
    }
    resp = await client.get(_WIKI_API, params=params)
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})
    for page in pages.values():
        text = page.get("extract") or ""
        return text[:_TEXT_CAP]
    return ""


@cached_fetch(key_fn=_wiki_key, ttl_seconds=_TTL)
async def fetch_wikipedia_text(company_name: str) -> dict[str, Any]:
    """Return {'wikipedia_text': str, 'page_title': str | None}.

    Both API calls share one httpx client. Returns empty text on any failure
    so the pipeline can safely check `data.get('wikipedia_text', '')`.
    """
    headers = {"User-Agent": _ua()}
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            page_title = await _search_page_title(company_name, client)
            if not page_title:
                return {"wikipedia_text": "", "page_title": None}
            text = await _fetch_article_text(page_title, client)
        return {"wikipedia_text": text, "page_title": page_title}
    except (httpx.HTTPError, ValueError):
        return {"wikipedia_text": "", "page_title": None}
