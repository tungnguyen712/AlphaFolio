"""Pydantic I/O schemas for the agent graph layer.

Separate from `app.models.db.*` — these do not hit the database. Agent nodes
consume the *Input type and emit the *Output type; the graph wires them.
"""
from app.models.agents.common import (
    AgentModel,
    AnalystChange,
    CongressTrade,
    InsiderTransaction,
    MacroContext,
    NewsItem,
    PriceSummary,
    SourceRef,
    VerdictLayer,
    VolumeAnomaly,
)
from app.models.agents.data_retrieval import (
    DataRetrievalInput,
    DataRetrievalOutput,
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
    "CongressTrade",
    "Counterargument",
    "DataRetrievalInput",
    "DataRetrievalOutput",
    "DevilsAdvocateInput",
    "DevilsAdvocateOutput",
    "HoldingSnapshot",
    "InsiderTransaction",
    "MacroContext",
    "MarketIntelInput",
    "MarketIntelOutput",
    "NewsItem",
    "PortfolioConstructionInput",
    "PortfolioConstructionOutput",
    "PriceSummary",
    "ProposedTrade",
    "RiskFactorsExcerpt",
    "Signal",
    "SignalAnalysisInput",
    "SignalAnalysisOutput",
    "SourceRef",
    "SynthesisInput",
    "SynthesisOutput",
    "VerdictLayer",
    "VolumeAnomaly",
]
