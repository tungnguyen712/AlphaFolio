"""Portfolio flow — LangGraph composition.

    START ──▶ portfolio_construction ──▶ END

MVP is a single-node graph: the API layer hands in pre-computed Synthesis
outputs as `candidates`. The graph shape (StateGraph with typed state) is
preserved so stage 3.5 persistence can treat research and portfolio runs
uniformly, and so we have a clean place to add future nodes (e.g. a
risk-check node before construction, or a rebalance-trigger emitter after).
"""
from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.models.agents import (
    HoldingSnapshot,
    PortfolioConstructionInput,
    PortfolioConstructionOutput,
    SynthesisOutput,
)
from app.models.db.enums import RiskProfile
from app.services.agents import portfolio_construction


class PortfolioState(TypedDict, total=False):
    # Inputs.
    portfolio_id: str
    holdings: list[HoldingSnapshot]
    cash_balance: Decimal
    risk_profile: RiskProfile
    candidates: list[SynthesisOutput]
    objective: str

    # Outputs.
    recommendation: PortfolioConstructionOutput


def new_portfolio_state(
    *,
    portfolio_id: str,
    holdings: list[HoldingSnapshot],
    cash_balance: Decimal,
    risk_profile: RiskProfile,
    candidates: list[SynthesisOutput] | None = None,
    objective: str | None = None,
) -> PortfolioState:
    state: PortfolioState = PortfolioState(
        portfolio_id=portfolio_id,
        holdings=holdings,
        cash_balance=cash_balance,
        risk_profile=risk_profile,
        candidates=candidates or [],
    )
    if objective is not None:
        state["objective"] = objective
    return state


# ---------------------------------------------------------------------------
# Nodes.
# ---------------------------------------------------------------------------


async def _portfolio_construction_node(state: PortfolioState) -> dict:
    kwargs = {
        "portfolio_id": state["portfolio_id"],
        "holdings": state["holdings"],
        "cash_balance": state["cash_balance"],
        "risk_profile": state["risk_profile"],
        "candidates": state.get("candidates") or [],
    }
    if "objective" in state:
        kwargs["objective"] = state["objective"]

    out = await portfolio_construction.run(PortfolioConstructionInput(**kwargs))
    return {"recommendation": out}


# ---------------------------------------------------------------------------
# Graph factory.
# ---------------------------------------------------------------------------


def build_portfolio_graph() -> CompiledStateGraph:
    graph: StateGraph = StateGraph(PortfolioState)
    graph.add_node("portfolio_construction", _portfolio_construction_node)
    graph.add_edge(START, "portfolio_construction")
    graph.add_edge("portfolio_construction", END)
    return graph.compile()
