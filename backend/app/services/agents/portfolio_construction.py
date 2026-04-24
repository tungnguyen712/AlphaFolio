"""Portfolio Construction agent (Sonnet tier).

Given current holdings + risk profile + candidate research verdicts, propose
a set of trades and target allocations. Output carries its own verdict/top-3/
uncertainty layer so the PortfolioRecommendation surface also renders in
VerdictCard.
"""
from __future__ import annotations

import json

from app.models.agents import PortfolioConstructionInput, PortfolioConstructionOutput
from app.services.llm.anthropic_client import AgentTier, call_structured

SYSTEM_PROMPT = """You are the Portfolio Construction agent.

Given a portfolio's current holdings, cash, risk profile, and a set of
candidate research verdicts, propose a set of trades plus target allocations.

Rules:
  - Respect the risk profile. Conservative = prefer trims over new adds;
    aggressive = willing to concentrate.
  - target_allocations sums to <= 1.0 (remainder stays in cash). Never exceed.
  - Every proposed_trade has a short rationale; if it traces to a research
    verdict, set links_to_report_ticker to that ticker.
  - The `layers` block populates the VerdictCard at the top of the
    recommendation. `layers.verdict` is the one-line headline; `top_3_signals`
    is the three strongest reasons to approve the plan; `key_uncertainty`
    names what could force a re-run. Calibrate confidence.
  - Prefer doing *less*: if candidates are weak or risk profile is already
    met, a HOLD recommendation with no trades is correct.

Call the record_output tool. No prose responses."""


async def run(inputs: PortfolioConstructionInput) -> PortfolioConstructionOutput:
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
    return (
        f"Propose trades and allocations for portfolio {inputs.portfolio_id}. "
        "Call record_output.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )
