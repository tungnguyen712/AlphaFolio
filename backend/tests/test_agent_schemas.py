"""Schema-level smoke tests — no LLM, no network.

Validates that:
  - The Pydantic agent I/O types can round-trip through JSON.
  - The NVDA fixtures actually parse under the schemas (catches shape drift
    between providers and agents fast).
  - VerdictLayer enforces the product rule (1-3 top signals, confidence 0..1).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.agents import (
    AnalystChange,
    CongressTrade,
    ConsensusData,
    MacroContext,
    PriceSummary,
    VerdictLayer,
    VolumeAnomaly,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def test_polygon_fixture_shapes_match_schemas() -> None:
    data = json.loads((_FIXTURES / "polygon" / "NVDA.json").read_text())

    PriceSummary.model_validate(data["price_series"])
    [VolumeAnomaly.model_validate(v) for v in data["volume_anomalies"]]
    [AnalystChange.model_validate(a) for a in data["analyst_changes"]]
    MacroContext.model_validate(data["macro_context"])


def test_quiver_fixture_shape_matches_congress_trade() -> None:
    data = json.loads((_FIXTURES / "quiver" / "NVDA.json").read_text())
    trades = [CongressTrade.model_validate(t) for t in data["congress_trades"]]
    assert trades[0].member == "Pelosi, N."
    assert trades[0].transaction == "buy"


def test_analyst_change_aliases_parse_wire_shape() -> None:
    # The Polygon payload uses `from`/`to`/`pt_from`/`pt_to`/`date`. Aliases
    # let us accept that shape without renaming fixtures.
    raw = {
        "firm": "Morgan Stanley",
        "action": "upgrade",
        "from": "overweight",
        "to": "overweight+top-pick",
        "pt_from": 950,
        "pt_to": 1050,
        "date": "2026-04-08",
    }
    parsed = AnalystChange.model_validate(raw)
    assert parsed.from_rating == "overweight"
    assert parsed.to_rating == "overweight+top-pick"
    assert parsed.price_target_to == 1050
    assert str(parsed.published_at) == "2026-04-08"


def test_verdict_layer_requires_nonempty_top_signals() -> None:
    with pytest.raises(ValidationError):
        VerdictLayer(
            verdict="BUY",
            top_3_signals=[],
            key_uncertainty="earnings next week",
            confidence=0.7,
        )


def test_verdict_layer_rejects_more_than_three_signals() -> None:
    with pytest.raises(ValidationError):
        VerdictLayer(
            verdict="BUY",
            top_3_signals=["a", "b", "c", "d"],
            key_uncertainty="x",
            confidence=0.7,
        )


def test_verdict_layer_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        VerdictLayer(
            verdict="BUY",
            top_3_signals=["a"],
            key_uncertainty="x",
            confidence=1.5,
        )


# ---------------------------------------------------------------------------
# ConsensusData
# ---------------------------------------------------------------------------


def test_consensus_data_full_round_trip() -> None:
    raw = {
        "current_price": 150.0,
        "target_low": 120.0,
        "target_high": 220.0,
        "target_mean": 180.0,
        "target_median": 175.0,
        "number_of_analyst_opinions": 12,
        "recommendation_key": "buy",
        "recommendation_mean": 2.1,
        "strong_buy": 4,
        "buy": 5,
        "hold": 3,
        "sell": 0,
        "strong_sell": 0,
        "eps_current_quarter": 1.20,
        "eps_current_year": 4.80,
        "eps_next_year": 5.50,
        "implied_upside_pct": 20.0,
    }
    c = ConsensusData.model_validate(raw)
    assert c.recommendation_key == "buy"
    assert c.number_of_analyst_opinions == 12
    assert c.implied_upside_pct == 20.0
    assert c.strong_buy == 4


def test_consensus_data_all_none_is_valid() -> None:
    """An empty dict must produce a valid ConsensusData (all fields optional)."""
    c = ConsensusData.model_validate({})
    assert c.current_price is None
    assert c.implied_upside_pct is None


def test_consensus_data_json_round_trip() -> None:
    c = ConsensusData(current_price=100.0, target_mean=130.0, implied_upside_pct=30.0)
    dumped = c.model_dump(mode="json")
    restored = ConsensusData.model_validate(dumped)
    assert restored.implied_upside_pct == 30.0
