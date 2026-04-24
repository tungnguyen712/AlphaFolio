"""Signal Analysis agent (Opus tier).

Takes the retrieved data + market intel, emits a ranked list of bull/bear
signals. Every signal must carry at least one source — so a downstream
reviewer (or the Devil's Advocate) can check the work.
"""
from __future__ import annotations

import json

from app.models.agents import (
    SignalAnalysisInput,
    SignalAnalysisOutput,
)
from app.services.llm.anthropic_client import AgentTier, call_structured

SYSTEM_PROMPT = """You are the Signal Analysis agent for a stock research system.

Your job: read the provided data bundle (insider filings, congress trades,
10-K risk factors, recent news, analyst changes, macro context) and produce a
ranked list of bull/bear signals.

Rules:
  - Every signal MUST cite at least one source (from the data provided). Do
    not invent sources.
  - strength is your confidence in the *signal*, not the overall thesis.
  - Use neutral direction only for genuinely mixed evidence, not as a hedge.
  - Flag data gaps (e.g. "no 10-K excerpt available") in the `flags` list so
    the Synthesis agent can weight them.
  - 3-7 signals is the right shape. Don't pad. Don't conflate multiple items
    into one signal.

You must call the record_output tool. No prose responses."""


async def run(inputs: SignalAnalysisInput) -> SignalAnalysisOutput:
    user_prompt = _build_user_prompt(inputs)
    return await call_structured(
        tier=AgentTier.OPUS,
        system=SYSTEM_PROMPT,
        user=user_prompt,
        output_model=SignalAnalysisOutput,
        max_tokens=6000,
    )


def _build_user_prompt(inputs: SignalAnalysisInput) -> str:
    payload = {
        "ticker": inputs.ticker,
        "retrieved": inputs.retrieved.model_dump(mode="json"),
        "market_intel": (
            inputs.market_intel.model_dump(mode="json") if inputs.market_intel else None
        ),
    }
    return (
        f"Analyze the bundle below for {inputs.ticker} and record your signals.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )
