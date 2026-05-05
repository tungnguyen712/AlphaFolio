from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.models.agents.supply_chain import RelatedCompany
from app.services.supply_chain.pipeline import run_supply_chain


async def test_supply_chain_degrades_when_sec_cik_resolution_is_rate_limited() -> None:
    with (
        patch(
            "app.services.supply_chain.pipeline._resolve_cik",
            AsyncMock(side_effect=RuntimeError("SEC 429")),
        ),
        patch(
            "app.services.supply_chain.pipeline._safe_10k",
            AsyncMock(return_value=([], None, None)),
        ),
        patch("app.services.supply_chain.pipeline._safe_gleif", AsyncMock(return_value=[])),
        patch("app.services.supply_chain.pipeline._safe_wikidata", AsyncMock(return_value=[])),
        patch("app.services.supply_chain.pipeline._safe_wikipedia", AsyncMock(return_value=[])),
        patch("app.services.supply_chain.pipeline._safe_efts", AsyncMock(return_value=[])),
        patch(
            "app.services.supply_chain.pipeline._safe_tavily",
            AsyncMock(
                return_value=[
                    RelatedCompany(
                        name="Taiwan Semiconductor",
                        relationship="supplier",
                        confidence="low",
                        sources=["tavily"],
                    )
                ]
            ),
        ),
    ):
        report = await run_supply_chain("NVDA")

    assert report.ticker == "NVDA"
    assert report.company_name == "NVDA"
    assert report.relationships[0].name == "Taiwan Semiconductor"
    assert report.data_sources_used == ["tavily"]
