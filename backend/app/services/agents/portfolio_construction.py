"""Portfolio Construction agent (Sonnet tier).

Given current holdings + risk profile + candidate research verdicts, propose
a set of trades and target allocations. Output carries its own verdict/top-3/
uncertainty layer so the PortfolioRecommendation surface also renders in
VerdictCard.

Before calling the LLM the agent runs a deterministic mean-variance / max-Sharpe
optimizer (scipy). The solver produces mathematically optimal weights from
90-day historical returns; the LLM's job is to narrate and adjust those weights
against the candidate research verdicts, not to invent numbers.
"""
from __future__ import annotations

import json

from app.models.agents import PortfolioConstructionInput, PortfolioConstructionOutput
from app.services.llm.anthropic_client import AgentTier, call_structured
from app.services.pipeline.portfolio_solver import SolverResult, solve_async

SYSTEM_PROMPT = """You are the Portfolio Construction agent.

You receive the portfolio's current holdings, cash, risk profile, candidate
research verdicts, AND the output of a deterministic mean-variance / max-Sharpe
optimizer (solver_result). Your job is to:

  1. Use solver_result.weights as the STARTING POINT for target_allocations.
     You may deviate from solver weights only when a strong research signal or
     risk-profile constraint justifies it — explain any deviation explicitly.
  2. Translate weight changes into proposed_trades (buy / sell / trim / add).
  3. Respect the risk profile. Conservative = prefer trims; aggressive = willing
     to concentrate up to the solver’s max-weight cap.
  4. target_allocations sums to <= 1.0 (remainder stays in cash). Never exceed.
  5. Every proposed_trade has a short rationale; if it traces to a research
     verdict, set links_to_report_ticker to that ticker.
  6. The `layers` block populates the VerdictCard. `layers.verdict` is the
     one-line headline; `top_3_signals` is the three strongest reasons to
     approve the plan; `key_uncertainty` names what could force a re-run.
  7. Prefer doing *less*: if candidates are weak or risk profile is already
     met, a HOLD with no trades is correct.
  8. If solver_result.method == "equal_weight" (fallback), note it in the
     rationale and rely more heavily on qualitative judgment.

Call the record_output tool. No prose responses."""


async def run(inputs: PortfolioConstructionInput) -> PortfolioConstructionOutput:
    # Run optimizer unless the caller pre-populated solver_result
    if inputs.solver_result is None:
        tickers = [h.ticker for h in inputs.holdings]
        solver = await solve_async(tickers, inputs.risk_profile)
        inputs = inputs.model_copy(update={"solver_result": solver})

    user_prompt = _build_user_prompt(inputs)
    return await call_structured(
        tier=AgentTier.SONNET,
        system=SYSTEM_PROMPT,
        user=user_prompt,
        output_model=PortfolioConstructionOutput,
        max_tokens=6000,
    )


def _build_user_prompt(inputs: PortfolioConstructionInput) -> str:
    payload = inputs.model_dump(mode="json")
    solver = inputs.solver_result
    solver_summary = (
        f"Optimizer method: {solver.method} | "
        f"Expected annual return: {solver.expected_annual_return_pct}% | "
        f"Expected annual volatility: {solver.expected_annual_volatility_pct}% | "
        f"Sharpe ratio: {solver.sharpe_ratio} | "
        f"Lookback: {solver.lookback_days} days"
        if solver
        else "Solver not available"
    )
    return (
        f"Propose trades and allocations for portfolio {inputs.portfolio_id}.\n"
        f"Solver summary: {solver_summary}\n"
        "Use solver_result.weights as the allocation baseline. Call record_output.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )
