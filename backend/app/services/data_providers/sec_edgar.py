"""SEC EDGAR client — real HTTP, cached, rate-limited per SEC fair-access policy.

SEC's published limit is 10 req/s per User-Agent. We stay at 8 rps to leave
headroom. Every request must carry a descriptive UA with a contact email;
that comes from `SEC_EDGAR_USER_AGENT`.

Scope (MVP): ticker→CIK resolution, recent filings index, Form 4 transaction
parsing, and 10-K Item 1A extraction. Earnings-transcript ingestion lives in
the embeddings path, not here.
"""
from __future__ import annotations

import html
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from app.config import get_settings
from app.services.data_providers._cache import (
    AsyncRateLimiter,
    cached_fetch,
    make_cache_key,
)

_BASE_WWW = "https://www.sec.gov"
_BASE_DATA = "https://data.sec.gov"
_COMPANY_TICKERS_URL = f"{_BASE_WWW}/files/company_tickers.json"

# SEC fair-access: 10 req/s per UA. Half-rate to be polite.
_rate_limiter = AsyncRateLimiter(rps=8.0)

# CIK map changes slowly; cache for a day.
_CIK_TTL = 24 * 60 * 60
# Filings index: 1 hour is a reasonable re-check cadence during active research.
_FILINGS_TTL = 60 * 60
# 10-K content rarely changes once filed; cache longer.
_DOCUMENT_TTL = 7 * 24 * 60 * 60


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "User-Agent": settings.sec_edgar_user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


# --------------------------------------------------------------------------
# ticker -> CIK
# --------------------------------------------------------------------------


def _cik_key(ticker: str) -> str:
    return make_cache_key("sec.cik", ticker=ticker.upper())


@cached_fetch(key_fn=_cik_key, ttl_seconds=_CIK_TTL, rate_limiter=_rate_limiter)
async def _resolve_cik(ticker: str) -> dict[str, Any]:
    """Return {'cik': '0001045810', 'ticker': 'NVDA', 'title': 'NVIDIA CORP'}.

    Raises LookupError if the ticker isn't in SEC's master list (OTC / foreign
    issuers often won't be).
    """
    async with httpx.AsyncClient(timeout=20.0, headers=_headers()) as client:
        resp = await client.get(_COMPANY_TICKERS_URL)
        resp.raise_for_status()
        table = resp.json()

    upper = ticker.upper()
    for row in table.values():
        if row.get("ticker", "").upper() == upper:
            cik = str(row["cik_str"]).zfill(10)
            return {"cik": cik, "ticker": upper, "title": row.get("title", "")}

    raise LookupError(f"Ticker {ticker!r} not found in SEC company_tickers master list")


# --------------------------------------------------------------------------
# filings index
# --------------------------------------------------------------------------


def _filings_key(cik: str, form_type: str, lookback_days: int) -> str:
    return make_cache_key("sec.filings", cik=cik, form=form_type, days=lookback_days)


@cached_fetch(key_fn=_filings_key, ttl_seconds=_FILINGS_TTL, rate_limiter=_rate_limiter)
async def _fetch_filings_index(
    cik: str, form_type: str, lookback_days: int
) -> dict[str, Any]:
    """Return {'filings': [{accession, primary_doc, filed_at, form}, ...]}.

    Pulls from /submissions/CIK{cik}.json which returns the most recent 1000
    filings. Sufficient for any lookback window we care about.
    """
    url = f"{_BASE_DATA}/submissions/CIK{cik}.json"
    async with httpx.AsyncClient(timeout=20.0, headers=_headers()) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        body = resp.json()

    recent = body.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filed_dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff = (datetime.now(UTC) - timedelta(days=lookback_days)).date()
    out: list[dict[str, Any]] = []
    for form, accession, filed_str, primary in zip(
        forms, accessions, filed_dates, primary_docs, strict=True
    ):
        if form != form_type:
            continue
        try:
            filed_date = datetime.strptime(filed_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if filed_date < cutoff:
            continue
        out.append(
            {
                "accession": accession,
                "accession_nodash": accession.replace("-", ""),
                "form": form,
                "filed_at": filed_str,
                "primary_doc": primary,
            }
        )
    return {"filings": out}


# --------------------------------------------------------------------------
# Form 4 transactions
# --------------------------------------------------------------------------

_FORM4_XML_NAMES = ("form4.xml", "primary_doc.xml", "edgar.xml")


async def fetch_form4_transactions(
    ticker: str, lookback_days: int = 90
) -> dict[str, Any]:
    """Return {'insider_filings': [transaction dicts]}.

    Each transaction dict: filer, role, transaction (buy/sell), shares, price,
    value_usd, filed_at, form, source_url. Matches DataRetrievalOutput.insider_filings
    shape from the plan's Stage 2.
    """
    company = await _resolve_cik(ticker)
    cik = company["cik"]
    cik_int = int(cik)
    idx = await _fetch_filings_index(cik, form_type="4", lookback_days=lookback_days)

    transactions: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20.0, headers=_headers()) as client:
        for filing in idx["filings"]:
            xml_url = _build_form4_xml_url(cik_int, filing)
            if xml_url is None:
                continue
            await _rate_limiter.acquire()
            try:
                resp = await client.get(xml_url)
                resp.raise_for_status()
            except httpx.HTTPError:
                continue
            transactions.extend(_parse_form4_xml(resp.text, filing))

    return {"insider_filings": transactions}


_XSL_PREFIX_RE = re.compile(r"^xsl[^/]*/", re.IGNORECASE)


def _build_form4_xml_url(cik_int: int, filing: dict[str, Any]) -> str | None:
    """Return the URL to the *raw* Form 4 XML (not the XSL-rendered HTML).

    SEC's submissions index gives `primary_doc` as the display path, usually
    prefixed with an XSL folder like `xslF345X06/wk-form4_...xml`. Hitting
    that URL returns HTML; the raw XML is at the same path with the XSL
    prefix stripped.
    """
    primary = filing.get("primary_doc", "")
    if not primary:
        return None
    raw = _XSL_PREFIX_RE.sub("", primary)
    if not raw.endswith(".xml"):
        # non-XML primary (shouldn't happen for Form 4 but be safe)
        return None
    return (
        f"{_BASE_WWW}/Archives/edgar/data/{cik_int}/"
        f"{filing['accession_nodash']}/{raw}"
    )


def _parse_form4_xml(xml_text: str, filing: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract non-derivative transactions from a Form 4 XML.

    Form 4 schema has `reportingOwner` + `nonDerivativeTable/nonDerivativeTransaction`.
    Transaction code `P`=open-market buy, `S`=open-market sell. Other codes
    (grants, exercises) are ignored here — they're not trading signals.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    filer = _text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName")
    role = _text(root, ".//reportingOwner/reportingOwnerRelationship/officerTitle")
    if not role:
        if _text(root, ".//reportingOwner/reportingOwnerRelationship/isDirector") == "1":
            role = "Director"
        elif _text(root, ".//reportingOwner/reportingOwnerRelationship/isOfficer") == "1":
            role = "Officer"

    source_url = (
        f"{_BASE_WWW}/Archives/edgar/data/"
        f"{int(filing.get('cik', 0)) or ''}/"
        f"{filing['accession_nodash']}/{filing.get('primary_doc', '')}"
    )

    out: list[dict[str, Any]] = []
    for tx in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
        code = _text(tx, ".//transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        shares = _as_float(_text(tx, ".//transactionAmounts/transactionShares/value"))
        price = _as_float(_text(tx, ".//transactionAmounts/transactionPricePerShare/value"))
        if shares is None or price is None:
            continue
        out.append(
            {
                "filer": filer,
                "role": role,
                "transaction": "buy" if code == "P" else "sell",
                "shares": shares,
                "price": price,
                "value_usd": round(shares * price, 2),
                "filed_at": filing["filed_at"],
                "form": "Form 4",
                "source_url": source_url,
            }
        )
    return out


def _text(node: ET.Element, xpath: str) -> str:
    found = node.find(xpath)
    return (found.text or "").strip() if found is not None and found.text else ""


def _as_float(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# 10-K Item 1A Risk Factors
# --------------------------------------------------------------------------


def _tenk_key(ticker: str) -> str:
    return make_cache_key("sec.10k", ticker=ticker.upper())


@cached_fetch(key_fn=_tenk_key, ttl_seconds=_DOCUMENT_TTL, rate_limiter=_rate_limiter)
async def fetch_10k_excerpts(ticker: str) -> dict[str, Any]:
    """Return {'risk_factors_excerpt': str, 'filing_url': str, 'filed_at': str}.

    Fetches the most recent 10-K HTML and pulls out the Item 1A section
    (truncated to ~4000 chars — enough for the LLM to reason about, not so
    much we blow a context window). Revenue segment extraction is left for
    later; XBRL parsing is a project in itself.
    """
    company = await _resolve_cik(ticker)
    cik = company["cik"]
    cik_int = int(cik)
    idx = await _fetch_filings_index(cik, form_type="10-K", lookback_days=400)

    if not idx["filings"]:
        return {"risk_factors_excerpt": "", "filing_url": "", "filed_at": ""}

    latest = idx["filings"][0]
    url = (
        f"{_BASE_WWW}/Archives/edgar/data/{cik_int}/"
        f"{latest['accession_nodash']}/{latest['primary_doc']}"
    )
    async with httpx.AsyncClient(timeout=30.0, headers=_headers()) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    excerpt = _extract_item_1a(html)
    return {
        "risk_factors_excerpt": excerpt,
        "filing_url": url,
        "filed_at": latest["filed_at"],
    }


_ITEM_1A_HEADER_RE = re.compile(
    r"item\s*1a\.?\s*risk\s*factors", re.IGNORECASE
)
_ITEM_1B_HEADER_RE = re.compile(
    r"item\s*1b\.?\s*(unresolved|cybersecurity)", re.IGNORECASE
)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


_XREF_LEAD_CHARS = frozenset("–—-,.\";:”’')")


def _extract_item_1a(raw_html: str) -> str:
    """Locate the Item 1A section *body*, not a ToC entry or cross-reference.

    10-Ks typically have several "Item 1A. Risk Factors" strings: one in the
    ToC (tiny gap to Item 1B), a few embedded cross-references in other sections
    (preceded/followed by sentence punctuation like "– Risks Related to…"), and
    one actual section header (followed by prose like "The following…").

    Filter by: (a) substantial gap to next Item 1B, and (b) the first non-space
    character after the header starts a new sentence (uppercase, not a dash/
    punctuation — which would indicate a cross-ref). Pick the earliest match.
    """
    text = _TAG_RE.sub(" ", raw_html)
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    starts = [m.end() for m in _ITEM_1A_HEADER_RE.finditer(text)]
    if not starts:
        return ""
    ends = [m.start() for m in _ITEM_1B_HEADER_RE.finditer(text)]

    def _is_section_body(start: int) -> bool:
        following = text[start : start + 200].lstrip()
        if not following:
            return False
        c = following[0]
        return not (c in _XREF_LEAD_CHARS or c.islower())

    candidates: list[tuple[int, int]] = []
    for s in starts:
        following_end = next((e for e in ends if e > s), None)
        if following_end is None or (following_end - s) < 5000:
            continue
        if not _is_section_body(s):
            continue
        candidates.append((s, following_end))

    # Fallback: if our filters rejected everything, relax to just "has a following 1B".
    if not candidates:
        for s in starts:
            following_end = next((e for e in ends if e > s), None)
            if following_end is not None:
                candidates.append((s, following_end))
    if not candidates:
        return ""

    start, end = min(candidates, key=lambda c: c[0])
    end = min(end, start + 4000)
    return text[start:end].strip()[:4000]
