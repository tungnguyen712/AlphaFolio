"""SEC EDGAR client — real HTTP, cached, rate-limited per SEC fair-access policy.

SEC's published limit is 10 req/s per User-Agent. We stay at 8 rps to leave
headroom. Every request must carry a descriptive UA with a contact email;
that comes from `SEC_EDGAR_USER_AGENT`.

Scope (MVP): ticker→CIK resolution, recent filings index, Form 4 transaction
parsing, 10-K Item 1A extraction, and S-1 excerpt extraction for pre-IPO
research. Earnings-transcript ingestion lives in the embeddings path, not here.
"""
from __future__ import annotations

import asyncio
import html
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from app.config import get_settings
from app.models.agents.common import InsiderSummary, InsiderTransaction
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

    # Fallback: try interpreting the input as a company name
    # (e.g. user types "ECHOSTAR" which is a company name, not a ticker)
    name_upper = upper
    starts_with = [
        r for r in table.values()
        if str(r.get("title", "")).upper().startswith(name_upper)
    ]
    if len(starts_with) == 1:
        row = starts_with[0]
        cik = str(row["cik_str"]).zfill(10)
        return {"cik": cik, "ticker": str(row.get("ticker", upper)).upper(), "title": row.get("title", "")}
    if len(starts_with) > 1:
        # Pick the shortest (most likely the flagship legal entity)
        row = min(starts_with, key=lambda r: len(str(r.get("title", ""))))
        cik = str(row["cik_str"]).zfill(10)
        return {"cik": cik, "ticker": str(row.get("ticker", upper)).upper(), "title": row.get("title", "")}

    raise LookupError(f"Ticker {ticker!r} not found in SEC company_tickers master list")


# --------------------------------------------------------------------------
# Company-name → ticker (public companies, friendly UX)
# --------------------------------------------------------------------------


def _name_to_ticker_key(name: str) -> str:
    return make_cache_key("sec.name_to_ticker", name=name.strip().upper())


@cached_fetch(key_fn=_name_to_ticker_key, ttl_seconds=_CIK_TTL, rate_limiter=_rate_limiter)
async def resolve_ticker_from_name(name: str) -> dict[str, Any]:
    """Fuzzy-match a human-friendly company name to its ticker symbol.

    Returns {'ticker': 'NVDA', 'cik': '0001045810', 'title': 'NVIDIA CORP'}.
    Raises LookupError with a diagnostic message if no confident match.

    Match precedence (highest first):
      1. Case-insensitive exact match on ticker — "nvda" -> NVDA.
      2. Case-insensitive exact match on title — "NVIDIA CORP" -> NVDA.
      3. Title starts with the query, single candidate — "Nvidia" -> NVDA
         (since only "NVIDIA CORP" starts with "nvidia").
      4. Title contains the query, single candidate.

    Ties at (3) or (4) raise LookupError listing the candidates so the caller
    can be more specific. Prevents silent wrong-ticker resolution.
    """
    query = name.strip()
    if not query:
        raise LookupError("Empty company name")
    query_upper = query.upper()

    async with httpx.AsyncClient(timeout=20.0, headers=_headers()) as client:
        resp = await client.get(_COMPANY_TICKERS_URL)
        resp.raise_for_status()
        table = resp.json()

    rows = list(table.values())

    # 1. Exact ticker match.
    for row in rows:
        if str(row.get("ticker", "")).upper() == query_upper:
            return _to_resolved(row)

    # 2. Exact title match.
    for row in rows:
        if str(row.get("title", "")).upper() == query_upper:
            return _to_resolved(row)

    # 3. Starts-with. Prefer a single hit; shortest title wins if ambiguous.
    starts_with = [r for r in rows if str(r.get("title", "")).upper().startswith(query_upper)]
    if len(starts_with) == 1:
        return _to_resolved(starts_with[0])
    if len(starts_with) > 1:
        # If the query IS one of the titles as a whole word (e.g. "APPLE" vs
        # "APPLE INC", "APPLE HOSPITALITY REIT INC"), pick the shortest — the
        # flagship company usually has the terser legal name.
        best = min(starts_with, key=lambda r: len(str(r.get("title", ""))))
        alt = [r for r in starts_with if r is not best]
        # Only auto-pick when the query completes a whole word boundary in the
        # best title (i.e. the best title starts with "<query> " or equals the
        # query) AND the best is substantially shorter than every alternative.
        # If all candidates share the same leading word (query is a mid-word
        # prefix like "APPL" into "APPLE …") they are genuinely ambiguous.
        best_title_upper = str(best.get("title", "")).upper()
        query_ends_on_word_boundary = (
            best_title_upper == query_upper
            or best_title_upper.startswith(query_upper + " ")
        )
        if query_ends_on_word_boundary and len(best_title_upper) * 2 < min(
            len(str(r.get("title", ""))) for r in alt
        ):
            return _to_resolved(best)
        candidates = [f"{r.get('ticker')} ({r.get('title')})" for r in starts_with[:8]]
        raise LookupError(
            f"Company name {name!r} matches multiple tickers: {candidates}. "
            "Pass a more specific name or the ticker directly."
        )

    # 4. Substring fallback.
    substring = [r for r in rows if query_upper in str(r.get("title", "")).upper()]
    if len(substring) == 1:
        return _to_resolved(substring[0])
    if len(substring) > 1:
        candidates = [f"{r.get('ticker')} ({r.get('title')})" for r in substring[:8]]
        raise LookupError(
            f"Company name {name!r} matches multiple tickers by substring: {candidates}. "
            "Pass a more specific name or the ticker directly."
        )

    raise LookupError(
        f"No SEC-registered ticker found for company name {name!r}. "
        "Check spelling or pass the ticker symbol directly."
    )


def _to_resolved(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(row.get("ticker", "")).upper(),
        "cik": str(row.get("cik_str", "")).zfill(10),
        "title": str(row.get("title", "")),
    }


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
                "planned_status": _detect_planned_status(tx, root),
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


def _detect_planned_status(tx: ET.Element, root: ET.Element) -> str:
    """Classify an insider transaction by intent using Form 4 footnotes.

    Searches footnote text for 10b5-1 plan references. Falls back to
    transaction code heuristics. Returns one of the planned_status literals.
    """
    footnote_ids = {el.get("id") for el in tx.findall(".//footnoteId") if el.get("id")}
    for fn in root.findall(".//footnotes/footnote"):
        if fn.get("id") in footnote_ids:
            text = (fn.text or "").lower()
            if "10b5-1" in text or "rule 10b5" in text:
                return "planned_10b5_1"
    code = _text(tx, ".//transactionCoding/transactionCode")
    if code == "M":
        return "option_exercise"
    if code == "F":
        return "compensation"
    if code in ("P", "S"):
        return "discretionary"
    return "unknown"


def aggregate_insider_transactions(
    transactions: list[InsiderTransaction],
) -> InsiderSummary:
    """Aggregate raw Form 4 rows into a summary keyed by unique filers.

    Breadth metrics (unique_sellers, csuite_sellers, etc.) are based on
    unique filer names, not raw transaction row count, so one person filing
    multiple line items doesn't overstate selling breadth.
    """
    _CSUITE_KEYWORDS = {"ceo", "cfo", "coo", "cto", "president", "chief"}

    sellers = [t for t in transactions if t.transaction == "sell"]
    buyers = [t for t in transactions if t.transaction == "buy"]

    def _is_csuite(role: str | None) -> bool:
        if not role:
            return False
        r = role.lower()
        # Use word-boundary search to avoid false positives like "director" ⊃ "cto"
        return any(re.search(rf"\b{k}\b", r) for k in _CSUITE_KEYWORDS)

    def _is_board(role: str | None) -> bool:
        if not role:
            return False
        return "director" in role.lower() and not _is_csuite(role)

    return InsiderSummary(
        unique_sellers=len({t.filer for t in sellers}),
        unique_buyers=len({t.filer for t in buyers}),
        csuite_sellers=len({t.filer for t in sellers if _is_csuite(t.role)}),
        board_sellers=len({t.filer for t in sellers if _is_board(t.role)}),
        num_distinct_filings=len({str(t.source_url) for t in transactions}),
        raw_transaction_count=len(transactions),
        total_sales_value=round(sum(t.value_usd for t in sellers), 2),
        total_purchase_value=round(sum(t.value_usd for t in buyers), 2),
    )


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


_ITEM_1_HEADER_RE = re.compile(
    r"item\s*1\.?\s*(?:business)", re.IGNORECASE
)
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


# --------------------------------------------------------------------------
# 10-K Item 1 Business section (supply chain: customers, suppliers, mfrs)
# --------------------------------------------------------------------------


def _tenk_item1_key(ticker: str) -> str:
    return make_cache_key("sec.10k.item1.v3", ticker=ticker.upper())


@cached_fetch(key_fn=_tenk_item1_key, ttl_seconds=_DOCUMENT_TTL, rate_limiter=_rate_limiter)
async def fetch_10k_item1_business(ticker: str) -> dict[str, Any]:
    """Return {'business_excerpt': str, 'filing_url': str, 'filed_at': str, 'company_name': str}.

    Fetches the most recent 10-K and extracts Item 1 "Business" section (truncated
    to ~5000 chars). This section contains significant customer names, sole-source
    suppliers, and manufacturing partner disclosures. Terminates at Item 1A.
    """
    company = await _resolve_cik(ticker)
    cik = company["cik"]
    cik_int = int(cik)
    idx = await _fetch_filings_index(cik, form_type="10-K", lookback_days=400)

    if not idx["filings"]:
        return {
            "business_excerpt": "",
            "filing_url": "",
            "filed_at": "",
            "company_name": company.get("title", ticker),
        }

    latest = idx["filings"][0]
    url = (
        f"{_BASE_WWW}/Archives/edgar/data/{cik_int}/"
        f"{latest['accession_nodash']}/{latest['primary_doc']}"
    )
    async with httpx.AsyncClient(timeout=30.0, headers=_headers()) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        raw_html = resp.text

    excerpt = _extract_item1_business(raw_html)
    return {
        "business_excerpt": excerpt,
        "filing_url": url,
        "filed_at": latest["filed_at"],
        "company_name": company.get("title", ticker),
    }


def _extract_item1_business(raw_html: str) -> str:
    """Extract Item 1 Business section body, terminating at Item 1A.

    Picks the 'Item 1. Business' start with the LARGEST gap to the next
    'Item 1A' occurrence — this reliably selects the real body section over
    ToC entries (tiny gap) and cross-references ("See Item 1A. Risk Factors"
    embedded in body prose, medium gap).
    """
    text = _strip_html(raw_html)

    starts = list(_ITEM_1_HEADER_RE.finditer(text))
    if not starts:
        return ""

    ends = [m.start() for m in _ITEM_1A_HEADER_RE.finditer(text)]

    best_start: int | None = None
    best_end: int | None = None
    best_gap = -1

    for m in starts:
        s = m.end()
        following_end = next((e for e in ends if e > s), None)
        gap = (following_end - s) if following_end is not None else (len(text) - s)
        if gap > best_gap:
            best_gap = gap
            best_start = s
            best_end = following_end

    if best_start is None:
        return ""

    end = min(best_end, best_start + 5000) if best_end is not None else (best_start + 5000)
    return text[best_start:end].strip()[:5000]


# --------------------------------------------------------------------------
# S-1 lookup by company name (pre-IPO research)
# --------------------------------------------------------------------------

# EDGAR full-text search (what the new EDGAR UI uses). Returns JSON with
# one hit per matching filing — no company-selection indirection like the
# legacy /cgi-bin/browse-edgar?output=atom path, which returns a list of
# matching *companies* for ambiguous name queries.
_FTS_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"


def _s1_search_key(company_name: str) -> str:
    return make_cache_key("sec.s1.search", name=company_name.strip().upper())


async def _edgar_fts_query(company_name: str, form: str) -> list[dict[str, Any]]:
    """One EDGAR full-text search request for a single form. Caller decides
    how to handle errors — we just raise httpx.HTTPError on any non-2xx or
    network failure, and ValueError if the body isn't valid JSON.

    Drops the surrounding quotes around the query: `q="Stripe"` (exact phrase)
    has been observed to 500 on common names; the looser `q=Stripe` is more
    forgiving and we'll filter false positives downstream by display_name.
    """
    params = {"q": company_name, "forms": form}
    async with httpx.AsyncClient(timeout=20.0, headers=_headers()) as client:
        resp = await client.get(_FTS_SEARCH_URL, params=params)
        resp.raise_for_status()
        body = resp.json()
    return body.get("hits", {}).get("hits", []) or []


@cached_fetch(key_fn=_s1_search_key, ttl_seconds=_FILINGS_TTL, rate_limiter=_rate_limiter)
async def resolve_company_by_name(company_name: str) -> dict[str, Any]:
    """Find recent S-1 (and S-1/A) filings for a company by name.

    Returns {'cik': str, 'company_title': str, 'filings': [...]} where each
    filing has {accession, accession_nodash, form, filed_at}.

    Raises LookupError if no S-1 match is found for this name OR if EDGAR's
    FTS endpoint returns an error (treat both as "we couldn't find a filing"
    so the pre_ipo branch's news-only fallback kicks in either way).

    Ambiguity handling: EDGAR's FTS returns hits from every company whose
    filings mention the query. We filter to hits whose `display_names`
    contains the query (case-insensitive) — that keeps "Reddit" from pulling
    in unrelated companies that merely referenced Reddit in an S-1.
    """
    # Two requests — EDGAR's FTS sometimes 500s on the combined "S-1,S-1/A"
    # forms parameter (the slash in S-1/A trips their parser intermittently).
    # Issuing them separately and merging is more reliable.
    raw_hits: list[dict[str, Any]] = []
    for form in ("S-1", "S-1/A"):
        try:
            raw_hits.extend(await _edgar_fts_query(company_name, form))
        except (httpx.HTTPError, ValueError):
            # 500/timeouts/JSON-decode failures all funnel into LookupError
            # below if the cumulative result set is empty.
            continue

    if not raw_hits:
        raise LookupError(
            f"No S-1 filings found on EDGAR for company name {company_name!r}. "
            "Pre-IPO research requires at least one S-1 on file."
        )

    query_lower = company_name.lower()

    # Bucket hits by CIK, keeping only the ones whose own display_name matches
    # the query — this drops cases where the filing mentions the company in
    # passing but isn't filed BY that company. Dedup by accession because we
    # query S-1 and S-1/A separately and a filing classified by EDGAR as
    # S-1/A could legitimately appear in both result sets.
    by_cik: dict[str, dict[str, Any]] = {}
    seen_accessions: set[str] = set()
    for hit in raw_hits:
        parsed = _parse_fts_s1_hit(hit, query_lower)
        if parsed is None:
            continue
        accession = parsed["filing"]["accession"]
        if accession in seen_accessions:
            continue
        seen_accessions.add(accession)
        cik = parsed["cik"]
        bucket = by_cik.setdefault(
            cik, {"company_title": parsed["company_title"], "filings": []}
        )
        bucket["filings"].append(parsed["filing"])

    if not by_cik:
        raise LookupError(
            f"EDGAR returned S-1 hits for {company_name!r} but none filed by a "
            "company whose name matches the query. Try a more specific name."
        )

    # Pick the CIK whose most recent filing is newest. Ties by CIK count matter
    # less than recency — a dormant shell with 10 S-1s shouldn't beat a live
    # filer's single recent S-1.
    best_cik = max(
        by_cik,
        key=lambda c: max(
            f.get("filed_at", "") for f in by_cik[c]["filings"]
        ),
    )
    bucket = by_cik[best_cik]
    filings = sorted(
        bucket["filings"], key=lambda f: f.get("filed_at", ""), reverse=True
    )

    return {
        "cik": best_cik,
        "company_title": bucket["company_title"],
        "filings": filings,
    }


def _parse_fts_s1_hit(hit: dict[str, Any], query_lower: str) -> dict[str, Any] | None:
    source = hit.get("_source", {})
    ciks = source.get("ciks") or []
    display_names = source.get("display_names") or []
    if not ciks or not display_names:
        return None

    # Require at least one display_name to contain the query — filters out
    # "company A's S-1 that mentions company B" hits.
    if not any(query_lower in name.lower() for name in display_names):
        return None

    cik = str(ciks[0]).zfill(10)
    display_name = display_names[0]
    adsh = source.get("adsh") or hit.get("_id", "")
    if not adsh:
        return None

    return {
        "cik": cik,
        "company_title": display_name,
        "filing": {
            "form": source.get("form", "S-1").upper(),
            "accession": adsh,
            "accession_nodash": adsh.replace("-", ""),
            "filed_at": source.get("file_date", ""),
        },
    }


# --------------------------------------------------------------------------
# S-1 excerpt extraction
# --------------------------------------------------------------------------


def _s1_excerpts_key(company_name: str) -> str:
    return make_cache_key("sec.s1.excerpts", name=company_name.strip().upper())


@cached_fetch(key_fn=_s1_excerpts_key, ttl_seconds=_DOCUMENT_TTL, rate_limiter=_rate_limiter)
async def fetch_s1_excerpts(company_name: str) -> dict[str, Any]:
    """Return {'risk_factors_excerpt', 'business_overview_excerpt',
    'filing_url', 'filed_at', 'form'}.

    Picks the most recent S-1 (or S-1/A amendment) for the company, fetches
    the primary document from the filing's index page, and extracts the two
    most load-bearing sections for pre-IPO research: Risk Factors and the
    Prospectus Summary (company's business overview).
    """
    resolved = await resolve_company_by_name(company_name)
    cik = resolved["cik"]
    latest = resolved["filings"][0]

    # Fetch the filing's index page to find the primary document filename.
    primary_url = await _find_s1_primary_doc_url(cik, latest)
    if primary_url is None:
        return _empty_s1_excerpts()

    async with httpx.AsyncClient(timeout=30.0, headers=_headers()) as client:
        resp = await client.get(primary_url)
        resp.raise_for_status()
        raw_html = resp.text

    return {
        "risk_factors_excerpt": _extract_s1_risk_factors(raw_html),
        "business_overview_excerpt": _extract_s1_prospectus_summary(raw_html),
        "filing_url": primary_url,
        "filed_at": latest.get("filed_at", ""),
        "form": latest.get("form", "S-1"),
    }


def _empty_s1_excerpts() -> dict[str, Any]:
    return {
        "risk_factors_excerpt": "",
        "business_overview_excerpt": "",
        "filing_url": "",
        "filed_at": "",
        "form": "",
    }


async def _find_s1_primary_doc_url(cik: str, filing: dict[str, Any]) -> str | None:
    """Read the filing's index JSON to find the primary .htm document."""
    cik_int = int(cik)
    index_json_url = (
        f"{_BASE_WWW}/Archives/edgar/data/{cik_int}/"
        f"{filing['accession_nodash']}/index.json"
    )
    async with httpx.AsyncClient(timeout=20.0, headers=_headers()) as client:
        try:
            resp = await client.get(index_json_url)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError:
            return None

    items = body.get("directory", {}).get("item", [])
    # Heuristic: primary S-1 doc is the largest .htm without "exhibit" in the name.
    candidates = [
        it
        for it in items
        if it.get("name", "").endswith(".htm") and "exhibit" not in it.get("name", "").lower()
    ]
    if not candidates:
        return None
    primary = max(candidates, key=lambda it: int(it.get("size", 0) or 0))
    return (
        f"{_BASE_WWW}/Archives/edgar/data/{cik_int}/"
        f"{filing['accession_nodash']}/{primary['name']}"
    )


# --- S-1 section extraction -------------------------------------------------

# S-1 Risk Factors header: usually just "Risk Factors" (all caps or title case),
# sometimes preceded by "RISK FACTORS" as a standalone section. Distinct from
# 10-K which uses "Item 1A. Risk Factors".
_S1_RISK_FACTORS_HEADER_RE = re.compile(
    r"(?<!\w)(?:RISK\s+FACTORS)(?!\w)", re.IGNORECASE
)
# After Risk Factors an S-1 typically continues with "Use of Proceeds" or
# "Special Note Regarding Forward-Looking Statements" etc. — we terminate on
# the first plausible next section header.
_S1_RISK_FACTORS_END_RE = re.compile(
    r"(?<!\w)(?:USE\s+OF\s+PROCEEDS|SPECIAL\s+NOTE|CAUTIONARY\s+STATEMENT|"
    r"DIVIDEND\s+POLICY|CAPITALIZATION)(?!\w)",
    re.IGNORECASE,
)

_S1_SUMMARY_HEADER_RE = re.compile(
    r"(?<!\w)(?:PROSPECTUS\s+SUMMARY|SUMMARY(?:\s+OF\s+THE\s+PROSPECTUS)?)(?!\w)",
    re.IGNORECASE,
)
_S1_SUMMARY_END_RE = re.compile(
    r"(?<!\w)(?:(?:THE\s+)?OFFERING|RISK\s+FACTORS|SPECIAL\s+NOTE)(?!\w)",
    re.IGNORECASE,
)


def _extract_s1_risk_factors(raw_html: str) -> str:
    text = _strip_html(raw_html)
    return _find_section(text, _S1_RISK_FACTORS_HEADER_RE, _S1_RISK_FACTORS_END_RE, max_chars=4000)


def _extract_s1_prospectus_summary(raw_html: str) -> str:
    text = _strip_html(raw_html)
    # Prospectus summary is shorter than risk factors; cap lower.
    return _find_section(text, _S1_SUMMARY_HEADER_RE, _S1_SUMMARY_END_RE, max_chars=2500)


def _strip_html(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", raw_html)
    text = html.unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _find_section(
    text: str,
    start_re: re.Pattern[str],
    end_re: re.Pattern[str],
    *,
    max_chars: int,
) -> str:
    """Find the section body whose header matches `start_re` and ends before
    `end_re`. Applies the same ToC-vs-body heuristic as `_extract_item_1a`:
    a real section has a substantial gap to the next header.
    """
    starts = [m.end() for m in start_re.finditer(text)]
    if not starts:
        return ""
    ends = [m.start() for m in end_re.finditer(text)]

    candidates: list[tuple[int, int]] = []
    for s in starts:
        following_end = next((e for e in ends if e > s), None)
        if following_end is None or (following_end - s) < 2000:
            # Likely a ToC entry — real sections have >2k chars of body.
            continue
        candidates.append((s, following_end))

    if not candidates:
        # Relax: accept any start with an end after it.
        for s in starts:
            following_end = next((e for e in ends if e > s), None)
            if following_end is not None:
                candidates.append((s, following_end))
    if not candidates:
        return ""

    start, end = min(candidates, key=lambda c: c[0])
    end = min(end, start + max_chars)
    return text[start:end].strip()[:max_chars]


# --------------------------------------------------------------------------
# Form D (private offering) — funding-round size for private companies
# --------------------------------------------------------------------------


def _form_d_search_key(company_name: str) -> str:
    return make_cache_key("sec.formd.search", name=company_name.strip().upper())


@cached_fetch(key_fn=_form_d_search_key, ttl_seconds=_FILINGS_TTL, rate_limiter=_rate_limiter)
async def fetch_form_d_filings(
    company_name: str, *, max_filings: int = 5
) -> dict[str, Any]:
    """Return {'filings': [<form_d_dict>, ...]} — Form D notices for the company.

    Form D is a notice of unregistered securities sale; private companies file
    one for each funding round (Series A/B/C/etc.). Each parsed entry has:
      issuer_name, accession, filed_at, date_of_first_sale,
      total_offering_amount_usd, total_amount_sold_usd, source_url.

    Returns empty list if no Form D filings found or if EDGAR errors — silent
    fallback because Form D is supplementary data, not load-bearing.
    """
    try:
        raw_hits = await _edgar_fts_query(company_name, "D")
    except (httpx.HTTPError, ValueError):
        return {"filings": []}

    if not raw_hits:
        return {"filings": []}

    query_lower = company_name.lower()
    metas: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in raw_hits:
        parsed = _parse_form_d_hit(hit, query_lower)
        if parsed is None:
            continue
        if parsed["accession"] in seen:
            continue
        seen.add(parsed["accession"])
        metas.append(parsed)
        if len(metas) >= max_filings:
            break

    # Fetch + parse the XML primary doc for each filing in parallel.
    parsed_filings = await asyncio.gather(
        *[_fetch_and_parse_form_d_xml(m) for m in metas], return_exceptions=True
    )
    out: list[dict[str, Any]] = []
    for filing in parsed_filings:
        if isinstance(filing, BaseException) or filing is None:
            continue
        out.append(filing)

    out.sort(key=lambda f: f.get("filed_at") or "", reverse=True)
    return {"filings": out}


def _parse_form_d_hit(hit: dict[str, Any], query_lower: str) -> dict[str, Any] | None:
    source = hit.get("_source", {})
    ciks = source.get("ciks") or []
    display_names = source.get("display_names") or []
    if not ciks or not display_names:
        return None
    if not any(query_lower in name.lower() for name in display_names):
        return None

    adsh = source.get("adsh") or hit.get("_id", "")
    if not adsh:
        return None

    return {
        "issuer_name": display_names[0],
        "cik": str(ciks[0]).zfill(10),
        "accession": adsh,
        "accession_nodash": adsh.replace("-", ""),
        "filed_at": source.get("file_date", ""),
    }


# Form D XML uses an SEC-specific namespace; tags vary slightly by version.
# We do a tag-suffix search (.//*[localname]) by stripping the namespace from
# each element rather than declaring the exact ns map (which has changed
# across schema versions).
_FORM_D_OFFERING_AMT_TAGS = ("totalOfferingAmount",)
_FORM_D_SOLD_AMT_TAGS = ("totalAmountSold",)
_FORM_D_FIRST_SALE_TAGS = ("dateOfFirstSale",)


async def _fetch_and_parse_form_d_xml(meta: dict[str, Any]) -> dict[str, Any] | None:
    """Locate the Form D primary XML, parse the dollar amounts and dates."""
    cik_int = int(meta["cik"])
    index_json_url = (
        f"{_BASE_WWW}/Archives/edgar/data/{cik_int}/"
        f"{meta['accession_nodash']}/index.json"
    )
    async with httpx.AsyncClient(timeout=20.0, headers=_headers()) as client:
        try:
            resp = await client.get(index_json_url)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError:
            return None

        items = body.get("directory", {}).get("item", [])
        # Form D primary doc is named primary_doc.xml (or sometimes the
        # form-d.xml legacy name).
        xml_name = next(
            (
                it["name"]
                for it in items
                if it.get("name", "").lower() in ("primary_doc.xml", "form-d.xml")
            ),
            None,
        )
        if xml_name is None:
            return None

        xml_url = (
            f"{_BASE_WWW}/Archives/edgar/data/{cik_int}/"
            f"{meta['accession_nodash']}/{xml_name}"
        )
        try:
            xml_resp = await client.get(xml_url)
            xml_resp.raise_for_status()
            xml_text = xml_resp.text
        except httpx.HTTPError:
            return None

    return _parse_form_d_xml(xml_text, meta, source_url=xml_url)


def _parse_form_d_xml(
    xml_text: str, meta: dict[str, Any], *, source_url: str
) -> dict[str, Any] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    def _find_first(tag_names: tuple[str, ...]) -> str | None:
        for el in root.iter():
            local = el.tag.rsplit("}", 1)[-1]
            if local in tag_names and el.text:
                stripped = el.text.strip()
                # Form D issuers occasionally leave date/amount fields blank
                # — collapse "" to None so Pydantic doesn't reject the row.
                if stripped:
                    return stripped
        return None

    return {
        "issuer_name": meta["issuer_name"],
        "accession": meta["accession"],
        "filed_at": meta.get("filed_at") or None,
        "date_of_first_sale": _find_first(_FORM_D_FIRST_SALE_TAGS),
        "total_offering_amount_usd": _as_float(_find_first(_FORM_D_OFFERING_AMT_TAGS)),
        "total_amount_sold_usd": _as_float(_find_first(_FORM_D_SOLD_AMT_TAGS)),
        "source_url": source_url,
    }
