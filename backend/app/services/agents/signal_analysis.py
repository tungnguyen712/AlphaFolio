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

Your job: read the provided data bundle and produce a ranked list of bull/bear signals.

Bundle fields (use all that are non-empty):
  - financial_facts.quarters: SEC XBRL quarterly revenue, net income, EPS, operating income.
    These are the highest-reliability fundamental signals — compute YoY growth by comparing
    quarters[0] vs quarters[4] (same period prior year). Always build a fundamental signal
    from financial_facts when quarters is non-empty.
  - material_events: SEC 8-K filings with item codes. Key codes to weight heavily:
      5.02 = officer departure/appointment (CEO/CFO change — HIGH impact)
      4.01 = auditor change (HIGH bearish impact)
      2.06 = material impairment (BEARISH)
      2.01 = acquisition/disposition (directional depends on deal terms)
      1.01 = material agreement (read description — CHIPS Act, major deal, etc.)
  - insider_filings / insider_summary: Form 4 transactions
  - risk_factors: 10-K Item 1A text
  - news_items: recent headlines
  - analyst_changes: rating changes
  - macro_context: rate/macro environment
  - analyst_consensus: Yahoo Finance aggregate price targets + recommendation distribution

## Analyst Consensus rules
  recommendation_mean scale: 1.0 = Strong Buy, 2.0 = Buy, 3.0 = Hold, 4.0 = Underperform, 5.0 = Strong Sell.
  - implied_upside_pct > +20% AND number_of_analyst_opinions ≥ 5: bullish signal, strength 0.5–0.7 depending on conviction spread.
  - implied_upside_pct < −10%: bearish signal, strength 0.4–0.6.
  - Thin coverage (number_of_analyst_opinions < 3): cap signal strength at 0.4 and add a 'thin_analyst_coverage' flag.
  - Consensus should corroborate fundamental/insider signals, not stand alone. Do NOT emit a pure-consensus signal as the only evidence for a verdict.
  - If analyst_consensus is null or absent: emit a flag 'analyst_consensus_unavailable' and proceed without it.
  - source kind for consensus signals: kind="market_data", quality="aggregator".

Signal rules:
  - Every signal MUST cite at least one source. Do not invent sources.
  - strength is your confidence in the *signal*, not the overall thesis.
  - Use neutral direction only for genuinely mixed evidence, not as a hedge.
  - Flag data gaps in the `flags` list so Synthesis can weight them.
  - 3-7 signals is the right shape. Don't pad. Don't conflate multiple items.
  - financial_facts signals should reference the specific quarter and USD amounts.
  - material_events signals should reference the filed_at date and item codes.

Insider transaction rules:
  - Reason from insider_summary (unique_sellers, csuite_sellers, board_sellers,
    num_distinct_filings) rather than from raw transaction row count.
  - One filer with 10 line items in a single filing is NOT "broad selling".
  - planned_10b5_1 = weak-to-moderate bearish, not strong evidence of discretionary selling.
  - Absence of buys is worth mentioning but should not be over-weighted.

Analyst data rules:
  - If analyst_signal_source = "news_reported_analyst_signal", treat analyst data as
    low-confidence secondary information, not structured consensus.

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
    retrieved_dump = inputs.retrieved.model_dump(mode="json")
    # Surface high-value fields at the top level for easier LLM access
    insider_summary = retrieved_dump.pop("insider_summary", None)
    financial_facts = retrieved_dump.pop("financial_facts", None)
    material_events = retrieved_dump.pop("material_events", None)
    consensus = retrieved_dump.pop("consensus", None)
    payload = {
        "ticker": inputs.ticker,
        "financial_facts": financial_facts,
        "material_events": material_events,
        "insider_summary": insider_summary,
        "analyst_consensus": consensus,
        "retrieved": retrieved_dump,
        "market_intel": (
            inputs.market_intel.model_dump(mode="json") if inputs.market_intel else None
        ),
    }
    return (
        f"Analyze the bundle below for {inputs.ticker} and record your signals.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )
