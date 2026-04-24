"""Research flow — LangGraph composition.

    START ──▶ data_retrieval ─┐
        └──▶ market_intel    ─┴─▶ signal_analysis ─▶ devils_advocate ─▶ synthesis ─▶ END

Parallel fan-out at START for the two data-gathering nodes; LangGraph waits
for both to finish before firing signal_analysis (barrier semantics — each
node in a `StateGraph` runs only after all its parents complete).

Nodes return dict updates, not full state. Each one writes to its own key so
there are no conflicting reducers.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.models.agents import (
    DataRetrievalInput,
    DataRetrievalOutput,
    DevilsAdvocateInput,
    DevilsAdvocateOutput,
    MarketIntelInput,
    MarketIntelOutput,
    SignalAnalysisInput,
    SignalAnalysisOutput,
    SynthesisInput,
    SynthesisOutput,
)
from app.services.agents import (
    data_retrieval,
    devils_advocate,
    market_intel,
    signal_analysis,
    synthesis,
)


class ResearchState(TypedDict, total=False):
    # Inputs (set by the caller via new_research_state).
    ticker: str
    lookback_days: int
    portfolio_id: str | None

    # Populated as the graph executes.
    retrieved: DataRetrievalOutput
    market_intel: MarketIntelOutput
    signals: SignalAnalysisOutput
    devils_advocate: DevilsAdvocateOutput
    synthesis: SynthesisOutput


def new_research_state(
    *, ticker: str, lookback_days: int = 90, portfolio_id: str | None = None
) -> ResearchState:
    """Build the initial state for a research run.

    Centralized so the API layer (stage 4) and tests have a single way to
    kick off a graph — no bare dict literals scattered around.
    """
    return ResearchState(
        ticker=ticker.upper(),
        lookback_days=lookback_days,
        portfolio_id=portfolio_id,
    )


# ---------------------------------------------------------------------------
# Nodes — thin adapters between graph state and typed agent I/O.
# ---------------------------------------------------------------------------


async def _data_retrieval_node(state: ResearchState) -> dict:
    out = await data_retrieval.run(
        DataRetrievalInput(
            ticker=state["ticker"],
            lookback_days=state.get("lookback_days", 90),
        )
    )
    return {"retrieved": out}


async def _market_intel_node(state: ResearchState) -> dict:
    out = await market_intel.run(
        MarketIntelInput(
            ticker=state["ticker"],
            lookback_days=state.get("lookback_days", 90),
        )
    )
    return {"market_intel": out}


async def _signal_analysis_node(state: ResearchState) -> dict:
    out = await signal_analysis.run(
        SignalAnalysisInput(
            ticker=state["ticker"],
            retrieved=state["retrieved"],
            market_intel=state.get("market_intel"),
        )
    )
    return {"signals": out}


async def _devils_advocate_node(state: ResearchState) -> dict:
    out = await devils_advocate.run(
        DevilsAdvocateInput(
            ticker=state["ticker"],
            signal_analysis=state["signals"],
        )
    )
    return {"devils_advocate": out}


async def _synthesis_node(state: ResearchState) -> dict:
    out = await synthesis.run(
        SynthesisInput(
            ticker=state["ticker"],
            signal_analysis=state["signals"],
            devils_advocate=state["devils_advocate"],
            market_intel=state.get("market_intel"),
            portfolio_id=state.get("portfolio_id"),
        )
    )
    return {"synthesis": out}


# ---------------------------------------------------------------------------
# Graph factory.
# ---------------------------------------------------------------------------


def build_research_graph() -> CompiledStateGraph:
    """Return a freshly compiled research graph.

    Called once at app startup (stage 4) or per-test. Checkpointing is left
    for stage 3.5; the compiled graph is safe to reuse across requests —
    state is per-invocation, not held on the graph object.
    """
    graph: StateGraph = StateGraph(ResearchState)

    graph.add_node("data_retrieval", _data_retrieval_node)
    graph.add_node("market_intel", _market_intel_node)
    graph.add_node("signal_analysis", _signal_analysis_node)
    graph.add_node("devils_advocate", _devils_advocate_node)
    graph.add_node("synthesis", _synthesis_node)

    # Parallel fan-out: both data-gathering agents start immediately.
    graph.add_edge(START, "data_retrieval")
    graph.add_edge(START, "market_intel")

    # Barrier: signal_analysis runs only after BOTH parents complete.
    graph.add_edge("data_retrieval", "signal_analysis")
    graph.add_edge("market_intel", "signal_analysis")

    graph.add_edge("signal_analysis", "devils_advocate")
    graph.add_edge("devils_advocate", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()
