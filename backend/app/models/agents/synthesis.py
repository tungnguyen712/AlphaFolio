"""Synthesis agent I/O (Opus).

Final judge. Weighs Signal Analysis + Devil's Advocate, emits the verdict/
top-3-signals/key-uncertainty surface that the UI renders in VerdictCard.
Also produces a plain-English rationale the user can read.
"""
from __future__ import annotations

from pydantic import Field

from app.models.agents.common import AgentModel, SourceRef, VerdictLayer
from app.models.agents.devils_advocate import DevilsAdvocateOutput
from app.models.agents.market_intel import MarketIntelOutput
from app.models.agents.signal_analysis import SignalAnalysisOutput
from app.models.db.enums import ResearchSignal


class SynthesisInput(AgentModel):
    ticker: str
    signal_analysis: SignalAnalysisOutput
    devils_advocate: DevilsAdvocateOutput
    market_intel: MarketIntelOutput | None = None
    portfolio_id: str | None = Field(
        default=None,
        description="If set, Research was invoked from Portfolio — report stays tagged to that portfolio.",
    )


class SynthesisOutput(AgentModel):
    """The ResearchReport body. Persisted verbatim into research_reports.report_json."""

    ticker: str
    signal: ResearchSignal
    layers: VerdictLayer
    rationale: str = Field(description="Multi-paragraph narrative, renders below the VerdictCard.")
    recommended_position_pct: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Suggested portfolio weight if user adopts this call. None for HOLD/SELL.",
    )
    sources: list[SourceRef] = Field(min_length=1)
