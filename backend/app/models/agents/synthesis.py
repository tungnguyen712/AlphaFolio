"""Synthesis agent I/O (Opus).

Final judge. Weighs Signal Analysis + Devil's Advocate, emits the verdict/
top-3-signals/key-uncertainty surface the UI renders in VerdictCard.
Also produces a plain-English rationale the user can read.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from app.models.agents.common import AgentModel, InsiderSummary, SourceRef, VerdictLayer
from app.models.agents.devils_advocate import DevilsAdvocateOutput
from app.models.agents.market_intel import MarketIntelOutput
from app.models.agents.signal_analysis import SignalAnalysisOutput
from app.models.db.enums import ResearchSignal


SECTION_HEADINGS: list[str] = [
    "Recommendation",
    "Investment Thesis",
    "Top Signals",
    "Valuation Bridge",
    "Key Uncertainties",
    "Devil's Advocate",
    "Data Quality",
    "Final Rationale",
]


class ScenarioCase(AgentModel):
    label: Literal["bull", "base", "bear"]
    price_target: float | None = None
    implied_upside_pct: float | None = None
    key_assumption: str


class ValuationBridge(AgentModel):
    """Structured price/valuation context assembled before synthesis.

    Scenarios use simple anchor multiples from current price when fundamental
    data (forward PE, EV/revenue) is unavailable. missing_fields lists what
    would improve the analysis.
    """

    current_price: float | None = None
    price_timestamp: date | None = None
    market_cap: float | None = None
    forward_pe: float | None = None
    ev_revenue: float | None = None
    scenarios: list[ScenarioCase] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class ConfidenceBreakdown(AgentModel):
    """Explainable confidence — positive and negative contributor strings."""

    positive_contributors: list[str] = Field(default_factory=list)
    negative_contributors: list[str] = Field(default_factory=list)
    final_score: float = Field(ge=0.0, le=1.0, default=0.5)


class ValidationResult(AgentModel):
    """Output of the deterministic pre-synthesis validation gate."""

    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    confidence_penalty: float = Field(ge=0.0, le=0.5, default=0.0)
    passed: bool = True


class SynthesisInput(AgentModel):
    ticker: str
    signal_analysis: SignalAnalysisOutput
    devils_advocate: DevilsAdvocateOutput
    market_intel: MarketIntelOutput | None = None
    portfolio_id: str | None = Field(
        default=None,
        description="If set, Research was invoked from Portfolio — report stays tagged to that portfolio.",
    )
    in_portfolio: bool = Field(
        default=False,
        description="True if the user already holds this ticker in any portfolio.",
    )
    current_price: float | None = Field(
        default=None,
        description="Most recent closing price in USD (PriceSummary.latest). Baseline for target math.",
    )
    insider_summary: InsiderSummary | None = None
    valuation_bridge: ValuationBridge | None = None
    validation_result: ValidationResult | None = None
    as_of_date: date | None = Field(
        default=None,
        description="Set only for historical research runs. All data timestamps at or before this date are intentional, not stale.",
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
    valuation_bridge: ValuationBridge | None = None
    confidence_breakdown: ConfidenceBreakdown | None = None
    validation_result: ValidationResult | None = None
    insider_summary: InsiderSummary | None = None
    report_sections: dict[str, str] | None = Field(
        default=None,
        description=(
            "Parsed sections from rationale keyed by heading name. "
            "Populated server-side by parsing ## headings. "
            "None for reports generated before this field was added."
        ),
    )
