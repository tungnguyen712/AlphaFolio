"""Devil's Advocate agent I/O (Opus).

Given the Signal Analysis output, generate the strongest bear case (or bull
case, if signals skew bearish). Synthesis weighs both before calling the
verdict.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.agents.common import AgentModel, SourceRef
from app.models.agents.signal_analysis import SignalAnalysisOutput


class Counterargument(AgentModel):
    claim: str
    severity: Literal["low", "medium", "high"]
    evidence: str
    sources: list[SourceRef] = Field(default_factory=list)


class DevilsAdvocateInput(AgentModel):
    ticker: str
    signal_analysis: SignalAnalysisOutput


class DevilsAdvocateOutput(AgentModel):
    ticker: str
    counterarguments: list[Counterargument]
    worst_case_scenario: str
