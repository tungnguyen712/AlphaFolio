"""Supply chain relationship endpoint.

GET /supply-chain/{ticker} — synchronous read-through, cached 24h.
No Celery task or SSE stream; supply chain data is stable enough for a
blocking GET with aggressive caching.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, DBSessionDep
from app.models.agents.supply_chain import SupplyChainReport
from app.services.data_providers._cache import cache_get, cache_set, make_cache_key
from app.services.supply_chain.pipeline import run_supply_chain

router = APIRouter(prefix="/supply-chain", tags=["supply-chain"])
logger = logging.getLogger(__name__)

_REPORT_TTL = 24 * 60 * 60  # 24 hours — supply chains change slowly


@router.get("/{ticker}", response_model=SupplyChainReport)
async def get_supply_chain(
    ticker: str,
    user: CurrentUserDep,
    db: DBSessionDep,
    refresh: bool = False,
) -> SupplyChainReport:
    upper = ticker.upper().strip()
    if not upper.isalpha() or len(upper) > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid ticker")

    cache_key = make_cache_key("sc.report.v9", ticker=upper)
    if not refresh:
        cached = await cache_get(cache_key)
        if cached is not None:
            return SupplyChainReport.model_validate(cached)

    try:
        report = await run_supply_chain(upper)
    except Exception as exc:
        logger.warning("Supply chain flow failed for %s: %s", upper, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supply chain providers are temporarily unavailable. Please try again shortly.",
        ) from exc

    if not report.relationships:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No supply chain data found for {upper}. "
                   "The ticker may not be SEC-listed or have insufficient public filings.",
        )

    await cache_set(cache_key, report.model_dump(mode="json"), _REPORT_TTL)
    return report
