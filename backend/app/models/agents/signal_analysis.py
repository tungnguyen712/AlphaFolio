"""Signal Analysis agent I/O (Opus).

Consumes retrieved data + market intel, produces a ranked list of bull/bear
signals with sources. This is where most of the "what does this *mean*"
reasoning happens; Devil's Advocate then attacks it.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.agents.common import AgentModel, SourceRef
from app.models.agents.data_retrieval import DataRetrievalOutput
from app.models.agents.market_intel import MarketIntelOutput


class Signal(AgentModel):
    name: str = Field(description="Short handle, e.g. 'insider_cluster_buy'.")
    direction: Literal["bullish", "bearish", "neutral"]
    strength: float = Field(ge=0.0, le=1.0)
    rationale: str
    sources: list[SourceRef] = Field(min_length=1)


class SignalAnalysisInput(AgentModel):
    ticker: str
    retrieved: DataRetrievalOutput
    market_intel: MarketIntelOutput | None = None


class SignalAnalysisOutput(AgentModel):
    ticker: str
    signals: list[Signal]
    flags: list[str] = Field(
        default_factory=list,
        description="Notes the Synthesis/DA agents should pay attention to (data gaps, anomalies).",
    )
