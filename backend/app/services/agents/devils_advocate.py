"""Devil's Advocate agent (Opus tier).

Read the Signal Analysis output and stress-test it. If signals skew bullish,
make the strongest bear case and vice versa. Synthesis weighs both.
"""
from __future__ import annotations

import json

from app.models.agents import DevilsAdvocateInput, DevilsAdvocateOutput
from app.services.llm.anthropic_client import AgentTier, call_structured

SYSTEM_PROMPT = """You are the Devil's Advocate agent for a stock research system.

Your only job: stress-test the Signal Analysis output. Assume the author is
motivated to be right and has blind spots.

  - If the signals skew bullish, construct the strongest bear case. Flipped if
    bearish. If genuinely mixed, attack both sides.
  - Counterarguments must be specific and falsifiable — "management has a
    history of missing Q4 guidance when channel inventory is above 8 weeks"
    beats "execution risk".
  - Rank by severity honestly. A "low" severity argument is still worth
    writing if it's real; a forced "high" is worse than none.
  - Cite sources when you have them. It's fine to have none if you're pointing
    at a gap in the data.

Call the record_output tool. Do not produce free prose."""


async def run(inputs: DevilsAdvocateInput) -> DevilsAdvocateOutput:
    user_prompt = _build_user_prompt(inputs)
    return await call_structured(
        tier=AgentTier.OPUS,
        agent_name="devils_advocate",
        system=SYSTEM_PROMPT,
        user=user_prompt,
        output_model=DevilsAdvocateOutput,
        max_tokens=6000,
    )


def _build_user_prompt(inputs: DevilsAdvocateInput) -> str:
    payload = {
        "ticker": inputs.ticker,
        "signal_analysis": inputs.signal_analysis.model_dump(mode="json"),
    }
    return (
        f"Stress-test this research on {inputs.ticker}. Record your counterarguments "
        "and a worst_case_scenario.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )
