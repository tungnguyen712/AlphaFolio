"""SEC EDGAR Full-Text Search (EFTS) client — cross-filer customer discovery.

Searches the entire corpus of SEC 10-K/20-F filings for exact-phrase mentions
of a company name.  Every filer that names the target company in their own filing
is, by definition, a business relationship — and for supplier companies (TSMC,
ASML, LRCX) the filer is almost always a customer.

This is the *inverse* of the standard 10-K pipeline which reads the target's
own filing.  EFTS answers "who depends on this company?" rather than "who does
this company depend on?".

Example:
  search "Taiwan Semiconductor Manufacturing" in 10-K filings
  → returns NVDA, AMD, QCOM, AAPL … each disclosing TSMC as their foundry.
  Those filers are TSMC's customers — a direction TSMC never self-discloses.

No API key required.  EFTS is a public SEC endpoint.
Rate: polite 0.3 rps, 7-day TTL — one lookup per company per week.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import get_settings
from app.services.data_providers._cache import (
    AsyncRateLimiter,
    cached_fetch,
    make_cache_key,
)

_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
_TTL = 7 * 24 * 60 * 60      # 7 days
_LOOKBACK_YEARS = 2           # only recent filings are relevant
_MAX_CUSTOMERS = 20

# Very polite — SEC has no auth but monitors abuse.
_rate_limiter = AsyncRateLimiter(rps=0.3)

# Strip ALL trailing parenthetical groups from display_names entries.
# Raw EFTS format: "COMPANY NAME  (TICKER1, TICKER2)  (CIK 0001234567)"
# We want just "COMPANY NAME".
_SUFFIX_RE = re.compile(r"(\s*\([^)]+\))+\s*$")

# Legal-suffix words to strip when building the search phrase, so that
# "ASML HOLDING NV" → "ASML HOLDING" and still matches "ASML Holding N.V."
_LEGAL_SUFFIX_RE = re.compile(
    r"\s+(?:INC|CORP|LTD|LLC|CO|NV|PLC|AG|SA|BV|KK|COMPANY|GROUP|"
    r"HOLDINGS?|INTERNATIONAL|TECHNOLOGIES?|SYSTEMS?|SEMICONDUCTOR|"
    r"MANUFACTURING|CORPORATION|INCORPORATED|LIMITED)\.?\s*$",
    re.IGNORECASE,
)


def _ua() -> str:
    settings = get_settings()
    email = settings.sec_edgar_user_agent.split()[-1]
    return f"AlphaFolio/1.0 ({email})"


def _efts_key(company_name: str) -> str:
    return make_cache_key("sec.efts.customers.v3", name=company_name.strip().upper())


def _extract_filer_name(display_name: str) -> str:
    """Strip trailing parenthetical suffix from EFTS display name.

    Handles both CIK format 'NVIDIA CORP  (CIK 0001045810)' and
    ticker format 'TAIWAN SEMICONDUCTOR  (TSM, TSMWF)' → 'TAIWAN SEMICONDUCTOR'.
    """
    return _SUFFIX_RE.sub("", display_name).strip()


def _search_phrase(company_name: str) -> str:
    """Build a concise exact-phrase search term by stripping legal suffixes.

    Keeps stripping until we can't reduce further (handles stacked suffixes
    like "HOLDINGS INC" in two passes).
    """
    name = company_name.strip()
    for _ in range(3):
        reduced = _LEGAL_SUFFIX_RE.sub("", name).strip()
        if reduced == name or not reduced:
            break
        name = reduced
    return name


@cached_fetch(key_fn=_efts_key, ttl_seconds=_TTL, rate_limiter=_rate_limiter)
async def fetch_efts_customers(company_name: str) -> dict[str, Any]:
    """Return {"customers": [{"name", "cik", "file_date"}]}.

    Issues one EFTS search for exact-phrase mentions of company_name in
    10-K and 20-F filings from the past _LOOKBACK_YEARS years.  Returns
    the filers (who mentioned the company) as prospective customers.
    Returns {"customers": []} on any error.
    """
    phrase = _search_phrase(company_name)
    if not phrase:
        return {"customers": []}

    start_dt = (
        datetime.now(UTC) - timedelta(days=365 * _LOOKBACK_YEARS)
    ).strftime("%Y-%m-%d")

    params = {
        "q": f'"{phrase}"',
        "forms": "10-K,20-F",
        "dateRange": "custom",
        "startdt": start_dt,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                _EFTS_URL,
                params=params,
                headers={"User-Agent": _ua()},
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"customers": []}

    hits = data.get("hits", {}).get("hits", [])
    customers: list[dict[str, str]] = []
    seen: set[str] = set()

    for hit in hits:
        source = hit.get("_source", {})
        display_names = source.get("display_names", [])
        ciks = source.get("ciks", [])
        file_date = source.get("file_date", "")

        if not display_names:
            continue

        name = _extract_filer_name(display_names[0])
        if not name:
            continue

        key = name.upper()
        if key in seen:
            continue
        seen.add(key)

        customers.append({
            "name": name,
            "cik": ciks[0] if ciks else "",
            "file_date": file_date,
        })

        if len(customers) >= _MAX_CUSTOMERS:
            break

    return {"customers": customers}
