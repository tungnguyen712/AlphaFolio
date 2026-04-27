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
    "supplier"     – provides raw materials, components, IP, or non-manufacturing
                     services to the filer (e.g. memory chips, licensing)
    "customer"     – buys products or services from the filer; named accounts or
                     named customer categories with a specific revenue concentration %
    "manufacturer" – FABRICATES or MANUFACTURES finished products or wafers on behalf
                     of the filer under a contract manufacturing / foundry / ODM model.
                     THIS INCLUDES: semiconductor foundries (TSMC, Samsung foundry,
                     GlobalFoundries), ODMs, EMS providers (Foxconn, Flextronics).
                     USE THIS even if the filing says "supply" or "outsourced" —
                     if the company is making/fabricating the end product, it is a
                     manufacturer, not a supplier.
    "subsidiary"   – owned or controlled by the filer
    "parent"       – owns or controls the filer
- evidence_snippet: a direct verbatim quote from the text (max 150 characters) \
showing this relationship
- is_significant: true if the text uses "significant", "sole-source", "primary", \
"key", "principal", "major", "concentrated", or discloses a specific revenue/supply %

CRITICAL RULE — manufacturer vs supplier:
  If a company FABRICATES CHIPS, WAFERS, or FINISHED HARDWARE for the filer
  (e.g. "manufactured by TSMC", "fab partner", "foundry services", "wafer supply
  from [company] under manufacturing agreement"), classify as "manufacturer" ALWAYS.
  Only use "supplier" for companies providing raw inputs (substrates, gases,
  photomasks, memory, IP cores) that are NOT doing end-product fabrication.

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


_TAVILY_SYSTEM = """\
You are a financial data extractor. Given news article snippets about a company, \
extract any supply chain relationships that are explicitly mentioned.

For each relationship, provide:
- name: the specific company name (not generic descriptions like "cloud providers")
- relationship: one of "supplier", "customer", "manufacturer"
- evidence_snippet: a direct quote from the snippets (max 150 chars)
- is_significant: true if described as "key", "major", "primary", "sole", or "largest"

Only extract relationships where a specific company NAME is mentioned. \
Omit generic references without names. Omit the target company itself.\
"""


async def extract_supply_chain_from_tavily(snippets: list[dict], ticker: str) -> SupplyChainEntities:
    if not snippets:
        return SupplyChainEntities(entities=[])

    combined = "\n\n".join(
        f"[{s.get('headline', '')}]\n{s.get('snippet', '')}"
        for s in snippets[:10]
    )
    user = (
        f"Extract supply chain relationships for {ticker} from these news snippets:\n\n"
        f"{combined[:3500]}"
    )
    return await call_structured(
        tier=AgentTier.HAIKU,
        system=_TAVILY_SYSTEM,
        user=user,
        output_model=SupplyChainEntities,
        max_tokens=512,
    )
