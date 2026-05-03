"""Haiku-powered extraction of supply chain entities from text sources.

Three extractors, each with a system prompt tuned to its source:
  extract_supply_chain_from_10k   — SEC 10-K Item 1 (manufacturing-focused)
  extract_supply_chain_from_tavily — Tavily news snippets (broad)
  extract_supply_chain_from_wikipedia — Wikipedia article (broadest, covers service companies)

Results are cached by the pipeline layer (separate keys per source).
"""
from __future__ import annotations

from app.models.agents.supply_chain import SupplyChainEntities
from app.services.llm.anthropic_client import AgentTier, call_structured

# ---------------------------------------------------------------------------
# 10-K extractor
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are a financial data extractor. Given the Business section (Item 1) from a \
SEC 10-K annual filing, extract all explicitly mentioned company relationships.

For each entity found, provide:
- name: the company or entity name exactly as written in the filing
- relationship: one of:
    "supplier"     – provides raw materials, components, IP, cloud infrastructure
                     (AWS, Azure, GCP), CDN services, technology platform vendors,
                     content licensors, payment processors, or any external service
                     or input the filer relies on for core operations
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
    "competitor"   – explicitly named as a competitor, rival, or competing vendor
                     in the same market or product category. Only use when the
                     text directly identifies them as a competitor — do NOT infer
                     from similar product descriptions alone.
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
        f"10-K Item 1 Business section:\n\n{item1_text[:55000]}"
    )
    return await call_structured(
        tier=AgentTier.HAIKU,
        system=_SYSTEM,
        user=user,
        output_model=SupplyChainEntities,
        max_tokens=4096,
    )


# ---------------------------------------------------------------------------
# Tavily extractor
# ---------------------------------------------------------------------------

_TAVILY_SYSTEM = """\
You are a financial data extractor. Given news article snippets about a company, \
extract any supply chain relationships that are explicitly mentioned.

For each relationship, provide:
- name: the specific company name (not generic descriptions like "cloud providers")
- relationship: one of:
    "supplier"     – provides components, raw materials, cloud infrastructure,
                     CDN services, technology platform vendors, content licensors,
                     payment processors, or any external service or input the
                     company relies on for core operations
    "customer"     – buys products or services from the target company
    "manufacturer" – FABRICATES or MANUFACTURES chips, wafers, or finished hardware
                     for the target company (foundry, ODM, EMS). Examples: TSMC,
                     Samsung foundry, GlobalFoundries, Foxconn, Intel Foundry Services.
                     Use "manufacturer" even if the snippet says "supply" — if the
                     company is making/fabricating the product, it is a manufacturer.
    "competitor"   – explicitly named as a competitor or rival in the same market.
                     Only use when the text directly says they compete — do NOT infer.
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
        for s in snippets[:15]
    )
    user = (
        f"Extract supply chain relationships for {ticker} from these news snippets:\n\n"
        f"{combined[:8000]}"
    )
    return await call_structured(
        tier=AgentTier.HAIKU,
        system=_TAVILY_SYSTEM,
        user=user,
        output_model=SupplyChainEntities,
        max_tokens=2048,
    )


# ---------------------------------------------------------------------------
# Wikipedia extractor — broadest, covers service/media companies
# ---------------------------------------------------------------------------

_WIKIPEDIA_SYSTEM = """\
You are a financial data extractor. Given a Wikipedia article about a company, \
extract all explicitly mentioned business relationships with other named companies.

For each relationship found, provide:
- name: the specific company or entity name exactly as written in the article
- relationship: one of:
    "supplier"     – provides cloud infrastructure (AWS, Azure, GCP), CDN services,
                     content licensing, platform services, technology vendors, payment
                     processors, raw materials, components, IP, or any external service
                     or input the company depends on for core operations
    "customer"     – buys products or services from the subject company; named accounts
                     or named customer categories with revenue or volume context
    "manufacturer" – physically fabricates or manufactures products, hardware, or wafers
                     for the subject company (foundry, ODM, EMS, contract manufacturer)
    "subsidiary"   – owned or controlled by the subject company (acquired companies,
                     wholly-owned divisions that are separate legal entities)
    "parent"       – owns or controls the subject company
    "competitor"   – explicitly named as a competitor, rival, or competing company
                     in the same market or product category. Only use when the
                     article directly states they compete — do NOT infer from
                     similar business descriptions alone.
- evidence_snippet: a direct verbatim quote from the article (max 150 characters)
- is_significant: true if described as "key", "major", "primary", "largest",
  "strategic", "exclusive", or "primary" partner, or if a percentage is given

Rules:
- Only extract relationships explicitly stated in the article — do not infer.
- Skip generic references without a specific company name.
- Skip government agencies, regulatory bodies, and trade associations.
- Skip individual people — only extract companies and organizations.
- For streaming/media companies: cloud providers (AWS, GCP), CDN providers,
  content studios, and device partners (Roku, Apple TV, Samsung TV) are
  valid suppliers or customers depending on the direction of the relationship.
- If the same company appears in multiple roles, emit one entry per role.\
"""


async def extract_supply_chain_from_wikipedia(
    article_text: str, ticker: str
) -> SupplyChainEntities:
    if not article_text:
        return SupplyChainEntities(entities=[])

    user = (
        f"Extract supply chain relationships for {ticker} from this "
        f"Wikipedia article:\n\n{article_text[:8000]}"
    )
    return await call_structured(
        tier=AgentTier.HAIKU,
        system=_WIKIPEDIA_SYSTEM,
        user=user,
        output_model=SupplyChainEntities,
        max_tokens=2048,
    )
