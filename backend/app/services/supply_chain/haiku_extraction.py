"""Haiku-powered extraction of supply chain entities from 10-K Item 1 text.

Called by pipeline.py after fetching Item 1 Business section. The result
is cached by the pipeline (key: sc.10k.haiku:{ticker}) with a 7-day TTL
matching the raw 10-K document cache — so Haiku is called at most once
per ticker per week regardless of how many users look up the same ticker.
"""
from __future__ import annotations

from app.models.agents.supply_chain import SupplyChainEntities
from app.services.llm.anthropic_client import AgentTier, call_structured

_SYSTEM = """\
You are a financial data extractor. Given the Business section (Item 1) from a \
SEC 10-K annual filing, extract all explicitly mentioned company relationships.

For each entity found, provide:
- name: the company or entity name exactly as written in the filing
- relationship: one of:
    "supplier"     – provides materials, components, or services to the filer
    "customer"     – buys products or services from the filer
    "manufacturer" – manufactures products on behalf of the filer (foundry, ODM)
    "subsidiary"   – owned or controlled by the filer
    "parent"       – owns or controls the filer
- evidence_snippet: a direct verbatim quote from the text (max 150 characters) \
showing this relationship
- is_significant: true if the text uses "significant", "sole-source", "primary", \
"key", "principal", "major", "concentrated", or discloses a specific revenue/supply %

Rules:
- Only extract relationships explicitly stated — do not infer or guess.
- Skip generic "customers", "suppliers" without a specific company name.
- Skip government agencies, regulatory bodies, and trade associations.
- If the same company appears in multiple roles, emit one entry per role.\
"""


async def extract_supply_chain_from_10k(item1_text: str, ticker: str) -> SupplyChainEntities:
    user = (
        f"Extract supply chain relationships for {ticker} from this "
        f"10-K Item 1 Business section:\n\n{item1_text[:4500]}"
    )
    return await call_structured(
        tier=AgentTier.HAIKU,
        system=_SYSTEM,
        user=user,
        output_model=SupplyChainEntities,
        max_tokens=1024,
    )
