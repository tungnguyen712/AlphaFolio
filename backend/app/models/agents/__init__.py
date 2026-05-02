"""Pydantic I/O schemas for the agent graph layer.

Separate from `app.models.db.*` — these do not hit the database. Agent nodes
consume the *Input type and emit the *Output type; the graph wires them.
"""
from app.models.agents.common import (
    AgentModel,
    AnalystChange,
    CongressTrade,
    ConsensusData,
    FilterReasonCode,
    FilteredNewsItem,
    FinancialFacts,
    FormDFiling,
    InsiderSummary,
    InsiderTransaction,
    MacroContext,
    MaterialEvent,
    NewsItem,
    OHLCVBar,
    PriceSummary,
    SourceQuality,
    SourceRef,
    VerdictLayer,
    VolumeAnomaly,
)
from app.models.agents.synthesis import (
    ConfidenceBreakdown,
    ScenarioCase,
    ValidationResult,
    ValuationBridge,
)
from app.models.agents.data_retrieval import (
    BusinessOverviewExcerpt,
    DataRetrievalInput,
    DataRetrievalOutput,
    RetrievalMode,
    RiskFactorsExcerpt,
)
from app.models.agents.devils_advocate import (
    Counterargument,
    DevilsAdvocateInput,
    DevilsAdvocateOutput,
)
from app.models.agents.market_intel import (
    MarketIntelInput,
    MarketIntelOutput,
)
from app.models.agents.portfolio_construction import (
    HoldingSnapshot,
    PortfolioConstructionInput,
    PortfolioConstructionOutput,
    ProposedTrade,
)
from app.models.agents.signal_analysis import (
    Signal,
    SignalAnalysisInput,
    SignalAnalysisOutput,
)
from app.models.agents.synthesis import SynthesisInput, SynthesisOutput

__all__ = [
    "AgentModel",
    "AnalystChange",
    "BusinessOverviewExcerpt",
    "ConfidenceBreakdown",
    "CongressTrade",
    "ConsensusData",
    "Counterargument",
    "DataRetrievalInput",
    "DataRetrievalOutput",
    "DevilsAdvocateInput",
    "DevilsAdvocateOutput",
    "FilterReasonCode",
    "FilteredNewsItem",
    "FinancialFacts",
    "FormDFiling",
    "HoldingSnapshot",
    "InsiderSummary",
    "InsiderTransaction",
    "MacroContext",
    "MaterialEvent",
    "MarketIntelInput",
    "MarketIntelOutput",
    "NewsItem",
    "OHLCVBar",
    "PortfolioConstructionInput",
    "PortfolioConstructionOutput",
    "PriceSummary",
    "ProposedTrade",
    "RetrievalMode",
    "RiskFactorsExcerpt",
    "ScenarioCase",
    "Signal",
    "SignalAnalysisInput",
    "SignalAnalysisOutput",
    "SourceQuality",
    "SourceRef",
    "SynthesisInput",
    "SynthesisOutput",
    "ValidationResult",
    "ValuationBridge",
    "VerdictLayer",
    "VolumeAnomaly",
]
