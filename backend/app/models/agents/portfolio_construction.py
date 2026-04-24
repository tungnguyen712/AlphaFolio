"""Portfolio Construction agent I/O (Sonnet).

Takes current holdings + risk profile + a set of candidate research verdicts,
proposes a set of trades. Output carries its own verdict/top-3/uncertainty so
the PortfolioRecommendation surface renders in VerdictCard too.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.models.agents.common import AgentModel, VerdictLayer
from app.models.agents.synthesis import SynthesisOutput
from app.models.db.enums import AssetClass, RiskProfile


class HoldingSnapshot(AgentModel):
    ticker: str
    shares: Decimal
    avg_cost: Decimal
    asset_class: AssetClass
    market_value_usd: Decimal | None = None


class PortfolioConstructionInput(AgentModel):
    portfolio_id: str
    holdings: list[HoldingSnapshot]
    cash_balance: Decimal
    risk_profile: RiskProfile
    candidates: list[SynthesisOutput] = Field(
        default_factory=list,
        description="Research verdicts up for consideration — e.g. accepted pending positions.",
    )
    objective: str = Field(
        default="maintain risk profile and integrate new convictions",
        description="Free-text objective for this run. Keeps the reasoning focused.",
    )


class ProposedTrade(AgentModel):
    ticker: str
    action: Literal["buy", "sell", "trim", "add"]
    target_weight_pct: float = Field(ge=0.0, le=1.0)
    rationale: str
    links_to_report_ticker: str | None = Field(
        default=None,
        description="If this trade traces back to a research verdict, the ticker of that report.",
    )


class PortfolioConstructionOutput(AgentModel):
    portfolio_id: str
    layers: VerdictLayer
    proposed_trades: list[ProposedTrade]
    target_allocations: dict[str, float] = Field(
        description="Ticker -> target portfolio weight (0..1). Must sum to <= 1.0.",
    )
    rationale: str
