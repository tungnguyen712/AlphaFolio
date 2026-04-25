"""Shared Pydantic types used across agent I/O schemas.

Provider-facing shapes (InsiderTransaction, NewsItem, CongressTrade,
AnalystChange, PriceSummary, MacroContext) are aligned with the dicts returned
by `app/services/data_providers/*`. Aliases are used where the provider's wire
shape uses a Python keyword (`from`/`to`) or a short key we'd rather expand.
Keep all provider-shape types here — if a provider's payload changes, this is
the one edit.
"""
from __future__ import annotations

from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class AgentModel(BaseModel):
    """Strict-by-default base for every agent I/O type.

    `extra="forbid"` catches provider/LLM drift at the boundary instead of
    letting junk flow downstream. `populate_by_name=True` lets us use tidy
    Python names while still accepting wire-shape aliases (e.g. `from`).
    """

    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True)


class SourceRef(AgentModel):
    """Citation for a claim. Every LLM-derived signal must point at one."""

    kind: Literal["sec_filing", "news", "congress_trade", "price_data", "transcript"]
    url: HttpUrl | None = None
    label: str
    retrieved_at: date | None = None


class InsiderTransaction(AgentModel):
    filer: str
    role: str | None = None
    transaction: Literal["buy", "sell"]
    shares: float
    price: float
    value_usd: float
    filed_at: date
    form: str = "Form 4"
    source_url: HttpUrl


class CongressTrade(AgentModel):
    """Matches Quiver's shape: member name + disclosed dollar range."""

    member: str
    party: str | None = None
    transaction: Literal["buy", "sell", "exchange"]
    amount_range_usd: tuple[int, int] | list[int] | None = None
    filed_at: date | None = None
    source: str | None = None


class FormDFiling(AgentModel):
    """Form D = notice of unregistered private securities sale. The most
    information-dense public source for funding-round size on private
    companies — issuer reports total offering amount + amount sold to date.
    Most useful for pre-IPO research; usually empty for established public
    companies (which don't sell unregistered securities to the same degree).
    """

    issuer_name: str
    accession: str
    filed_at: date | None = None
    date_of_first_sale: date | None = None
    total_offering_amount_usd: float | None = None
    total_amount_sold_usd: float | None = None
    source_url: HttpUrl | None = None

    @field_validator("filed_at", "date_of_first_sale", mode="before")
    @classmethod
    def _coerce_blank_date(cls, value: Any) -> Any:
        """Form D issuers sometimes file with blank date fields. Treat any
        empty/whitespace-only string as None so we don't reject the whole row."""
        if isinstance(value, str) and not value.strip():
            return None
        return value


class PriceSummary(AgentModel):
    """Point-in-time price summary from the Polygon stub.

    Not a time series — a precomputed rollup that's good enough for MVP
    signal weighting. Swap for a real candle series when we move off the stub.
    """

    latest: float
    pct_30d: float | None = None
    pct_90d: float | None = None
    iv_30d: float | None = None


class VolumeAnomaly(AgentModel):
    date: date
    z_score: float
    note: str | None = None


class AnalystChange(AgentModel):
    firm: str
    action: Literal["upgrade", "downgrade", "initiate", "reiterate"]
    from_rating: str | None = Field(default=None, alias="from")
    to_rating: str = Field(alias="to")
    price_target_from: float | None = Field(default=None, alias="pt_from")
    price_target_to: float | None = Field(default=None, alias="pt_to")
    published_at: date | None = Field(default=None, alias="date")


class NewsItem(AgentModel):
    headline: str
    source: str
    url: HttpUrl
    published: date | None = None
    score: float | None = None
    snippet: str = Field(default="", max_length=1000)

    @field_validator("published", mode="before")
    @classmethod
    def _coerce_published(cls, value: Any) -> Any:
        """Tavily returns RFC-2822 ("Tue, 14 Apr 2026 20:36:49 GMT") alongside
        plain ISO dates. Normalize both to `date` here so downstream agents
        don't each have to parse."""
        if value is None or isinstance(value, date):
            return value
        if not isinstance(value, str):
            return value
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        try:
            return parsedate_to_datetime(s).date()
        except (TypeError, ValueError):
            return None


class MacroContext(AgentModel):
    """Matches the Polygon-stub macro payload for now. Fields optional so a
    missing fixture yields an empty-but-valid object instead of a validation
    error."""

    fed_funds: float | None = None
    ten_yr_yield: float | None = None
    dxy: float | None = None
    semis_index_90d_pct: float | None = None
    regime: str | None = None
    key_drivers: list[str] = Field(default_factory=list)


class VerdictLayer(AgentModel):
    """The three layers that every recommendation surface MUST expose.

    Product rule: verdict -> top 3 signals -> key uncertainty. Embedded in any
    output that shows up in a `VerdictCard` on the frontend.
    """

    verdict: str = Field(description="One-line actionable call (e.g. 'BUY with 2% position cap').")
    top_3_signals: list[str] = Field(
        min_length=1,
        max_length=3,
        description="Strongest supporting signals, human-readable, ordered by weight.",
    )
    key_uncertainty: str = Field(
        description="The single biggest thing that could flip the call. Non-empty."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Model-assigned probability the verdict is correct."
    )
