"""Invariant checks over a research-graph final state.

An *invariant* is a property that should hold regardless of what the LLM
decides for a given ticker — e.g. "Synthesis emits at least one source",
"Devil's Advocate produces at least 2 counterarguments". If an invariant
fails, the agent layer is broken (prompt drift, model swap, schema loss)
and the human should look. Verdicts themselves (BUY/HOLD/SELL, confidence
number, specific top_3 content) are NOT invariants — they're expected to
move with the data.

Each invariant is a `(name, check)` pair. `check` takes the final state dict
and returns either None (pass) or a human-readable string (fail reason).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.models.agents import (
    DevilsAdvocateOutput,
    SignalAnalysisOutput,
    SynthesisOutput,
)

CheckResult = str | None  # None = pass; non-empty str = fail reason
CheckFn = Callable[[dict[str, Any]], CheckResult]


@dataclass
class Invariant:
    name: str
    check: CheckFn


# ---------------------------------------------------------------------------
# Signal Analysis
# ---------------------------------------------------------------------------


def _signals_present(state: dict[str, Any]) -> CheckResult:
    sigs: SignalAnalysisOutput = state["signals"]
    if len(sigs.signals) < 3:
        return f"Expected >= 3 signals, got {len(sigs.signals)}"
    return None


def _signals_have_direction_mix(state: dict[str, Any]) -> CheckResult:
    """Healthy analysis produces bull AND bear evidence. If the agent is stuck
    one-sided across 5+ signals, something's off — either prompt drift or the
    DA-style balance prompt isn't being honored."""
    sigs: SignalAnalysisOutput = state["signals"]
    if len(sigs.signals) < 5:
        return None  # not enough signals to expect a mix
    directions = {s.direction for s in sigs.signals}
    if {"bullish", "bearish"} - directions:
        return (
            f"All {len(sigs.signals)} signals are {directions} — expected both "
            "bullish and bearish represented at this signal count"
        )
    return None


# ---------------------------------------------------------------------------
# Devil's Advocate
# ---------------------------------------------------------------------------


def _devils_advocate_counterarguments_present(state: dict[str, Any]) -> CheckResult:
    da: DevilsAdvocateOutput = state["devils_advocate"]
    if len(da.counterarguments) < 2:
        return f"Expected >= 2 counterarguments, got {len(da.counterarguments)}"
    return None


def _devils_advocate_has_worst_case(state: dict[str, Any]) -> CheckResult:
    da: DevilsAdvocateOutput = state["devils_advocate"]
    if len(da.worst_case_scenario) < 100:
        return (
            f"worst_case_scenario is only {len(da.worst_case_scenario)} chars — "
            "expected a substantive (>100 char) narrative"
        )
    return None


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------


def _synthesis_verdict_layer_well_formed(state: dict[str, Any]) -> CheckResult:
    syn: SynthesisOutput = state["synthesis"]
    layers = syn.layers
    issues: list[str] = []
    if not layers.verdict or len(layers.verdict) < 10:
        issues.append(f"verdict too short: {layers.verdict!r}")
    if not (1 <= len(layers.top_3_signals) <= 3):
        issues.append(f"top_3_signals count out of range: {len(layers.top_3_signals)}")
    if not layers.key_uncertainty or len(layers.key_uncertainty) < 20:
        issues.append(f"key_uncertainty too short: {layers.key_uncertainty!r}")
    if not (0.0 <= layers.confidence <= 1.0):
        issues.append(f"confidence out of range: {layers.confidence}")
    return "; ".join(issues) if issues else None


def _synthesis_has_sources(state: dict[str, Any]) -> CheckResult:
    syn: SynthesisOutput = state["synthesis"]
    if not syn.sources:
        return "Synthesis sources list is empty"
    return None


def _synthesis_rationale_substantive(state: dict[str, Any]) -> CheckResult:
    syn: SynthesisOutput = state["synthesis"]
    if len(syn.rationale) < 300:
        return f"rationale is {len(syn.rationale)} chars — expected a multi-paragraph narrative"
    return None


def _synthesis_position_pct_consistent_with_signal(state: dict[str, Any]) -> CheckResult:
    """BUY should have a non-null recommended_position_pct; HOLD/SELL should not.

    Inconsistency here means the Synthesis prompt's constraint didn't hold —
    worth surfacing because downstream Portfolio Construction depends on it.
    """
    syn: SynthesisOutput = state["synthesis"]
    signal = str(syn.signal)
    rec = syn.recommended_position_pct
    if signal == "buy" and rec is None:
        return "signal=buy but recommended_position_pct is None"
    if signal in ("hold", "sell") and rec is not None:
        return f"signal={signal} but recommended_position_pct={rec} (should be None)"
    return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


ALL_INVARIANTS: list[Invariant] = [
    Invariant("signals.count>=3", _signals_present),
    # "signals.sources_nonempty" removed — Signal.sources has min_length=1
    # at the Pydantic layer already, so this invariant could never fire.
    Invariant("signals.direction_mix", _signals_have_direction_mix),
    Invariant("devils_advocate.counterarguments>=2", _devils_advocate_counterarguments_present),
    Invariant("devils_advocate.worst_case_substantive", _devils_advocate_has_worst_case),
    Invariant("synthesis.verdict_layer_well_formed", _synthesis_verdict_layer_well_formed),
    Invariant("synthesis.sources_nonempty", _synthesis_has_sources),
    Invariant("synthesis.rationale_substantive", _synthesis_rationale_substantive),
    Invariant("synthesis.position_pct_consistent", _synthesis_position_pct_consistent_with_signal),
]


def run_invariants(state: dict[str, Any]) -> list[tuple[str, CheckResult]]:
    """Run every invariant against a final research state. Returns a list of
    (invariant_name, result) tuples — result is None on pass."""
    return [(inv.name, inv.check(state)) for inv in ALL_INVARIANTS]
