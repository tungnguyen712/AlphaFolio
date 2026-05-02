"""Condition extractor — converts a finished SynthesisOutput into watch triggers.

Two layers:
  Layer A (deterministic, no LLM):
    • BUY  + entry_price_target  → PRICE_BELOW trigger
    • SELL + exit_price_target   → PRICE_ABOVE trigger
    • Live run (no as_of_date)   → EARNINGS_DATE trigger via yfinance calendar

  Layer B (Haiku, one call per report):
    • Parses key_uncertainty + "Key Uncertainties" section text
    • Outputs a list of watch conditions with optional date or offset_days
    • Date found     → CUSTOM trigger with fires_at set
    • No date found  → CUSTOM trigger fires_at = now + offset_days (default 30)

All triggers are returned as unsaved RebalanceTrigger ORM objects; the
caller (execute_research_run) bulk-inserts them in the same session.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import Field

from app.models.agents.common import AgentModel
from app.models.agents.synthesis import SynthesisOutput
from app.models.db.enums import RebalanceTriggerKind, ResearchSignal
from app.models.db.rebalance_trigger import RebalanceTrigger
from app.services.llm.anthropic_client import AgentTier, call_structured

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Haiku output schema
# ---------------------------------------------------------------------------


class _WatchCondition(AgentModel):
    description: str = Field(
        description="Short human-readable label, e.g. 'Q4 earnings beat/miss', 'FDA PDUFA decision'"
    )
    fires_at: date | None = Field(
        default=None,
        description="Specific calendar date extracted from the text (ISO format). Null if not mentioned.",
    )
    offset_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days from today to fire the reminder when no specific date is found.",
    )


class _WatchList(AgentModel):
    conditions: list[_WatchCondition] = Field(
        default_factory=list,
        description="List of watch conditions. Empty list if there are no actionable catalysts.",
    )


_HAIKU_SYSTEM = (
    "You are a financial analyst assistant. Extract actionable watch conditions from "
    "research report text. A watch condition is an event or catalyst the analyst "
    "explicitly says to wait for before acting (e.g. earnings beat, product launch, "
    "regulatory decision, macro inflection). Do NOT invent conditions not in the text. "
    "Output only what is explicitly mentioned as a reason to wait or monitor. "
    "Call record_output."
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_triggers(
    synthesis_out: SynthesisOutput,
    user_id: UUID,
    report_id: UUID,
    ticker: str,
    as_of_date: date | None = None,
) -> list[RebalanceTrigger]:
    """Return unsaved RebalanceTrigger rows for a finished research report.

    Runs Layer A (deterministic) and Layer B (Haiku) concurrently.
    Never raises — logs errors and returns whatever was collected.
    """
    layer_a, layer_b = await asyncio.gather(
        _layer_a(synthesis_out, user_id, report_id, ticker, as_of_date),
        _layer_b(synthesis_out, user_id, report_id, ticker),
        return_exceptions=True,
    )

    triggers: list[RebalanceTrigger] = []
    if isinstance(layer_a, list):
        triggers.extend(layer_a)
    else:
        logger.warning("condition_extractor layer_a error for %s: %s", ticker, layer_a)

    if isinstance(layer_b, list):
        triggers.extend(layer_b)
    else:
        logger.warning("condition_extractor layer_b error for %s: %s", ticker, layer_b)

    return triggers


# ---------------------------------------------------------------------------
# Layer A — deterministic
# ---------------------------------------------------------------------------


async def _layer_a(
    synth: SynthesisOutput,
    user_id: UUID,
    report_id: UUID,
    ticker: str,
    as_of_date: date | None,
) -> list[RebalanceTrigger]:
    triggers: list[RebalanceTrigger] = []
    base_condition: dict[str, Any] = {"ticker": ticker, "report_id": str(report_id)}

    # Price targets
    if synth.signal == ResearchSignal.BUY and synth.layers.entry_price_target:
        pt = synth.layers.entry_price_target
        triggers.append(
            RebalanceTrigger(
                user_id=user_id,
                portfolio_id=None,
                kind=RebalanceTriggerKind.PRICE_BELOW,
                condition_json={
                    **base_condition,
                    "threshold": pt.price,
                    "horizon": pt.horizon,
                    "rationale": pt.rationale,
                },
                fires_at=None,  # polled by price loop
                active=True,
            )
        )

    if synth.signal == ResearchSignal.SELL and synth.layers.exit_price_target:
        pt = synth.layers.exit_price_target
        triggers.append(
            RebalanceTrigger(
                user_id=user_id,
                portfolio_id=None,
                kind=RebalanceTriggerKind.PRICE_ABOVE,
                condition_json={
                    **base_condition,
                    "threshold": pt.price,
                    "horizon": pt.horizon,
                    "rationale": pt.rationale,
                },
                fires_at=None,
                active=True,
            )
        )

    # Earnings date — skip for historical (as_of) runs to prevent look-ahead bias
    if as_of_date is None:
        earnings_dt = await _fetch_next_earnings(ticker)
        if earnings_dt:
            triggers.append(
                RebalanceTrigger(
                    user_id=user_id,
                    portfolio_id=None,
                    kind=RebalanceTriggerKind.EARNINGS_DATE,
                    condition_json={**base_condition, "description": f"{ticker} earnings"},
                    fires_at=datetime.combine(earnings_dt, datetime.min.time()).replace(
                        tzinfo=UTC
                    ),
                    active=True,
                )
            )
            # Also schedule a post-earnings beat/miss check for the following day
            triggers.append(
                RebalanceTrigger(
                    user_id=user_id,
                    portfolio_id=None,
                    kind=RebalanceTriggerKind.EARNINGS_BEAT_CHECK,
                    condition_json={
                        **base_condition,
                        "earnings_date": earnings_dt.isoformat(),
                        "eps_estimate": (
                            synth.sources  # fall-through; actual estimate lives in consensus
                            and None  # will be filled by beat task from yfinance
                        ),
                    },
                    fires_at=datetime.combine(
                        earnings_dt + timedelta(days=1), datetime.min.time()
                    ).replace(tzinfo=UTC),
                    active=True,
                )
            )

    return triggers


async def _fetch_next_earnings(ticker: str) -> date | None:
    """Fetch next earnings date from yfinance (runs in thread pool)."""
    def _sync() -> date | None:
        try:
            import yfinance as yf  # noqa: PLC0415

            info = yf.Ticker(ticker).calendar
            if info is None:
                return None
            # calendar is a dict with key "Earnings Date" → list[datetime] or Timestamp
            earnings = info.get("Earnings Date")
            if not earnings:
                return None
            first = earnings[0] if isinstance(earnings, list) else earnings
            # pandas Timestamp or datetime
            if hasattr(first, "date"):
                return first.date()
            return None
        except Exception as exc:
            logger.debug("_fetch_next_earnings %s: %s", ticker, exc)
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync)


# ---------------------------------------------------------------------------
# Layer B — Haiku extraction
# ---------------------------------------------------------------------------


async def _layer_b(
    synth: SynthesisOutput,
    user_id: UUID,
    report_id: UUID,
    ticker: str,
) -> list[RebalanceTrigger]:
    # Build the text corpus from the most informative fields
    sections = synth.report_sections or {}
    text_parts = [
        f"key_uncertainty: {synth.layers.key_uncertainty}",
    ]
    if key_unc := sections.get("Key Uncertainties"):
        text_parts.append(f"Key Uncertainties section: {key_unc}")
    if thesis := sections.get("Investment Thesis"):
        text_parts.append(f"Investment Thesis: {thesis}")

    user_prompt = (
        f"Ticker: {ticker}\nSignal: {synth.signal}\n\n"
        + "\n\n".join(text_parts)
        + "\n\nExtract watch conditions. Call record_output."
    )

    try:
        watch_list: _WatchList = await call_structured(
            tier=AgentTier.HAIKU,
            system=_HAIKU_SYSTEM,
            user=user_prompt,
            output_model=_WatchList,
            max_tokens=512,
        )
    except Exception as exc:
        logger.warning("condition_extractor layer_b LLM error for %s: %s", ticker, exc)
        return []

    now = datetime.now(UTC)
    base_condition: dict[str, Any] = {"ticker": ticker, "report_id": str(report_id)}
    triggers: list[RebalanceTrigger] = []

    for cond in watch_list.conditions:
        if cond.fires_at:
            fires_at = datetime.combine(cond.fires_at, datetime.min.time()).replace(tzinfo=UTC)
        else:
            fires_at = now + timedelta(days=cond.offset_days)

        # Skip if the extracted date is in the past
        if fires_at <= now:
            continue

        triggers.append(
            RebalanceTrigger(
                user_id=user_id,
                portfolio_id=None,
                kind=RebalanceTriggerKind.CUSTOM,
                condition_json={
                    **base_condition,
                    "description": cond.description,
                    "offset_days": cond.offset_days,
                },
                fires_at=fires_at,
                active=True,
            )
        )

    return triggers
