"""Fixture-backed Polygon stub.

Identical return shape to the real client we'll build later, so swapping in
Polygon's live API is a one-file change. Reads `<ticker>.json` from the
directory in settings.polygon_stub_fixtures.

Small artificial delay so the SSE progress timeline looks realistic during
frontend development — cut it if it becomes annoying in tests.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.config import get_settings

_STUB_LATENCY_SECONDS = 0.4


class PolygonFixtureMissingError(LookupError):
    """Raised when no fixture exists for the requested ticker."""


async def fetch_market_intel(ticker: str) -> dict[str, Any]:
    """Return price_series, volume_anomalies, analyst_changes, macro_context.

    The real Polygon client will hit /v2/aggs/ticker, /vX/reference/news,
    etc. in parallel and assemble the same dict. Stub just loads JSON.
    """
    settings = get_settings()
    fixture_path = Path(settings.polygon_stub_fixtures) / f"{ticker.upper()}.json"
    if not fixture_path.exists():
        raise PolygonFixtureMissingError(
            f"No Polygon fixture for {ticker} at {fixture_path}. "
            f"Add one at tests/fixtures/polygon/{ticker.upper()}.json."
        )

    await asyncio.sleep(_STUB_LATENCY_SECONDS)
    return json.loads(fixture_path.read_text())
