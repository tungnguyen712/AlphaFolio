"""Post-retrieval news relevance filter.

Pure Python — no LLM, no network. Drops articles where the target company
is not the primary subject, removes near-duplicate headlines, and flags
known mirror/low-quality domains.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlparse

from app.models.agents.common import FilterReasonCode, FilteredNewsItem, NewsItem

_LOW_QUALITY_DOMAINS: frozenset[str] = frozenset(
    {
        "seekingalpha.com",
        "zerohedge.com",
        "investorplace.com",
        "motleyfool.com",
        "thestreet.com",
        "benzinga.com",
    }
)

# Country-code TLDs used by mirror/localized investing sites
_MIRROR_SUFFIX_RE = re.compile(
    r"\.(co\.uk|co\.in|com\.au|ca|de|fr|it|es|br|sg|mx|pl|nl|se|no|dk)$"
)


def filter_news(
    ticker: str,
    items: list[NewsItem],
    lookback_days: int,
    company_name: str | None = None,
) -> tuple[list[NewsItem], list[FilteredNewsItem]]:
    """Return (kept, dropped). Deterministic — no network calls, no LLM."""
    kept: list[NewsItem] = []
    dropped: list[FilteredNewsItem] = []
    seen_normalized: dict[str, NewsItem] = {}

    for item in items:
        result = _classify(item, ticker, company_name, lookback_days, seen_normalized)
        if result is None:
            kept.append(item)
            norm = _normalize_headline(item.headline)
            seen_normalized[norm] = item
        else:
            dropped.append(result)

    return kept, dropped


def _classify(
    item: NewsItem,
    ticker: str,
    company_name: str | None,
    lookback_days: int,
    seen: dict[str, NewsItem],
) -> FilteredNewsItem | None:
    """Return a FilteredNewsItem if item should be dropped, else None (keep)."""

    # 1. Staleness check
    if item.published and (date.today() - item.published).days > lookback_days:
        return _drop(item, "stale_article", f"published {item.published}")

    # 2. Low-quality source
    domain = _extract_domain(str(item.url))
    base_domain = _strip_mirror_suffix(domain)
    if base_domain in _LOW_QUALITY_DOMAINS:
        return _drop(item, "low_quality_source", domain)

    # 3. Relevance — ticker or company name must appear in headline + snippet
    text = f"{item.headline} {item.snippet}".lower()
    ticker_lower = ticker.lower()

    # Whole-word match to avoid "AI" matching "NVIDIA AI chips" on short tickers
    pattern = re.compile(rf"\b{re.escape(ticker_lower)}\b")
    company_hit = bool(pattern.search(text))

    if not company_hit and company_name:
        company_hit = company_name.lower() in text

    if not company_hit:
        # Substring present but not as a whole word → weak match
        if ticker_lower in text:
            return _drop(item, "weak_company_match", "ticker is substring, not whole word")
        return _drop(item, "unrelated_ticker", "no ticker/company mention in headline+snippet")

    # 4. Near-duplicate headline (first-seen wins; Tavily already ranks by score)
    norm = _normalize_headline(item.headline)
    if norm in seen:
        existing = seen[norm]
        return _drop(item, "duplicate_headline", f"matches: '{existing.headline[:60]}'")

    # 5. Mirrored domain (investing.com.br, investing.com.de, etc.)
    if _MIRROR_SUFFIX_RE.search(domain):
        return _drop(item, "mirrored_domain", f"country-localized domain: {domain}")

    return None  # keep


def _drop(item: NewsItem, reason: FilterReasonCode, detail: str = "") -> FilteredNewsItem:
    return FilteredNewsItem(
        headline=item.headline,
        source=item.source,
        url=item.url,
        reason=reason,
        reason_detail=detail,
    )


def _normalize_headline(headline: str) -> str:
    """Produce a short normalized key for near-duplicate detection."""
    normalized = re.sub(r"[^a-z0-9\s]", "", headline.lower())
    words = normalized.split()[:8]
    return " ".join(words)


def _extract_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.removeprefix("www.")
    except Exception:
        return ""


def _strip_mirror_suffix(domain: str) -> str:
    """Strip country-code TLD suffix so investing.com.uk → investing.com."""
    return _MIRROR_SUFFIX_RE.sub("", domain)
