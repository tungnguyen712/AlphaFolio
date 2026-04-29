"""Synthesis agent (Opus tier).

Final judge for the research flow. Takes Signal Analysis + Devil's Advocate
(+ optional Market Intel + pre-built ValuationBridge + ValidationResult),
emits a full equity research memo in SynthesisOutput.
"""
from __future__ import annotations

import json
import re

from app.models.agents import SynthesisInput, SynthesisOutput
from app.models.agents.synthesis import SECTION_HEADINGS
from app.services.llm.anthropic_client import AgentTier, call_structured

SYSTEM_PROMPT = """You are the Synthesis agent — the final judge in a stock research flow.

Write `rationale` as structured equity research memo prose. The rationale MUST contain
exactly 8 sections in this exact order. Each section MUST begin with its number, name,
and a colon on the same line as the opening content — no separate heading lines:

1. Recommendation: State the signal (buy/hold/sell) and a one-line verdict with sizing guidance.
Example: "1. Recommendation: HOLD — do not initiate at current prices; revisit on a pullback below $310."

2. Investment Thesis: 2–4 sentences on the core bull/bear setup and why this ticker is worth watching.

3. Top Signals: The 1–3 signals that matter most, each explicitly citing at least one source.

4. Valuation Bridge: Interpret the valuation_bridge data. Reference bull/base/bear scenario prices.
State missing metrics explicitly (e.g. "forward P/E unavailable from structured data").
Do not invent multiples or fair values not derivable from the input.

5. Key Uncertainties: The single most important thing that could invalidate the thesis. Name the specific
metric, event, or filing that would change the recommendation.

6. Devil's Advocate: The strongest counterargument. Name what evidence would confirm it.
Include worst-case scenario price if the devil's advocate provided one.

7. Data Quality: Disclose: validation_result warnings and errors; analyst_signal_source (structured vs
news-reported); missing price/valuation fields; insider aggregation note (unique
sellers vs raw transaction rows); whether any news was filtered.

8. Final Rationale: 2–4 sentences tying signals → rating → sizing → confidence. No new facts. Concise.

---
FORMAT RULES (strictly enforced):
- Each section MUST start with `N. Section Name:` (number, dot, space, exact name, colon) on the same line as the content.
- Do NOT use Markdown headings (no ##).
- Do NOT use asterisks `**...**` for section labels.
- Use plain prose in section bodies. Inline bold for specific figures is fine.
- Separate each section with a blank line.

NON-NEGOTIABLES (same as before):
- `signal` must be buy, hold, or sell. Pick one.
- `layers.verdict` is one actionable line; include sizing guidance for BUY.
- `layers.top_3_signals` is 1–3 items ordered by weight.
- `layers.key_uncertainty` names one thing only.
- `layers.confidence` = calibrated probability MINUS validation_result.confidence_penalty.
  If validation_result.errors is non-empty, confidence must not exceed 0.50.
  If validation_result.warnings count >= 3, reduce confidence by an additional 0.05.
- `recommended_position_pct` only for BUY. Null for HOLD/SELL.
- Every claim in `rationale` traces to signal_analysis or devil's advocate.
- Price targets: follow in_portfolio / signal / current_price rules.
  If current_price is null → both targets null.
- `confidence_breakdown`: positive_contributors and negative_contributors as short strings.
  final_score = post-penalty confidence value.
- `valuation_bridge`, `validation_result`, `insider_summary`: pass through unchanged.

Call record_output. Never respond with free prose."""


def _parse_rationale_sections(rationale: str) -> dict[str, str]:
    """Extract numbered or ## heading sections from the rationale string.

    Handles both:
    - New format: "1. Recommendation: content..." (numbered inline)
    - Old format: "## Recommendation\nbody..." (Markdown H2)

    Returns a dict mapping heading name → section body text.
    """
    # Try new numbered format first: "1. Section Name: body..."
    numbered_re = re.compile(r"^(\d+)\.\s+([^:\n]+):\s*", re.MULTILINE)
    matches = list(numbered_re.finditer(rationale))
    if matches:
        sections: dict[str, str] = {}
        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            body_start = match.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(rationale)
            body = rationale[body_start:body_end].strip()
            sections[heading] = body
        return sections
    # Fall back to old ## heading format
    heading_re = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    old_matches = list(heading_re.finditer(rationale))
    sections = {}
    for i, match in enumerate(old_matches):
        heading = match.group(1).strip()
        body_start = match.end()
        body_end = old_matches[i + 1].start() if i + 1 < len(old_matches) else len(rationale)
        body = rationale[body_start:body_end].strip()
        sections[heading] = body
    return sections


async def run(inputs: SynthesisInput) -> SynthesisOutput:
    user_prompt = _build_user_prompt(inputs)
    result = await call_structured(
        tier=AgentTier.OPUS,
        system=SYSTEM_PROMPT,
        user=user_prompt,
        output_model=SynthesisOutput,
        max_tokens=8000,
    )
    # Parse structured sections from rationale and override pass-through fields
    sections = _parse_rationale_sections(result.rationale)
    return result.model_copy(
        update={
            "report_sections": sections if sections else None,
            "valuation_bridge": result.valuation_bridge or inputs.valuation_bridge,
            "validation_result": result.validation_result or inputs.validation_result,
            "insider_summary": result.insider_summary or inputs.insider_summary,
        }
    )


def _build_user_prompt(inputs: SynthesisInput) -> str:
    payload: dict = {
        "ticker": inputs.ticker,
        "signal_analysis": inputs.signal_analysis.model_dump(mode="json"),
        "devils_advocate": inputs.devils_advocate.model_dump(mode="json"),
        "market_intel": (
            inputs.market_intel.model_dump(mode="json") if inputs.market_intel else None
        ),
        "portfolio_id": inputs.portfolio_id,
        "in_portfolio": inputs.in_portfolio,
        "current_price": inputs.current_price,
        "insider_summary": (
            inputs.insider_summary.model_dump(mode="json") if inputs.insider_summary else None
        ),
        "valuation_bridge": (
            inputs.valuation_bridge.model_dump(mode="json") if inputs.valuation_bridge else None
        ),
        "validation_result": (
            inputs.validation_result.model_dump(mode="json") if inputs.validation_result else None
        ),
    }
    historical_note = ""
    if inputs.as_of_date:
        historical_note = (
            f"\n\nHISTORICAL RESEARCH CONTEXT: This run is dated {inputs.as_of_date}. "
            "Every price timestamp, filing date, and news date at or before that date is CORRECT and INTENTIONAL — "
            "this is point-in-time historical analysis, not stale live data. "
            "Do NOT flag timestamps as 'stale' or 'may be outdated'. "
            "Frame the recommendation as 'what the evidence suggested on {inputs.as_of_date}' rather than present tense."
        )
    return (
        f"Synthesize the research on {inputs.ticker} into a final ResearchReport. "
        "Use ## headings as specified. Call record_output."
        f"{historical_note}\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )
