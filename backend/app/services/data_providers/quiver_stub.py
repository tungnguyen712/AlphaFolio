"""Fixture-backed Quiver stub (Congress trades)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.config import get_settings

_STUB_LATENCY_SECONDS = 0.3


class QuiverFixtureMissingError(LookupError):
    pass


async def fetch_congress_trades(ticker: str) -> list[dict[str, Any]]:
    """Return a list of Congress trade records for `ticker`.

    Real Quiver endpoint is /beta/historical/congresstrading/{ticker}.
    Stub returns the `congress_trades` array from the fixture; empty list
    if no fixture exists (absence is legitimate for most tickers).
    """
    settings = get_settings()
    fixture_path = Path(settings.quiver_stub_fixtures) / f"{ticker.upper()}.json"
    if not fixture_path.exists():
        await asyncio.sleep(_STUB_LATENCY_SECONDS)
        return []

    await asyncio.sleep(_STUB_LATENCY_SECONDS)
    data = json.loads(fixture_path.read_text())
    return data.get("congress_trades", [])
