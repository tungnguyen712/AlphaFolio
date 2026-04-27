"""Unit tests for the post-retrieval news filter.

All tests are pure Python — no network, no LLM, no database.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.agents.common import NewsItem
from app.services.data_providers.news_filter import filter_news


def _item(
    headline: str,
    url: str = "https://reuters.com/article/1",
    snippet: str = "",
    published: date | None = None,
    source: str = "reuters",
    score: float = 0.9,
) -> NewsItem:
    return NewsItem(
        headline=headline,
        url=url,
        snippet=snippet,
        published=published,
        source=source,
        score=score,
    )


LOOKBACK = 90


class TestRelevanceFiltering:
    def test_relevant_article_kept(self):
        item = _item("META reports record Q4 earnings beat", url="https://reuters.com/1")
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 1
        assert len(dropped) == 0

    def test_unrelated_ticker_dropped(self):
        item = _item("Oracle signs cloud deal with US government", url="https://reuters.com/1")
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 0
        assert len(dropped) == 1
        assert dropped[0].reason == "unrelated_ticker"

    def test_ticker_in_snippet_keeps_article(self):
        item = _item(
            "Big Tech roundup",
            snippet="META posted strong results this quarter.",
            url="https://reuters.com/1",
        )
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 1

    def test_company_name_match_keeps_article(self):
        item = _item("Meta Platforms beats ad revenue estimates", url="https://reuters.com/1")
        kept, dropped = filter_news("META", [item], LOOKBACK, company_name="Meta Platforms")
        assert len(kept) == 1

    def test_short_ticker_word_boundary(self):
        # "AI" should match only as a whole word, not as part of "NVIDIA"
        item = _item("NVIDIA advances its AI chips lineup", url="https://reuters.com/1")
        kept, dropped = filter_news("AI", [item], LOOKBACK)
        # "AI" is a whole word in this headline, so it should be kept
        assert len(kept) == 1

    def test_ticker_substring_only_gives_weak_match(self):
        # Ticker "IT" should not match "UNITED" or similar substrings
        item = _item("Enterprise software market update", url="https://reuters.com/1")
        kept, dropped = filter_news("IT", [item], LOOKBACK)
        assert len(kept) == 0
        assert dropped[0].reason in ("unrelated_ticker", "weak_company_match")

    def test_msft_article_excluded_from_meta_run(self):
        item = _item("Microsoft Azure grows 30% YoY", url="https://bloomberg.com/1")
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 0
        assert dropped[0].reason == "unrelated_ticker"


class TestStalenessFilter:
    def test_stale_article_dropped(self):
        old_date = date.today() - timedelta(days=LOOKBACK + 10)
        item = _item("META earnings recap", published=old_date, url="https://reuters.com/1")
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 0
        assert dropped[0].reason == "stale_article"

    def test_fresh_article_kept(self):
        fresh_date = date.today() - timedelta(days=5)
        item = _item("META ad revenue up 18%", published=fresh_date, url="https://reuters.com/1")
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 1

    def test_no_published_date_not_dropped_for_staleness(self):
        item = _item("META launches new VR headset", url="https://reuters.com/1", published=None)
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 1


class TestDuplicateDeduplication:
    def test_duplicate_headline_dropped(self):
        item1 = _item("META earnings beat analyst estimates", url="https://reuters.com/1", score=0.9)
        item2 = _item("META earnings beat analyst estimates", url="https://cnbc.com/2", score=0.7)
        kept, dropped = filter_news("META", [item1, item2], LOOKBACK)
        assert len(kept) == 1
        assert len(dropped) == 1
        assert dropped[0].reason == "duplicate_headline"
        # First-seen (higher score since Tavily ranks descending) is kept
        assert kept[0].url == item1.url

    def test_different_headlines_both_kept(self):
        item1 = _item("META Q4 revenue beats expectations", url="https://reuters.com/1")
        item2 = _item("META raises dividend for first time", url="https://cnbc.com/2")
        kept, dropped = filter_news("META", [item1, item2], LOOKBACK)
        assert len(kept) == 2
        assert len(dropped) == 0

    def test_investing_com_mirror_deduplicated(self):
        # Country-suffix mirror domain — second item has same headline AND mirror domain
        item1 = _item("META ad revenue Q4 results", url="https://investing.com/1", score=0.9)
        item2 = _item("META ad revenue Q4 results", url="https://investing.com.de/1", score=0.8)
        kept, dropped = filter_news("META", [item1, item2], LOOKBACK)
        # Second is duplicate of first — dropped as duplicate_headline (checked before mirror)
        assert len(kept) == 1
        assert len(dropped) == 1


class TestDomainFiltering:
    def test_mirrored_domain_dropped(self):
        item = _item(
            "META Q4 preview",
            url="https://investing.com.br/article/meta-preview",
        )
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 0
        assert dropped[0].reason == "mirrored_domain"

    def test_low_quality_source_dropped(self):
        item = _item(
            "META is a buy says analyst",
            url="https://seekingalpha.com/article/meta-buy",
        )
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 0
        assert dropped[0].reason == "low_quality_source"

    def test_reputable_source_kept(self):
        item = _item("META announces AI research lab", url="https://reuters.com/technology/meta")
        kept, dropped = filter_news("META", [item], LOOKBACK)
        assert len(kept) == 1


class TestReturnTypes:
    def test_returns_correct_types(self):
        items = [
            _item("META Q4 results", url="https://reuters.com/1"),
            _item("Oracle deal", url="https://reuters.com/2"),
        ]
        kept, dropped = filter_news("META", items, LOOKBACK)
        assert isinstance(kept, list)
        assert isinstance(dropped, list)
        from app.models.agents.common import FilteredNewsItem, NewsItem
        for k in kept:
            assert isinstance(k, NewsItem)
        for d in dropped:
            assert isinstance(d, FilteredNewsItem)
