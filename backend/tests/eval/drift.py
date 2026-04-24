"""Drift detection against last-good snapshots.

Drift checks are *warnings*, not failures. They catch silent regressions —
e.g. "NVDA used to come out HOLD @0.58, now it's SELL @0.3 with the same
data". That can be a real model behavior change worth reviewing, or it can be
legitimate signal movement. Either way, surface it.

Snapshots live under tests/eval/golden/<TICKER>.json. Re-record with
--update-golden on `run_eval.py`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_GOLDEN_DIR = Path(__file__).parent / "golden"
_CONFIDENCE_DRIFT_THRESHOLD = 0.2


def golden_path(ticker: str) -> Path:
    return _GOLDEN_DIR / f"{ticker.upper()}.json"


def snapshot_of(state: dict[str, Any]) -> dict[str, Any]:
    """Reduce a full graph state to the shape we care about for drift."""
    syn = state["synthesis"]
    return {
        "ticker": syn.ticker,
        "signal": str(syn.signal),
        "confidence": syn.layers.confidence,
        "top_3_signals": list(syn.layers.top_3_signals),
        "verdict": syn.layers.verdict,
        "key_uncertainty": syn.layers.key_uncertainty,
        "recommended_position_pct": syn.recommended_position_pct,
    }


def load_golden(ticker: str) -> dict[str, Any] | None:
    path = golden_path(ticker)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_golden(ticker: str, snapshot: dict[str, Any]) -> Path:
    _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = golden_path(ticker)
    path.write_text(json.dumps(snapshot, indent=2, default=str))
    return path


def compare_to_golden(
    current: dict[str, Any], golden: dict[str, Any]
) -> list[str]:
    """Returns human-readable drift notes. Empty list = no notable drift."""
    notes: list[str] = []

    if current["signal"] != golden["signal"]:
        notes.append(
            f"signal flipped: {golden['signal']} -> {current['signal']}"
        )

    delta = abs(current["confidence"] - golden["confidence"])
    if delta > _CONFIDENCE_DRIFT_THRESHOLD:
        notes.append(
            f"confidence moved {delta:+.2f} "
            f"({golden['confidence']:.2f} -> {current['confidence']:.2f})"
        )

    # Keyword-overlap check on top_3_signals: if there's zero overlap across
    # both sets after lowercasing, the thesis has rotated meaningfully.
    def _tokens(signals: list[str]) -> set[str]:
        out: set[str] = set()
        for s in signals:
            for word in s.lower().split():
                w = word.strip(".,:;'\"()[]")
                if len(w) > 4:  # skip stopwords-ish
                    out.add(w)
        return out

    current_tokens = _tokens(current["top_3_signals"])
    golden_tokens = _tokens(golden["top_3_signals"])
    if current_tokens and golden_tokens and not (current_tokens & golden_tokens):
        notes.append(
            "top_3_signals share zero substantive keywords with golden — "
            "thesis may have rotated"
        )

    return notes
