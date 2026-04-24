"""Manual verification script for step 2 provider layer.
Run: docker compose exec backend uv run python tests/verify_providers.py
"""
import asyncio

from app.services.data_providers.sec_edgar import (
    _fetch_filings_index,
    _resolve_cik,
    fetch_10k_excerpts,
    fetch_form4_transactions,
)
from app.services.data_providers.tavily import fetch_news


async def main() -> None:
    cik_info = await _resolve_cik("NVDA")
    print("NVDA CIK:", cik_info)

    idx = await _fetch_filings_index(cik_info["cik"], form_type="4", lookback_days=180)
    print(f"Form 4 filings in last 180d: {len(idx['filings'])}")
    if idx["filings"]:
        print("  most recent:", idx["filings"][0])

    txs = await fetch_form4_transactions("NVDA", lookback_days=90)
    print(f"Parsed open-market Form 4 transactions (90d): {len(txs['insider_filings'])}")
    for tx in txs["insider_filings"][:3]:
        print(
            f"  {tx['filed_at']} {tx['filer']} ({tx['role']}): "
            f"{tx['transaction']} {tx['shares']} @ {tx['price']} = ${tx['value_usd']:,.0f}"
        )

    tenk = await fetch_10k_excerpts("NVDA")
    print(f"10-K filed: {tenk['filed_at']}")
    print(f"Risk factors excerpt (first 300 chars):\n  {tenk['risk_factors_excerpt'][:300]}...")

    print("\n--- Tavily news ---")
    news = await fetch_news("NVDA", lookback_days=14)
    items = news["news_items"]
    print(f"Got {len(items)} news items")
    for item in items[:3]:
        src = item["source"]
        headline = item["headline"][:80]
        url = item["url"]
        print(f"  [{src}] {headline}")
        print(f"    {url}")

    print("\n--- Tavily news ---")
    news = await fetch_news("NVDA", lookback_days=14)
    items = news["news_items"]
    print(f"Got {len(items)} news items")
    for item in items[:3]:
        src = item["source"]
        headline = item["headline"][:80]
        url = item["url"]
        print(f"  [{src}] {headline}")
        print(f"    {url}")



asyncio.run(main())
