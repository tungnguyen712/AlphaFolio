"""Pydantic models for the supply chain flow."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RelationshipKind = Literal["supplier", "customer", "subsidiary", "parent", "manufacturer"]
ConfidenceLevel = Literal["high", "medium", "low"]


class RelatedCompany(BaseModel):
    name: str
    ticker: str | None = None
    relationship: RelationshipKind
    confidence: ConfidenceLevel
    sources: list[Literal["gleif", "wikidata", "10k", "sec_efts", "tavily", "wikipedia"]]
    evidence_snippet: str | None = None
    research_url: str | None = None  # /research?ticker=X — cross-link to Research flow


class SupplyChainReport(BaseModel):
    ticker: str
    company_name: str
    generated_at: str              # ISO 8601
    relationships: list[RelatedCompany]
    filing_url: str | None = None  # source 10-K URL
    filed_at: str | None = None
    data_sources_used: list[str]
    notes: str | None = None


# ---------------------------------------------------------------------------
# Haiku extraction schema — used by haiku_extraction.py
# ---------------------------------------------------------------------------


class ExtractedEntity(BaseModel):
    name: str
    relationship: RelationshipKind
    evidence_snippet: str  # direct quote from text, ≤150 chars
    is_significant: bool   # True if "sole-source", "significant", "primary", etc.


class SupplyChainEntities(BaseModel):
    entities: list[ExtractedEntity]
