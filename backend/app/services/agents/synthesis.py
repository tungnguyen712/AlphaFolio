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

SYSTEM_PROMPT = """You are the Synthesis agent, the final judge in a stock research flow.

Write `rationale` as a short, plain-English research note for someone deciding whether to
buy, hold or sell this stock. The rationale MUST contain exactly 3 sections in this exact order.
Each section MUST begin with its number, name, and a colon on the same line as the opening
content, no separate heading lines:

1. Recommendation: What to do, stated for a new buyer and for someone who already owns the stock,
with sizing guidance for BUY. Finish with one or two sentences on what result or event would change
the call (name the specific metric, event or filing and the level that would flip it).
Example: "1. Recommendation: **HOLD. Do not initiate at current prices.** Wait for a pullback below $310 or a quarter that confirms growth above 13%."

2. Investment Thesis: The story in plain English: why this company is worth watching, what is
working, what is not, and how the current price compares with the bull, base and bear scenario
prices in valuation_bridge. Cite sources for the facts that matter most. Do not invent multiples or
fair values that are not derivable from the input.

3. Devil's Advocate: The strongest case against your call, what evidence would confirm it, and the
worst-case price if the devil's advocate provided one.

READER RULES:
- The reader is not an analyst. Never mention internal names or mechanics: field names
  (market_cap, forward_pe, analyst_changes, insider_summary), validation warnings or errors, the
  confidence penalty, how data was retrieved, filtered or aggregated, or which step produced something.
  Do not say "valuation bridge", "signal analysis" or "devil's advocate" inside the prose either: say
  "our price scenarios" or "the bear case" instead.
- Mention missing data only when it genuinely changes the conclusion, in one short plain sentence
  (for example "we could not get a P/E ratio for this company").
- Do not restate the verdict, the confidence number or the three signals; the page already shows them.

---
FORMAT RULES (strictly enforced):
- Each section MUST start with `N. Section Name:` (number, dot, space, exact name, colon) on the same line as the content.
- Do NOT use Markdown headings (no ##).
- Do NOT use asterisks for section labels: the `N. Section Name:` label itself is never bold.
- BOLD LEAD: begin every section body with the 1 to 2 most important sentences, wrapped together in
  **double asterisks**. The lead must stand on its own: a reader who stops right after the bold text
  still gets the key point of that section. Use bold ONLY for this lead, never anywhere else.
- After the bold lead, add supporting detail in short paragraphs of 2 to 3 sentences, separated by a
  blank line. Leave out detail that only repeats the lead.
- For 3 or more parallel items (scenarios, risks) use lines that start with `- `.
  Never start a line inside a section with a number and a dot, because that marks a new section.
- Write plain English a non-expert can follow. Avoid jargon and stacked parentheticals.
- Separate each section with a blank line.

SIGNAL DECISION RULES, follow these strictly:
- BUY: net bullish signals clearly outweigh bearish (e.g. strong revenue growth, momentum,
  analyst upgrades, insider buying) AND no hard validation error. Missing valuation metrics
  alone (market_cap, forward_pe, ev_revenue) are NOT a reason to downgrade to HOLD, they
  are a disclosure item, not a veto. Say BUY with lower confidence and note the gap.
- SELL: net bearish signals clearly outweigh bullish AND no compelling bull thesis survives
  the devil's advocate.
- HOLD: genuine ambiguity only, bull and bear signals are roughly balanced in strength,
  OR there is a binary catalyst (pending ruling, earnings in <2 weeks) that makes direction
  unpredictable. HOLD is NOT the default for missing data. Missing data lowers confidence;
  it does not change a bullish read to neutral.

In plain terms: if signal_analysis shows 3 bullish signals at strength 0.7+ and 1 bearish
at 0.4, say BUY. If it shows 2 bullish at 0.5 and 2 bearish at 0.6, say HOLD. If it shows
3 bearish at 0.7+ and 1 bullish at 0.3, say SELL.

NON-NEGOTIABLES:
- `layers` MUST contain ALL of: `verdict`, `top_3_signals`, `key_uncertainty`, `confidence`
  (a number between 0 and 1, never omitted), `entry_price_target`, `exit_price_target` (null when not applicable).
- `signal` must be buy, hold, or sell. Pick one using the rules above.
- `layers.verdict` is one actionable line; include sizing guidance for BUY.
- `layers.top_3_signals` is 1–3 items ordered by weight, each a plain sentence a reader would say aloud.
  No pipeline names such as "devil's advocate" or "insider_summary" inside them.
- `layers.key_uncertainty` is one or two plain sentences naming the single thing the reader should
  watch. No jargon or field names.
- `layers.confidence` = calibrated probability MINUS validation_result.confidence_penalty.
  If validation_result.errors is non-empty, confidence must not exceed 0.50.
  The validation_result.confidence_penalty already accounts for warning count and
  data-quality gaps, do NOT apply any additional penalty for warning count here.
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
        agent_name="synthesis",
        system=SYSTEM_PROMPT,
        user=user_prompt,
        output_model=SynthesisOutput,
        max_tokens=10000,
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
            "Every price timestamp, filing date, and news date at or before that date is CORRECT and INTENTIONAL, "
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
