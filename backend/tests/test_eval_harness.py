"""Unit tests for the eval harness — invariants and drift detection.

Pure Python, no DB, no LLM. Builds canned final states and asserts the
invariants/drift-checks return what they should.
"""
from __future__ import annotations

from app.models.agents import (
    Counterargument,
    DevilsAdvocateOutput,
    Signal,
    SignalAnalysisOutput,
    SourceRef,
    SynthesisOutput,
    VerdictLayer,
)
from app.models.db.enums import ResearchSignal
from tests.eval.drift import compare_to_golden, snapshot_of
from tests.eval.invariants import run_invariants

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _sig(name: str, direction: str = "bullish") -> Signal:
    return Signal(
        name=name,
        direction=direction,
        strength=0.5,
        rationale="because reasons that are long enough to be taken seriously",
        sources=[SourceRef(kind="sec_filing", label="ref")],
    )


def _good_state(signal: ResearchSignal = ResearchSignal.HOLD) -> dict:
    """A final state that satisfies every invariant."""
    return {
        "signals": SignalAnalysisOutput(
            ticker="NVDA",
            signals=[
                _sig("a", "bullish"),
                _sig("b", "bullish"),
                _sig("c", "bearish"),
                _sig("d", "bearish"),
                _sig("e", "neutral"),
            ],
            flags=[],
        ),
        "devils_advocate": DevilsAdvocateOutput(
            ticker="NVDA",
            counterarguments=[
                Counterargument(claim="c1", severity="medium", evidence="e1", sources=[]),
                Counterargument(claim="c2", severity="high", evidence="e2", sources=[]),
            ],
            worst_case_scenario=(
                "If the downside realizes over the next two quarters, the stock drops "
                "to the $120-$140 range as multiple compression meets estimate cuts and "
                "hyperscaler substitution accelerates."
            ),
        ),
        "synthesis": SynthesisOutput(
            ticker="NVDA",
            signal=signal,
            layers=VerdictLayer(
                verdict="HOLD — wait for May guide",
                top_3_signals=["beat and raise", "insider cluster sell", "hyperscaler risk"],
                key_uncertainty="whether May guidance confirms Rubin ramp vs. decelerates",
                confidence=0.58,
            ),
            rationale=(
                "Paragraph one reasoning goes here and extends long enough to clear "
                "the 300-char minimum invariant threshold — this is the same kind of "
                "substantive narrative we would expect from real Synthesis output, "
                "covering the bull case, the bear case, and why we landed where we "
                "did overall. A second paragraph would normally follow discussing the "
                "position sizing logic and the key catalyst to watch."
            ),
            recommended_position_pct=None if signal != ResearchSignal.BUY else 0.03,
            sources=[SourceRef(kind="sec_filing", label="NVDA 10-K")],
        ),
    }


# ---------------------------------------------------------------------------
# Invariants — pass path
# ---------------------------------------------------------------------------


def test_invariants_all_pass_on_healthy_state() -> None:
    results = run_invariants(_good_state())
    failures = [(n, r) for n, r in results if r]
    assert failures == []


# ---------------------------------------------------------------------------
# Invariants — targeted failures
# ---------------------------------------------------------------------------


def test_signals_count_invariant_fails_on_short_list() -> None:
    state = _good_state()
    state["signals"] = SignalAnalysisOutput(
        ticker="NVDA",
        signals=[_sig("only-one")],
        flags=[],
    )
    results = dict(run_invariants(state))
    assert results["signals.count>=3"] is not None


def test_signals_direction_mix_fails_when_one_sided() -> None:
    state = _good_state()
    state["signals"] = SignalAnalysisOutput(
        ticker="NVDA",
        signals=[_sig(f"b{i}", "bullish") for i in range(5)],
        flags=[],
    )
    results = dict(run_invariants(state))
    assert results["signals.direction_mix"] is not None


def test_devils_advocate_invariant_fails_with_one_counter() -> None:
    state = _good_state()
    state["devils_advocate"] = DevilsAdvocateOutput(
        ticker="NVDA",
        counterarguments=[
            Counterargument(claim="only", severity="low", evidence="-", sources=[])
        ],
        worst_case_scenario="x" * 200,
    )
    results = dict(run_invariants(state))
    assert results["devils_advocate.counterarguments>=2"] is not None


def test_synthesis_position_pct_inconsistency_caught() -> None:
    # signal=sell but a pct is set — should fail the consistency invariant.
    state = _good_state(signal=ResearchSignal.SELL)
    state["synthesis"] = state["synthesis"].model_copy(
        update={"recommended_position_pct": 0.05}
    )
    results = dict(run_invariants(state))
    assert results["synthesis.position_pct_consistent"] is not None


def test_synthesis_rationale_invariant_fails_on_short() -> None:
    state = _good_state()
    state["synthesis"] = state["synthesis"].model_copy(update={"rationale": "too short"})
    results = dict(run_invariants(state))
    assert results["synthesis.rationale_substantive"] is not None


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


def test_drift_identical_snapshots_produce_no_notes() -> None:
    state = _good_state()
    snap = snapshot_of(state)
    assert compare_to_golden(snap, snap) == []


def test_drift_detects_signal_flip() -> None:
    current = snapshot_of(_good_state(signal=ResearchSignal.BUY))
    golden = snapshot_of(_good_state(signal=ResearchSignal.SELL))
    notes = compare_to_golden(current, golden)
    assert any("signal flipped" in n for n in notes)


def test_drift_detects_confidence_jump() -> None:
    current = snapshot_of(_good_state())
    golden_state = _good_state()
    golden_state["synthesis"] = golden_state["synthesis"].model_copy(
        update={
            "layers": golden_state["synthesis"].layers.model_copy(
                update={"confidence": 0.1}
            )
        }
    )
    golden = snapshot_of(golden_state)
    notes = compare_to_golden(current, golden)
    assert any("confidence moved" in n for n in notes)


def test_drift_detects_keyword_rotation() -> None:
    current = snapshot_of(_good_state())
    rotated_state = _good_state()
    rotated_state["synthesis"] = rotated_state["synthesis"].model_copy(
        update={
            "layers": rotated_state["synthesis"].layers.model_copy(
                update={
                    "top_3_signals": [
                        "inflation slowdown",
                        "housing weakness",
                        "yield curve inversion",
                    ]
                }
            )
        }
    )
    golden = snapshot_of(rotated_state)
    notes = compare_to_golden(current, golden)
    assert any("rotated" in n for n in notes)
