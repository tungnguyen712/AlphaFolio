
"""Unit tests for the pre-synthesis validation gate and valuation bridge.

Pure Python — no network, no LLM, no database.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.models.agents.common import InsiderSummary, NewsItem, PriceSummary, SourceRef
from app.models.agents.synthesis import ValidationResult, ValuationBridge
from app.services.pipeline.valuation_bridge import build_valuation_bridge
from app.services.pipeline.validation import validate_research_inputs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_retrieved(
    price_summary: PriceSummary | None = None,
    insider_filings: list = (),
    insider_summary: InsiderSummary | None = None,
) -> MagicMock:
    obj = MagicMock()
    obj.price_summary = price_summary
    obj.insider_filings = list(insider_filings)
    obj.insider_summary = insider_summary
    return obj


def _make_market_intel(
    analyst_signal_source: str = "structured",
    analyst_changes: list = (),
    news_items: list = (),
) -> MagicMock:
    obj = MagicMock()
    obj.analyst_signal_source = analyst_signal_source
    obj.analyst_changes = list(analyst_changes)
    obj.news_items = list(news_items)
    return obj


def _make_signal(name: str, sources: list[SourceRef] | None = None) -> MagicMock:
    sig = MagicMock()
    sig.name = name
    sig.sources = sources if sources is not None else [MagicMock()]
    return sig


def _make_signals(signals: list) -> MagicMock:
    obj = MagicMock()
    obj.signals = signals
    return obj


def _price_summary(**kwargs) -> PriceSummary:
    defaults = {"latest": 100.0}
    defaults.update(kwargs)
    return PriceSummary(**defaults)


# ---------------------------------------------------------------------------
# Validation gate tests
# ---------------------------------------------------------------------------


class TestValidationGate:
    def test_passes_when_data_clean(self):
        retrieved = _make_retrieved(price_summary=_price_summary())
        market_intel = _make_market_intel(news_items=[MagicMock()])
        signals = _make_signals([_make_signal("revenue_growth")])

        result = validate_research_inputs("AAPL", retrieved, market_intel, signals)

        assert result.passed is True
        # Some warnings are expected for missing fields (market_cap, forward_pe, etc.)
        assert len(result.errors) == 0

    def test_errors_on_missing_price_summary(self):
        retrieved = _make_retrieved(price_summary=None)
        market_intel = _make_market_intel(news_items=[MagicMock()])
        signals = _make_signals([_make_signal("revenue_growth")])

        result = validate_research_inputs("AAPL", retrieved, market_intel, signals)

        assert result.passed is False
        assert any("price data" in e.lower() for e in result.errors)

    def test_warns_on_missing_market_cap(self):
        ps = _price_summary(market_cap=None)
        retrieved = _make_retrieved(price_summary=ps)
        market_intel = _make_market_intel(news_items=[MagicMock()])
        signals = _make_signals([_make_signal("signal_a")])

        result = validate_research_inputs("AAPL", retrieved, market_intel, signals)

        assert any("market_cap" in w for w in result.warnings)

    def test_errors_on_unsourced_signal(self):
        ps = _price_summary()
        retrieved = _make_retrieved(price_summary=ps)
        market_intel = _make_market_intel(news_items=[MagicMock()])
        # Signal with no sources
        signals = _make_signals([_make_signal("bad_signal", sources=[])])

        result = validate_research_inputs("AAPL", retrieved, market_intel, signals)

        assert result.passed is False
        assert any("bad_signal" in e for e in result.errors)

    def test_warns_on_news_reported_analyst(self):
        ps = _price_summary()
        retrieved = _make_retrieved(price_summary=ps)
        market_intel = _make_market_intel(
            analyst_signal_source="news_reported_analyst_signal",
            news_items=[MagicMock()],
        )
        signals = _make_signals([_make_signal("revenue")])

        result = validate_research_inputs("META", retrieved, market_intel, signals)

        assert any("news snippets" in w.lower() or "analyst_changes" in w.lower() for w in result.warnings)

    def test_warns_on_stale_analyst_data(self):
        ps = _price_summary()
        retrieved = _make_retrieved(price_summary=ps)
        stale_analyst = MagicMock()
        stale_analyst.published_at = date.today() - timedelta(days=200)
        market_intel = _make_market_intel(
            analyst_signal_source="structured",
            analyst_changes=[stale_analyst],
            news_items=[MagicMock()],
        )
        signals = _make_signals([_make_signal("revenue")])

        result = validate_research_inputs("AAPL", retrieved, market_intel, signals)

        assert any("stale" in w.lower() for w in result.warnings)

    def test_warns_on_no_news_after_filtering(self):
        ps = _price_summary()
        retrieved = _make_retrieved(price_summary=ps)
        market_intel = _make_market_intel(news_items=[])  # empty after filtering
        signals = _make_signals([_make_signal("revenue")])

        result = validate_research_inputs("AAPL", retrieved, market_intel, signals)

        assert any("news" in w.lower() for w in result.warnings)

    def test_confidence_penalty_accumulates(self):
        # 2 warnings from market cap + forward_pe missing + 1 error from unsourced signal
        ps = _price_summary(market_cap=None, forward_pe=None)
        retrieved = _make_retrieved(price_summary=ps)
        market_intel = _make_market_intel(news_items=[MagicMock()])
        signals = _make_signals([_make_signal("bad", sources=[])])

        result = validate_research_inputs("TEST", retrieved, market_intel, signals)

        # At minimum 2 warnings (market_cap, forward_pe) + 1 error → 0.05*2 + 0.15 = 0.25
        assert result.confidence_penalty >= 0.20
        assert result.passed is False

    def test_confidence_penalty_capped_at_50_percent(self):
        ps = _price_summary(market_cap=None, forward_pe=None, ev_revenue=None, high_52w=None, low_52w=None)
        retrieved = _make_retrieved(price_summary=ps)
        # Many unsourced signals
        bad_signals = [_make_signal(f"bad_{i}", sources=[]) for i in range(10)]
        signals = _make_signals(bad_signals)
        market_intel = _make_market_intel()

        result = validate_research_inputs("TEST", retrieved, market_intel, signals)

        assert result.confidence_penalty <= 0.50

    def test_warns_on_no_insider_data(self):
        ps = _price_summary()
        retrieved = _make_retrieved(price_summary=ps, insider_filings=[])
        market_intel = _make_market_intel(news_items=[MagicMock()])
        signals = _make_signals([_make_signal("revenue")])

        result = validate_research_inputs("AAPL", retrieved, market_intel, signals)

        assert any("form 4" in w.lower() or "insider" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Valuation bridge tests
# ---------------------------------------------------------------------------


class TestValuationBridge:
    def test_scenarios_computed_from_price(self):
        ps = _price_summary(latest=100.0)
        retrieved = _make_retrieved(price_summary=ps)

        bridge = build_valuation_bridge(retrieved, None)

        assert len(bridge.scenarios) == 3
        bull = next(s for s in bridge.scenarios if s.label == "bull")
        bear = next(s for s in bridge.scenarios if s.label == "bear")
        base = next(s for s in bridge.scenarios if s.label == "base")

        assert bull.price_target == pytest.approx(125.0)
        assert bear.price_target == pytest.approx(82.0)
        assert base.price_target == pytest.approx(108.0)
        assert bull.implied_upside_pct == pytest.approx(25.0)
        assert bear.implied_upside_pct == pytest.approx(-18.0)

    def test_no_scenarios_when_no_price(self):
        retrieved = _make_retrieved(price_summary=None)
        bridge = build_valuation_bridge(retrieved, None)
        assert len(bridge.scenarios) == 0
        assert "current_price" in bridge.missing_fields

    def test_missing_fields_tracked(self):
        ps = _price_summary(market_cap=None, forward_pe=None, ev_revenue=None)
        retrieved = _make_retrieved(price_summary=ps)
        bridge = build_valuation_bridge(retrieved, None)
        assert "market_cap" in bridge.missing_fields
        assert "forward_pe" in bridge.missing_fields
        assert "ev_revenue" in bridge.missing_fields

    def test_available_fields_not_in_missing(self):
        ps = _price_summary(market_cap=1_000_000_000.0, forward_pe=25.0)
        retrieved = _make_retrieved(price_summary=ps)
        bridge = build_valuation_bridge(retrieved, None)
        assert "market_cap" not in bridge.missing_fields
        assert "forward_pe" not in bridge.missing_fields

    def test_returns_valuation_bridge_instance(self):
        retrieved = _make_retrieved(price_summary=_price_summary())
        result = build_valuation_bridge(retrieved, None)
        assert isinstance(result, ValuationBridge)

    def test_current_price_propagated(self):
        ps = _price_summary(latest=542.75)
        retrieved = _make_retrieved(price_summary=ps)
        bridge = build_valuation_bridge(retrieved, None)
        assert bridge.current_price == pytest.approx(542.75)

    def test_market_intel_none_is_ok(self):
        retrieved = _make_retrieved(price_summary=_price_summary())
        # Should not raise when market_intel is None
        bridge = build_valuation_bridge(retrieved, None)
        assert bridge is not None
