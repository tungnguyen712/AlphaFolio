"""Smoke tests for the data-provider layer.

Runs inside the backend container against the dev postgres. Cache test
cleans up its own rows; other tests don't touch the DB.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.db import SignalCache
from app.services.data_providers._cache import (
    AsyncRateLimiter,
    cache_get,
    cache_set,
    cached_fetch,
    make_cache_key,
)
from app.services.data_providers.polygon_stub import fetch_market_intel
from app.services.data_providers.quiver_stub import fetch_congress_trades
from app.services.data_providers.sec_edgar import _parse_form4_xml
from app.services.data_providers import yahoo_consensus
from app.models.agents import ConsensusData


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


async def test_polygon_stub_returns_nvda_fixture() -> None:
    data = await fetch_market_intel("NVDA")
    assert data["price_series"]["latest"] == 195.40
    assert data["analyst_changes"][0]["firm"] == "Morgan Stanley"
    assert data["macro_context"]["fed_funds"] == 4.25


async def test_quiver_stub_returns_nvda_trades() -> None:
    trades = await fetch_congress_trades("NVDA")
    assert len(trades) == 1
    assert trades[0]["member"] == "Pelosi, N."


async def test_quiver_stub_empty_for_unknown_ticker() -> None:
    trades = await fetch_congress_trades("ZZZZ_NOT_A_TICKER")
    assert trades == []


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


async def test_rate_limiter_serializes_concurrent_acquires() -> None:
    limiter = AsyncRateLimiter(rps=5.0)  # 200ms between acquires
    start = asyncio.get_event_loop().time()
    await asyncio.gather(limiter.acquire(), limiter.acquire(), limiter.acquire())
    elapsed = asyncio.get_event_loop().time() - start
    # First is free, next two wait ~200ms each → ≥0.4s total.
    assert elapsed >= 0.35, f"limiter did not serialize: elapsed={elapsed}"


# ---------------------------------------------------------------------------
# Form 4 XML parser
# ---------------------------------------------------------------------------


_SAMPLE_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerName>Huang, Jensen</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isOfficer>1</isOfficer>
      <officerTitle>CEO</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding>
        <transactionCode>S</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>120000</value></transactionShares>
        <transactionPricePerShare><value>892.40</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionCoding>
        <transactionCode>A</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><value>0</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def test_form4_parser_extracts_open_market_trades_only() -> None:
    filing = {
        "accession_nodash": "000104581026000015",
        "filed_at": "2026-03-11",
        "primary_doc": "primary_doc.xml",
        "cik": "1045810",
    }
    txs = _parse_form4_xml(_SAMPLE_FORM4_XML, filing)
    # Grant (code A) is filtered out; only the open-market sell remains.
    assert len(txs) == 1
    tx = txs[0]
    assert tx["filer"] == "Huang, Jensen"
    assert tx["role"] == "CEO"
    assert tx["transaction"] == "sell"
    assert tx["shares"] == 120000.0
    assert tx["price"] == 892.40
    assert tx["value_usd"] == 107088000.0
    assert tx["filed_at"] == "2026-03-11"


# ---------------------------------------------------------------------------
# Cache decorator (hits real DB)
# ---------------------------------------------------------------------------


async def test_cache_decorator_serves_second_call_from_db() -> None:
    call_count = 0
    ns = "test.cache.roundtrip"

    def key(x: int) -> str:
        return make_cache_key(ns, x=x)

    @cached_fetch(key_fn=key, ttl_seconds=60)
    async def provider(x: int) -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"x": x, "doubled": x * 2}

    try:
        first = await provider(21)
        second = await provider(21)
        assert first == second == {"x": 21, "doubled": 42}
        assert call_count == 1, "decorator did not short-circuit the second call"
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(SignalCache).where(SignalCache.cache_key.like(f"{ns}:%"))
            )
            await session.commit()


async def test_cache_get_miss_returns_none() -> None:
    assert await cache_get("definitely.not.a.real.key:xyz") is None


@pytest.mark.asyncio
async def test_cache_set_then_get_roundtrip() -> None:
    key = make_cache_key("test.cache.setget", id="abc")
    try:
        await cache_set(key, {"hello": "world"}, ttl_seconds=60)
        assert await cache_get(key) == {"hello": "world"}
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(SignalCache).where(SignalCache.cache_key == key))
            await session.commit()


# ---------------------------------------------------------------------------
# yahoo_consensus provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_consensus_returns_none_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider must swallow all exceptions and return None."""
    def _boom(ticker: str) -> dict:  # type: ignore[return]
        raise RuntimeError("network error")

    monkeypatch.setattr(yahoo_consensus, "_sync_fetch", _boom)
    # Bypass the cache decorator so _sync_fetch is actually called.
    monkeypatch.setattr(yahoo_consensus, "_fetch_raw", yahoo_consensus._sync_fetch)

    result = await yahoo_consensus.fetch_consensus("AAPL")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_consensus_parses_financial_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_consensus maps Yahoo's camelCase keys to ConsensusData correctly."""
    _FAKE_RAW = {
        "financial_data": {
            "currentPrice": 150.0,
            "targetMeanPrice": 185.0,
            "targetLowPrice": 130.0,
            "targetHighPrice": 220.0,
            "targetMedianPrice": 182.0,
            "numberOfAnalystOpinions": 10,
            "recommendationKey": "buy",
            "recommendationMean": 2.0,
        },
        "recommendation_trend": {
            "strongBuy": 3,
            "buy": 4,
            "hold": 3,
            "sell": 0,
            "strongSell": 0,
        },
        "eps_estimates": {
            "current_quarter": 1.10,
            "current_year": 4.40,
            "next_year": 5.20,
        },
    }

    async def _fake_fetch_raw(ticker: str) -> dict:
        return _FAKE_RAW

    monkeypatch.setattr(yahoo_consensus, "_fetch_raw", _fake_fetch_raw)

    result = await yahoo_consensus.fetch_consensus("AAPL")
    assert isinstance(result, ConsensusData)
    assert result.current_price == 150.0
    assert result.target_mean == 185.0
    assert result.recommendation_key == "buy"
    assert result.strong_buy == 3
    assert result.buy == 4
    assert result.eps_current_year == 4.40
    # implied_upside_pct = (185 - 150) / 150 * 100 = 23.33...
    assert result.implied_upside_pct is not None
    assert abs(result.implied_upside_pct - 23.33) < 0.01


@pytest.mark.asyncio
async def test_fetch_consensus_handles_empty_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty dicts from Yahoo (e.g. ticker not found) must yield a valid object."""
    async def _fake_fetch_raw(ticker: str) -> dict:
        return {"financial_data": {}, "recommendation_trend": {}, "eps_estimates": {}}

    monkeypatch.setattr(yahoo_consensus, "_fetch_raw", _fake_fetch_raw)

    result = await yahoo_consensus.fetch_consensus("ZZZZ")
    assert isinstance(result, ConsensusData)
    assert result.current_price is None
    assert result.implied_upside_pct is None
